---
name: python-project-porting
description: Playbook for adding a package's riscv64 wheel build to the RISE python-wheels repo (published to pypi.riseproject.dev). Use when porting a Python package to riscv64, authoring or debugging a .github/workflows/build-<pkg>.yml, wiring cibuildwheel/maturin/setuptools-rust builds for riscv64, triaging manylinux_riscv64 build or test failures, deciding whether a package is feasible to port, or handling the PR/publish/licensing steps for a python-wheels contribution.
license: See repository LICENSE
compatibility: Designed for Claude Code in the riseproject-dev/python-wheels repo. Uses git, gh (needs workflow and project token scopes), and docker/podman for local QEMU + aarch64 validation. Builds run on ubuntu-24.04-riscv self-hosted runners.
metadata:
  source: Distilled from the python-wheels porting playbook (originally CLAUDE.md), generalized from the protobuf port onward.
---

# Python project porting (riscv64 wheels)

Guidance for adding a new package's riscv64 wheel build to this repo and publishing it to
`pypi.riseproject.dev`. The 192 hard-won "gotchas" are split by theme under
[`references/gotchas/`](references/gotchas/) and routed by
[references/gotchas-index.md](references/gotchas-index.md) — **skim the index before you start,
then read the themed file for the step you're on.** Many gotchas each cost a full CI cycle
(minutes for a simple package, hours for one that compiles a large C++ world).

This SKILL.md is the navigator: the core loop and the rules that are always in force. Depth
lives in the reference files linked at the bottom — load them as the task calls for them.

## What this repo does

Builds riscv64 wheels for packages that don't ship them on public PyPI, and
publishes them to `pypi.riseproject.dev`. Each package gets a
`.github/workflows/build-<pkg>.yml`. Wheels are consumed on `ubuntu-24.04-riscv`
self-hosted runners.

Four structural goals (from the [development guide](https://pypi.riseproject.dev/python-wheels/development.html)):
1. give users a simple index to install riscv64 wheels from;
2. build them with workflows that **closely mirror each upstream project's own CI**,
   narrowed to riscv64;
3. carry tooling that tracks upstream releases, automates version bumps, and makes
   deprecation easy once upstream ships riscv64 itself;
4. serve as evidence to upstream maintainers that riscv64 support is cheap to add.

Goal 2 is the one that constrains daily work: **a workflow that diverges from upstream's
for no reason is a defect**, because these files are meant to be handed to upstream as a
working precedent.

## Non-negotiable rules

These are low-freedom guardrails — each has been reinforced by a revert, a rejected commit,
or a repeated ask. Follow them exactly; the reference files explain the why.

- **Never write outside the repository.** Worktrees go in `.claude/worktrees/<pkg>`, scratch
  files in `.git/pw-scratch/<pkg>`, local lock state in `.git/pw-locks/`. No files in `$HOME`,
  `~/.local/bin`, `/tmp`, or sibling directories, and **no installing software** on the host
  (brew/apt/dnf/npm/pip). If you think you need either, ask first.
- **A port adds files only under `.github/workflows/` and `patches/<pkg>/<version>/`.** Never
  create a `ci/` directory or any helper script, Dockerfile, or test file elsewhere — not for
  a build step, not for a smoke test, not "just this once." Anything a job needs that is not a
  patch is **written by the workflow at run time** from a `run:` heredoc (gotcha 7). Treat a
  new top-level path as a hard stop, not a judgement call. Full rules:
  [references/environment-and-auth.md](references/environment-and-auth.md).
- **Commit identity is `Ludovic Henry <git@ludovic.dev>`** and is already configured. Never
  pass `-c user.email`/`user.name` or set `GIT_AUTHOR_*`/`GIT_COMMITTER_*` (in particular not
  the address from your own session context — it differs). A `pre-commit` hook rejects any
  other identity and any workflow adding `BUILD_VERBOSITY`; if it fires, fix the command,
  don't bypass the hook.
- **Both workflow triggers, always** (`workflow_dispatch` **and** `pull_request: paths`). The
  `pull_request` trigger is the only thing that registers a new workflow with GitHub; without
  it dispatch and `Trigger:` lines both 404 (gotchas 45/54). Shipping `workflow_dispatch`
  alone is why #364 was reverted by #391.
- **Default to NO comments in workflows** — they are read as reference. One "why" line only for
  a genuine non-obvious deviation; never narrate standard steps.
- **Never set `CIBW_BUILD_VERBOSITY`** — drop it if you inherit it from a template.
- **Start from upstream's own build/test workflow, then delete** everything that isn't Linux
  glibc/musl, and only then apply the riscv64 changes. See
  [references/workflow-anatomy.md](references/workflow-anatomy.md).
- **Pushing workflow files needs `workflow` scope** on the gh token; the post-merge steps need
  `project` scope. Refresh with `gh auth refresh -h github.com -s workflow` (and `-s project`).

## Working process

Given a package to port, the loop is always the same (project-specific inputs —
name, repo, version, upstream build docs — come from the invoking prompt):

1. Branch `<pkg>` from `origin/main` and work in a dedicated git worktree, created at
   **`.claude/worktrees/<pkg>`** inside this repo (locally ignored via `.git/info/exclude`).
   Never put a worktree — or anything else — outside the repository.
2. Add `.github/workflows/build-<pkg>.yml` following the playbook below and
   [references/workflow-anatomy.md](references/workflow-anatomy.md).
3. Validate locally (gotcha 9), then push to `origin` and open a PR. The
   `pull_request: paths` trigger is what produces the **first** run of a new workflow, and
   that run is what registers it with GitHub. **A `Trigger:` line alone cannot start a new
   package's build** — dispatch resolves the workflow through the registry and answers
   `HTTP 404` until a `pull_request` run exists (gotcha 54). Once the workflow is
   registered (or already on `main`), a `Trigger: <pkg>:<tag>` line in the **PR
   description** — one per version, `Trigger: numpy:v2.5.1` — lets `pr-trigger.yml` build
   a different version without editing the workflow.
4. Watch CI, triage failures, iterate until every matrix job is green and the
   `publish` job dry-runs cleanly.
5. When the wheels build and tests pass, reply to any review threads, then
   record reusable, project-agnostic learnings back into this skill — add them to the
   matching themed file under [`references/gotchas/`](references/gotchas/) as the next unused
   number, and add a row to [references/gotchas-index.md](references/gotchas-index.md) (see the
   index header for the numbering rules).

## Porting playbook (do these in order)

1. **Read the upstream project's own build + release docs first.** Find how *they*
   build their wheels and sdist. Don't assume `python -m build` works (see gotcha 1).

2. **Fetch and inspect the real PyPI sdist** to learn its layout and whether it's
   self-contained:
   ```
   pip download <pkg>==<ver> --no-binary :all: --no-deps -d /tmp/x
   tar tzf /tmp/x/<pkg>-*.tar.gz | head -50
   ```
   Then try to build a wheel from it locally (works even on x86/aarch64 — proves
   portability before you burn a riscv CI cycle):
   ```
   pip wheel /tmp/x/<pkg>-*.tar.gz --no-deps --no-build-isolation -w /tmp/out
   ```
   If that succeeds with no special toolchain, the riscv bdist job can be minimal.

3. **Decide where the sdist comes from** (only relevant for the sdist→bdist shape).
   **Always build the sdist yourself from an upstream checkout** — never wire the
   prebuilt PyPI sdist in as the CI build input (fetch it only for the local
   *inspection* in step 2). Use `python -m build --sdist` from the checkout if the
   project supports it; otherwise whatever the project uses (protobuf: Bazel
   `//python/dist:source_wheel`). Heads-up for Rust/maturin projects: a
   locally-built sdist may pin dependencies *differently* than the released PyPI
   sdist — see gotcha 10.

4. **Map the git tag to the Python version** (see gotcha 3). Take the tag as the
   workflow input; derive `package_version` from the built sdist filename.

5. **Identify native deps** the bdist needs at build time. Three cases: (a) none
   bundled → add `CIBW_BEFORE_BUILD` to build them in-container (cffi builds libffi
   that way); (b) the sdist bundles its C sources (protobuf bundles upb/utf8_range)
   → no before-build needed; (c) the dep is another Python wheel we already ship →
   `pip install` it from our registry in `CIBW_BEFORE_BUILD` (see gotcha 17).

6. **Wire up real testing** — mirror how upstream tests its wheels (gotcha 6).

7. **Validate locally, then push** (gotcha 9). Open a PR; the `pull_request` path
   trigger runs CI. Watch, triage, iterate.

## Reference files

Load these on demand — they are one level deep from here.

- **[references/workflow-anatomy.md](references/workflow-anatomy.md)** — the anatomy of a
  `build-<pkg>.yml`: standard triggers, UV/env vars, the interpreter matrix, `setup-uv`
  vs `setup-python`, the two build shapes (sdist→bdist, build-from-checkout), driving the
  container yourself, and the shared `publish` job.
- **[references/gotchas-index.md](references/gotchas-index.md)** — the router for all 190
  gotchas: a topic→file table and the full number→file lookup. Start here when you have a
  symptom but not a number, or to resolve a "gotcha N" citation to its file. The gotchas
  themselves live in [`references/gotchas/`](references/gotchas/), split by theme (listed
  under "Finding the right gotcha" below).
- **[references/patching-and-licensing.md](references/patching-and-licensing.md)** — when a
  patch is justified, the `patches/<pkg>/<version>/` mechanics, the five `Upstream-Status:`
  types, and licence/GPL-sources compliance (the `gpl_sources` job).
- **[references/pr-and-publishing.md](references/pr-and-publishing.md)** — the post-merge
  publish/issue/project steps, the PR description template (use it verbatim), and the PR/CI
  conventions (draft status, no hard-wrapping, dry-run checks).
- **[references/environment-and-auth.md](references/environment-and-auth.md)** — where files
  may and may not go, commit identity, token scopes, and remotes.

### Finding the right gotcha

The 190 gotchas are split into themed files under `references/gotchas/`. **Read the one file
that matches your current step** rather than loading them all — each file opens with an
`## In this file` list of its entries. Three ways in:

1. **By symptom (no number yet)** — jump to the file whose theme matches, or grep the whole
   set: `grep -rn '<term>' references/gotchas/`. The map:
   - `feasibility-and-triage.md` — is this worth porting? all-`py3-none-*` wheels, vendored blobs, conda/CUDA-blocked deps, source-only distros.
   - `sdist-source-and-versioning.md` — where the sdist comes from; git-tag≠version; dirty-tree/`setuptools_scm`/`tag_build` version poisoning; no-tag upstreams.
   - `cibuildwheel-matrix-and-abi3.md` — `{project}` vs `{package}`, the interpreter matrix, abi3 tag collapse, the `CIBW_ENVIRONMENT` cascade, YAML folding, heredocs.
   - `rust-maturin-and-pyo3.md` — maturin/setuptools-rust/pyo3, rustup targets, `MATURIN_PEP517_ARGS`, cargo features, cross-compile pre-flight.
   - `native-build-bazel-and-drivers.md` — Bazel bootstrap, driving the container yourself, rules_python, per-interpreter loops, vcpkg-image replacement.
   - `manylinux-image-and-toolchain.md` — Rocky 10 packages, EPEL/CRB, GCC/binutils versions, RVV/SIMD gates, perl/gconv.
   - `native-deps-and-linking.md` — build-once C++, the dep-wheel pattern, static-vs-shared, auditwheel `--exclude`, `patchelf` RPATH, missing symbols.
   - `compiled-vs-pure-detection.md` — is the wheel actually compiled? the `.so` proof, mislabeled pure wheels, the require-extension knob, free-threading declaration.
   - `dependencies-and-registry.md` — checking pypi.riseproject.dev, per-interpreter coverage, `PIP_ONLY_BINARY`, matrix trimming, test-venv rebuilds.
   - `build-tool-drift-and-pins.md` — Cython/setuptools/numpy version drift, `--no-build-isolation`, `PIP_BUILD_CONSTRAINT`, a published wheel breaking another package.
   - `testing-and-shadowing.md` — tests importing the checkout instead of the wheel: `CIBW_TEST_SOURCES`, rootdir shadowing, renaming the staged package, in-container build products.
   - `pytest-config-servers-and-selection.md` — staging the pytest ini (`addopts`/`markers`/`log_level`), servers in `before-test`, `-W error`, choosing which tests run.
   - `test-failures-and-flakes.md` — a job fails/segfaults/flakes: refcount bugs, xdist crashes, slow-runner races, libgomp/OpenMP, numeric divergence, native backtraces.
   - `licensing-and-gpl.md` — vendored-dep LICENSE files, PEP 639 vs setuptools globs, REUSE `LICENSES/`, the `gpl_sources` job, SBOMs.
   - `local-validation-and-rehearsal.md` — local `pip wheel`, QEMU, the aarch64 rehearsal and its traps, `pip download` resolution checks.
   - `pr-ci-and-maintainer.md` — registering a new workflow, `Trigger:` lines, action-SHA pins, maintainer holds/cancellations, post-merge publish.
2. **By number** — a "gotcha N" citation (in these files or in workflow comments). Find its
   file in the number→file table of [references/gotchas-index.md](references/gotchas-index.md),
   then `grep -n '^N\. ' references/gotchas/<file>`.
3. **Numbers are stable IDs, not positions** — they are *not* contiguous, and four (33, 55,
   56, 57) are **reused** with different content across two themes each. When a citation is
   ambiguous, the topic decides which one; the index marks the reused rows.
