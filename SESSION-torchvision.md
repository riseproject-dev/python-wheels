# Session summary — porting `torchvision` 0.28.0 to riscv64 wheels

Status as of 2026-08-20. **Paused** pending an external dependency step (see
"Blocker / next action"). This file is a working scratchpad for resuming; it is
not meant to be committed.

## Goal

Add `.github/workflows/build-torchvision.yml` producing riscv64 wheels for
torchvision 0.28.0, published to `pypi.riseproject.dev`, following the porting
playbook in `CLAUDE.md`. Full loop: branch + worktree → workflow → validate
locally under QEMU → push → PR → watch CI → iterate to green + clean publish
dry-run → fold learnings back into `CLAUDE.md`.

## Coordinates

- PyPI distribution: `torchvision`
- Version/tag: `0.28.0` (git tag `v0.28.0`, commit `8fb87713`)
- Source repo: https://github.com/pytorch/vision
- Pairs with: **torch 2.13** (exactly what's on our registry — cleaner than
  torchaudio, which was forward-compat).

## Environment

- Worktree: `.claude/worktrees/torchvision`, branch **`torchvision`**, based on
  `origin/main` @ `e83b9b0` (playbook-compliant: branch `<pkg>` from
  `origin/main`).
- Docker 29.1.3 available; QEMU `qemu-riscv64` binfmt registered; the
  `quay.io/pypa/manylinux_2_39_riscv64:latest` image is already cached locally
  (2.15 GB). So **local validation under QEMU is possible.**
- Push caveats (from memory): needs `workflow` scope on the gh token to push
  `.github/workflows/*`; use gh-HTTPS push in this WSL setup, not SSH.

## What was established (research done)

torchvision is the near-twin of the **torchaudio** port (see
`memory/torchaudio-port.md`) — same build shape: a torch companion built from an
upstream **git checkout** (no PyPI sdist) via `cibuildwheel` directly, the
`build-onnx.yml` / `build-torchaudio.yml` shape. Reuse that workflow almost
verbatim. Key facts confirmed from upstream at `v0.28.0`:

- **Tag maps 1:1 to version.** `version.txt` = `0.28.0`; `setup.py`'s
  `get_version()` uses `BUILD_VERSION` if set, else appends `+<sha7>`. So set
  `BUILD_VERSION=0.28.0` — no tag→version translation needed (unlike protobuf).
- **`setup.py` does `import torch` at module top** and imports
  `torch.utils.cpp_extension`. `pyproject.toml` `[build-system]` requires
  `["setuptools", "torch", "wheel"]`, **no `[tool.cibuildwheel]` section**. So:
  preinstall torch + `--no-build-isolation` (same as torchaudio).
- **Runtime torch-version compat:** `torchvision/extension.py` only checks CUDA
  *major* version (no-op on a CPU build) — it does **not** raise/​warn on
  differing torch versions. So a CPU build against torch 2.13 is fine.
- **Wheels are per-CPython** (link `libtorch_python`), not abi3. Matrix:
  `cp312 / cp313 / cp314 / cp314t`, matching torch's registry matrix.
- **auditwheel must EXCLUDE the libtorch/libc10/libgomp family** (torch provides
  them at runtime) — identical exclude list to torchaudio, or the wheel vendors
  ~130 MB of libtorch.
- **NVJPEG** only activates when `CUDA_HOME` is set → no-op on our CPU build.
  `FORCE_CUDA`/`FORCE_MPS` default off. Good.

### THE key difference from torchaudio — native image libraries

torchvision's `setup.py` enables three image backends **by default (all "1")**:
`TORCHVISION_USE_PNG`, `TORCHVISION_USE_JPEG`, `TORCHVISION_USE_WEBP`
(`TORCHVISION_USE_NVJPEG` too, but that's CUDA-gated → off for us). It locates
them at build time via:

- PNG: `find_libpng()` → needs **`libpng-config`** on PATH (min 1.6.0),
- JPEG: `find_library(header="jpeglib.h")` → links `jpeg`,
- WEBP: `find_library(header="webp/decode.h")` → links `webp`.

Unlike libtorch, these image libs **should be vendored into the wheel** by
auditwheel (they're genuine third-party deps, not provided by torch at runtime).

**How upstream sources them** (from `packaging/pre_build_script.sh`, Linux
branch, lines 28–39) — the answer to "where does upstream take them from":

```
# aarch64 only:
conda install libpng -y
conda install -y libjpeg-turbo -c pytorch-nightly
# all Linux:
conda install libwebp>=1.3.2 -y
conda install libjpeg-turbo -c pytorch
yum install -y freetype gnutls        # <-- only freetype/gnutls from yum
pip install "auditwheel<6.3.0"
```

i.e. **conda** (conda-forge + PyTorch's own `pytorch` channel) is upstream's
source of truth for libpng / libjpeg-turbo / libwebp; only freetype+gnutls come
from yum. libpng on x86_64 is baked into PyTorch's custom manylinux builder
image (not installed in this script).

**Why that doesn't transfer to us:** conda-forge and the `pytorch` conda channel
have **no riscv64 builds**. And our `manylinux_2_39_riscv64` image (Rocky Linux
10.2) ships only the libpng **runtime** `.so.16` — verified by inspecting the
container:

```
libpng-config : NOT present
png.h         : MISSING
jpeglib.h     : MISSING
webp/decode.h : MISSING
/usr/lib64/libpng16.so.16(.40.0)  # runtime only, no -devel, no headers
pkg manager: dnf (Rocky Linux 10.2 "Red Quartz")
```

So we must supply the three `-devel` libs another way on riscv64.

## Decision point (options for getting png/jpeg/webp on riscv64)

1. **`dnf install` from Rocky 10 riscv64 repos** in `CIBW_BEFORE_ALL` — one line
   if `libpng-devel` + `libjpeg-turbo-devel` + `libwebp-devel` exist for
   riscv64. This is the check that was about to run when we paused:
   ```
   dnf -q list --available libpng-devel libjpeg-turbo-devel libwebp-devel
   ```
   (runs under QEMU, slow — ~minutes).
2. **Build the three from source in `CIBW_BEFORE_ALL`** — the pattern this repo
   already uses (`build-cffi.yml` builds libffi; `build-pillow.yml` builds
   libavif via cmake flags). More code, but pins exact versions and is immune to
   distro-repo drift. auditwheel then vendors them into the wheel.

Recommended: try (1); fall back to (2). Either way, verify with the local
`pip wheel` / cibuildwheel-under-QEMU smoke before burning a CI cycle.

## Blocker / next action

**User is adding libpng/libjpeg-turbo/libwebp to conda for riscv64** and will
return when that's done. On resume:

- If those conda packages become installable for riscv64, the workflow can
  mirror upstream's `pre_build_script.sh` conda approach more closely.
- Otherwise, proceed with option (1) or (2) above.

## Testing plan (not yet wired)

Upstream's `test/smoke_test.py` is **too heavy for CI**: it downloads ResNet50
weights, classifies a dog image ("German shepherd"), and needs the
`torchvision-extra-decoders` package for AVIF/HEIC. **Don't run it as-is.**
Instead wire a lean smoke test (à la torchaudio's) that:

- `import torch, torchvision`; print versions;
- asserts `torch.ops.image.decode_png is not None` and
  `torch.ops.torchvision.roi_align is not None` (proves the `_C` + image
  extensions loaded);
- decodes a tiny in-repo PNG/JPEG/WebP via `torchvision.io.decode_image` to
  exercise the linked image libs;
- runs `torchvision.ops.nms` on a couple of boxes (pure C++ op, no weights).

Pull test deps (torch, numpy, pillow) from our registry via
`CIBW_TEST_REQUIRES` + `PIP_EXTRA_INDEX_URL` (they lack public riscv64 wheels).

## Workflow skeleton to write (build-torchvision.yml)

Start from `build-torchaudio.yml` (on branch `torchaudio` / PR #285) and change:

- names/version → `torchvision` / `0.28.0`; repo `pytorch/vision`, ref
  `v0.28.0`.
- `TORCH_VERSION: 2.13.0+cpu` (unchanged).
- `CIBW_BUILD_FRONTEND: "pip; args: --no-build-isolation"` (unchanged).
- `CIBW_BEFORE_ALL`: install/build libpng + libjpeg-turbo + libwebp (the new
  bit — see decision point).
- `CIBW_BEFORE_BUILD`: `pip install --only-binary=:all: torch==2.13.0+cpu
  setuptools wheel ninja` (unchanged).
- `CIBW_ENVIRONMENT`: `USE_CUDA=0 FORCE_CUDA=0 BUILD_VERSION=0.28.0
  PIP_EXTRA_INDEX_URL=...` (+ keep image backends default-on; optionally set
  `TORCHVISION_USE_PNG/JPEG/WEBP=1` explicitly for clarity).
- `CIBW_REPAIR_WHEEL_COMMAND`: same libtorch/libc10/libgomp `--exclude` list as
  torchaudio; **do NOT** exclude png/jpeg/webp — let those vendor in.
- `CIBW_TEST_REQUIRES` / `CIBW_TEST_COMMAND`: the lean smoke test above.
- `publish` job: shared `publish-wheels@main`,
  `artifact-pattern: torchvision-0.28.0-*-manylinux_riscv64`.

## References

- Precedent memory: `memory/torchaudio-port.md` (the twin port).
- Precedent workflows: `build-torchaudio.yml` (torch companion),
  `build-onnx.yml` (build-from-checkout shape), `build-pillow.yml` /
  `build-cffi.yml` (building native deps in-container).
- Playbook + gotchas: `CLAUDE.md`.
- WSL push/auth caveats: `memory/wsl-git-network-auth-broken.md`.
- CI-watching caveat: `memory/gha-concurrency-cancels-on-rapid-push.md`.
