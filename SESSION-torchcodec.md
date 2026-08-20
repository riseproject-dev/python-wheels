# Session summary — porting `torchcodec` 0.16.0 to riscv64 wheels

Status as of 2026-08-20. **PAUSED** — blocked on an external dependency:
riscv64 conda packages (ffmpeg + a conda/mamba bootstrap) do not exist yet.
This file is a working scratchpad for resuming; it is **not meant to be
committed** (mirrors the `SESSION-torchvision.md` convention on the
`torchvision` branch).

Companion memory: `memory/torchcodec-port.md` (persists across sessions and
holds the same core facts). Sibling precedent: `memory/torchaudio-port.md`,
`SESSION-torchvision.md` on branch `origin/torchvision`.

---

## Goal

Add `.github/workflows/build-torchcodec.yml` producing riscv64 wheels for
torchcodec 0.16.0, published to `pypi.riseproject.dev`, following the porting
playbook in `CLAUDE.md`. Full loop: branch + worktree → workflow → validate
locally under QEMU → push → PR → watch CI → iterate to green + clean publish
dry-run → fold learnings back into `CLAUDE.md`.

## Coordinates

- PyPI distribution: `torchcodec`
- Version/tag: `0.16.0` (git tag `v0.16.0`, commit `ce046a849e8a` — note the
  repo moved from `pytorch/torchcodec` to **`meta-pytorch/torchcodec`**; raw
  files at `raw.githubusercontent.com/meta-pytorch/torchcodec/v0.16.0/<path>`).
- Source repo: https://github.com/meta-pytorch/torchcodec
- PyPI: https://pypi.org/project/torchcodec/ ; docs:
  https://meta-pytorch.org/torchcodec/stable/index.html
- Pairs with **torch 2.13** (torchcodec 0.16 is ABI-stable w.r.t. torch since
  2.11; our registry has torch 2.13.0+cpu riscv64 — see matrix below).

## Environment (this WSL setup)

- Worktree: `.claude/worktrees/torchcodec`, branch **`torchcodec`**, based on
  `origin/main` @ `03d1611` (playbook-compliant: branch `<pkg>` from
  `origin/main`).
- Docker 29.1.3 available; QEMU `qemu-riscv64` binfmt **registered**; the
  `quay.io/pypa/manylinux_2_39_riscv64` image pulls/runs under QEMU. So **local
  validation under QEMU is possible** once the dep blocker is resolved.
- Push caveats (from `memory/wsl-git-network-auth-broken.md`): needs `workflow`
  scope on the gh token to push `.github/workflows/*`; use gh-HTTPS push in this
  WSL setup, not SSH.

---

## Research — what was established (all verified at the v0.16.0 tag)

### Build shape = build-from-checkout (like build-onnx / build-torchaudio)
- **No PyPI sdist** for 0.16.0 (only a `0.0.0.dev0` placeholder across all
  history). Must build from a **git checkout at `v0.16.0`**.
- **Tag maps 1:1 to version**: `version.txt` = `0.16.0`;
  `packaging/torchcodec_version.py` returns `$BUILD_VERSION` if set, else
  `version.txt` + `+<sha>`. So set **`BUILD_VERSION=0.16.0`** to get a clean
  version — no tag→version translation (unlike protobuf).

### Build system = scikit-build-core (NOT setuptools)
- `pyproject.toml`: `[build-system] requires = ["scikit-build-core>=0.10",
  "pybind11"]`, `build-backend = "scikit_build_core.build"`.
- **torch is deliberately NOT in build requires** → **must build with
  `--no-build-isolation` and torch preinstalled** (same constraint as
  torchaudio/torchvision).
- Build deps to preinstall in-container: **torch 2.13.0+cpu** (from our
  registry), **`scikit-build-core>=0.10`** + **`pybind11`** (pip, pure-python),
  **`ninja`** (pip wheel exists for riscv64, or `dnf install ninja-build`).
- `find_package(Torch)` "just works": root `CMakeLists.txt` auto-detects
  `import torch; torch.utils.cmake_prefix_path` and appends it to
  `CMAKE_PREFIX_PATH`. No `-DTorch_DIR` needed as long as torch is importable in
  the build interpreter (guaranteed by `--no-build-isolation`).
- CMake toggles exposed via env (`[tool.scikit-build.cmake.define]`):
  `ENABLE_CUDA`, `TORCHCODEC_DISABLE_COMPILE_WARNING_AS_ERROR` (set to `1` on a
  new arch to drop `-Werror`), `TORCHCODEC_BUILD_IMAGE` + per-codec
  `TORCHCODEC_BUILD_{JPEG,PNG,WEBP,AVIF,GIF,HEIC,NVJPEG}`.
- Upstream build cmd (x86/aarch64): `BUILD_AGAINST_ALL_FFMPEG_FROM_S3=1 python
  -m build --wheel -vvv --no-isolation`.

### torch dependency
- Not pinned at build or runtime (`install_requires` has no torch; stable ABI,
  `TORCH_TARGET_VERSION=0x020b...` = torch 2.11). Needs torch **>= 2.11**.
- Registry has **torch 2.13.0+cpu riscv64** for **cp312 / cp313 / cp314 /
  cp314t** only. So **matrix = those 4** (torchcodec supports cp310–cp314t, but
  torch availability gates us). **Per-CPython wheels, NOT abi3** (links
  libtorch_python).

### FFmpeg — the hard part
- torchcodec supports FFmpeg majors **4–9**; ships one
  `libtorchcodec_core{N}.so` + `libtorchcodec_custom_ops{N}.so` per major it was
  built against, and **dlopens highest-first at runtime** (9→8→…→4) via
  `torch.ops.load_library`. FFmpeg is **NOT bundled in the wheel** — it's a
  runtime dependency the user supplies (upstream `repair_wheel.py` excludes
  `libav*`/`libsw*`/`libpostproc*`).
- Two mutually exclusive build modes in
  `src/torchcodec/_core/CMakeLists.txt`:
  - **Mode A** `BUILD_AGAINST_ALL_FFMPEG_FROM_S3=1`: FetchContent downloads
    prebuilt non-GPL FFmpeg 4/5/6/7/8/9 from
    `pytorch.s3.amazonaws.com/torchcodec/ffmpeg/2025-03-14/<platform>/`.
    **Platforms: linux_x86_64 / linux_aarch64 / macos_arm64 / windows_x86_64 —
    NO riscv64.** Cannot use. (Same for the S3 libavif in
    `fetch_avif_from_s3.cmake`, `2026-07-22` bucket — no riscv64.)
  - **Mode B** (else branch): `add_ffmpeg_target_with_pkg_config` →
    `pkg_check_modules(REQUIRED IMPORTED_TARGET libavdevice libavfilter
    libavformat libavcodec libavutil libswresample libswscale)`, maps libavcodec
    soname major → ffmpeg major, builds **ONE** core lib. **This is the riscv64
    path.** Needs pkg-config + FFmpeg **dev** libs at build time.
- **License guard** (CMakeLists lines 10–17): a wheel build FATAL_ERRORs unless
  `BUILD_AGAINST_ALL_FFMPEG_FROM_S3` **or**
  `I_CONFIRM_THIS_IS_NOT_A_LICENSE_VIOLATION` is set. For Mode B we must set
  **`I_CONFIRM_THIS_IS_NOT_A_LICENSE_VIOLATION=1`**.
- **Which FFmpeg major to target:** **6** (`libavcodec.so.60`). Ubuntu 24.04
  (noble) riscv64 — the stated consumer platform — ships **FFmpeg 6.1.1**
  (`7:6.1.1-3ubuntu5`, `libavcodec60`). Building torchcodec against major 6 means
  the published wheel loads the FFmpeg users already have. libavcodec→ffmpeg map:
  58→4, 59→5, **60→6**, 61→7, 62→8, 63→9.

### Runtime FFmpeg for the smoke test needs a FUNCTIONAL, GPL FFmpeg
- `test/smoke_test.py` **generates** its own media by encoding then decoding
  (VideoEncoder→`to_file("test.mp4", crf=0)` etc.), so runtime FFmpeg must have
  real encoders/muxers — not the bare LGPL skeleton
  `packaging/build_ffmpeg.sh` produces (that's fine only to *link* against).
- The **default mp4 codec is H.264** (`oformat->video_codec`); FFmpeg has **no
  native H.264 encoder** → needs **libx264 (GPL)** (`--enable-gpl
  --enable-libx264`). Audio path uses wav/pcm (fine). CI decision (below) was to
  build a functional FFmpeg **with libx264** for the test runtime — GPL is OK
  because FFmpeg is never shipped in the wheel.

### Image codecs
- Building all image decoders is default-ON and *required* (fails loudly if a
  codec lib is missing). `TORCHCODEC_BUILD_IMAGE=0` turns them into
  runtime-raising stubs AND skips the S3 libavif fetch + libheif.
- **AVIF is infeasible on riscv64 in 0.16.0**: `fetch_avif_from_s3.cmake` is
  hardcoded (S3, no riscv64) with **no `find_package(libavif)` fallback** — a
  conda/system libavif would NOT be picked up without patching CMake.
- JPEG/PNG/WEBP use standard `find_package(JPEG|PNG|WebP)`; **HEIC** uses
  `find_package(libheif CONFIG)` then pkg-config fallback — all can come from
  system/conda if present.
- Skip logic: image tests carry `@needs_{jpeg,png,webp,avif,heic}` marks and
  **auto-skip** when the lib is absent, UNLESS `FAIL_WITHOUT_IMAGE_CODECS=1`.
  **`test_decode_gif` has NO mark** (giflib is vendored) so it always runs — if
  image is fully disabled, run a curated smoke test, not the whole file.

### Testing (upstream)
- Build-box smoke test is a no-op (`packaging/fake_smoke_test.py` prints
  "Success"). Real testing is a separate `install-and-test` job across
  `python × ffmpeg-version ∈ {4..9}`: installs wheel + torch + conda ffmpeg,
  runs `python packaging/assert_ffmpeg_version.py <major>` then
  `FAIL_WITHOUT_IMAGE_CODECS=1 pytest test/smoke_test.py`; full `pytest test`
  only when ffmpeg==7.
- **Test assets are in the git repo** under `test/resources/` (159 files); they
  are NOT in any wheel/sdist. `test/smoke_test.py` mostly self-generates media;
  image tests use the bundled `GRADIENT_*` files.
- Test deps: `numpy pytest pillow` (the `dev` extra) — pull from our registry
  via `PIP_EXTRA_INDEX_URL` (pillow/numpy lack public riscv64 wheels).

### manylinux_2_39_riscv64 build container inventory (verified under QEMU)
- Rocky Linux 10.2. Has: **cmake 4.4.2, gcc/g++ 14.3, make, git, perl, xz, tar,
  patchelf, pkg-config 2.1.0**. Python interpreters in `/opt/python/`
  (cp310…cp315 incl. cp314t).
- **Missing: ninja** (pip `ninja` riscv64 wheel exists; or `dnf install
  ninja-build` from crb). **No FFmpeg, no nasm/yasm** (nasm irrelevant on riscv64
  — FFmpeg configure needs `--disable-x86asm`).
- zlib is present (`zlib.h` + `/usr/lib64/pkgconfig/zlib.pc`, `libz.so`),
  `libpng16.so.16` runtime present but **no `png.h`** by default.

---

## Decisions taken with the user (this session)

1. **Test strategy = "Faithful + libx264"**: build a functional FFmpeg 6.x
   **with libx264** (GPL, build/test-only, never shipped) and run upstream's own
   `pytest test/smoke_test.py` (image tests auto-skip / gif handled).
2. **Image scope = "Add jpeg/png/webp"**: build against libjpeg-turbo + libpng +
   libwebp and vendor them into the wheel (auditwheel). AVIF + HEIC stay off
   (avif infeasible; heif optional/omitted for first wheel).
3. **conda channel = conda-forge**, **conda made available by bootstrapping**
   Miniforge/micromamba in `CIBW_BEFORE_ALL`.

→ **Decisions 3 is now BLOCKED (see below). Decisions 1–2 stand but their
implementation depends on how the FFmpeg/x264 blocker is resolved.**

---

## BLOCKER / why paused

The conda approach for the FFmpeg (+x264) runtime is **not available on riscv64
today**, confirmed by inspecting conda-forge's repodata directly:

- `https://conda.anaconda.org/conda-forge/linux-riscv64/repodata.json` **exists**
  (HTTP 200) but is tiny (~228 KB, **224 packages**) — it's essentially just the
  **conda-forge bootstrap toolchain** (gcc, binutils, gfortran, cmake, curl,
  fmt, freetype, fontconfig, brotli, bzip2, …).
- **Absent from conda-forge/linux-riscv64:** `ffmpeg` (0), `x264` (0), `x265`
  (0), `libwebp` (0), `libheif` (0), **`python` (0)**, **`conda`/`mamba` (0)**.
  Present: `libjpeg-turbo` (1), `libpng` (1) — but those we can get from dnf
  anyway.
- **No riscv64 Miniforge/micromamba installer** (mamba-org micromamba-releases
  has no `linux-riscv64` asset). So even bootstrapping conda-the-tool into the
  container isn't possible yet, independent of package availability.

**User will resume when these deps become available** (riscv64 ffmpeg on a conda
channel + a way to run conda on riscv64), OR when we decide to switch to the
source-build fallback.

---

## Dependency list (what torchcodec needs on riscv64, and where each can come from)

| Dependency | Role | dnf (Rocky 10.2 riscv64)? | conda-forge riscv64? | Plan |
|---|---|---|---|---|
| torch 2.13.0+cpu | build+runtime | n/a | n/a | **pypi.riseproject.dev** (cp312/313/314/314t) |
| scikit-build-core, pybind11 | build backend | n/a | n/a | **pip** (pure-python) |
| ninja | build | ✅ `ninja-build` (crb) | — | pip `ninja` or dnf |
| **FFmpeg 6.x (dev)** | **build (Mode B pkg-config)** | ❌ none | ❌ none | **BLOCKED** — build from source, or conda when it exists |
| **FFmpeg 6.x + libx264** | **test runtime (functional+GPL)** | ❌ none | ❌ none | **BLOCKED** — build from source, or conda when it exists |
| libjpeg-turbo (dev) | image build+vendor | ✅ `libjpeg-turbo-devel` 3.0.2 | ✅ | **dnf** |
| libpng (dev) | image build+vendor | ✅ `libpng-devel` 1.6.40 | ✅ | **dnf** (zlib already present) |
| libwebp (dev) | image build+vendor | ✅ `libwebp-devel` 1.3.2 | ❌ | **dnf** |
| libavif | AVIF decode | ❌ | ✅ (but unused) | **infeasible** — CMake hardcodes S3, no find_package fallback |
| libheif | HEIC decode | ❌ | ❌ | **optional/omitted** for first wheel |
| numpy, pytest, pillow | test | n/a | n/a | **pypi.riseproject.dev** via PIP_EXTRA_INDEX_URL |

**Net:** the *only* genuinely blocked dependency is **FFmpeg (+x264)**. Image
libs (jpeg/png/webp) come free from **dnf** — no conda needed for those.

---

## Options for resume (in preference order)

**Option A — conda, once riscv64 ffmpeg + conda-tool exist (user's chosen path).**
Wait for (1) a riscv64 conda/micromamba bootstrap and (2) `ffmpeg` (gpl, =6) +
transitive `x264`/`x265` on a conda channel for `linux-riscv64`. Then in
`CIBW_BEFORE_ALL`: bootstrap micromamba, `micromamba create -p /opt/ffenv
ffmpeg=6.* x264` (gpl variant), export
`PKG_CONFIG_PATH=/opt/ffenv/lib/pkgconfig` and
`LD_LIBRARY_PATH`/`CMAKE_PREFIX_PATH` so Mode B pkg-config finds it and tests can
load it. Image libs still from dnf. This is the least custom code.

**Option B — build FFmpeg + x264 from source in `CIBW_BEFORE_ALL` (works today).**
No conda dependency at all. Pattern already used in this repo (build-cffi builds
libffi; build-numpy builds ccache; build-pillow builds libavif via cmake flags):
  1. `dnf install -y libjpeg-turbo-devel libpng-devel libwebp-devel` (enable crb).
  2. Build **x264** from source (`./configure --enable-shared --enable-pic
     --disable-cli`), then **FFmpeg 6.1.1** from the `n6.1.1` GitHub tag with
     `--enable-shared --enable-gpl --enable-libx264 --enable-pic
     --disable-x86asm` + the encoders/decoders/muxers/demuxers the smoke test
     needs (do NOT copy build_ffmpeg.sh's `--disable-everything` skeleton — that
     can't encode). Install to a prefix on `PKG_CONFIG_PATH`.
  3. Build torchcodec (Mode B) against it;
     `I_CONFIRM_THIS_IS_NOT_A_LICENSE_VIOLATION=1`.
  4. auditwheel excludes libtorch* AND libav*/libsw* (FFmpeg not shipped); jpeg/
     png/webp DO vendor in.
  5. Tests: the same FFmpeg prefix is present at runtime (functional+libx264), so
     `pytest test/smoke_test.py` can encode/decode. Set
     `FAIL_WITHOUT_IMAGE_CODECS=1` but `FAIL_WITHOUT_HEIC=0 FAIL_WITHOUT_AVIF=0`
     (those two are intentionally absent) — or run a curated subset.
  Risk: FFmpeg-from-source under QEMU is slow (minutes) and adds config surface,
  but it's fully self-contained and unblocks immediately.

**Option C — split build vs test FFmpeg.** Link the build against the tiny LGPL
skeleton (`packaging/build_ffmpeg.sh`, fast) but install a functional+GPL FFmpeg
for the test runtime. More moving parts; only worth it if the skeleton link is
much faster. Not recommended over B.

If unblocking quickly matters, **Option B is the pragmatic choice** and needs no
external dependency. Option A is cleaner *if/when* the riscv64 conda ecosystem
catches up.

---

## Workflow skeleton to write (build-torchcodec.yml)

Start from **`build-torchaudio.yml`** (branch `torchaudio` / PR #285 — the torch
companion with `--no-build-isolation` + auditwheel excludes) and adapt:

- SPDX header; `name: Build torchcodec wheels (riscv64)`; based-on comment →
  torchcodec's `.github/workflows/linux_wheel.yaml`.
- Triggers/env: `workflow_dispatch` input `version` default `0.16.0`;
  `pull_request: paths: ['.github/workflows/build-torchcodec.yml']`;
  `concurrency` group; standard `UV_*` + `MANYLINUX_RISCV64_IMAGE` env.
  `TORCHCODEC_VERSION: ${{ inputs.version || '0.16.0' }}`.
- `build_wheels` job on `ubuntu-24.04-riscv`, matrix
  `python-version: [312, 313, 314, 314t]`.
- Checkout `meta-pytorch/torchcodec` at `v${TORCHCODEC_VERSION}`
  (`persist-credentials: false`).
- `pypa/cibuildwheel` with:
  - `CIBW_BUILD: "cp${{ matrix.python-version }}-manylinux_riscv64"`,
    `CIBW_MANYLINUX_RISCV64_IMAGE`.
  - **`CIBW_BEFORE_ALL_LINUX`**: enable crb + `dnf install -y libjpeg-turbo-devel
    libpng-devel libwebp-devel`; then **provide FFmpeg 6.x + libx264** (Option A
    conda bootstrap *or* Option B source build). Export `PKG_CONFIG_PATH` so
    Mode B finds FFmpeg.
  - `CIBW_BUILD_FRONTEND: "pip; args: --no-build-isolation"`.
  - `CIBW_BEFORE_BUILD: pip install --only-binary=:all: torch==2.13.0+cpu
    scikit-build-core>=0.10 pybind11 ninja`.
  - `CIBW_ENVIRONMENT`: `BUILD_VERSION=0.16.0 ENABLE_CUDA=0
    I_CONFIRM_THIS_IS_NOT_A_LICENSE_VIOLATION=1
    TORCHCODEC_DISABLE_COMPILE_WARNING_AS_ERROR=1
    TORCHCODEC_BUILD_IMAGE=ON TORCHCODEC_BUILD_JPEG=1 TORCHCODEC_BUILD_PNG=1
    TORCHCODEC_BUILD_WEBP=1 TORCHCODEC_BUILD_AVIF=0 TORCHCODEC_BUILD_HEIC=0
    TORCHCODEC_BUILD_NVJPEG=0
    PKG_CONFIG_PATH=<ffmpeg prefix>/lib/pkgconfig
    PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/` +
    `CIBW_ENVIRONMENT_PASS_LINUX: PIP_EXTRA_INDEX_URL` (and pass through any
    LD_LIBRARY_PATH/PKG_CONFIG_PATH set in BEFORE_ALL).
  - `CIBW_REPAIR_WHEEL_COMMAND`: `auditwheel repair -w {dest_dir} {wheel}` with
    `--exclude` for the libtorch family (libtorch, libtorch_cpu,
    libtorch_python, libtorch_global_deps, libc10, libgomp.so.1, plus
    libgfortran/libopenblas as in torchaudio) **and** the FFmpeg family
    (libavcodec.so.60, libavformat.so.60, libavutil.so.58, libavdevice.so.60,
    libavfilter.so.9, libswscale.so.7, libswresample.so.4 — the FFmpeg-6
    sonames; verify against the built FFmpeg). Let libjpeg/libpng/libwebp vendor
    in (do NOT exclude them).
  - `CIBW_TEST_REQUIRES: torch==2.13.0+cpu numpy pytest pillow`;
    `CIBW_TEST_COMMAND`: `FAIL_WITHOUT_IMAGE_CODECS=1 FAIL_WITHOUT_AVIF=0
    FAIL_WITHOUT_HEIC=0 pytest {project}/test/smoke_test.py` (or a curated
    subset). Runtime FFmpeg must be reachable via LD_LIBRARY_PATH — ensure the
    BEFORE_ALL prefix persists into the test env (it's the same container).
- `publish` job: shared `riseproject-dev/python-wheels/actions/publish-wheels@main`,
  `artifact-pattern: torchcodec-${{ env.TORCHCODEC_VERSION }}-*-manylinux_riscv64`,
  gitlab-* vars/secrets. Dry-runs on PR branches.
- Upload artifact name: `torchcodec-${TORCHCODEC_VERSION}-cp${{ matrix.python-version }}-manylinux_riscv64`,
  path `./wheelhouse/*.whl`.

## Local validation plan (gotcha 9) — before any push
- `python -c "import yaml; yaml.safe_load(open('.github/workflows/build-torchcodec.yml'))"`.
- `actionlint` (expect only the `ubuntu-24.04-riscv` unknown-label warning).
- Dry-run the FFmpeg/x264 build + a single-python `cibuildwheel` under QEMU
  docker before burning a CI cycle (image already runs locally).

## Key source URLs (v0.16.0)
- `pyproject.toml`, `version.txt`, `packaging/torchcodec_version.py`
- `src/torchcodec/_core/CMakeLists.txt` (license guard + Mode A/B),
  root `CMakeLists.txt` (Torch prefix autodetect)
- `src/torchcodec/share/cmake/TorchCodec/ffmpeg_versions.cmake`
  (`add_ffmpeg_target_with_pkg_config`, soname→major map)
- `src/torchcodec/_core/fetch_and_expose_non_gpl_ffmpeg_libs.cmake`,
  `fetch_avif_from_s3.cmake` (S3, no riscv64)
- `packaging/build_ffmpeg.sh` (LGPL skeleton — insufficient for tests),
  `packaging/install_build_dependencies.sh`, `packaging/repair_wheel.py`
- `test/smoke_test.py`, `test/conftest.py` (skip logic), `test/utils.py`
- `src/torchcodec/_core/Encoder.cpp` (default mp4 codec = H.264)

## References
- Playbook + gotchas: `CLAUDE.md`.
- Precedent memory: `memory/torchcodec-port.md` (this port),
  `memory/torchaudio-port.md` (twin), `memory/wsl-git-network-auth-broken.md`,
  `memory/gha-concurrency-cancels-on-rapid-push.md`.
- Precedent workflows: `build-torchaudio.yml` (origin/torchaudio, PR #285),
  `build-onnx.yml` (from-checkout + CMake env), `build-cffi.yml` / `build-numpy.yml`
  (build native deps in-container), `build-pillow.yml` (libavif via cmake flags).
- Sibling paused port: `SESSION-torchvision.md` on branch `origin/torchvision`.
