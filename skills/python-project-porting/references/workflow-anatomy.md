## Anatomy of a build-<pkg>.yml

Standard triggers (copy from an existing workflow):

```yaml
on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version glob to (re)build; empty builds every version of docs/packages/<pkg>.yaml not released yet'
        required: false
        default: ''
  pull_request:
    branches: [main]
    paths: ['.github/workflows/build-<pkg>.yml', 'docs/packages/<pkg>.yaml']
  push:
    branches: [main]
    paths: ['.github/workflows/build-<pkg>.yml', 'docs/packages/<pkg>.yaml']

concurrency:
  group: ${{ github.workflow }}-${{ github.head_ref || github.run_id }}
  cancel-in-progress: true
```

**All three triggers, always.** `pull_request: paths` is not optional and is not redundant
with `workflow_dispatch`: it is the only thing that can produce a new workflow's first run,
and without it the workflow is never registered, so `workflow_dispatch` fails with
`HTTP 404` (gotcha 54; this is why #364 was reverted by #391). `push` is what builds and
publishes the pending versions once the PR merges. Never ship a `build-<pkg>.yml` with
`workflow_dispatch` alone, and never bake a version literal into the workflow.

**The versions come from `docs/packages/<pkg>.yaml`.** A port adds that file alongside the
workflow:

```yaml
package-name: <pkg>
source-code: <repo url>
license: <SPDX id>
versions:
- version: <wheel version>
  python-versions: ['3.12', '3.13', '3.14', '3.14t']   # filled in by check_versions.py
```

An entry with neither `tag:` nor `files:` is pending. The `setup` job hands the pending
versions (or the ones matching the dispatch glob) to every other job as `matrix.version`:

```yaml
jobs:
  setup:
    uses: $/.github/workflows/_setup.yml
    with:
      package: <pkg>
      version: ${{ inputs.version }}
      python-matrix: true                        # per-version interpreters, see below

  build_wheels:
    needs: [setup]
    if: needs.setup.outputs.versions != '[]'     # GHA rejects an empty matrix vector
    name: Build <pkg> ${{ matrix.version }} ${{ matrix.python }}-manylinux_riscv64
    strategy:
      fail-fast: false
      matrix:
        include: ${{ fromJSON(needs.setup.outputs.matrix) }}
    env:
      <PKG>_VERSION: ${{ matrix.version }}       # steps keep using env.<PKG>_VERSION
```

Every job that consumes the matrix carries the `if:` guard, the `version:` vector (or the
`include:` matrix, for the build jobs) and (for
`runs-on` jobs) the `env:` line; a `uses:` job (publish) takes no `env:`. `version` is the
version the **wheel** will carry — `update_doc.py` refuses to document a wheel whose version
is not declared — so the workflow derives the git ref from it (`ref: v${{ env.X_VERSION }}`,
or a small `run:` step for irregular tags, see `build-rtoml.yml`/`build-torch.yml`), never the
reverse. **Job outputs are not per matrix leg**: never pass the sdist filename or version
through `outputs:`; name the artifact `<pkg>-${{ env.X_VERSION }}-sdist`, upload
`dist/*.tar.gz`, and resolve it on the consumer side with a `steps.sdist_path` echo (see
`build-bcrypt.yml`).

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

**The interpreter matrix comes from upstream, per version (`python-matrix: true`).** There
is no RISE-wide list of Python versions any more. Each version entry of the package YAML
carries `python-versions`, the interpreters upstream built that release for, and
`_setup.yml` outputs `matrix`, an `include:` list of `{version, python}` pairs built from it
by `ci_scripts/pending_versions.py --python-matrix` (no network access needed).

`python-versions` is written by `ci_scripts/check_versions.py` from upstream's wheels on PyPI:
the nightly job adds it to every version it declares; for a version you add by hand, run
`uv run --with-requirements ci_scripts/requirements.txt python3 ci_scripts/check_versions.py --python-versions <pkg>`. It maps:

- `cpXY-cpXY` / `cpXY-cpXYt` wheels to `'3.X'` / `'3.Xt'`; a `cpXY-abi3` wheel to one
  `'3.X'` build (gotcha 11), so abi3 packages collapse on their own.
- No version-specific wheels (sdist-only, pure): `requires_python` decides, without
  free-threaded builds. Not on PyPI at all: nothing is written; add it by hand.

Values must be quoted strings (`'3.10'`, not `3.10`, which YAML reads as 3.1);
`pending_versions.py --check` (run by pr-checks) rejects anything else. When building the
matrix, versions riscv64 can't build are dropped: the matrix is limited to `RISCV64_PYTHONS`,
the `*-manylinux_riscv64` identifiers of the pinned cibuildwheel (cp39…cp315t, no cp313t).
Update that list when bumping cibuildwheel; it is a technical limit, not a policy.

Override in two ways, each with a comment saying why. Edit a version's `python-versions` to
build more or fewer interpreters than upstream for that version (e.g. add `'3.14t'`). Use the
`python-exclude` input to drop tags for every version: `python-exclude: "cp39 cp315*"` drops
cibuildwheel tags (globs) that can't work on riscv64 — e.g. a dependency with no riscv64
wheel for an old interpreter (numpy ≥ 2.5 has none below cp312).

**Converting old workflows is gradual.** Most `build-<pkg>.yml` still hard-code `python:
[...]` next to `version:`. When a workflow is touched to build a new release, switch it:
make sure the new version's entry has `python-versions`, add `python-matrix: true` to the
`setup` call, and replace the `version:` + `python:` vectors
of the build job(s) with `include: ${{ fromJSON(needs.setup.outputs.matrix) }}` (see
`build-falcon.yml`). The matrix may grow (cp310/cp311, cp315/cp315t): exclude what fails for
riscv64-specific reasons rather than reverting to a hard-coded list. Workflows whose extra
axes (`libc`, `build`) don't fit a `{version, python}` include can stay hard-coded.

A JSON `include:` can't carry per-entry keys (`test_skip`, `pytest_k`, …) or be trimmed by
`exclude:`, so compute per-interpreter values in expressions instead, e.g.
`CIBW_TEST_SKIP: ${{ endsWith(matrix.python, 't') && '*' || '' }}`.

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
  an sdist and uploads it as `<pkg>-<version>-sdist`; job 2 (a
  matrix over the interpreters) downloads the sdist, extracts it, and
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
  **bare interpreter tags** (`cp312`, `cp314t`, as `python-matrix` emits them) and the
  `-manylinux_riscv64` suffix is appended at each use site (job `name:`, cibuildwheel
  `only:`, artifact `name:`) — cleaner than embedding the full `cp312-manylinux_riscv64`
  tag in the matrix (the older `build-onnx.yml` `matrix.build` style).

When cibuildwheel doesn't fit, drive the build container yourself. Two sub-shapes:
- **`container:`** (see `build-torch.yml`): the GHA `container:` key on the job — works when the
  build is a self-contained shell script inside a known image.
- **`podman run` or `docker run`** (see `build-orjson.yml`): explicit container invocation on the
  runner — used when the build script already lives in the upstream repo or when orjson-style
  per-interpreter looping is needed. See gotcha 15 for the heavy C++ variant.

The `publish` job always calls the shared reusable workflow — it dry-runs off
`main`, so it is safe on PR branches:

```yaml
publish:
  name: Publish <pkg> ${{ matrix.version }}
  needs: [setup, <build jobs>]
  if: needs.setup.outputs.versions != '[]'
  strategy:
    fail-fast: false
    matrix:
      version: ${{ fromJSON(needs.setup.outputs.versions) }}
  permissions: { contents: write, pull-requests: write }
  uses: $/.github/workflows/_publish-wheel.yml
  with:
    artifact-pattern: <pkg>-${{ matrix.version }}-*-manylinux_riscv64
```

`_publish-wheel.yml` fills the version's entry of `docs/packages/<pkg>.yaml` with the
release tag and wheel files (`ci_scripts/update_doc.py`) and adds the package to
`ci_scripts/packages.txt` on first publish, so beyond the YAML **a new package needs no
manual registration anywhere**. Per-version `patched: true`, `comment:` and `warning:` keys
may be pre-filled on the pending entry. `permissions` needs `contents: write` **and**
`pull-requests: write` (not `contents: read`) because that docs step pushes a branch and
opens a PR with the default `GITHUB_TOKEN`.

