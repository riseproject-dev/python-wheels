# Gotchas — The manylinux image & toolchain

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/manylinux-image-and-toolchain.md`.

## In this file

- **26** — The riscv64 runners ship GCC 13; some packages need GCC 14 or later.
- **46** — The riscv64 manylinux image ships only the minimal `perl-interpreter`, which
- **51** — An upstream `before-build` can name a package that only exists in EPEL — and
- **71** — A vendored 3rd-party library can gate its riscv64 SIMD path on the *parent*
- **100** — A Rust project that generates code with prost/tonic needs `protoc` in the
- **106** — A `yum_install <pkg>` that "fails" may have installed exactly what you needed —
- **124** — A wheel whose compiled payload is a Go binary builds fine and then dies at
- **138** — Two more manylinux-image facts, in the vein of gotchas 46 and 51.
- **139** — RISC-V SIMD in an upstream that already supports riscv64: two traps, both invisible
- **207** — A vendored dependency three submodules deep can declare a `cmake_minimum_required`
- **226** — GCC 14 turns `-Wincompatible-pointer-types` (and `-Wimplicit-function-declaration`,
- **235** — The manylinux image's bundled `/opt/python/cpXY-cpXY` interpreters have
- **377** — Rocky's `lib64` `GNUInstallDirs` default can make a hardcoded `"lib"`
- **378** — A newer libstdc++ on the manylinux image can turn a project's own
- **257** — `CMAKE_POLICY_VERSION_MINIMUM` also works as an environment variable, not just a
- **243** — The `manylinux_2_39_riscv64` container's IPv6 loopback binds but can't send:
- **252** — Rocky 10 (the riscv64 manylinux image's base) names the Wayland client
- **250** — A vendored C library's strict-aliasing UB can miscompile *silently* under a
- **267** — A vendored C++ library's own architecture-dispatch macro (not a SIMD gate,
- **271** — `AVIF_CODEC_AOM_DECODE=OFF` and `-DCONFIG_AV1_HIGHBITDEPTH=0` are a normal
- **272** — A riscv64 project's own `getauxval(AT_HWCAP)` runtime dispatch can still
- **289** — A CMake `ExternalProject_Add` patch step can shell out to `wget`, which the
  manylinux image doesn't ship (only `curl`) — and a parallel `make -j` build hides it.
- **294** — An upstream CMakeLists' own `-fPIC` allowlist can name only `x86_64`/`aarch64`,
  leaving riscv64 to link non-PIC objects into a shared library.
- **279** — Gotcha 272's zlib-ng `vsetvli` SIGILL recurs whenever a *second*, independent
- **288** — Rocky/AlmaLinux 10 dropped the classic SDL2-devel package entirely, on every
- **327** — A project's own `before-all`/`before-build` can already "fix" gotcha 138's
  stale `config.guess`/`config.sub` by downloading fresh copies at build time.
- **328** — A vendored SIMD library with no portable/generic implementation at all can
  still be ported to riscv64 by routing its x86-only path through SIMDe.
- **332** — A SIMDe SSE-emulation port can compile clean, pass its own project's
  per-primitive unit tests, and still produce wrong full-pipeline results on riscv64.
- **333** — A vendored C++ library's architecture-fallback stub (unlike gotcha 267's
  dead `#warning` branch) can have a genuinely correct no-op body that still trips
  `-Werror=unused-parameter` on any architecture outside its named x86/ARM/PPC set.
- **337** — lexbor, re2 and uchardet are absent from Rocky 10's baseos/appstream/crb on
  every arch, and `re2-devel` only resolves from EPEL — which riscv64 does not carry.
- **351** — A project's own build script can gate a *sibling* vendored library's SIMD
  macros on `platform.machine() != "ppc64le"`, silently assuming "not ppc64le" means
  "x86 or ARM" — the hdf5plugin/c-blosc2 case.
- **358** — `dnf`/`apk` installing an older cmake to satisfy gotcha 257 doesn't
  necessarily make it the one that runs: both manylinux and musllinux riscv64 images
  carry a pipx-installed cmake >= 4 earlier on `PATH` by default.
- **359** — A CMake project forked from old LLVM sources can validate the host
  architecture through *two* independent mechanisms — the vendored `utils/llvm-build`
  Python tool has its own separate check and its own escape hatch.
- **374** — `find_package(Python3 REQUIRED COMPONENTS Interpreter Development)` fails on
  manylinux's static-libpython CPython, on any architecture — only `Development.Module`
  is ever needed to build an extension module, not the `Development.Embed` half.

---

26. **The riscv64 runners ship GCC 13; some packages need GCC 14 or later.** The compiler
    that matters is the one in the *build container*, not on the runner — a cibuildwheel
    build against the manylinux_riscv64 image gets a newer toolchain for free. A project
    that builds directly on the runner does not: if it needs GCC 14+, either move the build
    into the container or provision a newer toolchain explicitly.

46. **The riscv64 manylinux image ships only the minimal `perl-interpreter`, which
    breaks any dependency that builds OpenSSL from source (the confluent-kafka case).**
    Upstreams whose from-source path compiles its own OpenSSL (librdkafka's mklove
    `--install-deps --source-deps-only`, and anything else vendoring openssl) install a
    couple of perl modules in their manylinux script — confluent-kafka's
    `tools/build-manylinux.sh` does `yum install perl-IPC-Cmd perl-Pod-Html` — because
    the AlmaLinux 8 images carry the rest. Rocky 10 does not: `Time::Piece` and
    **`FindBin`** are missing too, and `Configure` dies with
    `Can't locate FindBin.pm in @INC` before printing anything useful. Install the whole
    distribution (`dnf -y install perl`) rather than chasing modules one CI cycle at a
    time.
    - **Two more Rocky 10 package facts worth not rediscovering:** `zlib-devel` still
      resolves (the preinstalled `zlib-ng-compat-devel` provides it), and `python3`,
      `make`, `patch`, `file`, `nm`, `ar`, `autoconf`, `automake`, `libtool` and
      `pkg-config` are all present — so an upstream `yum install -y zlib-devel gcc-c++`
      line can usually be left untouched.
    - **A source-built dependency is unstripped where upstream's prebuilt one is not.**
      librdkafka came out at 58MB against the 11MB `librdkafka.redist` upstream bundles,
      a 19MB wheel against 4.9MB. `auditwheel repair --strip` puts it back at 9.8MB.
      Check with `unzip -l <whl>` whenever the build compiles a dependency that upstream
      downloads prebuilt.

51. **An upstream `before-build` can name a package that only exists in EPEL — and
    manylinux ships no EPEL on riscv64 (the duckdb/ccache case).**
    `docker/build_scripts/install-runtime-packages.sh` sets `EPEL=` (empty) for `i686`
    and **`riscv64`** while installing `epel-release` everywhere else, so an inherited
    `[tool.cibuildwheel.linux] before-build = ["yum install -y ccache"]` — a very common
    line, since ccache is EPEL-only on RHEL derivatives — fails the build before it
    starts. Rocky 10's own repos answer this in one query
    (`dnf -q list <pkg>` in `rockylinux/rockylinux:10` under `--platform linux/riscv64`,
    a 60MB pull versus the multi-GB manylinux image): `cmake` 3.31.8 is there,
    **`ninja-build` and `ccache` are not**.
    - **Override it with an empty string**, don't reimplement it:
      `CIBW_BEFORE_BUILD: ''`. cibuildwheel's `_resolve_cascade` skips only `None`
      values (`ignore_empty` is False for `before-build`), and the env var sits after
      the `[tool.cibuildwheel.linux]` table in the cascade — so `''` genuinely clears
      it. Dropping a compiler cache costs nothing in a throwaway container.
    - **Don't reach for `dnf` to replace it**: a scikit-build-core project pulls
      `cmake`/`ninja` from its own build requirements, and both publish riscv64 wheels
      on PyPI (`cmake-4.4.2-py3-none-manylinux_2_31_riscv64.whl`,
      `ninja-1.13.0-py3-none-manylinux_2_31_riscv64.whl`), so the isolated build env
      provisions them itself. Check `pypi.org/pypi/<tool>/json` for the arch before
      writing an install step for a build tool.

71. **A vendored 3rd-party library can gate its riscv64 SIMD path on the *parent*
    project's dispatch probe and then re-probe with baseline flags — a guaranteed
    `FATAL_ERROR` (the opencv-python case; see `build-opencv-python.yml`).** OpenCV probes
    RVV twice: once with the baseline flags (`HAVE_CPU_RVV_SUPPORT` — **fails**, the
    baseline is `-march=rv64gc`) and once with `-march=rv64gc_v`
    (`HAVE_CXX_MARCH_RV64GC_V` — **succeeds**, which is all a *dispatch* target needs).
    `CPU_RVV_SUPPORTED` therefore ends up ON, and `3rdparty/libpng/CMakeLists.txt` takes
    it as the default for `PNG_RISCV_RVV` — then compiles `#include <riscv_vector.h>`
    with the *baseline* flags, gets `COMPILER_SUPPORTS_RVV - Failed`, and calls
    `message(FATAL_ERROR "Compiler does not support RISC-V Vector extension")`. Configure
    dies before one object is built. Nothing is wrong with the toolchain — the image's
    GCC 14.3.1 does support RVV; the two probes just disagree because only one passes
    `-march`. Distinct from gotcha 26 (a genuinely too-old compiler).
    - **Turn the vendored dep's SIMD off; do not add `-march` globally.** Raising the
      baseline to `rv64gcv` would make every wheel require RVV hardware. And off is the
      only correct answer anyway: the same block appends
      `riscv/filter_rvv_intrinsics.c` with **no** per-source `-march`, so the path could
      not compile even if the probe had passed. `off` is libpng's own documented default.
    - **A `scikit-build` (classic) project takes extra `-D` flags from the `CMAKE_ARGS`
      environment variable**, so this is a one-line `CIBW_ENVIRONMENT` entry
      (`CMAKE_ARGS=-DPNG_RISCV_RVV=off`), not a patch: `setuptools_wrap.py` prepends them
      to the `cmake_args` passed to `setup()` and `cmaker.py` appends them to the
      configure command line — unless `SKBUILD_CONFIGURE_OPTIONS` is set, which wins and
      makes `CMAKE_ARGS` a silent no-op. `scikit-build-core` reads `SKBUILD_CMAKE_ARGS`
      instead. Check which backend `[build-system] build-backend` names before reaching
      for either.
    - **Grep the vendored tree for the other gates in the same pass** — each one you miss
      is a full CI cycle: `grep -rn --include=CMakeLists.txt --include='*.cmake' -iE
      'riscv|rvv' 3rdparty cmake`, then look for `FATAL_ERROR` in the hits. In OpenCV
      5.0.0 only libpng is fatal; `zlib-ng` (`set(WITH_RVV OFF)`) and `mlas` degrade
      quietly, which is why the failure looks isolated rather than systemic.
    - **A `cmake` *configure* under `--platform linux/riscv64` settles it in ~4 minutes**
      (gotcha 15): copy the exact `-D` list the failing CI log printed — skbuild echoes
      the whole command — add the candidate flag, and read the "Configuring done" line.
      Cheaper than the queue wait on the shared riscv64 runners, and it prints the
      config summary so you can also check what got disabled (`GUI: NONE`, `FFMPEG: NO`).

100. **A Rust project that generates code with prost/tonic needs `protoc` in the
    container, and the riscv64 manylinux image can supply it — from CRB, at 3.19 (the
    temporalio case; see `build-temporalio.yml`).** Upstreams whose cibuildwheel config
    pulls protoc from a wheel (`pip install protoc-wheel-0`, the near-universal choice —
    it is what `[tool.cibuildwheel] before-all` installs) hit a dead end on riscv64:
    protoc-wheel-0 publishes **only wheels, no sdist**, and none for riscv64. Two facts
    settle it without a CI cycle.
    - **Rocky 10's CRB repo is *enabled* in `manylinux_2_39_riscv64`** (unlike EPEL, which
      gotcha 51 shows is absent for this arch), and `protobuf-compiler`/`protobuf-devel`
      live there — so `yum install -y protobuf-compiler protobuf-devel` in
      `CIBW_BEFORE_BUILD` is a one-line override. `dnf repolist --all` in the image is the
      check; do not assume a package is missing because it is not in baseos/appstream.
    - **CRB's protoc is 3.19.6, and protoc < 22 does not carry the well-known types inside
      the binary** — they ship as `.proto` files in `/usr/include`, so a build that worked
      with protoc-wheel-0's 30.x dies on `google/protobuf/field_mask.proto: File not
      found`. prost-build (checked in 0.14.4, `config.rs`) forwards `$PROTOC_INCLUDE` as an
      extra `-I`, so `PROTOC_INCLUDE=/usr/include` in `CIBW_ENVIRONMENT` is the whole fix.
    - **Prove the old protoc can parse the tree before trusting it**, on any host and in
      seconds: run `protoc --descriptor_set_out` over the exact file/include lists the
      crate's `build.rs` passes, inside `rockylinux/rockylinux:10`. `grep -rh '^syntax'
      --include='*.proto'` first — proto2/proto3 are fine for 3.19, an `edition = "2023"`
      file is not. Then compile just the generating crate (`cargo build -p <protos-crate>`)
      in the aarch64 manylinux image for end-to-end proof in under a minute.

106. **A `yum_install <pkg>` that "fails" may have installed exactly what you needed —
    check `Provides:` before adding a gotcha-46-style `dnf install` (the pyproj case).**
    multibuild-derived dependency scripts define
    `yum_install() { yum install -y "$1" && rpm -q "$1"; }`, and the `rpm -q` half fails
    whenever dnf satisfied the request through a virtual provide rather than a literal
    package name. On Rocky 10 riscv64 `dnf -y install perl-core` installs the full `perl`
    distribution and exits 0, yet `rpm -q perl-core` reports "not installed" — so
    `build_perl` returns non-zero even though `FindBin` and `Time::Piece` are now present,
    and it `touch`es its stamp unconditionally regardless. Prefixing `before-all` with
    `dnf -y install perl` therefore fixes nothing and is exactly the redundant divergence
    gotcha 49 warns about; gotcha 46 applies only where upstream installs *no* perl at all.
    - **Settle it by importing the module in the real image, before and after upstream's
      line**, rather than by reading package lists:
      `docker run --rm --platform linux/riscv64 quay.io/pypa/manylinux_2_39_riscv64 bash -c
      "perl -MFindBin -e1; dnf -y install perl-core; perl -MFindBin -e1"` fails, then
      succeeds. A `dnf list` that omits the name proves nothing — `dnf list perl-core` is
      silent on Rocky 10 while `dnf install perl-core` succeeds.
    - **Refines gotcha 101's aarch64 rehearsal**: the aarch64 manylinux image is
      **AlmaLinux 10**, not the same Rocky 10 build as the riscv64 one, and the two do not
      carry identical packages (`perl-core` is a real package on AlmaLinux and only a
      provide on Rocky). The rehearsal still validates the recipe end to end; it does not
      settle package availability, so probe the riscv64 image itself for that.
    - Two invocation traps worth not rediscovering when setting the rehearsal up:
      cibuildwheel refuses `--platform`/`--archs` alongside `--only` (the arch is computed
      from it), and `uv run` inside the upstream checkout tries to install that checkout as
      a project first, dying in its `setup.py` — pass `--no-project`.

124. **A wheel whose compiled payload is a Go binary builds fine and then dies at
    `execve` with ENOENT, because Go <=1.26 hardcodes the wrong riscv64 ELF interpreter
    (the wandb case; see `build-wandb.yml`).** Gotchas 27/35 read an all-`py3-none-*` wheel
    set as "nothing is compiled"; the third shape is a wheel with **no** ABI tag whose
    platform half is real *and* whose payload the build compiles from source — wandb's
    hatchling hook builds `wandb/bin/wandb-core` (Go, `-mod=vendor`) plus two Rust artifacts,
    so `py3-none-<platform>` here means "one wheel for every interpreter", not "pure Python".
    That is an ordinary port, and because the wheel is ABI-independent the matrix collapses
    to a single build identifier (gotcha 11's collapse, reached from a different direction).
    - **`FileNotFoundError: [Errno 2]` naming a file that is demonstrably present in the
      wheel is the kernel reporting a missing *interpreter*, not a missing binary.** Go's
      internal linker emits a dynamic executable even at `CGO_ENABLED=0` when any package
      uses `//go:cgo_import_dynamic` (wandb vendors `github.com/ebitengine/purego`, whose
      `dlfcn_nocgo_linux.go` does exactly that for `dlopen`/`dlsym`) — and Go pins
      `/lib/ld.so.1` as the riscv64 loader, a name no glibc distribution ships. Debian
      trixie, Ubuntu 24.04 and `manylinux_2_39_riscv64` all carry only
      `/lib/ld-linux-riscv64-lp64d.so.1`. That is golang/go#77209, fixed by CL 737180 after
      go1.26.5; until the version in `core/go.mod` (or wherever the project pins Go) carries
      the fix, pass the psABI path with the linker's `-I` flag
      (`-ldflags="... -I /lib/ld-linux-riscv64-lp64d.so.1"`). It is a no-op wherever Go links
      statically, so it needs no arch guard beyond the one you write for clarity. Tag it
      `Inappropriate` — the fix belongs in Go, not in the package.
    - **Diagnose it in one command, on any host**: `readelf -lW <binary> | grep interpreter`.
      A trivial `CGO_ENABLED=0` Go program has *no* `PT_INTERP`, so an interpreter line at
      all tells you some dependency forced dynamic linking; `grep -rl cgo_import_dynamic
      vendor/` then names it.
    - **Put `PT_INTERP` in the wheel-content assertion**, next to gotcha 20's "the compiled
      thing is really in there". Parsing it is ~10 lines of `zipfile` + struct offsets
      (`e_phoff` at 0x20, `e_phentsize` at 0x36, `e_phnum` at 0x38; `PT_INTERP == 3`), and it
      turns a two-hour build-then-fail cycle into a host step. Assert `interp in (None,
      "/lib/ld-linux-riscv64-lp64d.so.1")` so a static binary passes too.
    - **Cross-compile the payload on your fast host before spending the native cycle.** Go
      cross-compiles with no toolchain install (`GOOS=linux GOARCH=riscv64 go build`), and
      Rust workspaces cross-build in a container with `rustup target add
      riscv64gc-unknown-linux-gnu` plus `gcc-riscv64-linux-gnu` as the linker — 70s each here
      against **1h45m** for the same code natively on `ubuntu-24.04-riscv`. That pre-flight
      is also where you settle the one dependency that usually decides a Rust port:
      `aws-lc-sys` (rustls' default provider) ships prebuilt bindings for riscv64gc, visible
      as `src/riscv64gc_unknown_linux_gnu_crypto.rs` in the crate tarball.
    - **A hatchling `[tool.cibuildwheel.linux] environment` table is load-bearing** — wandb's
      carries the `PATH` entries for Go and cargo, and upstream's own workflow comments that
      `CIBW_ENVIRONMENT_LINUX` would replace it. Pass the registry index with
      `CIBW_ENVIRONMENT_PASS_LINUX` plus a job-level `env:` instead of clobbering the table.

138. **Two more manylinux-image facts, in the vein of gotchas 46 and 51.**
    - **The image carries only glibc's *built-in* charset converters.** RHEL 9+ split the
      rest into `glibc-gconv-extra`, so anything recoding through `iconv` fails for every
      non-trivial encoding: GDAL's shapefile driver made 11 `test_non_utf8_encoding_*`
      tests fail with a bare "Error adding field" until `dnf -y install glibc-gconv-extra`
      went into the image. The tell is that only the non-UTF-8/non-Latin-1 cases fail.
    - **An old autotools tarball ships a `config.guess`/`config.sub` that predates the
      architecture.** libspatialite 5.1.0's are stamped 2009 and recognise neither riscv64
      *nor* aarch64, so `configure` dies with `cannot guess build type; you must specify
      one` — on both, which is what makes it cheap to catch off-target. `--build=$(gcc
      -dumpmachine)` does not help, because the same stale `config.sub` rejects the triplet;
      copy automake's over instead (`cp /usr/share/automake-*/config.guess
      /usr/share/automake-*/config.sub .`), which the manylinux image already has.

139. **RISC-V SIMD in an upstream that already supports riscv64: two traps, both invisible
    until the wheel runs (the faiss-cpu case).** Finding `-march=rv64gcv...` and
    `impl-riscv.cpp` in a project reads as "the port is already done". It is not, and the
    two things that go wrong are independent of each other and of the package.
    - **The image's binutils is older than the ISA extension name the flags use.**
      `manylinux_2_39_riscv64` is Rocky Linux 10, which ships **binutils 2.41**; `zvfhmin`
      landed in 2.42. An old assembler rejects the **whole** `-march` string rather than
      the one unknown extension, so every affected translation unit dies with
      ``unknown prefixed ISA extension `zvfhmin'`` — and the message names an ISA string
      you never wrote, so it reads like a compiler bug. GCC itself is fine (Rocky 10 has
      14.3.1); it is `as` that refuses. Settle it in 30 seconds, no build:
      `docker run --rm --platform linux/riscv64 rockylinux/rockylinux:10 sh -c 'dnf -y install gcc-c++ >/dev/null; echo "int main(){}" >t.cc; g++ -march=<flags> -c t.cc'`,
      then bisect the flag by dropping extensions. The fix is a `check_cxx_source_compiles`
      probe with a fallback to the extension-free `-march`, not a hardcoded downgrade —
      grep the sources for `f16`/`float16` first, since a probe that silently disables
      something the code needs just moves the failure.
    - **"Compiled with RVV" often means "assumes RVV", with no runtime check.** Projects
      copy the aarch64 pattern where NEON is architecturally guaranteed, and write
      `detected_level = RISCV_RVV` unconditionally while compiling *only* the vector
      kernels with `-march=rv64gcv` and everything else at the rv64gc baseline. The build
      is green, the tests pass on a runner that happens to have V, and the published wheel
      SIGILLs on JH7110/P550-class hardware — exactly what a `manylinux_riscv64` tag
      promises to run on. Read the dispatch site (`getauxval`/`__riscv_hwprobe` present?)
      before trusting a green test job; the repo's standing position is that moving the
      baseline to `rv64gcv` "would make every wheel require RVV hardware".
      The patch is usually a five-line mirror of the project's own SVE path —
      `getauxval(AT_HWCAP) & (1 << ('V' - 'A'))` — which keeps the speedup where the
      hardware has it instead of disabling the kernels. Check the dispatcher falls back to
      a scalar level first; QEMU reports the V bit set, so this cannot be tested by
      emulation alone, only read.

207. **A vendored dependency three submodules deep can declare a `cmake_minimum_required`
    below CMake 4's hard floor even when the top-level project and its direct submodule
    don't — and only a CMake new enough to need the workaround has a riscv64 PyPI wheel
    at all (the ctranslate2/Ruy/cpuinfo/clog case).** CTranslate2's own
    `cmake_minimum_required(VERSION 3.7)` and Ruy's `VERSION 3.13` are both fine; the
    failure is three levels down, in Ruy's vendored `third_party/cpuinfo/deps/clog`,
    which CMake 4 refuses outright (`Compatibility with CMake < 3.5 has been removed`)
    rather than warning. There is no `dnf install`-around-it either: the riscv64
    manylinux image's own repo `cmake` is fine, but a `CIBW_BEFORE_ALL_LINUX` script that
    does `pip install cmake` to get a version newer than whatever the image ships hits
    this on riscv64 specifically, because the *first* riscv64 wheel on PyPI is
    `cmake==4.1.0` — every version old enough to predate this CMake policy change (<4.0)
    has no riscv64 wheel to fall back to, so there is no way to sidestep the collision by
    pinning an older `cmake` the way an x86_64/aarch64 build could.
    - **The fix is `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` on the top-level configure line**;
      it is a no-op for a project already declaring 3.5 or higher and unblocks the
      deeply-vendored one three `add_subdirectory()` calls down.
    - **Confirm exactly which vendored `CMakeLists.txt` needs it by reading the
      "CMake Error at ..." path in the configure log**, not by guessing from the
      top-level project's own declared minimum — it is rarely the direct dependency.

226. **GCC 14 turns `-Wincompatible-pointer-types` (and `-Wimplicit-function-declaration`,
    `-Wimplicit-int`) from a warning into a hard error by default for C code — a
    toolchain-version fact, not a riscv64 one, that bites old-style C sources compiled
    against a newer manylinux image than upstream targets (the uamqp case).** uamqp's
    Cython-generated `c_uamqp.c` calls into the vendored `azure-uamqp-c` C API with
    loosely-typed pointers that were always technically wrong but only warned under the
    GCC upstream's own manylinux2014 image ships. `manylinux_2_39_riscv64` (Rocky 10)
    carries GCC 14.3.1, so the same code hard-fails there — refines gotcha 26 from "too
    old to build at all" to "new enough to enforce what an old one let slide". uamqp's
    own `pyproject.toml` already carries the fix — `[tool.cibuildwheel.linux]
    environment = {..., CFLAGS="-Wno-error=incompatible-pointer-types
    -Wunused-function"}` — for exactly this reason, presumably hit on a newer x86_64 CI
    image at some point.
    - **A `CIBW_ENVIRONMENT` override that adds `PIP_EXTRA_INDEX_URL` (or anything
      else) silently drops that CFLAGS too, since `CIBW_ENVIRONMENT` replaces the whole
      table (gotcha 107)** — read upstream's `environment` entry before overriding and
      carry forward anything build-relevant, not just the keys your port needed to add.
    - Confirm it's this exact class before reaching for the flag: the compiler error
      text names the diagnostic (`error: ... incompatible-pointer-types` in
      `[-Wincompatible-pointer-types]`), and it appears identically on any sufficiently
      new GCC/Clang regardless of architecture — nothing riscv64-specific to chase.

235. **The manylinux image's bundled `/opt/python/cpXY-cpXY` interpreters have
    `sqlite3` loadable extensions disabled — test anything using
    `sqlite3.Connection.enable_load_extension` on the runner's own Python instead (the
    sqlite-vec case).** These are python-build-standalone-style builds, compiled with a
    feature set that differs from a normal distro Python — confirmed with
    `python3 -c "import sqlite3; print(hasattr(sqlite3.connect(':memory:'),
    'enable_load_extension'))"` returning `False` in `/opt/python/cp312-cp312` through
    `cp314-cp314` inside `quay.io/pypa/manylinux_2_39_riscv64`, and `True` for both
    Rocky 10's own system `python3` (inside the same image) and Ubuntu 24.04's apt
    `python3` on the real `ubuntu-24.04-riscv` runner target. A package whose whole
    purpose is `conn.load_extension(...)` therefore cannot be exercised inside the
    build container at all — the AttributeError looks like a build problem but is a
    property of that specific Python build, present on every architecture, not
    riscv64-specific.
    - **Test on the host runner, not the container, when this hits.** Since
      `ubuntu-24.04-riscv` runs glibc 2.39 — the same version the `manylinux_2_39_riscv64`
      tag promises — a wheel built inside the container installs and loads correctly
      when tested directly on the runner afterward (outside `docker run`), which is also
      what a real end user's environment looks like. Building in the container and
      testing on the host is not a compromise here; it is the only combination that
      exercises the feature at all.
    - **Not unique to `sqlite3`** — any stdlib module a python-build-standalone-style
      interpreter compiles out (readline, tkinter, and others depending on the build
      profile) will show the same "works everywhere except `/opt/python`" shape. `python3
      -c "import <mod>"` inside `/opt/python/cpXY-cpXY` is a five-second check before
      assuming a `CIBW_TEST_COMMAND` failure is riscv64-specific.

243. **The `manylinux_2_39_riscv64` container's IPv6 loopback binds but can't send:
    `socket.socket(AF_INET6).bind(("::1", 0))` succeeds, then any actual traffic on
    it raises `OSError: [Errno 101] Network is unreachable`.** zeroconf's
    `has_working_ipv6()` helper only checks the bind (plus that some adapter reports
    an IPv6 address), so it reports IPv6 as working and every IPv6-gated test runs —
    all but one pass; the one that actually round-trips a packet over `('::1', ...)`
    fails, identically on cp312/cp313/cp314/cp314t. A pure bind-and-close probe is
    not proof that IPv6 loopback is usable inside this container — anything that
    also sends will find out otherwise. `--deselect` the one node rather than
    disabling IPv6 testing wholesale (upstream's own `SKIP_IPV6` knob skips far more
    than this single failure); copy the nodeid verbatim from the `FAILED` line
    (gotcha 144) and confirm it repeats identically across the whole interpreter
    matrix before trusting it is not a flake.

250. **A vendored C library's strict-aliasing UB can miscompile *silently* under a
    newer GCC — no error, no warning, just wrong output (the pyreadstat/ReadStat
    case).** ReadStat's `readstat_writer.c` casts `void*` through
    `readstat_variable_t**` and similar type-punning the C standard forbids; GCC 13+
    at `-O2` exploits the type-based-aliasing assumption those casts violate and
    optimizes away the affected value-label writes. Unlike gotcha 226's
    `-Wincompatible-pointer-types` (a hard build-time error), this produces a wheel
    that builds cleanly and passes any test that doesn't specifically check the
    corrupted field — it only shows up as wrong output, on any sufficiently new GCC,
    nothing riscv64-specific about it. pyreadstat's own upstream CI already carries
    the fix — `CFLAGS=-O2 -fno-strict-aliasing` on Linux, with a comment naming the
    exact function and GCC version — so `manylinux_2_39_riscv64`'s GCC 14.3.1
    qualifies and the flag has to be carried into `CIBW_ENVIRONMENT_LINUX` even
    though nothing about the port itself triggers it. The tell, when upstream's own
    comment isn't there to find: a project vendoring older C against a newer image
    than it was written for is reason enough to check whether upstream's own CI sets
    any non-default `CFLAGS`/`CXXFLAGS` before assuming a clean, warning-free build
    means the code is safe on this compiler.

252. **Rocky 10 (the riscv64 manylinux image's base) names the Wayland client
    library's devel package differently from the Fedora/EPEL convention an
    upstream's own CI script assumes (the glfw case).** pyGLFW's `.gitlab-ci.yml`
    installs `libwayland-client-devel` on its manylinux2014/manylinux_2_28 jobs — that
    name resolves on the AlmaLinux-based x86_64/aarch64 manylinux images the same way
    it does on Fedora/EPEL, so the line looks portable. It is not a package on Rocky
    10: `dnf install libwayland-client-devel` reports "No matching Packages to list"
    on `manylinux_2_39_riscv64`, even with CRB enabled. The library and its pkg-config
    file (`wayland-client.pc`) are both present — just under Rocky's own package name,
    **`wayland-devel`** (`dnf -q provides '*/wayland-client.pc'` finds it in seconds
    and is the fastest way to settle a "no matching packages" dead end without
    guessing at synonyms). `libxkbcommon-devel` and `wayland-protocols-devel`, by
    contrast, keep their upstream names unchanged on Rocky 10 — only the client
    library's package is renamed, so swap that one line rather than assuming the
    whole dependency list needs translating.
    - Distinct from gotcha 106 (a `yum_install` that "fails" but actually succeeded
      under a virtual provide): here the literal name genuinely does not exist under
      any provide, and the fix is the *correct* package name, not a Rocky-vs-AlmaLinux
      quirk in how `rpm -q` reports success.

257. **`CMAKE_POLICY_VERSION_MINIMUM` also works as an environment variable, not just a
    `-D` cache flag — the fix when the failing `cmake` invocation is inside a script
    that isn't ours to add flags to (refines gotcha 207; the freetype-py case, see
    `build-freetype-py.yml`).** Gotcha 207's fix (`-DCMAKE_POLICY_VERSION_MINIMUM=3.5`
    on the configure line) assumes the port controls that line — true for a
    `CIBW_BEFORE_ALL_LINUX` we write ourselves, false when a project's own `setup.py`
    shells out to a fixed `cmake ...` command string, as freetype-py's
    `setup-build-freetype.py` does to build the FreeType (`cmake_minimum_required(VERSION
    3.0)`) and HarfBuzz it bundles. There is no argument to inject without patching the
    script. CMake reads `CMAKE_POLICY_VERSION_MINIMUM` from the process environment with
    the same effect as the cache variable, so setting it in `CIBW_ENVIRONMENT` (which
    `subprocess.run(..., shell=True)` inherits by default, with no explicit `env=`
    needed) reaches every `cmake` invocation the script makes, however many, without
    touching its source.
    - **Same value, same reasoning as gotcha 207**: pick the CMake-4 floor (`3.5`) rather
      than matching the project's own declared minimum exactly — it is a no-op for
      anything already at or above 3.5 and unblocks whichever vendored piece is below it,
      including ones three directory levels down that a top-level patch would miss.
    - **Confirm locally before spending a riscv64 CI cycle**: reproduce the bare
      `CMake Error ... Compatibility with CMake < 3.5 has been removed` on any host with a
      CMake ≥4 (`brew`/`apt` current versions qualify), then re-run with
      `CMAKE_POLICY_VERSION_MINIMUM=3.5` exported and confirm configure proceeds — no
      container or cross-compile needed, since the error is a CMake-version fact, not an
      architecture one.

267. **A vendored C++ library's own architecture-dispatch macro (not a SIMD gate, gotcha
    71's case) can have no riscv64 branch at all, and its harmless catch-all `#warning`
    still kills the build under `-Werror` (the awslambdaric case).** aws-lambda-cpp
    vendors `backward-cpp` for enhanced crash stack traces; its signal handler picks the
    faulting instruction pointer out of `ucontext_t` with an `#if defined(__aarch64__)
    ... #elif defined(__arm__) ...` chain that has no riscv64 arm at all, so it falls into
    the `#else` branch: a bare `#warning` plus a now-unused `ucontext_t*` local. Neither
    is a real defect — the fallback just leaves the address unset, so the crash handler
    still fires and unwinds, only without pinpointing the instruction — but the vendoring
    project's own `-Wall -Wextra -Werror` (set unconditionally in its `CMakeLists.txt`,
    not gated by build type) turns both into hard compile errors before the extension
    that actually matters is ever reached.
    - **Fix at the point the port controls, not inside the vendored source.** The
      library's C++ sources ship inside a tarball vendored *inside the package's own git
      tree* (`deps/aws-lambda-cpp-0.2.6.tar.gz`), not as plain files — patching its
      `CMakeLists.txt` or `backward.h` textually means unpacking, patching and re-packing
      a binary blob, which `git apply` cannot do. The package's own build script that
      invokes `cmake` (`scripts/preinstall.sh`, a plain text file in the checkout) is the
      patchable surface: append `-Wno-error=cpp -Wno-error=unused-variable` to the
      `-DCMAKE_CXX_FLAGS` it already passes. Order relative to the target's own
      `-Werror` (added later, via `target_compile_options`) does not matter — GCC treats
      a named `-Wno-error=<diag>` as more specific than the blanket `-Werror` regardless
      of which comes first on the effective command line.
    - **Confirm it's this class before reaching for the flag**: the diagnostic name is
      right there in the error (`[-Werror=cpp]` for the `#warning`, `[-Werror=unused-
      variable]` for the dead local) — same read as gotcha 226, different toolchain
      trigger (an unrecognized target architecture, not a newer GCC's stricter C
      defaults).
    - **Verify locally before burning a riscv64 CI cycle**: `docker run --rm --platform
      linux/riscv64 quay.io/pypa/manylinux_2_39_riscv64 sh -c '<vendored cmake
      invocation>'` reproduces the exact error via QEMU in under a minute once the
      library's own build dependencies are unpacked, and confirms the `-Wno-error=`
      fix turns the same two lines into warnings without touching anything else.

271. **`AVIF_CODEC_AOM_DECODE=OFF` and `-DCONFIG_AV1_HIGHBITDEPTH=0` are a normal libavif
    combination (upstream's own `wheelbuild/config.sh` passes both); on riscv64 it hits a
    real, still-unfixed bug in libaom's CMake, not a config mistake (the
    pillow-avif-plugin case).** libavif vendors libaom via `FetchContent` at a pinned tag
    (`v3.14.1` for libavif 1.4.2), and a `-D` flag on the *outer* libavif cmake invocation
    becomes a normal cache variable that libaom's own `set_aom_config_var`/
    `set_aom_option_var` macros (`cmake/util.cmake`) explicitly refuse to override —
    that's how `CONFIG_AV1_HIGHBITDEPTH=0` from the command line actually reaches aom.
    But `av1/av1.cmake`'s `AOM_AV1_COMMON_INTRIN_RVV` list unconditionally includes
    `highbd_convolve_rvv.c`, `highbd_compound_convolve_rvv.c` and
    `highbd_wiener_convolve_rvv.c` — unlike the equivalent x86 lists a few lines down,
    which wrap their highbd-only files in `if(CONFIG_AV1_HIGHBITDEPTH)`. With
    highbitdepth off, `av1_rtcd_defs.pl` never declares `av1_highbd_convolve_{x,y,2d}_sr`
    or their `_c` fallbacks, so the RVV file's calls to `av1_highbd_convolve_y_sr_c` etc.
    become undeclared-function errors (`-Wimplicit-function-declaration` promoted to
    `-Werror` by aom's own flags). Confirmed against both the pinned `v3.14.1` tag and
    current aom `main` (still present as of 2026-09) — this is not a stale-version issue
    a bump would fix.
    - **Fix: add `-DENABLE_RVV=0` to the same outer cmake invocation.** `ENABLE_RVV`
      (`cmake/aom_config_defaults.cmake`) is a plain `option()`-backed cache var subject
      to the same command-line-wins rule, and `cmake/cpu.cmake` gates *all* of aom's RVV
      object-library creation on it (`if(ENABLE_RVV) ... else() ... --disable-rvv`) — so
      it removes the broken translation unit instead of papering over one symbol, and
      the RTCD generator stops emitting `_rvv` dispatch entries entirely. aom is encoder-
      only here (`AVIF_CODEC_AOM_DECODE=OFF`), so the cost is slower (portable-C) AV1
      encode, not a functional loss; same trade as gotcha 71's `PNG_RISCV_RVV=off`.
    - **Verify before spending a CI cycle**: this is a from-source C dependency build
      (gotcha 15's territory), so a `docker run --rm --platform linux/riscv64
      quay.io/pypa/manylinux_2_39_riscv64` QEMU rehearsal of the *exact* `cmake -S ... -B
      ...` / `cmake --build ...` pair — pip-installing `ninja` first, since the image has
      none — reproduces the failure verbatim and then confirms the fix actually links
      `libavif.so`, not just that configure succeeds.

272. **A riscv64 project's own `getauxval(AT_HWCAP)` runtime dispatch can still SIGILL,
    because the "is this instruction safe" probe is itself one of the instructions being
    probed for (the zlib-ng case; see `build-zlib-ng.yml`).** Unlike gotcha 139's
    "compiled with RVV, no runtime check at all" failure, zlib-ng's
    `riscv_check_features()` does gate its RVV-accelerated deflate/inflate paths on
    `getauxval(AT_HWCAP) & ISA_V_HWCAP` first — a textbook-correct guard. But once that
    passes, it *also* runs an inline `vsetvli`/`csrr` asm probe to double-check vector
    length and tail/mask-agnostic mode before trusting the kernel's HWCAP report. On this
    repo's `ubuntu-24.04-riscv` runner hardware, HWCAP reports V present, and the very
    first `vsetvli` that probe executes raises `Fatal Python error: Illegal instruction`
    — crashing every process that imports the extension, before a single deflate/inflate
    call. (Confirmed at `zng_deflateInit2`, reached at Python import time via
    `zlib.compressobj()` in the test module.)
    - **QEMU cannot reproduce or falsify this** — same caveat as gotcha 139's closing
      line. TCG implements `vsetvli` correctly, so a `docker run --platform linux/riscv64`
      rehearsal of the *unpatched* wheel passes its entire test suite locally with no
      SIGILL. A local rehearsal here can only prove a patch doesn't break the (RVV-free)
      code path, never that it fixes the crash — only a real run on the self-hosted
      riscv64 runner settles that.
    - **The fix is the project's own `--without-rvv` configure flag, not a CMake flag,
      even though the vendored tree ships a CMakeLists.txt** — that CMake path is
      Windows-only; the Linux build (`setup.py`) drives zlib-ng's autoconf-style
      `./configure && make` directly and exposes no environment-variable hook for extra
      configure args, so the flag has to be added by patching `setup.py` itself, guarded
      on `platform.machine() in ("riscv64", "riscv32")` so other platforms are unaffected.
    - Distinct from gotcha 139 (no runtime check at all) and gotcha 71 (a *build-time*
      compiler-flag probe mismatch, not a runtime SIGILL): this is a runtime check that
      is present and correctly gated on HWCAP, and still unsafe, because confirming an
      instruction's availability by executing that same instruction assumes the one
      fact being tested.

279. **Gotcha 272's zlib-ng `vsetvli` SIGILL recurs whenever a *second*, independent
    port vendors the same library — and this repo's own queue notes from a QEMU-only
    rehearsal are not evidence it is fixed (gemmi's `FETCH_ZLIB_NG=ON` CMake
    `FetchContent`, vs. zlib-ng's own autoconf `setup.py` build; see
    `build-gemmi.yml`).** gemmi's `CMakeLists.txt` fetches the same zlib-ng project via
    `FetchContent`/`add_subdirectory` rather than the autoconf `./configure && make`
    path gotcha 272 patched, and hits the identical failure on the identical
    `ubuntu-24.04-riscv` hardware: the wheel builds, installs, and runs cleanly right
    up until the first test that touches real deflate/inflate (`test_align.py`'s
    `test_assign_best_sequences`, reading a gzip-compressed `.pdb.gz`), which dies with
    `Illegal instruction (core dumped)`. Before landing on RVV, disabling project-wide
    LTO first (a nearby, unrelated `CMakeLists.txt` comment about LTO corrupting
    zlib-ng specifically) reproduced the identical crash unchanged, ruling that out
    fast rather than assuming it was the fix because it touched the same subsystem.
    - **A QEMU-validated port is not evidence the same library is safe elsewhere** —
      gotcha 272 already establishes that QEMU's `vsetvli` never reproduces this SIGILL
      (TCG implements it correctly; only the real runner hardware doesn't), so an
      *other* port's "verified under QEMU, N passed" note is not proof this build shape
      avoids the crash — it proves only that nobody ran it on real riscv64 hardware yet.
      Treat such a note as untested for this purpose, not as a green light.
    - **The CMake embedding is the one place this is cheaper than gotcha 272's fix**:
      the vendored `CMakeLists.txt` already exposes a normal `option(WITH_RVV ...)`,
      so `-DWITH_RVV=OFF` in `SKBUILD_CMAKE_ARGS` falls back to zlib-ng's portable C
      kernels with a one-line `CIBW_ENVIRONMENT` change — no `setup.py` patch, no
      `platform.machine()` guard, because the CMake path (Windows-only for zlib-ng's
      *own* build) is the one gemmi actually drives.

288. **Rocky/AlmaLinux 10 dropped the classic SDL2-devel package entirely, on every
    arch — not a riscv64 gap (the pygame case; see `build-pygame.yml`).** `dnf list
    SDL2-devel` finds nothing: SDL2 now ships only as `sdl2-compat`, a runtime-only
    shim (`libSDL2-2.0.so.0`) implemented on top of SDL3, with no headers, no
    unversioned `libSDL2.so`, and no `sdl2.pc`. `SDL3-devel` exists instead
    (`appstream`/`crb`), but a project whose build genuinely needs SDL2 (`sdl2-config`,
    `pkg-config sdl2`) has to build it from source regardless of target arch — this
    is a base-image fact, not gotcha 51's EPEL-on-riscv64 gap. It cascades: EPEL's
    prebuilt `SDL2_image-devel`/`SDL2_mixer-devel`/`SDL2_ttf-devel` all declare
    `Requires: pkgconfig(sdl2) >= 2.0.9`, so `dnf install SDL2_image-devel` fails
    outright with "nothing provides pkgconfig(sdl2)" even where EPEL is enabled —
    those three have to be built from source too, not just SDL2 itself. Their own
    from-source builds are unaffected: `./configure --enable-png --disable-png-shared
    ...` etc. happily link the ordinary `libpng-devel`/`libjpeg-turbo-devel`/
    `libwebp-devel`/`libtiff-devel`/`mpg123-devel`/`flac-devel`/`libvorbis-devel`/
    `opus-devel` packages Rocky 10 still ships normally — only the SDL-family
    packages themselves are gone.
    - **`portmidi-devel`, `libmodplug-devel` and `fluidsynth-devel` are EPEL-only**
      (gotcha 51), so on riscv64 (no EPEL) portmidi has to be built from source
      (a plain `cmake . && make && make install`) and SDL2_mixer's mod/fluidsynth-midi
      backends have to be dropped (`--disable-music-mod-modplug
      --disable-music-midi-fluidsynth`) rather than built — a reasonable trim when the
      port's own test suite already excludes music-playback tests.
    - **A from-source SDL2 stack's full licence closure is bigger than the upstream
      project's own `docs/licenses/` folder** (gotcha 137's warning generalizes past
      auditwheel-vendored *distro* libraries): pygame's own reference licences cover
      SDL2/SDL2_image/SDL2_mixer/portmidi/freetype/libpng/libjpeg/etc., but building
      SDL2_ttf pulls in its bundled `external/harfbuzz` (MIT, its own `COPYING`, no
      riscv64 harfbuzz-devel to link instead) as a *separate* vendored `.so`, and
      `libtiff-devel`/`libwebp-devel` transitively pull in `liblerc` (Apache-2.0),
      `libzstd`, `jbigkit-libs` (GPL-2.0-or-later) and `brotli` — none of which
      upstream's own docs folder ships a licence text for, because upstream never
      builds this exact dependency graph. Verify the final vendored set with
      `auditwheel show`/`unzip -l` before trusting a project's own bundled licence
      folder is complete for *your* build.

289. **A CMake `ExternalProject_Add` patch step can shell out to `wget`, which the
    manylinux image doesn't ship (only `curl`) — and a parallel `make -j` build hides
    the real failure point behind unrelated targets that keep building for tens of
    minutes (the casadi/metis-external case; see `build-casadi.yml`).** CasADi's
    top-level build vendors METIS via `ExternalProject_Add(metis-external ...)`, whose
    patch step invokes upstream's own patch-fetch script — which calls `wget`, not
    `curl`, to download a patch file. `quay.io/pypa/manylinux_2_39_riscv64` has no
    `wget` binary, so the step fails immediately (`Utility wget not found in your
    PATH`) at only ~2% into the build. But `cmake --build build -j "$(nproc)"` is a
    parallel `make`, and `metis-external` is just one of many external-project/library
    targets scheduled concurrently with casadi's own core — `gmake` keeps building
    everything else (including "Built target casadi" itself) and only reports the
    overall failure once every *other* scheduled job finishes, tens of minutes later.
    - **`gh run view --log-failed` truncates to the tail of the log and shows only the
      late, unrelated-looking failure summary near the end** (e.g. "43% ... Error 2");
      it does not show the real error 20+ minutes earlier. Pull the full raw job log —
      `gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences`
      — and search near the *start* of the build output, not the end, for a build that
      fails "late" despite a fast, early root cause.
    - **The fix is a one-line system-package install**, not a build-flag change: add
      `wget` alongside the image's other missing packages in the same `dnf install`
      (or `apk add` on a musllinux leg, guarded by `matrix.libc` where one exists) —
      no need to disable the ExternalProject or switch fetch tools.
    - Don't confuse this with an *unrelated* real fix already in place on the same
      workflow: casadi separately had to switch its CMake generator from Ninja to Unix
      Makefiles because its `ExternalProject_Add` calls don't declare `BYPRODUCTS`,
      which Ninja's stricter build-graph check rejects. That fix stays — this gotcha's
      `wget` failure is a second, independent blocker that only surfaces once the
      generator issue is already resolved and the build reaches the external-project
      patch step at all.

294. **An upstream CMakeLists' own `-fPIC` allowlist can name only `x86_64`/`aarch64`,
    leaving riscv64 to link non-PIC objects into a shared library — which riscv64's `ld`
    rejects outright, unlike some other architectures (the casadi/casadi-sundials case;
    see `build-casadi.yml`).** CasADi's top-level `CMakeLists.txt` has a `-fPIC` section
    guarded by `if("${CMAKE_SYSTEM_PROCESSOR}" STREQUAL "x86_64" OR
    "${CMAKE_SYSTEM_PROCESSOR}" STREQUAL "aarch64")` before appending `-fPIC` to
    `CMAKE_C_FLAGS`/`CMAKE_CXX_FLAGS`/`CMAKE_Fortran_FLAGS` — riscv64 falls through with
    no `-fPIC` at all. Its vendored `casadi-sundials` static library (a plain
    `add_subdirectory`, not an `ExternalProject_Add`) then compiles without it, and
    linking it into `libcasadi_sundials_common.so`/`libcasadi_rootfinder_kinsol.so` fails
    with `relocation R_RISCV_JAL against 'KINProcessError' which may bind externally can
    not be used when making a shared object; recompile with -fPIC`. The build gets much
    further than gotcha 289's `wget` failure (~49 minutes vs. ~2%) before dying here,
    because everything upstream builds via `ExternalProject_Add` with its own autotools/
    libtool sub-build (IPOPT, MUMPS, METIS) already defaults to PIC objects for its own
    shared-library targets independently of the top-level flags — only a plain in-tree
    CMake static-library target inherits the arch-gated flags, and only riscv64 is
    excluded from them.
    - **Fix from the workflow, not a source patch: pass
      `-DCMAKE_POSITION_INDEPENDENT_CODE=ON`** on the outer `cmake -B...` configure
      line. This CMake variable initializes the `POSITION_INDEPENDENT_CODE` target
      property on every target in the project (static libraries included), independent
      of whatever the project's own hand-written `CMAKE_*_FLAGS` logic does — it adds
      `-fPIC`, it does not need to replace or conflict with an existing arch check.
      Confirmed no upstream `CMakeLists.txt` override of this variable exists for the
      main build (only inside a few unrelated `ExternalProject_Add(... CMAKE_ARGS
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON ...)` calls for *other* sub-dependencies,
      which don't touch the outer project's own variable).
    - **The error text names the exact riscv64 relocation type** (`R_RISCV_JAL`) and is
      unambiguous once you see it — but `gh run view --log-failed`/a truncated tail can
      still land you mid-build output rather than at the true `ld` error; grep the full
      raw log (gotcha 289) for `recompile with -fPIC` rather than trusting where the
      log happens to end.
    - **Don't assume this is riscv64-specific to relocations in general** — `x86_64`/
      `aarch64` tolerate certain non-PIC-into-.so link patterns that riscv64's linker
      does not for this particular relocation kind, which is exactly why an
      arch-allowlist written against only those two targets silently breaks on a third.

327. **A project's own `before-all`/`before-build` can already "fix" gotcha 138's stale
    `config.guess`/`config.sub` by downloading fresh copies from an external mirror at
    build time — and that download can itself 404 from inside the riscv64 container even
    though the identical URL succeeds from a laptop or any other network (the
    python-mecab-ko case).** `scripts/install_mecab_ko.py` fetches
    `http://git.savannah.gnu.org/gitweb/?p=config.git;a=blob_plain;f=config.guess;hb=HEAD`
    with plain `urllib.request.urlopen` — no special headers, no proxy — and it 404s only
    from the CI job (confirmed via `gh api .../jobs/<id>/logs --allow-escape-sequences`,
    gotcha 144-style raw-log reading), while the same request from outside CI returns 200.
    Like gotcha 243's IPv6 loopback, this is a container/runner network quirk that no
    amount of local rehearsal on a dev machine will reproduce — only the actual job log
    proves it. The fix is the one already in gotcha 138: patch the script to copy
    `/usr/share/automake-*/config.guess`/`config.sub` (already current enough for
    riscv64) instead of reaching the network at all, rather than trying to debug *why*
    the external mirror is unreachable from that specific runner.

328. **A vendored SIMD library with genuinely no portable/generic implementation at all
    (not even a slow reference one wired to the same public API) can still be ported to
    riscv64 by routing its x86-only path through SIMDe, as long as the actual intrinsics
    used stay within what SIMDe covers (the pyhmmer/HMMER case; see `build-pyhmmer.yml`).**
    HMMER3's fast filters (MSVFilter, ViterbiFilter, the striped Forward/Backward) exist
    only as hand-written SSE/NEON/VMX kernels operating on `P7_OPROFILE`/`P7_OMX`, and
    `CMakeLists.txt`'s own detection cascade hard `FATAL_ERROR`s when none of the three
    is found. Unlike gotcha 276's isal case, there is no `_base`/generic C implementation
    of the *optimized* pipeline sitting in the "always built" source list — the
    `generic_*.c` files are a separate, unoptimized reference algorithm used only for
    calibration/testing, not something `Pipeline` can fall back to. Two checks settle
    whether SIMDe is even viable before writing anything: `grep -ohE '_mm_[a-zA-Z0-9_]+'`
    over every file the SSE backend compiles, filtered to actual call sites (not comments
    — one hit here was `_mm_hadd_ps` named only in a comment explaining why the code
    avoids it) to see how far up the SSE/SSE2/SSE3/SSSE3/SSE4.1/AVX ladder the code
    actually reaches (SIMDe supports all of these, but the deeper the ISA, the larger the
    portable-fallback compile cost), and grepping for the corresponding `esl*ENABLE_SSE4`
    (or equivalent) build-time toggle to confirm any deeper-ISA calls are already gated
    off when that toggle is unset — HMMER's own `eslENABLE_SSE4` gate around its one
    SSE4.1 use (`_mm_max_epi8`/`_mm_blendv_ps`, both with an SSE2 fallback already coded)
    meant the riscv64 path only ever needs `simde/x86/sse3.h`.
    - **Route the redirect through a build-time header shim, not a source patch, when the
      project carries its own line-number-based patch mechanism against those same
      files.** pyhmmer's `src/hmmer/CMakeLists.txt` applies `patches/impl_sse/*.c.patch`
      against the vendored sources at build time via a custom `apply_patch.py` that seeks
      by the diff's absolute `-`-side line numbers with **no context verification** —
      inserting even one line above the patched hunk (e.g. wrapping
      `#include <emmintrin.h>` in an `#ifdef`) silently shifts every subsequent hunk onto
      the wrong lines and corrupts the file without erroring. Two of the twelve
      SSE-backend files here (`p7_omx.c`, `p7_oprofile.c`) are exactly the ones pyhmmer's
      own patches touch. The fix that avoids the whole class of bug: generate a small
      include directory at CMake configure time (`file(WRITE ...)`) containing stub files
      literally named `xmmintrin.h`/`emmintrin.h`/`pmmintrin.h`/`x86intrin.h`, each just
      `#define SIMDE_ENABLE_NATIVE_ALIASES` + `#include <simde/x86/sse3.h>`, and
      `include_directories(BEFORE <that dir> <simde source dir>)` only on the
      no-native-SIMD branch — every vendored file's own `#include <xmmintrin.h>` line
      resolves to the shim without a single byte of the vendored tree changing, so
      pyhmmer's own patches keep applying at their original, correct line numbers.
    - **A build's own runtime CPU-feature detection can assume "this vector backend
      implies real x86", which breaks independently of the SIMD redirect itself.**
      Easel's `esl_cpu.c` compiles `cpu_run_id()`/`cpu_has_sse()` — raw
      `__asm__("cpuid" ...)` — whenever `eslENABLE_SSE` is defined, because historically
      that could only be true on real x86/x86-64 hardware. Turning `eslENABLE_SSE` on for
      the SIMDe/riscv64 path breaks that assumption and the inline asm fails to
      assemble; grep for who actually *calls* the corresponding `esl_cpu_has_*()`
      function before patching (here: nobody in the compiled sources), so the fix is
      just gating the asm-bearing internals on an additional "are we really on x86"
      macro rather than reimplementing a CPUID equivalent for riscv64.
    - **Confirm the wheel doesn't build a wrong `HMMER_IMPL`/`eslENABLE_*`-keyed dispatch
      dead — grep the Cython/pybind layer for its own copy of the same dispatch,** not
      just the C headers. pyhmmer's `.pxd` files gate `libhmmer.impl_sse` vs `impl_neon`
      vs `impl_vmx` on a literal `HMMER_IMPL` string Cython constant piped in from the
      *same* CMake variable (`cython_extension(... DIRECTIVES -E HMMER_IMPL=${HMMER_IMPL})`)
      — reusing `"SSE"` (rather than inventing a new `"SIMDE"` value) for the riscv64
      branch is what keeps this second, easy-to-miss dispatch pointed at the right impl
      directory without a matching Cython-side change.

332. **A SIMDe SSE-emulation port (gotcha 328) can compile clean, pass its own project's
    per-primitive/per-function unit tests, and still produce wrong results at the
    full-pipeline level on riscv64 specifically — and the wrongness does not reproduce
    on any other host you can test locally, including one exercising the exact same
    "portable, no native ISA" SIMDe fallback (the pyhmmer/HMMER MSVFilter case; PR
    riseproject-dev/python-wheels#1497, parked rather than merged).** After landing
    gotcha 328's SIMDe redirect for pyhmmer's `impl_sse` backend, real riscv64 CI (not
    a QEMU rehearsal — the actual self-hosted `ubuntu-24.04-riscv` runners) failed 60
    of 995 tests with hit counts of `0` where real hits were expected, or under-counts
    like `479 != 482`. That pattern — mostly-zero with occasional near-misses, not
    uniformly wrong — is what actually happened when the underlying cause was
    isolated to one specific function, `p7_MSVFilter()` in `impl_sse/msvfilter.c`.
    - **Reproduce with a QEMU container, not Docker Desktop, if Docker is stuck**
      behind a stalled privileged-access dialog with no way to click through it in an
      agent session: `podman machine ssh` can itself hang for unrelated reasons, but
      `podman run --privileged --platform linux/riscv64 <manylinux image>` on a
      `tonistiigi/binfmt`-registered podman machine works — the container needs
      `--privileged` for QEMU's user-mode ptrace-based emulation even after
      `docker/podman run --privileged docker.io/tonistiigi/binfmt --install riscv64`
      shows the interpreter `enabled` with flags `POCF` (F/fix-binary set); without it,
      any riscv64 container exits 139 (SIGSEGV) before your entrypoint ever runs.
    - **The project's own per-function unit test drivers (`#ifdef pXXX_TESTDRIVE` in
      HMMER's case, one per `impl_sse/*.c` file, comparing the SIMD-optimized filter
      against the project's independent portable/"generic" reference implementation)
      are exactly the right tool to bisect a SIMDe port with — but passing all of them
      individually does not prove the full pipeline is correct.** Every other
      `impl_sse` component (ViterbiFilter, the Forward filter, posterior decoding,
      optimal-accuracy alignment, null2 bias correction) and the hand-vectorized
      `expf`/`logf` approximations in `esl_sse.c` passed their own dedicated unit
      tests on real riscv64/GCC 14.3.1 (accuracy matching arm64 almost to the bit:
      ~6e-9 average relative error, ~1.2e-7 max, right at float precision). Only
      `p7_MSVFilter` failed, and it failed *hard* — `scores differ (-21.25, -10.86)`,
      a ~10-nat divergence, not a rounding artifact.
    - **A deterministic, non-flaky wrong answer that reproduces identically across
      every optimization level rules out a compiler miscompilation, not just an
      `-O3`-specific one.** The exact same `(-21.25, -10.86)` mismatch reproduced at
      `-O1`, `-O2` and `-O3` (test the specific translation unit at each level by
      dropping a single freshly-compiled `.o` into a copy of the otherwise-`-O3`
      static archive with `ar rcs` — no need to rebuild the whole library per level).
      A genuine GCC backend bug from register pressure/spilling would be expected to
      be *sensitive* to optimization level, not identical across three of them.
    - **When a filter has an internal fast-path shortcut to a related, separately
      testable function, A/B it by force-disabling the shortcut** — here,
      `p7_MSVFilter()` unconditionally tries `p7_SSVFilter()` first
      (`if (status != eslENORESULT) return status;`) before falling into its own DP
      loop. Patching that call to `status = eslENORESULT;` (skip the shortcut,
      guaranteed fallthrough) reproduced the *identical* wrong score. That rules out
      `ssvfilter.c`'s control flow as the cause and points at something the two paths
      share (most obviously the input data both read, `om->rbv`/`om->sbv`, but see
      below) rather than either filter's own loop logic.
    - **Every individual SIMD primitive the failing function uses can check out fine
      in a tiny synthetic harness, and the full function can still be wrong** — this
      is the core, hard-won lesson. Standalone probes against real riscv64 GCC 14.3.1,
      each run hundreds of random trials against a scalar C reference: the saturating
      DP step (`_mm_max_epu8`/`_mm_adds_epu8`/`_mm_subs_epu8`), the byte-lane shift
      (`_mm_slli_si128`), the horizontal-max reduction chain
      (`_mm_shuffle_epi32`/`_mm_shufflelo_epi16`/`_mm_srli_si128`), and even the
      `union { __m128i v; uint8_t i[16]; }` type-pun pattern the profile-conversion
      code (`mf_conversion()` in `p7_oprofile.c`) uses to build `om->rbv` — every one
      of them was bit-exact correct in isolation. The bug is therefore not in any
      single SIMDe primitive's semantics; it is in how the real function composes
      many of them across a real loop (many live `__m128i` temporaries, `Q`-many
      inner iterations, `L`-many outer iterations) — something no small synthetic
      harness reproduces, and something that would need either a real riscv64 GCC
      debugger session stepping through the actual failing call, or upstream
      SIMDe/HMMER maintainer input, to pin to an exact line.
    - **Checking the "generic"/reference implementation's own internal self-consistency
      is a cheap way to make "maybe the reference is wrong, not the SIMD path" less
      likely, without being able to directly diff scores across architectures.**
      `generic_viterbi.c` has its own `p7GENERIC_VITERBI_TESTDRIVE` that checks
      `p7_GViterbi()`'s score against an independently reconstructed optimal
      traceback's score (`p7_GTrace` + `p7_trace_Score`, tolerance `1e-6`) — pure
      portable C, zero SIMD/SIMDe dependency. It passed cleanly on real riscv64,
      which doesn't *prove* the Generic score matches what x86 would compute, but
      combined with "pure C, no architecture-specific code path exists to diverge
      through" it's good enough evidence to stop suspecting the reference and treat
      the ~10-nat divergence as real.
    - **When a bisection this thorough still can't isolate the exact line within a
      bounded budget, park the port rather than merging a function you can't explain
      the wrongness of** — `.queue.yml` `status: parked` with a note naming the exact
      function, what was ruled out, and what remains (a real debugger session or
      upstream input), and leave the PR open (not draft, not deleted) with the
      investigation written up in its description, so the next attempt starts from
      "here's what's already eliminated" instead of from zero.

333. **A vendored C++ library's architecture-fallback stub can have a genuinely correct
    no-op body and still trip `-Werror=unused-parameter` on any architecture outside its
    named x86/ARM/PPC set — unlike gotcha 267's dead `#warning` branch, there is no
    wrong/missing code here, just an unused parameter (the pyorc/liborc case).**
    liborc (Apache ORC's C++ core, which pyorc's `setup.py` downloads and builds from
    source) gates its CPU-feature-detection code in `CpuInfoUtil.cc` on
    `CPUINFO_ARCH_X86`/`CPUINFO_ARCH_ARM`/`CPUINFO_ARCH_PPC`; riscv64 matches none of
    them, so it falls into the final `#else` branch — a correct, intentional catch-all
    whose `ArchParseUserSimdLevel`/`ArchVerifyCpuRequirements` bodies are genuine no-ops
    (`return true;` and an empty body) that simply never reference their parameters.
    liborc's own `CMakeLists.txt` defaults `STOP_BUILD_ON_WARNING` to `ON`, appending
    `-Werror` unconditionally; upstream's CI only ever builds x86/ARM/PPC, so this branch
    is never compiled there and the warning-turned-error never surfaces upstream.
    - **The wrapper's own env-var plumbing can silently defeat the usual
      `CXXFLAGS=-Wno-error=...` escape hatch — check for it before assuming the fix is a
      one-line `CIBW_ENVIRONMENT` addition.** pyorc's `setup.py` has a
      `_get_build_envs()` helper that unconditionally does `env["CXXFLAGS"] = "-fPIC"`
      (a bare assignment, not an append) right before invoking `cmake`, discarding
      anything `CIBW_ENVIRONMENT` set. Gotcha 267's fix (append `-Wno-error=<diag>` to
      the vendoring project's own `-DCMAKE_CXX_FLAGS`) still applies in spirit, but the
      patchable surface has to be the wrapper's hardcoded `cmake_args` list, not the
      environment.
    - **A source patch is simpler here because the vendored source lands as plain
      extracted files, not a packed blob** (contrast gotcha 267's `.tar.gz` vendored
      inside the checkout, which `git apply` cannot reach). `setup.py` downloads and
      extracts liborc's tarball itself at build time, so the fix patches `setup.py` to
      add a few `str.replace()` calls on the two affected function bodies right after
      its own `_download_source()` call — the same shape as the existing
      `_patch_protobuf_version` fixup already in the file, just targeting a `.cc` file
      instead of a `.cmake` one.
    - **Confirm it's this class before writing anything**: the diagnostic names the
      exact parameters (`simdLevel`, `hardwareFlags`, `ci`) and the exact line numbers,
      and the failing function names (`ArchParseUserSimdLevel`,
      `ArchVerifyCpuRequirements`) are the tell that this is the *architecture*
      dispatch's fallback, not a SIMD gate (gotcha 71) or a dead code path (gotcha 267).

337. **lexbor, re2 and uchardet are absent from Rocky 10's baseos/appstream/crb on every
    arch, and `re2-devel` only resolves from EPEL — which riscv64 does not carry (refines
    gotcha 51; the resiliparse case).** `dnf -q list lexbor-devel re2-devel uchardet-devel`
    against a bare `rockylinux/rockylinux:10` with CRB enabled finds nothing for the first
    and third on any arch; `re2-devel` (Fedora's naming for Google's RE2) resolves only
    after installing `epel-release`, and gotcha 51 already established EPEL is absent on
    riscv64. The fix is the same shape as `build-google-re2.yml`'s abseil-cpp + re2
    pattern: build all three from source in `CIBW_BEFORE_ALL_LINUX`, with
    `-DCMAKE_INSTALL_LIBDIR=lib` on every one of them — GNUInstallDirs otherwise defaults
    some of them to `lib64` on this image (gotcha in native-deps-and-linking.md), invisible
    until the extension that needs that particular library fails to link — and
    `LIBRARY_PATH`/`LD_LIBRARY_PATH=/usr/local/lib` in `CIBW_ENVIRONMENT`.
    - **A project's own vcpkg overlay port can pin a fork, not upstream.** resiliparse's
      `.vcpkg/ports/lexbor` builds `phoerious/lexbor` at a specific commit, not
      `lexbor/lexbor`; the fork adds DOM node reference counting the Cython bindings
      depend on, so building vanilla upstream lexbor compiles cleanly and only misbehaves
      (or crashes) much later, with no configure-time error to point at the real cause.
      Diff the fork against upstream (`gh api repos/<fork>/compare/<upstream-owner>:
      <upstream-branch>...<fork-owner>:<ref>`) before assuming any lexbor checkout is
      interchangeable — `status: diverged` plus a small, on-topic file list confirms it's
      a deliberate patch set, not a stale mirror.
    - **A monorepo sibling's `.pxd` can pull a header for a library the importing
      extension never links.** resiliparse's `itertools.pyx` `cimport`s a type from
      fastwarc's `legacy/warc.pxd` (copied in locally by `setup.py`, not pip-installed),
      and that pxd's own `cdef extern from` chain reaches `<lz4hc.h>` — so the extension
      needs `zlib-devel lz4-devel` even though its own `Extension(..., libraries=[])`
      names neither. `dnf install`ing the same two packages the sibling package's own
      build already needs, in this package's `before-all` too, is cheaper than tracing
      which cimported header pulled which system library in a `fatal error: lz4hc.h: No
      such file or directory` from deep inside a Cython-generated `.cpp` file.

351. **A project's own build script can gate a *sibling* vendored library's SIMD macros
    on `platform.machine() != "ppc64le"`, silently assuming "not ppc64le" means "x86 or
    ARM" — the hdf5plugin/c-blosc2 case.** Gotcha 71 covers a vendored library gating
    riscv64 SIMD on the *parent build's* variable; this is a step removed: hdf5plugin's
    own `setup.py` (not c-blosc2's CMake, which gates cleanly on its own) has an
    `if platform.machine() == "ppc64le": ... else: define_macros.append(("SHUFFLE_SSE2_
    ENABLED", 1)) ... SHUFFLE_AVX2_ENABLED ... SHUFFLE_AVX512_ENABLED ... SHUFFLE_NEON_
    ENABLED` block that force-enables every one of c-blosc2's shuffle SIMD backends for
    any architecture that isn't ppc64le. Each per-ISA `.c` file (`shuffle-sse2.c`,
    `shuffle-avx2.c`, `shuffle-neon.c`) is itself correctly gated on the *compiler's*
    `__SSE2__`/`__AVX2__`/`__ARM_NEON__` macros and compiles to an empty translation unit
    on riscv64 — but `shuffle.c`'s CPU-dispatch code reads only the `SHUFFLE_*_ENABLED`
    macros, independent of whether the paired `.c` file compiled anything. With
    `SHUFFLE_NEON_ENABLED` force-defined, `shuffle.c`'s `#elif defined(SHUFFLE_NEON_
    ENABLED)` branch compiles `blosc_get_cpu_features()` against `getauxval(AT_HWCAP) &
    HWCAP_ARM_NEON` — an ARM-only glibc hwcap constant undeclared on riscv64 — a hard
    compile error; even past that, `SHUFFLE_AVX512_ENABLED`/`AVX2_ENABLED` pull in
    `is_shuffle_avx2`/`is_bshuf_AVX512` externs that `shuffle-avx2.c` never defines
    without `__AVX2__`, an undefined-reference link error. Fix: gate on the actual
    detected architecture (`HostConfig.ARCH` in this project, already used two lines
    below in the same function for an `ARM_7`/`ARM_8`-only compile flag) rather than on
    the absence of one named architecture — `PPC_64` → Altivec, `ARM_7`/`ARM_8` → NEON,
    `X86_32`/`X86_64` → SSE2/AVX2/AVX512, everything else (riscv64 included) → none of
    these macros, falling back to `shuffle-generic.c`/`bitshuffle-generic.c` exactly as
    the project's own non-force-enabled v1 blosc plugin already does. Simulating the
    parsed architecture string against the exact dispatch logic (`_parse_arch("riscv64")`
    from the project's own `py-cpuinfo` build dependency) before touching CI proves the
    fix produces identical macros for x86_64/aarch64/ppc64le/armv7l and none for riscv64,
    with no manylinux image or QEMU rehearsal needed.

358. **`dnf`/`apk` installing an older cmake to satisfy gotcha 257 doesn't necessarily make
    it the one that runs: both manylinux and musllinux riscv64 images carry a
    pipx-installed cmake >= 4 earlier on `PATH` by default (the keystone-engine case).**
    `dnf install -y cmake` lands `cmake-3.31.8` at `/usr/bin/cmake`; `apk add --no-cache
    cmake` lands `cmake-3.31.7` at the Alpine equivalent — both genuinely satisfy a
    project whose vendored `CMakeLists.txt` calls `cmake_policy(SET CMP0051 OLD)` (whose
    `OLD` behaviour CMake 4.0 removed outright, a harder failure than gotcha 257's
    `cmake_minimum_required` floor — no `CMAKE_POLICY_VERSION_MINIMUM` env var rescues
    it). But the CI log still shows the error coming from
    `/opt/_internal/pipx/venvs/cmake/.../cmake-4.4/Modules/...` — the image's own
    pre-baked cmake, installed via pipx into a directory the image puts ahead of
    `/usr/bin` on `PATH` by design (so a plain `pip install cmake` inside `before-build`
    hits the same shadow, not just the system package manager path).
    - **The fix is a dedicated one-binary `PATH` entry, not `PATH=/usr/bin:$PATH`.**
      `mkdir -p /tmp/x-cmake && ln -sf /usr/bin/cmake /tmp/x-cmake/cmake`, then
      `CIBW_ENVIRONMENT: PATH=/tmp/x-cmake:$PATH`, shadows only `cmake` and leaves
      cibuildwheel's own interpreter resolution alone. Prepending the whole of
      `/usr/bin` instead breaks a *different* thing on musllinux specifically: Alpine's
      `python3` package (a dependency of `automake`/other `apk add` packages, or already
      present) also lands a `python` at `/usr/bin/python`, and cibuildwheel's own
      pre-build self-check ("python available on PATH doesn't match our installed
      instance") aborts the build before it reaches the actual compile — a failure mode
      that never shows up on manylinux (Rocky's base image has no bare `/usr/bin/python`
      to collide with), so it only appears once the musllinux leg of the same matrix runs.

359. **A CMake project forked from old LLVM sources can validate the host architecture
    through *two* independent mechanisms — the vendored `utils/llvm-build` Python tool
    has its own separate check and its own escape hatch (the keystone-engine case).**
    Patching `config-ix.cmake`'s `LLVM_NATIVE_ARCH` if/elseif chain to add a `riscv64`
    branch (gotcha for the "Unknown architecture" `FATAL_ERROR` it throws otherwise) is
    only half the fix. That chain's job is just picking a *placeholder* string — mapping
    to any of the project's own target names (`X86`, `ARM`, ...) or an invented one like
    `RISCV` passes config-ix.cmake fine, since `LLVM_NATIVE_ARCH`'s only other consumer
    there is a `list(FIND LLVM_TARGETS_TO_BUILD ...)` membership check that treats "not
    found" as a harmless "native JIT unavailable" message. But `llvm/CMakeLists.txt`
    separately shells out to `utils/llvm-build/llvm-build --native-target
    "${LLVM_NATIVE_ARCH}"`, a Python tool that validates the value against real
    `LLVMBuild.txt`-declared components and hard-errors `invalid native target: 'RISCV'
    (not in project)` for anything that isn't one — including an invented placeholder
    that happened to satisfy the CMake-side check. Read `llvmbuild/main.py`'s own
    argument handling before picking a value: it special-cases the literal string
    `"Unknown"` to mean "no native target" (`native_target_name = None`, skipping the
    component lookup entirely) — the same state a real absent architecture already
    reaches, and the only value that satisfies both checks at once.

374. **`find_package(Python3 REQUIRED COMPONENTS Interpreter Development)` fails on
    manylinux's own CPython the same way on x86_64/aarch64/riscv64 alike — nothing
    riscv64-specific about it (the tensordict case).** CMake's `Development` component
    is shorthand for *both* `Development.Module` (what building a `.so` extension needs)
    and `Development.Embed` (a linkable `libpython` for embedding Python in a C++ host).
    manylinux images build CPython with `Py_ENABLE_SHARED=0` and ship only a static
    `libpythonX.Y.a`, and `Development.Embed`'s `Python3_LIBRARIES` lookup does not
    accept it — `FindPython3` aborts with `Could NOT find Python3 (missing:
    Python3_LIBRARIES Development Development.Embed)` before a single file compiles.
    A pybind11/pure-C-extension project that never embeds Python only ever needs
    `Development.Module`; requesting the wider `Development` component is the bug, not
    the missing static lib. Confirmed by reproducing the exact configure failure on
    `quay.io/pypa/manylinux_2_39_aarch64` (no QEMU/riscv64 needed to hit it), then
    confirming `Development.Module` alone lets configure succeed, the extension link
    with zero `libpython` reference in `ldd`, and the import work. Fix: patch the
    project's `CMakeLists.txt` component list from `Development` to `Development.Module`
    (`Upstream-Status: To upstream`, since it is a real portability bug independent of
    riscv64) — do not reach for a `dnf`/pip-installed shared-libpython workaround, since
    the fix is one word and matches how manylinux extensions are meant to link anyway.

377. **Rocky's `lib64` `GNUInstallDirs` default can make a hardcoded `"lib"`
    packaging check silently drop the one file a wheel exists to ship (the mlx case;
    see `build-mlx.yml`).** CMake's `GNUInstallDirs` defaults `CMAKE_INSTALL_LIBDIR` to
    `lib64` on 64-bit RHEL/Rocky-family systems — every `manylinux_2_39_*` image,
    riscv64 included, since they are all Rocky 10 — not the plain `lib` that
    Debian-based hosts (upstream's own `ubuntu-22-large`/`ubuntu-22.04-arm` CI runners)
    use. MLX splits every release into a per-interpreter `mlx` wheel and a `mlx-cpu`
    backend wheel by classifying each installed file in `setup.py` with
    `file.is_relative_to(Path(mlx_dir, "lib"))` (plus `"include"`/`"share"`) — a
    hardcoded `"lib"` that never matches `mlx/lib64/libmlx.so` on a Rocky-based build,
    so the entire compiled compute library is deleted from the one wheel that is
    supposed to ship it, with the build otherwise going green (`Successfully built
    mlx_cpu-...whl`, no error, just a wheel 15x smaller than expected and missing its
    only real payload). Passing `-DCMAKE_INSTALL_LIBDIR=lib` in `CMAKE_ARGS` sidesteps
    the bug with no source patch, since `GNUInstallDirs` respects an already-set value.
    - **Caught by inspecting the built wheel's file list, not a riscv64 CI failure.**
      `unzip -l dist/*.whl | grep -i lib` on any host reproduces it identically on
      `manylinux_2_39_aarch64`/`_x86_64` too — it is a Rocky-vs-Debian `GNUInstallDirs`
      difference, not an riscv64 one, so a local rehearsal (gotcha 101) catches it for
      free before spending a CI cycle.
    - **A packaging script that classifies files by a hardcoded path fragment is a
      pattern to watch for generally** whenever a project splits one build into
      multiple wheels (frontend/backend, core/GPU, etc.) — the classification logic is
      usually written and tested only against the author's own CI image family.

378. **A newer libstdc++ on the manylinux image can turn a project's own
    `-DCMAKE_COMPILE_WARNING_AS_ERROR=ON` CI flag into a build failure that has nothing
    to do with riscv64 (the mlx case).** `quay.io/pypa/manylinux_2_39_riscv64`/`_aarch64`
    ship GCC 14 (Rocky 10), whose libstdc++ marks the free-function
    `std::atomic_load`/`atomic_store`/`atomic_exchange` overloads on `shared_ptr`
    deprecated (superseded by `std::atomic<std::shared_ptr<T>>`, C++20). MLX's
    `mlx/error.h` uses exactly those three calls, and upstream's own release action
    always adds `-DCMAKE_COMPILE_WARNING_AS_ERROR=ON` for non-Windows — a flag their own
    `ubuntu-22-large`/`-arm` runners' older libstdc++ never trips, so it reached 0.32.2
    unnoticed. Building the identical source under the newer toolchain turns three
    warnings into three hard errors (`cc1plus: all warnings being treated as errors`)
    before a single test runs. Simply not passing that one flag (CMake defaults
    `CMAKE_COMPILE_WARNING_AS_ERROR` to `OFF`) reproduces upstream's actual
    `CMakeLists.txt` unmodified — the `-Werror` promotion is their CI script's opinion,
    not the project's own baseline, so omitting it needed no patch and is not really a
    divergence from the project being built, only from one argument in their action.
    - **Reproduce locally first**: a plain `python -m build -w` with the flag on vs. off
      on `manylinux_2_39_aarch64` (gotcha 101) settles which of the two is responsible
      in minutes, and shows the exact deprecated symbols by name.
