# CLAUDE.md — python-wheels porting playbook

Guidance for adding a new package's riscv64 wheel build to this repo. Written
from the protobuf port; generalized so the next one is faster. Read the
"Gotchas" section before you start — several cost a full CI cycle each (minutes
for a simple package, hours for one that compiles a large C++ world).

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

## Working process

Given a package to port, the loop is always the same (project-specific inputs —
name, repo, version, upstream build docs — come from the invoking prompt):

1. Branch `<pkg>` from `origin/main` and work in a dedicated git worktree, created at
   **`.claude/worktrees/<pkg>`** inside this repo (locally ignored via `.git/info/exclude`).
   Never put a worktree — or anything else — outside the repository.
2. Add `.github/workflows/build-<pkg>.yml` following the playbook below.
3. Validate locally (gotcha 9), then push to `origin` and open a PR with a
   `Trigger: <pkg>:<tag>` line in the **PR description** for every version you want
   built (`Trigger: numpy:v2.5.1`). `build-<pkg>.yml` is `workflow_dispatch`-only —
   it has no `pull_request` trigger of its own, so a `Trigger:` line is the only
   thing that ever starts a run; editing the workflow file alone does nothing.
   `pr-trigger.yml` parses the directives, dispatches each via `workflow_dispatch`,
   and posts one GitHub Check Run per directive through the Checks API — a
   properly named, real check on the PR (`build-<pkg>.yml @ <version>`) whose
   "Details" link goes straight to the dispatched run, with real
   pending/success/failure/cancelled status mirrored via `gh run watch`.
4. Watch CI, triage failures, iterate until every matrix job is green and the
   `publish` job dry-runs cleanly.
5. When the wheels build and tests pass, reply to any review threads, then
   record reusable, project-agnostic learnings back into this file.

## Anatomy of a build-<pkg>.yml

Standard trigger (copy from an existing workflow) — `workflow_dispatch` only, no
`pull_request` block. A per-package `pull_request: paths` trigger was tried and
dropped: with 40+ package workflows, any PR touching several of their files fired
that many separate (mostly skipped) runs, flooding the Actions list for no benefit
— `pr-trigger.yml`'s Checks-API relay (step 3 above) gives the same visible,
per-directive status without it:

```yaml
on:
  workflow_dispatch:
    inputs:
      version: { description: '<pkg> version/tag', required: true, default: '<latest stable>' }
```

UV env vars (`UV_EXTRA_INDEX_URL`, `UV_INDEX_STRATEGY`, `UV_ONLY_BINARY`) are **only** needed
if the workflow has steps that actually invoke `uv` (e.g. an sdist-build job on `ubuntu-latest`
that uses `setup-uv`). For pure cibuildwheel build-from-checkout workflows with no `uv` steps,
skip them entirely — pass the registry to the container via
`CIBW_ENVIRONMENT: PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/` instead.

Newer workflows start with an SPDX header:
```
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
```

**Default to NO comments — these workflows are read as reference.** Add one only
when it is absolutely necessary, i.e. genuinely non-obvious: a deviation from the upstream recipe, a riscv-only
workaround, a load-bearing env var. Do **not** narrate standard steps (checkout,
Python install, the build matrix) or write multi-line explanations of what a line
does — a reader mines our workflows to copy patterns, and verbose commentary makes
it look like we customized far more than we did. Keep each note to a single "why"
line; if a comment restates the YAML it's on, cut it. (PR #308 review: the tomli
workflow's per-step paragraphs were trimmed for exactly this.)

**Never set `CIBW_BUILD_VERBOSITY`.** Do not add it to a new workflow, and drop it if
you inherit one from a template or an existing workflow you copied.

**Start from upstream's own workflow, then delete.** Find their build/test workflow
(`wheels.yml`, `build.yml`, `release.yml`, `python.yml`, …), copy the Linux glibc/musl
parts to `.github/workflows/build-<pkg>.yml`, and strip everything else: other
architectures, macOS/Windows, and the sdist job unless a build or test step consumes it.
Repeat for the test workflow if upstream keeps it separate. Only then apply the riscv64
changes below.

**Default interpreter matrix is `["cp312", "cp313", "cp314", "cp314t"]`.** RISE used to
track the four newest `major.minor` plus free-threaded variants, but numpy (as of 2.5.0)
sets 3.12 as its floor, and enough of the registry depends on numpy that everything
follows it. `3.13t` is deliberately excluded — it was experimental with limited support
(and the riscv64 manylinux image ships no cp313t either, gotcha 11). Deviating is allowed,
but weigh similarity-to-upstream against maintenance cost.

**Check the upstream repo out at the workspace root** — `actions/checkout` with
`repository:`/`ref:` and no `path:`. It replaces the default python-wheels checkout so the
workflow behaves as if it lived in the upstream tree, which cibuildwheel needs since it
treats the root as the project to build. When you also need *this* repo (patches, actions),
check it out **second** into a subdir (`path: python-wheels`), as `build-zstandard.yml` does.

**`actions/setup-python` does not support riscv64** — it silently falls back to whatever
host interpreter matches the requested `major.minor`. Replace it with `astral-sh/setup-uv`:

```yaml
- uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39  # v8.2.0
  with:
    python-version: '3.12'
    activate-environment: true
    enable-cache: false
```

`activate-environment: true` reproduces setup-python's behaviour for our purposes;
`enable-cache: false` is load-bearing — the cache has broken builds before.

**Dropping musllinux is an accepted outcome.** Building both glibc and musl is desirable,
but if the musl jobs fail with no obvious fix, strip them and open an issue tracking the
incompatibility rather than blocking the port. Dependent packages then can't rely on musl
either, which is the expected consequence.

Two build shapes exist in the repo — pick based on the package:

- **sdist → bdist** (see `build-cffi.yml`, `build-protobuf.yml`): job 1 produces
  an sdist and uploads it + exposes `package_version` as a job output; job 2 (a
  matrix over `cp312/cp313/cp314/cp314t`) downloads the sdist, extracts it, and
  runs `cibuildwheel ./extracted`; job 3 publishes. cibuildwheel also accepts the
  sdist tarball directly as `package-dir` (it extracts internally), so you can skip
  the manual `tar zxf` (see `build-apache-tvm-ffi.yml`).
- **build-from-checkout** (see `build-onnx.yml`, `build-sentencepiece.yml`, `build-tiktoken.yml`, `build-fonttools.yml`):
  check out the upstream tag with submodules, then use `uses: pypa/cibuildwheel@<sha>` directly
  (no `setup-uv` / `uv pip install cibuildwheel` step needed — the action bundles its own
  Python). Pass `only: ${{ matrix.python }}-manylinux_riscv64` and feed native deps via
  `CIBW_ENVIRONMENT`/CMake, or a prebuilt dependency wheel from our registry via
  `CIBW_BEFORE_BUILD` (see gotcha 17 for the dep-wheel pattern).
  Prefer the `build-fastuuid.yml`/`build-fonttools.yml` matrix convention: entries are
  **bare interpreter tags** (`python: ["cp312", "cp313", "cp314", "cp314t"]`) and the
  `-manylinux_riscv64` suffix is appended at each use site (job `name:`, cibuildwheel
  `only:`, artifact `name:`) — cleaner than embedding the full `cp312-manylinux_riscv64`
  tag in the matrix (the older `build-onnx.yml` `matrix.build` style).

When cibuildwheel doesn't fit, drive the build container yourself. Two sub-shapes:
- **`container:`** (see `build-torch.yml`): the GHA `container:` key on the job — works when the
  build is a self-contained shell script inside a known image.
- **`podman run` or `docker run`** (see `build-orjson.yml`): explicit container invocation on the
  runner — used when the build script already lives in the upstream repo or when orjson-style
  per-interpreter looping is needed. See gotcha 15 for the heavy C++ variant.

The `publish` job is always the shared action — it dry-runs off `main`, so it's
safe on PR branches:

```yaml
publish:
  needs: [<build jobs>]
  runs-on: ubuntu-latest
  permissions: { contents: write, pull-requests: write }
  steps:
    - uses: riseproject-dev/python-wheels/actions/publish-wheels@main
      with:
        artifact-pattern: <pkg>-${{ needs.<sdist-job>.outputs.package_version }}-*-manylinux_riscv64
        gitlab-username: ${{ vars.GITLAB_DEPLOY_USER }}
        gitlab-token: ${{ secrets.GITLAB_DEPLOY_TOKEN }}
        gitlab-project-id: ${{ vars.GITLAB_PROJECT_ID }}
        gh-token: ${{ secrets.GITHUB_TOKEN }}
```

`publish-wheels` auto-creates `docs/packages/<pkg>.yaml` from the wheel metadata on
first publish (`ci_scripts/update_doc.py`). Nightly checks and docs are driven off
that YAML, so **a new package needs no manual registration anywhere** — just the
workflow. Don't hand-write the docs YAML unless you need a `comment`/`warning`.
`permissions` needs `contents: write` **and** `pull-requests: write` (not `contents: read`)
because that docs step pushes a branch and opens a PR with the default `GITHUB_TOKEN`.
Reach for the lower-level `publish-to-gitlab` action directly only when a workflow needs the
upload without the docs-PR side effect.

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

## Gotchas (the "wish I knew from the start" list)

1. **Not every project can build an sdist from its git checkout.** protobuf's
   `setup.py` only works from an already-assembled source package — the README says
   so explicitly: the real sdist is produced by Bazel and bundles generated code
   (`*_pb2.py`) + vendored C. Always check upstream docs before assuming.

2. **The PyPI sdist is often self-contained and architecture-independent** — it
   bundles generated sources so building the bdist from it needs **no** codegen
   toolchain, even though building from the repo does. Confirm with the local
   `pip wheel` test in step 2.

3. **Git tag ≠ Python package version.** protobuf tags are `vNN.M` (`v35.1`) but the
   package is `7.NN.M` (`7.35.1`). Never hardcode the version twice. Take the tag as
   input and derive the version from the sdist filename:
   ```bash
   package_version="$(echo "$sdist_name" | sed -En 's/<pkg>-(.+)\.tar\.gz/\1/p')"
   ```
   For `setuptools_scm` projects built from a *shallow* checkout (no tag history),
   `git describe` can't see the version — pin it with
   `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_<PKG>=<ver>` instead.

4. **Build arch-independent artifacts on `ubuntu-latest`, not the riscv runner.**
   The sdist and any `py3-none-any` helper wheels don't depend on arch — build them
   once on x86. Only the actual bdist needs `ubuntu-24.04-riscv`. Building a codegen
   toolchain (e.g. protoc via Bazel) on riscv is a dead-end; don't attempt it.

5. **cibuildwheel `{project}` vs `{package}`.**
   `{project}` = invocation dir (`/project`); `{package}` = path passed to CLI
   (`cibuildwheel ./<subdir>` → `/project/<subdir>`). When you pass a subdir,
   **everything in it — including bundled `tests/` — is under `{package}`, not
   `{project}`**. Reference test suites and staged helpers via `{package}`.
   Symptoms: exit **127** (script not found) or exit **4** + `no tests ran` (pytest
   aimed at wrong dir). **Local-repro trap:** `cd <subdir> && cibuildwheel .` makes
   `{project}==subdir` and masks the bug — always invoke from the parent dir.

6. **Running a real test suite through cibuildwheel:**
   - Stage helper files inside the package dir (cibuildwheel copies that tree into
     the container); reference them via `{package}`.
   - `CIBW_TEST_REQUIRES: <deps>` and `CIBW_TEST_COMMAND: bash {package}/.../run.sh`.
   - `CIBW_ENVIRONMENT_PASS_LINUX: PIP_EXTRA_INDEX_URL` + set
     `PIP_EXTRA_INDEX_URL: https://pypi.riseproject.dev/simple/` so test deps that
     lack riscv64 wheels on public PyPI (e.g. numpy) resolve from our registry
     inside the container. (build-onnx.yml uses the same mechanism.)
   - **Check whether tests ship in the sdist.** protobuf's don't — upstream builds a
     separate `protobuftests` wheel (`py3-none-any`, via Bazel
     `//python/dist:test_wheel`, not published to PyPI) that bundles the `*_test.py`
     files + generated test protos. Build it alongside the sdist on x86, upload it as
     a second artifact, install it in the test step. Then discover+run like upstream:
     ```bash
     tests="$(pip show -f protobuftests | grep _test.py \
       | grep -v -e _pybind11_test.py -e proto_api_test.py \
       | sed 's,[/\\],.,g' | sed -E 's,.py$,,g')"
     rc=0; for t in $tests; do python -m unittest -v "$t" || rc=1; done; exit $rc
     ```
   - **The easy inverse: the sdist bundles both its tests and the `[tool.cibuildwheel]`
     config** (apache-tvm-ffi ships `tests/` + `test-command`, `test-groups`,
     `build-frontend`). Passing the sdist as `package-dir` inherits all of it unchanged
     — you get upstream's exact test invocation for free and only add the riscv
     overrides (`CIBW_ARCHS`, image, registry env; see gotchas 12–14). GPU-only tests
     usually self-skip via `torch.cuda.is_available()`.
   - Collect **all** failures per run (`|| rc=1`), don't stop at the first — each CI
     cycle is expensive, so surface the whole list. For genuinely-incompatible tests,
     exclude with an explicit justification comment (build-onnx.yml documents its
     skipped `maxpool` test this way).

7. **Heredoc inside a YAML `run: |` block.** YAML strips the common indent, *then*
   bash needs the `EOF` terminator at column 0. Use `<<'EOF'` (quoted) to stop the
   shell expanding `$…` inside the script. Verify by parsing the YAML and checking the
   `EOF` line de-indents to column 0. The `run:` default shell is `bash` on Linux, but
   word-splitting differs from zsh — test shell snippets under real `bash`, not your
   interactive zsh.

8. **Pin Bazel to a version that actually exists.** bazelisk reads
   `USE_BAZEL_VERSION`. I guessed `8.5.2` (doesn't exist) → 404 → instant fail. There
   is no `.bazelversion` at protobuf release tags. Verify a candidate is real before
   pushing:
   ```
   curl -sI https://releases.bazel.build/<ver>/release/bazel-<ver>-linux-x86_64   # want 200
   ```
   Use a version the project's own CI uses (grep their workflows) that satisfies their
   `MODULE.bazel` `bazel_compatibility`. Install bazelisk yourself; don't assume the
   runner has Bazel. Bazel's `system_python` needs a host interpreter, so run
   `actions/setup-python` before Bazel.

9. **Validate before every push**. Cheap local checks that catch the dumb stuff:
   - `python -c "import yaml; yaml.safe_load(open('<wf>'))"` — YAML parses.
   - `actionlint <wf>` — it runs shellcheck on `run:` blocks too. The only expected
     warning is `label "ubuntu-24.04-riscv" is unknown` (custom self-hosted runner);
     every workflow trips it. Fix everything else (SC2011 `ls|xargs`, SC2129 repeated
     `>>` redirects, etc.) to match repo cleanliness.
   - Simulate shell pipelines against sample input under `bash`.
   - Run the wheel's import/smoke line against a locally-built wheel in a venv.
   - Use docker to run cibuildwheel on riscv64. For a heavy from-source C++ build
     (gotcha 15), a `cmake` *configure* under `--platform linux/riscv64` is a cheap
     proxy that catches flag/dep errors without the full multi-hour compile.
   - **Run cibuildwheel under QEMU** on a non-riscv host (a full build+smoke loop
     can be validated this way on an aarch64 machine):
     - Needs `qemu-riscv64` binfmt with the **`F` (fix-binary) flag** —
       `grep flags /proc/sys/fs/binfmt_misc/qemu-riscv64` should show `F`; that's
       what lets QEMU run *inside* the manylinux container.
     - Needs **cibuildwheel ≥ 3** (4.2.0 works) — older versions don't know the
       `manylinux_riscv64` arch and error out. `uv tool install cibuildwheel` may
       fetch a stale one; check `--print-build-identifiers --archs riscv64`.
     - Fetch a riscv64 wheel on a non-riscv host to inspect it with plain
       `pip download --platform manylinux_2_39_riscv64 --python-version 313
       --implementation cp --abi cp313 --only-binary=:all: <pkg>` (`uv pip
       download` does not exist).
     - Iterate fast: first pass with `CIBW_TEST_SKIP="*"` (build only), then
       validate the import in a raw `docker run --platform linux/riscv64 …`
       container — far quicker than a full cibuildwheel rebuild to re-run tests.

10. **Rust/PyO3 packages (maturin *or* setuptools-rust) — traps.** Two build
    backends show up: **maturin** (fastuuid, litellm, tiktoken, hf-xet) and
    **setuptools-rust** (bcrypt, and the whole pyca/cryptography family —
    `build-backend = setuptools.build_meta`, crate wired via
    `[[tool.setuptools-rust.ext-modules]]`). The toolchain/musl traps below apply
    to both; the abi3 mechanism differs (see gotcha 11).
    - **Floating deps in a locally-built sdist.** If upstream gitignores `Cargo.lock`
      (common for libraries), a fresh `python -m build --sdist` re-resolves crates to
      today's latest semver-compatible versions. With `#![deny(warnings)]`, a newly
      deprecated API in a bumped dep becomes a hard compile error. Fix: pin the
      offending crate to the version upstream released against *before* building the
      sdist, so maturin captures it into the bundled lock (see `build-fastuuid.yml`):
      ```bash
      cargo update -p <crate> --precise <version>
      python -m build --sdist
      ```
      Diagnose: grep CI log for `use of deprecated` / `could not compile`. If upstream
      commits `Cargo.lock` into the repo (litellm does), this trap doesn't apply —
      the lock is bundled into the sdist verbatim.
    - **Rust toolchain must be installed inside the manylinux container.** If the
      project's `pyproject.toml` has a `[tool.cibuildwheel] before-all` that does this
      (tiktoken does), it's inherited automatically. Otherwise supply it yourself:
      `CIBW_BEFORE_ALL_LINUX: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y`
      and `CIBW_ENVIRONMENT_LINUX: PATH="$PATH:$HOME/.cargo/bin"`. rustup provisions a
      native `riscv64gc-unknown-linux-gnu` toolchain in the container.
    - **musllinux can't build** — rustup.rs ships no riscv64 musl toolchain. Restrict
      `CIBW_BUILD` to `*-manylinux_riscv64` (or `CIBW_SKIP: '*-musllinux_*'`). Whether
      the matrix is per-interpreter `[cp312, cp313, cp314, cp314t]` or collapses to
      `[cpXY-abi3, cp3Nt]` depends on whether the extension is built abi3 — see
      gotcha 11, which covers both maturin and setuptools-rust.
    - **The rustc target triple is not `riscv64`.** Upstream maturin matrices usually carry
      a short `target:` field (`x86_64`, `aarch64`, `armv7`, `ppc64le`); there is no
      `riscv64` target, it is `riscv64gc-unknown-linux-gnu` (`rustup target list | grep
      riscv64`), so adding `target: riscv64` just fails. Make the matrix entries explicit
      instead — `{runner: ubuntu-24.04-riscv, target: riscv64gc-unknown-linux-gnu,
      arch: riscv64}` — and switch the upload step's artifact name to interpolate the new
      `arch` field rather than `target`.

11. **abi3 wheels collapse the matrix.** If `pyproject.toml` sets `wheel.py-api = "cpXY"`
    (or otherwise builds abi3/limited-API), one `cpXY` build loads on every newer
    non-free-threaded CPython, so the matrix is just `[cpXY, cp3Nt]` — the abi3 build
    plus a free-threaded build (free-threaded can't use the stable ABI). Tell from the
    PyPI wheel names: `…-cp312-abi3-…` + `…-cp314-cp314t-…` = exactly two builds (same
    shape as onnx/hf-xet, and apache-tvm-ffi). Don't add cp313/cp314 — they'd duplicate
    the cp312 abi3 wheel.
    Some packages ship **only** the abi3 wheel with no cp314t variant (litellm: upstream
    publishes `cp310-abi3` only, no free-threaded wheel). In that case the matrix
    collapses to a single build; run it on cp312 (our minimum) and test-reuse on
    cp313/cp314 via cibuildwheel's `find_compatible_wheel` logic.
    - **maturin abi3 is a pyproject/Cargo feature; setuptools-rust abi3 is a
      build-time *flag* you must inject.** For maturin the abi3 tag comes from
      `wheel.py-api`/the `pyo3/abi3-pyNN` crate feature — set once, inherited. But
      **setuptools-rust** projects (bcrypt, pyca/cryptography) commonly set
      `py-limited-api = "auto"` on the ext, which only turns on abi3 **when
      `bdist_wheel` is passed `--py-limited-api=cpNN`** — and *cibuildwheel does not
      set that itself*. So a plain cibuildwheel run of such a project yields
      per-interpreter `cpNN-cpNN` wheels despite the "auto"; you must inject the flag:
      `CIBW_CONFIG_SETTINGS: --build-option=--py-limited-api=cp312`. It works *with*
      build isolation (setuptools-rust comes from `build-system.requires`), so no
      `--no-build-isolation` needed. Verify locally: build once with the flag (→
      `cpNN-abi3`) and once without (→ `cpNN-cpNN`). The abi3 + free-threaded split
      then needs **two build configs, not one matrix**: the abi3 job passes the flag
      and selects `cp312-* cp313-* cp314-*` (one wheel, reused+tested on each); the
      free-threaded job passes **no** flag and selects `cp314t-*` (pyo3 auto-disables
      abi3 under `Py_GIL_DISABLED`, so it can't be forced). See `build-bcrypt.yml`.
      Heads-up: the `manylinux_2_39_riscv64` image ships cp39–cp315 incl. cp314t/cp315t
      but **no cp313t**, so cp314t is the only free-threaded target even when upstream
      also publishes cp313t.

12. **Scope an env var to one phase with the right knob.** `CIBW_ENVIRONMENT` applies to
    **both** build and test; `CIBW_TEST_ENVIRONMENT` is test-only. This bites with
    `only-binary`: putting `PIP_ONLY_BINARY=:all:` in `CIBW_ENVIRONMENT` to stop a heavy
    *test* dep (torch) from source-building also starves the **build backend**, and
    `cython` (a common build requirement) has no riscv64 wheel anywhere — it must
    compile from sdist. So keep registry index URLs in `CIBW_ENVIRONMENT` (both phases
    need them) but put `only-binary` in `CIBW_TEST_ENVIRONMENT` alone.

13. **`build-frontend = "build[uv]"` crashes the audit step on the riscv runner.**
    cibuildwheel's post-build "Auditing wheel…" step makes a venv *on the host* and, for
    a uv frontend, asserts a host `uv` exists (`venv.py: assert uv_path is not None`) —
    the self-hosted runner has none, so the wheel builds and auditwheel-repairs fine and
    *then* dies with a bare `AssertionError`. Fix: `CIBW_BUILD_FRONTEND: build` (plain
    pip/virtualenv, the default onnx/cffi/tiktoken already use).

14. **torch-dependent tests flake two ways on the riscv runner — deselect, don't chase.**
    torch is usually gated `python_version < '3.14'`, so these bite your `cp312`/abi3
    build but not `cp314t` — a tell it's torch, not your wheel. (a) torch's libcpuinfo
    can't parse this runner's `/sys/.../core_id` (reads `-1`) and writes
    `Error in cpuinfo: failed to parse … core_id` to **stderr**, so any test asserting a
    subprocess's `stderr == ""` fails nondeterministically — deselect the whole module.
    (b) tests spawning many workers under a hard timeout (16 subprocesses,
    `wait(timeout=60)`) blow it on the slower runner. To drop tests, override
    `CIBW_TEST_COMMAND` with **`--ignore <abspath>`** (whole module) and
    **`-k "not <name>"`** (single test) — *not* path-based `--deselect {package}/…`,
    which silently no-ops because pytest reports collected nodeids relative to its
    rootdir while your path is absolute. Verify locally by running pytest from a
    different cwd and checking the deselected count is non-zero.

15. **Heavy C++ ports: drive the build container yourself, build the C++ once.**
    When the extension links a big C++ tree whose sources sit *beside* the Python
    package (e.g. Cython over a sibling `cpp/`), cibuildwheel's copy-the-package-dir
    model can't see them, and the manylinux image ships no Node so a `container:` job
    can't run JS actions. So: checkout + upload-artifact on the host, and a `docker run`
    step that bind-mounts the source and an inline-written build script into
    `$MANYLINUX_RISCV64_IMAGE`. Build the C++ lib **once** into a prefix, then loop the
    interpreters (`for pytag in $PYTHON_TAGS`) building only the bindings against it —
    don't rebuild C++ per Python.
    - **Feed dep sources from the OS, not vcpkg.** Upstreams that vcpkg their deps
      rely on a binary cache baked into *their* x86/arm images; the riscv image has
      none. Use the project's from-source path instead (Arrow:
      `-DARROW_DEPENDENCY_SOURCE=BUNDLED`, which downloads+compiles each pinned dep).
    - **The image is Rocky 10 (`dnf`), missing `ninja-build`, OpenSSL dev headers,
      and `zip`** — `dnf install` them in the script; it already has cmake/gcc/
      auditwheel/git. Enable heavy features (network storage, LLVM) incrementally
      from a small green core, one env flag per feature — each drags in a dep tree
      that may not have been built on riscv64 before.
    - **A full qemu build is impractical, but `cmake` *configure* under
      `--platform linux/riscv64` finishes in minutes** and catches most flag/dep/
      toolchain mistakes (missing lib, unresolved target) before you spend a
      multi-hour native CI cycle. Do that as your gotcha-9 local check for these.

16. **All-static BUNDLED build + a dep the project can't bundle = link failure.**
    An all-static dependency build (Arrow's `-DARROW_DEPENDENCY_USE_SHARED=OFF`)
    tries to link *every* dep statically — including ones that only exist as shared
    libs in the image. OpenSSL is the classic: Arrow can't vendor it, the Rocky
    image ships only `libssl.so`/`libcrypto.so` (no `.a`), so the static lookup
    yields `OPENSSL_CRYPTO_LIBRARY-NOTFOUND`, the `OpenSSL::SSL`/`::Crypto` imported
    targets are never created, and the *generate* step dies with "target not found"
    cascading through everything that links SSL (bundled gRPC, parquet). Fix: force
    that one dep shared (`-DARROW_OPENSSL_USE_SHARED=ON`), keep the rest static.
    Signature: configure succeeds, **generate** fails on a missing imported target.

17. **Building an extension that links another wheel we ship (the dep-wheel pattern).**
    When an extension links shared libraries from a heavy Python wheel that only exists
    on our registry (e.g. a domain library linking `libtorch`/`libc10`), four pieces
    have to line up:
    - **Install the dep from our registry in `CIBW_BEFORE_BUILD`:**
      `pip install --only-binary=:all: <dep>>=<min_ver> setuptools wheel ninja`.
      `--only-binary=:all:` is load-bearing — without it pip silently falls back to
      building the dep from source in-container when public PyPI has no riscv64
      wheel. Prefer a range (`<dep>>=<ver>`) over a hard pin so it resolves to
      whatever's latest on the registry (confirm your package's compat policy with
      the dep first).
    - **Pass `PIP_EXTRA_INDEX_URL` into the build**, not just the test step:
      `CIBW_ENVIRONMENT: … PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/`,
      so the dep and its own deps resolve from our registry inside the container.
    - **Disable build isolation** when `setup.py` imports the dep at module top and
      declares no `[build-system]` table (legacy setuptools):
      `CIBW_BUILD_FRONTEND: "pip; args: --no-build-isolation"`. Otherwise the build
      env can't see the preinstalled dep.
    - **Exclude the dep's shared libs from the auditwheel repair**, or auditwheel
      vendors all of them in (a small wheel balloons to the full dep size). Find the
      list by unzipping the dep wheel and listing `*/lib/*.so`; then:
      ```
      CIBW_REPAIR_WHEEL_COMMAND: >-
        auditwheel repair -w {dest_dir} {wheel}
        --exclude lib<dep_a>.so --exclude lib<dep_b>.so ...
      ```
      This mirrors how upstream ships domain-library wheels — the dep's libs are
      assumed present at runtime (the dep is imported first and loads them
      `RTLD_GLOBAL`).
    - Note: `py_limited_api=True` does **not** guarantee a single abi3 wheel here.
      An extension may set it but still need a per-CPython build because it links a
      version-specific shared lib from the dep. Check what the extension links before
      trimming the matrix (build-onnx.yml *does* get one abi3 wheel by avoiding
      version-specific links).

18. **The wheel-filename version is canonical; keep three places in sync** (see
    PR #246, which fixed broken doc links from exactly this). Whatever version ends
    up in the `.whl` filename (driven by `BUILD_VERSION`) must match, byte for byte:
    (1) the wheel filename, (2) the `docs/packages/<pkg>.yaml` `version:` key
    (auto-populated by `update_doc.py` from the wheel), and (3) the
    `patches/<pkg>/<version>/` directory name — `docs/.../generate_packages_doc.py`
    links patches as the literal path `patches/{name}/{version}`, so a mismatch is a
    404. torch ships a **local segment** (`2.13.0+cpu`, pytorch's CPU-index
    convention) so its patches live under `patches/torch/2.13.0+cpu/`.
    **Match upstream's own PyPI filename convention** — if a package ships plain
    `X.Y.Z` on PyPI, build plain `X.Y.Z` (no `+cpu` or other local segment).
    Decoupled from all this: the nightly `check_versions.py` compares the workflow's
    `version:` **input default** against PyPI — keep that the plain upstream version,
    regardless of any local segment `BUILD_VERSION` adds.

19. **mypyc-compiled wheels behind a `flit_core` pyproject (the tomli pattern; see
    `build-tomli.yml`).** Some pure-Python-*looking* packages publish
    mypyc-compiled binary wheels (a `.so` per module, big speedup) *alongside* the
    `py3-none-any` wheel — so riscv64 is worth building even though the sdist is
    pure Python. The compiled build is **opt-in and gated on an env var**, and the
    committed `pyproject.toml` declares `flit_core` (which can only make
    pure-Python wheels). Tell-tale: a `setup.py` sits next to the flit pyproject
    doing `if os.environ.get("<PKG>_USE_MYPYC")=="1": ext_modules =
    mypycify(glob("src/**/*.py"))`, plus a `scripts/use_setuptools.py`-style helper
    that rewrites `[build-system]` to `setuptools + mypy[mypyc]`. Two things must
    both happen to get compiled wheels — reproduce upstream's release job exactly:
    - **Run upstream's backend-swap script on the host** before cibuildwheel
      (`uv pip install -r scripts/requirements.txt && python
      scripts/use_setuptools.py`). It edits the checkout's `pyproject.toml` in
      place; the host interpreter (setup-uv) only runs the swap — the wheels
      compile in-container.
    - **Forward the mypyc env var into the container:**
      `CIBW_ENVIRONMENT_PASS_LINUX: <PKG>_USE_MYPYC` + `<PKG>_USE_MYPYC: '1'`.
      Without the pass-through the container build silently produces a *pure-Python*
      wheel (mypycify never fires) — you'd ship a no-op.
    There's usually **no `[tool.cibuildwheel]` table**, so supply
    `CIBW_MANYLINUX_RISCV64_IMAGE` and the test command yourself from the upstream
    release workflow's `env:` (grep `.github/workflows/*.y*ml` for `mypyc` /
    `use_setuptools` / `cibuildwheel`). Matrix is **per-interpreter**
    `[cp312, cp313, cp314, cp314t]` — mypyc wheels are *not* abi3 (confirm: PyPI
    shows separate `cpXY-cpXY` wheels, no `-abi3-` tag). The manylinux image already
    has the C toolchain + `Python.h`, so no `before-build`/`dnf` is needed — but a
    bare host (WSL) that lacks Python dev headers *will* fail the local `python -m
    build` with `fatal error: Python.h`; validate under QEMU/docker instead, where
    the container has them.

20. **Optional C extensions silently degrade to a mislabeled pure-Python wheel
    (the SQLAlchemy pattern; see `build-sqlalchemy.yml`).** When `setup.py` declares
    `Extension(..., optional=True)` — or gates it on an env var, SQLAlchemy uses
    `optional=not REQUIRE_SQLALCHEMY_CEXT` over 5 `.pyx` modules — a Cython/compile
    failure is **swallowed**: setuptools finishes and ships a wheel that still
    carries the `cp3XX-…-manylinux_riscv64` tag but contains **no `.so`**, just the
    pure-Python fallback. The job goes green and the "riscv64 wheel" is worthless
    (identical to the `py3-none-any` PyPI already ships). Fix: force the project's
    "require extension" knob so any build failure hard-fails — SQLAlchemy:
    `CIBW_ENVIRONMENT: REQUIRE_SQLALCHEMY_CEXT=1` (build phase needs it). **Always
    verify the `.so` is actually in the output wheel** (`unzip -l wheel.whl | grep
    '\.so$'`) — a green build is not proof. (These packages are pure-Python +
    *optional* speedups, so PyPI ships both a `py3-none-any` wheel *and*
    per-interpreter compiled wheels; the compiled riscv64 ones are the value-add,
    and the matrix is per-interpreter `[cp312, cp313, cp314, cp314t]`, not abi3.)

21. **`python -s` (no-user-site) does NOT propagate to pytest-xdist workers.** A
    project whose `test-command` runs `python -s -m pytest -n4` to force importing
    the *installed* wheel over a local source tree has a latent bug on riscv:
    the `-s` flag sets `sys.flags.no_user_site=1` on the **controller**, but execnet
    respawns each `-n` worker **without** it (`no_user_site=0`). SQLAlchemy's
    `test/conftest.py` injects `{project}/lib` onto `sys.path` *unless* no_user_site
    is set — so on the workers pytest imports the **pure-Python source** (no `.so`),
    not the compiled wheel. Combined with gotcha 20's `REQUIRE_*_CEXT` (whose test
    plugin then asserts the extension is present) every worker hard-crashes at
    `pytest_sessionstart` → `RuntimeError: Unexpectedly no active workers available`.
    Fix: set no-user-site as the **`PYTHONNOUSERSITE=1` env var**, which xdist *does*
    inherit into workers, and scope it to the test phase (`CIBW_TEST_ENVIRONMENT`,
    gotcha 12) so it can't touch the build. Verify arch-independently on any host: a
    5-line `conftest.py` that prints `sys.flags.no_user_site` from inside a test,
    run under `python -s -m pytest -n2` — the workers report `0`, the env var flips
    them to `1`.

22. **A release-branch checkout can carry `[egg_info] tag_build = dev` in
    `setup.cfg`, poisoning the wheel version with `.dev0`** (the SQLAlchemy variant
    of gotcha 3/18). `python -m build --sdist` from the tag then emits
    `<pkg>-<ver>.dev0.tar.gz`, and every wheel built from it inherits `.dev0` —
    breaking the wheel-filename-is-canonical rule (gotcha 18: docs YAML `version:`
    and `patches/<pkg>/<version>/` path both derive from it, and the nightly PyPI
    check compares against the clean upstream version). The released PyPI sdist has
    the tag blank because upstream strips it at release; do the same before building:
    ```bash
    sed -i '/tag_build = dev/d' setup.cfg
    ```
    Tell-tale: your locally-built sdist version has a `.dev0`/`.devN` suffix the PyPI
    sdist doesn't. Distinct from setuptools_scm dev suffixes (missing tag history —
    fix with `SETUPTOOLS_SCM_PRETEND_VERSION`, gotcha 3); this one is a literal line
    in `setup.cfg`. Confirm by diffing your sdist's `setup.cfg` against the released
    PyPI sdist's.

23. **A floating *build tool* can break code the release-era tool compiled fine
    (the Cython version-drift variant of gotcha 10; see `build-fonttools.yml`).**
    Gotcha 10 is about a package's *dependencies* floating; the same trap applies to
    the **build tool itself**. A project that compiles Cython extensions but pins
    Cython nowhere (`setup_requires=["cython"]`, no `[build-system]` table) will, on a
    fresh build, pull whatever Cython is newest *today* — often much newer than what
    upstream cut their wheels with. A newer Cython can change codegen semantics and
    break unchanged source. fonttools tripped this: **Cython 3.3.0** began enforcing
    PEP-484 argument annotations like `def f(quads: List[List[Point]])` as **strict
    runtime type checks** in compiled code; `qu2cu` passes a list-of-tuples there, so
    the compiled extension raised `TypeError: Expected list, got tuple` — 9 test
    failures on **all** interpreters. Cython 3.2.x (current when the release shipped)
    ignored the annotation.
    - **Looks like a port bug but reproduces on x86** — it's toolchain drift, not
      arch. Diagnose by comparing the package's sdist date against the tool's release
      timeline (`curl -s https://pypi.org/pypi/Cython/json`), then reproduce natively
      across the boundary versions (`pip install "cython==X"`) — far faster than QEMU
      and proves it's arch-independent.
    - **Fix mirrors the gotcha-17 preinstall shape, applied to a build tool:** pin
      below the breaking version (`CYTHON_SPEC: 'cython<3.3.0'`), preinstall it, and
      disable build isolation so the build actually uses it:
      ```yaml
      CIBW_BEFORE_BUILD: pip install "${CYTHON_SPEC}" setuptools wheel
      CIBW_BUILD_FRONTEND: "pip; args: --no-build-isolation"
      CIBW_ENVIRONMENT_PASS_LINUX: CYTHON_SPEC
      ```
      **Preinstall + `--no-build-isolation` is load-bearing, a pip pin alone is not:**
      `setup.py` appends `"cython"` to `setup_requires` only when Cython isn't already
      importable, and that fetch is an **easy_install that ignores pip specifiers** —
      so the pinned Cython must already be present for `setup.py`'s `has_cython` path
      to use it, and `--no-build-isolation` stops a fresh isolated env re-resolving to
      newest. Quote the spec so the shell doesn't read `<` as redirection. Revisit the
      ceiling when bumping the package version.

24. **Feasibility triage: some "binary-looking" packages never compile anything —
    check before you port (the multiprocess case).** A package can carry C sources in
    its sdist *and* publish platform-tagged wheels on PyPI and still be 100%
    pure Python. multiprocess bundles a full copy of CPython's
    `Modules/_multiprocessing` C sources under `py3.NN/Modules/_multiprocess/` and
    ships `…-pp311-pypy311_pp73-manylinux_2_28_x86_64.whl`, which looks like a port
    target. It isn't: `setup.py` defines `run_setup(with_extensions=True)` but calls
    `run_setup(False)` at **both** call sites, so the `Extension` is dead code; the
    installed `_multiprocess/__init__.py` is a one-line shim
    (`from _multiprocessing import *`) delegating to CPython's own builtin. The
    CPython wheels are `pyNN-none-any` and already install on riscv64 unmodified.
    Three cheap checks settle it in minutes — run all three before writing any YAML:
    - **`unzip -l <plat-tagged wheel> | grep '\.so'`** — a platform tag with *zero*
      `.so` means the tag is a packaging artifact (a `Distribution.has_ext_modules`
      override or a manual `--plat-name`), not compiled content.
    - **`pip wheel <sdist> --no-deps --no-build-isolation`** on any host, then read
      the generated `dist-info/WHEEL`: `Root-Is-Purelib: true` + `Tag: py3-none-any`
      means there is no arch-specific artifact to build, on any architecture.
    - **grep `setup.py` for how the `Extension` list is actually reached** — a
      defaulted-True parameter proves nothing if every caller passes False.
    Distinct from gotcha 20 (SQLAlchemy): there the extension is *attempted* and
    silently degrades on failure, so forcing `REQUIRE_*_CEXT` is the right fix. Here
    it is never attempted for **any** platform, so forcing it on would ship riscv64 a
    binary upstream ships nowhere else — a divergence, not a port. Report
    `not-feasible` and move on. (Contrast gotcha 19/20, where PyPI *does* show real
    `cpXY-cpXY` wheels — that is the signal that a compiled build genuinely exists.)

25. **Build-from-checkout + pytest = the repo's source package shadows the wheel you
    just built (the pymongo case; fix with `test-sources`).** In the
    build-from-checkout shape the importable package sits at the **repo root**
    (`bson/`, `pymongo/`), and cibuildwheel runs `test-command` from the checkout. If
    the suite is a *package* (`test/__init__.py` exists — check it), pytest's default
    prepend import mode puts the **rootdir** on `sys.path[0]`, so `import <pkg>`
    resolves to the source tree and never touches the installed wheel. The job goes
    green having tested pure Python — the exact failure gotcha 20 warns about, reached
    by a different route (there the `.so` was never built; here it was built and then
    not imported). Fix: `CIBW_TEST_SOURCES: test tools pyproject.toml` — cibuildwheel
    ≥3 copies just those paths into an empty temp cwd, so the shadowing source packages
    aren't there. Then use **paths relative to that cwd** in `CIBW_TEST_COMMAND`
    (`python -m pytest test/...`), not `{project}`/`{package}` (gotcha 5) — those
    still point at the full checkout. Stage `pyproject.toml` too or `[tool.pytest.ini_options]`
    is lost.
    - **Verify, don't assume** — same rule as gotcha 20's `unzip -l | grep '\.so$'`,
      one level up: assert the *import* is the compiled one. Many projects ship a
      ready-made probe (pymongo: `tools/fail_if_no_c.py`, which asserts `bson.has_c()`);
      chain it with `&&` ahead of pytest so a shadowed import is fatal.
    - **Reproduces on any host in 30 seconds**, no QEMU: two dirs with the same package
      name (one "SOURCE" at a fake repo root, one "INSTALLED" on `PYTHONPATH`) plus a
      `test/__init__.py` — run pytest from the repo root (imports SOURCE) and from a
      staged cwd holding only `test/` (imports INSTALLED).
    - Distinct from gotcha 21, which is about `python -s` failing to reach xdist
      workers and a conftest that *explicitly* injects a lib dir. This one is pytest's
      own rootdir insertion and needs no conftest cooperation at all.
    - While you're there, **pin floating test deps the same way gotcha 23 pins build
      tools**. A project with `filterwarnings = ["error", ...]` turns any new
      DeprecationWarning from a freshly-resolved plugin into a hard failure — pymongo
      needed `pytest-asyncio==1.3.0` (upstream's `uv.lock` version) because 1.4 made
      its own `event_loop_policy` override warn. Take the version from upstream's lock
      file, not from "latest".

26. **The riscv64 runners ship GCC 13; some packages need GCC 14 or later.** The compiler
    that matters is the one in the *build container*, not on the runner — a cibuildwheel
    build against the manylinux_riscv64 image gets a newer toolchain for free. A project
    that builds directly on the runner does not: if it needs GCC 14+, either move the build
    into the container or provision a newer toolchain explicitly.

27. **`py3-none-<platform>` is a hand-set `--plat-name`, never compiled content (the
    watchdog variant of gotcha 24).** Gotcha 24's tell-tale was a *platform-tagged
    wheel with zero `.so`*; the sharper, faster signal is the **interpreter/ABI half
    of the tag**. A wheel that actually contains an extension module is tagged
    `cpXY-cpXY-<platform>` (or `cpXY-abi3-…`) — the ABI tag is what pins it to a
    CPython build. `py3-none-<platform>` is a contradiction on its face: `py3-none`
    says "no interpreter-specific, no ABI-specific content", so the platform half can
    only have been forced by hand. watchdog 6.0.0 publishes
    `watchdog-6.0.0-py3-none-manylinux2014_{x86_64,aarch64,armv7l,i686,ppc64,ppc64le,s390x}.whl`
    plus per-CPython **macOS** wheels (`cp312-cp312-macosx_…`) — the split is the whole
    story: only macOS compiles anything (`_watchdog_fsevents.c`, linking
    `-framework CoreFoundation -framework CoreServices`), and `setup.py` builds
    `ext_modules = []` unless `sys.platform == "darwin"`. On Linux watchdog drives
    inotify through pure-Python `ctypes`. Upstream's release workflow does it in the
    open — on `ubuntu-latest`, with only `setuptools wheel` installed and no compiler:
    ```bash
    for platform in manylinux2014_x86_64 … win_amd64; do
      python setup.py bdist_wheel --plat-name $platform
    done
    ```
    **Triage rule: read the ABI tag before downloading anything.** All-`py3-none-*`
    Linux wheels ⇒ nothing to compile ⇒ `not-feasible`; stop before writing YAML.
    Confirm in one step with `unzip -p <whl> '*/WHEEL'` (`Root-Is-Purelib: true`).
    - **Distinct from gotcha 24 in what happens on riscv64 today.** multiprocess's
      CPython wheels were `pyNN-none-**any**`, so riscv64 already got a wheel. watchdog
      publishes **no `-any` wheel at all** — deliberately, so that a macOS user on a new
      Python falls back to the sdist rather than to a pure wheel missing the extension
      (the upstream workflow's header comment says exactly this). So on riscv64
      `pip install watchdog` builds from the sdist. That is **not** a reason to port it:
      the sdist build is pure Python, needs no compiler and no riscv64 anything, and
      finishes in seconds. Publishing a `py3-none-manylinux_2_39_riscv64` wheel would
      ship zero arch-specific content — a packaging convenience, not a port.
    - **Generalizes past this repo's macOS case:** whenever upstream's compiled
      extension is gated on one OS (`sys.platform == …`, a `-framework`/`Win32` link
      line), the other platforms' wheels are pure-Python by construction. Grep the
      gate in `setup.py` *before* the download loop — it settles feasibility on its own.

28. **mypyc-by-default is the other half of gotcha 19 — verify the `.so`, don't add
    the env var (the pytokens case; see `build-pytokens.yml`).** Gotcha 19's tomli
    shape has the mypyc build *opt-in* (`<PKG>_USE_MYPYC=1`) behind a `flit_core`
    pyproject with no `[tool.cibuildwheel]` table. The commoner shape inverts all
    three: `setup.py` sets
    `USE_MYPYC = platform.python_implementation() == "CPython"` unless the env var
    is present, `build-system.requires` already lists `mypy`, and upstream ships a
    real `[tool.cibuildwheel]` table (`build-frontend`, `MYPYC_OPT_LEVEL`, `skip`).
    The port is then a plain build-from-checkout with **one** override,
    `CIBW_MANYLINUX_RISCV64_IMAGE` — forcing `<PKG>_USE_MYPYC=1` yourself would be
    divergence, not insurance. What does need doing is gotcha 20's proof that the
    wheel is compiled: mypyc turns `src/<pkg>/__init__.py` into
    `<pkg>/__init__.cpython-3XX-….so`, so chain
    `python -c "import <pkg>; assert <pkg>.__file__.endswith('.so'), <pkg>.__file__"`
    ahead of pytest — `__file__` is the direct tell, no `has_c()`-style probe needed.
    - **`CIBW_TEST_SOURCES` cuts both ways on `pyproject.toml` (refines gotcha 25).**
      Gotcha 25 says stage it or lose `[tool.pytest.ini_options]`. The mirror trap:
      staging it imports `addopts` wholesale, and a dev-oriented
      `addopts = "--cov --cov-report=term-missing"` then kills the run with
      `unrecognized arguments: --cov` unless `pytest-cov` is also in
      `CIBW_TEST_REQUIRES`. Read `addopts` before deciding: stage `pyproject.toml`
      only if the suite needs its config, otherwise leave it out
      (`CIBW_TEST_SOURCES: tests`) and the coverage flags go with it. Upstream's tox
      `commands = pytest` is the reference for what the suite actually needs.

29. **setuptools 82 deleted `pkg_resources`; any `setup.py` importing it breaks under
    build isolation (the asyncpg case).** The setuptools instance of gotcha 23's
    floating-*build-tool* trap, and a common one — `pkg_resources` was removed outright
    in **setuptools 82.0.0** (2026-02-08). A project whose `pyproject.toml` only
    *floors* setuptools (`requires = ["setuptools>=77.0.3", ...]`) resolves to today's
    latest in the isolated build env, so a legacy `setup.py` that imports
    `pkg_resources` — asyncpg does, to version-check Cython on the cythonise path —
    dies inside `finalize_options` with `ModuleNotFoundError: No module named
    'pkg_resources'`, surfacing only as the generic `ERROR Backend subprocess exited
    when trying to invoke build_wheel`.
    - **Reproduces on any host** — drift, not arch. Settle the boundary without
      building anything: `unzip -l setuptools-8{1,2}.0.0-*.whl | grep -c 'pkg_resources/'`
      → 19 files on 81.0.0, 0 on 82.0.0.
    - **Fix is gotcha 23's shape** — preinstall the pin, disable isolation:
      ```yaml
      CIBW_BEFORE_BUILD: pip install "setuptools<82" "Cython>=3.2.1,<4.0.0" wheel
      CIBW_BUILD_FRONTEND: "build; args: --no-isolation"
      ```
      **The flag name is frontend-specific**: `build` takes `--no-isolation`, pip takes
      `--no-build-isolation`. Copying pip's spelling into a `build` frontend is an
      immediate argument error — match the frontend upstream declares in
      `[tool.cibuildwheel] build-frontend` (gotcha 13 explains why `build[uv]` is the
      one to avoid). Mirror the project's whole `build-system.requires` in the
      preinstall: `build --no-isolation` still *verifies* those requirements and fails
      on a missing one.
    - Revisit the ceiling when bumping the package version — upstream will eventually
      stop importing `pkg_resources`.

30. **Check our own registry before dropping a dependency as "no riscv64 wheel".**
    `pypi.riseproject.dev` **302-redirects to pypi.org for anything it doesn't host**, so
    one call answers the question: `curl -s https://pypi.riseproject.dev/simple/<dep>/` —
    an HTML link list means we ship it (read the filenames for the interpreter tags), a
    302 means we don't. asyncpg's port initially deleted `uvloop` from upstream's `test`
    dependency-group and hand-copied the remaining requirements, assuming no riscv64
    uvloop existed; we ship 0.22.1 for cp312/cp313/cp314/cp314t. Inheriting upstream's
    `test-groups` unchanged and adding
    `CIBW_ENVIRONMENT: PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/` was both
    less YAML and closer to upstream — the divergence goal 2 warns about, introduced for
    a reason that wasn't true.
    - **The version has to line up, not just the name.** With `PIP_EXTRA_INDEX_URL` pip
      picks the highest version across *both* indexes and only then picks a file, so our
      riscv64 wheel gets used only when our version is the one pip resolves to. If PyPI's
      latest is newer than what we host, pip takes that and compiles it from sdist (or
      fails). Check with
      `curl -s https://pypi.org/pypi/<dep>/json | python3 -c 'import json,sys;print(json.load(sys.stdin)["info"]["version"])'`
      before relying on it.

31. **`git apply` onto a `setuptools_scm` checkout renames the wheel (the lz4 case).**
    A third route to a poisoned version, distinct from gotcha 3 (shallow checkout, no tag
    history) and gotcha 22 (`tag_build = dev` in `setup.cfg`): patching the upstream tree
    leaves it **dirty**, and `setuptools_scm` reads a dirty tree at a tag as post-release —
    `4.4.5` silently becomes `4.4.6.dev0+g59b2d817.d20260825`. That flows straight into the
    wheel filename and breaks gotcha 18's three-way match (the docs YAML `version:`, the
    `patches/<pkg>/<version>/` directory the patch itself lives in, and the nightly PyPI
    check all key off it). Committing the patch instead of leaving it unstaged does **not**
    help — `git describe` then reports `4.4.6.dev1+g<sha>`. Pin the version explicitly:
    ```yaml
    CIBW_ENVIRONMENT: >-
      ... SETUPTOOLS_SCM_PRETEND_VERSION_FOR_<PKG>=${{ env.<PKG>_VERSION }}
    ```
    `<PKG>` is the *distribution* name upper-cased with `-`/`.` → `_`. Once it's set
    setuptools_scm never consults git, so a `fetch-depth: 0` that existed only to make the
    tag reachable becomes dead weight — drop it in the same commit rather than leaving two
    mechanisms fighting over the version. **Costs nothing to catch**: a `pip wheel .` on any
    host prints the filename, so the wrong version is visible before you push.

32. **Vendored C libraries are the usual licensing gap — and upstream often has the fix
    already.** The Licensing section's "does the wheel carry the licences of what it links"
    check almost always fails the same way: the wheel ships the *wrapper's* LICENSE while a
    bundled C tree (`lz4libs/`, a vendored zlib/zstd/xxHash) is compiled straight into the
    extension under its own BSD/MIT terms, whose binary-redistribution clause requires the
    copyright notice to travel with the binary. Two-command check on any host:
    ```bash
    unzip -l <wheel> | grep -i licen     # what actually ships
    ls <vendored-dir>                    # what got linked in
    ```
    setuptools only globs `LICEN[CS]E*` etc. at the **project root**, so a licence file
    inside the vendored subdir is *not* picked up automatically — it needs an explicit
    `license_files=[...]` listing every file, the wrapper's own included, or you drop the
    original while adding the new ones.
    - **Search upstream before writing anything**: `gh search issues --repo <upstream>
      license --include-prs`. python-lz4 had both an open issue *and* an open PR fixing
      exactly this; carrying that PR turned a hand-rolled patch into
      `Upstream-Status: Submitted [url]` — the strongest tag available, and it drops out
      cleanly when upstream merges. Refresh it onto the tag you build (theirs was anchored
      on a `license=` line added after the release) and note the refresh in the commit
      message.
    - **Reproduce the copyright notice the vendored source actually carries**, not the one
      in the dependency's current `LICENSE` — the bundled copy is usually several releases
      old and the year range differs.

33.  **One green interpreter beside identically-failing others is a CPython feature
    gate, not a build bug (the debugpy case).** When a per-interpreter matrix comes back
    with cp314 fully green while cp312 and cp313 each fail the *same* N tests, suspect a
    runtime capability that newer CPython provides natively and older ones reach through
    arch-specific native code that has no riscv64 build. debugpy attaches to a running
    process by injecting a shim from a prebuilt per-arch library —
    `pydevd_attach_to_process/add_code_to_python_process.py` accepts only
    `arm64/amd64/x86/x86_64/i386` — but on 3.14 it goes through **`sys.remote_exec()`
    (PEP 768)** and needs no shim, so the 100 `attach_pid` failures were riscv64-real on
    3.12/3.13 and genuinely absent on 3.14.
    - **Read the failure *set* before any failure text.**
      `grep -oE 'FAILED [^ ]+' <log> | sort -u` then count how many carry the suspect
      parametrisation — 100 of 100 is a gate, a scattered mix is not. That one command
      separates "upstream doesn't support this on riscv64" from "our wheel is broken",
      and it costs nothing next to re-reading tracebacks.
    - **Deselect per matrix entry, not globally.** Turn `python: [cp312, ...]` into
      `include:` with a per-entry filter and interpolate it into the test command
      (`-k "${{ matrix.pytest_k }}"`), so the interpreter that *can* exercise the
      feature keeps testing it — dropping it everywhere would have thrown away 105
      real tests on cp314. `-k ""` is a valid no-op filter, so the unrestricted entry
      needs no second command shape.
    - **Free-threading is settled by upstream signals, not by debugging the crashes.**
      Three cheap checks decide whether `cp314t` belongs in the matrix at all: does PyPI
      list a `cp3XXt` wheel, does `tox.ini`/upstream CI carry a free-threaded env, do the
      classifiers mention free threading. debugpy answers no to all three, and its cp314t
      job crashed 40 pytest-xdist workers spread evenly over *every* test module —
      breakage of that shape means the configuration is unsupported, not that one feature
      is broken. Shipping it would give riscv64 a build upstream ships nowhere; drop the
      entry and say why in a one-line comment. (A *coherent subset* of failures would
      mean the opposite — keep digging.)

33. **Not every `.so` in a wheel is an extension module — some are ctypes/cffi-loaded
    raw shared libraries (the pycryptodome case; see `build-pycryptodome.yml`).**
    Gotchas 20/25/28 all reach for an import probe to prove the wheel is compiled
    (`import <pkg>; assert <pkg>.__file__.endswith('.so')`). That probe is invalid for a
    project that declares `Extension(...)` purely to get the C compiled and then `dlopen`s
    the result itself: pycryptodome's 40 `Crypto/*/_raw_*.abi3.so` have no `PyInit_*`, so
    `from Crypto.Cipher import _raw_aes` dies with **`ImportError: dynamic module does not
    define module export function (PyInit__raw_aes)`** — a probe failure that looks like a
    broken build but isn't. Tell-tale in 5 seconds: `grep -rl PyInit src/` returns nothing
    while the project has dozens of `Extension`s, and the loader (`Crypto/Util/_raw_api.py`)
    uses `ctypes.CDLL`/`cffi.dlopen`.
    - **The same fact removes the need for a probe.** Such a loader has no pure-Python
      fallback — it raises `OSError: Cannot load native module` — and the `Extension`s are
      not `optional=`, so a missing or unbuilt `.so` is a hard failure the moment the test
      suite imports anything. Use upstream's own test command unmodified and keep the
      gotcha-20 `unzip -l <whl> | grep '\.so$'` check as your proof instead.

34. **A third way a project gets abi3: `setup.py` sets the `bdist_wheel` option itself.**
    Gotcha 11 splits abi3 into maturin (pyproject/Cargo feature, inherited) vs
    setuptools-rust (a `--py-limited-api` flag *you* must inject via
    `CIBW_CONFIG_SETTINGS`). Plain setuptools has a third form — `setup(options={'bdist_wheel':
    {'py_limited_api': 'cpNN'}})` computed in `setup.py` — which needs **no** cibuildwheel
    config at all, and which upstream commonly guards with
    `if not sysconfig.get_config_var('Py_GIL_DISABLED')` so the free-threaded build silently
    drops back to a per-interpreter wheel. Two consequences:
    - Don't add `CIBW_CONFIG_SETTINGS` "to be safe" — it's redundant divergence. Settle it by
      building the sdist once on any host: pycryptodome yields
      `pycryptodome-3.23.0-cp37-abi3-macosx_....whl` with no flags.
    - **The abi3 floor is upstream's, not ours.** The wheel is tagged `cp37-abi3` even when
      cibuildwheel builds it on cp312, so name the job/artifact after the tag the wheel
      actually carries (`cp37-abi3-manylinux_riscv64`), not after the interpreter that built
      it — `build-bcrypt.yml`'s `cp312-abi3` naming only fits when *we* pick the floor.

35. **A `py3-none-<platform>` wheel whose platform tag is real: a downloaded prebuilt
    runtime (the playwright case).** Gotcha 27 reads an all-`py3-none-*` wheel set as
    "the platform half was forced by hand, nothing is compiled, stop". Half of that is
    always right — no ABI tag means no extension module — but the *reason* has two
    shapes, and they end in different statuses. watchdog's tag was cosmetic
    (`--plat-name` on an otherwise identical pure wheel). playwright's is **load-bearing**:
    each of its 8 wheels is ~40 MB because `setup.py` extracts a per-platform bundle into
    `playwright/driver/` containing a prebuilt **Node.js binary** plus the prebuilt
    `playwright-core` npm package. Nothing in the wheel is *compiled by the build*, yet the
    wheels genuinely differ per platform. That is `vendored-binary`, not `not-feasible`.
    - **Find the fetch, then find its platform table.** Two greps settle it: the download
      base (playwright: `NODEJS_DIST = "https://nodejs.org/dist"` in
      `scripts/build_driver.py`) and the hardcoded platform list beside it
      (`PLATFORMS = [Platform("linux", "linux-x64", ...), Platform("linux-arm64", ...)]`,
      mirrored by `base_wheel_bundles` in `setup.py`). Then ask the *upstream artifact*
      index whether our arch exists at all:
      `curl -s https://nodejs.org/dist/v<ver>/SHASUMS256.txt | grep -c riscv` → 0.
      No upstream artifact to bundle ⇒ nothing a workflow could assemble.
    - **An unofficial build of the runtime is not a green light.**
      `unofficial-builds.nodejs.org` *does* publish `node-v24.18.1-linux-riscv64.tar.gz`,
      so the bundle is technically assemblable — and it would still be worthless. Check
      what the vendored payload does at *runtime* before chasing the binary: playwright's
      own browser registry (`playwright-core`'s `lib/coreBundle.js`) enumerates only
      `{ubuntu,debian}NN.NN-{x64,arm64}` host platforms and contains zero `riscv`
      strings, and Microsoft publishes no riscv64 Chromium/Firefox/WebKit — so
      `playwright install` resolves to `<unknown>` and fails. Swapping in an unofficial
      runtime to ship a wheel upstream ships nowhere, that cannot then do its job, is
      divergence twice over.

36. **`test-sources` preserves each path's position relative to the project root —
    which is what makes `__file__`-relative fixture lookups survive the staging (the
    brotli case; see `build-brotli.yml`).** cibuildwheel (>=3, checked in 4.2.0
    `platforms/linux.py`) runs `test-command` in an **empty** temp dir, not in the
    checkout, and `copy_test_sources` copies each entry to `test_cwd/<same relative
    path>`. So a suite that locates its data by walking up from its own file —
    `project_dir = dirname(dirname(dirname(__file__)))` then `project_dir/tests/testdata`,
    a common unittest idiom — keeps working if you stage the sibling data at its original
    relative path: `CIBW_TEST_SOURCES: python/tests python/bro.py tests/testdata`.
    Stage the data under a flattened name and every lookup breaks.
    - **Choosing what *not* to stage is the shadowing fix (cheaper than gotcha 25's).**
      brotli's importable `brotli.py` lives in `python/` beside `python/tests/`; staging
      only `python/tests` leaves `test_cwd/python/` without it, so `import brotli` can
      only resolve to the wheel. Same reasoning applies to `unittest discover -s <dir>`,
      which inserts `<dir>` at `sys.path[0]` exactly like pytest's rootdir insertion —
      so what sits in that directory decides which copy gets imported.
    - **`setup.py test` is gone (removed in setuptools 72), so an upstream whose CI is
      `python setup.py test` needs translating, not copying.** Read the `test_suite`
      entry point and reproduce it directly — brotli's
      `test_loader.discover("python", pattern="*_test.py")` becomes
      `python -m unittest discover -s python -p '*_test.py'`. Closer to upstream than
      inventing a pytest invocation, and it needs no test-requires at all.

37. **pytest-xdist's controller can SIGSEGV under the free-threaded interpreter;
    `-n 0` sidesteps it (the snowflake-connector-python case).** A suite that runs
    green on `cp312`/`cp313`/`cp314` can kill the **cp314t** job with
    `Fatal Python error: Segmentation fault`, and the traceback is entirely
    *pure-Python execnet frames* — `gateway_base._read_int4` →
    `_thread_receiver`, under `<Cannot show all threads while the GIL is
    disabled>`, with `OSError: cannot send (already closed?)` from the workers
    trailing behind it. No project code on the stack, no `.so` involved, and it
    is **intermittent**: the same job on the same tree completed the whole suite
    on an earlier run. That is xdist's own gateway machinery, which only exists
    when `-n` is on, so the fix is to take execnet out of the picture for that
    one interpreter rather than to chase the crash.
    - **`-n 0` is the clean off switch, not `-p no:xdist`.** xdist's
      `pytest_cmdline_main` special-cases it: `numprocesses == 0` forces
      `dist = "no"` and `tx = []`, so no gateway is created and no receiver
      thread spawns — while the plugin stays loaded, so `pytest.mark.xdist_group`
      is still a registered marker (`-p no:xdist` deregisters it and trips
      `--strict-markers`). It also overrides an inherited `--dist loadfile`, so
      the flag can stay in a shared command string.
    - **Vary it per matrix entry, not globally** — serial costs real time (30min
      vs 18min here), so keep upstream's `-n auto` on the GIL-ful interpreters.
      Switch the matrix from a bare `python:` list to `include:` entries carrying
      the flags, and interpolate `${{ matrix.pytest_dist }}` into
      `CIBW_TEST_COMMAND`.
    - Distinct from gotchas 21 and 25, which are about what the xdist *workers*
      import. This one is the **controller** process crashing outright, and no
      amount of `PYTHONNOUSERSITE`/`test-sources` touches it.

38. **A slow runner turns a latent test race into a hard failure — simulate the
    slowness on your fast host instead of guessing.** Test suites are full of
    timing assumptions that hold on the x86 CI upstream sizes them for. Three
    shapes showed up in one port, all of them *arch-independent bugs* that only
    riscv64 was slow enough to reach:
    - **A fixed timeout constant sized for fast hardware** — a wiremock
      standalone server given 12s to answer `/__admin/health` while four xdist
      workers each boot their own JVM; a `platform_detection_timeout_seconds=1`
      budget that a first `boto3.client("sts", …)` service-model load overshoots.
      Both are the playbook's "artificial test limitation" patch case: raise the
      ceiling, note that the wait returns early so faster hardware pays nothing.
    - **A thread the code under test deliberately abandons.** The nastiest one:
      `Auth.authenticate()` runs its MFA wait in a daemon `Thread` and gives up
      with `t.join(timeout=…)`, so the request mock keeps running after the call
      returns — and reaches its trailing `mock_cnt += 1` ~9s later, inside the
      *next* sub-case, which has already reset that global to stage its own
      response. Result: a wrong branch and a `KeyError` instead of the expected
      exception. Fix the mock to complete its mutation of shared state **before**
      it sleeps (read-and-advance in one step at the top), leaving branch
      selection unchanged — not to widen the assertion.
    - **Reproduce it on any host by inserting the delay yourself.** Find the
      window the failure needs and `time.sleep()` it open — here, an 11s sleep
      right after the next sub-case's counter reset reproduced the exact CI
      `KeyError` on macOS/arm64, and the patch flipped it to green. Same
      30-second, no-QEMU discipline as gotchas 23/25/29, applied to timing: it
      proves the bug is upstream's rather than the port's, and it is the evidence
      that justifies the patch in review.
    - **Look for upstream's own admission.** A `skipif(IS_WINDOWS, reason="…race
      condition issues with the global …")` on the very test that fails is
      upstream telling you the race is known and merely platform-dependent —
      quote it in the commit message and tag the patch `To upstream`, not
      `Inappropriate`.
    - **Keep `Upstream-Status:` on ONE physical line.** `ci_scripts/check_patch.py`
      matches `^Upstream-Status: *(.*)$` and then validates the bracketed comment
      with `^(\[.*\])?$` — a bracket wrapped across two lines leaves the value
      unbalanced and fails `check_patches`, costing a push. Verify before pushing
      with `uv run --python 3.13 python ci_scripts/check_patch.py origin/main HEAD`
      (the script needs ≥3.12 for its nested-quote f-strings).

39. **Testing a unittest-native suite against the installed wheel: three traps past
    gotcha 25 (the dulwich case; see `build-dulwich.yml`).** `CIBW_TEST_SOURCES` stops the
    checkout's source package from shadowing the wheel, but a suite written to run against
    an *in-place* `build_ext -i` then breaks in three new ways.
    - **Fixture data resolved relative to the package, not the rootdir.** dulwich's
      *shipped* `dulwich/tests/utils.py` opens `<pkg>/tests/../../testdata`, and
      `tests/test_source.py` walks `<rootdir>/dulwich` — with only `tests/` staged, 95
      tests error. Staging the *installed* package into the test cwd fixes both at once
      and still exercises the compiled wheel:
      ```
      cp -a "$(python -c 'import <pkg>, os; print(os.path.dirname(<pkg>.__file__))')" <pkg>
      ```
      Keep gotcha 20's proof beside it (`python -c "import <pkg>._ext"`) — the copy is
      worth nothing if it has no `.so`.
    - **An upstream `test_suite()` callable can't be filtered, and pytest is not the way
      out.** `python -m unittest -k` has no negation and never reaches a suite built by a
      module-level callable. Switching to pytest as the filtering runner loses tests
      *silently*: **pytest never collects `__init__.py`, even when you name it explicitly**
      — dulwich keeps 591 of its 4620 tests in `tests/porcelain/__init__.py`, and only
      `-o python_files="test_*.py __init__.py"` sees them. Run upstream's exact suite minus
      one test with a flatten-and-filter one-liner instead (flattening preserves order, so
      `setUpClass` grouping survives):
      ```
      python -c "import sys, unittest, tests; flat = lambda s: [t for x in s for t in (flat(x) if isinstance(x, unittest.TestSuite) else [x])]; sys.exit(not unittest.TextTestRunner().run(unittest.TestSuite(t for t in flat(tests.test_suite()) if not t.id().endswith('.<test>'))).wasSuccessful())"
      ```
      Before switching runners at all, diff the two collections — `comm -13` over sorted
      test ids exposed the missing 591 in one run.
    - **The test phase runs as root, in a container that is not upstream's CI runner.**
      Two symptoms: a test asserting a mode-0 file is unreadable can never fail for root
      (deselect it), and tests shelling out to CLIs the image lacks *error* rather than
      skip — dulwich's `test_signature` needs `ssh-keygen`/`gpgsm`. Install those in
      `CIBW_BEFORE_TEST_LINUX` (`dnf -y install openssh-clients gnupg2-smime`) rather than
      deselecting: upstream's runners have them, so installing is the smaller divergence.
      And don't trust a local `docker run` of the image to settle what's present — the
      self-hosted riscv64 runner used an older cached `manylinux_2_39_riscv64` than a fresh
      `docker pull`, with `gpgsm` in one and not the other.

40. **A port can be blocked by a *dependency* that is conda-produced, even when the
    package itself builds cleanly (the numba case).** The early-skip triage asks whether
    *upstream's* wheel repackages a conda artifact; the commoner shape is one level down.
    numba's own wheel build is a plain manylinux `docker run` + `python -m build` with no
    conda anywhere, its C extensions need only numpy, and nothing in it gates on the
    architecture. It is still un-portable today because `install_requires` pins
    `llvmlite>=0.49.0dev0,<0.50`, and llvmlite is the conda-blocked one: its wheels link a
    patched LLVM that comes from the `llvmdev` **conda package** on the `numba` channel
    (`buildscripts/manylinux/prepare_miniconda.sh` installs miniconda *inside* the
    manylinux container, then `conda install llvmdev`), and `ffi/CMakeLists.txt` hard-fails
    on any other LLVM major (`LLVMLITE_SUPPORTED_LLVM_VERSION_DEFAULT 22`) — so the
    distro/manylinux LLVM is not a substitute, and upstream's install docs say in as many
    words not to use a system LLVM. Report the *dependency's* status, not the package's.
    - **Run the dependency check before reading any build script.** Take
      `info.requires_dist` from the package's PyPI JSON, drop the extras, and for each
      hard requirement ask (a) does PyPI publish a riscv64 wheel, (b) do we
      (gotcha 30's `curl -s https://pypi.riseproject.dev/simple/<dep>/` — a 302 means no).
      A `no` on both for a dependency imported at `import <pkg>` time means the wheel you
      would publish cannot be installed *or* smoke-tested; there is no partial win in
      shipping it.
    - **"The dependency needs its own port" is a real answer.** It is not the same as the
      port being merely hard: nothing in `build-<pkg>.yml` can fix it, because the
      gotcha-17 dep-wheel pattern presupposes the dep is already on our registry. Say which
      package must land first and why it is stuck, so the work can be sequenced.

41. **Compiling a huge amount of real code does not make a package portable — check
    what the compiled artifact *targets* (the triton case).** Gotchas 24/27/35 all
    triage packages that compile *nothing*; the inverse trap is a package that compiles
    an enormous C++ world and is still `not-feasible`, because the thing it builds is a
    **cross-compiler for someone else's ISA** whose assembler and runtime are proprietary
    vendor blobs. triton's wheel is ~190 MB: a 473 MB `triton/_C/libtriton.so` built from
    a pinned LLVM revision (genuinely compiled — the "big C++ tree is a port, not a
    blocker" rule would wave it through) sitting beside ~140 MB of *downloaded* NVIDIA
    binaries — `bin/ptxas`, `bin/ptxas-blackwell`, `bin/nvdisasm`, `bin/cuobjdump`,
    `lib/cupti/libcupti*`, `libnvperf_host.so`. Three cheap checks, in this order:
    - **Read the wheel's big files before reading `setup.py`.** No download needed — the
      zip central directory is enough, over HTTP range requests (cap each range at ~1 MB;
      `files.pythonhosted.org` answers a whole-file range with `501 Unsupported client
      range`). `bin/` entries and vendor-named `lib*.so` next to your own `.so` are the
      tell.
    - **Ask the vendor's own artifact index whether our arch exists**, the way gotcha 35
      asks `nodejs.org/dist`: NVIDIA's
      `https://developer.download.nvidia.com/compute/cuda/redist/redistrib_<ver>.json`
      lists exactly `linux-x86_64`, `linux-sbsa`, `windows-x86_64`, `linux-all` — no
      riscv64, in *any* release up to the newest. Same answer from triton's prebuilt-LLVM
      blob store (`oaitriton.blob.core.windows.net/public/llvm-builds/llvm-<hash>-<os>-<arch>-1.tar.gz`
      → 200 for `{ubuntu,almalinux}-{x64,arm64}`, 404 for anything riscv).
    - **Then ask what the wheel would do at runtime if you built it anyway.** The backend
      list is usually one line (`BackendInstaller.copy(["nvidia", "amd"])` — no CPU
      backend upstream), and each backend `driver.py` names the shared library it dlopens
      (`libcuda.so.1`, `libamdhip64.so`). Neither NVIDIA's driver nor ROCm ships riscv64,
      so both backends report zero devices and nothing can be compiled.
    An "offline build" escape hatch (`TRITON_OFFLINE_BUILD=1`, or presetting the
    `TRITON_PTXAS_PATH`-style variables that make `download_and_copy` return early) makes
    the 404s go away and is **not** a port: it ships a wheel with the vendor tools missing,
    which is strictly worse than the honest failure. Report `not-feasible` with the redist
    index and the `driver.py` dlopen line as evidence.

42. **Settling "is this arch conda-blocked?" — ask the channel's subdir, and count
    packages rather than trusting the HTTP status (the llvmlite case).** Gotcha 40
    names llvmlite as numba's conda-blocked dependency; confirming it for a *new*
    package takes two greps and one JSON read, and one of them has a trap.
    - **Find the conda pull in the wheel script, not the CI yaml.** llvmlite's
      `buildscripts/manylinux/build_llvmlite.sh` sources `prepare_miniconda.sh` (which
      curls a Miniconda installer and installs it *inside* the manylinux container) and
      then `conda install -y -c defaults numba/label/llvm_wheel::llvmdev=22 --no-deps`
      before `python setup.py bdist_wheel`. The channel name is usually also an `env:`
      key in upstream's workflow (`CONDA_CHANNEL_NUMBA: numba/label/llvm_wheel`).
    - **`https://conda.anaconda.org/<channel>/<subdir>/repodata.json` returns `200` for
      a subdir that does not exist** — anaconda.org synthesises an empty index rather
      than 404ing, so a `curl -sI` status check says "yes" for every arch. Read the body
      and count: `linux-64` and `linux-aarch64` each list `llvmdev-22.1.0-manylinux_1.conda`,
      `linux-riscv64` lists **0** packages. (Distinct from gotcha 30, where our own
      registry answers a missing package with a 302.)
    - **Check the installer too, and the version gate.** repo.anaconda.com publishes
      Miniconda3 for `x86_64`/`aarch64`/`s390x` only — no riscv64 — so even the
      bootstrap step has no artifact. And confirm the project can't just use a system
      LLVM: llvmlite's `ffi/CMakeLists.txt` hard-fails unless
      `LLVM_VERSION_MAJOR == LLVMLITE_SUPPORTED_LLVM_VERSION_DEFAULT` (22), and the
      conda recipe builds that LLVM from the `llvm-project` source tarball *with
      patches*, so the distro copy is not a substitute. Report `waiting-on-conda`.

43. **Upstream may not be on git at all — look for the author's own read-only git
    mirror before building a fetch step (the ruamel.yaml.clib case).** PyPI's
    `project_urls` pointed only at a SourceForge **Mercurial** repo, which
    `actions/checkout` cannot fetch, and neither fallback is workable: SourceForge
    serves the anonymous hg endpoint over **http only** (https answers 401), and its
    snapshot-tarball URL returns the commit *page*, not an archive. Do not conclude
    from that that the sdist must be the CI input — check whether upstream keeps a git
    mirror, because a project whose own CI is GitHub Actions necessarily has one.
    `gh api "search/repositories?q=<name>+in:name&sort=updated"` found `ruamel/yaml.clib`
    (the author's, carrying every release tag and the `build_wheels.yaml` upstream
    actually runs); checking it out is *closer* to upstream than any sdist route, so the
    port collapses to the ordinary build-from-checkout shape.
    - **Rank candidates by freshness, not by name.** The obvious-looking mirror
      (`pycontribs/ruamel-yaml-clib`, "read-only git mirror from official hg repository")
      had stopped at 0.2.8 in 2023. Sorting the search by `pushed_at` is what surfaced
      the live one.
    - **Prove the tag is the release before trusting it**: `gh api repos/<m>/tarball/<tag>`
      and diff against the PyPI sdist (`setup.py`, `pyproject.toml`, `LICENSE`, the
      vendored C) — identical files mean the mirror is a faithful export, not a fork.
      Say so in the commit message; a reviewer will ask why the checkout isn't upstream.

44. **Naming a vendored dependency's licence `LICENSE.<dep>` at the project root
    needs no packaging change at all (refines gotcha 32).** Gotcha 32's fix is an
    explicit `license_files=[...]`, which is only necessary when the file lives inside
    the vendored subdirectory. setuptools' *default* `license_files` glob is
    `LICEN[CS]E*`/`COPYING*`/`NOTICE*`/`AUTHORS*` **at the root**, so a file added there
    as `LICENSE.libyaml` is picked up automatically and lands in
    `dist-info/licenses/` beside the project's own — a one-file patch with no
    `setup.cfg`/`setup.py` edit, and no way to accidentally drop the original by
    replacing the default glob with a hand-written list.
    - **Make the patch self-verifying**, since a licence patch that silently stops
      applying still produces a green build: assert it from the test command via the
      installed metadata rather than eyeballing the wheel —
      `[p for p in importlib.metadata.files('<dist>') if '.dist-info/licenses/' in str(p)]`
      compared against the expected set. Check it fails on an unpatched wheel before
      trusting it.

## Environment / auth notes

- **Never write outside the repository.** Worktrees go in `.claude/worktrees/<pkg>`, scratch
  files in `.git/pw-scratch/<pkg>`, local lock state in `.git/pw-locks/`. No files in `$HOME`,
  `~/.local/bin`, `/tmp`, or sibling directories, and **no installing software** on the host
  (brew/apt/dnf/npm/pip). If you think you need either, ask first.
- **Commit identity is `Ludovic Henry <git@ludovic.dev>`** and is already configured. Never
  pass `-c user.email`/`-c user.name` or set `GIT_AUTHOR_*`/`GIT_COMMITTER_*` — in particular
  do not use the user's address from your own session context, which is a *different*
  address. A `pre-commit` hook rejects any other identity (and any workflow adding
  `BUILD_VERBOSITY`); if it fires, fix the command, don't bypass the hook.

- **Pushing workflow files needs `workflow` scope** on the gh token, else the push is
  rejected ("refusing to allow an OAuth App to create or update workflow … without
  `workflow` scope"). Fix: `gh auth refresh -h github.com -s workflow` (interactive).
- `origin` (`riseproject-dev/python-wheels`) is canonical; there is no separate
  `upstream` remote. Branch from `origin/main`.
- Use `gh` extensively for anything requiring access to GitHub.

## Patching a project

Patching is decided case by case and reviewed as such — test as much real functionality as
possible rather than patching failures away. A patch is justified when the failure is:

- in a narrow part of the module, or dependent on external resources (large downloads);
- caused by software unavailable on riscv64;
- an artificial test limitation (a fixed timeout, say) rather than a real defect;
- from build scripts calling host tooling absent on the runners or in the riscv64 manylinux
  image (`apt` vs `dnf`);
- a missing LICENSE the project or a dependency requires (see Licensing below).

Mechanics: put the patch under `patches/<pkg>/<version_tag>/`, add a `git apply` step before
the build/test step, document the change on the package's docs entry, and give every patch an
`Upstream-Status:` tag — `ci_scripts/check_patch.py` enforces its presence on PRs. Extra
detail in the commit message beyond the tag pays for itself at maintenance time. The five
valid types:

| Type | Use when | Must include |
|---|---|---|
| `Issue` | build/test found a bug, reported upstream | link to the issue |
| `Submitted` | fix sent upstream, carried until merged + released | link to the PR/commit |
| `To upstream` | needs upstreaming, but submission is blocked | why it's blocked |
| `Inappropriate` | needed for riscv64/our infra, irrelevant upstream | short reason |
| `Backport` | already fixed in a later upstream release | link + description |

## Licensing and GPL sources

RISE distributes these wheels, so licence compliance is ours. Check two things per port:

- the built wheel carries the LICENSE file(s) from the upstream source;
- if it ships statically or dynamically linked libraries from other projects, their licence
  requirements are met too.

If either fails, patch the build (above) and send the fix upstream as well.

When a build links GPL components that come from **our build environment** rather than the
project — most often the `gcc` baked into the manylinux_riscv64 image — we must make those
sources available permanently, not just for CI's artifact retention window. Add a
`gpl_sources` job beside `build_wheels` using the `collect-gpl-sources` action, give it the
**same pinned `MANYLINUX_RISCV64_IMAGE`** the build used (otherwise the sources don't
correspond to the toolchain that produced the wheels), add it to the publish job's `needs:`,
and pass the artifact through:

```yaml
gpl-sources-artifact: <pkg>-<version>-gpl-sources
gpl-sources-release-tag: <pkg>-v<version>
gpl-sources-description: gcc
```

`publish-wheels` attaches the tar to a GitHub Release (creating it if needed) and hands the
download URL to `update_doc.py`, which renders it as that version's `comment:` — no manual
docs edit. `build-numpy.yml` is the complete example.

## PR / CI conventions

- `pr-checks.yml` rejects commits starting with `revertme`/`revert me`/`DO NOT MERGE`
  and validates `Upstream-Status:` headers in added/modified patches under `patches/`.
- Sanity that the `publish` job **dry-ran** on your PR branch (grep its log for
  "Dry run (not on main branch …)"); it should list the wheels it *would* upload
  without uploading.
- **Merging does not publish.** `publish-wheels`/`publish-to-gitlab` only do the real thing
  (twine upload, GPL-sources release, docs PR) when the run's ref is `main`; on any other
  ref they print a dry run — resolved globs, the twine command, the branch/PR title
  `update_doc.py` would have used. That is deliberate: only reviewed, merged workflows push
  packages. After your PR merges, **re-trigger the workflow from `main`** for the wheels to
  actually reach the registry.
