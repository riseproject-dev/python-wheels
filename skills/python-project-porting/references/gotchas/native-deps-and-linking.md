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
