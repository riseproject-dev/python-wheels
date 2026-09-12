# Gotchas — Feasibility & triage

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/feasibility-and-triage.md`.

## In this file

- **24** — Feasibility triage: some "binary-looking" packages never compile anything —
- **27** — `py3-none-<platform>` is a hand-set `--plat-name`, never compiled content (the
- **35** — A `py3-none-<platform>` wheel whose platform tag is real: a downloaded prebuilt
- **40** — A port can be blocked by a *dependency* that is conda-produced, even when the
- **41** — Compiling a huge amount of real code does not make a package portable — check
- **42** — Settling "is this arch conda-blocked?" — ask the channel's subdir, and count
- **50** — A distribution that ships no Linux wheel on *any* arch has no riscv64 gap to
- **79** — A `<pkg>-headless`/`-gpu`/`-lite` sibling is usually the same upstream tree behind one
- **81** — A `py3-none-<platform>` wheel can hold a real compiled library — gotcha 27's stop
- **114** — tree-sitter grammar packages are a family with one shape — and one free-threading
- **116** — cffi `set_source(<name>, None)` is ABI mode — the project compiles nothing on
- **126** — Gotcha 50 without the sibling: a project that is source-only on Linux *by design*,
- **145** — A `py3-none-<platform>` wheel can also be a *compiled-from-source* binary —
- **150** — Before writing any YAML, check whether a sibling package from the same upstream
- **157** — A closed-source vendored runtime has no source to fall back on — and its platform
- **185** — A sibling distribution can be selected by an upstream *source-transform script*
- **186** — A sibling package's riscv64 vendor doesn't transfer if it publishes a different
- **230** — "CMake" isn't always a hand-maintained build — a project's own CMakeLists can be a
- **236** — An "LLVM-based" port is not automatically libclang-scale — check which CMake target
- **246** — A `pyO3`/uniffi "binding" package can vendor a closed-source Rust core as a git-committed
- **248** — An "inactive"/deprecated package's own PyPI ceiling can be a real ABI wall, not
- **273** — A pinned transitive crate can lack riscv64 support outright, and `cargo check
- **276** — A hand-written-SIMD C library that looks x86/aarch64-only can still have a
- **284** — A package whose C/C++ extension calls CUDA/HIP/cuFile is not automatically
- **303** — A "Python 2 only" classifier is a stop sign the project's own `setup.py` may
- **311** — A transitive crate's `compile_error!` gated on `target_feature` (not
- **318** — An explicit `python_requires` *upper* bound is a harder wall than an
- **334** — A stdlib-absorbed backport can fail to build on a modern interpreter for a
- **335** — Gotcha 273 generalizes: a pinned embedded-engine crate (deno_core/rusty_v8)
- **338** — A package whose real PyPI wheels are produced by a *packaging fork*, not its own
  source repo, can hard-depend at runtime on a sibling package from that same packaging
  ecosystem — and that sibling can itself be the actual blocker (the eigenpy/cmeel-boost case).
- **341** — A build-time transpiler binary from a *third* language ecosystem can block a port
  even when the extension itself is pure, portable C++ (the prophet/cmdstanpy/stanc3 case).
- **340** — Gotcha 335 generalizes past deno_core/rusty_v8 to a second embedded-engine family:
  a Rust FFI crate that itself only *downloads* a prebuilt native core, never builds it, can
  leave riscv64 with no build path at all even though the wrapper crate is pure Rust (the
  livekit case).
- **343** — A Bazel-built package can clear every dependency-tree check (gotcha 132/214) and
  still be blocked because its `WORKSPACE` links the extension directly against a *live,
  pip-installed* sibling package's compiled library, not just its headers (the
  tensorflow-io-gcs-filesystem case).

---

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

50. **A distribution that ships no Linux wheel on *any* arch has no riscv64 gap to
    close — and its binary sibling may already be done (the psycopg2 case).** Gotchas
    24/27/35/41 triage packages by what the wheel *contains*; this one is settled purely
    by what upstream *publishes*, in one PyPI JSON read, before any checkout.
    `psycopg2` compiles a real C extension against libpq, so every content-based check
    says "port it" — but PyPI's file list for 2.9.12 (and 2.9.9–2.9.11) is a `.tar.gz`
    plus six `win_amd64` wheels and nothing else. Upstream deliberately splits the
    project: `packages.yml`'s Linux and macOS wheel jobs hardcode
    `CIBW_ENVIRONMENT: PACKAGE_NAME=psycopg2-binary`, so the prebuilt-libpq wheels ship
    under the **sibling name** while `psycopg2` stays source-only (the split exists so a
    process linking another libpq doesn't end up with two copies). riscv64 users are
    therefore in exactly the same position as x86_64 users, and a `manylinux_riscv64`
    wheel named `psycopg2` would be psycopg2-binary's content under the name upstream
    reserves for system-libpq source builds — auditwheel vendors libpq in regardless.
    Divergence with no gap closed.
    - **Check the sibling distribution before the source repo.** The naming convention is
      well known (`<pkg>` / `<pkg>-binary`, `<pkg>` / `<pkg>-bin`, `uwsgi` / `pyuwsgi`):
      read the `PACKAGE_NAME`-style env key in upstream's wheel job to learn which name
      the wheels are published under, then re-run the coverage check against *that* name.
      psycopg2-binary 2.9.12 already ships `manylinux_2_38_riscv64` **and**
      `musllinux_1_2_riscv64` for cp39–cp314.
    - **Grep this repo's own closed issues first — the port may already have been done
      upstream, by us.** `gh issue list --repo riseproject-dev/python-wheels --state all
      --search <pkg>` surfaced issue #79 "psycopg2-binary riscv64 support", closed
      pointing at the merged psycopg/psycopg2#1813 "Add riscv64 support for linux builds".
      That is goal 3's deprecation path having already run to completion; re-porting the
      same code under another name undoes the win.
    - **The registry's own shape is the sanity check.** Every `docs/packages/*.yaml` entry
      is a package whose upstream publishes manylinux/musllinux wheels for other arches;
      scripted against PyPI, the only "no Linux wheels" hit is `pyzstd`, which went
      pure-Python at 0.19 and is already marked `deprecated:`. There is no precedent for
      publishing a wheel upstream ships on no Linux architecture at all.

79. **A `<pkg>-headless`/`-gpu`/`-lite` sibling is usually the same upstream tree behind one
    env var — mirror the sibling workflow instead of re-deriving it (the
    opencv-python-headless case).** Gotcha 50 covers the sibling distribution that makes a
    port pointless (`psycopg2`/`psycopg2-binary`); the commoner shape is a sibling that is a
    *legitimate second port* of a tree already in the repo. opencv-python's `setup.py` picks
    `package_name` from `ENABLE_HEADLESS` and appends `-DWITH_QT=OFF -DWITH_GTK=OFF
    -DWITH_MSMF=OFF -DWITH_OBSENSOR=OFF -DOPENCV_FFMPEG_ENABLE_LIBAVDEVICE=OFF`; nothing else
    differs, so `build-opencv-python-headless.yml` is `build-opencv-python.yml` plus that
    variable. Grep `setup.py` for the `package_name = ` assignments first — the branches name
    every sibling upstream publishes and the flag that selects each. Copying the proven
    sibling is also goal 2's answer: two near-identical files read as one recipe, and a
    re-derived second one invites a diff a reviewer has to justify.
    - **A pre-stamped generated file can override the env var you think selects the build.**
      Workflows commonly stamp a generated `version.py`/`_version.py` on the host and delete
      `.git` so the container build runs no git (and cibuildwheel copies ~1 GB less). But
      `setup.py` may *read that file back* for more than the version: opencv-python's
      `get_and_set_info()` regenerates it only when `.git` exists and otherwise returns
      `version["headless"]`, discarding `ENABLE_HEADLESS`. So the variant flag has to be set
      in **both** places — at the stamp (`find_version.py False True False False`) and in
      `CIBW_ENVIRONMENT` — and the stamp step should `grep -Fqx "headless = True"` the way it
      already greps the version, since getting this wrong silently builds the *other* sibling
      under your artifact name after a two-hour compile.

185. **A sibling distribution can be selected by an upstream *source-transform script*
    rather than a build flag — mirror that script verbatim as its own workflow step (the
    pi-heif/pillow-heif case; see `build-pi-heif.yml`).** Gotcha 79's opencv-python-headless
    shape is the easy version: one `setup.py` branches on an env var and the package name
    changes in metadata only. pillow_heif's `pi-heif` sibling is a step further — upstream's
    own `wheels-pi_heif.yml` runs `cp -r ./pi-heif/* .` (overlaying a `setup.cfg` with the
    other name plus any per-OS overrides) then `python3 .github/transform_to-pi_heif.py`,
    which text-replaces `pillow_heif`→`pi_heif` in `setup.py`/`MANIFEST.in`/the `.c` source
    and **renames the package directory and the C extension file themselves**
    (`pillow_heif/_pillow_heif.c` → `pi_heif/_pi_heif.c`). Nothing about this is
    reconstructable from reading `setup.py` alone — the transform script is the spec, so
    checkout it, copy its two commands into a workflow step ahead of the build, and don't
    hand-roll an equivalent sed. A build/link flag can still be layered on top for the parts
    that *are* a simple toggle: pi-heif also sets `PH_LIGHT_ACTION=1`, which changes what
    `libheif/build_libs.py` compiles (drops `x265`, so only `libheif`+`libde265` end up in
    the wheel) — verify by downloading both siblings' real wheels off PyPI and diffing
    `*.libs/` and `dist-info/licenses/`, since that's the wheel-content assertion a workflow
    should check, not the source-tree transform.
    - **The env var a source-transform flag sets can also gate a *test*, not just the
      build** — thread it through `CIBW_ENVIRONMENT` (visible in `before-all`, `build`, and
      `test`, confirmed by pi-heif's own CI relying on exactly this), not a one-off `export`
      inside `CIBW_BEFORE_ALL_LINUX`, or the variant-specific correctness test silently
      *skips* instead of running. pillow_heif's `tests/basic_test.py::test_light_build` is
      `skipif(not PH_LIGHT_ACTION)` — set the flag only for the native-build step and this
      test never executes, so a broken "light" build (e.g. x265 accidentally still linked)
      would ship green.
    - **A sibling can be a *last release*, not an ongoing one — check PyPI's own `version`
      field before picking a tag, not just the source repo's tags.** pillow_heif discontinued
      `pi-heif` between its own v1.4.0 and v1.5.0 (`chore: discontinue pi-heif package`); the
      source repo still tags newer releases, but PyPI's `pi-heif` project has no wheel past
      1.4.0. Pin to the sibling's own latest published version, not the source repo's.

81. **A `py3-none-<platform>` wheel can hold a real compiled library — gotcha 27's stop
    rule needs a third branch (the xgboost case).** Gotcha 27 reads an all-`py3-none-*`
    wheel set as proof that the platform tag was forced by hand and nothing is compiled;
    gotcha 35 adds the downloaded-prebuilt-runtime branch. xgboost is the third and most
    dangerous shape, because from the tag alone it is indistinguishable from the first:
    3.4.1 publishes `py3-none-manylinux_2_28_{x86_64,aarch64}.whl` at **57 MB each**, and
    those bytes are a `libxgboost.so` compiled from the sibling C++ tree during the wheel
    build. Applying gotcha 27's rule would have returned `not-feasible` on a package that
    is an ordinary, fully green port.
    - **The ABI tag is absent because there is no extension module, not because there is
      no native code.** xgboost defines no `PyInit_*` at all: `xgboost/libpath.py` locates
      `xgboost/lib/libxgboost.so` and `core.py` opens it with `ctypes`. That is the second
      gotcha 33's pycryptodome mechanism applied to the *whole* package rather than to a
      few `_raw_*.so` sitting beside real extensions — and a ctypes-only package holds
      nothing CPython-version-specific, so `py3-none` is the *correct* tag for a wheel
      that is nonetheless per-platform.
    - **Wheel size settles it faster than reasoning about the tag.** Gotcha 27's watchdog
      wheels and gotcha 24's multiprocess wheels are the same handful of KB on every
      platform; xgboost's range from 2.4 MB (macOS, linking system libs) to 57 MB (Linux,
      vendoring them). **Diff the `size` field across the platform wheels in
      `pypi.org/pypi/<pkg>/<ver>/json` before concluding anything from an all-`py3-none-*`
      tag set** — near-identical sizes mean one artifact relabelled, divergent sizes mean
      real per-platform content. One JSON read, nothing downloaded.
    - **It also collapses the matrix, which is the payoff.** `[tool.scikit-build]
      wheel.py-api = "py3"` is the scikit-build-core spelling of the gotcha 11/34 idea one
      step past abi3: a *single* build serves every interpreter, so the workflow is
      `only: cp312-manylinux_riscv64` with no `python:` matrix at all. Read `py-api`
      before writing a four-entry matrix that would build the identical wheel four times.

114. **tree-sitter grammar packages are a family with one shape — and one free-threading
    trap (the tree-sitter-bash case; see `build-tree-sitter-bash.yml`).** Every
    `tree-sitter-<lang>` grammar is packaged identically, so porting one ports the recipe
    for all of them: a `setup.py` compiling `src/parser.c` + `src/scanner.c` +
    `bindings/python/<pkg>/binding.c`, a `[tool.cibuildwheel] build = "cp310-*"` table, and
    upstream CI that is a *reusable workflow in another repo*
    (`tree-sitter/workflows/.github/workflows/package-pypi.yml`) — read the reusable
    workflow, not the three-line caller, or you will not see how the wheels are built.
    - **`generate: true` in the caller does not mean you need the tree-sitter CLI.** The
      generated `src/parser.c` (~10 MB) is committed at the tag; diffing the tag tarball
      against the released PyPI sdist showed `parser.c`, `scanner.c`, `binding.c`,
      `setup.py` and `pyproject.toml` byte-identical, so it is a plain
      build-from-checkout with no codegen and no sdist job. Do that diff rather than
      assuming either way — it costs two `curl`s.
    - **A fourth abi3 route, and the only one that can mislabel a wheel** (extends gotcha
      34, which covers `setup(options={'bdist_wheel': {...}})`). Here `setup.py` subclasses
      `bdist_wheel` and overrides `get_tag()` to return `("cp310", "abi3")` for *any*
      interpreter tag starting with `cp`, while the `Py_LIMITED_API` macro is added only
      `if not get_config_var("Py_GIL_DISABLED")`. So a `cp314t` build compiles against the
      **full** API and is still tagged `cp310-abi3` — an unloadable-on-3.10 wheel that
      claims to be stable-ABI. Upstream never trips it because its own matrix is
      `cp310-*`; neither should we. PyPI listing no `cp3XXt` wheel is the usual
      free-threading signal (gotcha 33), and here the `get_tag` override is a second,
      independent reason not to add the job.
    - **`CIBW_TEST_EXTRAS` reproduces an upstream `pip install .[extra]` exactly.** When
      upstream's test action is `pip install -e .[core]` + `python -m unittest discover -s
      <dir>`, naming the extra is smaller divergence than hand-listing its contents in
      `CIBW_TEST_REQUIRES` — cibuildwheel installs the built wheel *with* the extra. Check
      the extra's own riscv64 coverage first (gotcha 30): `tree-sitter` itself publishes
      `manylinux_2_39_riscv64` wheels on public PyPI for cp310-cp314, so no extra index is
      needed, and the test loading the grammar through `tree_sitter.Language(...)` is also
      gotcha 20's proof that the `.so` is real.
    - **Shadowing (gotcha 25) does not arise**: the importable package lives under
      `bindings/python/`, so staging only `bindings/python/tests` via `CIBW_TEST_SOURCES`
      leaves a test cwd where `import <pkg>` can only resolve to the installed wheel.

116. **cffi `set_source(<name>, None)` is ABI mode — the project compiles nothing on
      *any* platform (the sounddevice case).** A `cffi_modules=[...]` line in `setup.py` and a
      `cffi` runtime dependency both look like a compiled port, and gotchas 24/27/35 all
      triage on the *wheel*. This one is settled one level earlier, in the cffi builder
      itself: `ffibuilder.set_source('_<pkg>', None)` selects **ABI mode**, which emits a
      pure-Python `_<pkg>.py` that `dlopen`s a system library at import time; only
      **API mode** (a real C source string as the second argument) produces an extension
      module. One grep decides it:
      ```bash
      grep -rn 'set_source' <sdist>/    # second arg None => ABI mode, nothing is compiled
      ```
      Distinct from gotcha 33, where the `.so` files are real (just `ctypes`/`cffi`-loaded
      rather than importable) — here there is no `.so` to build at all.
      - **Read the project's own `get_tag()` before the PyPI file list.** sounddevice
        subclasses `bdist_wheel` as `bdist_wheel_half_pure` and returns
        `('py3','none', <macos versions>|win_*|**'any'**)` — the Linux branch is literally
        `'any'`, so upstream can never emit a Linux platform wheel, for any architecture.
        That is stronger evidence than gotcha 27's "all-`py3-none-*`" reading, because it
        states the intent rather than inferring it.
      - **Platform wheels that exist can still be pure**: sounddevice's 1MB
        `py3-none-macosx…`/`py3-none-win*` wheels carry `_sounddevice_data/portaudio-binaries/`
        — prebuilt PortAudio `.dylib`/`.dll` files from a sibling repo, i.e. gotcha 35's
        vendored-runtime shape — while `Root-Is-Purelib: true` holds throughout. **Report
        `not-feasible`, not `vendored-binary`**, when the *Linux* wheel is the universal
        `-any` one: riscv64 already installs the exact wheel x86_64 Linux installs and links
        the distro's `libportaudio.so.2`, so there is no arch gap to close. `vendored-binary`
        is for the playwright case, where riscv64 gets *nothing usable* because every wheel
        is platform-specific.

126. **Gotcha 50 without the sibling: a project that is source-only on Linux *by design*,
    because the wheel would have to vendor a system client library (the mysqlclient case).**
    Gotcha 50's psycopg2 shape ends well — the binary sibling already ships riscv64. The
    variant with **no sibling at all** is easier to mistake for a gap: nobody on any Linux
    gets a binary wheel, and the source build is the documented, supported install path.
    mysqlclient 2.2.8 — and every release back to 2.0.3 — publishes exactly `sdist +
    win_amd64`; the only wheel workflow upstream has is `windows.yaml` (cibuildwheel with
    `CIBW_ARCHS: AMD64/ARM64`, static-linking a MariaDB Connector/C it builds itself),
    while `tests.yaml` installs on Linux with a plain `pip install -v .` against apt's
    `libmariadb-dev`. The README's Linux section is the whole policy: `apt-get install
    python3-dev default-libmysqlclient-dev build-essential pkg-config` then `pip install
    mysqlclient`. Issue #554 "Manylinux wheels support" was closed by the maintainer
    pointing at the pile of earlier closed threads asking the same thing.
    - **Confirm the ordinary path already works on our arch instead of assuming it
      doesn't** — one HTTP status per package, no checkout:
      `curl -s -o /dev/null -w '%{http_code}' https://packages.ubuntu.com/noble/riscv64/<dev-pkg>`
      answers 200 for `libmysqlclient-dev`, `default-libmysqlclient-dev` and
      `libmariadb-dev`. If the dev package the README names exists for riscv64, riscv64
      users install exactly the way x86_64 users do — there is no gap to close, and the
      sdist compiles one `.c` in seconds.
    - **A near-neighbour already in the registry is not precedent.**
      `build-mysql-connector-python.yml` links the same `libmysqlclient` out of the
      manylinux image (gotchas 72/73), which makes this port look pre-solved — but
      mysql-connector-python *does* publish manylinux x86_64/aarch64 wheels, so it had a
      real gap. Compare what the two upstreams **publish**, not what they link.
    - **Here the licence makes shipping it worse than neutral.** auditwheel would vendor
      GPL-2.0 `libmysqlclient` (or LGPL `libmariadb`) into a wheel of a GPL-2.0-or-later
      project that deliberately links it from the system on Linux — a redistribution
      obligation RISE would take on to close a gap that does not exist.

145. **A `py3-none-<platform>` wheel can also be a *compiled-from-source* binary —
    maturin's `bindings = "bin"` (the magika case; see `build-magika.yml`).** Gotcha 27
    reads an all-`py3-none-*` Linux wheel set as "the platform half was forced by hand,
    nothing is compiled, stop"; gotcha 35 refines it to `vendored-binary` when the
    platform half is a *downloaded* prebuilt runtime. There is a third shape, and it is
    an ordinary port: a project shipping a pure-Python `py3-none-any` wheel **and** much
    larger `py3-none-<platform>` wheels, where the extra weight is its own CLI, compiled
    by maturin from Rust sources in the same repo and installed as
    `<dist>-<ver>.data/scripts/<name>`. `py3-none` is honest there — the artifact is a
    *script*, not an extension module, so no ABI tag applies and gotcha 27's
    "`py3-none` ⇒ nothing compiled" inference does not hold. Two reads separate the three
    cases before any checkout:
    - `unzip -p <whl> '*/WHEEL'` → `Generator: maturin (…)` plus `Root-Is-Purelib: false`.
      maturin only emits a platform tag when it actually built a binary for that target.
    - `unzip -l <whl>` sorted by size → a single tens-of-MB `.data/scripts/<name>` is the
      compiled CLI; gotcha 35's case instead shows a vendor payload upstream fetched
      (`node`, `bin/ptxas`), and gotcha 27's cosmetic tag shows nothing at all.
    **The pure wheel is not a substitute for the platform one**, so `pip install` already
    working on riscv64 does not close the gap: magika's `[project.scripts] magika` in the
    pure wheel is a placeholder that prints "you have attempted to run `$ magika` (the
    Rust client), but this is not available" and exits 1. Matrix collapses to a single
    build — one `py3-none-<platform>` wheel serves every interpreter — but still test it
    on each, because the *Python* half of the wheel is what imports the runtime deps.

150. **Before writing any YAML, check whether a sibling package from the same upstream
    family already has a workflow in this repo (the tree-sitter-javascript case).** The
    playbook says to start from *upstream's* workflow; the cheaper starting point is a
    package whose upstream shares the same packaging machinery, because that workflow has
    already been reviewed and driven green here. Whole families are packaged from one
    reusable workflow — every `tree-sitter-<lang>` grammar (there are dozens) is built by
    `tree-sitter/workflows/.github/workflows/package-pypi.yml`, and the same holds for any
    org that centralises releases. `ls .github/workflows/build-<family-prefix>*` settles
    it in one command, and the diff between siblings is usually just the package name and
    version.
    - **Verify the family assumption rather than inheriting it.** Confirm per package that
      the generated sources are committed and match the released sdist
      (`gh api repos/<org>/<pkg>/tarball/<tag>`, then `diff` `setup.py`,
      `pyproject.toml`, the generated `parser.c`/`scanner.c` and the binding against the
      PyPI `.tar.gz`) — that is what lets you skip upstream's `generate: true` and needs no
      code generator on the runner. Grammars differ in whether `src/scanner.c` and
      `queries/` exist at all, and `setup.py` branches on both.
    - **The whole port is then two cheap local checks** (gotcha 9), no QEMU: `uv build
      --wheel` on any host proves the tag upstream's `get_tag` override produces
      (`cp310-abi3`, so no `CIBW_CONFIG_SETTINGS` — gotcha 34), and staging the test dir
      into an empty cwd exactly as `test-sources` does, then running the suite against the
      installed wheel, proves the import resolves to the wheel and not the checkout
      (gotcha 25). Both ran in under a minute here and the first CI run was green.
    - **Match the sibling's scope decisions too, and say why in the PR.** Dropping
      musllinux was not arbitrary: the family's runtime dep (`tree-sitter`) publishes no
      `musllinux_*_riscv64` wheel, so `CIBW_TEST_EXTRAS` could not resolve it in a musl
      container. Re-check that per package — a `~=` floor can resolve to a *newer* dep
      than the one you looked at (`tree-sitter~=0.24` resolved to 0.26.0), so confirm the
      arch wheels exist for the version pip will actually pick (gotcha 30's second bullet).

157. **A closed-source vendored runtime has no source to fall back on — and its platform
    table is published in three independent places (the claude-agent-sdk case).** Gotcha 35
    triages a `py3-none-<platform>` wheel whose payload is a downloaded prebuilt runtime by
    finding the fetch and then the vendor's artifact index. When the vendored tool is a
    *closed-source* product rather than an open-source runtime like Node, gotcha 77's escape
    hatch — build the dependency from source yourself — does not exist, so the index answer
    is final. claude-agent-sdk's wheels are 343 MB uncompressed of which **342.56 MB is one
    file**, `claude_agent_sdk/_bundled/claude`, fetched at build time by
    `scripts/download_cli.py` running `bash install.sh` from `https://claude.ai/install.sh`;
    the remaining 0.5 MB is pure Python built by hatchling (`only-include =
    ["src/claude_agent_sdk"]`), so the build compiles nothing on any platform.
    - **Three cheap, independent reads of the same platform table**, any one of which
      settles it: the installer's own `case "$(uname -m)"` (`x86_64|amd64`, `arm64|aarch64`,
      `*) Unsupported architecture; exit 1`); the vendor's release manifest
      (`https://downloads.claude.ai/claude-code-releases/<ver>/manifest.json` → exactly
      `{darwin,linux,win32}-{x64,arm64}` plus the two musl variants, at the pinned version
      *and* at `latest`); and — for anything also distributed through npm — the launcher
      package's **`optionalDependencies`**, which fan out to one native-binary package per
      platform (`@anthropic-ai/claude-code-linux-arm64`, …). Add that last one to the
      collection beside `nodejs.org/dist`, NVIDIA's redist index and conda repodata: it is
      one `curl` of `registry.npmjs.org/<pkg>/latest` and needs no download.
    - **"pip install works on riscv64" is not the same as "riscv64 is served" — read the
      runtime resolver before choosing between `not-feasible` and `vendored-binary`.**
      Gotcha 116 reports `not-feasible` when the Linux wheel is the universal `-any` one,
      because riscv64 already installs exactly what x86_64 installs. Here upstream publishes
      **no `-any` wheel at all**, so riscv64 falls back to the sdist — which builds fine in
      seconds and yields a working *import* whose every call fails: `_find_cli()` looks for
      `_bundled/claude`, then for `claude` on PATH and in six install locations, and raises
      `CLINotFoundError` when none exists, which on riscv64 is always. Installable but
      non-functional is `vendored-binary`, not `not-feasible`.
    - **Read the wheel's central directory over an HTTP range request** (gotcha 41) rather
      than downloading 100 MB: sorting the entries by uncompressed size showed the single
      payload file and the 0.5 MB of Python beside it in one call, which is the whole
      finding.

183. **`vendored-binary` is a category, not a verdict — the disposition still has to be
    earned per package (closing the loop on gotcha 35, re-verified against playwright
    1.62.0).** Gotchas 35 and 157 both stop at "this is `vendored-binary`, not
    `not-feasible`", which answers *what kind of gap this is* but not *whether to port it*.
    The actual call is whether the vendored payload's **primary function** has any riscv64
    story at all, and playwright supplies the other worked example past `av` (which ships
    it and is `in-review`): re-fetching the real v1.62.0 sources confirmed every fact in
    gotcha 35 still holds (`NODE_VERSION` pins 24.18.1, `SHASUMS256.txt` has zero `riscv`
    matches, `unofficial-builds.nodejs.org` does publish a `riscv64` tarball for that exact
    version) and added the missing last link: `playwright-core`'s own
    `hostPlatform.ts::calculatePlatform()` doesn't crash on an unrecognised Linux arch, it
    *degrades gracefully* to `{hostPlatform: "<unknown>", isOfficiallySupportedPlatform:
    false}` — which is worse for triage, because a wheel that merely throws would fail
    loudly in one smoke test, while this one imports fine and only breaks the two calls
    that are the entire reason anyone installs the package (`playwright install`, and any
    local browser launch).
    - **Ask "does the primary use case have a riscv64 story", not "can I assemble the
      bytes".** `av` is `vendored-binary` too (bundled ffmpeg libs), but those libraries
      *do* build for riscv64, so vendoring them is a packaging convenience with a real
      target. playwright's vendored payload (a Node.js driver, and — one layer further in —
      Chromium/Firefox/WebKit, which the driver launches) has no riscv64 build from its
      vendor at any layer, official or otherwise usable: Microsoft ships no riscv64 browser
      binary period, so an unofficial Node.js build would only get you a driver that can
      start, not one that can do anything a user opened the package for.
    - **An unofficial third-party build is not free even when it exists.** Swapping
      `NODEJS_DIST` for `unofficial-builds.nodejs.org` in a patch is mechanically easy and
      still the wrong move here, because it fixes the *shallower* of the two missing
      artifacts (the driver) while leaving the *deeper* one (the browsers) permanently
      unavailable — so the patch would ship a wheel that imports and then fails on its own
      documented quick-start. Don't stop at "can this fetch succeed" — trace one level past
      the vendored binary to what it does at runtime, same as gotcha 35's `coreBundle.js`
      read.
    - **Verdict: park a `vendored-binary` port when the primary function is unreachable, not
      merely degraded.** This mirrors sglang's `parked` disposition ("buildable but not
      installable") one layer up the stack: playwright's wheel would be *installable and
      importable* but not *usable* for the thing it exists to do, on every currently
      supported interpreter, with no patch that changes that — record it in `queue.yml` as
      `parked` with the specific unreachable primitive named (here: no riscv64 browser
      binary, at any layer, official or unofficial), not as a generic "no riscv64 wheel yet".

186. **A sibling package's riscv64 vendor doesn't transfer if it publishes a different
    *artifact shape* — libraries to link against are not the same deliverable as a
    standalone executable (imageio-ffmpeg vs. `av`, closing the loop on gotcha 183).**
    imageio-ffmpeg's 6 Linux/macOS/Windows wheels are all `py3-none-<platform>` for the
    same reason as gotcha 35/183's cases: nothing is compiled, `setup.py` has zero
    `ext_modules`, and `tasks.py`'s `build` task just drops a prebuilt per-platform
    `ffmpeg` executable into `imageio_ffmpeg/binaries/` before hand-retagging the wheel
    (`Root-Is-Purelib: true`, `Tag: py3-none-manylinux2014_x86_64`, …). The binary comes
    from a curated vendor repo, `imageio/imageio-binaries` (raw-fetched by
    `tasks.py:get_ffmpeg_binary`), whose Linux entries are themselves johnvansickle.com
    static builds per a comment in `_definitions.py`. Both have zero riscv64 offering —
    `gh api repos/imageio/imageio-binaries/contents/ffmpeg` lists only
    linux-{x86_64,aarch64}, and johnvansickle.com/ffmpeg/ ships only
    amd64/i686/arm64/armhf/armel — so per gotcha 183 the next question is whether an
    *unofficial* riscv64 ffmpeg build exists anywhere else, official or otherwise.
    - **One does — but check what it actually contains before assuming it transfers.**
      `av` (gotcha 183's own positive worked example) vendors FFmpeg too, and its wheels
      are `in-review` in this repo precisely because its vendor, `PyAV-Org/pyav-ffmpeg`,
      *does* publish a riscv64 release (`ffmpeg-manylinux-riscv64.tar.gz`, confirmed by
      downloading it). That looked, at first glance, like it would settle imageio-ffmpeg
      too. It doesn't: `tar tzf` on that release shows only `include/*.h` and
      `lib/*.so*` — headers and shared libraries meant for PyAV to link against via
      `scripts/fetch-vendor.py`, **no `bin/ffmpeg` executable at all**. `av` needs a
      *library* to link; imageio-ffmpeg needs a *standalone CLI binary* to shell out to
      (`get_ffmpeg_exe()` returns a path, then `subprocess.check_call([exe, "-version"])`
      elsewhere). Same upstream project (FFmpeg), same riscv64 target architecture, same
      general vendoring pattern (`vendored-binary`), but a different artifact shape — and
      a vendor publishing one shape says nothing about whether the other exists.
    - **Producing the missing shape yourself is not "patching a URL" (gotcha 183's
      "unofficial build is not free") — it's authoring a new build system.** Turning
      pyav-ffmpeg's linkable libraries (or raw FFmpeg source) into a working `ffmpeg`
      CLI executable for riscv64 would mean this repo compiling FFmpeg's `fftools/`
      front end from source ourselves — something imageio-ffmpeg's own upstream CI
      *never does on any platform* (it only ever copies a prebuilt exe out of
      `imageio-binaries`). That fails goal 2 (a workflow should narrow upstream's own CI
      to riscv64, not invent a CI upstream doesn't have) and is a different order of
      scope than the URL-swap or config-flag patches this repo normally carries.
      Contrast with `av`: PyAV's *own* existing fetch step already had a riscv64 target
      at its vendor, so porting it is running upstream's process as-is. Verdict: park,
      same as playwright — `vendored-binary`, no artifact of the shape needed exists
      anywhere (official or unofficial), and producing one would require building an
      unrelated new pipeline rather than porting an existing one.

187. **Gotcha 40's numba wall catches more than numba itself — check a candidate
    package's *own* `install_requires` for a hard, unconditional numba dependency before
    assuming it's independently portable (the shap case), and when you do hit the wall
    again, check the LLVM version by *conda channel*, not just by package name (a
    refinement of gotcha 42).** shap 0.52.0's `pyproject.toml` requires numba
    unconditionally on every platform except macOS+x86_64 (`'numba; sys_platform !=
    "darwin" or platform_machine != "x86_64"'` — true for linux/riscv64), and it is not
    an optional accelerator: `shap/utils/_masked_model.py` and
    `shap/explainers/_partition.py` both do module-level `from numba import njit`, and
    `shap/__init__.py` unconditionally imports `PartitionExplainer` at package-import
    time, so `import shap` itself hard-fails without numba installed. Run gotcha 40's
    dependency check (`info.requires_dist` from PyPI JSON, drop the extras) *before*
    inspecting a candidate's own build system — a package with a clean, portable build of
    its own is still blocked if a hard dependency isn't. Re-confirming gotcha 42's
    conda-blocked verdict surfaced a wrinkle worth checking next time: llvmlite's build
    script hardcodes the `numba/label/llvm_wheel` conda channel, which still publishes 0
    `linux-riscv64` packages (`https://conda.anaconda.org/numba/label/llvm_wheel/linux-riscv64/repodata.json`)
    — but **conda-forge's own `llvmdev`, a different channel entirely, does publish
    `linux-riscv64` builds at the exact LLVM major llvmlite's `ffi/CMakeLists.txt`
    requires** (`llvmdev-22.1.8`, confirmed via
    `https://conda.anaconda.org/conda-forge/linux-riscv64/repodata.json`). That doesn't
    by itself unblock llvmlite — the build script would need patching to source from a
    different channel, and numba's own patches to LLVM (not just its version) are the
    reason it uses its own channel rather than conda-forge's — but it's a concrete lead
    for whoever eventually picks up the numba/llvmlite port, and worth checking again
    then rather than re-deriving from scratch.

203. **A `py2.py3-none-<platform>` wheel bundling a runtime can be the *opposite* of
    gotchas 35/183/186's vendored-binary pattern — check whether the build compiles that
    runtime from source before assuming it is (the nodejs-wheel-binaries case).** Gotcha
    35 finds playwright's `py3-none-<platform>` tag load-bearing because `setup.py`
    downloads a prebuilt Node.js binary from `nodejs.org/dist`, and gotcha 186 shows
    imageio-ffmpeg doing the same for a curated ffmpeg vendor — both are
    `vendored-binary`, gated on whether the *vendor* publishes the target arch. Gotcha
    145's magika case is the compiled-from-source counterpart, but there the port's own
    Rust source is what maturin builds; here the port has no compiled code of its own at
    all, and what gets built is a *third-party upstream project's own source*, fetched
    fresh by the build. nodejs-wheel-binaries looks identical to the vendored-binary
    cases at a glance (same `py2.py3-none-<platform>` tag, a Node.js binary is the whole
    point) but its `CMakeLists.txt` has no download-a-binary step at all: an
    `ExternalProject_Add` block fetches Node's own
    **source** tarball (`https://github.com/nodejs/node/archive/refs/tags/v<ver>.tar.gz`)
    and runs upstream's own `configure && make` — the identical recipe upstream's own CI
    uses to build its x86_64/aarch64/macOS/Windows wheels. That makes it an ordinary
    from-source heavy-C++ port (gotcha 15's family), not a vendored-binary one, so the
    feasibility question is not "does a vendor publish riscv64" but "does the upstream
    *project's own build* support riscv64" — settled by grepping the vendored project's
    own configure/build-system for the arch (`grep -n riscv deps/v8/BUILD.gn
    configure.py` in a fetched Node source tree both hit) and, as corroborating rather
    than load-bearing evidence, that `unofficial-builds.nodejs.org` already ships a
    working `node-v<ver>-linux-riscv64.tar.gz` built the same way.
    - **Find the fetch, then read what it fetches — a URL alone doesn't say vendored vs.
      source.** The same one-liner that settles gotcha 35 (`grep` the download base) has
      to be followed by checking whether the URL path is a *release/dist asset*
      (prebuilt, vendor-gated) or a *source archive/tag* (`archive/refs/tags/`, a
      `.tar.gz` of the repo itself, compiled by the very build you're writing) —
      `ExternalProject_Add`/`FetchContent` fetching a GitHub `archive/refs/tags/` URL is
      close to definitive for the second case.
    - **A from-source port of a runtime this size still needs the heavy-build
      treatment**, not special-casing: `timeout-minutes: 1440` (Node's V8 + bundled ICU
      is comparable in scope to the other 24h riscv64 jobs — pyarrow, torch,
      onnxruntime), and gotcha 9's QEMU proxy validates cheaply — running the vendored
      project's own `configure` (not just the outer CMake project's) under `docker run
      --platform linux/riscv64 <manylinux image>` finishes in seconds and proves the arch
      is recognized, without attempting the multi-hour compile locally.

214. **Not being Bazel-blocked doesn't mean a build is in scope — count the
    independently-vendored dependency tree before committing (the ortools case).**
    jaxlib (PR #526, parked) established one hard-blocker shape: Bazel + riscv64. ortools
    looked like it might be the same family (a big C++ operations-research suite with a
    `bazel/` tree) but isn't — its actual PyPI release wheel is built by
    `tools/release/build_delivery_linux.sh`'s `build_python()`, which is plain
    `cmake -S. -B... -DBUILD_PYTHON=ON` against upstream's own `CMakeLists.txt`
    (confirmed against the real release script and `.github/workflows/amd64_linux_cmake_python.yml`,
    both CMake-only, no Bazel involved). The absence of a Bazel wall doesn't make it
    in-scope: `BUILD_DEPS=ON` (forced whenever `BUILD_PYTHON` is on) `FetchContent`-builds
    abseil, protobuf, Eigen3, re2, Boost, SoPlex, SCIP, and the four-library COIN-OR suite
    (CoinUtils/Osi/Clp/Cgl/Cbc) *and* HiGHS and PDLP and BOP, on top of compiling ortools'
    own large C++ core (CP-SAT, routing) and generating its SWIG Python bindings — over a
    dozen independent large C++ projects glued together in one build, most of which
    (SCIP/SoPlex/Boost-as-a-solver-dep/COIN-OR) have zero riscv64 precedent anywhere in
    this repo, unlike abseil/protobuf (proven via grpcio-tools/chromadb/ctranslate2) and
    HiGHS (already `published` standalone as highspy — a small fraction of what ortools
    would additionally compile). Cross-checking against this repo's own largest build to
    date — libclang's from-scratch LLVM/Clang compile, ~10h and explicitly logged as "the
    largest build in this repo so far" — a build that FetchContents *that much additional*
    unproven C++ on top of a comparably-sized core, each new dependency a plausible source
    of its own multi-hour fix/rebuild cycle, is a reasonable multi-day-effort read even
    with zero hard architectural blocker. Parked without opening a worktree: this is the
    scope call the task brief itself invites ("if it turns out to be ... otherwise a
    multi-day effort disproportionate to this task's scope, it's fine to park it"), and the
    research needed to make that call (reading the real release script, diffing it against
    the Bazel tree, counting `FetchContent`/`CMAKE_DEPENDENT_OPTION` third-party solvers in
    `CMakeLists.txt`, cross-checking which of them are already proven or still unproven in
    this repo's own history) is all doable read-only against the upstream repo and this
    repo's own git history, without a checkout.
    - **A project can carry both a `bazel/` tree and a working CMake-only release path —
      check which one the actual PyPI wheel comes from**, not which build system the repo
      leads with. `tools/release/*.Dockerfile` (or equivalent) is the ground truth; a
      top-level `BUILD.bazel`/`WORKSPACE.bzlmod` next to a `CMakeLists.txt` is not evidence
      either way on its own.
    - **`CMAKE_DEPENDENT_OPTION(BUILD_<dep> ... "NOT BUILD_DEPS" ON)` blocks are a
      dependency-tree census** — grepping them (or their Bazel-equivalent `deps.bzl`/
      `MODULE.bazel` counterpart) gives an honest count of what a wrapper build actually
      FetchContents, before writing a line of workflow YAML.
    - **Weigh new dependencies against this repo's own track record, not against the
      package's inherent difficulty in isolation** — a dependency this repo has already
      built for riscv64 (protobuf, abseil, HiGHS) is de-risked; a same-scale dependency
      this repo has never touched (SCIP, SoPlex, the COIN-OR suite) carries the full
      first-timer risk of an unfixed gotcha, and a build with many such unknowns compounds
      that risk rather than averaging it out.

230. **"CMake" isn't always a hand-maintained build — a project's own CMakeLists can be a
    mechanical export of a closed internal build graph, with no fallback for an unlisted
    architecture (the catboost case).** catboost looked like a candidate for the
    jaxlib/ortools family (a large C++ ML framework historically built with a proprietary,
    Arcadia-derived `ya make` tool) but resolves differently again: its Linux CI
    (`.github/workflows/build_per_platform.yaml`) really does drive plain
    `./ci/build_all.py` → `cmake`/ninja, no `ya`/Arcadia tooling invoked anywhere in the
    build path, and `catboost/python-package/setup.py` calls that same CMake build for its
    `_catboost`/`_hnsw` extensions (no pure-Python fallback). The blocker is one layer
    down: every `CMakeLists.txt` with platform-specific content — 350 separate files across
    the tree, confirmed via `gh api search/code -f 'q=filename:CMakeLists.linux-x86_64.txt
    repo:catboost/catboost'` — is a **generated stub**, each carrying the identical
    boilerplate header "This file was generated by the YaTool build system
    (https://github.com/yandex/yatool)... simple modifications are allowed like adding
    source-files... complex modifications ... may be rejected", and each dispatching purely
    on `CMAKE_SYSTEM_NAME`/`CMAKE_SYSTEM_PROCESSOR` with **no `else()` branch**:
    `if (... STREQUAL "x86_64") include(CMakeLists.linux-x86_64.txt) elseif (... STREQUAL
    "aarch64") ... elseif (... STREQUAL "ppc64le") ... endif()`. Only x86_64, aarch64, and
    ppc64le get a Linux variant anywhere in the repo (confirmed identically at both the
    top-level `build/CMakeLists.txt` dispatcher and a leaf like
    `catboost/libs/model/CMakeLists.txt`) — riscv64 has no generated file to include, so the
    `endif()` falls through silently and every one of those 350 injection points (SIMD
    boosting kernels, source lists, compile flags) contributes nothing on riscv64, not a
    compile error but a systematically incomplete build. `riscv` hits elsewhere in the tree
    (62 of them) are all inside incidentally-vendored third-party libs that already carry
    generic riscv64 support upstream of catboost (lzma, abseil, libunwind, boost.predef) —
    none touch catboost's own generated dispatch layer. Fixing this for real means either
    running Yandex's YaTool generator for a new "linux-riscv64" platform preset it has never
    targeted (unproven, requires Arcadia-side platform/toolchain definitions this repo has
    no access to), or hand-writing riscv64 equivalents of all 350 generated files by reverse
    engineering the x86_64/aarch64 ones and porting away their SIMD/intrinsics content — a
    larger and more mechanically-blocked undertaking than ortools' dozen `FetchContent`d
    dependencies (gotcha 214), which at least had a plain hand-written `CMakeLists.txt` to
    extend. Parked without opening a worktree, same as gotcha 214: the call was fully
    resolvable read-only via `gh api` against the tagged release (workflows, `build_all.py`,
    `build_native.py`, `setup.py`, and a `search/code` count of the generated-stub pattern),
    no checkout needed.
    - **The YaTool boilerplate comment itself is the tell** — a `CMakeLists.txt` that opens
      with "This file was generated by the YaTool build system... from ya.make files" is a
      mechanical export, not a build to extend by adding an `elseif` branch; treat that
      header the way gotcha 41 treats "compiles a lot of real code" — a proof of *scale*,
      not of *portability*.
    - **A per-platform `if/elseif` cascade with no `else()` is architecture allow-listing,
      not architecture detection** — grep one leaf file for the full list of `elseif`
      branches (here: x86_64/aarch64/ppc64le/Darwin x86_64+arm64/Windows x86_64/four Android
      ABIs) before assuming "it's CMake, CMake is portable" from the file extension alone.
    - **`gh api search/code -f 'q=filename:<generated-stub-name> repo:<org>/<repo>'`** turns
      "how many places would need a new architecture" from a guess into a number in one
      call — 350 here, versus ortools' roughly a dozen `FetchContent`s, is the concrete
      scale comparison that justified parking without a build attempt.

236. **An "LLVM-based" port is not automatically libclang-scale — check which CMake target
    the build actually asks for (the clang-format case; see `build-clang-format.yml`).**
    libclang (PR #866, gotchas 211/225) set the expectation that "compiles LLVM from
    source" means a multi-hour build with `-DLLVM_TARGETS_TO_BUILD=RISCV` and
    `-static-libgcc -static-libstdc++` to make `libclang.so` portable off the container.
    clang-format-wheel's own `CMakeLists.txt` fetches the identical
    `llvm-project-<ver>.src.tar.xz` release tarball via `ExternalProject_add` (gotcha 203's
    "source, not vendored-binary" shape) but builds only `--target clang-format` with
    `-DLLVM_TARGETS_TO_BUILD=` **empty** — no codegen backend at all, because a formatter
    needs the frontend (Lex/AST/Format) and none of the target-specific machinery
    `libclang.so`'s indexing API pulls in. It also passes no static-linking flags, so
    nothing about the manylinux image's GCC needs the CRB `libstdc++-static` package
    libclang required. Read the actual `--target`/`CMAKE_ARGS` a wrapper project passes,
    not just "it downloads llvm-project and runs cmake", before budgeting a port at
    libclang's scale — the two builds share a download URL and nothing else about their
    cost.
    - **The payoff compounds with the matrix collapse.** clang-format-wheel's
      `pyproject.toml` sets `wheel.py-api = "py2.py3"` (gotcha 113/xgboost's `py3` case,
      one step further since the tool has no C-extension ABI at all), so cibuildwheel
      needs `only: cp312-manylinux_riscv64` with no interpreter matrix — one build, not
      four.

246. **A `pyO3`/uniffi "binding" package can vendor a closed-source Rust core as a git-committed
    binary blob, not a build-time download — the onepassword-sdk case.** Gotcha 157's
    claude-agent-sdk fetches its closed-source payload at build time via an installer script,
    so the platform table is readable from that script's own `case` statement or a release
    manifest. `onepassword-sdk` 0.4.1 is the same closed-source-vendor shape one layer
    earlier: there is no Rust source, no `Cargo.toml`, and no fetch step anywhere in
    `1Password/onepassword-sdk-python` — `setup.py`'s `get_shared_library_data_to_include()`
    just points `package_data` at `src/onepassword/lib/{x86_64,aarch64}/libop_uniffi_core.{so,dylib}`,
    ~20 MB binaries checked directly into the repo as ordinary git blobs (confirmed via
    `gh api .../contents/... --jq '{size,encoding}'` — real file, not an LFS pointer). The
    `op_uniffi_core` Rust crate that produces them is 1Password's proprietary cross-SDK core
    (shared with their Go/JS SDKs); it is not published in any public 1Password repo
    (`gh search repos`/`search/code` for `op_uniffi_core` across the org: zero hits), so
    gotcha 77's escape hatch — build the vendored dependency from source yourself — does not
    exist, same as gotcha 157. Only x86_64 and aarch64 directories exist under `lib/`; PyPI's
    10 published wheels confirm the same two Linux arches
    (`manylinux_2_32_{x86_64,aarch64}` × cp39-cp313, plus macOS/Windows) with no riscv64 and
    no `py3-none-any` fallback. `not-feasible`/`parked`, no worktree pushed.
    - **The sdist is not a working fallback here, unlike claude-agent-sdk's.** `pip install`
      on an unsupported arch does not degrade to "installs fine, fails at call time"
      (claude-agent-sdk) — `get_shared_library_data_to_include()` keys off
      `platform.machine().lower()`, and `riscv64` matches neither its `x86_64/amd64` nor
      `aarch64/arm64` branches, so `include_path` stays bare `"lib"` and `package_data` names
      a file (`lib/libop_uniffi_core.so`) that only ever exists under `lib/x86_64/` or
      `lib/aarch64/`. The `bdist_wheel` override (`root_is_pure = False`,
      `plat_name = get_platform()...`) still tags the result as a real platform wheel even
      though the build silently packaged zero bytes of native code — installable, importable
      up to the point `op_uniffi_core.py`'s `ctypes`/ffi loader tries to open a `.so` that was
      never included, then a hard failure on every call. Confirm this shape by reading the
      `package_data` computation next to the actual `lib/<arch>/` directory listing, not by
      trusting that "there's a sdist" means riscv64 has a source-build path.
    - **Three independent, cheap confirms, same pattern as gotcha 157's "three tables":** the
      `lib/` subdirectory listing (`x86_64`, `aarch64`, nothing else) via `gh api
      .../contents/src/onepassword/lib`; PyPI's per-release wheel filename list
      (`manylinux_2_32_{x86_64,aarch64}` only, `pip.pypi.org/pypi/<pkg>/json`); and the
      absence of any `op_uniffi_core`/"core" repo in the vendor's GitHub org via `gh repo
      list`/`gh search repos`/`gh api search/code`. All three agree with no download needed.

248. **An "inactive"/deprecated package's own PyPI ceiling can be a real ABI wall, not
    stale trove classifiers — verify by building, don't infer from staleness alone (the
    typed-ast case).** `typed-ast` carries `Development Status :: 7 - Inactive` and tells
    installers "no longer maintained... use the standard library `ast` module instead" for
    Python 3.8+; its last release (1.5.5, Dec 2023) ships wheels only for
    cp36-cp311 — never cp312+. That alone reads like gotcha 41's "staleness" caution,
    not proof of a hard wall, so it was checked by actually building: `pip download
    typed-ast==1.5.5 --no-binary :all:` then `pip wheel <sdist> --no-deps
    --no-build-isolation` against cp312/cp313/cp314 locally (no container needed —
    this is a pure C-extension compile, arch-independent). It **built and imported
    cleanly, unmodified, on cp312** — the classifiers understate what actually compiles.
    But cp313 and cp314 both hard-fail: `ast27/Include/compile.h:12: error: unknown
    type name 'PyFutureFeatures'`. CPython 3.13 renamed that public struct to
    `_PyFutureFeatures` and moved it from `cpython/compile.h` into
    `internal/pycore_symtable.h` (confirmed by grepping both interpreters' own
    installed headers) — a permanent upstream CPython internal-API removal, not a
    local toolchain quirk. Since typed-ast vendors its own complete tokenizer/parser/ast
    tree (it doesn't touch CPython's compiled-AST internals at all, just the stable
    object C-API) it tracks CPython's headers further than the classifiers admit, but
    still not past 3.12 — and this repo's default interpreter matrix is
    cp312/cp313/cp314/cp314t (gotcha in workflow-anatomy.md), so at most 1 of 4 target
    ABIs would build. `parked`, no worktree pushed (one was opened per this task's
    instructions, then removed after the verdict — nothing to commit).
    - **A vendored-parser fork can outlive its stated Python ceiling by exactly the
      versions where the CPython C-API it happens to touch stayed stable** — don't
      read "only ships wheels through cp3N" as "won't compile past cp3N" without a
      build attempt; the two can diverge in either direction.
    - **A local `pip wheel --no-build-isolation` against several interpreter
      minors (via `uv python install` or equivalent, no container) is the cheapest way
      to find the exact minor where a C extension's assumptions about CPython's public
      headers break**, and it's portable across host arches — the failure is a header
      compile error, unrelated to riscv64 itself.

249. **Gotcha 40/187's `Requires-Dist` check can pass clean while a *build-time-only*
     dependency, invisible to that check, is the real wall — and that dependency can
     itself need a from-scratch native port (the torch-c-dlpack-ext case).**
     `torch-c-dlpack-ext`'s only `Requires-Dist` is `torch`, which pypi.riseproject.dev
     already serves for riscv64 (cp312-cp314t) — the check gotcha 40 prescribes says
     "go ahead." But the package ships no `.so` in its sdist; its custom PEP 517 backend
     (`build_backend.py`, `backend-path = ["."]`) only returns a static `Requires-Dist`
     and instead adds `apache-tvm-ffi>=0.1.1` *dynamically*, from
     `get_requires_for_build_wheel()`, only when a prebuilt library isn't already
     sitting in the tree — a requirement that never appears in PyPI JSON, wheel
     METADATA, or `pyproject.toml`'s `[project.dependencies]`, only in code that runs
     during resolution. Building requires running
     `python -m tvm_ffi.utils._build_optional_torch_c_dlpack`, and merely importing
     that module is enough to sink the port: `tvm_ffi/__init__.py` unconditionally
     ctypes-loads its own compiled native core (`libinfo.load_lib_ctypes`) at package
     import time, with no lazy path. `apache-tvm-ffi` has zero riscv64 wheels anywhere
     (not PyPI, not our registry) and its native core is an independent ~10k-line
     CMake/C++ project (vendored `3rdparty/dlpack`, optional libbacktrace) that has
     never targeted riscv64 — porting *it* first would be a whole separate package port,
     out of scope for whatever package merely happens to build against it.
     - **A dynamic `get_requires_for_build_wheel()`/`get_requires_for_build_sdist()` in a
       custom `build-backend` is exactly the kind of requirement gotcha 40's static
       `info.requires_dist` read cannot see.** Read `build_backend.py` (or equivalent)
       before trusting a clean `Requires-Dist` — a package whose only declared runtime
       dependency is already portable can still be built by a tool that is not.
     - **A build tool failing to *import* is a harder stop than one failing to *compile*
       against your target's headers** — no amount of patching the package under port
       helps if the tool it shells out to 500-errors before running a single build step
       because its own native core has no riscv64 artifact to load.

263. **A PyPI wheel with no sdist and a closed-binary redistribution licence can still be
     portable, when the code inside it is an Apache/BSD/MIT project the vendor merely
     repackages — check the upstream *project's* licence and buildability, not the
     wheel's (the tbb case).** PyPI's `tbb` ships one wheel
     (`tbb-2023.1.0-py2.py3-none-manylinux_2_28_x86_64.whl`), no sdist, under the "Intel
     Simplified Software License" — "provided in binary form only... No reverse
     engineering... or modification" — which reads like a hard stop (gotcha 157's
     closed-vendored-runtime shape). It is not: the wheel is Intel's own prebuilt
     Apache-2.0 oneTBB (`github.com/uxlfoundation/oneTBB`, tag `v2023.1.0` matches the
     PyPI version exactly), and that EULA governs *Intel's binary*, not a rebuild from
     the public source. Building oneTBB from source and shipping the result under
     oneTBB's own Apache-2.0 licence (its `LICENSE.txt`) sidesteps the closed licence
     entirely — the same reasoning Debian's `onetbb` source package relies on.
     - **An external distro's build farm is admissible feasibility evidence, and settles
       an ISA-intrinsics worry (gotcha 41/231) faster than reading source.**
       `madison.php?package=onetbb` showed `onetbb 2023.1.0-3` in Debian sid, and
       `buildd.debian.org/status/package.php?p=onetbb&a=riscv64` showed it `Installed` —
       proof the exact upstream version builds and works on real riscv64 hardware,
       before touching CMakeLists. oneTBB's own portability holes are real but narrow:
       `include/oneapi/tbb/detail/_machine.h` gates `_mm_pause`/RTM to
       `__TBB_x86_64||__TBB_x86_32` with a generic `yield()` fallback, and
       `src/tbbmalloc/frontend.cpp`'s `highestBitPos` gates its x86 `bsr`/ARM `clz` asm
       the same way, falling through to a portable lookup table — confirmed by actually
       building it (`cmake --build`, no flags) under `docker run --platform
       linux/riscv64 quay.io/pypa/manylinux_2_39_riscv64` via QEMU, which compiled clean
       to a working `libtbb.so`/`libtbbmalloc.so` with no source changes.
     - **A dependency-detection library that degrades to "skip" rather than "fail" when
       its dependency is absent lets you narrow scope safely.** oneTBB's
       `src/tbbbind/CMakeLists.txt` does `if (NOT TARGET ${REQUIRED_HWLOC_TARGET})
       ... return()` per hwloc variant — no `hwloc-devel` in the container means
       `libtbbbind*.so` (NUMA-topology binding) is silently not built, not a failed
       configure. Building it anyway would add a dynamic `libhwloc.so` dependency
       outside manylinux's baseline (Intel's own wheel avoids this by statically
       linking three separate hwloc versions into three `libtbbbind_*.so` variants) —
       dropping the optional feature is the manylinux-safe choice over chasing parity.
     - **`GNUInstallDirs`-based CMake defaults `CMAKE_INSTALL_LIBDIR` to `lib64` on an
       RPM-family image** (the Rocky-Linux-based manylinux images), silently moving
       `cmake --install`'s output out from under a hardcoded `install/lib/` collection
       step — pass `-DCMAKE_INSTALL_LIBDIR=lib` explicitly when the packaging step
       assumes one path.
     - **To reproduce a `SONAME`-versioned library's flat `libfoo.so`/`libfoo.so.N`/
       `libfoo.so.N.M` trio as independent files inside a wheel (`cp` symlinks don't
       survive zip/cross-OS extraction the way upstream's own wheel ships them), use
       `cp -L` to dereference each name onto its real content** rather than copying the
       CMake-installed symlink chain as-is.

273. **A pinned transitive crate can lack riscv64 support outright, and `cargo check
     --target` (no cross-linker needed) finds it cheaper than gotcha 182's full
     `cargo build --release` (the mitmproxy-wireguard case).** mitmproxy-wireguard
     0.1.23 (archived upstream, PyPI's last release, superseded by the already-ported
     mitmproxy-rs, PR #962) pins `boringtun = "0.5"` in its released sdist's checked-in
     `Cargo.lock`, which resolves to `ring v0.16.20`. ring 0.16's `build.rs` hand-lists
     which target architectures get an assembly-optimized crypto backend; riscv64 isn't
     on that list, and the lookup that should return "no asm, fall back" instead
     `unwrap()`s a `None` and panics: `cargo check --target riscv64gc-unknown-linux-gnu`
     failed with `thread 'main' panicked at .../ring-0.16.20/build.rs:358:10: called
     'Option::unwrap()' on a 'None' value` — a hard wall, not a missing toolchain flag.
     ring didn't gain riscv64gc support until 0.17; mitmproxy-rs's own `Cargo.lock`
     (the actively maintained successor) resolves `boringtun 0.7.1` → `ring 0.17.14`,
     which is exactly why that port succeeded where this one cannot without forking the
     unmaintained 0.5.x/0.16.x pin ourselves — out of proportion for an archived
     predecessor with a maintained, already-ported replacement.
     - **`cargo check --target <riscv64 triple>` alone (with `rustup target add
       riscv64gc-unknown-linux-gnu`) is enough to hit this** — unlike gotcha 182's
       pre-flight, which needs a real cross-linker (`gcc-riscv64-linux-gnu`) and
       `PYO3_CROSS`/`pyo3/extension-module` because it links a working `.so`, a
       `build.rs` panic during dependency resolution surfaces at the *check* stage,
       before any linking, so no cross-linker install is needed to catch it. Reach for
       the full `cargo build --release --features pyo3/extension-module` link-level
       check (182) only once `cargo check` is clean.
     - **Distinct from gotcha 248's Python-ABI wall.** A native `cargo check`/`cargo
       check --target` against both a stock and a free-threaded CPython (via
       `PYO3_PYTHON=.../python3.14t`) built cleanly here — `pyo3 0.18.2`'s
       `abi3-py37` feature makes the crate version-independent of the linked
       interpreter, so the Python ABI was never the blocker. The wall was purely in a
       transitive Cargo dependency's own architecture support, invisible to any
       `Requires-Dist`/PyPI-classifier check (compare gotcha 249's build-time-only
       Python dependency — same "invisible to the obvious check" shape, one layer
       further down in the native dependency graph instead of the Python one).

276. **A hand-written-SIMD C library that looks x86/aarch64-only can still have a
     genuine, full-featured portable-C fallback reachable through a plain Makefile
     variable, not just through the autotools/CMake arch-detection path (the isal
     case; see `build-isal.yml`).** ISA-L's `igzip`/`crc`/`erasure_code` units are
     built almost entirely from `.asm` files under per-arch `x86_64/`/`aarch64/`
     directories, which reads as "riscv64 has nothing to build with". But
     python-isal's `setup.py` drives ISA-L through `Makefile.unx`, not
     `configure.ac`/CMake, and `make.inc` has an unconditional catch-all: `ifeq
     ($(filter aarch64 x86_%,$(host_cpu)),) host_cpu=base_aliases endif`. Any
     `uname -m` that isn't `aarch64` or `x86_*` — riscv64 included, with zero
     riscv64-specific code anywhere in this vendored version — silently switches
     the source list to `igzip_base.c`/`crc_base.c`/`ec_base.c` (unconditionally
     compiled for every arch already) plus a thin `*_base_aliases.c` file that
     wires the public entry points straight to the `_base` implementations
     (`isal_deflate_body` -> `isal_deflate_body_base`, etc.) — a real, complete
     deflate/CRC/erasure-code implementation, not a stub, and the same mechanism
     upstream already ships for ppc64le, and ppc64le is far from the only proof:
     Debian unstable already builds `libisal2` for riscv64 from the same base.
     - **Two checks settle it without a CI cycle**: grep the vendored Makefile
       tree for the *fallback* variable name (`base_aliases`, `generic`, `noarch`,
       `scalar` — whatever this project calls it) in addition to the per-arch
       dispatch names, and diff the "always built" (`lsrc +=`) source list against
       the per-arch (`lsrc_x86_64 +=`, `lsrc_aarch64 +=`) ones — if the
       always-built list already contains a working implementation and the
       fallback source list is just a dispatch shim onto it, the arch gap is
       cosmetic, not structural. Confirm with `grep -l
       'immintrin\|emmintrin\|_mm_\|arm_neon'` over the fallback and
       always-built files: none found means no x86/ARM intrinsics leaked into
       the "portable" path.
     - **A native QEMU rehearsal is cheap enough to run before writing the
       workflow, not just after** (extends gotcha 101 from aarch64 to riscv64
       directly): `docker run --platform linux/riscv64
       quay.io/pypa/manylinux_2_39_riscv64` built ISA-L, built the wheel, and
       ran upstream's real pytest suite (228 passed, 6 skipped, 0 failures) in
       well under the time a real riscv64 CI job
       would have taken — full proof of correctness, not just "it compiles",
       before any CI cycle was spent.

284. **A package whose C/C++ extension calls CUDA/HIP/cuFile is not automatically
     GPU-blocked — check whether those calls are resolved at build time (linked
     against a CUDA toolkit) or at runtime (`dlopen`/`dlsym`) before assuming the
     port needs a GPU host to even compile (the fastsafetensors case; see
     `build-fastsafetensors.yml`).** fastsafetensors' pybind11 extension calls
     `cudaMemcpy`, `cudaHostAlloc`, `cuFileRead`, etc., and even ships a HIP/ROCm
     mirror of the same API — reading like a hard CUDA/ROCm build dependency. But
     `fastsafetensors/cpp/gpu_compat.h` documents the actual design: "All GPU
     functions are loaded at runtime via `dlopen()`/`dlsym()` — no CUDA or HIP
     headers are included and no GPU runtime library is linked at build time." The
     extension defines its own minimal `cudaError_t`/`cudaMemcpyKind`/etc. types in
     `ext.hpp` instead of including `cuda_runtime.h`, and `load_library_functions()`
     tries `dlopen("libcudart.so")` then `dlopen("libamdhip64.so")` at import time,
     falling back to a CPU-only stub table (`cpu_cudaMemcpy` = `memcpy`, etc.) when
     neither is present — so `is_cuda_found()`/`is_hip_found()` legitimately return
     `False` on a GPU-less riscv64 CI runner instead of failing.
     - **Two greps settle it without burning a CI cycle**: `grep -rn
       '#include.*cuda_runtime\|#include.*<hip/hip_runtime' <ext dir>` (a real
       compile-time dependency needs the toolkit's own headers) and `grep -rn
       'dlopen\|dlsym' <ext dir>` (present alongside CUDA/HIP symbol names is the
       runtime-detection tell). No CUDA/HIP includes plus a `dlopen` table pointed
       at `libcudart.so`/`libamdhip64.so` means the build never touches a GPU
       toolkit; a `local_validation` `pip wheel .` on a GPU-less host that succeeds
       and whose smoke test asserts only `isinstance(is_cuda_found(), bool)` (not
       `is True`) confirms it before writing the workflow.
     - This is the inverse of gotcha 40/187's conda/CUDA wall: those catch a
       dependency that genuinely cannot resolve without a GPU-built channel;
       this one catches the opposite mistake — assuming CUDA symbols anywhere in
       a `.cpp`/`.h` file make the *build itself* GPU-blocked, when the runtime
       merely offers to accelerate on a GPU if one happens to be present.

303. **A "Python 2 only" classifier is a stop sign the project's own `setup.py` may
    already act on — check what it installs for the interpreters actually in scope
    before reading anything else (the subprocess32 case).** subprocess32's PyPI
    metadata is unambiguous before any download: `Programming Language :: Python ::
    2 :: Only`, classifiers list only 2.6/2.7, and the only Linux wheel is
    `subprocess32-3.5.4-cp27-cp27mu-manylinux2014_x86_64.whl` plus an sdist —
    nothing this repo's cp312/cp313/cp314/cp314t matrix could ever install as a real
    build. Reading the sdist confirms *why* there is nothing to build, not just that
    PyPI never published it: `setup.py`'s `main()` branches on
    `sys.version_info[0] == 2` — only there does it declare the
    `_posixsubprocess32` `Extension` and wire up the `./configure`-driven
    `build_ext`. The `else` branch (every Python 3) installs zero extensions and
    instead packages `python3_redirect/__init__.py`, whose entire body is
    `sys.modules['subprocess32'] = subprocess` — a compatibility stub so code
    importing `subprocess32` under Python 3 transparently gets the stdlib module.
    `python_requires='>=2.6, !=3.0.*, !=3.1.*, !=3.2.*, <4'` looks like real 3.x
    support; it only buys the redirect shim.
    - **The redirect shim closes the riscv64 "gap" before a workflow could open
      one.** `pip install subprocess32` on riscv64 today already builds this sdist
      in under a second (pure Python, no compiler, `Root-Is-Purelib: true` on
      Python 3) and produces a working `subprocess32` that *is* the interpreter's
      own `subprocess`. Publishing a `manylinux_riscv64` wheel for cp312+ would
      ship exactly that redirect under an arch tag — zero arch-specific content, on
      a version of Python the C extension never targets. This is gotcha 24/27's
      "nothing is compiled" shape, but for a *specific, known-in-advance
      interpreter range* rather than inferred from a wheel's ABI tag — the
      classifier and `setup.py` branch tell you before you'd even need to check
      `unzip -l` or `WHEEL`.
    - **The classifier is the cheapest of the two checks, not a substitute for
      it.** `Programming Language :: Python :: 2 :: Only` on
      `pypi.org/pypi/<pkg>/json` settles feasibility against a `cp312+`-only repo
      in one HTTP read; reading `setup.py`'s version branch is the confirmation
      that the reason isn't merely "upstream hasn't gotten around to a 3.x wheel"
      but "there is no 3.x extension to build, by design, forever." Report
      `not-feasible`/`parked` — the redirect module is genuinely correct behavior
      to preserve, not a bug to patch around by forcing the C extension to build
      under Python 3.

310. **A package's algorithmic pedigree does not describe its current toolchain —
    check the actual sdist/repo tree before assuming a compiler is needed (the
    quadprog case).** quadprog's docstring and README still credit "the
    Goldfarb/Idnani dual algorithm", the same numerically-stable QP method whose
    reference implementation is classic Fortran, and older forks of this package
    did indeed f2c-translate that Fortran and wrap it with Cython — a real reason
    to expect `gfortran` on the build image. `tar tzf quadprog-0.1.13.tar.gz` (or
    the `quadprog/quadprog` GitHub tree at the release tag) tells a different,
    current story: the package ships hand-ported `linear-algebra.c`,
    `qr-update.c` and `solve.QP.c` next to a plain `quadprog.pyx` that takes typed
    memoryviews (`double[:, :] G`) with no `cimport numpy`/`np.import_array()` —
    so the build needs only a C compiler and Cython, nothing numpy-C-API-shaped
    and no Fortran toolchain at all.
    - **The tell is absence, not presence.** Grepping the extracted sdist (or the
      GitHub tree) for `*.f`/`*.f90`/`*.pyf` and finding none is the whole check —
      cheaper than reasoning from the algorithm's academic history or from what a
      same-named package once needed. Do this before reaching for gfortran
      precedent (`build-scs.yml`'s OpenBLAS `gpl_sources` job): a pure-C/Cython
      port needs neither the compiler nor the `libgfortran` GPL-sources job that
      comes with linking a Fortran-built BLAS.

311. **A transitive crate's `compile_error!` gated on `target_feature` (not
    `target_arch`) means there is no scalar fallback to find — stop looking
    before proposing a patch (the polars-hash/gxhash case).** Gotcha 273's
    lesson is "check whether a pinned transitive crate has gained riscv64
    support in a newer release"; gotcha 276's is "check whether an
    apparently arch-gated build still has a real portable-C path reachable
    another way." Both assume the crate is *capable* of running without the
    missing arch-specific code, just not wired up for it yet. `gxhash` (used
    unconditionally, no Cargo feature gate, by `polars_hash::expressions` to
    implement the public `nchash.gxhash32/64/128` Polars expressions) is a
    different shape: its only two platform modules are `x86.rs`
    (`cfg(target_arch = "x86"/"x86_64")`) and `arm.rs`
    (`cfg(target_arch = "arm"/"aarch64")`), and `x86.rs` itself opens with an
    unconditional `#[cfg(not(any(all(target_feature = "aes", target_feature =
    "sse2"), docsrs, doc)))] compile_error!{"Gxhash requires aes and sse2
    intrinsics..."}` — proof the crate has never had a portable/scalar path on
    *any* architecture, x86 included without AES-NI: every hash step is a
    direct call to a hardware AES intrinsic
    (`_mm_aesenc_si128`/`_mm_aesenclast_si128` or the ARM crypto-extension
    equivalent). Confirmed no fix exists to wait for: the crate's own git
    `main` branch (two years of history past the last crates.io release) still
    has only these two platform files, and the downstream project's issue
    tracker and unreleased `Cargo.toml` still pin it unconditionally. Because
    the downstream test suite hardcodes exact expected hash values sourced
    from the reference PyPI `gxhash` package, even forking the downstream
    crate to add a `platform/riscv64.rs` would require a from-scratch,
    bit-exact reimplementation of AES-based hashing for an architecture whose
    vector-crypto extension (Zvkned) is itself new and not reliably present on
    generic riscv64 CI hardware — out of proportion to a small plugin port,
    and not a fix upstream could plausibly adopt. Verdict: `blocked-on-dependency`,
    not a patch candidate — the tell that separates this from gotchas 273/276
    is the `target_feature`-gated `compile_error!` itself, visible by reading
    the one platform source file the crate ships for the closest supported
    architecture.

318. **An explicit `python_requires` *upper* bound is a harder wall than an
    unsupported-on-newer-interpreters staleness signal, and it can mean the
    package's entire purpose was absorbed by the stdlib (the pickle5 case).**
    pickle5 backports PEP 574 (pickle protocol 5, `pickle.PickleBuffer`) for
    Python versions that predate it. Its `setup.py` hard-pins
    `python_requires='>=3.5, <3.8'`, and every one of its 12 releases
    (0.0.1-0.0.12) has published wheels only for cp36/cp37 — never cp38+, in
    over five years of releases. That upper bound isn't a maintenance gap
    like gotcha 248's typed-ast (which kept compiling past its stated ceiling
    until a real CPython internal-API removal stopped it) — `python_requires`
    is installer-enforced metadata, not an aspirational classifier, so `pip`
    refuses to even attempt the build on any excluded interpreter. And unlike
    gotcha 303's subprocess32 (whose `setup.py` redirects Python 3 to the
    stdlib module it shadows), pickle5 ships no compatibility shim at all for
    3.8+ — because none is needed: protocol 5 and `PickleBuffer` have been in
    the stdlib `pickle` module since Python 3.8 (confirmed importable on a
    plain Python 3.9 here), so every interpreter this repo could target
    already has upstream's feature natively. This repo's default matrix
    (cp312/cp313/cp314/cp314t, `workflow-anatomy.md`) has zero overlap with
    cp36/cp37, and deviating to build only cp36/cp37 wouldn't help — numpy's
    own floor is 3.12 so nothing else in the registry could use those wheels,
    and the manylinux riscv64 image/runners (`ubuntu-24.04-riscv`) don't carry
    EOL Python 3.6/3.7 toolchains to build against regardless. `parked`, no
    worktree pushed.
    - **Read `Requires-Python` on `pypi.org/pypi/<pkg>/json` and diff it
      against this repo's interpreter matrix before anything else** — an
      upper bound that excludes the whole matrix is decidable from one HTTP
      read, cheaper than gotcha 248's "build it and see."
    - **Check whether the backported feature already shipped in the stdlib at
      or before this repo's floor interpreter.** A backport package for a
      now-stdlib feature, gated to versions before that feature landed, is
      `parked` by construction — not because the port is hard, but because
      every interpreter capable of consuming the wheel doesn't need it.

334. **A stdlib-absorbed backport can fail to build on a modern interpreter for a
    concrete, reproducible reason, not just stale metadata (the pysha3 case).**
    pysha3 backports `hashlib.sha3_*`/`shake_*` for Python < 3.6 by vendoring the
    exact C sources CPython later shipped as its own `_sha3` module; `sha3.py`
    only monkey-patches `hashlib` `if not hasattr(_hashlib, "sha3_512")` — a no-op
    on every interpreter since 3.6. Unlike gotcha 318's pickle5, pysha3's
    `setup.py` carries no `python_requires` upper bound and PyPI's classifiers
    (2.7/3/3.4/3.5) are merely stale, so the metadata check alone doesn't settle
    it — building is what does: `Modules/_sha3/backport.inc` does
    `#include "pystrhex.h"` for Python >= 3.5, and `pystrhex.h` is (and always
    was) a CPython-internal header under `Modules/`, never installed under
    `Include/` alongside `Python.h` — confirmed by actually building the sdist
    (`pip wheel . --no-deps --no-build-isolation`) against a real Python 3.12
    venv: `fatal error: 'pystrhex.h' file not found`. Upstream itself settled the
    question in November 2022 by deleting the entire tree down to a one-line
    `README.md` — "pysha3 has reached its end of life ... please use SHA-3
    functions from hashlib" — rather than leaving stale releases to bit-rot
    quietly. `parked`, no worktree pushed.
    - **A missing `python_requires` upper bound does not clear a backport** —
      still check whether the backported feature is in the stdlib at this
      repo's floor interpreter (gotcha 318), and if the metadata is ambiguous,
      settle it by actually building the sdist against a locally cached modern
      interpreter (`uv python list --only-installed`) before ruling either way.
    - **`#include` of a header from CPython's `Modules/` tree (not `Include/`)
      is a build-breaker on any standard `python3-dev`-style toolchain** — those
      headers are internal to the CPython build itself and are never installed
      for extension authors, regardless of interpreter version.
    - **An upstream repo emptied to a single deprecation-notice file is a
      stronger signal than an unmaintained-looking tag/issue tracker** — it's
      the maintainer affirmatively telling downstream not to build this anymore,
      not just silence.

335. **Gotcha 273 generalizes past `ring`'s missing-asm-backend case: a pinned
    embedded-engine crate can have *zero* riscv64 story at all, and the fact
    that a far newer release of the same crate has it doesn't help a version
    this old (the vl-convert-python case).** vl-convert-python 1.9.0.post1
    (source: the `vega/vl-convert` monorepo's `vl-convert-python` subdirectory
    — `jonmmease/vl-convert` is a stale fork, last pushed 2025-01, kept alive
    only as the crates.io homepage/repository metadata) wraps `vl-convert-rs`,
    which drives Vega-Lite→SVG/PNG/PDF rendering through a real, embedded
    Deno/V8 JS engine: `deno_core = "0.307.0"`, whose own `Cargo.toml` pins
    `v8 = "0.105.0"` (caret-compatible, resolving to 0.105.1 in the checked-in
    `Cargo.lock`). The GitHub Releases API for `denoland/rusty_v8` tag
    `v0.105.1` lists prebuilt static-lib assets for exactly five targets —
    `aarch64-apple-darwin`, `aarch64-unknown-linux-gnu`, `x86_64-apple-darwin`,
    `x86_64-unknown-linux-gnu`, `x86_64-pc-windows-msvc` — no riscv64 asset at
    all. Unlike gotcha 273's `ring`, there's no silent-fallback path: rusty_v8's
    `build.rs` does support building V8 from source when no prebuilt binary
    exists (`V8_FROM_SOURCE=1`), but its `target_cpu` GN-arg mapping in that
    same file only handles `aarch64`/`arm`/`i686`/`x86_64` — riscv64 falls
    through with no GN arg set at all, so the from-source path has nothing
    correct to build against either (`denoland/rusty_v8#1476`, "Failed to build
    V8 on riscv64", tracks this exact gap). Checking the *current* rusty_v8
    releases (as of this check, 2026-09) shows riscv64 prebuilt binaries do
    exist — but only from `v150.1.0` onward (published 2026-07-10), roughly 150
    releases and two years past the `0.105.1` this package is pinned to; even
    vl-convert's own unreleased `v2.0.0-rc5` is only at `deno_core = "0.411.0"`,
    still short of that riscv64-capable line. Closing the gap would mean
    bumping `deno_core`/`deno_runtime`/`deno_emit`/`deno_graph` across that
    whole span and likely adapting `vl-convert-rs`'s own V8-facing source — a
    fork-scale change to a third-party dependency chain, not a
    `patches/<pkg>/<version>/` fix. `parked`, no worktree pushed.
    - **"A newer release of the pinned crate supports riscv64" does not make
      the *pinned* version portable** — Cargo's own semver resolution
      (`^0.105.0` blocks `150.x`) means the fix has to land upstream in the
      package's own dependency bump, not in anything we can carry as a patch.
    - **When a crate ships prebuilt binaries per-target and also has a
      from-source fallback, check *both* before ruling on the fallback** — a
      `V8_FROM_SOURCE=1` escape hatch is not a real answer if the same
      `build.rs` has no architecture mapping to invoke it correctly for your
      target; grep the build script for the target's arch string, don't just
      confirm the escape hatch environment variable exists.
    - **An embedded JS/V8 engine (deno_core, boa, quickjs-ng's V8 rivals aside)
      is a stronger red flag than a "just Rust" dependency tree** — it pulls in
      an entire second build system (GN/ninja/depot_tools) whose own
      architecture support lags the Rust ecosystem by years, so check the
      engine crate's own per-target released-binary list before assuming
      "it's just cargo, it'll cross-compile."

338. **A package whose real PyPI wheels are produced by a *packaging fork*, not its own
    source repo, can hard-depend at runtime on a sibling package from that same packaging
    ecosystem — and that sibling can itself be the actual blocker (the eigenpy case).**
    `.queue.yml`'s `home`/`repo` for eigenpy point at `cmake-wheel/eigenpy`, not
    `stack-of-tasks/eigenpy` — that is correct, not a queue error: `gh api
    repos/cmake-wheel/eigenpy` shows it is a fork whose parent is `stack-of-tasks/eigenpy`,
    and upstream's own checked-in `pyproject.toml` (at the released tag) carries no
    `[build-system]` at all — it is a plain CMake project consumed via conda/robotpkg/apt,
    not something `pip wheel` can build. The fork's `pyproject.toml` is what actually
    produces the wheels PyPI publishes as `eigenpy`: `build-backend = "cmeel"`, and
    `project.dependencies` is `["cmeel-boost ~= 1.90.0"]` — confirmed against the live
    `info.requires_dist` on PyPI's JSON API, not just the fork's source. `cmeel-boost` is a
    *runtime* dependency (eigenpy's compiled `.so` links its Boost.Python shared libraries),
    not merely a build input, so `pip install eigenpy` cannot resolve on riscv64 until
    `cmeel-boost` itself has a riscv64 wheel somewhere.
    - **The "cmeel" ecosystem's own packages differ wildly in weight — check each one, don't
      assume the family is uniformly light.** `cmeel` itself and `cmeel-eigen` (Eigen is
      header-only) are both `py3-none-any` — zero riscv64 concern, already installable from
      public PyPI as-is. `cmeel-boost` is the opposite extreme: its sdist is a 4 KB
      `CMakeLists.txt` whose `ExternalProject_Add` downloads the *entire* upstream
      `boost_1_90_0.tar.bz2` from `archives.boost.io` and runs `./bootstrap.sh && ./b2
      link=shared python=3.X` with no `--with-libraries` filter — i.e. it compiles Boost's
      whole default library set, not just Boost.Python, once per interpreter. That is a
      build on the order of this repo's largest to date (libclang's from-scratch LLVM/Clang
      compile, ~10h) — plausibly portable (no architectural riscv64 blocker; Boost is
      ordinary cross-platform C++), but a full dedicated port of its own, which is exactly
      why `cmeel-boost` already carries its own separate `.queue.yml` entry rather than being
      something to inline into a dependent package's build.
    - **Per gotcha 125, "no wheel anywhere" is not automatically a stop — but a pip-resolvable
      sdist is not automatically a *reasonable* one either.** `cmeel-boost` would very likely
      build from its sdist inside a cibuildwheel container (proving the CI job could go
      green), but that same full-Boost compile would then re-run for every future end user's
      `pip install eigenpy` on riscv64 (no riscv64 wheel to resolve to), which most users'
      environments won't even have the toolchain for (CMake ≥ 4.0, a C++ compiler, numpy
      headers) — defeating the "simple index to install riscv64 wheels from" goal even on a
      green CI run. Treat this the same as gotcha 150's sibling-workflow check, inverted: a
      hard runtime dep on another *queued* package sequences this port behind that package's
      own, same as the k-means-constrained/ortools and cvxpy/sparsediffpy cases — status
      `blocked-on-dependency`, no PR, no worktree needed when the blocker is confirmed fully
      read-only (PyPI JSON + `gh api` + one sdist download, no checkout required).

340. **Gotcha 335 generalizes past deno_core/rusty_v8 to a second embedded-engine family: a
    Rust FFI crate that itself only *downloads* a prebuilt native core, never builds it, can
    leave riscv64 with no build path at all even though the wrapper crate is pure Rust (the
    livekit case).** `livekit` 1.1.16's real source is the `livekit-rtc` directory of the
    `livekit/python-sdks` monorepo, not a maturin/pyo3 project — its `pyproject.toml` uses
    `build-backend = "setuptools.build_meta"` and produces plain `py3-none-manylinux_*` wheels.
    The tell is `[tool.cibuildwheel] before-build = "pip install requests && python
    rust-sdks/download_ffi.py --output livekit/rtc/resources"`: `download_ffi.py` (in the
    `livekit/rust-sdks` submodule) fetches a prebuilt `livekit-ffi` shared library straight
    from GitHub Releases and never invokes `cargo build` at all — its own `--arch` argparse
    `choices` are `["x86_64", "arm64", "armv7"]`, no riscv64 entry exists at any level. That
    ffi library links `webrtc-sys`, whose `build.rs` does the same thing one layer down:
    `webrtc_sys_build::download_webrtc()` fetches a prebuilt `libwebrtc.a` per
    `{target_os}-{target_arch}-release` triple from the same repo's Releases (tag
    `webrtc-89d790b`) — `gh api repos/livekit/rust-sdks/releases/tags/webrtc-89d790b` lists
    only android-{arm,arm64,x64}, ios-{device,simulator}-arm64, linux-{arm64,x64},
    mac-{arm64,x64}, win-{arm64,x64}; no riscv64 asset anywhere.
    - **The `LK_CUSTOM_WEBRTC` escape hatch only relocates the problem, it doesn't solve it.**
      Producing a riscv64 `libwebrtc.a` to point it at means running LiveKit's own
      `.github/workflows/webrtc-builds.yml`, which drives `depot_tools`/`gn`/`ninja` against a
      Chromium-derived checkout (a `.gclient` `target_os` step) — a second, Chromium-scale
      build system, unlike anything else in this repo. That workflow's own matrix (checked at
      the `rust-sdks` submodule pin `2d9f01ab1e933a86a8a5c53805ee29ee58b9be1b`) covers only
      win/mac/linux/android/ios × {x64,arm64,arm} — LiveKit itself has never attempted a
      riscv64 WebRTC build, which is a stronger signal than gotcha 335's rusty_v8 case (whose
      `build.rs` at least *tried* to map an architecture and simply missed riscv64).
    - **Even a hand-built `libwebrtc.a` would not be enough on its own** — `webrtc-sys/build.rs`'s
      Linux-specific glue hardcodes exactly two architectures: `add_gio_headers()` panics
      `"unsupported arch"` for anything but `arm64`/`x64`, and `add_lazy_load_so()`'s prebuilt
      dlopen-shim objects (used for `libdrm`/`libva`/`libcuda` etc.) only exist under
      `src/lazy_load_deps_for/*/{x86_64-linux-gnu,aarch64-linux-gnu}/` — so a riscv64 build
      would also need new shim sources this crate has never shipped, on top of the WebRTC
      static library itself.
    - **A "just Rust" wrapper crate can still hide a Chromium-scale native dependency two
      layers down.** `livekit-ffi` and `webrtc-sys` both look like ordinary crates.io-shaped
      Rust — no `compile_error!`, no obviously exotic build step — until you read past their
      `download_ffi.py`/`build.rs` to find the actual native artifact is fetched from a
      GitHub Releases page whose asset list is the real portability ceiling, same lesson as
      gotcha 335's closing note but one layer removed (crate → downloader script → releases
      page, not crate → `build.rs` → releases page directly).
    - `blocked-on-dependency`, no worktree/branch opened — fully diagnosed read-only via
      `gh api` against `livekit/python-sdks` and `livekit/rust-sdks` (submodule pin
      `2d9f01ab1e933a86a8a5c53805ee29ee58b9be1b`) plus the real GitHub Releases asset list, no
      checkout required.

341. **A build-time transpiler binary from a *third* language ecosystem can block a port even
    when the extension itself is pure, portable C++ (the prophet/cmdstanpy/stanc3 case).**
    prophet 1.4.0's `python/pyproject.toml` has no exotic build backend —
    `build-backend = "setuptools.build_meta"`, `requires = [..., "cmdstanpy>=1.0.4"]` — and its
    wheels are `py3-none-<platform>` (gotcha 81's shape: a real compiled artifact under a
    no-ABI tag), not maturin/pyo3/Bazel. `python/setup.py`'s custom `build_py` command calls
    `cmdstanpy.install_cmdstan(version="2.37.0", ...)` unconditionally at wheel-build time
    (`STAN_BACKEND=CMDSTANPY` is the *only* supported backend since prophet ≥ 1.1 — the same
    `setup.py` raises `ValueError` if `PYSTAN` is requested), then compiles `prophet.stan` into
    `prophet_model.bin` using that freshly-installed CmdStan. CmdStan's own `make/stanc` rule
    makes `build:` depend on `bin/stanc$(EXE)`, downloaded as a **prebuilt OCaml binary** from
    `stan-dev/stanc3`'s GitHub Releases, keyed off `uname -m` via a fixed `ARCH_TAG` table
    (`aarch64→-arm64`, `ppc64le→-ppc64el`, `s390x→-s390x`, `armv7l→-armel`/`-armhf`); `riscv64`
    matches none of those branches, so `ARCH_TAG` stays empty and the makefile would fetch
    plain `linux-stanc` — an x86_64 ELF that cannot execute on riscv64. Confirmed against both
    the pinned `stan-dev/stanc3` release tag `v2.37.0` (cmdstan 2.37.0's `CMDSTAN_VERSION`) and
    the current `nightly` release (checked 2026-09-10): asset list is
    `linux-stanc`/`linux-arm64-stanc`/`linux-armel-stanc`/`linux-armhf-stanc`/
    `linux-ppc64el-stanc`/`linux-s390x-stanc`/`mac-*`/`windows-stanc` — no riscv64 asset has
    ever been published, on any release. Unlike the blocker, Stan Math's own vendored TBB
    (`lib/tbb_2020.3`, a plain copy not a submodule, using the pre-oneAPI classic Makefile
    build) is **not** the problem: `tbb_machine.h`'s `__linux__` branch checks
    `TBB_USE_GCC_BUILTINS && __TBB_GCC_BUILTIN_ATOMICS_PRESENT` *before* any architecture
    `#elif`, and `tbb_config.h` sets both unconditionally for `__TBB_GCC_VERSION >= 70000` —
    so any GCC ≥ 7 build (riscv64 manylinux images included) takes the portable
    `machine/gcc_generic.h` path, the exact same code already exercised by the existing
    x86_64/aarch64 wheels; a compiled Stan Math program is genuinely architecture-agnostic
    C++ here. The blocker is narrowly `stanc`: it is itself a nontrivial OCaml/`dune` project
    (menhir, ppxlib, and similar opam dependencies) with **zero riscv64 CI or release history**
    of its own — OCaml's compiler has had a riscv64 native-codegen backend since 4.12 and opam
    lists a `host-arch-riscv64` package, but that only proves the *language* can target
    riscv64 in principle; bootstrapping that toolchain from source and then building stanc3 —
    a separate upstream project this repo cannot patch or file against — would mean standing
    up a whole second, previously-untested build pipeline as a prerequisite, not narrowing an
    existing one (skill goal 2: workflows should be "cheap to add" evidence for upstream, not
    a novel cross-ecosystem bootstrap). `blocked-on-dependency`, no worktree/branch opened —
    diagnosed read-only via `gh api` against `facebook/prophet` (`v1.4.0`), `stan-dev/cmdstan`
    (`v2.37.0`), `stan-dev/stanc3` (`v2.37.0` and `nightly`), and `stan-dev/math` (the
    `58ad15b...` submodule pin resolved through `stan-dev/stan`'s own pin), no checkout
    required.
    - **A `py3-none-<platform>` wheel that embeds a *toolchain-downloaded* transpiler binary
      is a different risk shape than one that only embeds its own compiled C/C++** — grep the
      build backend for anything that shells out to install a *second* project's release
      asset (not just the package's own `Extension`/CMake/Bazel target), the same way gotcha
      335/340 taught checking two crate layers down for Rust.
    - **A vendored classic (pre-oneAPI) Intel TBB copy is not automatically an x86/ARM-only
      blocker** — `tbb_machine.h`'s unmatched-architecture fallthrough to
      `machine/gcc_generic.h`, gated only on a GCC-version check that's true for any modern
      compiler, makes it portable to any architecture GCC's `__atomic` builtins support;
      read the actual `#elif` chain before assuming a 2020-era vendored TBB needs a
      per-architecture port.
    - **"The language has a riscv64 backend" and "this specific project has ever been built
      for riscv64" are different claims** — OCaml/opam supporting riscv64 as a *host*
      architecture in the abstract doesn't mean stanc3's own dependency graph (menhir,
      ppxlib, etc.) has ever been exercised there; treat an ecosystem-level "yes" as a
      starting point for a feasibility spike, not as clearance to park the port on it.

342. **A proprietary shared library downloaded and *linked* by `setup.py` itself — not merely
    run after install (gotcha 157) or vendored as a git blob (gotcha 246) — fails closed on an
    unrecognised arch instead of degrading (the ibm-db case).** `ibm-db` 3.3.0's `setup.py`
    compiles a real C extension (`ibm_db.c`) against IBM's proprietary Db2 CLI driver
    (`library = ['db2']`), which it downloads at build time from
    `https://public.dhe.ibm.com/ibmdl/export/pub/software/data/db2/drivers/odbc_cli/<ver>/<cliFileName>`
    (falling back to a GitHub mirror, `ibmdb/db2drivers`, on failure) — the driver is a
    build-and-link-time dependency, not just a runtime one, so there is no "installs fine,
    fails at call time" middle ground like claude-agent-sdk's. The download filename is picked
    by an `if/elif` chain on `os.uname()[4]` (`ppc64le`, `ppc`/`ppc64`, `'86' in machine` for
    x86/x86_64, `'390' in machine` for s390/s390x) with **no branch for `riscv64` or
    `aarch64`** — on either arch none of the `elif`s match, so `cliFileName`/`arch_` are never
    assigned and the next reference to them raises a bare `NameError`, not a clean
    "unsupported platform" message. Confirmed no riscv64 asset exists at any layer: the
    download server's top level and every one of its 9 versioned subdirectories
    (`v11.1.4` … `v12.1.4`) list only `{aix,linuxia32,linuxx64,macarm64,macos64,nt,ntx64,
    ppc32,ppc64,ppc64le,s390,s390x64,sun32,sun64,sunamd32,sunamd64}_odbc_cli.{tar.gz,zip}`,
    and the GitHub mirror fallback matches that list exactly. There is also no Linux ARM
    offering at all (only `linuxia32`/`linuxx64`), which is why PyPI's 3.3.0 wheels are
    `manylinux_2_34_{i686,x86_64}` only — zero `aarch64`, confirming the clidriver's own arch
    ceiling drives the published wheel matrix, not an unrelated packaging choice.
    `not-feasible`/`parked`: no source is available for `db2`/IBM's CLI driver (closed,
    IBM-distributed only) so gotcha 77's "build it yourself" escape hatch does not exist, and
    there is no open-source Db2 driver `ibm_db.c` could be relinked against without forking
    the C extension. No worktree/branch opened.
    - **A build-time arch `if/elif` chain with no `else` is worth reading for its failure
      mode, not just its coverage list** — a chain that silently leaves a variable unbound on
      an unmatched arch (vs. one that calls `_printAndExit` with a clear message) still proves
      the same "no riscv64 branch" fact, but is a much noisier first symptom if someone tries
      the build blind without checking the vendor's asset index first.
    - **When a wheel already exists for some architectures on PyPI but not others on the same
      OS (here: Linux x86/i686 but no Linux aarch64), treat that gap as a hint to check the
      *same* upstream-vendor blocker before assuming riscv64 is uniquely unserved** — it
      often means the real ceiling is a proprietary dependency's own arch list, which riscv64
      merely joins aarch64 in missing.

343. **A Bazel-built package can clear every dependency-tree check and still be blocked
    because its `WORKSPACE` links the extension directly against a *live, pip-installed*
    sibling package's compiled library, not just its headers (the
    tensorflow-io-gcs-filesystem case).** tensorflow-io-gcs-filesystem looked like gotcha
    132's territory: its own `WORKSPACE` pulls abseil/protobuf/grpc/BoringSSL/google-cloud-cpp
    as plain `http_archive` source builds, every one of which already has riscv64 precedent
    elsewhere in this repo. But `tools/build/configure.py` does `import tensorflow` and reads
    `tf.sysconfig.get_compile_flags()`/`get_link_flags()` from whatever `tensorflow` package
    is pip-installed on the build host, then `WORKSPACE`'s `tf_configure` repository rule
    (`third_party/toolchains/tf/tf_configure.bzl`) `cp -r`'s that package's *actual*
    `libtensorflow_framework.so` into `@local_config_tf`, and
    `tensorflow_io_gcs_filesystem/core/BUILD`'s `cc_library` lists that `.so` as a `srcs`
    entry — so the final `cc_binary(linkshared = 1, ...)` links against it directly. The
    symbols it needs (`TF_SetStatus`, `TF_Filesystem*Ops`, …) are real code in that library,
    not header-only declarations, so the linker needs an ELF for the *target* architecture,
    not just the text of a C header. Confirmed no riscv64 candidate exists at any layer: no
    `tensorflow*` wheel on PyPI or on this repo's own registry ships riscv64 (this repo's own
    `tensorflow` entry sits `parked`, undiagnosed, zero work started), and Google's official
    standalone libtensorflow C-library tarball has no riscv64 build either
    (`storage.googleapis.com/tensorflow/versions/<ver>/libtensorflow-cpu-linux-riscv64.tar.gz`
    → 404, confirmed against the working `linux-x86_64` URL). Producing one means
    bootstrapping full TensorFlow core via Bazel for riscv64 — a separate, much larger effort
    than jaxlib (PR #526, parked), which shares the same XLA/TSL stack at a fraction of
    TF-core's size and is itself still blocked on an upstream RISC-V codegen gap. Parked
    (`.queue.yml` `blocked-on-dependency`) rather than hand-rolling a synthetic stub `.so`
    with fabricated symbols: that would diverge completely from upstream's own build and
    produce an artifact nothing on riscv64 can actually load or test. No worktree/branch
    opened.
    - **"Does the dependency tree have riscv64 precedent" and "does the build link against a
      library that must already exist, compiled, for this exact architecture" are different
      questions** — gotcha 132/214 answer the first; this is the second, and a project mixing
      source-built third-party deps with a `pip install <sibling-project>`-sourced library
      (common in the TF/XLA/TSL ecosystem, where sub-packages configure against the parent
      framework's own build) can pass the first check cleanly and still fail the second.
    - **Grep the `WORKSPACE`/`tf_configure`-equivalent for what a repository rule actually
      copies (`cp`, `symlink`, genrule `srcs`) versus what it only reads as text** (header
      trees are portable; a `.so`/`.a`/`.lib` it also copies is not) before concluding a
      Google-ML-stack sibling package inherits gotcha 132's clean bill of health.

366. **A genuinely-compilable CMake C++ library can still be `not-feasible` when its kernel
    code is gated to specific SIMD ISAs with no portable/scalar fallback anywhere in the
    build (the embreex/Embree case).** embreex itself is a thin Cython binding that builds
    trivially; the blocker is the Embree ray-tracing kernel library it links against.
    embreex's own `before-build` step (`package/fetch-embree.py`) downloads Embree's
    prebuilt release archive, and RenderKit/embree's GitHub Releases publish
    `x86_64-linux`, `x86_64`/`arm64`-`macos`, and `x64`-`windows` only (confirmed against
    the real v4.4.0 release assets) — no riscv64, so building Embree from source is the
    only route in. Embree's own `CMakeLists.txt` platform detection recognizes exactly two
    families: `EMBREE_ARM` (Apple silicon, or `CMAKE_SYSTEM_PROCESSOR` == `aarch64`/`ARM64`)
    or, for everything else, `EMBREE_MAX_ISA` defaulting through to `SSE2`
    (`common/simd/sse.h` and friends use `__m128`/`_mm_*` intrinsics unconditionally outside
    the ARM branch). There is no third "generic"/"portable"/"scalar" option — unlike gotcha
    276's isal case, `EMBREE_MAX_ISA`'s own `STRINGS` property lists only
    `NONE NEON NEON2X` (ARM) or `NONE SSE2 SSE4.2 AVX AVX2 AVX512 DEFAULT` (everything else).
    riscv64 matches neither family, silently falls into the x86 SSE2 default, and fails to
    compile (`xmmintrin.h` doesn't exist for a riscv64-targeted GCC). Confirmed no RISC-V
    work exists anywhere upstream: `common/simd/` has an `arm/` shim
    (`sse2neon.h`/`avx2neon.h`) but no riscv equivalent, a GitHub code search across
    `RenderKit/embree` for "riscv" returns zero hits (both the v4.4.0 tag and current
    `master`), and Embree's own project site documents support for x86 (Linux/macOS/Windows)
    and ARM (macOS) CPUs plus Intel Arc GPUs only. Closing this gap would mean writing a full
    SSE/AVX-to-RVV translation shim covering the hundreds of intrinsics Embree's kernels use
    — a new engineering project for *upstream*, not a `patches/<pkg>/<version>/` fix — and it
    would not "closely mirror upstream's own CI, narrowed to riscv64" (goal 2: upstream has
    no riscv64 CI or code path to narrow). Parked (`.queue.yml`); no worktree/branch/PR
    created — resolved read-only from the real v4.4.0 `pyproject.toml`/`setup.py`/
    `package/fetch-embree.py`/`package/embree.json` (embreex) and the real
    `CMakeLists.txt`/`common/simd/*` (Embree).
    - **A CMake C++ port isn't cleared by "does it compile a real amount of code" (gotcha 41)
      alone — check whether the kernel-level code is SIMD-ISA-gated with no scalar/portable
      path**, the same way gotcha 276 checks a Makefile-driven library for a `base`/`generic`
      fallback variable: read the platform-detection block of the top-level `CMakeLists.txt`
      for an explicit non-x86/non-ARM branch, and check whatever cache variable selects the
      ISA for a `NONE`/`generic`/`portable` value in its own allowed-`STRINGS` list, before
      assuming "it's CMake, so it's portable".
    - **A vendored dependency fetched via a prebuilt-binary `before-build` step (gotcha 35's
      shape) can hide a *second*, deeper blocker even after deciding to build it from source
      instead**: the source itself can carry the same architecture ceiling as the binaries it
      normally downloads.

372. **Zero sdist ever published, plus a license that independently bars redistribution even
    if a riscv64 build existed, is a double lock, not one (the hdbcli case).** `hdbcli`
    2.29.27's PyPI project history — all 1352 files across every version, not just the
    latest — contains no `.tar.gz`/sdist at all, only platform wheels
    (`manylinux2014_{x86_64,aarch64,ppc64le}`, `musllinux_1_2_x86_64`, two macOS, two
    Windows); `home`/`repo` both resolve to `https://www.sap.com/`, a marketing page with no
    source host behind it. Each wheel's payload is not a vendored-and-called runtime (gotcha
    157) or a git-committed prebuilt blob linked at build time (gotcha 246) — it *is* the
    entire extension: a single 14 MB `pyhdbcli.abi3.so`, unstripped x86-64 ELF, alongside ~11
    KB of pure-Python glue (`hdbcli/dbapi.py` etc.). There is no `setup.py`/`pyproject.toml`
    build step to read and no C source to inspect, so gotcha 77's "build it yourself" escape
    hatch fails at the first step: there is nothing upstream ever published to build *from*.
    That alone would already be `not-feasible`, but the `LICENSE` shipped in
    `*.dist-info/licenses/` closes the second, independent door: the SAP DEVELOPER LICENSE
    AGREEMENT's IP clause (§2(a)) prohibits the licensee from "provid[ing] or mak[ing] the
    APIs, Tools or Software available to any third party", "creat[ing] derivative works of or
    based on the APIs, Tools or Software", and reverse-engineering them — so even a
    hypothetical riscv64 `pyhdbcli.abi3.so` obtained directly from SAP could not legally be
    rehosted on `pypi.riseproject.dev` as a rebuilt `hdbcli` wheel; the license, not just the
    missing source, forecloses this port. Confirmed by downloading the real
    `manylinux2014_x86_64` wheel from `files.pythonhosted.org` and inspecting its contents
    directly (`unzip -l`, `file pyhdbcli.abi3.so`, the bundled `LICENSE` text) rather than
    trusting the PyPI classifier (`License :: Other/Proprietary License`) alone. Parked
    (`.queue.yml`); no worktree/branch/PR created — there is no buildable artifact to stage a
    workflow around.
    - **A generic vendor homepage (`https://<company>.com/`) in `home`/`repo` is itself a
      signal worth checking early** — a real open-source project's PyPI metadata almost
      always points `repo` at the actual source host; a corporate marketing URL in both
      fields together with zero sdists across the *entire* release history (not just the
      pinned version) is enough to suspect a closed-source vendor drop before even opening a
      wheel.
