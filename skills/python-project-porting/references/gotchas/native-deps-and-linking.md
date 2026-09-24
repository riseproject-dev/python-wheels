# Gotchas — Native dependencies & linking

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/native-deps-and-linking.md`.

## In this file

- **16** — All-static BUNDLED build + a dep the project can't bundle = link failure.
- **17** — Building an extension that links another wheel we ship (the dep-wheel pattern).
- **63** — Upstream's native dependency may live in a prebuilt CI Docker image built by a
- **72** — A native dependency upstream gets from a vendor tarball may already be in the
- **73** — A project that links its dependency *statically* silently produces no `-L` when
- **77** — A setup.py that *downloads* a prebuilt native library can often be satisfied by
- **98** — A prebuilt native dependency fetched from upstream's *own* sibling build repo is
- **121** — An add-on wheel that must interoperate with another wheel we ship has to be built
- **143** — Static-with-PIC dependency inside a *shared* dependency: one bundled `.so`
- **159** — Bundling shared libraries next to a binary: `patchelf --set-rpath` writes
- **160** — An architecture `select()` that supplies *source* files and ends in
- **206** — A C++ ML/inference engine that gates its fast BLAS backend to x86 usually
- **220** — BLST (Ethereum's vendored elliptic-curve library, pulled in by ckzg/c-kzg-4844
- **231** — A vendored C library's own CMake can carry a genuine, tested riscv64 branch —
- **363** — A `libraries=[...]` entry can go missing from the link line with *no* error —
- **368** — Linking several codecs against Rocky 10's system libraries instead of
- **395** — When a project dlopen()s a differently-named shared library per major version
- **400** — A `setup.py` knob that feeds a downloaded dependency's *sources* into
  `Extension(sources=...)` needs a path relative to the project root, so the tarball has
  to be extracted inside the checkout, not into `/tmp`.
- **415** — Turning an optional native codec OFF can select a stub whose signature has
  drifted from its declaration; the ELF links anyway and the first `dlopen` is where it
  dies.

- **461** — A dependency wheel *shipping* a library is not a promise that the library has the
  symbol a build gates on: a presence-of-file probe must become a presence-of-symbol probe, or
  the extension links clean and fails at import (the vllm/OpenBLAS `sbgemm_` case).
- **463** — Substituting our dep wheel for an upstream prebuilt can change the SONAME: when the
  package's own linker-flag emitter says `-l<name>`, re-soname the staged copy instead of
  shipping a symlink farm (the sherpa-onnx-core/onnxruntime case).
- **486** — Legacy TBB 2020.x (the hand-written makefile build, not oneTBB's CMake one) needs
  no riscv64 patch, so don't switch a project to `--onetbb` on suspicion — settle it with one
  QEMU `make` (the usd-core/OpenUSD case).
- **547** — A vendored BoringSSL's generated assembly is self-guarded, so an architecture it
  does not list needs no `OPENSSL_NO_ASM`.
- **550** — When the downloader's unknown-platform branch is a graceful PATH search rather
  than a hard failure, gotcha 77's patch is unnecessary — just put the self-built binary
- **554** — A Go-binary-in-a-wheel tool (not a downloader) can also lack riscv64 in its own
  platform table — drive its Python API directly instead of patching it (the mcp-grafana case).
  there (the shfmt-py case).
---

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

63. **Upstream's native dependency may live in a prebuilt CI Docker image built by a
    *sibling repo* — that repo is the recipe (the h5py case; see `build-h5py.yml`).**
    A `[tool.cibuildwheel]` table whose `manylinux-<arch>-image` points at
    `ghcr.io/<org>/...` rather than `quay.io/pypa/...` means the native library is not
    built by the workflow at all: it is baked into an image, and there is no riscv64
    variant to inherit. h5py builds HDF5 + libaec into
    `ghcr.io/h5py/manylinux_2_28_<arch>-hdf5`. Find the image repo with
    `gh api "search/repositories?q=org:<org>&sort=updated"` — it holds the Dockerfiles
    and the `install_<dep>.sh` scripts — and replay those scripts from
    `CIBW_BEFORE_ALL_LINUX`, which is a plain multi-line shell script run under `sh -c`
    with `CIBW_ENVIRONMENT` already in scope (checked in cibuildwheel 4.2.0
    `platforms/linux.py`), so `$DEP_VERSION`/`$<DEP>_DIR` set there reach it.
    - **Take the dependency versions from the image repo's history at the package's
      release date, not from its HEAD.** `git log -- Dockerfile_manylinux_...` plus the
      PyPI upload time pins them, and the published wheel confirms it in one command:
      `unzip -l <upstream wheel> | grep '\.so'` showed `libhdf5-….so.320.0.0` and
      `libaec-….so.0.1.4`, i.e. HDF5 2.0.0 + libaec 1.1.4, the pair the image carried
      then — HEAD had already moved to 2.2.0.
    - **Pin `CMAKE_INSTALL_LIBDIR=lib`.** GNUInstallDirs picks `lib64` on RedHat-family
      hosts (the riscv64 manylinux image is Rocky 10), while a `<DEP>_DIR=/usr/local`
      prefix is usually expanded by `setup.py` as `$<DEP>_DIR/lib` only — h5py's
      `setup_configure.py` does exactly that. Upstream hit the same thing later and
      pinned it identically (`h5py/hdf5-manylinux@5b15b5d`).
    - **Read the image script before running it verbatim.** These scripts end with
      image-size cleanup (`yum erase -y zlib-devel`) that is harmless in a throwaway
      image layer but can cascade in a build container — on Rocky 10 `zlib-devel` is a
      *provide* of the preinstalled `zlib-ng-compat-devel`. Mirror the build steps,
      drop the cleanup.
    - **`CIBW_TEST_GROUPS: ''` clears an inherited `test-groups`**, the same way gotcha
      51's `CIBW_BEFORE_BUILD: ''` clears `before-build`: list options are read with
      `ignore_empty=False` too, so the empty env var wins over the pyproject value.
      That is how you drop an upstream wheel-test path built on `tox` + `tox-uv` +
      a nightly wheel index (h5py's `test-groups = ["wheels"]` / `ci/cibw_test_command.sh`)
      and run the suite the project's own tox `test` env runs instead.
    - **The licence for such a dependency has a zero-packaging-change home more often
      than gotcha 44 suggests**: a project that already vendors third-party licence
      texts usually declares a directory glob (h5py: `license-files = [..., "licenses/*"]`),
      so dropping `licenses/<dep>.txt` in is the whole patch. Verify it the gotcha-44 way,
      and check the assertion actually fails against the *upstream* wheel first — h5py's
      published Linux wheels bundle libaec and ship no libaec licence.

72. **A native dependency upstream gets from a vendor tarball may already be in the
    manylinux image's own repos — and the aarch64 image is a native-speed rehearsal
    host for the whole recipe (the mysql-connector-python case).** Gotcha 51 queries
    Rocky's repos for a *build tool*; the same query settles the harder question of
    where a **library** comes from. mysql-connector-python's C extension links the
    MySQL C API, which Oracle publishes for x86_64/aarch64 only
    (`dev.mysql.com/get/.../mysql-<ver>-linux-glibc2.28-riscv64.tar.xz` → 404,
    `repo.mysql.com/yum/.../el/10/` lists only `aarch64/` and `x86_64/`) — that reads
    like `not-feasible` or a multi-hour from-source port of MySQL itself. It is
    neither: Rocky 10 CRB ships `mysql8.4-devel` for riscv64, and manylinux's
    `install-runtime-packages.sh` already runs `dnf config-manager --set-enabled crb`,
    so `CIBW_BEFORE_ALL_LINUX: dnf -y install <pkg>-devel` is the whole provisioning
    step and auditwheel vendors the `.so` into the wheel.
    - **Answer it from repo metadata, before pulling any image** — one gunzip per
      repo, and it covers every arch at once:
      ```bash
      md=$(curl -s https://dl.rockylinux.org/pub/rocky/10/CRB/riscv64/os/repodata/repomd.xml \
           | grep -oE 'repodata/[a-f0-9]+-primary\.xml\.gz' | head -1)
      curl -s "https://dl.rockylinux.org/pub/rocky/10/CRB/riscv64/os/$md" | gunzip \
           | grep -oE '<name>[^<]*<pkg>[^<]*</name>' | sort -u
      ```
      Check `CRB` as well as `AppStream`/`BaseOS`: `-devel` subpackages very often live
      only in CRB (`mysql8.4` is in AppStream, `mysql8.4-devel` only in CRB). The same
      trick against `.../AppStream/source/tree/` confirms the SRPM exists before you
      wire up a `gpl_sources` job.
    - **`manylinux_2_39_aarch64` is AlmaLinux 10, `manylinux_2_39_riscv64` is Rocky 10**
      (pypa/manylinux's README says "AlmaLinux/RockyLinux 10 based"). Same package set,
      same paths, same `dnf`. So on an arm64 host the *entire* recipe — before-all,
      compile, `auditwheel repair`, venv install, before-test, and the real test
      command run from an empty cwd — replays natively in minutes, no QEMU. That caught
      three distinct failures here (link error, missing `setuptools`, `EPERM` on
      `execve`) that would each have cost a riscv64 CI cycle. Confirm the one thing
      aarch64 cannot tell you — that the package exists for riscv64 — with a single
      `dnf install` in the riscv64 image.
    - **The version you get is the distro's, not upstream's.** Check the C source is
      version-gated before accepting it (`grep -n 'MYSQL_VERSION_ID' src/*.c` showed
      every newer-API use behind `#if`, and `MYSQL_TYPE_VECTOR` `#define`d when the
      header predates it), and say in the commit message which features compile out.

73. **A project that links its dependency *statically* silently produces no `-L` when
    only the shared library is installed.** Distributions ship `libfoo.so` and no
    `libfoo.a`, and an upstream that was only ever built against a vendor tree can
    depend on the static one in a way that is invisible until the link step.
    mysql-connector-python's `cpydist` is the sharp version: `mysql_c_api_info()`
    records the library path under the key **`link_dirs`**, `BuildExt.run()` only ever
    reads **`library_dirs`**, and the gap is bridged by `_finalize_mysql_capi()`, which
    copies `libmysqlclient*` into a private `build/temp.*/capi/lib` and then deletes
    everything not ending in `.a` "to force static linking". With a distro package that
    directory ends up empty, the only `-L` on the command line points at it, and the
    build dies with `cannot find -lmysqlclient` after compiling every object
    successfully.
    - **Look for an upstream escape hatch before patching.** cpydist already reads
      `EXTRA_LINK_ARGS` from the environment, so
      `CIBW_ENVIRONMENT: ... EXTRA_LINK_ARGS=-L/usr/lib64/mysql` fixes it with no diff
      at all. `LDFLAGS` is the generic fallback — `distutils.sysconfig.customize_compiler`
      appends it to `ldshared`, so it lands ahead of the objects and the `-l` flags.
    - **The symptom names the missing `-L`, not the missing `.a`** — read the failing
      link line for which directories actually reached it rather than assuming the
      library is absent.

77. **A setup.py that *downloads* a prebuilt native library can often be satisfied by
    building that library yourself — read whether the downloader skips or fails
    (the ddtrace/libddwaf case).** Gotcha 35 rejects a port when the vendored payload has no
    upstream build for our arch *and no source to build*. When the payload is an ordinary
    open-source C/C++ library, the port is normal work: fetch its source at the version the
    project pins and drop the result where the download would have landed. Two properties of
    the downloader decide whether that needs a patch at all — both were true for ddtrace:
    - the per-arch loop **`continue`s** on an unrecognised platform
      (`if not get_platform().endswith(arch): continue`) rather than raising, so the build
      proceeds and only the *runtime* `ctypes.CDLL` fails; and
    - `download_artifacts()` **returns early when the target directory is already non-empty**,
      so pre-populating `<pkg>/.../libddwaf/<arch>/lib/libddwaf.so` from `CIBW_BEFORE_ALL`
      makes it a no-op. `package_data` globs the same path, so the library ships.
    Check the surrounding clean-up too: ddtrace's `build_py` calls `remove_artifacts()`
    (an `rmtree` of exactly that directory) unless its incremental flag is on — it defaults
    to on, but a workflow that turned it off would silently ship a wheel with no library.
    - **`-static-libstdc++` needs `libstdc++.a`, which the riscv64 manylinux image does not
      ship** — the link dies with `/usr/bin/ld: cannot find -lstdc++`. `dnf -y install
      libstdc++-static` (Rocky 10 CRB, already enabled) fixes it; add it beside the
      `dnf` lines gotcha 15 and 46 collect.
    - **Validate the library build alone under QEMU** (`docker run --platform linux/riscv64
      <image>`) before spending a runner cycle: libddwaf took ~50 min emulated and proved the
      cmake invocation, the ExternalProject downloads, the C++20 compile and the link — and
      caught the missing `libstdc++.a` in the *first* attempt.

98. **A prebuilt native dependency fetched from upstream's *own* sibling build repo is
    not gotcha 35's blocker — read that repo's release assets before triaging (the av
    case; see `build-av.yml`).** Gotchas 35/41 both end in a skip because the vendor
    artifact upstream bundles (a Node runtime, NVIDIA's ptxas) has no riscv64 build
    anywhere. The much commoner shape for a C-library binding looks identical from
    `setup.py` and is the opposite answer: upstream keeps a *second* repository whose
    only job is to compile the dependency for every wheel platform, and the wheel job
    fetches its release tarball in `before-build`. PyAV's `scripts/fetch-vendor.py`
    downloads `PyAV-Org/pyav-ffmpeg`'s `ffmpeg-{platform}.tar.gz`, where `{platform}`
    is derived from `platform.machine()` plus a glibc/musl prefix — and that project
    already publishes `ffmpeg-manylinux-riscv64.tar.gz`, so the whole port is upstream's
    workflow with the image override and nothing else.
    - **One API call settles it**, before any checkout:
      `gh api repos/<org>/<deps-repo>/releases/tags/<pin> -q '.assets[].name'`. The pin
      is in the config the fetch script reads (`scripts/ffmpeg-latest.json` →
      `.../releases/download/8.1.2-1/...`), and **must be read at the tag you are
      building** — the default branch had already moved to a newer FFmpeg release.
    - **Verify the artifact is really our arch, not a name that merely parses**:
      `tar -xzf` it and check `e_machine` in the ELF header is `0xf3` (EM_RISCV), then
      that its max `GLIBC_2.x` symbol version is within the manylinux image's glibc —
      `strings lib*.so | grep -o 'GLIBC_2\.[0-9]*' | sort -uV | tail -1`.
    - **The whole recipe validates natively on aarch64 in minutes** — the
      `quay.io/pypa/manylinux_2_39_aarch64` image is the same Rocky 10 family, so a
      `git clone --branch <tag>` + the same `fetch-vendor` + `pip wheel .` +
      `auditwheel repair` + upstream's test command exercises everything except the ISA.
      Far cheaper than QEMU and it settles the wheel *tag* the matrix must be named for
      (gotcha 34) before you push.
    - Distinct from gotcha 17: there the dependency is another *wheel* on our registry
      and needs `--only-binary=:all:` + an auditwheel `--exclude` list. Here it is a
      plain tarball of `.so`s that auditwheel is *supposed* to vendor into the wheel.

121. **An add-on wheel that must interoperate with another wheel we ship has to be built
    with the *same code generator version* that wheel was built with (the pymupdf-layout
    case; see `build-pymupdf-layout.yml`).** Gotcha 17 gets the dep wheel installed and its
    shared libraries excluded from the repair; gotcha 23 pins a floating build *tool* so it
    does not miscompile the source. This is the third form: two wheels compile fine
    separately and only fail when one passes an object to the other, because the wrapper
    generator emits a version-keyed type registry. pymupdf-layout's `tgif` extension takes a
    `mupdf::FzPage&` created by pymupdf, and building it with swig 4.4.1 against a pymupdf
    built with 4.3.1 yields `TypeError: in method 'fz_visual_table_grid_finder', argument 1
    of type 'mupdf::FzPage &'` at *runtime* - the build and the auditwheel repair are clean.
    - **The dep wheel usually records the version it used.** pymupdf ships
      `pymupdf/_build.py` with `swig_version = '4.4.1'`; read that (`unzip -p <dep>.whl
      '<pkg>/_build.py' | grep -i swig`) rather than inferring from upstream's CI, because
      *our* riscv64 wheel and upstream's PyPI wheel are frequently built with different ones
      - here PyPI's macOS wheel is 4.3.1 and ours is 4.4.1, since `build-pymupdf.yml` sets
      `PYMUPDF_SETUP_SWIG=swig` and takes the manylinux image's copy (manylinux pipx-installs
      `swig==4.4.1`, `docker/build_scripts/requirements-tools/swig`).
    - **Point the port at the same source**: setting `<PKG>_SETUP_SWIG=swig` also stops
      `get_requires_for_build_wheel()` adding the PyPI `swig` distribution to the build
      requirements, so there is exactly one swig in play and it is the image's.
    - **Reproduces on any host in one build cycle**, no QEMU: build the add-on against the
      PyPI dep wheel with the *wrong* generator, run the suite, then rebuild with the right
      one. The failure is a plain `TypeError`, so it is invisible to `unzip -l | grep '\.so$'`
      and to an `import` probe - only a test that actually crosses the boundary catches it.

143. **Static-with-PIC dependency inside a *shared* dependency: one bundled `.so`
    instead of dozens (the abseil/re2 case).** When a port has to build a C++ dependency
    that itself pulls a large modular library (abseil, boost, folly), the obvious
    `-DBUILD_SHARED_LIBS=ON` for both is a 20x size mistake: auditwheel vendors every
    transitive `.so`, and a modular library is *many* small ones — abseil contributed 40
    `libabsl_*.so` at 130–350 kB each, turning a 601 kB wheel into 14 MB, because each
    shared object carries its own ELF overhead. Build the inner library **static with PIC**
    (`-DCMAKE_POSITION_INDEPENDENT_CODE=ON`, no `BUILD_SHARED_LIBS`) and only the outer one
    shared: the archives are linked into that single `.so`, auditwheel bundles one file,
    and the result matches what upstream's own static link (Bazel, here) produces —
    601 kB against upstream's 590 kB. Add `auditwheel repair --strip` (gotcha 46) on top.
    - **This is the ordering fix too, not just a size fix.** The reason you cannot simply
      make *everything* static is gotcha 16's other half: `setup.py` typically hard-codes
      `libraries=['<outer>']` and offers no hook for the inner library's archives, and
      `LDFLAGS` lands in `LDSHARED` — *before* the objects — where GNU ld ignores it for
      resolving their symbols. Burying the archives inside the outer shared library sizes
      the wheel correctly *and* keeps the link line upstream wrote working unchanged.
    - **Measure before choosing**: two `auditwheel repair` runs and `unzip -l` settle it in
      one container session, on any arch.
    - **The licence obligation comes with it (refines gotchas 44/53).** Code linked in is
      redistributed: abseil is Apache-2.0 inside an otherwise-BSD wheel. When the
      dependency is fetched at build time there is no tree to patch, and no patch file is
      needed either — `before-all` already has the source unpacked, so
      `cp /tmp/<dep>/LICENSE {package}/LICENSE.<dep>` drops it at the project root where
      setuptools' default `LICEN[CS]E*` glob ships it into `dist-info/licenses/` beside the
      project's own. One line, no packaging change, nothing to rebase. Assert it from a
      post-build `zipfile.namelist()` check so it cannot silently stop happening.

159. **Bundling shared libraries next to a binary: `patchelf --set-rpath` writes
    **DT_RUNPATH**, and the loader does not search an object's RUNPATH for that object's
    *own* dependencies — every bundled library needs its own `$ORIGIN` (the semgrep case;
    see `build-semgrep.yml`).** The `ldd`-the-binary / copy-into `bin/libs/` /
    `patchelf --set-rpath '$ORIGIN/libs'` recipe is the standard way to make a wheel that
    ships a compiled executable self-contained, and it half works: the binary's *direct*
    `DT_NEEDED` entries resolve, so most libraries load. The first transitive one does not.
    semgrep-core links `libdw` but not `libelf`; `libdw`'s `NEEDED libelf.so.1` is looked
    up using **libdw's** search path (empty), never the executable's, and the wheel dies at
    startup with `error while loading shared libraries: libelf.so.1`. DT_RPATH *is*
    inherited, which is why the pre-2000s spelling appeared to work — but the fix is one
    more line, not `--force-rpath`:
    ```bash
    patchelf --set-rpath '$ORIGIN/libs' "$binary"
    patchelf --set-rpath '$ORIGIN'      "$libs"/*
    ```
    - **`ldd` is transitive, so the copy step is already complete** — the missing piece is
      only the second `patchelf`. That is what makes the failure so late and so confusing:
      the library is right there in the wheel.
    - **Check what upstream's own wheel does before inventing a scheme.** Read one bundled
      library's dynamic section out of upstream's published wheel for another arch — over
      HTTP range requests, no download (gotcha 41) — and the answer is explicit: semgrep's
      `libdw.so.1` carries `RUNPATH $ORIGIN`. auditwheel does the same thing for the `.so`s
      it vendors.
    - **Parsing `DT_NEEDED`/`DT_RUNPATH` is ~40 lines of `struct` over the ELF program
      headers**, which is worth having on a host with no `readelf`: it turns "which library
      is missing and why" into a fact before you spend another multi-hour cycle.
    - **A wheel that ships a prebuilt binary can be re-tested without rebuilding it.**
      Download the failed run's wheel artifact, unpack it in the build image under QEMU,
      apply the candidate `patchelf` there, and run the workflow's own test script against
      it — that validated this fix end to end (`semgrep --version`, `semgrep-core -version`
      and the e2e scan) in minutes against a 2.5-hour CI job.

160. **An architecture `select()` that supplies *source* files and ends in
    `//conditions:default: []` links a library with undefined symbols — the build stays
    green and the first `dlopen` is where it fails (the ray/boost.context case).** Gotcha
    71's vendored-SIMD gate at least dies loudly at configure; this one says nothing at
    all. rules_boost picks Boost.Context's stack-switching assembly — `jump_fcontext`,
    `make_fcontext`, `ontop_fcontext`, one hand-written file per (arch, ABI, object
    format) — with `BOOST_CTX_ASM_SOURCES`, which enumerates aarch64/arm/ppc64/x86_64/
    Apple/Windows and ends in `"//conditions:default": []`. On riscv64 `@boost//:context`
    is therefore compiled with **no** assembly, and because an ELF shared object may carry
    undefined symbols, `_raylet.so` linked, all three wheels built, and an 11-hour job
    failed at the very end on
    `OSError: .../ray/_raylet.so: undefined symbol: jump_fcontext`.
    - **The symbol name is the whole diagnosis.** Find which upstream file defines it and
      whether that project ships an arch variant: Boost has shipped
      `libs/context/src/asm/{jump,make,ontop}_riscv64_sysv_elf_gas.S` since 1.71.0 and ray
      pins 1.81.0, so the sources were already in the fetched archive and the fix was a
      `linux_riscv64` `config_setting` plus one select branch — no new code, and it lands
      through the project's existing patch list (ray already patches this same file).
    - **Audit every arch select in one pass — `dlopen` reports only the *first* unresolved
      symbol**, so fixing them one per cycle is the worst case on a build measured in
      hours. `grep -n 'linux_x86_64\|linux_aarch64' <build file>` and check each hit that
      supplies **`srcs`**; ones that only set `linkopts`/`defines` are harmless. rules_boost
      has exactly two, and only `BOOST_CTX_ASM_SOURCES` mattered — nothing in the graph
      depends on `:stacktrace` (`grep -n '":stacktrace"' BUILD.boost` returns nothing), so
      its identically-shaped empty default is dead. Confirm which targets are really linked
      with `grep -rhoE '@<dep>//:[a-z_0-9]+' --include=BUILD --include='*.bzl' .` over the
      project.
    - **Upload the wheel *before* the smoke test.** With `upload-artifact` after the test,
      a failing import leaves no artifact and the next debugging round costs another full
      build. Moving it ahead costs nothing — `publish` still gates on the whole job — and
      hands you the `.so` to run `ldd -r` against, which lists *all* unresolved symbols at
      once instead of the first. (Filter `Py`-prefixed ones: manylinux extensions resolve
      those from the interpreter at runtime.)
    - Settle that the arch's assembly actually builds before spending the cycle: `gcc -c`
      the three `.S` files in `rockylinux/rockylinux:10` under `--platform linux/riscv64`
      and `nm --defined-only` the objects.
    - **A patch that *adds* a file is erased by a `git clean -x` between interpreters.** A
      workflow that loops interpreters in one checkout wipes build outputs between them
      (ray: `git clean -f -f -x -d -e python/ray/dashboard/client`), and `git apply` leaves
      an added file **untracked** — so the new patch is deleted before bazel resolves its
      label, while the *modified* tracked files survive untouched. Nothing in the patch
      looks wrong; the build just fails on a missing target. Add it to the `-e` list beside
      whatever else is staged before the loop, and check with
      `git clean -n -f -f -x -d -e <existing> | grep <your file>` — a dry run costs nothing
      and the real thing costs the whole build.

206. **A C++ ML/inference engine that gates its fast BLAS backend (MKL/oneDNN) to x86
    usually already has a portable one wired in for the same reason aarch64 needs it —
    reach for that, not a from-source OpenBLAS build (the ctranslate2 case).**
    CTranslate2's CMakeLists exposes `WITH_MKL`/`WITH_DNNL`/`WITH_ACCELERATE`/
    `WITH_OPENBLAS`/`WITH_RUY`, and upstream's own aarch64 Linux CI already builds
    `-DWITH_MKL=OFF -DWITH_OPENBLAS=ON -DWITH_RUY=ON -DOPENMP_RUNTIME=COMP` — read the
    dependency's own backend-selection code (`src/cpu/backend.cc`'s `get_gemm_backend()`)
    before copying that whole recipe: Ruy alone already handles both `FLOAT32` and every
    `INT8*` compute type, so OpenBLAS is redundant on riscv64 and its own from-source
    build (a `make TARGET=ARMV8`-style dance, arch-specific to begin with) can be dropped
    entirely — set just `WITH_RUY=ON`.
    - **Ruy's own portability comes from a preprocessor platform check, not a config
      flag** (`ruy/platform.h`'s `RUY_PLATFORM_X86`/`RUY_PLATFORM_ARM` macros both read
      `0` on riscv64), so it silently takes the generic scalar path with no patch needed
      — the same shape as the parent project's own `CT2_BUILD_ARCH`/`CpuIsa::GENERIC`
      fallback when neither `CT2_X86_BUILD` nor `CT2_ARM64_BUILD` gets defined.
    - **Ruy's vendored `cpuinfo` (pytorch/cpuinfo) submodule degrades to a harmless
      warning on an unrecognized `CMAKE_SYSTEM_PROCESSOR`, not a fatal error** — even a
      pre-riscv64-support pin (CTranslate2 4.8.1 pins a 2023 commit with no riscv64
      branch at all) just sets `CPUINFO_SUPPORTED_PLATFORM FALSE` and makes
      `cpuinfo_initialize()` a permanent no-op; nothing on Ruy's call path requires it to
      succeed on this arch. Read the dependency's actual `CMakeLists.txt` at the pinned
      commit (`git show <sha>:CMakeLists.txt`) before assuming an old pin blocks the
      build outright.
    - **A backend swap (OpenBLAS+Ruy on the real aarch64 wheel vs. Ruy-only here) can
      surface as a single test failure with a byte-for-byte different result, not a
      crash** — an int8-quantized wav2vec2 transcription test came back one character
      off under Ruy-only int8 GEMM. Same divergence class as gotcha 170, now confirmed in
      ML inference / quantization rather than linear algebra: deselect the specific test
      with a one-line reason, don't chase the difference as a bug.

220. **BLST (Ethereum's vendored elliptic-curve library, pulled in by ckzg/c-kzg-4844
    and likely other Ethereum-crypto ports) auto-detects an unsupported arch at build
    time and falls back to real portable C — no patch, no `CIBW_ENVIRONMENT` flag
    needed.** Same shape as gotcha 206's Ruy fallback, different mechanism: blst's
    `build.sh` greps the compiler's predefined macros
    (`echo ${predefs} | grep -E -q 'x86_64|aarch64'`) and appends `-D__BLST_NO_ASM__`
    for anything else, riscv64 included. That macro (checked in `src/vect.h`) swaps
    every hand-written assembly primitive for a plain-C equivalent, and
    `build/assembly.S`'s own arch dispatch (`#elif defined(__BLST_NO_ASM__) || ...`)
    compiles to nothing on riscv64 — so the object file that lands in `libblst.a`
    carries zero unresolved arch-specific symbols, unlike gotcha 160's Boost.Context
    case where an empty `select()` branch links clean and only fails at `dlopen`.
    Confirmed by building the real 2.1.8 sdist locally (`make -C src blst`) and reading
    the `-D__BLST_NO_ASM__`-gated code paths; no riscv64-specific configuration was
    needed in `build-ckzg.yml` beyond mirroring upstream's own
    `CIBW_BEFORE_BUILD_LINUX: make -C src blst`.

231. **A vendored C library's own CMake can carry a genuine, tested riscv64 branch — and a
    bundled JIT compiler can have a real riscv64 code-generation backend, not just a scalar
    bailout (the blosc2/miniexpr/minicc case).** Gotcha 220 shows BLST detecting an
    unsupported arch and silently degrading to portable C. c-blosc2 (fetched by
    `python-blosc2`'s CMake via `FetchContent`) does the equivalent explicitly: its
    `CMakeLists.txt` has `elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "^(riscv32|riscv64|riscv)")`
    setting every `COMPILER_SUPPORT_{SSE2,AVX2,AVX512,NEON,ALTIVEC}` flag `FALSE` with a
    `message(STATUS ...)` explaining the generic path will be used — no patch needed, and
    grepping for that `elseif` chain before assuming a SIMD-heavy C library is a port
    blocker settles it in seconds. The sharper finding is one level deeper: python-blosc2
    also bundles `miniexpr`, whose optional expression JIT is a fork of tinycc
    (`Blosc/minicc`) — and minicc ships real riscv64 backend files
    (`riscv64-asm.c`/`riscv64-gen.c`/`riscv64-link.c`/`riscv64-tok.h`), so its own
    `MiniexprOptions.cmake` allow-lists `riscv64` alongside `x86_64|aarch64|arm|i386` as a
    "native backend available" architecture and *builds the JIT*, rather than falling back
    to interpretation. Don't assume a JIT is x86/arm-only — `ls`/`grep` the compiler's
    source tree for an arch-named backend file before writing off a JIT feature as
    unavailable on riscv64. (The library's *other* SIMD math — SLEEF-accelerated
    transcendentals — does take the fallback path: `functions-simd.c` gates the
    vectorized code with `#if defined(__x86_64__) ... #elif defined(__aarch64__)` and
    falls through to a plain `libm`-calling scalar implementation for every other arch,
    confirmed by reading the file rather than assuming.)

363. **A `libraries=[...]` entry can go missing from the link line with *no* error —
    check whether `setup.py` builds `library_dirs` from an environment variable that is
    merely *present*, not necessarily non-empty (the python-fcl case).** A `setup.py`
    helper doing `if "LD_LIBRARY_PATH" in os.environ: lib_dirs +=
    os.environ["LD_LIBRARY_PATH"].split(":")` looks like a no-op when the variable is
    unset, but our manylinux images (and some cibuildwheel container setups) export
    `LD_LIBRARY_PATH=""` — present, empty. `"".split(":")` returns `['']`, so an empty
    string lands in `library_dirs`, and distutils turns *every* dir into its own `-L<dir>`
    token — including a bare `-L` with nothing after it. GNU ld/gcc then parse that bare
    `-L` as taking the *next* argv as its path, silently swallowing the following `-l<dep>`
    as a (nonsensical) search-directory name instead of a link request. The dependency
    that happens to sit right after the empty dir in `libraries=[...]` vanishes from the
    link with **zero warnings or errors** — the build succeeds, the `.so` loads (its other
    deps still resolve), and the failure only surfaces later as `undefined symbol` for
    whatever the missing library alone provided (`typeinfo for fcl::CollisionGeometry<double>`
    here, since everything else in FCL is header-only/inline and needed no external
    symbol). A later `-l` in the same list is unaffected, producing a confusing asymmetry
    where sibling libraries (`octomap`) link and vendor fine while the first one (`fcl`)
    does not.
    - **Diagnose from the actual `-o *.so` link command, not from cibuildwheel's output.**
      `auditwheel repair`'s log (no "Grafting"/copying lines for the missing lib) and
      `readelf -d <ext>.so | grep NEEDED` (the dependency absent entirely, not just
      unvendored) are the tell; the definitive proof is the printed compiler invocation
      itself — grep the build log for ` -o build/lib*/**/*.so` and read the `-L`/`-l`
      sequence left to right for a bare `-L` with no path token before the next `-l`.
    - **`-Wl,--no-as-needed` does not fix this and is a useful negative test.** `--as-needed`
      only drops a `-l` that *was* parsed but resolved nothing; here the `-l` was never
      parsed as a `-l` at all (it was consumed as `-L`'s argument), so forcing
      `--no-as-needed` on has no effect — confirming the bug is upstream of linker
      behavior, in argument construction.
    - **Fix upstream's helper to treat empty as unset**: `os.environ.get("VAR", "")` plus
      an `if value:` truthiness check (not `"VAR" in os.environ`), and filter empty
      elements out of the `.split(":")` result in case of a trailing/doubled separator too.

368. **Linking several codecs against Rocky 10's system libraries instead of
    vendoring surfaces API-version-skew failures one library at a time, not all at
    once — each looks like an isolated compile bug until you've hit the pattern (the
    imagecodecs case; see `build-imagecodecs.yml`).** A build that links against a
    dozen distro `-devel` packages compiles most extensions cleanly and then dies on
    one specific codec calling an API newer than the packaged library version: a
    struct field and macro missing entirely (`WavpackConfig.worker_threads`,
    `OPEN_THREADS_SHFT` — Rocky 10 ships WavPack 5.6.0, that field landed later) or a
    whole function undeclared (`png_set_cICP` — added in libpng 1.6.45, Rocky 10 ships
    1.6.40). Fixing that one (drop the codec, or patch out the call) just uncovers the
    next one a build minute later; treat this as an expected multi-round pattern for
    any project whose Cython/C layer tracks upstream libraries aggressively, not as a
    sign the port needs a fundamentally different approach.
    - **A container-format library can also lack a whole *codec inside itself*, not
      just a newer function — check its RPM `Requires:` for the codec's own shared
      library, not just its own version number.** Rocky 10's `libtiff` (4.6.0) links
      `libLerc`/`libjpeg`/`libwebp`/`libz`/`libzstd` but no `liblzma`, meaning it was
      built with LZMA support compiled out entirely; any TIFF-container operation
      needing that pseudo-tag fails with `TiffError: Unknown pseudo-tag <N>` even
      though the project's own *standalone* LZMA codec (linked directly against
      `liblzma`, unrelated to libtiff) works fine. `rpm -q --requires <pkg>` (or the
      primary/filelists repodata gotcha 369 describes) is the fast way to confirm which
      codecs a distro's container-format library was actually built with, before
      chasing the pseudo-tag error as if it were a bug in the wrapper code.
    - **Settle "is this a real version wall" against the library's own changelog, not
      by guessing from the error text.** `implicit declaration of function
      'png_set_cICP'` reads like it could be a header/macro-guard issue fixable with a
      compiler flag; libpng's own `CHANGES` file (`grep -n cICP CHANGES` against the
      tagged release) gives the exact version the symbol was added in, and confirms
      Rocky 10's 1.6.40 predates it — a real wall, not a flag away.

395. **When a project dlopen()s a differently-named shared library per major version of
    a native dependency, the version you build against is not an implementation detail —
    it is an ABI contract with whatever the *user's* machine has installed (the torchcodec
    case).** torchcodec compiles `libtorchcodec_core<N>.so` where `N` is the FFmpeg major
    version, and at import time tries `N` = 9, 8, 7, 6, 5, 4 in turn, using the first that
    loads; upstream ships all six in one wheel by linking against prebuilt non-GPL FFmpeg
    tarballs it hosts on S3. Those tarballs have no riscv64 build, so the riscv64 wheel
    goes down the project's other path — `pkg-config` against one installed FFmpeg — and
    therefore carries exactly one `N`. That makes the FFmpeg version a **user-visible**
    choice: build against 7.x and the wheel imports on nothing that ships FFmpeg 6.
    - **Pick the major version of the platform the wheels are consumed on**, not the
      newest release: `ubuntu-24.04-riscv` (the runner these wheels target) ships FFmpeg
      6.1, so a 6.1.x source build is what makes `apt install ffmpeg` enough for a user.
      The mapping is from the *library* soname, not the FFmpeg release number — FFmpeg 6
      is `libavcodec.so.60`/`libavutil.so.58`, and it is the `libavcodec` major that the
      project's CMake switches on.
    - **Build it LGPL and do not ship it.** No `--enable-gpl`/`--enable-nonfree` and no
      third-party codec integrations keeps the FFmpeg build itself LGPL, and excluding
      `libav*`/`libsw*`/`libpostproc*` from `auditwheel repair` keeps it out of the wheel
      entirely — which is also what upstream's own `packaging/repair_wheel.py` enforces,
      since FFmpeg is a runtime dependency the user supplies.
    - **Assert the resulting `.so` name in a post-build step.** `libtorchcodec_core6.so`
      present in the wheel is the one-line proof that the FFmpeg the container built is
      the FFmpeg that got linked; a silent fallback to a different major would otherwise
      only surface as an ImportError on a user's machine.

400. **A `setup.py` env-var knob that feeds a downloaded dependency's *sources* into
    `Extension(sources=...)` needs a path **relative to the project root** — distutils
    hard-errors on an absolute one, so the tarball has to be extracted inside the
    checkout, not into `/tmp` (the cvxopt/SuiteSparse case).** Gotcha 53's shape is a
    `before-all` that curls a dependency tarball, builds it and links the resulting
    library; the variant here compiles the dependency's own `.c` files straight into the
    extension instead, through a knob like cvxopt's `CVXOPT_SUITESPARSE_SRC_DIR` (its
    `setup.py` globs `<dir>/AMD/Source/*.c`, `<dir>/CHOLMOD/Core/c*.c`, … into
    `sources=`). Extracting to `/tmp` and pointing the knob there — the obvious choice,
    since it keeps the checkout clean — dies at `build_wheel` with `error: Error: setup
    script specifies an absolute path: /tmp/<dep>/… setup() arguments must *always* be
    /-separated paths relative to the setup.py directory, *never* absolute paths`. That
    check is distutils' own and the project cannot opt out of it, so the fix is
    `tar xzf /tmp/<dep>.tar.gz -C {project}` plus the bare directory name as the value.
    - **The knob's own upstream usage is the tell, and it differs per knob kind**: the
      same `setup.py` takes absolute values happily for every `*_LIB_DIR`/`*_INC_DIR`
      (they only ever reach `library_dirs`/`include_dirs`), and upstream's own CI writes
      the *source* one relative (`CVXOPT_SUITESPARSE_SRC_DIR=SuiteSparse-${VERSION}`
      after untarring into the checkout). Sources are the restricted argument; search
      paths are not.
    - **An untracked dependency tree inside the checkout does not poison a
      `setuptools_scm` version.** Gotcha 31's hazard is *modified tracked* files;
      `git describe --dirty` ignores untracked paths, so a 31 MB `SuiteSparse-7.11.0/`
      plus three staged `LICENSE.<dep>` files at the checkout root still produced a plain
      `1.3.3` wheel, with no `SETUPTOOLS_SCM_PRETEND_VERSION` needed.

415. **Turning an optional native codec/feature OFF can select a disabled-path stub whose
    signature has drifted out of sync with its declaration — the shared object links
    anyway, and the first `dlopen` is where it dies (the torchcodec `decode_avif` case).**
    torchcodec 0.16.0 needs `TORCHCODEC_BUILD_AVIF=0` on riscv64 (libavif comes only from
    upstream's S3 bucket, which has no riscv64 build, and is packaged in neither Rocky 10
    nor a riscv64 EPEL). That selects `DecodeAvif.cpp`'s `#if !TORCHCODEC_ENABLE_AVIF`
    branch — a stub that raises an actionable "not compiled with libavif support" error.
    Except the stub still had the *three*-parameter signature from before `num_threads`
    was added, while `DecodeAvif.h`, the real implementation and the op registration
    (`m.impl("decode_avif", TORCH_BOX(&decode_avif))`) all use four. The stub therefore
    defined a different overload and the four-parameter one existed nowhere. Because an
    ELF shared object may carry undefined symbols, `libtorchcodec_image.so` linked, the
    wheel built, `auditwheel repair` was happy, and all four jobs failed ~50 minutes in at
    the test step with `OSError: ... undefined symbol:
    _ZN8facebook10torchcodec11decode_avifERKN5torch6stable6TensorElll`. Same mechanism as
    gotcha 160, different trigger: there an arch `select()` supplied no sources, here a
    feature flag supplied the wrong stub.
    - **Whenever you flip a `*_BUILD_<FEATURE>=0` knob, diff the disabled stub against the
      declaration before you push.** `grep -rn '#if !.*_ENABLE_' <src>` lists every
      such branch; for each, compare the stub's parameter list with the header's and with
      whatever takes the function's *address* (an op/dispatch registration table is the
      usual caller — taking `&f` needs an exact-signature definition, whereas a plain
      call would have failed at compile time). A project whose own CI always builds the
      feature ON never compiles that branch, so the drift is invisible upstream and the
      fix is a real upstream bug report, not a riscv64 workaround.
    - **`ldd -r` over every `.so` in the built wheel enumerates *all* unresolved symbols
      in one pass; `dlopen` reports only the first.** Run it in the manylinux image with
      the dependency's library directory on `LD_LIBRARY_PATH` (`<venv>/.../torch/lib` for
      a libtorch extension, plus the wheel's own `<pkg>.libs/`), and ignore the `Py*` and
      `_Py*` lines — those are resolved from the statically linked interpreter at run time
      and are expected on manylinux. Anything else is a real dangling reference. That
      turned "is there a second bug hiding behind this one?" into a fact for five
      libraries at once, instead of one more multi-hour CI cycle per symbol.

461. **A dependency wheel *shipping* a library is not a promise that the library exports the
    symbol a build gates on — turn a presence-of-file probe into a presence-of-symbol probe
    (the vllm/OpenBLAS `sbgemm_` case).** vLLM's `cmake/cpu_extension.cmake` decides whether
    to compile its OpenBLAS bf16 GEMM path with
    `file(GLOB ... "${TORCH_INSTALL_PREFIX}/lib/libopenblas*.so*")` and defines
    `VLLM_HAS_OPENBLAS` if the glob hits. Our riscv64 `torch==2.13.0+cpu` wheel does ship
    `torch/lib/libopenblas.so.0`, so the glob hits — but that OpenBLAS is built **without
    `BUILD_BFLOAT16`**, which OpenBLAS only enables for the targets it has bf16 kernels for
    (x86_64 Cooper Lake and later, ARM64 Neoverse, POWER10, z14 and later). RISC-V is not one
    of them: `nm -D --defined-only libopenblas.so.0` finds `sgemm_` and **no `sbgemm_`, and
    zero bf16 symbols at all**. The build still succeeded; `import vllm._C` then failed with
    `undefined symbol: sbgemm_` after a 75-minute job.
    - **The reason it reaches import rather than link is worth internalizing.** The same file
      comments "we don't link openblas directly to _C extension, as it's available through
      libtorch.so" — a deliberate choice, since torch loads it `RTLD_GLOBAL`. A shared object
      with an unresolved symbol and no library to resolve it against **links without
      complaint**; only `dlopen` reports it. So this class of bug is invisible to the build log
      and to `auditwheel`, and is caught only by actually importing the extension — which is
      why gotcha 6's "wire up real testing" earns its keep even when the test is one `import`.
    - **Check what the dependency wheel actually exports, on the host, before theorising.**
      `nm` reads foreign-arch ELF perfectly well, so download the riscv64 wheel, extract the
      library and query it — no QEMU, no container, about a minute. The wheel's `torch/lib/`
      also reveals the transitive companions (`libgfortran.so.5`, `libgomp.so.1`) that decide
      whether a *link*-based probe would even work.
    - **Prefer the arch-agnostic probe to an arch exclusion** when the upstream code already has
      a fallback. Here `blas_gemm.h`'s `#else` branch dispatches through
      `at::native::cpublas::gemm_no_downcast_stub`, which `libtorch_cpu.so` does export
      (verify: `nm -D --defined-only libtorch_cpu.so | grep gemm_no_downcast_stub`), so the fix
      is to probe with `execute_process(COMMAND ${CMAKE_NM} --dynamic --defined-only <lib>)` and
      only define the macro when the symbol is there. `if (SYMS STREQUAL "" OR SYMS MATCHES
      "[ \t]sbgemm_[\r\n]")` keeps the old behaviour whenever the probe itself cannot run, so
      no working platform regresses — which is what makes it `To upstream` rather than a
      riscv64-only exclusion.
    - **`check_library_exists()` is the tempting CMake idiom and the wrong one here**: it links
      the library, so it drags in `libgfortran`/`libgomp` from the same wheel directory and
      fails for *link-environment* reasons on platforms where the symbol does exist — silently
      turning the fast path off everywhere. The `nm` probe cannot fail that way.
    - **Validate the CMake logic locally in seconds, on any arch.** Point a four-line throwaway
      `CMakeLists.txt` at the extracted riscv64 `libopenblas.so.0` and print the decision, then
      re-run it against two synthetic `.so` files built with `gcc -shared` — one exporting
      `sbgemm_`, one exporting only `dsbgemm_`/`sbgemm_direct` — to prove both the positive case
      and the absence of a substring false positive. That is the whole patch under test without
      a riscv64 cycle.

463. **Swapping our dep wheel in for an upstream prebuilt can change the SONAME, and that breaks
    a package whose own linker-flag emitter says `-l<name>`: re-soname the staged copy rather
    than shipping a symlink farm (the sherpa-onnx-core/onnxruntime case).** Gotcha 17's
    dep-wheel pattern usually ends at "point the build's `*_LIB_DIR` at the extracted wheel".
    The extra step appears when the wheel we ship is *versioned* and the binary upstream vendors
    is not. Our `onnxruntime` riscv64 wheel carries `libonnxruntime.so.1.29.0` with
    `SONAME libonnxruntime.so.1`; upstream sherpa-onnx vendors a plain `libonnxruntime.so` with
    **no SONAME at all**. Three consequences follow from that one difference:
    - **The consumer's own flags decide the required filename, not the build.** The `-core`
      wheel ships `sherpa_onnx/_info.py`, which emits `-L<libdir> -lsherpa-onnx-c-api
      -lonnxruntime`, so a user's `g++` needs a file literally named `libonnxruntime.so` in the
      wheel. Grep the package for the code that *prints* link flags (`--libs`, a `.pc` template,
      an `_info.py`) before choosing what to stage — the build succeeding proves nothing about
      whether the shipped wheel is linkable.
    - **Symlinks are not an option inside a wheel.** The zip format can carry them but installers
      generally materialise them as regular files, so the honest alternatives are one real copy
      or N real copies. Keeping the versioned name plus two compatibility names tripled a 19 MB
      library (that is exactly why the sibling `sherpa-onnx` riscv64 wheel carries
      `libonnxruntime.so`, `.so.1` and `.so.1.29.0` at 19.4 MB each).
    - **So copy once under the linker name and fix the SONAME**: `cp
      libonnxruntime.so.<ver> <dir>/libonnxruntime.so` then `patchelf --set-soname
      libonnxruntime.so <dir>/libonnxruntime.so`, before configuring. `DT_NEEDED` follows the
      SONAME, not the filename, so this is what makes the dependents record the short name; it
      also narrows the project's own `file(GLOB … libonnxruntime*)` install rule to one file, so
      a plain `cp install/lib/lib*.so` yields upstream's exact wheel content. Do it to the
      *staged copy*, never in place in a shared location.
    - **Rehearse it off-target with `--replace-needed`.** You cannot relink the dependents
      without the real build, but you can reproduce the finished relationship exactly:
      `patchelf --set-soname` the library, then `patchelf --replace-needed
      lib<name>.so.<N> lib<name>.so` on **every** dependent (missing one leaves a dangling
      `.so.1` that only shows up as an `ld` warning and a runtime loader failure), package it and
      compile an example against the installed wheel under QEMU. That caught the omitted second
      library in one minute instead of a two-hour CI cycle.

486. **Legacy TBB 2020.x — the hand-written makefile build, not oneTBB's CMake one — needs no
    riscv64 patch, so do not switch a project to `--onetbb` on suspicion (the usd-core/OpenUSD
    case; see `build-usd-core.yml`).** A project pinned to `oneTBB` tag `v2020.3.x` looks like a
    guaranteed deviation: that tree predates RISC-V, has per-arch `machine/*.h` atomics headers,
    and its `build/linux.inc` arch table lists only i686/ia64/x86_64/sparc64/armv7. It builds
    anyway, for three separate reasons, each of which is the one you would expect to break:
    - `build/linux.inc` ends its table with `export arch := $(uname_m)`, so `arch` becomes the
      literal `riscv64` rather than failing.
    - the export-list prefix is chosen by `ifeq (64,$(findstring 64,$(arch)))` → `def_prefix =
      lin64`, so `src/tbb/lin64-tbb-export.def` is found by substring match, not by an arch
      allowlist.
    - `include/tbb/tbb_machine.h` falls through its per-arch `#elif`s to
      `#elif __TBB_GCC_BUILTIN_ATOMICS_PRESENT → machine/gcc_generic.h`, which any GCC ≥ 4.7
      satisfies. There is no `#error` for an unmatched platform.
    `make -j4` in `quay.io/pypa/manylinux_2_39_riscv64` under QEMU exits 0 and links
    `libtbb.so.2` from `build/linux_riscv64_gcc_cc14.3.1_.../`, with only C++20
    `-Wtemplate-id-cdtor` warnings from `atomic.h`.
    - **The general point: a per-arch build system that degrades by substring/uname fallback is
      not the same as one that degrades by allowlist** (contrast gotcha 294, where casadi's
      `-fPIC` block names only x86_64/aarch64 and riscv64 silently gets nothing). Find the
      fallback branch before deciding, and prove it with the cheapest possible build — TBB 2020
      is ~6 minutes under QEMU, against a multi-hour cycle for the project that consumes it.
    - **Sticking with upstream's default keeps the workflow a clean precedent.** Passing
      `--onetbb` "to be safe" would have been an unexplainable divergence in a file meant to be
      handed to upstream, and it changes the library the wheel vendors (`libtbb.so.2` vs
      oneTBB's) for no gain.

547. **A vendored BoringSSL produced by `generate_build_files.py` needs no `OPENSSL_NO_ASM` on
     an architecture it does not list — the generated assembly is self-guarded, and the C
     fallbacks are selected by the same macros (the couchbase case).** The generated
     `CMakeLists.txt` puts *every* platform's assembly in one `CRYPTO_SOURCES_ASM` list
     (`linux-x86_64/`, `linux-aarch64/`, `apple-*`, `win-*`) and appends the whole list whenever
     `OPENSSL_ASM` is on, which reads like a hard x86/ARM dependency. It is not: each generated
     `.S` opens with `#if !defined(OPENSSL_NO_ASM) && defined(OPENSSL_X86_64) && defined(__ELF__)`
     (or the `OPENSSL_AARCH64` equivalent), so on riscv64 they preprocess to empty objects, and
     `crypto/` picks its portable C paths off the same `OPENSSL_<ARCH>` macros. Forcing
     `OPENSSL_NO_ASM` would be a needless divergence.
     - **The one-line check is `src/include/openssl/target.h`**: a revision that maps
       `defined(__riscv) && __SIZEOF_POINTER__ == 8` to `OPENSSL_RISCV64` knows the architecture
       at all. Absent that macro, nothing selects a fallback and the port is a real question.
     - **Confirm from the built wheel, not the configure log.** couchbase's C++ core exposes its
       TLS backend through `couchbase.get_metadata()['openssl_runtime']`; asserting `BoringSSL`
       there in the test command proves the static library is genuinely linked in rather than
       the build having quietly fallen back to the image's OpenSSL.

550. **When the downloader's unknown-platform branch is a graceful PATH search rather than
     a hard failure, gotcha 77's patch is unnecessary — just put the self-built binary there
     (the shfmt-py case).** shfmt-py vendors mvdan/sh's `shfmt` Go binary: `setup.py`'s
     `fetch_binaries` command looks up `(sys.platform, platform.machine())` in a hardcoded
     `POSTFIX_SHA256` table and downloads the matching GitHub release asset. riscv64 isn't a
     key — mvdan/sh's own release process publishes no `linux_riscv64` asset for any version —
     but unlike gotcha 77's ddtrace case (a `continue`/early-return that needs patching to
     reach), the `KeyError` here is already caught by a `fall_back_to_path_shfmt()` the project
     ships for its *own* unsupported platforms (FreeBSD, illumos): it `shutil.which("shfmt")`s
     and copies whatever it finds. Building `shfmt` from source with the Go toolchain
     (`CGO_ENABLED=0 GOOS=linux GOARCH=riscv64 go build ./cmd/shfmt` — Go's cross-compilation
     needs no riscv64 host) and copying the result to `/usr/local/bin/shfmt` in
     `CIBW_BEFORE_BUILD` exercises that existing fallback with **zero patches to setup.py**,
     unlike s5cmd's sibling case (`patches/s5cmd/`) where the downloader had no such escape
     hatch.
     - **Read the `except`/fallback branch before reaching for a patch.** A downloader that
       raises immediately on an unknown platform needs gotcha 77's treatment; one that already
       degrades to a PATH search, a bundled system package, or a "build it yourself" branch
       needs only a workflow step to satisfy that branch — check for this before patching.
     - **This also means the port needs no maintenance once upstream ships riscv64**: the
       instant `POSTFIX_SHA256` gets a real `("linux", "riscv64")` entry, `fetch_binaries` stops
       raising and downloads it instead — nothing here to revert (goal 3 for free).
     - **The version string still comes out right with no `-ldflags` stamping**, unlike
       s5cmd's `peak/s5cmd` (which needs an explicit `-X .../version.Version=` because it has
       no VCS stamping): `mvdan.cc/sh`'s `cmd/shfmt` reads
       `debug.ReadBuildInfo().Main.Version`, and Go's automatic VCS stamping fills that in
       correctly from a plain `actions/checkout` at the tag even with the default
       `fetch-depth: 1` — verified locally against a shallow clone.

554. **A Go-binary-in-a-wheel tool (not a downloader) can also lack riscv64 in its own
     platform table — drive its Python API directly instead of patching it (the mcp-grafana
     case).** Gotcha 550 is a project's own downloader missing a riscv64 entry; mcp-grafana
     puts the same gap one layer further out. Its PyPI wheels aren't built by setuptools or
     cibuildwheel at all — upstream's `release.yml` calls a third-party tool,
     [go-to-wheel](https://github.com/nikaro/go-to-wheel), pinned to one commit, which
     cross-compiles `./cmd/mcp-grafana` per platform (`CGO_ENABLED=0`, Go's own
     cross-compilation) and hand-writes the wheel zip. Its `PLATFORM_MAPPINGS` dict — the
     table of `"linux-amd64"`-style keys to `(goos, goarch, wheel-platform-tag)` triples —
     has no riscv64 key, and its CLI silently `continue`s past any platform string that isn't
     already a key, so passing `--platforms linux-riscv64` on the command line does nothing.
     - **The tool is a plain importable module, not a black box.** Since a port only adds
       files under `.github/workflows/` and `docs/packages/`, patching go-to-wheel itself
       would need a `patches/` entry for a *dependency of the build*, not of the package being
       ported — out of scope. Importing it and mutating the module-level dict before calling
       its own `build_wheels()` function needs no patch at all: `import go_to_wheel as gtw;
       gtw.PLATFORM_MAPPINGS["linux-riscv64"] = ("linux", "riscv64",
       "manylinux_2_39_riscv64")`, then call `gtw.build_wheels(..., platforms=["linux-riscv64"])`
       with the same `name`/`version`/`package_path`/`description`/`url`/`license_`/`readme`
       upstream's own CLI invocation passes — this is "drive the tool yourself", the same
       move workflow-anatomy.md documents for cibuildwheel-shaped builds, applied to a
       different build tool.
     - **The tool's wheels ship no LICENSE at all**, on any platform — `go_to_wheel.build_wheel`
       never writes a `dist-info/licenses/` entry regardless of the `--license` string passed
       (that string only reaches the `License-Expression` METADATA header). This repo requires
       every wheel it publishes to carry upstream's licence file, so the gap needs a second,
       independent fix even once riscv64 itself builds: read the built wheel back, add
       `<dist-info>/licenses/LICENSE`, and regenerate `RECORD` (`gtw.generate_record()` is
       already exported and does the hashing) before uploading — a few lines of `zipfile`
       in the same `run:` step, no new files.
