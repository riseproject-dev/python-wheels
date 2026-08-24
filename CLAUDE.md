# CLAUDE.md — python-wheels porting playbook

Guidance for adding a new package's riscv64 wheel build to this repo. Written
from the protobuf port; generalized so the next one is faster. Read the
"Gotchas" section before you start — several cost a full CI cycle each (minutes
for a simple package, hours for one that compiles a C++ world like pyarrow).

## What this repo does

Builds riscv64 wheels for packages that don't ship them on public PyPI, and
publishes them to `pypi.riseproject.dev`. Each package gets a
`.github/workflows/build-<pkg>.yml`. Wheels are consumed on `ubuntu-24.04-riscv`
self-hosted runners.

## Working process

Given a package to port, the loop is always the same (project-specific inputs —
name, repo, version, upstream build docs — come from the invoking prompt):

1. Branch `<pkg>` from `origin/main` and work in a dedicated git worktree.
2. Add `.github/workflows/build-<pkg>.yml` following the playbook below.
3. Validate locally (gotcha 9), then push to `origin` and open a PR. The
   `pull_request: paths` trigger runs the workflow on the PR branch.
4. Watch CI, triage failures, iterate until every matrix job is green and the
   `publish` job dry-runs cleanly.
5. When the wheels build and tests pass, reply to any review threads, then
   record reusable, project-agnostic learnings back into this file.

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

Two build shapes exist in the repo — pick based on the package:

- **sdist → bdist** (see `build-cffi.yml`, `build-protobuf.yml`): job 1 produces
  an sdist and uploads it + exposes `package_version` as a job output; job 2 (a
  matrix over `cp312/cp313/cp314/cp314t`) downloads the sdist, extracts it, and
  runs `cibuildwheel ./extracted`; job 3 publishes. cibuildwheel also accepts the
  sdist tarball directly as `package-dir` (it extracts internally), so you can skip
  the manual `tar zxf` (see `build-apache-tvm-ffi.yml`).
- **build-from-checkout** (see `build-onnx.yml`, `build-xgrammar.yml`, `build-sentencepiece.yml`, `build-torchaudio.yml`):
  check out the upstream tag with submodules, then use `uses: pypa/cibuildwheel@<sha>` directly
  (no `setup-uv` / `uv pip install cibuildwheel` step needed — the action bundles its own
  Python). Pass `only: ${{ matrix.python }}-manylinux_riscv64` and feed native deps via
  `CIBW_ENVIRONMENT`/CMake, or a prebuilt dependency wheel from our registry via
  `CIBW_BEFORE_BUILD` (torchaudio pulls `torch` this way — see gotcha 17).

When cibuildwheel doesn't fit, drive the manylinux container yourself with a
plain **`docker run`** (see `build-torch.yml`, `build-pyarrow.yml`; gotcha 15).

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
   → no before-build needed; (c) the dep is another Python wheel we already ship
   (torchaudio needs `torch`) → `pip install` it from our registry in
   `CIBW_BEFORE_BUILD` (see gotcha 17).

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
   - **Run cibuildwheel under QEMU** on a non-riscv host (the whole torchaudio
     build+smoke loop was done on aarch64 this way):
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

10. **Rust/PyO3 (maturin) packages — three traps.**
    - **Floating deps in a locally-built sdist.** If upstream gitignores `Cargo.lock`
      (common for libraries), a fresh `python -m build --sdist` re-resolves crates to
      today's latest semver-compatible versions. With `#![deny(warnings)]`, a newly
      deprecated API in a bumped dep becomes a hard compile error. Fix: pin the
      offending crate to the version upstream released against *before* building the
      sdist, so maturin captures it into the bundled lock:
      ```bash
      cargo update -p <crate> --precise <version>
      python -m build --sdist
      ```
      Diagnose: grep CI log for `use of deprecated` / `could not compile`.
    - **Rust toolchain must be installed inside the manylinux container.** If the
      project's `pyproject.toml` has a `[tool.cibuildwheel] before-all` that does this
      (tiktoken does), it's inherited automatically. Otherwise supply it yourself:
      `CIBW_BEFORE_ALL_LINUX: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y`
      and `CIBW_ENVIRONMENT_LINUX: PATH="$PATH:$HOME/.cargo/bin"`. rustup provisions a
      native `riscv64gc-unknown-linux-gnu` toolchain in the container.
    - **musllinux can't build** — rustup.rs ships no riscv64 musl toolchain. Restrict
      `CIBW_BUILD` to `*-manylinux_riscv64`. PyO3 extensions are generally not abi3, so
      the matrix is per-interpreter `[cp312, cp313, cp314, cp314t]`.

11. **abi3 wheels collapse the matrix.** If `pyproject.toml` sets `wheel.py-api = "cpXY"`
    (or otherwise builds abi3/limited-API), one `cpXY` build loads on every newer
    non-free-threaded CPython, so the matrix is just `[cpXY, cp3Nt]` — the abi3 build
    plus a free-threaded build (free-threaded can't use the stable ABI). Tell from the
    PyPI wheel names: `…-cp312-abi3-…` + `…-cp314-cp314t-…` = exactly two builds (same
    shape as onnx/hf-xet, and apache-tvm-ffi). Don't add cp313/cp314 — they'd duplicate
    the cp312 abi3 wheel.

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

15. **Heavy C++ ports (pyarrow): drive `docker run` yourself, build the C++ once.**
    When the extension links a big C++ tree whose sources sit *beside* the Python
    package (pyarrow = Cython over Arrow C++ in a sibling `cpp/`), cibuildwheel's
    copy-the-package-dir model can't see them, and the manylinux image ships no
    Node so a `container:` job can't run JS actions. So: checkout + upload-artifact
    on the host, and a `docker run` step that bind-mounts the source and an
    inline-written build script into `$MANYLINUX_RISCV64_IMAGE`. Build the C++ lib
    **once** into a prefix, then loop the interpreters (`for pytag in $PYTHON_TAGS`)
    building only the bindings against it — don't rebuild C++ per Python.
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

17. **Building an extension that links another wheel we ship (the torch /
    domain-library pattern; see `build-torchaudio.yml`).** torchaudio's extension
    links `libtorch`/`libc10`/… which come from the `torch` wheel — a 130MB riscv64
    wheel that exists only on our registry. Four pieces have to line up:
    - **Install the dep from our registry in `CIBW_BEFORE_BUILD`:**
      `pip install --only-binary=:all: torch>=2.11 setuptools wheel ninja`.
      `--only-binary=:all:` is load-bearing — without it pip silently falls back to
      building the dep from source in-container when public PyPI has no riscv64
      wheel. Prefer a range (`torch>=2.11`) over a hard pin so it resolves to
      whatever's latest on the registry (torchaudio targets torch's stable ABI and
      pins no version at runtime; confirm your package's compat policy).
    - **Pass `PIP_EXTRA_INDEX_URL` into the build**, not just the test step:
      `CIBW_ENVIRONMENT: … PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/`,
      so the dep and its own deps resolve from our registry inside the container.
    - **Disable build isolation** when `setup.py` imports the dep at module top and
      declares no `[build-system]` table (legacy setuptools):
      `CIBW_BUILD_FRONTEND: "pip; args: --no-build-isolation"`. Otherwise the build
      env can't see the preinstalled dep.
    - **Exclude the dep's shared libs from the auditwheel repair**, or auditwheel
      vendors all of them in (a 1.2MB wheel becomes ~130MB). Find the list by
      unzipping the dep wheel and listing `*/lib/*.so`; then:
      ```
      CIBW_REPAIR_WHEEL_COMMAND: >-
        auditwheel repair -w {dest_dir} {wheel}
        --exclude libtorch.so --exclude libtorch_cpu.so --exclude libtorch_python.so
        --exclude libtorch_global_deps.so --exclude libc10.so
        --exclude libgomp.so.1 --exclude libgfortran.so.5 --exclude libopenblas.so.0
      ```
      This mirrors how upstream ships domain-library wheels — libtorch is assumed
      present at runtime (torch is imported first and loads them `RTLD_GLOBAL`).
    - Note: `py_limited_api=True` does **not** guarantee a single abi3 wheel here.
      torchaudio sets it but still needs a per-CPython build because it links the
      version-specific `libtorch_python.so`. Check what the extension links before
      trimming the matrix (build-onnx.yml *does* get one abi3 wheel; torchaudio
      doesn't).

18. **The wheel-filename version is canonical; keep three places in sync** (see
    PR #246, which fixed broken doc links from exactly this). Whatever version ends
    up in the `.whl` filename (driven by `BUILD_VERSION`) must match, byte for byte:
    (1) the wheel filename, (2) the `docs/packages/<pkg>.yaml` `version:` key
    (auto-populated by `update_doc.py` from the wheel), and (3) the
    `patches/<pkg>/<version>/` directory name — `docs/.../generate_packages_doc.py`
    links patches as the literal path `patches/{name}/{version}`, so a mismatch is a
    404. torch ships a **local segment** (`2.13.0+cpu`, pytorch's CPU-index
    convention) so its patches live under `patches/torch/2.13.0+cpu/`.
    **Match upstream's own PyPI filename convention:** torchaudio ships plain
    `2.11.0` on PyPI, so we build plain `2.11.0` (`BUILD_VERSION=<tag>`), no `+cpu`.
    Decoupled from all this: the nightly `check_versions.py` compares the workflow's
    `version:` **input default** against PyPI — keep that the plain upstream version,
    regardless of any local segment `BUILD_VERSION` adds.

## Environment / auth notes (this WSL setup)

- **Pushing workflow files needs `workflow` scope** on the gh token, else the push is
  rejected ("refusing to allow an OAuth App to create or update workflow … without
  `workflow` scope"). Fix: `gh auth refresh -h github.com -s workflow` (interactive).
- `origin` (`riseproject-dev/python-wheels`) is canonical; there is no separate
  `upstream` remote. Branch from `origin/main`.
- Use `gh` extensively for anything requiring access to GitHub.

## PR / CI conventions

- `pr-checks.yml` rejects commits starting with `revertme`/`revert me`/`DO NOT MERGE`
  and validates `Upstream-Status:` headers in added/modified patches under `patches/`.
- Sanity that the `publish` job **dry-ran** on your PR branch (grep its log for
  "Dry run (not on main branch …)"); it should list the wheels it *would* upload
  without uploading.
