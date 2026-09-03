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
