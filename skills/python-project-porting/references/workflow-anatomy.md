## Anatomy of a build-<pkg>.yml

Standard triggers (copy from an existing workflow):

```yaml
on:
  workflow_dispatch:
    inputs:
      version: { description: '<pkg> version/tag', required: true, default: '<latest stable>' }
  pull_request:
    paths: ['.github/workflows/build-<pkg>.yml']   # CI runs when you edit the workflow itself
```

**Both triggers, always.** `pull_request: paths` is not optional and is not redundant with
`workflow_dispatch`: it is the only thing that can produce a new workflow's first run, and
without it the workflow is never registered, so `workflow_dispatch` and `Trigger:` both
fail with `HTTP 404` (gotcha 54; this is why #364 was reverted by #391). Never ship a
`build-<pkg>.yml` with `workflow_dispatch` alone.

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

The `publish` job always calls the shared reusable workflow — it dry-runs off
`main`, so it is safe on PR branches:

```yaml
publish:
  needs: [<build jobs>]
  permissions: { contents: write, pull-requests: write }
  uses: $/.github/workflows/_publish_wheel.yml
  with:
    artifact-pattern: <pkg>-${{ needs.<sdist-job>.outputs.package_version }}-*-manylinux_riscv64
```

`_publish_wheel.yml` auto-creates `docs/packages/<pkg>.yaml` from the wheel metadata on
first publish (`ci_scripts/update_doc.py`). Nightly checks and docs are driven off
that YAML, so **a new package needs no manual registration anywhere** — just the
workflow. Don't hand-write the docs YAML unless you need a `comment`/`warning`.
`permissions` needs `contents: write` **and** `pull-requests: write` (not `contents: read`)
because that docs step pushes a branch and opens a PR with the default `GITHUB_TOKEN`.

