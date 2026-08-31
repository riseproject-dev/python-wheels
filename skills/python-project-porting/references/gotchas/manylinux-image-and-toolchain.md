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
