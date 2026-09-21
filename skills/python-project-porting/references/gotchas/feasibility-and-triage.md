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
- **376** — A permissive `License:` field on the wrapper package says nothing about whether
  the payload it ships has any source at all — check the binary's own content, not the
  metadata's license family (the tableauhyperapi case).
- **411** — A GPU-first package is not CUDA-blocked when its own build system makes the CPU
  backend the *default* — read the backend selector and diff the per-platform wheel sizes
  before parking it (the bitsandbytes case).
- **381** — A third-party *vendor release* of a project this repo has already ruled out
  inherits that verdict — resolve the redistribution to its upstream before triaging anything
  else (the tokenspeed-triton case).
- **382** — Several PyPI distributions carved out of *one* build are one unit of work, not
  one port each — check the allowed `--build-type` values before writing any YAML, and let
  `requires_dist` (not the most "core-sounding" name) fix the order (the
  pyside6/-essentials/-addons case).
- **383** — The *umbrella* distribution of a split family carries no compiled code at all,
  gets its platform+`abi3` tag from a deliberately fake `Extension`, and its payload is
  generated stubs for the union of its siblings' modules — so it cannot be cut from a
  different build than they were (the pyside6 meta-wheel case).
- **385** — A no-sdist vendor wheel can still have a fully public build recipe — read
  `dist-info/WHEEL`'s `Generator:` before parking it for "no source anywhere"; a
  vendor-named generator is usually a *repackager*, which moves the stop to whether the
  vendor publishes the payload for our arch (the pyqt6-qt6 case).
- **386** — A GPU-only package can be small, source-open and blob-free and still be
  unportable: in a JIT kernel library the compiled part is a few-hundred-KB shim, so gotcha
  41's vendor-payload tell is absent and the wall is what that shim links — `libtorch_cuda.so`,
  which our CPU-only riscv64 torch can never provide (the humming-kernels case).
- **387** — A GPU-toolkit-suffixed distribution name (`-cuda12x`, `-rocm-7-0`) is a toolkit
  selector whose name can come from a *separate* release-tools repo, and a documented
  stub/no-CUDA build mode is a docs build, not a port (the cupy-cuda12x case).
- **388** — The queue entry's wheel shape is a snapshot — re-read the *latest* release's tag
  set first, because upstream can delete the arch-specific payload and erase the gap outright
  (the tokenspeed-mla case).
- **392** — With no project URL and a stock `Generator:`, the *conda-forge feedstock* is the
  cheapest source-availability oracle; and `readelf -S` splits a real compiled extension into
  engine vs embedded-model-weights in one command (the livekit-local-inference case).
- **405** — An NVIDIA-owned, profiler-adjacent package can have no CUDA dependency whatsoever
  — read the extension's header set and `libraries=` list before filing it with the GPU batch
  (the nvtx case).
- **407** — An upstream recipe can stop being conda-based between releases, so read it at the
  *newest* tag before pricing a port or recording a conda blocker (the cadquery-ocp-novtk
  case).
- **418** — An upstream wheel for *another* non-x86 architecture is only a precedent for the
  parts of it that are actually that architecture — `readelf -h` every `.so` in it (the
  paddlepaddle case).
- **419** — Gotcha 411's "is the CPU backend the default?" test can pass and still not yield a
  port: the non-CUDA branch of a torch extension can compile operator *schemas* with no
  implementations, so the build succeeds and the wheel is a dead stub (the xformers case).
- **426** — A `-cpu` sibling can be an *x86_64-only label* rather than a portable CPU variant:
  where the base package's wheel is already CPU-only on every non-x86 arch, the sibling name
  closes no gap and inherits the base's park (the tensorflow-cpu case).
- **431** — A distribution that has never shipped an sdist leaves the wheel as the only
  evidence: `strings -a` the vendored blob and its builder paths (`/.conan/data/…@vendor/prod`)
  prove a closed vendor with no public source (the livekit-plugins-noise-cancellation case).
- **436** — A project's whole non-x86 story can be one `uname -m == aarch64` boolean, and an
  `aarch64` branch is only as portable as the dependency behind it — survey every site of the
  boolean, then triage the one whose branch works only because that dep ships an ARM SIMD shim
  (the Open3D case).
- **438** — A "redistributable `<vendor binary>`" distribution can repack a vendor blob on some
  OSes and build from source on the one that matters, so decide gotcha 35/157/431 per OS; plus the
  depot_tools/gn/CIPD riscv64 readiness check and the two CIPD gaps `custom_deps` removes (the
  comfy-angle/ANGLE case).
- **442** — A vendored dependency's *build system* can silently omit a capability flag its other
  build system defaults on, and only auditing every dispatch site (not just "does it build")
  proves which one actually shipped (the mediapipe/XNNPACK case).
- **449** — A prebuilt riscv64 binary an upstream downloads for you can be built for a *vendor*
  ISA: `file`/`e_machine 243` says it is riscv64, not *which* riscv64 — read `Tag_RISCV_arch`
  and count CUSTOM-opcode instructions too (the openvino/oneTBB T-Head case).
- **450** — A vendored native payload can be a *GraalVM Native Image* (AOT-compiled Java), which
  moves the wall from "is there source?" to "does the AOT toolchain target riscv64?" — and an
  arch enum in the toolchain's own code is not shipping support (the saxonche/SaxonC-HE case).
- **452** — A GPU-only package can enforce the GPU from its *pure-Python* `__init__.py`, through a
  driver-probe module that has no CUDA linkage of its own — so the first `readelf -d` is
  misleading, and a documented CUDA-free build flag upstream never ships rescues nothing
  (the pynvvideocodec case).
- **453** — A closed commercial engine is not one build recompiled per arch: each arch statically
  links a *different* proprietary math kernel, and the x86_64↔aarch64 wheel-size gap names which
  one — so "the vendor would just have to rebuild" is wrong (the gurobipy case).
- **459** — A CUDA-only PyPI wheel does not make the *project* CUDA-only: a
  device-selecting build env var can produce a genuinely portable CPU distribution from the
  same tree, and upstream may already carry riscv64 kernels for it (the vllm case).
- **462** — A `<pkg>-core` split sibling is still its own port after the main package shipped
  in the *non-split* shape: the self-contained wheel closes the Python gap but not the
  native-consumer one, and the missing piece is two tiny files (the sherpa-onnx-core case).
- **464** — A full `cpXY-cpXY-<platform>` tag can be fabricated with no extension module at
  all, by a `Distribution.has_ext_modules()` that hardcodes `True`; and the payload behind it
  can be a *foreign-language runtime* the package only shells out to, whose arch fallback
  quietly produces a wheel with no arch-specific content (the artifacts-keyring case).
- **465** — A closed vendor accelerator blob can be *full* of `riscv` strings and carry a whole
  LLVM RISC-V backend while shipping x86_64-only wheels, because the ISA runs on cores inside
  the accelerator; registered LLVM targets and device-side proto paths tell the two apart (the
  libtpu case).
- **467** — Gotcha 341's foreign-ecosystem code generator, one step harder: when the generator
  runs at *runtime* over arbitrary user input rather than at build time over fixed input, the
  "pre-generate the output on x86_64 and vendor it as a patch" escape hatch cannot exist at
  all (the httpstan/stanc3 case).
- **470** — A `.queue.yml` note reading `abi: 0` is a wheel *build tag*, not an ABI tag — and
  for a co-installed-prefix ecosystem one released wheel's `readelf -d` enumerates the whole
  chain of ports that must land first (the pin/pinocchio case).
- **471** — A GPU package's architecture axis is bounded by its *accelerator vendor's* toolkit
  axis, so a freshly added aarch64 wheel is not a sign riscv64 is next; and a forced-platform
  env var whose accepted values name three GPU vendors is not gotcha 459's rescue (the
  torch-memory-saver case).
- **475** — When a package vendors a whole database engine, the architecture review can come
  out *green* and the port still be unaffordable: price it in ninja edges × this fleet's
  measured per-edge cost, check whether the build runs twice, and remember that an upstream
  arch port living inside `if (CMAKE_CROSSCOMPILING)` gives a native build none of its
  accommodations (the chdb-core/ClickHouse case).
- **476** — A CMake project whose CI submits to CDash publishes its own build cost per
  platform, so a from-source C++ port can be priced before booking a runner — and the
  per-language rows say whether the interpreter leg is cheap (the simpleitk/ITK case).
- **478** — Gotcha 343's "revisit once `<dep>` is ported" escape hatch does not apply when
  the blocked project is *archived*: its dependency pin is frozen on a historical window,
  so unblocking needs an old version of the dep nobody would port, and that window's own
  interpreter coverage can miss this repo's matrix entirely (the tensorflow-addons case).
- **480** — A non-NVIDIA accelerator vendor can hide its toolkit behind `dlopen`, leaving
  `readelf -d` clean, and the CPU backend its CMake advertises can be stamped `+cpu` by
  upstream's own `setup.py` — a build mode that renames the artifact cannot produce the
  queued version (the memfabric-hybrid / Huawei Ascend case).
- **481** — A `[tool.poetry.build] script` makes poetry-core stamp a full
  `cpXY-cpXY-<platform>` tag whatever the script does, and compiling gettext catalogs is the
  commonest reason — the release history dates the fabricated tag (the jsonschema2md case).
- **483** — Gotcha 125's "the dependency builds from sdist, so it is not a blocker" has to be
  *executed*, and the bar is the end user's `pip install`, not a green CI job: a sibling whose
  vendored `CMakeLists.txt` is below CMake 4's floor fails from sdist, and the environment
  variable that rescues it in CI does not travel with the published wheel (the cmeel-urdfdom
  case).
- **484** — A large C++ project with its own architecture abstraction layer concentrates the
  whole port into a handful of `#error` gates in that one directory — and the build config
  the *wheel* uses decides how many of them you ever reach (the usd-core/OpenUSD case).
- **492** — A declared dependency the build never actually links against still blocks the
  port, because pip enforces metadata and not linkage — prove which it is with the wheel's
  own `.pc`/`readelf` output, then block anyway (the cmeel-assimp/cmeel-zlib case).
- **503** — Triage a framework's closure by each node's *own published artifacts*: the
  same-org siblings that look like the native core can be `py3-none-any` while the leaves
  block, an exact `==` pin makes an already-ported package a blocker at the *version* level,
  `--only-binary` resolvers false-positive on sdist-only pure Python, and an sdist with zero
  native sources can still be unbuildable (the angr case).
- **505** — A cmeel note's build number need not be `0`, and `abi: 4,5` means one version was
  packaged twice: build the highest `.cN` tag, never an assumed `.c0`.
- **506** — Gotcha 263's "closed wheel, open project inside" rescue is per *package*, not per
  vendor: before reusing it on another Intel oneAPI wheel, check that the version maps to an open
  tag and that the *largest* payload's `DT_NEEDED` list stays inside that open project (the
  intel-openmp case).

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

373. **A binding whose own C-extension source is fully open can still be `not-feasible` when
    the thing it `dlopen()`s at runtime is proprietary, has zero source anywhere, and has no
    riscv64 build at the vendor, official or unofficial (the cx_Oracle case) — a third shape
    past gotcha 157/183's "vendored inside the wheel" and gotcha 342's "linked at build
    time".** cx_Oracle 8.3.0's extension is cx_Oracle's own BSD-licensed glue plus a vendored
    copy of ODPI-C (dual Apache-2.0/UPL, `odpi/` in the sdist) — read `setup.py` and
    `odpi/src/dpiOci.c` directly rather than assume from the "wraps Oracle" reputation:
    `dpiOci.c` self-declares every OCI type/function prototype it calls (no Oracle SDK
    headers needed to compile) and reaches `libclntsh.so*` only via `dlopen()`/`dlsym()` at
    runtime — nothing is bundled or downloaded into the wheel at all, the same shape as
    psycopg2 expecting the user to supply `libpq`. So the wheel itself builds and imports
    cleanly on any arch, riscv64 included, with zero proprietary bytes anywhere in it. The
    permanent blocker sits one layer out: every real operation (`connect()` and everything
    after) needs Oracle Instant Client's `libclntsh.so`, which is closed-source with no
    source ever published, and Oracle's own Instant Client download pages list only Linux
    x86-64, Linux x86-32, Linux ARM (aarch64), Windows x64, and macOS ARM64 — no riscv64 at
    any client version, official or unofficial (unlike playwright's Node.js driver, gotcha
    183, there is no third-party rebuild possible either, because there is no open Instant
    Client to rebuild from). Same verdict as playwright: installable and importable, but
    non-functional for its entire purpose on riscv64, with no patch or build-from-source
    escape hatch (gotcha 77 does not apply — there is nothing to build). Also unlike
    mssql-python-odbc/hdbcli (gotchas 342/372), the *binding* here has real, open, portable
    source; only the vendor runtime it dlopens at call time is the dead end. Parked
    (`.queue.yml`); no worktree/branch/PR — confirmed read-only against the real 8.3.0 sdist
    (`setup.py`, `odpi/src/dpiOci.c`, `LICENSE.txt`) and Oracle's live Instant Client
    download/documentation pages.
    - cx_Oracle 8.3.0 was itself Oracle's last release of this package before folding into
      `python-oracledb`, which added a pure-Python "thin mode" speaking the Oracle Net
      protocol directly and needing no Instant Client at all — a real riscv64 path exists
      in the ecosystem, just not in this legacy binding; that successor package is a
      separate `.queue.yml` candidate, out of scope here.

376. **A permissive `License:` field on the wrapper package says nothing about whether the
    payload it ships has any source at all — check the binary's own content, not the
    metadata's license family (the tableauhyperapi case).** Gotcha 372's hdbcli reasoning
    pairs "zero sdist" with a *restrictive* bundled EULA as a double lock; tableauhyperapi
    is the inversion that still ends `parked` even though the second lock is absent.
    `tableauhyperapi` 0.0.26359's `dist-info/METADATA` declares `License: Apache-2.0` and
    ships a plain, unmodified Apache-2.0 `LICENSE` file — nothing here bars redistribution
    the way SAP's DEVELOPER LICENSE AGREEMENT does. Downloading and unzipping the real
    89 MB `manylinux2014_x86_64` wheel shows why that doesn't matter: its payload is not a
    compiled Python extension at all but two prebuilt native artifacts —
    `tableauhyperapi/bin/hyper/hyperd` (255 MB uncompressed, a stripped x86-64 PIE ELF —
    Tableau's proprietary in-process "Hyper" database engine, launched as a subprocess by
    `hyperprocess.py`) and `tableauhyperapi/bin/libtableauhyperapi.so` (43 MB, stripped
    x86-64 ELF, `dlopen()`'d directly in ABI mode: `impl/dll.py` does
    `lib = ffi.dlopen(str(find_hyper_api_library()))`, and `impl/cdef_compiled.py` is only
    cffi type declarations, not C source — gotcha 116's ABI-mode signal, but here there is
    no API-mode alternative anywhere to fall back to). There is no `setup.py`/
    `pyproject.toml` build step and zero sdist across the *entire* PyPI release history —
    152 files across all 46 versions ever published, confirmed via the full releases JSON,
    every one a wheel — so gotcha 77's "build it yourself" escape hatch fails at the first
    step exactly as it does for hdbcli, just without hdbcli's license-side reinforcement.
    The bundled `HYPER_API_OSS_disclosure.txt` lists ~40 third-party OSS components
    compiled into `hyperd` (abseil, Arrow, LLVM 22.1.7, PostgreSQL, protobuf, zstd, ...)
    but conspicuously never lists the Hyper engine's own core code — the Apache-2.0 grant
    covers the wrapper and lets those dependencies' licenses pass through cleanly, it does
    not make the engine itself open source.
    - **Read the vendor's own hardware/system-requirements page, not just the PyPI wheel
      list, for the architecture verdict.** Tableau's installation docs
      (`tableau.github.io/hyper-db/docs/installation/`) state the requirement in as many
      words: "Intel Nehalem, Apple Silicon or AMD Bulldozer processor or newer" — x86_64
      and Apple-Silicon ARM64 only, no RISC-V, stated as policy rather than inferred from
      an absence. PyPI's own file list for 0.0.26359 corroborates it structurally:
      `macosx_10_11_x86_64`, `macosx_13_0_arm64`, `manylinux2014_x86_64`, `win_amd64` — no
      `manylinux*_aarch64` wheel exists either, so even Linux ARM64 users get nothing,
      let alone riscv64.
    - **A closed-source binary can still embed strings that look like architecture
      support and mean nothing of the kind.** `strings` on `hyperd` turns up hundreds of
      `riscv`/`aarch64` symbols (`llvm::RISCVVType`, `ELFLinkGraphBuilder_riscv`,
      `__aarch64_cas16_acq`, ...) — these are LLVM's own JIT backend code, compiled into
      Hyper because it uses LLVM to JIT-compile query plans, not evidence that Hyper runs
      on those host architectures. Grep for the vendor's *own* product code, not a vendored
      compiler toolchain's target list, before reading anything into a binary's strings.
    - Parked (`.queue.yml`); no worktree/branch/PR created — diagnosed read-only against
      the real 0.0.26359 wheel contents (`unzip -l`, `file`/`strings` on both native
      binaries) and Tableau's own installation/hardware-requirements documentation.

411. **A GPU-first package is not CUDA-blocked when its own build system makes the CPU
    backend the *default* — read the backend selector and diff the per-platform wheel
    sizes before parking it (the bitsandbytes case; see `build-bitsandbytes.yml`).**
    bitsandbytes reads as the archetypal GPU port: the repo is `.cu` kernels, the
    classifiers say `Environment :: GPU :: NVIDIA CUDA`, and the Linux wheels are
    23-43 MB of `libbitsandbytes_cuda1NN.so`. Its `CMakeLists.txt` nevertheless opens
    with `set(COMPUTE_BACKEND "cpu" CACHE STRING ...)`, and every `BUILD_CUDA`/`BUILD_HIP`/
    `BUILD_XPU` branch — including `enable_language(CUDA)` and `find_package(CUDAToolkit
    REQUIRED)` — sits behind an `if` that a plain `cmake .` never enters. So the default
    build compiles two ordinary C++17 files (`csrc/cpu_ops.cpp`, `csrc/pythonInterface.cpp`)
    against nothing but OpenMP, and needs no GPU toolkit at build *or* test time.
    - **The per-platform wheel sizes say which backend is optional, not just that the
      platforms differ.** Gotcha 81 reads divergent sizes in `pypi.org/pypi/<pkg>/<ver>/json`
      as "real per-platform content"; the sharper reading is the *small* end. bitsandbytes
      0.50.2 ships 43 MB (x86_64), 23 MB (aarch64) — and **123 KB** (macOS arm64) and 1 MB
      (win_arm64). A platform upstream itself builds at three orders of magnitude smaller is
      upstream shipping the CPU-only backend, which is exactly the wheel riscv64 wants. No
      `--enable-cpu` flag to discover, no divergence to justify: the port is upstream's own
      macOS/Windows-ARM recipe pointed at a third platform.
    - **Check the GPU dependency is not also a *runtime* wall** before committing. Here it
      is not: `bitsandbytes/cextension.py` `ctypes.CDLL`s whichever `libbitsandbytes_*.so`
      matches the detected runtime, falling back to a `BNBNativeLibrary` whose `__getattr__`
      raises only when a CUDA-only entry point is actually *called*, and the test suite's
      GPU half is gated behind a `requires_cuda` fixture plus `@pytest.mark.slow`, both
      deselected by upstream's own default `addopts`. Contrast gotcha 40/187's conda wall
      and the sglang case, where the blocker is a *dependency* (`cuda-python`) with no
      riscv64 build at all — an optional backend inside one CMake tree is not that.

381. **A third-party *vendor release* of a project this repo has already ruled out inherits
     that verdict — resolve the redistribution to its upstream before triaging anything else
     (the tokenspeed-triton case).** Nothing in a queue entry says a distribution is somebody
     else's rebuild of another project: `tokenspeed-triton`'s PyPI `Author`,
     `Author-email` and `Home-page` are copied verbatim from upstream triton (Philippe
     Tillet, `phil@openai.com`, `github.com/triton-lang/triton/`), and `.queue.yml`'s
     `home`/`repo` inherit them, so it reads as an ordinary triton port. Two metadata tells
     give it away, both free: the summary suffix — "A language and compiler for custom Deep
     Learning operations **(vendor release for TokenSpeed)**" — and a version that upstream
     never released (`3.8.10.post<YYYYMMDD>`, five dated builds, while PyPI `triton`'s newest
     is `3.8.0` and there is no `3.8.10` tag). Dated `.postN` builds off a release *line*
     are a vendor-nightly smell in general.
     - **The renamed namespace *is* the redistribution, and its transform is private.**
       `top_level.txt` is `tokenspeed_triton`, every path in the wheel is
       `tokenspeed_triton/…`, and the backend entry points are `[tokenspeed_triton.backends]`;
       the consumer (`lightseekorg/tokenspeed`, a GPU LLM inference engine) even bans the real
       name in `python/pyproject.toml` (`"triton" = { msg = "Use tokenspeed_triton instead." }`).
       This is gotcha 185's rename shape without gotcha 185's escape hatch: pi-heif's
       `transform_to-pi_heif.py` is checked in upstream and can simply be run, whereas the
       downstream triton fork here is not public — TokenSpeed's own
       `.skills/bisect-triton-release.md` instructs its developers to "ask where the downstream
       triton repo is to inspect downstream changes" — and **zero sdists exist across every
       version ever published**, so there is no source for the thing PyPI actually ships.
     - **Check only what the rebuild changed; don't re-derive the upstream verdict.** For
       triton that verdict is gotcha 41, and the wheel confirms it in one range-request read
       — `uv run ci_scripts/wheel_contents.py <pkg> --match <wheel-tag>` lists a remote
       wheel largest-first without downloading it, and `--member <path>` pulls one file
       (`dist-info/entry_points.txt`, a backend `driver.py`) out of the same wheel:
       a 179 MB `tokenspeed_triton/_C/libtriton.so` beside
       `backends/nvidia/bin/{ptxas,ptxas-blackwell,nvdisasm,cuobjdump}` and
       `backends/nvidia/lib/libdevice.10.bc`, plus an AMD backend of HIP/HSA headers and
       `*.bc`. The two questions specific to a fork are whether it *added* a backend or a CPU
       path upstream lacks (it did not — `entry_points.txt` lists exactly `amd` and `nvidia`,
       matching upstream `setup.py`'s `BackendInstaller.copy(["nvidia", "amd"])`, and each
       `driver.py` `ctypes.CDLL`s `libcuda.so.1` / `libamdhip64.so`), and whether the vendor
       toolchain now reaches our arch (it does not — NVIDIA's
       `redist/redistrib_13.{0,2}.0.json` still lists only `linux-x86_64`, `linux-sbsa`,
       `windows-x86_64`).
     - **Re-check a moved build mechanism rather than trusting the older gotcha's file
       names.** triton's pinned prebuilt LLVM is no longer `cmake/llvm-hash.txt` (404 today)
       but `cmake/llvm-info.json` read by `python/build_helpers.py`; its `sha256sum` keys are
       `almalinux`/`ubuntu`/`macos`-`{x64,arm64}` + `windows-x64`, and
       `llvm-b010a18d-<suffix>-1.tar.gz` on `oaitriton.blob.core.windows.net` answers 200 for
       `ubuntu-x64`/`almalinux-arm64` and 404 for every riscv64 spelling. Use a *real* hash
       from that JSON when probing — a made-up one 404s for every arch and proves nothing.
       `get_llvm_system_suffix()` returns `None` on an unrecognised machine and falls back to
       a user-supplied LLVM, so a port would first owe a from-source build of that exact
       revision (libclang-scale, gotcha 338) before hitting the blockers that end it anyway.
     - Report `parked`, cite the upstream gotcha, and note the family: sibling distributions
       from the same vendor (`tokenspeed-mla`, `tokenspeed-kernel*`) are the same shape, as
       are the already-parked `sglang`/`onnxruntime-gpu` entries.

382. **Several PyPI distributions carved out of one build are one unit of work, not one
    port each — read the allowed `--build-type` values before writing any YAML, and let
    `requires_dist` fix the order (the pyside6/pyside6-essentials/pyside6-addons case).**
    The queue holds each split distribution as its own entry, so each arrives looking like
    an independent port with its own workflow. Settle first whether the distribution you
    were handed is a *build target* at all. pyside-setup 6.11.2's
    `build_scripts/config.py:get_allowed_top_level_build_values()` returns exactly four:
    `all`, `shiboken6`, `shiboken6-generator`, `pyside6`. `pyside6-essentials`,
    `pyside6-addons` and the `pyside6` meta-wheel are **not** among them — they are carved
    out *after* the build by the root-level `create_wheels.py`, which walks
    `build/<env>a/package_for_wheels` once and emits all of
    `{shiboken6, shiboken6_generator, PySide6_Essentials, PySide6_Addons, PySide6,
    PySide6_Examples}` from `build_scripts/wheel_files.py`'s per-wheel `ModuleData` lists.
    So a standalone `build-pyside6-addons.yml` would run the entire multi-hour Qt6
    bindings build and throw away four of the five wheels it just produced, and a sibling
    `build-pyside6-essentials.yml` would run the same build again to keep a different one.
    That is also why `shiboken6` *was* portable on its own (`build-shiboken6.yml`): it has
    its own `--build-type`. `--module-subset` does not rescue the split either — it only
    narrows which Qt modules get bindings, it does not change which wheels
    `create_wheels.py` writes, and the dependent wheel's modules still need the base
    wheel's typesystems and `libpyside6` to generate and link against.
    - **Let `requires_dist` fix the dependency order; the "core-sounding" name is often
      the *last* link, not the first.** `pyside6` looks like the core package and is the
      one a porter reaches for, but its Linux wheel is 0.57 MB against essentials' 80 MB
      and addons' 175 MB: it is a meta-wheel requiring `shiboken6` + `PySide6_Essentials`
      + `PySide6_Addons`. Addons requires `PySide6_Essentials==<ver>`; essentials requires
      only `shiboken6`. So the real critical path is
      shiboken6 → essentials → addons → pyside6, and porting "pyside6" first is porting
      the tip. One check of each `requires_dist` (gotcha 40/187's dependency-tree check,
      reused for ordering rather than for feasibility) settles the order in a minute and
      prevents two agents duplicating one build in parallel PRs.
    - **Diff the dependent wheel's module list against the base's — that is where the new
      native dependencies hide.** `wheel_files_pyside_essentials()` lists 26 modules, all
      covered by Rocky 10 riscv64's AppStream (`qt6-qtbase-devel`, `qt6-qtdeclarative-devel`,
      `qt6-qtsvg-devel`, `qt6-qttools-*`, …). `wheel_files_pyside_addons()` lists 41, and
      nine of them — `QtWebEngineCore`/`QtWebEngineQuick`/`QtWebEngineWidgets`, `QtPdf`,
      `QtPdfWidgets`, `QtGraphs`, `QtGraphsWidgets`, `QtHttpServer`,
      `QtWebView`(+`QtWebViewQuick`) — need `qt6-qtwebengine`, `qt6-qtgraphs`,
      `qt6-qthttpserver` and `qt6-qtwebview`, none of which Rocky 10 ships in *any* of the
      image's four enabled repos (baseos/appstream/crb/extras) on *any* arch — not riscv64,
      not x86_64, not aarch64 (RHEL 10 ships no Qt6 WebEngine at all), and there is no
      `chromium` and no `gn` package either. QtWebEngine *is* Chromium, so those nine are
      not a `dnf install` line away; they are a Chromium-for-riscv64 bring-up, gotcha 186's
      "producing the missing artifact shape yourself is authoring a new build system"
      scale. Enumerate the repodata directly (`repomd.xml` → `primary.xml.gz` under
      `dl.rockylinux.org/pub/rocky/10/<repo>/<arch>/os/`) rather than `dnf`-ing inside the
      image: it is faster than QEMU and, per gotcha 51's EPEL note, an egress proxy that
      MITMs TLS breaks in-container `dnf` against `mirrors.rockylinux.org` anyway.
    - **A missing payload file is only a warning, so a reduced wheel is silently
      producible — make that call deliberately.** `create_wheels.py`'s copy loop prints
      `Warning: {file} does not exist` (and only when `verbose > 0`) and carries on; it
      does not fail. Shipping a `pyside6-addons` wheel that keeps the same name and
      version as upstream's while missing nine of its 41 advertised modules is a product
      decision about what `pypi.riseproject.dev` promises, not something to let a
      suppressed warning decide. Record the choice on the queue entry either way.
    - **Record it as `blocked-on-dependency`, not `parked`, when the blocker is a sibling
      port rather than absent source.** Contrast `pyqt5-qt5`, parked because no sdist or
      build recipe exists anywhere across its whole release history. Here the source is
      fully open (LGPL-3.0/GPL-2.0/GPL-3.0), 32 of the 41 addon modules are already
      covered by prebuilt Rocky 10 riscv64 `-devel` packages, and the base sibling is
      simply unported — a real dependency, not a dead end. Point the note at the base
      entry and leave the WebEngine sub-decision to the combined port. Once that port
      exists, gotcha 380 covers publishing the several wheels it emits: one
      `_publish-wheel.yml` call per distribution with disjoint `artifact-pattern`s, since
      the reusable workflow asserts a single normalized name and version per invocation.

383. **The *umbrella* distribution of a split family carries no compiled code at all, gets
    its platform+`abi3` tag from a deliberately fake `Extension`, and its payload is
    generated stubs for the union of its siblings' modules — so it cannot be cut from a
    different build than they were (the pyside6 meta-wheel case).** Gotcha 382 establishes
    that a split family is one unit of work and fixes the order from `requires_dist`; this
    is the umbrella end of that chain, and it is stronger than "do it last". Read the
    umbrella's file list before assuming it is a thin metadata shim: `pyside6`
    6.11.2's `manylinux_2_39_aarch64` wheel is 0.57 MB compressed but 67 entries and
    4.9 MB uncompressed, and holds **zero** `.so` — 59 generated `Qt*.pyi` stubs plus
    `__init__.py`, `_config.py`, `_git_pyside_version.py`, `py.typed` and `dist-info`.
    - **A platform tag with no compiled content has a third origin beyond gotcha 27's
      hand-set `--plat-name` and gotcha 81/145's real payload: a fake extension declared
      on purpose.** `wheel_artifacts/setup.py.base` passes
      `ext_modules=[Extension("PySide6/QtCore", [], py_limited_api=True)]` — no sources —
      next to a `build_ext` `Command` subclass whose `run()` is `pass` and whose
      `get_source_files()` returns `[]`, and says so in a comment: it exists only "to force
      setuptools to understand we are using extension modules". With
      `wheel_artifacts/pyproject.toml.base`'s `[tool.distutils.bdist_wheel] py_limited_api
      = "cp310"` and `plat_name = PROJECT_TAG`, that is the entire reason the wheel is
      tagged `cp310-abi3-manylinux_…` instead of `py3-none-any`. Grepping the sdist for
      `Extension(` would have "confirmed" a compiled package; reading its arguments is what
      settles it. (The tag needs no `--plat-name` CLI flag either — `create_wheels.py`'s
      `get_platform_tag()` computes `manylinux_{platform.libc_ver()[1]}_{platform.machine()}`
      itself, which is what you want, since passing `--plat-name` to `setup.py bdist_wheel`
      crashes on a native non-macOS Linux build.)
    - **Do not conclude "arch-independent content, therefore no port needed" (gotcha 27)
      without checking for an sdist.** watchdog was dismissible because upstream ships no
      `py3-none-any` wheel *and* publishes an sdist, so riscv64 `pip install` already falls
      back and builds in seconds. `pyside6` publishes **no sdist on any version** — 6.11.2
      has exactly five wheels and nothing else — so `pip install pyside6` on riscv64 has
      nothing to fall back to and genuinely does need this wheel. Stub-only content changes
      *when* it gets built, not *whether*.
    - **The umbrella's stub set spans every sibling, which is why it must come out of the
      same build tree, not merely a later one.** `create_wheels.py`'s
      `get_simple_manifest("PySide6")` is the single line `prune PySide6`, which with
      `include_package_data=True` keeps exactly the *top-level* files of
      `build/<env>a/package_for_wheels/PySide6/` and drops every subdirectory (`Qt/`,
      `scripts/`, `support/`, …) — hence stubs only. But those 59 stubs cover essentials
      modules, addons modules *and* the nine WebEngine-family modules from gotcha 382,
      whose `.so`s live in the other wheels. So if the combined port ships a reduced
      module set, the umbrella built from that same tree correctly advertises the reduced
      stub set, while an umbrella built from any *other* run can advertise stubs for
      modules the published sibling wheels do not contain. Publish the umbrella as an
      artifact of the one build that produced its siblings.
    - **Check the in-image SDK's *minor version* against the binding release, not just
      whether the packages exist.** A family like this pins `==` across its own
      distributions but is generated against whatever system SDK the image has, and those
      can be different minors. `dnf repoquery 'qt6*'` inside
      `quay.io/pypa/manylinux_2_39_riscv64` (Rocky Linux 10.2) reports **6.10.1** for every
      one of the ~100 `qt6-*` packages in appstream/crb — not 6.11.x — and this repo's own
      published `shiboken6-6.11.2-6.10.1-cp37-abi3-manylinux_2_39_riscv64.whl` already
      records it: that `6.10.1` is a wheel *build tag* carrying the Qt version. It is not a
      hard stop — `sources/pyside6/cmake/PySideSetup.cmake` marks only
      Core/Gui/Widgets/PrintSupport/Sql/Network/Test/Concurrent `REQUIRED` (all in
      `qt6-qtbase*`, present), leaves the rest `OPTIONAL_COMPONENTS`, and derives
      `PYSIDE_QT_VERSION` from the discovered `Qt6Core_VERSION` rather than asserting a
      minimum, so the configure succeeds and shiboken's typesystem `since=` gating drops
      the newer API. But it means the wheels would expose a Qt 6.10 API surface under a
      6.11.2 version number, and that a module introduced in the binding's own minor
      (`QtCanvasPainter`, new in 6.11 and present in upstream's stub set) has no provider
      in the image at all. That is a second, independent divergence from upstream stacked
      on top of the missing-modules one, and it belongs on the queue entry as an explicit
      decision, not as an unremarked build outcome.

385. **A no-sdist vendor wheel can still have a fully public build recipe — read
    `dist-info/WHEEL`'s `Generator:` before parking it for "no source anywhere" (the
    pyqt6-qt6 case).** pyqt5-qt5 was parked on the gotcha-372 signal: generic vendor
    homepage, zero sdists across the whole release history. pyqt6-qt6 matches that signal
    exactly — 41 releases, 184 files, **0** sdists, `repo` pointing at a marketing page —
    and the verdict is still different, because one small file names the tool that built
    it. `WHEEL` says `Generator: pyqt-qt-wheel`, and `pyqt-qt-wheel` is a console script of
    the **sibling** distribution `PyQt-builder` (BSD-2-Clause, sdist on PyPI):
    `pyqtbuild/bundle/qt_wheel.py` plus a per-package payload manifest in
    `pyqtbuild/bundle/packages/pyqt6.py`. The recipe was public the whole time. Read the
    `Generator:` line first — it costs one range request
    (`wheel_contents.py <whl> --member <dist-info>/WHEEL`, gotcha 41) and it decides which
    question you are actually answering. A stock generator (`bdist_wheel`, `setuptools`,
    `maturin`, `hatchling`, `skbuild`) tells you nothing; a **vendor-named** one is a lead
    to chase into that vendor's other PyPI distributions.
    - **A named generator is often a *repackager*, not a build — which moves the stop from
      "is there source?" to "does the vendor publish the payload for our arch?"**
      `qt_wheel()` compiles nothing: it copies files out of `--qt-dir` and writes a
      `dist-info` from prototypes, which is why every wheel is `py3-none-<platform>` with a
      load-bearing platform tag (gotcha 35). So the port's real input is not a source tree,
      it is *the vendor's own prebuilt tree*, and the feasibility check is gotcha 35/41's
      vendor-artifact-index check aimed **one level up** — at the installer, not at the
      wheel. `download.qt.io/online/qtsdkrepository/` offers exactly `linux_x64`,
      `linux_arm64`, `mac_x64`, `windows_x86`, `windows_arm64`, a 1:1 match with the six
      wheels Riverbank publishes. The wheel matrix is not a packaging choice to be widened;
      it is the Qt Company's prebuilt-binary matrix, and riscv64 is absent from both.
    - **Two path-parsing habits pin such a tool to the vendor's own layout — grep for them
      before assuming you can point it at anything else.** `abstract_package.py` derives the
      Qt version from `os.path.basename(os.path.dirname(qt_dir))`, and `qt_wheel.py` maps
      `os.path.basename(qt_dir)` through a closed table (`gcc_64`, `gcc_arm64`, `macos`/
      `clang_64`/`x86_64`/`arm64`, `msvc*`) to the platform tag, raising
      `UserException("Qt architecture '<x>' is unsupported")` on anything else. `--qt-dir`
      must therefore be `<prefix>/6.11.2/gcc_64`, i.e. an official online-installer tree.
      The encouraging half: `bundle_qt()` branches only on `manylinux*`/`macosx*`/`win*`
      prefixes, so that arch table is the *only* riscv64 blocker inside the tool — a
      few-line patch, not a rewrite. The tool is a third-party build dependency, so such a
      patch belongs wherever the workflow installs it, not in `patches/<pkg>/<version>/`.
    - **Hardcoded sonames in the manifest rule out substituting a distro build, and
      `ignore_missing` hides it.** `packages/pyqt6.py` names its non-Qt payload literally —
      `libicui18n.so.73`/`libicuuc.so.73`/`libicudata.so.73` and
      `libavcodec.so.61`/`libavformat.so.61`/`libavutil.so.59`/`libswresample.so.5`/
      `libswscale.so.8` — because they are *the vendor's own* ICU and FFmpeg builds. Point
      the tool at a distro Qt whose ICU major differs and
      `bundle_qt(..., ignore_missing=True)` merely warns: you ship a wheel silently missing
      ICU and FFmpeg that resolves them from the host. Same trap as gotcha 382's suppressed
      `create_wheels.py` warning — a missing-payload warning must never be allowed to make
      the product decision.
    - **Check the in-image distro version too, not just the package names.** Rocky 10.2
      riscv64 (the `manylinux_2_39_riscv64` base) does ship a broad Qt6 — 76 `qt6-*`
      packages in AppStream and 28 in CRB, enumerated straight from the repodata per
      gotchas 369/384 — but at **6.10.1**, not 6.11.2, so it cannot back a wheel carrying
      upstream's 6.11.2 version (the same minor-version divergence gotcha 383 flags for the
      pyside6 family), and it has no `qt6-qtpdf`, `qt6-qtwebengine`, `qt6-qtquick3dphysics`
      or `qt6-qtwebview`, and no `ffmpeg`, `chromium` or `gn`. Of the 96 `libQt6*.so.6` in
      the aarch64 wheel, `QtPdf`/`QtPdfQuick`/`QtPdfWidgets` come from the qtwebengine repo
      (PDFium, a Chromium subset), so they are gotcha 382's Chromium-for-riscv64 wall again.
    - **Park it as *scope*, and say which kind of stop it is.** Qt's sources are public and
      LGPL-3.0, and distros build Qt 6.10 for riscv64 natively, so nothing here is
      unportable in principle; producing the input artifact is a from-source Qt 6 SDK
      bring-up — ~96 shared libraries across ~22 Qt repos plus ICU, FFmpeg and PDFium —
      i.e. gotcha 186 scale, the same scope stop as pyqt5-qt5 reached by a different route.
      Recording *which* park this is matters for re-triage later: "no recipe exists" never
      becomes actionable, while "the recipe exists, its input artifact does not" becomes
      actionable the moment anyone stands up a Qt-for-riscv64 SDK build.

386. **A GPU-only package can be small, source-open and blob-free and still be unportable —
     in a JIT kernel library the compiled part is a few-hundred-KB shim, so gotcha 41's
     "big vendor payload" tell is absent and the wall is what that shim *links*: torch's own
     CUDA libraries (the humming-kernels case).** Every earlier CUDA verdict here had a loud
     tell — triton's 140 MB of downloaded `ptxas`/`nvdisasm` (gotcha 41), sglang's
     `cuda-python` requirement, a closed vendor blob (gotcha 157). A JIT kernel library has
     none of them: humming-kernels 0.1.13 is a 338 KB `py3-none-manylinux_2_28_{x86_64,aarch64}`
     wheel of Apache-2.0 source (`github.com/inclusionAI/humming`, tagged per release) whose
     "kernels" are `.cuh` headers compiled by NVRTC on the user's GPU at first call, so the
     only native content is three small shims — `humming/_native/<arch>/{libhumming_launcher.so,
     libcubinpatch.so, nvrtc_compile}`. Nothing about the wheel's size, licence or provenance
     objects; the port is dead anyway. Four checks, cheapest first, and the third is the one
     no other gotcha covers:
     - **Read the package's own arch table before anything else.** A project that ships
       per-arch precompiled artifacts has a `platform.machine()` map somewhere, and it is a
       one-line statement of upstream's supported set — here `get_native_arch()` in
       `humming/utils/jit.py` maps only `x86_64|amd64` and `aarch64|arm64`, so on riscv64 it
       returns `None`, `build_native()` raises `Unsupported architecture`, and every
       `get_precompiled_artifact_path()` lookup returns `None` (the pure-Python half then
       silently has no kernels). Adding `"riscv64"` to that dict is a one-word patch that
       fixes nothing, which is the tell that the blocker is below it.
     - **Run gotcha 284's two greps and accept the answer when it comes out the other way.**
       fastsafetensors passed because it `dlopen`s CUDA and includes no toolkit headers; here
       `humming/csrc/launcher/{launcher.cpp,tensor.h,tma.h}` `#include <cuda.h>` and
       `csrc/nvrtc_compile.cpp` `#include <nvrtc.h>`, and `humming/build.py:_find_cuda_include()`
       hard-fails without `cuda.h` from `nvidia-cuda-runtime-cu12` or `CUDA_HOME`. NVIDIA's
       redist index answers that for good: `redistrib_13.0.0/13.2.0/13.4.2.json` list only
       `linux-x86_64`, `linux-sbsa`, `windows-x86_64/arm64` and contain zero `riscv` strings,
       and `nvidia-cuda-nvrtc`/`nvidia-cuda-runtime-cu12` publish x86_64/aarch64/win wheels
       only. CUDA-on-RISC-V was announced as a *host CPU* target in July 2025 (RVA23 plus the
       RISC-V server SoC/platform specs) with no release and no shipped artifact since.
     - **`libtorch_cuda.so` is its own wall, and our riscv64 torch can never clear it.** This
       is the new one: a torch-extension build that links the CUDA half of torch —
       `_torch_library("libtorch_cuda.so")` raising *"is required; build with a CUDA-enabled
       torch wheel"*, or equivalently a `torch.utils.cpp_extension.CUDAExtension`, or an
       `#include <c10/cuda/CUDAStream.h>` — is blocked by *our own registry*, independently of
       the toolkit question. pypi.riseproject.dev serves `torch-2.13.0+cpu`/`2.14.0+cpu` for
       riscv64 and PyPI serves no riscv64 torch file at all, so no `libtorch_cuda.so` /
       `libc10_cuda.so` exists for the arch and none can be produced without a CUDA toolkit
       for it first. Gotcha 249's lesson generalizes: `Requires-Dist: torch` looking portable
       says nothing about *which* torch libraries the build links. Note this survives even a
       fully stubbed link line — upstream already generates an empty `libcuda.so` stub with
       `-Wl,-soname,libcuda.so.1` to link the launcher without a driver present, which proves
       stubbing is not the missing idea; the torch CUDA libraries are linked as real files.
     - **Then confirm the wheel could not even be smoke-tested** (gotcha 40's criterion):
       `import humming` → `humming.ops` → `ops/input.py`'s `import triton` plus
       `from triton.language.extra.cuda import gdc_wait`, and `import cuda.bindings.driver` in
       eleven `humming/kernel/*.py` and in `jit/{compiler,runtime}.py`. `triton` (gotcha 41's
       own project) and `cuda-bindings` both publish manylinux x86_64/aarch64 wheels and **no
       sdist**, so the install fails before any import runs.
     Record it `parked` with the unreachable primitive named, as with sglang. Upstream's
     `.github/workflows/build-wheel.yml` is worth reading for the shape even so: it builds
     inside `quay.io/pypa/manylinux_2_28_{x86_64,aarch64}` with `torch==2.11.0` plus
     `nvidia-cuda-{runtime,nvrtc}-cu12` from `download.pytorch.org/whl/cu126`, runs a
     `tools/build_native.py` that **is not in the sdist**, then hand-retags the wheel with
     `python -m wheel tags --python-tag py3 --abi-tag none --platform-tag …` — i.e. a
     `py3-none-<platform>` tag that is neither gotcha 27's cosmetic tag nor gotcha 145's
     maturin binary, but a per-arch C++ shim retagged by hand (0.1.14+ adds a
     `_device_info.abi3.so` and becomes honestly `cp310-abi3`, so an `abi: py3` note in the
     queue goes stale on a package like this).

387. **A GPU-toolkit-suffixed distribution name (`-cuda12x`, `-cuda13x`, `-rocm-7-0`) is a
    toolkit *selector*, and the name can be injected from a **separate** release-tools
    repository the source repo never mentions (the cupy-cuda12x case).** Gotcha 79's
    `-gpu`/`-headless` sibling branches inside one `setup.py`, and gotcha 185's transform
    script at least lives in the source tree. cupy is a step further out: `cupy/cupy`'s
    `pyproject.toml` says `name = "cupy"` and nothing in that repo builds a suffixed
    wheel. The suffixed distributions come from `cupy/cupy-release-tools`, whose
    `dist_config.py` holds the whole sibling axis as a table —
    `'12.x' → {'name': 'cupy-cuda12x', 'kind': 'cuda', 'image':
    'cupy/cupy-release-tools:cuda-runfile-12.9.0-el8-amd64'}`, plus `12.x-aarch64`,
    `13.x`, `13.x-aarch64`, `rocm-7.0` — and whose `dist.py` calls
    `rename_project(f'{workdir}/cupy/pyproject.toml', package_name)` to rewrite
    `project.name` before building. So the playbook's "read upstream's own build/release
    docs first" has to mean *that* repo: it is where the arch list, the base images and
    the name mapping actually are. Read the table before anything else — if every `kind`
    is a proprietary GPU toolkit and there is no CPU entry, the suffix is not a feature
    flag and there is no CPU-shaped sibling of that distribution (same conclusion as the
    parked `onnxruntime-gpu`, reached from a different direction).
    - **Ask the vendor's own redist index for our arch, as gotcha 41 does.** All 24 CUDA
      12.x manifests (`developer.download.nvidia.com/compute/cuda/redist/redistrib_12.*.json`)
      list only `linux-x86_64`, `linux-sbsa`, `linux-aarch64`, `linux-ppc64le`,
      `linux-all` and `windows-x86_64`; 13.x is the same minus ppc64le. The PyPI
      republications agree (`nvidia-cuda-runtime-cu12`, `nvidia-cublas-cu12`,
      `nvidia-cuda-nvrtc-cu12`: manylinux x86_64/aarch64 and Windows only). CUDA on
      RISC-V is an announced future capability for RVA23 server-class platforms with no
      released nvcc, cuDNN or `libcuda.so.1`.
    - **Check whether the toolkit is a build requirement or a runtime `dlopen` (gotcha
      284) — here it is the former.** `install/cupy_builder/_features.py`'s `CUDA_cuda`
      feature sets `required = True` and configures by *compiling* a probe that reads
      `CUDA_VERSION` from `cuda.h` (rejecting anything below 12000); its `includes` are
      `cuda_runtime.h`/`cublas_v2.h`/`cufft.h`/`curand.h`/`cusparse.h`, its link list is
      `cudart_static`+`cublas`+`cufft`+`curand`+`cusparse`+`cuda`+`nvrtc`, and four `.cu`
      sources (`cupy_cub.cu`, `cupy_thrust.cu`, `cupy_distributions.cu`,
      `cupy_cufftXt.cu`) need nvcc. `setup.py` `sys.exit(1)`s when a required feature
      fails to configure, so there is no partial build.
    - **The un-suffixed base name is not the escape hatch.** PyPI's `cupy` project ships
      an sdist and *no wheel on any arch or interpreter* — gotcha 50/126, no riscv64 gap
      to close — and that sdist builds through the same `required` CUDA feature. Retarget
      a `-cuda*` queue entry to the base name only if the base actually publishes wheels
      somewhere.
    - **Nor is the project's own "no-GPU" build mode.** `CUPY_INSTALL_USE_STUB=1` (auto-set
      when `READTHEDOCS=True`) defines `CUPY_NO_CUDA`, pins the compile-time
      `CUPY_CUDA_VERSION` to 0, and compiles against `cupy_backends/stub/*.h`, whose
      banner reads "This file is a stub header file of cuda for Read the Docs" and whose
      entry points all `return cudaSuccess` (`cudaDriverGetVersion` writes 0). It builds
      clean with no toolkit installed and yields a wheel that computes nothing — gotcha
      41's rejected offline-build escape hatch behind a friendlier switch. A documented
      stub/no-CUDA flag is evidence about the *docs build*, never about portability.
    - **A metadata file inside the wheel can state the coupling outright, for one range
      request.** `ci_scripts/wheel_contents.py <pkg> --member cupy/.data/_wheel.json`
      returns `{"cuda": "12.x", "packaging": "pip", "nccl": {...}}`, and the same listing
      shows the wheel bundles *no* CUDA `.so` at all (only cupy's own extensions plus
      vendored CCCL/jitify/xsf headers) — i.e. the toolkit is a hard external dependency
      resolved at runtime (`cuda-pathfinder`, the `ctk` extra's
      `cuda-toolkit[...]==12.*`), not a vendored payload that could be swapped.
    - **One tree spread over several queue entries is one verdict, not several
      triages.** `cupy-cuda12x` and `cupy-cuda13x` are separate `.queue.yml` rows for the
      same source tree differing only in the toolkit major; park each with the same
      evidence rather than re-deriving it (gotcha 150's sibling check used to save work
      rather than to sequence it).

388. **The queue entry's wheel shape is a *snapshot* — re-read the latest release's tag set
     before triaging the queued version, because upstream can delete the arch-specific payload
     and erase the gap outright (the tokenspeed-mla case).** Gotcha 386 closes with one way a
     queue note's `abi:` goes stale (upstream stopped mislabelling a compiled wheel); this is
     the sharper version of the same hazard, where the *platform* half goes away too and the
     gap disappears with it. Gotchas 27/35/81/145/157 all reason about one *fixed* set of
     `py3-none-<platform>` wheels and ask what the platform half contains; they tacitly assume
     the set you were handed is the set upstream still ships. It need not be: `.queue.yml`
     records the wheel shape at the moment the queue was generated (here `2 Linux wheels
     upstream (abi: py3)`, true of 0.2.5), and a later release can drop the payload and
     collapse to a single universal wheel — at which point riscv64 already installs exactly
     what x86_64 installs and there is nothing left to port, whatever the older version's
     wheels held. tokenspeed-mla 0.2.0–0.2.8 each publish
     `py3-none-manylinux_2_28_{x86_64,aarch64}` (~0.75 MB) and **0.2.9 publishes one
     `py3-none-any` (0.15 MB)**, having deleted `tokenspeed_mla/fmha_binary.py` and the
     `tokenspeed_mla/objs/*.so` those wheels existed to carry.
     - **Make the per-version tag table the first read of any triage**, before `pip download`,
       before `wheel_contents.py`, before the repo checkout:
       `uv run ci_scripts/queue_triage.py <pkg> --deps` prints latest-vs-queued (flagging a
       stale entry), each recent release's ABI/platform tags with sizes, whether an sdist
       exists, and which releases already have a riscv64-installable file. A `riscv64-OK` row
       on the **latest** version closes the case on its own. Reading only the queued version's
       files would have sent this port straight into the far more expensive question of whether
       two NVIDIA Blackwell cubins can be rebuilt.
     - **Size direction is the tell that a payload was removed, not added.** Gotcha 81 diffs
       sizes *across platforms at one version* to separate a cosmetic tag from real content;
       diff them *across versions at one platform* too. A platform wheel that is 5x the new
       universal wheel means the arch-specific bytes were dropped, so read the newest release's
       file list rather than inferring from the version the queue names.
     - **A vanished gap still is not automatically "already works".** Confirm what the
       universal wheel actually does on riscv64 before reporting: 0.2.9 installs and imports
       fine in `quay.io/pypa/manylinux_2_39_riscv64`, but `__init__.py` wraps every import in
       one `try:`/`except ImportError` and substitutes `_unavailable` stubs, so
       `tokenspeed_mla.tokenspeed_mla_decode()` raises `ImportError: tokenspeed_mla requires
       PyTorch, CUDA bindings, and NVIDIA CuTe DSL runtime dependencies`. That is gotcha
       183's importable-but-unusable shape — and it is a property of the package upstream
       publishes for *every* architecture, so it is not a riscv64 gap and not ours to close.
     - **Watch for a `py3-none-any` *facade* in the dependency check.** `nvidia-cutlass-dsl`
       resolves on riscv64 (its own wheel is `py3-none-any`, ~15 KB) and is nonetheless a hard
       blocker: it is a metapackage whose `requires_dist` pins
       `nvidia-cutlass-dsl-libs-{base,cu12}==<ver>`, which publish
       `cp310–cp314(t)-manylinux_2_28_{x86_64,aarch64}` only, no sdist, ~88 MB of CUDA payload.
       Follow any `py3-none-any` dependency one level down before calling it available —
       `pip download <dep> --no-deps` says yes where a full resolve says `ResolutionImpossible`.

392. **When PyPI records no project URL and `Generator:` is stock, the *conda-forge feedstock*
    is the cheapest source-availability oracle — and `readelf -S` tells you in one command
    whether a real compiled extension is code or embedded model weights (the
    livekit-local-inference case).** Gotcha 385 says to read `dist-info/WHEEL`'s `Generator:`
    before parking anything for "no source anywhere", because a vendor-named generator is a
    lead. `livekit-local-inference` 0.2.7 says `Generator: setuptools (84.0.0)` — a stock
    one, which by 385's own rule tells you nothing — and PyPI's JSON has
    `project_urls: null`, `home_page: null`, no author and no description, so there is no
    link to follow either. The next cheap read is conda-forge:
    - **A GitHub code search for the *distribution name* finds the feedstock**, and its
      recipe is written by someone who already answered "where does this build from?".
      `conda-forge/livekit-local-inference-feedstock`'s `recipe/recipe.yaml` opens with the
      verdict in as many words — *"This package is closed-source and ships only binary wheels
      on PyPI (no sdist)"* — and proves it structurally: its `source:` is not a tarball but a
      nest of `if: target_platform == ...` / `if: match(python, "3.X.*")` blocks each naming a
      `files.pythonhosted.org` **wheel** URL, one per (platform, interpreter). A feedstock
      whose source is the PyPI wheels is a *repackager* (gotcha 385's second bullet, arrived
      at from the other side), so it adds no platform upstream doesn't already ship and
      riscv64 has nothing to repackage. `recipe.yaml`'s `about:` also fills the blanks PyPI
      left — `repository:`, `documentation:`, `homepage:` — which is how the queue entry's
      empty `home`/`repo` get answered at all. Two `curl`s of
      `raw.githubusercontent.com/conda-forge/<pkg>-feedstock/main/recipe/recipe.yaml`
      (or `meta.yaml`) settle it; `conda-forge/feedstock-outputs`'s
      `outputs/<a>/<b>/<c>/<pkg>.json` confirms a feedstock exists before you guess its name.
      Distinct from gotchas 40/42, which ask whether a *dependency*'s conda channel serves our
      subdir — this uses the recipe as evidence about **source**, not about availability.
    - **`readelf -S -W` separates "compiled code" from "a blob with a `.so` extension"
      faster than `strings`.** The wheel is a genuine `cp312-cp312-manylinux_2_27_x86_64`
      extension — gotcha 27/35/81's `py3-none-<platform>` tells are all absent, and gotcha
      41's vendored `bin/`/`lib*.so` neighbours are absent too: 14 entries, one of which is
      `livekit/local_inference/_native.cpython-312-x86_64-linux-gnu.so` at 35.0 MB of a
      35.1 MB wheel. The section table is the tell: `.text` is `0x444ad` (**~280 KB**) while
      `.rodata` is `0x21168f8` (**~34.8 MB**), i.e. 99.2% of the file is constant data baked
      into the binary — the proprietary model weights, not an inference runtime. Corroborated
      without downloading more: `DT_NEEDED` lists only `libstdc++/libm/libgcc_s/libpthread/
      libc`, so nothing like ONNX Runtime is linked; the `.comment` is
      `GCC: (GNU) 14.2.1 20250110 (Red Hat 14.2.1-11)` and `strings` shows pybind11 v12
      internals, so ~280 KB of hand-written C++ is the whole engine; and the shipped
      `_native.pyi` says so outright (*"Eagerly init the EOT model singleton (~108 MB)"*).
      Per-platform wheel sizes within ~45 KB of each other across five platforms say the same
      thing from the outside (gotcha 81's cross-platform size diff, inverted: near-identical
      sizes mean the *weights* dominate and the code is noise).
    - **A compound `License:` with a `LicenseRef-` term is the metadata echo of that split,
      and it is gotcha 372's second lock.** `License: Apache-2.0 AND LicenseRef-LiveKit-Model`
      plus *two* files under `dist-info/licenses/` (`LICENSE`, `MODEL_LICENSE`) and both
      `License :: OSI Approved :: Apache Software License` **and** `License :: Other/
      Proprietary License` classifiers: the permissive half covers the thin wrapper, the
      bespoke half covers the 34.8 MB that matters. The LIVEKIT MODEL LICENSE AGREEMENT bars
      using the models "on a standalone basis or with any frameworks other than LiveKit
      Agents" and bars making them available to third parties except under that agreement, so
      even lifting the weights out of an existing `.so` into a self-built riscv64 wheel is
      foreclosed. Same double lock as hdbcli (gotcha 372), reached from a *permissive-looking*
      top-level license rather than a uniformly proprietary one — the inverse of gotcha 376,
      where the permissive field was real and the source was still absent.
    - **An open-source org's flagship repo can be the closed-source package's *consumer*,
      never its source.** LiveKit has 79 public repos and the obvious search hits are all in
      `livekit/agents` — but every one is an `import`: `livekit-agents/livekit/agents/
      inference/vad.py`, `inference/eot/transports.py` and `ipc/_preload.py` do
      `from livekit.local_inference import VAD/EOT`, and `livekit-agents/pyproject.toml`
      lists `livekit-local-inference>=0.2.7` in `dependencies`. No repo in the org contains
      the extension's sources, and none is named for it. "The org is open source", a sibling
      port from the same org (livekit-blingfire, built from `livekit/agents`), and even a
      dependency edge from an open-source package are all *not* evidence that a given
      distribution has source — check `requires_dist` direction before assuming a monorepo
      hit is the upstream. Note the consequence for the queue: a closed-source leaf can
      block an otherwise-pure-Python parent, since `livekit-agents` core cannot be installed
      on riscv64 at all while this dependency has no wheel.
    - **Confirm zero sdist across the *whole* release history, not the queued version**
      (gotcha 372): 120 files across 0.2.2–0.2.7, every one a `bdist_wheel`, tags limited to
      `macosx_10_9/10_13/10_15_x86_64`, `macosx_11_0_arm64`,
      `manylinux_2_27/2_28_{x86_64,aarch64}` and `win_amd64` for cp310–cp314. Parked; no
      worktree/branch/PR — there is no build input to stage a workflow around.
393. **The *bindings* half of a "bindings wheel + vendored-SDK wheel" pair looks unblocked
     from its sdist and is not: the pin that blocks it is written by the vendor's release
     step, not by the sources, and the real coupling is a `RUNPATH` into the sibling wheel's
     install directory (the pyqt6 case).** Gotcha 385 parked `pyqt6-qt6`, the SDK half, for
     scope. `pyqt6`, the bindings half, fails every signal that usually marks a blocked
     package: it publishes a real GPL-3.0 sdist on every release, the sdist holds actual
     C++/`.sip` sources for 35 binding sets, and it builds with two public, pure-Python
     tools (`sip`, `PyQt-builder`). Its sdist `PKG-INFO` declares exactly one dependency —
     `Requires-Dist: PyQt6-sip (>=13.11, <14)`, which this registry already serves. The
     published wheel's `METADATA` declares two: that one (relaxed to `>=13.8`) **and**
     `PyQt6-Qt6 (>=6.11.0, <6.12.0)`. Nothing in the project or in PyQt-builder writes the
     second line — the only `Requires-Dist` in `pyqtbuild` is `bundle/qt_wheel.py`, which
     writes it *into* the Qt wheel, and `bundle/bundle.py`, which *deletes* it from the
     bindings wheel when `pyqt-bundle` bundles Qt inside. It is added by the vendor's own
     release pipeline. So **the sdist's metadata is not the wheel's metadata**: read the
     published wheel's `METADATA` (one range request, gotcha 41) and settle the pin with the
     resolver rather than by eye —
     `uv run ci_scripts/check_riscv64_deps.py --python 312 -- 'PyQt6-Qt6>=6.11.0,<6.12.0'`
     answers `UNRESOLVABLE ... (from versions: none)`.
     - **One `readelf -d` on one extension module proves the coupling.**
       `wheel_contents.py <pkg> --match <linux wheel> --member PyQt6/QtCore.abi3.so` then
       `readelf -d`: `NEEDED libQt6Core.so.6` next to `RUNPATH $ORIGIN/Qt6/lib` — and the
       wheel ships no `Qt6/lib` at all (893 entries, 40.6 MB uncompressed: `.abi3.so`s,
       `.pyi` stubs and one `Qt6/qsci/api` file). That directory is filled by the *sibling*
       wheel at install time. A wheel that resolves its shared libraries out of another
       distribution's install path is structurally incomplete on its own, whatever its own
       sources build.
     - **Building against the distro SDK instead is a real option, and the sibling's
       *dlopened* payload is what defeats it.** Everything upstream about such a build is
       permissive: `project.py` rejects only `qt_version >> 16 != 6` (no minimum minor),
       PyQt-builder derives the sip tag from the *discovered* `qt_version_tag`
       (`bindings.py`), and sipbuild's `update_buildable_bindings()` *silently deletes* any
       bindings whose config test fails, so a build against Rocky 10 riscv64's Qt 6.10.1
       (`qmake6` is in `qt6-qtbase-devel`; 28 module `-devel` packages in AppStream)
       configures and produces a reduced, Qt-6.10-API wheel under a 6.11.0 version number
       (gotcha 383's divergence, with gotcha 382's "a warning must not make the product
       decision" on top). auditwheel then bundles the Qt libraries the extensions *link*.
       It cannot bundle what Qt `dlopen`s — the platform plugins (`platforms/libqxcb.so`,
       `libqoffscreen.so`), the imageformat and sqldriver plugins, the QML module tree — and
       the bundled distro `libQt6Core` keeps its compiled-in `/usr/lib64/qt6/plugins` prefix,
       so the wheel imports cleanly and then dies at the first `QApplication` with "no Qt
       platform plugin could be initialized". **When the sibling wheel supplies plugins, QML
       and data as well as libraries, auditwheel's linked-library bundling is not a
       substitute for it** — reproducing that payload *is* the sibling's port.
     - **For a vendor pair `<pkg>` + `<pkg>-<sdk>`, triage the SDK entry first; it decides
       both.** `pyqt5`/`pyqt5-qt5`, `pyqt6`/`pyqt6-qt6` and the pyside6 family are the same
       shape three times over. Mark the bindings half `blocked-on-dependency` pointing at the
       SDK entry (gotcha 382's rule: the blocker is a sibling port, not absent source), keep
       the two entries' notes pointed at each other, and do not re-run the SDK investigation
       on the bindings entry — record only what is new on the *consumer* side (the wheel-vs-
       sdist metadata split, the `RUNPATH`, the resolver output).

405. **An NVIDIA-owned, profiler-adjacent package can have no CUDA dependency whatsoever —
     read the extension's own header set and `libraries=` list before filing it with the GPU
     batch (the nvtx case; see `build-nvtx.yml`).** Gotcha 284 covers CUDA symbols that turn
     out to be `dlopen`ed at runtime; this is the step before it, where there are no CUDA
     symbols at all and only the vendor's name suggests otherwise. The PyPI `nvtx`
     distribution is the `python/` subdirectory of `NVIDIA/NVTX`: five Cython modules over a
     header-only C annotation API. `setup.py` declares a single
     `Extension('*', sources=['src/nvtx/_lib/*.pyx'], include_dirs=[<repo>/c/include])` with
     no `libraries=` at all, and the only `cdef extern from` headers across its `.pxd` files
     are `nvtx3/nvToolsExt{,Counters,Payload}.h`, `nvtx3/nvToolsExtSemantics*.h` and
     `nvtxw3/nvtxw3*.h` — no `cuda.h`, no `cuda_runtime.h`, nothing to link. The GPU is the
     *consumer*, not a dependency: annotations are inert until an external profiler injects a
     library through `NVTX_INJECTION64_PATH`, and `nvtx.enabled()` is literally
     `not os.getenv("NVTX_DISABLE")` with no hardware probe anywhere.
     - **Two checks settle it, both cheaper than a CI cycle**: `grep -rn 'libraries=' setup.py`
       plus `grep -rn 'cdef extern from\|#include' <extension sources>` (an instrumentation
       SDK's own headers only), and then `auditwheel show` on a locally built wheel — one that
       references nothing but `libc.so.6` has no GPU runtime to find.
     - **The cost of getting this wrong is not one entry.** An annotation SDK shows up in the
       `Requires-Dist` of GPU-ecosystem distributions (vllm's CUDA wheels among them), so
       parking it on "NVIDIA ⇒ GPU-only" converts one bad triage into a fake blocker for every
       consumer that is itself portable.
     - **What actually distinguishes the parked set** (`onnxruntime-gpu`, `cupy-cuda12x`/
       `-cuda13x`, `jax-cuda*-plugin`, `numba-cuda`) is that those need the toolkit's own
       headers and libraries — or nvcc — *at build time* (gotcha 387). A vendor's profiling,
       tracing or annotation library typically needs neither, and belongs in the ordinary
       Cython/C-extension lane.

407. **An upstream recipe can stop being conda-based between releases, so read it at the
    *newest* tag before pricing a port or recording a conda blocker (the
    cadquery-ocp-novtk case).** Gotcha 388 says the queue entry's wheel *shape* is a
    snapshot; the recipe's *build environment* is one too. `CadQuery/ocp-build-system` at
    `v7.9.3.1.1` — the version the queue entry named — builds the OCCT SDK for Linux
    inside a micromamba environment (`environment.yml`'s python plus `micromamba install
    fontconfig freetype freeimage`), which is gotcha 40's wall: conda-forge has
    `linux-riscv64` freetype and fontconfig but **no** freeimage. At `v8.0.1.0.0`,
    released since that entry was written, the same repo's Linux path is `dnf` system
    libraries plus `astral-sh/setup-uv`, and conda survives only on macOS/Windows — so
    the riscv64 port needs no conda at all and is an ordinary CMake build.
    - **`https://api.anaconda.org/package/conda-forge/<name>` is the per-package form of
      gotcha 42's subdir count** — one small JSON per dependency,
      `{f["attrs"]["subdir"] for f in d["files"]}`, with no 100 MB `repodata.json`
      download, which is what makes "which of these conda deps is missing for riscv64" a
      one-minute question.
    - **micromamba itself is never the blocker.**
      `https://micro.mamba.pm/api/micromamba/linux-riscv64/latest` serves a real riscv64
      ELF (8.3 MB), so a conda-based recipe fails on *package* coverage only.
    - **Diff the recipe, not just the version string** (`git log --oneline v<old>..v<new>
      -- .github/` on the recipe repo). The same diff decides which component versions
      you build: upstream's workflow `env:` block carries `WHEEL`, `OCP` and `OCCT`, so
      read them out of the tag the job checks out instead of hardcoding them, and assert
      that `WHEEL` equals the version in `docs/packages/<pkg>.yaml` so a bump that moves
      them fails loudly.

418. **An upstream wheel for *another* non-x86 architecture is only a precedent for the
    parts of it that are actually that architecture — `readelf -h` every `.so` in it (the
    paddlepaddle case).** Gotcha 186 warns that a vendor publishing one *artifact shape*
    says nothing about another; this is the sharper version, where the vendor publishes
    the right shape for the wrong ISA and ships it anyway. Paddle's CMake knows four
    non-x86 architectures (`WITH_ARM`/`WITH_SW`/`WITH_MIPS`/`WITH_LOONGARCH`), each
    turning off Xbyak, MKL and AVX, and upstream publishes `linux_aarch64` wheels off the
    first — which reads as "the non-x86 CPU path is maintained, mirror it". It mostly is.
    But `cmake/external/lapack.cmake` takes **one prebuilt tarball for the whole of
    Linux** (`lapack_lnx_v3.10.0.20210628.tar.gz`, x86-64 only — the comment beside it
    says "lapack need fortran compiler which many machines don't have"), and `setup.py`
    copies `LAPACK_LIB`/`BLAS_LIB`/`GFORTRAN_LIB`/`GNU_RT_LIB_1` into `paddle/libs/`
    unconditionally. So the released
    `paddlepaddle-3.3.1-cp312-cp312-linux_aarch64.whl` carries x86-64
    `liblapack.so.3`, `libblas.so.3`, `libgfortran.so.3` and `libquadmath.so.0` beside a
    genuinely aarch64 `libopenblas.so.0`.
    - **The check is two commands and needs no build.** Download the sibling-arch wheel,
      then `unzip -q -j <whl> '<pkg>/libs/*' -d x && file x/*` (or `readelf -h`) — a
      mismatched `Machine:` line names every payload whose build step is
      architecture-blind. Do it before writing the workflow: it is the difference between
      "mirror upstream" and "mirror upstream and fix what it got wrong", and it is the
      only way to find these, because nothing links against them (Paddle `dlopen`s
      LAPACK through `phi/backends/dynload/lapack.cc`, so the build is green and the
      failure is a runtime `paddle.linalg` error).
    - **A prebuilt-for-one-arch dependency is not automatically gotcha 35's wall** — but
      *building* the missing artifact is the second answer, not the first. Ask what the
      payload actually is: here it is Reference-LAPACK, which gotcha 401's Rocky 10
      riscv64 `lapack`/`blas` packages already provide as the very `liblapack.so.3` and
      `libblas.so.3` the `dlopen` asks for, so one `dnf install` plus four
      `${CMAKE_C_COMPILER} -print-file-name=<soname>` lookups replaces the whole tarball
      branch. Adding a 30-line `ExternalProject_Add` for Reference-LAPACK v3.10.0 instead
      cost a CI round to a `cmake` configure failure whose diagnostic gotcha 434's stamp
      logs had swallowed — and it puts a Fortran build on a 4-core riscv64 runner for a
      library nothing links against. Whichever you pick, gate it on the new arch flag so
      x86-64 and macOS keep the tarball, resolve the sonames with a `FATAL_ERROR` so a
      missing one fails in the first configure minute rather than at wheel-packing time,
      and say in the patch that the fix would repair the sibling arch too.

419. **Gotcha 411's "is the CPU backend the default?" test can pass and still not yield a
    port: a torch extension's non-CUDA branch can compile *operator schemas with no
    implementations*, so the build succeeds in seconds against a CPU-only torch and the
    wheel it produces is a dead stub (the xformers case).** bitsandbytes (gotcha 411) was
    rescued by reading its backend selector; xformers' selector reads the same way and ends
    somewhere else. `setup.py:get_extensions()` sets `extension = CppExtension` and only
    promotes it to `CUDAExtension` (adding `source_cuda`) inside
    `if (torch.cuda.is_available() and CUDA_HOME is not None and torch.version.cuda is not
    None) or FORCE_CUDA=1 or TORCH_CUDA_ARCH_LIST != ""`, with the HIP branch behind
    `torch.version.hip` — so with our `torch-2.14.0+cpu` and no toolkit the CPU path is
    what runs, needs no GPU host, and `pip wheel . --no-deps --no-build-isolation` finishes
    in seconds. Everything after that is the trap.
    - **Count and read the sources the non-CUDA branch globs — don't stop at "it built".**
      The CPU branch's `sources` is `xformers/csrc/**/*.cpp` minus the HIP directory: at
      0.0.35 that is exactly two files, 44 lines total, and every line is an `m.def("op(...)
      -> ...")` inside `STABLE_TORCH_LIBRARY_FRAGMENT` — `attention.cpp`'s entire body is
      additionally wrapped in `#if defined(USE_ROCM)`, so it contributes nothing at all.
      Every `m.impl` lives in a `.cu` (or HIP `.cpp`) that only the GPU branches compile. A
      schema with no implementation registers fine and then raises `NotImplementedError:
      Could not run '<ns>::<op>' with arguments from the 'CPU' backend` on the first call.
    - **When upstream publishes no CPU wheel to size-diff against, build one and diff the
      `.so`.** Gotcha 411's cheapest signal was upstream's own 123 KB macOS wheel next to a
      43 MB Linux one. Here upstream ships no CPU artifact anywhere, so produce it:
      the CPU-built `xformers/_C.so` is 233 KB with **five** dynamic symbols, none of them
      an operator (`nm -D --defined-only`), against the published CUDA wheel's 11.6 MB
      `_C.so`. Two orders of magnitude *and* an empty symbol table is not "a smaller
      backend", it is "no backend".
    - **`_has_cpp_library is True` proves only that the `.so` loaded.** xformers'
      `_cpp_lib.py` catches a failed `torch.ops.load_library` and degrades with a warning,
      so a package-level "did the extension load" flag reads healthy on a wheel whose every
      op is missing. Install the wheel and *call* something: `memory_efficient_attention`
      answers `No operator found ... device=cpu (supported: {'cuda'})`, and one grep
      (`grep -rn SUPPORTED_DEVICES <pkg>/ops/`) shows every op class in the dispatch list
      declaring `{"cuda"}` — i.e. no patch to the build reaches the Python layer either.
    - **Check upstream's wheel matrix for a CPU job before calling the CPU path
      "upstream's own recipe".** `.github/workflows/wheels.yml`'s target determinator emits
      only `toolkit_type` `cuda` (cu126/cu128/cu130) and `rocm` (7.1); there is no CPU
      entry, and `upload_pip` filters `*torch2.10.0+cu128*`. bitsandbytes' CPU wheel exists
      upstream and merely lacked a third platform; a CPU-only xformers wheel is an artifact
      upstream ships nowhere — gotcha 24's divergence test, reached from the opposite
      direction.
    - **Verdict: `parked` under gotcha 183's rule** (installable and importable, primary
      function unreachable rather than degraded), not `not-feasible` — the build genuinely
      works, which is exactly why the note has to say what the built wheel *contains*.
    - **Free bonus for triage notes: a `py39-none-<platform>` tag on a torch extension is
      real compiled content.** It is neither gotcha 27's cosmetic `--plat-name` nor gotcha
      145's maturin binary: `bdist_wheel.get_tag()` hand-returns `("py39", "none",
      plat_tag)` because the `.so` talks only to torch's stable ABI
      (`STABLE_TORCH_LIBRARY_FRAGMENT`, `get_export_symbols()` returning `[]`, no
      `PyInit_*`), so one wheel covers every CPython 3.9+ including free-threaded. A queue
      note reading "1 Linux wheel (abi: py39)" on a torch-extension package is that
      convention, not a pure-Python tell — and it means the port, had it been feasible,
      would have been one wheel rather than a per-interpreter matrix.

426. **A `-cpu` sibling can be an *x86_64-only label*, not a portable CPU variant — if the
    base package already ships a CPU-only wheel on every non-x86 arch, the sibling name
    closes no riscv64 gap (the tensorflow-cpu case).** Gotcha 79's `-headless`/`-gpu`/`-lite`
    sibling is usually a legitimate second port, and gotcha 50's `-binary` sibling is where
    the wheels actually live. This is the third shape: a sibling that exists **only because
    one architecture's default wheel is the GPU one**. `tensorflow-cpu` and `tensorflow`
    2.21.0 are the same tree — `tensorflow/tools/pip_package/utils/tf_wheel.bzl` reads
    `WHEEL_NAME` out of `@python_version_repo` and its own docstring says "Should be set via
    `--repo_env=WHEEL_NAME=tensorflow_cpu`" — and their PyPI metadata is identical down to
    the same 12 `nvidia-*; extra == "and-cuda"` requirements. What differs is only which
    arch each name is *built* for, and that is the whole triage:
    - **Scan the sibling's entire release history for platform tags, not just the version in
      the queue entry.** One pass over `https://pypi.org/pypi/<sibling>/json`'s `releases`
      counting the trailing tag of every file: `tensorflow-cpu` has published `win_amd64`
      and `manylinux*_x86_64` **only** — across every release ever, zero aarch64, zero
      ppc64le, zero other Linux arch, and no sdist. A sibling that has never left x86_64 is
      a label for "x86_64 without the GPU bits", not a CPU variant.
    - **Then compare the base package's per-arch wheel *sizes* to find which arches are
      already CPU-only under the base name.** `tensorflow` 2.21.0 is 545 MB on
      `manylinux_2_27_x86_64` but 268 MB on `manylinux_2_27_aarch64` — and `tensorflow_cpu`
      x86_64 is 261 MB. The aarch64 wheel matching the *cpu* wheel's size rather than its own
      arch's GPU wheel is the proof: on aarch64 upstream ships the CPU-only build under the
      plain name, because there is no CUDA there to ship. riscv64 is in exactly that
      position, so the riscv64 deliverable for "CPU-only TensorFlow" is `tensorflow`, and a
      `manylinux_riscv64` wheel named `tensorflow-cpu` would invent a name upstream uses on
      exactly one Linux architecture — gotcha 50's divergence-with-no-gap-closed, reached
      from the sibling side.
    - **So the `-cpu` sibling is never *cheaper* than the base, and inherits its verdict.**
      The tempting inference is "the CPU-only variant sidesteps whatever made the full
      package impractical (no CUDA build to worry about)". It is backwards: on an arch with
      no CUDA the base package's build *is already* the CPU build, so the sibling saves
      nothing and is the identical compile under a worse name. If the base entry is
      `parked`, park the sibling for the base's reason plus the naming one, and say so in
      both notes — an under-documented base park is what makes an agent re-derive this.
    - **Don't inherit a sibling-family blocker citation across versions — re-verify it at
      the revision your target actually pins.** jaxlib (PR #526, parked) died in XLA's
      `xla/codegen/intrinsic/cpp` `embed_bitcode`, which links every LLVM backend except
      RISC-V, and TensorFlow vendors the whole XLA tree at `third_party/xla/`, so that reads
      like a ready-made blocker for TF too. At TF 2.21.0 it is not one: that tag's XLA
      predates the restructure (the rule is `cc_ir_header` in `cc_to_llvm_ir.bzl`, whose
      `ir_to_string` tool deps are just `llvm:Object`+`llvm:Support`, no per-arch CodeGen),
      and `xla/backends/cpu/codegen/BUILD` *does* wire `if_llvm_riscv_available(["@llvm-project//llvm:RISCVCodeGen"])`
      for the CPU JIT, with `linux_riscv64` and `riscv64_or_cross` defined in
      `xla/tsl/BUILD`. Citing the sibling's hunk anyway would put a false hard blocker in the
      queue; the honest note says "scope and naming, *not* Bazel-blocked like jaxlib".
    - **Before costing a big Bazel build, check whether its wheel is per-interpreter.**
      `_get_full_wheel_name` formats `cp{v}-cp{v}` from `HERMETIC_PYTHON_VERSION`, so TF is
      one full build **per** interpreter (cp310–cp313 = 4), with none of the abi3/`py3-none`
      collapse that let mediapipe serve every interpreter from a single ctypes-loaded `.so`.
      That multiplier belongs in the estimate before anything else.

431. **A distribution that has never shipped an sdist leaves the wheel as the only evidence —
    read the vendored blob's build provenance out of its own debug strings (the
    livekit-plugins-noise-cancellation case).** Gotchas 35 and 157 both triage a
    `py3-none-<platform>` vendored-binary wheel the same way: find the *fetch* in the sdist's
    build script (`scripts/build_driver.py`, `scripts/download_cli.py`), then ask the vendor's
    artifact index whether riscv64 exists. That method presupposes an sdist. Some
    distributions ship **none, at any version**: livekit-plugins-noise-cancellation has 13
    releases, five platform wheels each (`macosx_10_9_x86_64`, `macosx_11_0_arm64`,
    `manylinux_2_28_{x86_64,aarch64}`, `win_amd64`) and **zero** sdists — so there is no
    `setup.py`, no download script and no hardcoded platform table to grep. Upstream's
    monorepo doesn't help either: `livekit/agents/livekit-plugins/` holds ~80 plugin
    directories and *no* noise-cancellation among them (the near-miss is a differently-named
    `livekit-plugins-krisp`), a global code search for the payload filename returns only other
    people's committed `site-packages` copies, and no `Cargo.toml` on GitHub defines the crate.
    - **Count sdists across *every* release before concluding anything about source.** One
      read settles it — `curl -s https://pypi.org/pypi/<pkg>/json`, then count
      `packagetype == 'sdist'` over all of `d['releases']`, not just the target version.
      "No sdist at this version" is common and recoverable (build one from the checkout);
      "no sdist ever published, and no upstream directory" means there is no checkout to
      build one *from*, which is a different and much harder finding.
    - **`strings -a` the payload — a vendor's builder paths are its provenance.** Grep the
      blob for builder/package-manager roots: here
      `/var/lib/jenkins/.conan/data/<pkg>/<ver>/<user>/<channel>/…` named nine closed Conan
      packages on a private remote (`krisp-core/2.0.41`, `krisp-inference-engine/2.2.23`,
      `krisp-nc-processor/4.0.9`, `krisp-dsp`, `krisp-blas`, `krisp-mlops`, `krisp-common`,
      `krisp-audio-stream`, plus `fftw/3.3.10_7@krisp/stable`), every one in a `krisp/prod`
      channel. A vendor-private Conan/Jenkins path is gotcha 157's closed-source-vendor
      finding reached **without** any vendor docs, installer script or release manifest —
      and it is final: there is no public source to build for riscv64 at any version.
      Generalize the grep, not the string: `/\.conan/data/`, `/\.hunter/`,
      `/vcpkg/buildtrees/`, `/home/jenkins/`, `/builds/<org>/` all leak the same thing.
    - **Don't let open-source crates in the same output talk you out of it.** That identical
      `strings` run also lists `cargo/registry/src/index.crates.io-*/{ureq,rustls,ring,
      serde_json,flate2,…}`, which makes the blob look like an ordinary Rust build someone
      could retarget. Read what those crates *do*: an `ureq`+`rustls`+`serde_json` set is the
      licence-check HTTP client wrapped **around** the closed DSP core, not the DSP. The
      proportions say the same — 4 KB of Python, a 39 MB `.so`, and vendor-private paths
      dominating its grep hits.
    - **Price the non-code payload too.** ~64 MB of the 73 MB wheel is three opaque `.kef`
      model files with no recognizable magic bytes, and the metadata reads
      `License: SEE LICENSE IN https://livekit.io/legal/terms-of-service` — a proprietary ToS,
      not an OSS licence. Even a hypothetical riscv64 rebuild of the wrapper would still have
      to redistribute models we have no licence to republish, so the licensing answer blocks
      it independently of the missing source.
    - **Verdict `parked` on two independent grounds, and name the dependency one as well.**
      Closed at the vendor layer (gotcha 157) *and* function-gated — the README requires
      LiveKit Cloud, so the primary function is unreachable in gotcha 183's sense, not merely
      degraded. Record the second-order blocker in the same note: the mandatory
      `livekit>=0.21.3` runtime dep is itself `py3-none-<platform>` over those same five
      platforms with no riscv64 wheel, so nothing downstream of this plugin resolves on
      riscv64 today either.

436. **A big CMake project's whole non-x86 story can be one `uname -m == aarch64` boolean, and
    an `aarch64` branch is only as portable as the dependency behind it — survey every site of
    that boolean, then triage the one whose branch exists solely because *that dep* has an ARM
    SIMD shim (the Open3D case).** Open3D 0.19.0 is a 753-TU / 250 kLoC CMake C++ tree that
    upstream already builds for a non-x86 Linux arch, with a dedicated slim config
    (`docker/Dockerfile.openblas`: `BUILD_SHARED_LIBS=OFF`, CUDA/PyTorch/TensorFlow/SYCL all
    OFF) exercised by `.github/workflows/ubuntu-openblas.yml` on a GCE `t2a-standard-4`. That
    reads as a ready-made riscv64 precedent and is not one: every arch fallback in the tree is
    gated on `LINUX_AARCH64`, set in `CMakeLists.txt` by `execute_process(COMMAND uname -m)`
    matching the literal string `aarch64`, so riscv64 takes the `else()` branch written for
    x86_64 everywhere.
    - **`grep -rn <ARCH_BOOL> CMakeLists.txt 3rdparty/` *is* the survey, and it is the
      authoritative list of what upstream itself considers arch-conditional.** Here six sites,
      five of which name a prebuilt **x86_64-only** archive riscv64 would try to download:
      MKL static (`USE_BLAS=OFF` → `mkl_static-2024.1.0-linux_x86_64.tar.xz`), Filament
      (`BUILD_FILAMENT_FROM_SOURCE=OFF` → `filament-v1.9.19-linux-20.04.tgz`), WebRTC
      (`BUILD_WEBRTC=ON` → `webrtc_<rev>_cxx-abi-1.tar.gz`), the ISPC compiler
      (`BUILD_ISPC_MODULE=ON`) and prebuilt VTK 9.1 (`BUILD_VTK_FROM_SOURCE=OFF`). All five
      have a from-source route the aarch64 branch already takes, so they are configuration
      work, not blockers — the point of the survey is that the set is finite and enumerated
      before any container is started. A dep that self-gates on its own (`WITH_IPP` drops out
      via `IPP_SUPPORTED_HW AMD64 x86_64 x64`) needs nothing at all.
    - **The sixth site is the verdict: an `elseif(<ARCH_BOOL>)` that only turns the x86 ISAs
      off works because the dependency has an ARM-specific SIMD backend, and nothing more.**
      `3rdparty/embree/embree.cmake`'s aarch64 branch passes
      `-DEMBREE_ISA_{SSE2,SSE42,AVX,AVX2,AVX512}=OFF` and lets Embree pick NEON. Copy that
      branch for a third arch and gotcha 366 lands unchanged — and it is unavoidable here,
      because unlike the other five Embree has **no** `BUILD_*`/`WITH_*`/`USE_*` off switch:
      it is appended to `Open3D_3RDPARTY_PRIVATE_TARGETS_FROM_CUSTOM` unconditionally and
      `cpp/open3d/t/geometry/CMakeLists.txt` compiles `RaycastingScene.cpp` in *both* the SYCL
      and non-SYCL branch, for a class (`o3d.t.geometry.RaycastingScene`) that is documented
      public Python API. So there is no honest reduced wheel, and gotcha 41's
      "escape-hatch build with the payload missing" is the only alternative.
    - **Reproduce a third arch's configure failure on an x86 host in seconds, before booking a
      riscv64 runner.** Whatever the `aarch64` branch passes is by construction also what a
      non-x86/non-ARM arch would pass, and on an x86 host the dep's ARM boolean is OFF exactly
      as it is on riscv64 — so `cmake <embree-4.3.3-src>
      -DEMBREE_ISA_{SSE2,SSE42,AVX,AVX2,AVX512}=OFF -DEMBREE_TASKING_SYSTEM=INTERNAL` prints
      `CMake Error at CMakeLists.txt:636 (MESSAGE): You have to enable at least one ISA!` on
      any laptop. That costs one download and settles the "just add riscv64 to the arch
      boolean" patch idea, which is always the first thing you will want to try.
    - **Check the *compiler* gate on the source-build fallbacks too, not just the arch gate.**
      The Filament fallback the aarch64 branch relies on hard-errors for any non-Clang
      toolchain (`message(FATAL_ERROR "Detected C compiler ${CMAKE_C_COMPILER_ID} is
      unsupported")`, `MIN_CLANG_VERSION 6.0`) and the pinned revision is a 2021-era
      `isl-org/filament` fork, so "build it from source like aarch64 does" carries a second
      prerequisite our GCC-based manylinux images do not meet. `BUILD_GUI=OFF` sidesteps it at
      the cost of `open3d.visualization.{gui,rendering,draw}` — worth knowing, but it does not
      reach the Embree blocker, so it changes nothing about the verdict.
    - **Price it anyway, so the park note can say "and it would also have been expensive".**
      The openblas config builds OpenBLAS + VTK 9.1 + Filament + Embree + assimp/curl/
      boringssl/TBB/qhull from source and then 753 Open3D TUs, per interpreter (cp38–cp312 =
      5 full builds; the wheel is `cp3X-cp3X`, no abi3 collapse), for a ~450 MB payload each —
      against PR #2104 (mediapipe) at 5h23m plus 2h24m–3h21m of queue wait per job on the same
      shared pool. Independently disproportionate, which is worth one sentence but is *not*
      the reason: state the hard blocker first and the cost second, so an unpark attempt does
      not start by trying to make it cheaper.
438. **A "redistributable `<vendor binary>`" package can be a blob repack on *some* OSes and a
    genuine from-source build on the one that matters — decide gotcha 35/157/431 per OS, not per
    distribution (the comfy-angle/ANGLE case).** Every surface reading says vendored blob:
    summary "Redistributable ANGLE libraries", nine releases with **zero** sdists, every wheel
    `py3-none-<platform>`, and a payload of two prebuilt-looking `.so` files beside an
    `electron-LICENSE` and a 19 MB `LICENSES.chromium.html`. `scripts/download.js` plus
    `scripts/electron-version.txt` then confirm a vendor fetch — but only for Windows and macOS.
    The same repo also carries `scripts/build_linux.py`, `scripts/angle-revision.txt` and
    `scripts/depot-tools-revision.txt`, and builds the **Linux** libraries from that pinned ANGLE
    revision with depot_tools/gn/ninja. The only wheel a riscv64 port needs is the one built from
    source, so the park reasoning never applies.
    - **Enumerate the build scripts, not just the download script.** A `download.js`/`fetch_*.py`
      sitting next to a `build_<os>.py` means the vendor path is per-OS. One `README` read settles
      which is which ("Windows and macOS libraries are extracted from Electron releases. Linux
      libraries are built from the corresponding ANGLE revision"), and upstream's release workflow
      confirms it — a `download` job feeding artifacts to a separate `build-linux` job that runs
      inside a `manylinux` container is the shape to look for. Gotcha 385's "read `WHEEL`'s
      `Generator:`" does not catch this, because both halves are packaged by the same setuptools
      run.
    - **"No sdist ever" stops meaning much once the git tag builds.** Gotcha 431 treats a
      zero-sdist history as near-fatal because there is nothing to build from; here the checkout
      *is* the build input (the build-from-checkout shape), so the finding downgrades to "derive
      the version from the tag", nothing more.
    - **The depot_tools/gn/CIPD stack is already riscv64-capable, and you can prove it in minutes
      without a checkout.** `curl -s -o /dev/null -w '%{http_code}'
      "https://chrome-infra-packages.appspot.com/dl/<pkg>/<platform>/+/latest"` answers 302 when a
      CIPD package exists and 404 when it does not — calibrate with a bogus `linux-notarch` first,
      which must 404. For `linux-riscv64` these exist: the cipd client (`infra/tools/cipd`),
      `infra/3pp/tools/cpython3`, `infra/3pp/tools/ninja`, `gn/gn` and `infra/tools/luci/*`.
      depot_tools' own `detect_host_arch.py` maps `riscv*` to `riscv64`, so gclient does not reject
      the host. On the build side, `build/toolchain/linux/BUILD.gn` defines
      `gcc_toolchain("riscv64")` with `toolprefix = "riscv64-linux-gnu"`, `BUILDCONFIG.gn` selects
      `//build/toolchain/linux:$target_cpu` as soon as `is_clang=false`, and
      `config/compiler/BUILD.gn` carries riscv64 cflags.
    - **Two CIPD packages are the whole gap, and `custom_deps` removes them.** `build/siso` has no
      `linux-riscv64` build and `infra/rbe/client` (reclient) has neither `linux-riscv64` **nor**
      `linux-arm64` — which is why upstream's `DEPS` already carries a
      `not (host_os == "linux" and host_cpu == "arm64")` carve-out on reclient, the precedent to
      cite. Both are unused for a standalone checkout (`use_remoteexec` is false, and
      `use_siso_default` in `build/toolchain/siso.gni` is false unless `build_with_chromium`, so
      `autoninja` dispatches ninja), so null them in the generated `.gclient` —
      `'third_party/siso/cipd': None` — the same mechanism such scripts already use to drop
      SwiftShader/VK-GL-CTS/catapult. A missing CIPD package aborts `gclient sync` before anything
      compiles, so this is worth settling before booking a runner.
    - **The x86-only DEPS *hooks* are noise, not blockers.** `tools/clang/scripts/update.py` maps
      every Linux host to a flat `'linux': 'Linux_x64'` with no arch check, so it downloads an
      unusable x86-64 clang and succeeds; the prebuilt `glslang_validator` and `flex_bison` hooks
      are the same. A green upstream **aarch64** job is the proof that none of those binaries is
      executed by a narrow target set — reuse that argument instead of auditing each hook.
    - **Price the enabled targets, not the project's reputation.** "ANGLE" reads as
      Chromium-scale, but the gn args decide: `libEGL`+`libGLESv2` only, one backend, with tests,
      SwiftShader, dawn, the GL and WGPU backends, the validation layers and frame capture all
      off. Read the arg list before invoking proportionality (gotcha 41), and reuse the *existing*
      non-x86 branch verbatim — aliasing the container's `gcc/g++/ar/readelf/nm` under the
      `<toolprefix>-` names the GCC toolchain expects, with `is_clang=false`,
      `use_custom_libcxx=false` and `treat_warnings_as_errors=false` — so the patch is a
      toolprefix table entry rather than a new code path.
    - **Building what upstream downloads changes the licence payload.** Electron's
      `electron-LICENSE` and the `LICENSES.chromium.html` that Electron's build generates describe
      an artifact this wheel no longer contains, so shipping them would be wrong. Stage the
      licences of the tree actually built instead — the project's own `LICENSE` plus an aggregate
      of the `third_party` `LICENSE`/`LICENCE`/`COPYING` files — and collect it by directory so it
      over-reports rather than omit something statically linked.

442. **A vendored dependency's build system can silently omit a capability flag its *other* build
    system defaults on, and only auditing every dispatch site proves which one actually shipped
    (the mediapipe case).** mediapipe vendors XNNPACK, whose riscv64 RVV (vector) microkernels are
    gated behind a preprocessor macro, `XNN_ENABLE_RISCV_VECTOR`. XNNPACK's **CMake** build defines
    it (`XNNPACK_ENABLE_RISCV_VECTOR` option, default ON); XNNPACK's **Bazel** build — the one
    mediapipe actually uses — never defines it at all, in any `.bzl`/`BUILD.bazel` file. An
    undefined macro in `#if`/`#elif` evaluates to 0, so every RVV dispatch block compiles out to
    its scalar `#else` branch. That matters because roughly half of those dispatch blocks
    (68 of 128 in `src/configs/`, audited exhaustively) have **no runtime `getauxval(AT_HWCAP)`
    check** before selecting an RVV kernel — they assume the macro means what CMake's default
    would mean. On a `manylinux_riscv64` wheel, which must not crash on V-less hardware, those
    ungated blocks going live would SIGILL — and QEMU cannot catch this in rehearsal, since it
    reports the V bit set regardless of what real hardware has.
    - **"The build passed" and "the fp16 build passed" are different claims.** Gotcha 420's
      `--define=xnn_enable_riscv_fp16_vector=false` fixed a *different*, narrower macro (the
      fp16-vector family, which failed at the assembler for an unrelated ISA-string reason). It
      does not touch `XNN_ENABLE_RISCV_VECTOR`, and fixing one does not tell you the state of the
      other — check each capability macro independently by grepping the actual build files for
      where the wheel's *build system* defines it, not by pattern-matching on the vendor's most
      publicized default.
    - **The safety here is an omission, not a guarantee — re-verify on every version bump.**
      Two changes would silently turn this into a shipping SIGILL bug: XNNPACK's Bazel build
      catching up to `build_defs.bzl`'s own pattern (every sibling `XNN_ENABLE_*` macro is already
      emitted there) and adding the missing definition, or mediapipe/TFLite switching XNNPACK's
      build from Bazel to CMake. On any XNNPACK version bump inside a Bazel-built riscv64 wheel,
      re-grep `build_defs.bzl` for `XNN_ENABLE_RISCV_VECTOR`; if it appears, the ungated dispatch
      blocks go live and `--define=xnn_enable_riscv_vector=false` becomes mandatory, not optional.

449. **A prebuilt riscv64 binary an upstream downloads for you can be built for a *vendor* ISA —
    `file`/`e_machine 243` tells you it is riscv64, not *which* riscv64 (the openvino/oneTBB
    case).** Gotcha 418's rule was "`file`/`readelf -h` every `.so` in the sibling wheel"; this is
    the column that rule is missing. OpenVINO's `cmake/dependencies.cmake` `ov_download_tbb()`
    fetches `oneapi-tbb-2022.3.0-lin-riscv-release.tgz` from storage.openvinotoolkit.org and
    `setup.py` bundles it into the wheel exactly as it does the x86_64/aarch64 TBB. Triage
    downloaded it and recorded "genuine riscv64 oneTBB (ELF e_machine 243)" — true, and not
    enough. Its `Tag_RISCV_arch` is
    `rv64i2p0_m2p0_a2p0_f2p0_d2p0_c2p0_**xtheadc**2p0`: a T-Head Xuantie toolchain build.
    - **Confirm from the instruction stream, not just the attribute.** Standard RISC-V never
      emits the CUSTOM-0 opcode `0x0B` (nor `0x2B`/`0x5B`/`0x7B`). `libtbb.so.12` holds **906**
      such instructions in 166 KiB of `.text` and `libtbbmalloc.so.2` **892** in 97 KiB, while
      the **17 libraries OpenVINO compiled itself in the same wheel have zero across 52 MiB** —
      the control that makes the count trustworthy. So the vendor instructions are really there;
      the attribute is not a toolchain default that emitted nothing.
    - **What it costs: the wheel is T-Head-only, and a green run stops being transferable.**
      Those blobs execute fine on this repo's runner fleet — which is itself the finding, since
      it means the fleet is T-Head (C906/C910/C920 class: TH1520, SG2042), and it is why nothing
      caught this. The same wheel would SIGILL on SiFive U74/P550, JH7110, or plain QEMU
      `rv64gc`. **CI passing on a T-Head fleet is not evidence that a `manylinux_riscv64` wheel
      is portable**, and this is a second, independent shipping blocker from gotcha 448's RVV
      one — fixing the RVV question alone still leaves a vendor-ISA blob in the wheel.
    - **It also explains neighbouring symptoms.** A fleet that runs `xtheadc` is a T-Head core,
      hence RVV **0.7.1**, hence gotcha 272's otherwise-odd pairing: HWCAP advertises V and the
      first RVV-1.0 `vsetvli` is still illegal. Treat "which riscv64 is the runner?" as a fact
      worth establishing once, from binaries that already run there.
    - **The check is cheap and needs no riscv64 binutils**: parse the section headers in Python,
      regex `rv(32|64)[0-9a-z_p]+` out of `.riscv.attributes`, and walk `.text` counting opcodes
      (skip RVC halfwords — low two bits `!= 0b11`). Do it at triage on every prebuilt the build
      downloads, not after a 12-hour build has already spent the runner slot.

450. **A vendored native payload can be a *GraalVM Native Image*, which moves the wall from
    "is there source?" to "does the AOT toolchain target riscv64?" (the saxonche/SaxonC-HE
    case).** Gotchas 35/157/431 triage a vendored blob by hunting for its source or its
    vendor's artifact index; gotcha 376 adds "a permissive `License:` says nothing about the
    payload". saxonche is the shape those miss, because it is neither closed-source nor
    portable: it is MPL-2.0 Java, published, that only exists as a native library because
    Saxonica AOT-compiles it with GraalVM Native Image — and Native Image itself is what has no
    riscv64.
    - **The tell is three `strings` hits in the big `.so`, and it takes seconds.**
      saxonche 13.0.0 ships 35 wheels, all genuinely `cpXY-cpXY` (so gotcha 27's ABI-tag rule
      waves it through) and ~41 MB each, and has **never published an sdist** on any of its 14
      releases, so per gotcha 431 the wheel is the only evidence. `unzip -l` sorted by size
      splits it cleanly: a 7.8 MB `saxonche.cpython-312-<arch>-linux-gnu.so` (a real Cython
      extension, built from the `saxonc/saxonc.cpp` the wheel also ships), a 617 KB
      `saxonche.libs/libsaxonc-he-*.so.13.0.0` (the C++ API glue) — and
      `saxonche.libs/libsaxonc-core-he-*.so.13.0.0` at **109 MB, 87% of the wheel**.
      `strings -a` that one and it says `GraalVM CE 25.0.1+8.1 (serial gc)`,
      `com/oracle/svm/core/…` and `.svm_heap`: it is the whole SaxonJ engine AOT-compiled, not
      hand-written C++. Upstream's release notes confirm it in as many words ("SaxonC 13 is
      built from SaxonJ 13 using GraalVM Native Image (version 25.0.1)"). Add
      `GraalVM`/`svm_heap`/`com.oracle.svm` to the `strings` vocabulary beside gotcha 431's
      `/.conan/data/…` builder paths.
    - **`readelf -d` decides whether the missing payload is fatal or merely degrading.** Here
      the extension carries `RPATH $ORIGIN/saxonche.libs` and a hard
      `NEEDED libsaxonc-core-he-*.so.13.0.0`, so with no core there is no `import` at all —
      stricter than gotcha 157's claude-agent-sdk, whose sdist still imports and only fails per
      call. Do this before reasoning about runtime behaviour; a `NEEDED` edge ends the enquiry
      that a `dlopen` would only start.
    - **Published source can still be no build.** The Saxon-HE GitHub *releases* do carry
      SaxonC-HE source zips (`SaxonCHE-source-12-9-0.zip`, 242 KB, 91 files: the C/C++ glue
      under `src/main/c/`, the `net.sf.saxon.option.cpp` Java bridge under `src/main/java/`,
      and the Cython `python/saxonc/saxonc.pyx`) — and **zero build files**: no
      Makefile/CMakeLists/pom.xml/setup.py and no native-image configuration at all (no
      reflect-config, no `native-image.properties`). Its own README calls it "the source files
      used to build SaxonC-HE", which is not the same claim. Worse for the version actually
      queued: the `SaxonHE13-0` release carries only `SaxonHE13-0J.zip` and `saxon13-0source.zip`
      (both SaxonJ), and `downloads.saxonica.com/SaxonC/HE/13/SaxonCHE-source-13-0-0.zip` is a
      404. `unzip -l <src>.zip | grep -icE 'makefile|cmake|pom\.xml|setup\.py|\.json'` returning
      0 is the check — run it before concluding a source drop gives you a from-source path.
    - **Then ask the AOT toolchain's artifact index — three HEAD requests, nothing downloaded.**
      `download.oracle.com/graalvm/25/latest/graalvm-jdk-25_linux-{x64,aarch64}_bin.tar.gz` → 200,
      `linux-riscv64` → **404**; GraalVM CE
      (`graalvm-community-jdk-25.0.1_linux-{x64,aarch64}_bin.tar.gz`) → 200, `linux-riscv64` →
      **404**; and Mandrel, Red Hat's native-image-only distribution
      (`mandrel-java25-linux-{amd64,aarch64}-25.0.1.0-Final.tar.gz`) → 200, `riscv64` → **404**.
      Native Image's distribution list belongs in the collection beside `nodejs.org/dist`,
      NVIDIA's redist index, conda `repodata.json` and npm `optionalDependencies`. The vendor's
      own table says the same thing one layer up: `downloads.saxonica.com/SaxonC/HE/13/` answers
      200 for `SaxonCHE-linux-x86_64-13-0-0.zip` and `SaxonCHE-linux-arm64-13-0-0.zip`, 404 for
      every riscv64 spelling.
    - **An arch enum inside the toolchain is not shipping support for that arch.** This one is a
      genuine trap: `Platform.LINUX_RISCV64` has been a Native Image leaf platform since 22.2,
      and `oracle/graal` master really does carry `ELFMachine.RISCV64` with a full
      `ELFRISCV64Relocation` table — searching for "GraalVM riscv64" turns up a 2023 GraalVM blog
      post announcing it works. Read *how*: riscv64 is reached through the **LLVM backend**, not
      the Graal compiler, and that backend's own doc says it "is not included by default as part
      of Native Image" — you build GraalVM from source with
      `mx --dynamicimports /substratevm build` and pass `--tool:llvm-backend`, and the riscv64
      port behind the post was a GraalVM **dev build**. So the enum proves a research port
      landed, not that any shipped `native-image` can emit a riscv64 image. Generalize it:
      when an arch appears in a build tool's *source* but in none of its *releases*, the
      releases are the fact.
    - **Verdict: park, and say which layer is missing.** Per gotcha 183, everything the package
      exists for routes through the Native Image core, so this is unreachable, not degraded.
      Doing it ourselves would mean bootstrapping a riscv64 GraalVM from source with an unshipped
      experimental backend *and then* reinventing a native-image recipe (entry points, reflection
      config, resource config) upstream has never published, for a version whose SaxonC source is
      not published either — the opposite of goal 2's "mirror upstream's own CI, narrowed to
      riscv64". Note also that `saxonche`/`saxoncpe`/`saxoncee` are one engine behind three
      licence tiers, so the verdict carries to all three at once (and PE/EE have no published
      source at all) — gotcha 382's "one build, several distributions" arithmetic applied to a
      park rather than to a port.

452. **A GPU-only package can enforce the GPU from its *pure-Python* `__init__.py`, through a
    driver-probe module that has no CUDA linkage of its own — and a documented CUDA-free build
    flag upstream never ships rescues nothing (the pynvvideocodec case).** Gotcha 411 says to
    read the backend selector before parking a GPU-first package, and gotcha 284 says a
    CUDA-calling extension is not automatically blocked. pynvvideocodec (NVIDIA's PyNvVideoCodec,
    the Python binding for the NVENC/NVDEC hardware engines) answers both the other way, and the
    mechanism is worth recognising because the obvious first check points the wrong way.
    - **The probe module is the gate, and it is CUDA-free.** The wheel ships *three* extensions:
      `PyNvVideoCodec_121.*.so` and `PyNvVideoCodec_130.*.so` (two NVENC API variants) plus a
      small `VersionCheck.*.so`. `readelf -d VersionCheck…so` lists only
      `libstdc++/libm/libgcc_s/libc` — no CUDA at all — yet that module is what makes the package
      unusable: its `DriverWrapper` does `dlopen("libnvidia-encode.so.1", RTLD_LAZY)` and throws
      on failure. **Read the pure-Python entry point before trusting any `readelf`**: the
      top-level `__init__.py` runs `_get_driver_version()` at import, unconditionally, with no
      lazy path and an `except` that re-`raise`s, then picks `_121` vs `_130` from the version the
      driver reports (`>= 13*16` → `_130`, `>= 12*16+1` → `_121`, else
      `RuntimeError("Driver version is too old")`). So `import <pkg>` cannot succeed without the
      proprietary driver — stricter than gotcha 284's counterexample and than gotcha 183's
      playwright, which at least imports. The real extensions confirm it one layer down:
      `DT_NEEDED libcuda.so.1` plus a vendored `libcudart-*.so.12.*`, undefined `cuInit`/
      `cuCtxCreate_v2`/`cuMemAlloc_v2`/`cudaLaunchKernel@libcudart.so.12`, `.nv_fatbin` +
      `.nvFatBinSegment` sections, and a `dlopen` of `libnvcuvid.so.1` for the whole `cuvid*`
      NVDEC API.
    - **A CUDA-free build mode is not a CPU backend — check three things before calling it an
      escape hatch.** The CMake tree has `option(DEMUX_ONLY …)`, and it is real: it skips
      `find_package(CUDAToolkit 11.2 REQUIRED)` and the entire `VideoCodecSDKUtils` subdirectory
      (four `.cu` files, `project(… LANGUAGES CXX CUDA)`, an SM-50…90 `CMAKE_CUDA_ARCHITECTURES`
      list) and compiles two demuxer sources against ffmpeg. It still yields nothing, and the
      three questions that settle any such flag are: (a) **does upstream ship it?** — `setup.py`
      is a bare `skbuild.setup()` that never sets it, and the released wheels contain both
      CUDA variants, so a `DEMUX_ONLY` wheel is gotcha 41's rejected offline build / gotcha 387's
      docs-only stub, published under a name that promises hardware codecs; (b) **does the
      package's Python entry point gate on the GPU independently of the flag?** — here yes, the
      same `__init__.py` ships either way and still dlopens `libnvidia-encode.so.1` first, so the
      artifact would not even import on riscv64; (c) **what is left?** — an ffmpeg demuxer, with
      every encode/decode/transcode API `#ifdef`-ed out, i.e. gotcha 419's dead stub reached by a
      build flag rather than a torch branch.
    - **"Distributed via NGC, not PyPI" is worth checking and was false here** — and the check is
      cheap, unauthenticated and useful for any NVIDIA package. `pypi.org/pypi/<pkg>/json` shows an
      ordinary project (19 wheels, cp310–cp314, manylinux x86_64/aarch64 + Windows, **no sdist**,
      zero `requires_dist`), so `pip install` is the documented path and no NGC key is involved;
      NGC carries a *separate, fully public* source zip, and
      `api.ngc.nvidia.com/v2/resources/<org>/<name>` reports `isPublic: true` /
      `canGuestDownload: true`, with `…/versions/<v>/files` naming the artifact and
      `…/versions/<v>/files/<name>` fetching it anonymously (the `…/versions/<v>/zip` form 404s).
      Add that pair to the artifact-index collection beside `nodejs.org/dist`, NVIDIA's redist
      manifests, conda `repodata.json` and npm `optionalDependencies`. Source being public did not
      change the verdict — it is what let the `DEMUX_ONLY` and `__init__.py` reads above be made
      against the real tree rather than inferred.
    - **A secondary arch wall usually sits behind the first; name it, don't stop at it.** The
      bundled prebuilt ffmpeg has exactly `lib/{x86_64,aarch64,x64,arm64}`, and `ffmpeg.cmake`
      maps `CMAKE_SYSTEM_PROCESSOR` to those four only, leaving the library dir empty on anything
      else so `link_av_component` fails with "Required FFmpeg library avformat not found". That
      one is fixable (the wheel even ships the ffmpeg source tarball for LGPL compliance) — which
      is exactly why it must not be reported as the blocker.
453. **A closed commercial engine is not one build recompiled per architecture — each arch
    statically links a *different* proprietary math kernel, and the x86_64↔aarch64 wheel-size
    gap names which one (the gurobipy case).** gurobipy 13.0.3 reproduces gotcha 372's hdbcli
    double lock exactly — `home`/`repo` both `https://www.gurobi.com`, `License: Proprietary`,
    zero sdists across all 28 releases ever published (so per gotcha 431 the wheel is the only
    evidence), and a bundled `dist-info/licenses/LICENSE.txt` whose §2.1/§2.2 grant is
    "non-transferrable, non-sublicensable" and states "You will not use, copy, modify, or
    distribute the Product", which forecloses rehosting a rebuilt wheel on
    `pypi.riseproject.dev` independently of whether one could be built. The reusable finding is
    the *third* lock, and it is two commands deep:
    - **Diff the platform wheels' sizes, then `strings` the gap.** The same cp312 wheel is
      15.0 MB for `manylinux_2_17_x86_64` and 87.2 MB for `manylinux_2_26_aarch64`; unzipped,
      `gurobipy/.libs/libgurobi130.so` is 49.6 MB vs 168.5 MB. `strings -a` identifies the
      delta: the x86_64 engine has Intel MKL linked in (`mkl_avx_d_opt_gemm_ker`,
      `Intel(R) Math Kernel Library Version`, `Intel MKL FATAL ERROR: This system does not meet
      the minimum requirements…`), the aarch64 one Arm Performance Libraries
      (`ARMPL_NEOVERSE_N1`, `ARMPL_KUNPENG_920`, `ARMPL_APPLE_M1`). Neither engine contains a
      single `riscv`/`rv64` string (0 hits in 712k). Gotcha 81 uses the size diff across
      platform wheels to prove there *is* per-platform content; here the same one-JSON-read
      diff tells you *what* the vendor would have to replace, and the answer — a
      hand-optimised closed BLAS for our arch, from Intel or Arm, which neither ships — is
      why a vendor port is not a recompile.
    - **The shipped LICENSE file enumerates the vendored toolkits for free.** Gurobi's
      `LICENSE.txt` carries a "SIMPLIFIED END USER LICENSE AGREEMENT FOR FREE OF CHARGE ARM
      REDISTRIBUTABLES" section beside the Apache/BSD notices — reading the third-party
      sections of a proprietary wheel's own licence text names its bundled vendor components
      before any `strings` run, the mirror image of gotcha 376's HYPER_API_OSS_disclosure read.
    - **A commercial vendor has the same two independent platform tables as an open one**
      (gotcha 35/157's artifact-index move, gotcha 42's count-don't-trust-the-status):
      `packages.gurobi.com/13.0/gurobi13.0.3_{linux64,armlinux64}.tar.gz` and the macOS pkg
      answer `206` to a 2-byte range request while every riscv64 spelling 404s; and the
      vendor's own conda channel has 124/88/122/124 packages in
      `linux-64`/`linux-aarch64`/`osx-64`/`win-64` against **0** in `linux-riscv64`, which
      still returns `200` with a synthesised empty index. Upstream's docs agree in prose —
      the Supported Platforms table lists exactly `win64`, `linux64`, `macos_universal2`,
      `armlinux64`.
    - **A licence-key-gated payload has no swap-in escape hatch.** Gotcha 35's playwright
      could in principle have been fed an unofficial Node build; here the wheel ships
      `gurobipy/.libs/gurobi.lic` (`TYPE=PIP`, `EXPIRATION=`, `KEY=`) and the engine carries
      the whole enforcement path (`Invalid PIP license`, `HostID mismatch (licensed to %x…)`,
      `Model too large for size-limited license`), so any substitute binary would have to be
      one the vendor signed. And the payload is hard-linked, not dlopened:
      `readelf -d gurobipy/_core.cpython-312-*.so` shows `NEEDED libgurobi130.so` plus
      `RPATH $ORIGIN/.libs`, and `gurobipy/__init__.py` imports `._core`/`._batch`/`._matrixapi`
      at import time — the saxonche/gotcha 450 shape (no engine ⇒ no importable wheel at all),
      stricter than gotcha 157's claude-agent-sdk, which at least imports.
    - **"Is there a community edition?" is answered by the vendor's own OSS page, not by
      searching for a source repo.** Gurobi publishes gurobipy-pandas, gurobi-machinelearning,
      gurobi-optimods, gurobi-modelanalyzer and gurobi-logtools under Apache-2.0 and states in
      the same article that the calls those make into "the proprietary Gurobi library" are a
      support matter — wrappers around the engine, never the engine or `gurobipy` itself. One
      read, and it also tells you which sibling distributions on the queue *are* ordinary
      pure-Python ports.

459. **A CUDA-only PyPI wheel does not make the *project* CUDA-only — look for a
    device-selecting build env var before parking a GPU package (the vllm case).** Gotchas
    41 (triton), 284, and the `sglang`/`cuda-tile` parked entries all triage a GPU package
    by what its *published wheel* requires, and for those that was the whole story. vLLM
    looks identical at that level and is not: `pypi.org/pypi/vllm/json` shows two
    `cp38-abi3-manylinux_2_28_{x86_64,aarch64}` wheels of ~310 MB whose `requires_dist` is
    unconditionally NVIDIA — `flashinfer-python`, `nvidia-cutlass-dsl[cu13]`,
    `PyNvVideoCodec`, `nvtx`, `tilelang`, `quack-kernels`, none of them behind a marker. But
    `setup.py` reads `VLLM_TARGET_DEVICE` (auto-detected from the *build host*, which is why
    the published wheels are CUDA), `get_requirements()` selects
    `requirements/<device>.txt` from it, and `get_vllm_version()` appends a `+cpu` local
    segment — so the same tag builds a second, differently-versioned distribution under the
    same name whose dependency closure has no NVIDIA package in it at all. The port target
    is `0.29.0+cpu`, the same shape `torch` is already published as here.
    - **Read `requirements/<device>.txt` for our arch's marker before anything else — it is
      upstream stating which arches it expects to work.** vLLM's `requirements/cpu.txt`
      already excludes `torchaudio`, `torchvision`, `torchcodec`, `llguidance` and
      `xgrammar` on `platform_machine == "riscv64"` and pins `torch==2.13.0` there
      specifically (the aarch64/x86_64 lines pin `2.13.0+cpu` instead). An upstream that has
      written per-arch markers for riscv64 has already done the dependency triage for you;
      confirm with `grep -rn riscv cmake/ csrc/` that real kernels back them
      (`cmake/cpu_extension.cmake` has a `CMAKE_SYSTEM_PROCESSOR MATCHES "riscv64"` branch,
      `csrc/cpu/` has RVV intrinsics and `cpu_types_riscv*.hpp`, `vllm/platforms/` has a
      `CpuArchEnum.RISCV`), or you are reading aspirational markers.
    - **The docs are not the test — code and requirements markers are.** vLLM's
      `docs/getting_started/installation/cpu.md` lists only x86/ARM/Apple/S390X, its
      `docker/Dockerfile.cpu` handles only `amd64`/`arm64`, and no CI job builds riscv64. An
      arch can be fully implemented and simply undocumented; conversely a documented arch
      can be stale. Grep the build system, not the prose.
    - **The remaining blocker is usually one ordinary dependency, and the marker list tells
      you how upstream already handles it.** Here it is `numba` (gotcha 40/187's
      llvmlite/conda wall), required by `cpu.txt` on every arch *except* s390x. That is not
      automatically a `blocked-on-dependency` park: the project declares numba optional
      (`vllm/utils/import_utils.py::is_numba_available()`), degrades to a non-numba path
      when it is missing, and already ships s390x in exactly that configuration — so
      extending the existing exclusion to riscv64 is a one-line marker patch that reproduces
      a state upstream already supports, not a fork of its architecture. Park only when the
      absent dependency has *no* upstream-supported degraded mode; check for an
      `is_<dep>_available()`-style probe and an arch already excluded from the same
      requirement line before deciding.
    - **A native runner's `/proc/cpuinfo` is not a wheel's target.** `cpu_extension.cmake`
      auto-detects `VLLM_RVV_VLEN` by grepping the build host's `zvl<N>b`, then compiles
      `-march=rv64gcv_zvfh…zvl<N>b`. On this repo's native `ubuntu-24.04-riscv` runners that
      silently bakes whatever vector extensions that machine happens to have into a wheel
      every riscv64 user installs — gotcha 259/274's "compiled with RVV means assumes RVV",
      reached through host auto-detection rather than a hardcoded flag. Force the baseline
      explicitly (`CMAKE_ARGS=-DVLLM_RVV_VLEN=0`, upstream's documented scalar `rv64gc`
      mode); it also disables the oneDNN dependency, which is gated on the same probes.
    - **A portable *design* still has to survive the build.** The CPU backend here needed two
      further fixes, both invisible from the triage above and both found only by CI: a build
      dependency upstream installs in its Dockerfile rather than declaring (gotcha 460) and a
      BLAS symbol its CMake assumes every non-x86 torch wheel carries (gotcha 461). Treat
      "the project supports this arch" as permission to start, not as a prediction of a green
      first run.

462. **A `<pkg>-core` split sibling is still its own port after the main package shipped in the
    *non-split* shape — the self-contained wheel closes the Python gap, not the
    native-consumer one (the sherpa-onnx-core case; see `build-sherpa-onnx-core.yml`).**
    Gotcha 382/383 covers a split family as *one* unit of work; the trap here is the reverse
    reading. `sherpa-onnx` was already ported and published for riscv64 by deliberately
    building upstream's **non-split** shape (`SHERPA_ONNX_SPLIT_PYTHON_PACKAGE` unset), which
    bundles `libsherpa-onnx-c-api.so`, `libsherpa-onnx-cxx-api.so`, `libonnxruntime.so` and the
    C-API headers straight into the one wheel — precisely *because* the `-core` sibling had no
    riscv64 wheel. That makes the sibling look closed out, and it isn't: `pip install
    sherpa-onnx` on riscv64 delivers every `.so` and header, yet `python3 -m sherpa_onnx
    --cflags` / `--c-api-libs` still fails, because the non-split wheel omits the two files
    that *are* the `-core` package's Python half (`sherpa_onnx/_info.py` and
    `sherpa_onnx/__main__.py`, ~1.8 KB together). Those are upstream's documented way for
    C/C++/Rust/Go/Dart consumers to locate the payload, and upstream's own CI tests them as a
    separate "Test sherpa-onnx-core" step.
    - **Diff the two distributions' Python file lists, not their `.so` lists.** `unzip -l` both
      wheels and compare only the non-`lib/`, non-`include/` entries; the native payload is the
      part everyone checks and the part most likely to be identical. A split family's `-core`
      package often carries a *discovery shim* whose absence is invisible to an import smoke
      test and fatal to the package's actual audience.
    - **The `py3-none` tag is honest here, which collapses the matrix** (gotcha 81's ctypes
      reading, one step further: there is no `PyInit_*` *and* no `ctypes` loader — the wheel is
      libraries plus headers plus a path-printing shim). One build serves every interpreter, so
      there is no `python:` matrix at all; still install it on each of cp312/cp313/cp314/cp314t,
      since the Python half is all that varies per interpreter.
    - **Porting it also un-blocks the sibling's own divergence.** The non-split build is a
      deviation from what upstream publishes (its `install_requires` is
      `sherpa-onnx-core==<ver>` in the split shape), so landing `-core` is what would later let
      `build-sherpa-onnx.yml` match upstream — goal 2 paid back. Say so in the PR rather than
      leaving the two workflows looking like unrelated choices.
    - **Watch for the file-collision footnote.** Both distributions install into the same
      `sherpa_onnx/` directory, so a user who installs both gets overwrites. It is benign here
      (our non-split wheel's `Requires-Dist` names no `-core`, so pip never pulls it in
      implicitly) but it is worth one PR line, because the same shape in another family could
      break the base package.

464. **A full `cpXY-cpXY-<platform>` tag can be fabricated by `has_ext_modules()` alone, and
    the payload behind it can be a foreign-language runtime the package only shells out to
    (the artifacts-keyring case).** Gotcha 27 made the ABI half of the tag the fast, reliable
    signal: `py3-none-<platform>` is a hand-set `--plat-name`, while `cpXY-cpXY-<platform>`
    means a real extension module pinned to a CPython build. The second half of that is not
    safe. artifacts-keyring 1.0.0 publishes 16 Linux wheels across cp39–cp313 **and**
    pp39/pp310/pp311 and compiles nothing: `setup.py` declares no `Extension` at all, but
    subclasses `Distribution` with `has_ext_modules()` returning a hardcoded `True` and
    `bdist_wheel.finalize_options` setting `root_is_pure = False`, which is all setuptools
    needs to emit an interpreter+platform tag. The 33 MB body is Microsoft's .NET Azure
    Artifacts credential provider, downloaded at build time from a *different* repo's
    releases (`Microsoft/artifacts-credprovider` v1.4.1).
    - **Two tells outrank the tag, and both are in the PyPI JSON.** A **PyPy tag beside
      CPython tags** for a supposedly compiled package (`pp310-pypy310_pp73-manylinux…`) —
      nobody builds a CPython C extension for PyPy's ABI by accident — and **wheel sizes that
      are identical across interpreters** (33257355–33257357 bytes for every one of
      cp39…cp313 aarch64). A real extension cannot be byte-size-identical across ABIs.
      `unzip -l | grep '\.so'` then confirms it: the only `.so`s are the vendored runtime's
      (`libcoreclr.so`, `libclrjit.so`, …), and no `PyInit_*` exists anywhere.
    - **The arch payload is picked by an env var with a silent fallback — read the fallback,
      not just the platform table.** Upstream's pipeline sets
      `ARTIFACTS_CREDENTIAL_PROVIDER_RID` per job (`win-x64`, `osx-x64`, `osx-arm64`,
      `linux-x64`; `[tool.cibuildwheel.linux] archs = ["x86_64", "aarch64"]`) to fetch the
      *self-contained* provider for that RID. Unset — or set for an arch the helper doesn't
      know — and `get_runtime_identifier()` prints a warning, returns `""`, and the build
      downloads the **framework-dependent** provider instead: arch-neutral managed
      assemblies, the same payload the sdist carries. So a riscv64 build never fails; it
      succeeds and yields a wheel containing nothing riscv64-specific. A fallback that
      degrades the *content* instead of erroring is the dangerous shape — it looks like a
      green port.
    - **Then the wall is one layer outside Python: the payload needs `dotnet` on PATH.**
      `plugin.py` treats the presence of a `runtimes/` directory as "not self-contained", runs
      `dotnet --list-runtimes`, raises `Unable to find dependency dotnet` when it is missing,
      and only otherwise runs `dotnet exec CredentialProvider.Microsoft.dll`. Microsoft ships
      no `linux-riscv64` .NET runtime (community builds only — dkurt/dotnet_riscv,
      filipnavara; RISE's own LR_04_001 is porting it) and no riscv64 self-contained
      credprovider asset. Note `runtimeconfig.json`'s `"rollForward": "Major"`, which means a
      future riscv64 .NET ≥8 *would* run the net8.0 provider unchanged — the missing piece is
      a runtime the user installs, not bytes a wheel could ship.
    - **Rehearse the riscv64 artifact on x86_64 in one command.** `env
      ARTIFACTS_CREDENTIAL_PROVIDER_NON_SC=true pip wheel <sdist> --no-deps` takes the exact
      same code path riscv64 takes and produced `…-cp311-cp311-linux_x86_64.whl`, 5.8 MB, zero
      `.so`, 49 entries; installing it imports fine and registers the keyring backend, while
      constructing `CredentialProvider()` raises the missing-`dotnet` error. (It needs
      setuptools ≥ 70.1 for `setuptools.command.bdist_wheel`, which `[build-system] requires =
      ["setuptools>=42", …]` under-declares — use a fresh venv, not a distro setuptools.)
    - **Verdict: parked, under both existing rules at once.** Gotcha 27's watchdog clause —
      upstream ships no `py3-none-any` wheel, so riscv64 `pip install` already falls back to
      the sdist, which needs no compiler, finishes in seconds and installs exactly the
      arch-neutral bytes a riscv64 wheel could carry, making the wheel a packaging
      convenience, not a port — and gotcha 183's, because the primary function (fetch Azure
      Artifacts credentials by executing the provider) is *unreachable*, not merely degraded,
      until a riscv64 .NET runtime exists. Either one alone parks it; recording both is what
      makes the entry re-checkable when .NET riscv64 lands.

465. **A closed vendor accelerator blob can be *full* of `riscv` — because the ISA runs on
    cores inside the accelerator, not on the host (the libtpu case).** Every earlier
    vendor-payload gotcha triages a blob whose arch strings name the *host*
    (35/157/431/449/453). libtpu inverts the tell and is the one blob where grepping for our
    own architecture actively misleads: `strings -a libtpu/libtpu.so | grep -ci riscv` returns
    1190 (1188 unique), including a complete LLVM RISC-V code generator
    (`_GLOBAL__sub_I_RISCVTargetMachine`, `…RISCVISelLowering`, `…RISCVInsertVSETVLI`,
    `…RISCVZilsdOptimizer`, the `riscv-br-merging-base-cost` `cl::opt` help text, the whole
    `R_RISCV_*` reloc table) — and the wheel is still `manylinux_2_31_x86_64` only, in all 60
    releases since 2021. Two reads separate "compiled *for* riscv64" from "compiles *to*
    riscv64":
    - **`readelf -h` the payload, and list which LLVM targets are actually registered.**
      `Machine: Advanced Micro Devices X86-64`, and the registration entry points present are
      exactly `LLVMInitialize{AArch64,ARM,PowerPC,TPU,X86}Target{,Info,MC,AsmParser,AsmPrinter}`
      — no `LLVMInitializeRISCVTarget` — beside a custom in-tree `TPU` backend
      (`llvm::TPUInstrInfo::isMxuInstr`, `llvm::TPUAAResult`). The RISC-V TUs are linked but
      unregistered, i.e. dead or device-side code, not a host target.
    - **The device-side ISA leaves proto/path fingerprints; read those, not the string count.**
      `platforms/asic_sw/lib/common/riscv/results.proto`, `.asic_sw.riscv.ExceptionInfo` and
      `.asic_sw.riscv.StackFrameWithException` sit next to `platforms/asic_sw/driver/...`,
      `/dev/accel0`, `/dev/vfio/*` and chip codenames (`jellyfish`, `pufferfish`, `viperfish`,
      `TPU v4`…`TPUv7`) — the RISC-V here is firmware/exception plumbing on the ASIC, reached
      only through the vendor's own kernel driver. Same distinction as gotcha 41's
      cross-compiler-for-someone-else's-ISA, with the ISA swapped so it reads as good news.
    - **A sibling `.so` in the same wheel carries the internal builder path.** `libtpu/sdk.so`
      (23 MB, a *real* extension module — `PyInit_sdk` plus 159 undefined `Py*` symbols, so the
      `cpXY-cpXY` tag is honest here, unlike gotcha 464's) contains
      `bazel-out/k8-fastbuild/bin/sdk/client/python/sdk.so`. Bazel's `k8` is its x86_64 CPU
      name: the release is configured for one host arch inside a tree nobody outside the vendor
      has, and the project has never published an sdist (220 files on PyPI, 0 `.tar.gz`).
    - **Two independent artifact indexes, then the framework's own platform table.** PyPI's
      file list and the vendor's own bucket index
      (`storage.googleapis.com/libtpu-releases/index.html`, 1283 wheel links across
      libtpu/libtpu-nightly/jaxlib) both answer zero for `riscv|aarch64|arm64`; JAX's
      installation matrix states Cloud TPU is supported on Linux x86_64 and `n/a` everywhere
      else. And there is no CPU/simulator mode to fall back on — no `TPU_*` flag or string
      offers one.
    - **A `LICENSE` file that names a *cloud agreement* is a redistribution stop on its own**
      (gotcha 453's EULA point, in its cheapest form): libtpu's 298-byte `LICENSE` says the
      payload "is made available as \"Software\" under the agreement governing your use of
      Google Cloud Platform", i.e. cloud.google.com/terms, whose §3.3 bars copying, derivative
      works and distribution of the Services. No source, no non-x86_64 vendor build, and no
      right to republish the bytes even if one appeared — three independent parks.

467. **Gotcha 341's foreign-ecosystem code generator, one step harder: a generator that runs at
    *runtime* over arbitrary user input has no "pre-generate it on x86_64 and vendor the output"
    escape hatch (the httpstan/stanc3 case).** httpstan 4.17.0 is the Stan REST server PyStan
    3.x drives, and it hits the same `stan-dev/stanc3` wall gotcha 341 found through
    prophet/CmdStan — but the shape of the wall differs in the one way that matters. prophet
    transpiles *one fixed* `prophet.stan` at wheel-build time, so 341 could at least name a
    hypothetical bypass (run `stanc` on x86_64 once, carry the generated `.hpp` as a patch,
    leave riscv64 compiling only portable C++). httpstan's entire product is
    `POST /v1/models` with a caller-supplied Stan program: `httpstan/compile.py` shells out to
    the bundled binary per request — `subprocess.run([stanc_binary, "--name", …,
    "--print-cpp", filepath], timeout=1)` — and that is the only path to C++ in the package
    (no endpoint, flag or env var accepts pre-generated code; `httpstan/models.py` then feeds
    the result to `setuptools.Extension` and links it against the shipped `stan_services.o`).
    The transpiler therefore has to be a *native executable inside the wheel*, and no amount
    of ahead-of-time generation substitutes for it. So: **when a package embeds a code
    generator from another language ecosystem, classify it by when it runs before costing the
    port** — build time with a fixed input set is a maybe (pre-generation is expressible as a
    patch); runtime over arbitrary input is `blocked-on-dependency` with no patch-shaped fix,
    however portable the rest of the C++ is. Four supporting reads, each cheap:
    - **Probe the generator's release assets by URL, not just its docs, and probe the moving
      tag too.** `curl -sS -o /dev/null -w '%{http_code}' -L -r 0-0
      https://github.com/stan-dev/stanc3/releases/download/<tag>/linux-riscv64-stanc` returns
      404 for `v2.39.0` (httpstan's pinned `STANC_VERSION`), `v2.40.0`, `v2.41.0` and
      `nightly`, while `linux-stanc`, `linux-arm64-stanc`, `linux-armhf-stanc`,
      `linux-ppc64el-stanc`, `linux-s390x-stanc` and `mac-stanc` all answer 206 — a one-command
      check that works even when the GitHub API is unreachable for that org.
    - **Read the generator's own CI matrix: it names the upstream ask and the right repo to
      file it against.** stanc3's `Jenkinsfile` has a literal
      `values 'arm64', 'ppc64el', 's390x', 'armhf', 'armel'` axis fed to a
      `qemuArchFlag()` → `--platform=linux/<arch>` Docker build over
      `scripts/docker/static-builder/Dockerfile`. riscv64 is a missing *matrix entry* in a
      mechanism that already exists, so the actionable request is on `stan-dev/stanc3`, not on
      the package being ported — worth recording in the queue note, because it is a far
      cheaper ask than it looks from the consumer side.
    - **"The image packages the language" is not "the image packages the pinned toolchain."**
      `quay.io/pypa/manylinux_2_39_riscv64` (Rocky Linux 10.2) does have `ocaml 5.2.0-4.el10`
      and `ocaml-dune 3.16.0-4.el10` in **crb**, which looks like clearance — but stanc3
      2.39.0's `stanc.opam` pins `ocaml {= "4.14.1"}` and `scripts/install_build_deps.sh` pins
      `core.v0.16.0 menhir.20230608 ppx_deriving.5.2.1 fmt.0.11.0 yojson.2.1.0 cmdliner.2.1.0`,
      and `dnf list --available` finds **no** `opam`, `ocaml-menhir*`, `ocaml-core*`,
      `ocaml-ppx*`, `ocaml-yojson*`, `ocaml-fmt*` or `ocaml-cmdliner*` for riscv64, and no
      EPEL 10 riscv64 to reach for. Upstream's own recipe is
      `apk add opam && opam switch create 4.14.1 && bash install_build_deps.sh`, i.e. compile
      the pinned compiler and ~40 opam packages (the Jane Street `core` ppx graph) from source
      — a second, never-exercised-on-riscv64 toolchain bootstrap for *another project's*
      release artifact, which we would then ship as our own binary. That is 341's "novel
      cross-ecosystem bootstrap", and the exact-version pin is what stops the distro packages
      from short-circuiting it. (OCaml itself is fine: 4.14.1's `configure.ac` maps
      `riscv64-*-linux*` to `arch=riscv; model=riscv64` with `natdynlink=true`, and
      `asmcomp/riscv/` exists — the language is not the blocker, the pinned dependency graph's
      zero riscv64 history is.)
    - **Confirm the rest of the build really is portable, so the report names one wall and not
      a vague "big C++ port".** Everything in httpstan except `stanc` checks out on riscv64:
      Stan Math 5.3.0's `make/compiler_flags` branches only on `__aarch64__` and Windows (no
      `-march`/`-msse`/`-mavx` anywhere), its vendored classic TBB 2020.3 takes the portable
      `machine/gcc_generic.h` atomics path at `tbb_machine.h`'s `__linux__` branch *before* any
      architecture `#elif` (341's point) and its `build/linux.inc` falls through to
      `arch := $(uname_m)` with `def_prefix = lin64` via `findstring 64`, and `libtbb.so.2`
      plus the sundials 6.1.1 static libs build clean under
      `docker run --platform linux/riscv64 quay.io/pypa/manylinux_2_39_riscv64` with GCC
      14.3.1. The wheel's compiled payload is not even an extension module: poetry's `build.py`
      adds `Extension("httpstan.empty", …)` purely to force a platform tag (gotcha 383's fake
      `Extension`, and `httpstan/empty.*.so` is not in poetry's `include` list, so it is absent
      from the shipped wheel) — the real content is a 44 MB `httpstan/stan_services.o`, four
      `libsundials_*.a`, a vendored `libtbb.so`, ~13 900 headers and the `stanc` executable
      (`e_machine` 62 = `EM_X86_64` in the published wheels). **A `.so`-presence check passes
      here for the wrong reason** — the only `.so` is the vendored TBB — so don't let it stand
      in for "the compiled part builds".
    - **Do not try to *demonstrate* the mismatch inside an emulated container — that test
      gives a false green.** Extracting the published wheel's `stanc` and running it in
      `docker run --platform linux/riscv64 quay.io/pypa/manylinux_2_39_riscv64` prints
      `stanc3 v2.39.0 (Unix)` and `exit=0`, even though `uname -m` says `riscv64` and
      `readelf -h /bin/bash` says `Machine: RISC-V` in the same shell. The container really is
      riscv64; the *host* kernel is x86_64, and `binfmt_misc` only redirects **foreign** ELFs
      to `qemu-riscv64` — an x86_64 ELF is simply executed natively, so this is the one setup
      where an x86_64-only bundled binary silently works. Prove the mismatch from the bytes
      (`readelf -h` → `Machine: Advanced Micro Devices X86-64`, or `e_machine` 62 = `EM_X86_64`
      read straight out of the wheel member) and treat any local QEMU rehearsal of a wheel that
      *executes a bundled binary* as unable to catch that class of failure at all; it only
      shows up on a real riscv64 runner as `Exec format error`.
    - **Needing a host C++ compiler at *install-and-use* time is not a riscv64 gap.**
      httpstan compiles every model on the user's machine via `setuptools.Extension`, so a
      toolchain must exist at runtime — but that is equally true of upstream's own x86_64 and
      macOS wheels, so it is a property of the package, not something a riscv64 port has to
      solve. Separate "this package needs a compiler at runtime" from "this package needs a
      *binary we cannot produce* at runtime"; only the second blocks.

470. **A `.queue.yml` note reading `abi: 0` is a wheel *build tag*, not an ABI tag — and for a
    co-installed-prefix ecosystem one released wheel's `readelf -d` enumerates the whole chain
    of ports that must land first (the pin/pinocchio case).** Two independent traps, both cheap
    to clear before reading a single build script.
    - **Check the real filename before believing the note's shorthand.** pin 4.1.0's wheels are
      `pin-4.1.0-0-cp312-cp312-manylinux_2_28_x86_64.whl`: the `0` between version and
      interpreter tag is PEP 427's optional *build number* (`Build: 0` in `dist-info/WHEEL`,
      stamped by `Generator: cmeel`), which a queue scanner reading the tag triple positionally
      reports as `abi: 0`. It means neither "pure `py3-none`" (gotchas 24/27's skip) nor abi3
      (gotcha 469's floor-interpreter handling) — these are ordinary per-interpreter compiled
      wheels, ten of them, cp310–cp314. Every `cmake-wheel`/cmeel distribution shows `abi: 0`
      for this reason, so the note is accurate about the field it read and worthless as a
      signal; the same goes for the sibling `py3-none-manylinux_2_28_*` cmeel wheels, which are
      real compiled C++ with no Python extension (gotcha 35's shape, not gotcha 27's).
    - **`readelf -d` on one released wheel for *any* arch is the fastest complete dependency
      map here.** cmeel wheels unpack into `cmeel.prefix/` and link with
      `RUNPATH $ORIGIN/../../../../lib` into a prefix directory **shared** with their siblings:
      nothing is bundled, so every `NEEDED` line names another distribution rather than a
      vendored copy. pin's one 47 MB `pinocchio_pywrap_default.cpython-312-*.so` needs
      `libpinocchio_{default,parsers,collision}.so` (libpinocchio), `libcoal.so` (libcoal),
      `libeigenpy.so` (eigenpy), `liburdfdom_{model,world,sensor}.so.6` (cmeel-urdfdom),
      `libconsole_bridge.so.1.0` (cmeel-console-bridge), `liboctomap/liboctomath.so.1.10`
      (cmeel-octomap) and `libboost_*.so.1.90.0` (cmeel-boost). One `readelf` gives the
      sequencing that walking build scripts would not.
    - **Measure the closure and hand over the tiers, not just "blocked".** Walking
      `info.requires_dist` (extras dropped) transitively across PyPI and
      `https://pypi.riseproject.dev/simple/<dep>/` puts 11 unported distributions under pin —
      leaves first: cmeel-zlib, cmeel-tinyxml2, cmeel-console-bridge, cmeel-octomap,
      cmeel-qhull → cmeel-assimp, cmeel-urdfdom, eigenpy → libcoal → coal, libpinocchio → pin
      — against four already satisfied (`cmeel` and `example-robot-data` are `py3-none-any`
      straight off public PyPI; `cmeel-boost` and `numpy` are on our registry). Gotcha 338
      parked eigenpy from this same ecosystem one layer down, and the lesson of cmeel-boost
      landing since is that clearing one leaf unblocks *its* consumer only: read the closure
      per package rather than assuming the family moved.
    - **The `[build-system] requires` is the same unported set, so there is no build to
      attempt** — pin pins `cmeel-urdfdom[build]`, `coal[build]` and `libpinocchio == 4.1.0` as
      build inputs (they supply headers *and* the link targets), which is gotcha 249 inverted:
      here the build-time list adds no blocker the runtime list didn't already have.
    - **Settle portability anyway, and record *sequenced* rather than *infeasible*.** pin's
      `[tool.cmeel] configure-args` is only
      `-DBUILD_PYTHON_INTERFACE=ON -DBUILD_STANDALONE_PYTHON_INTERFACE=ON`
      `-DBUILD_WITH_COLLISION_SUPPORT=ON -DBUILD_WITH_LIBPYTHON=OFF`, i.e. the default build
      excludes the CppAD/CasADi autodiff backends; the sdist contains no CUDA/nvcc reference
      and no `-march`/`-mavx`/SSE string (Eigen's vectorization degrades to scalar on its own).
      A clean portability read must not then tempt a monolithic build that compiles the
      siblings inside `build-pin.yml`: it would rewrite cmeel's shared-prefix contract, publish
      none of the siblings (they are outside the port's commit scope), and still ship a wheel
      with three `Requires-Dist` entries nothing on the index can satisfy.
    - **Carry the interpreter ceiling down the chain.** Nothing above cmeel-boost can exceed
      cmeel-boost's own riscv64 coverage — cp312/313/314 today — even though upstream pin ships
      cp310–cp314. Decide that once, at the bottom of the chain, not per package.

471. **A GPU package's architecture axis is bounded by its *accelerator vendor's* toolkit axis
    — and a forced-platform env var whose accepted values name three GPU vendors is not gotcha
    459's rescue (the torch-memory-saver case).** The tempting read of this one is "upstream
    just added a second architecture, so the arch axis is open and riscv64 is the same patch":
    0.0.9.post1 is the release that added `manylinux2014_aarch64` beside the long-standing
    `manylinux2014_x86_64` wheel (0.0.9 and every earlier release are x86_64-only), and 0.0.10
    keeps exactly that pair. Read the *body* of the arch branch, not the wheel list.
    - **The non-x86 branch names the vendor, not the architecture.** `scripts/build.sh`'s entire
      `ARCH` switch is `aarch64 → LIBCUDA_ARCH="sbsa"; BUILDER_NAME="pytorch/manylinuxaarch64-builder"`,
      else `LIBCUDA_ARCH=${ARCH}` with `pytorch/manylinux2_28-builder`, and the image is always
      `${BUILDER_NAME}:cuda${CUDA_VERSION}`; `scripts/build_in_docker.sh` then symlinks
      `/usr/local/cuda-${CUDA_VERSION}/targets/${LIBCUDA_ARCH}-linux/lib/stubs/libcuda.so`.
      aarch64 was cheap *because* NVIDIA ships an aarch64 (sbsa) CUDA toolkit and PyTorch
      publishes a CUDA aarch64 builder image — neither exists for riscv64
      (`redistrib_13.0.0/13.2.0/13.4.2.json` still list only `linux-x86_64`, `linux-sbsa`,
      `linux-all`, `windows-*`). Sharpens gotcha 418: a non-x86 precedent transfers only as far
      as the vendor toolkit's own arch list.
    - **Read a forced-platform env var's accepted *values*, not just its existence.** gotcha 459
      rescued vllm because `VLLM_TARGET_DEVICE=cpu` names a device *class*. Here
      `_detect_platform()` probes `hipcc`, then `nvcc`, then `icpx`, and defaults to `"cuda"`;
      the released 0.0.9.post1 has no override at all and current `master` adds one
      (`TMS_PLATFORM`) whose only meaningful values are `hip`, `cuda` and `xpu`, with
      `csrc/macro.h` ending `#else #error "USE_PLATFORM is not set"` — repeated at every branch
      in `core.h` and `core.cpp`. Three *GPU vendors* with no CPU member is a vendor selector —
      and the override arrived together with the XPU backend, i.e. with a *third vendor* rather
      than with a CPU fallback. All three arms are shut anyway: ROCm publishes
      `binary-amd64` only (`repo.radeon.com/rocm/apt/latest/dists/noble/main`) and Intel's
      oneAPI/XPU stack has no riscv64 build either.
    - **Two commands prove the build-time CUDA requirement** (gotcha 284's headers side, on a
      host with no CUDA): `python3 setup.py --version` → `RuntimeError: TMS_CUDA_MAJOR env var
      must be set for CUDA builds`, then `TMS_CUDA_MAJOR=12 pip wheel . --no-deps
      --no-build-isolation` → `csrc/macro.h:46:10: fatal error: cuda_runtime_api.h: No such file
      or directory`. `setup.py` also sets `libraries=['cuda','cudart']` against
      `$CUDA_HOME/lib64{,/stubs}`.
    - **"It hooks allocations with `LD_PRELOAD`" is not the same as hooking a generic
      allocator.** The preload build exports `cudaMalloc`/`cudaFree` (`csrc/entrypoint.cpp`
      under `TMS_HOOK_MODE_PRELOAD`) and forwards through `dlsym(RTLD_NEXT, "cudaMalloc")`;
      underneath, the pause/resume mechanism *is* the CUDA virtual-memory-management driver API
      — `readelf -Ws` on the released `.so` shows `cuMemCreate`, `cuMemMap`, `cuMemUnmap`,
      `cuMemRelease`, `cuMemSetAccess`, `cuMemAddressReserve` undefined, with `DT_NEEDED
      libcuda.so.1` plus `libcudart.so.{12,13}`. Unmapping physical pages while keeping a
      virtual address reserved has no host-RAM equivalent in that API, so "the same idea for
      CPU memory" would be a different package, not a reduced build of this one.
    - **And the pure-Python gate closes even a hypothetical stub** (gotcha 452's shape):
      `utils.py::_detect_cuda_major()` reads `torch.version.cuda`, falls back to
      `ctypes.CDLL("libcudart.so.{13,12}")` and otherwise raises `RuntimeError:
      torch_memory_saver: could not detect CUDA runtime` — reproduced by importing that one
      module on a GPU-less host. A CPU-only riscv64 torch has `torch.version.cuda is None`, so
      the path that picks which `<stem>_cu{12,13}.abi3.so` to load can never resolve.

475. **When a package vendors an entire database engine, the architecture review and the
    affordability review are two different reviews — and the first one can come out green
    while the second parks it (the chdb-core/ClickHouse case).** chdb-core is not a binding
    over a library: the repo *is* a ClickHouse fork (`src/` 4,559 `.cpp`, `base/`, `programs/`,
    a 285-entry `contrib/` of which `.github/scripts/update-submodules.sh` documents 139 as
    submodules to clone), and the wheel's payload is `chdb/_chdb.abi3.so`, i.e. the whole
    engine linked as one Python module. Everything a normal triage looks for says *go*:
    `cmake/arch.cmake` sets `ARCH_RISCV64`, `cmake/linux/toolchain-riscv64.cmake` exists,
    `ci/defs/job_configs.py` carries a `BuildTypes.RISCV64` job producing `CH_RISCV64`,
    `contrib/jemalloc-cmake/include_linux_riscv64` and `contrib/llvm-project-cmake`'s
    `ARCH_RISCV64` branches are already written, `contrib/corrosion-cmake` maps
    `riscv64gc-unknown-linux-gnu`, the vendored wasmtime is 45.0.1/cranelift 0.132 (riscv64
    backend long since upstream), and `cmake/tools.cmake`'s `CLANG_MINIMUM_VERSION 21` — with
    GCC rejected outright — is satisfied off the shelf by the image's own 21.1.8 clang/lld
    (gotcha 454). No vendored blob, no closed dep, Apache-2.0, a real riscv64 gap (four wheels:
    macOS x86_64/arm64, manylinux_2_17 x86_64/aarch64, all `cp39-abi3`). It is still a park,
    on runner-hours alone.
    - **Price the build in ninja edges times this fleet's *measured* per-edge cost, not in
      adjectives.** Two anchors already exist in this repo's own history, both on the same
      4-core T-Head runners: `build-vtk.yml`'s comment records 5,095 of 12,192 edges in 7.5 h
      (≈21 core-s/edge) and the stpyv8 V8 build reached 1,146 of 2,117 targets in 9 h 17 m
      (≈117 core-s/edge). ClickHouse TUs belong to the second class, not the first — upstream's
      own heavy-build guard (`cmake/heavy_build_check_scripts/prlimit_generic.sh`, wired by
      `ENABLE_CHECK_HEAVY_BUILDS` in its riscv64 CI job) allows **1000 CPU-seconds and 5 GB per
      translation unit** on a fast x86/ARM builder. ~4,900 in-tree TUs at V8-class cost is
      already ~160 core-hours ≈ 40 h wall at 4 cores, *before* contrib's own thousands (the
      embedded-compiler LLVM, arrow/parquet, aws-sdk, azure, icu, rocksdb, protobuf,
      librdkafka, mongo, libpqxx) and before the Rust workspace (270 crates + delta-kernel-rs;
      deltalake's 840-crate graph took 8.1 h here). Against a 48 h ceiling — the largest
      `timeout-minutes` this repo has ever granted (`build-vtk.yml`,
      `build-nodejs-wheel-binaries.yml`, `build-cadquery-ocp-novtk.yml`) and ~5× the ~10 h
      libclang record — that is at or past the wall on the first pass, with no margin for the
      iterations a first-ever port always needs.
    - **Check whether the build runs *twice*, and whether the flag that changes between the two
      passes lands in a generated header.** `chdb/build.sh` configures and builds the whole tree
      with `-DENABLE_PYTHON=0` (relinking the `clickhouse` link line into `libchdb.so`), then
      reconfigures with `-DENABLE_PYTHON=1` and builds again (relinking into
      `_chdb.abi3.so`). That second pass is not incremental: `ENABLE_PYTHON` sets `USE_PYTHON`
      in `src/configure_config.cmake`, which is `#cmakedefine01`'d into `src/Common/config.h.in`
      — a header nearly every TU includes — so ninja rebuilds essentially all of `src/`. Two
      near-full passes is the single biggest multiplier in the estimate and it is invisible in
      the CMake flags; it is only in the build script. (Skipping the standalone `libchdb.so`,
      which the wheel does not ship, is the one real lever — `CHDB_LITE=1` already takes it —
      and it still leaves one full pass over the engine.)
    - **An upstream arch port that lives inside `if (CMAKE_CROSSCOMPILING)` gives a *native*
      build none of its accommodations.** Every riscv64 concession in `cmake/target.cmake`
      (`GLIBC_COMPATIBILITY OFF`, `ENABLE_PARQUET OFF`, `ENABLE_RUST OFF` — "it might be ok, but
      we need to update 'sysroot'" — `ENABLE_MYSQL/HDFS/GRPC/LDAP OFF`, `OPENSSL_NO_ASM ON`)
      sits under that guard, and upstream's riscv64 job is a cross-compile from ARM runners
      against `contrib/sysroot/linux-riscv64`. This repo builds natively in the manylinux
      container, where `CMAKE_CROSSCOMPILING` is 0, so the configuration you actually get is the
      full feature set — precisely the libraries upstream has never compiled for riscv64 — and
      the riscv64 CI evidence covers none of it. `chdb/build.sh` then forces several *further*
      ON: `-DENABLE_VECTORSCAN=1`, `-DENABLE_USEARCH=1 -DENABLE_SIMSIMD=1` (all three contrib
      CMakes carry AMD64/AARCH64 source lists and nothing else) and `-DGLIBC_COMPATIBILITY=1`
      (whose `base/glibc-compatibility/CMakeLists.txt` is a bare
      `message(FATAL_ERROR "glibc_compatibility can only be used on x86_64 or aarch64")`). Each
      is a one-line override, and each override is a behaviour change to justify — the point is
      that "upstream builds riscv64 in CI" bought none of them.
    - **Say so when the host cannot even *configure*, because that is what makes the first CI
      run a multi-day unvalidated shot.** Gotcha 9's local rehearsal needs a clang ≥ 21 (the host
      had 18.1.3), ~10 GB for the 139-submodule checkout (8 GB free) and tens of GB for a build
      tree. So there is no cheap way to learn the real edge count or to catch a configure error
      before burning a slot, and each discovery costs another one. Combined with a shared pool
      that already had 8 runs in flight — two of them V8 builds measured in days — parking is the
      proportionate call, the same shape as the ortools and tensorflow entries: no hard
      architectural blocker, just a cost the pool cannot carry.

476. **A CMake project whose CI submits to CDash has already published what its own build
    costs, per platform — read the dashboard instead of estimating the size of the C++ world
    (the simpleitk/ITK case; see `build-simpleitk.yml`).** SimpleITK presents as the most
    expensive shape there is: a SWIG wrapper whose CMake SuperBuild compiles Lua, PCRE2, SWIG
    4.4.1, *all* of ITK 5.4.7 and a static SimpleITK core from scratch, with upstream's own
    docs asking for "4 GB of RAM plus 2 GB per thread" and 10-16 GB of disk — the family
    (paddlepaddle, chdb, tensorstore) this repo parks. Its `CTestConfig.cmake` names the
    dashboard, and one request prices it: `curl -s
    "https://open.cdash.org/api/v1/index.php?project=SimpleITK&date=<YYYY-MM-DD>"` returns, per
    submission, the site, the build name and `configure`/`compilation`/`test` seconds. At the
    v2.5.6 tag the full SuperBuild is **1h03m-1h50m of compile on 4-core GitHub-hosted Linux**
    (2h30m-3h30m on 4-core macOS) — a quarter of VTK's tree, not a multiple of it.
    - **The per-language rows are the ones that decide the workflow's shape.** Beside each
      full build sit `build-py311`, `build-py314t`, `build-java` rows at **2-8m** of compile
      each, because those configure only `Wrapping/<lang>` against the already-built core. That
      is gotcha 456's question — does the loop amortize anything? — answered from upstream's
      own dashboard before writing any YAML: here the core dominates and the interpreter legs
      are nearly free, so a per-interpreter matrix costs ~2x the core, not 2x the whole port.
    - **Read the build group, not just the number.** A `Nightly`/`Continuous` row at 21m
      compile is an incremental rebuild of a warm tree; price off the `Package`/`Experimental`
      rows submitted at the release tag, whose names carry the tag (`…-30486816103-v2.5.6-`).
    - **A hosted-runner cap is a second, independent upper bound, and a published wheel is
      proof it was met.** SimpleITK's Linux wheels come out of `Package.yml`'s
      `package-docker` job on `ubuntu-latest` / `ubuntu-22.04-arm` — 4 vCPU, GitHub's 6h
      per-job ceiling — which builds the core once *plus* Java *plus* four Python wrappings
      *plus* their ctest suites. The `manylinux2014_aarch64` wheel on PyPI says that job
      finishes, so nothing in the port can be a 10h build on comparable cores.
    - **Census the translation units against a port this repo already did.** 2409 compiled
      sources in ITK, 1990 of them cheap vendored C (HDF5, GDCM, OpenJPEG, TIFF, PNG, zlib-ng,
      MINC, NIFTI, MetaIO, VXL), plus 81 hand-written SimpleITK sources and one generated
      filter `.cxx` per `Code/BasicFilters/json/*.json` (297) — ~2,800 edges against VTK's
      12,192 and chdb's ~4,900 V8-class ones (gotcha 475), with abi3 halving the legs on top.
    - **The lever generalizes**: every Kitware-adjacent project (ITK, VTK, ParaView, GDCM,
      CMake itself) submits to `open.cdash.org`, `&date=` walks history, and the same JSON
      carries the test counts, so the "how long, and how much of it is per-interpreter"
      question is answerable for them without a single CI minute of ours.

478. **Gotcha 343's parting advice — "revisit once `<dep>` has a riscv64 build" — is wrong
    for an *archived* project: an upstream that is read-only can never widen its dependency
    pin, so the port is blocked on a **historical** version of that dependency, not on the
    version anyone would ever port (the tensorflow-addons case).** tensorflow-addons is
    structurally the same wall as tensorflow-text and tensorflow-io-gcs-filesystem — a
    TensorFlow custom-ops package whose Bazel build links every kernel `.so` against the
    `libtensorflow_framework.so` taken out of a *pip-installed* `tensorflow` wheel. The
    mechanism is a third variant to grep for: `configure.py` does a module-level `import
    tensorflow`, reads `tf.sysconfig.get_compile_flags()`/`get_link_flags()`, and writes
    `TF_HEADER_DIR`/`TF_SHARED_LIBRARY_DIR`/`TF_SHARED_LIBRARY_NAME` as
    `build --action_env` lines into a generated `.bazelrc`; `WORKSPACE`'s `tf_configure`
    (`build_deps/tf_dependency/tf_configure.bzl`) `cp -f`s that directory's real `.so` into
    `@local_config_tf`, whose `BUILD.tpl` wraps it as
    `cc_library(name = "libtensorflow_framework", srcs = ["%{TF_SHARED_LIBRARY_NAME}"])`,
    and `custom_op_library()` in `tensorflow_addons/tensorflow_addons.bzl` appends that
    target to the `deps` of *every* op library unconditionally. `readelf -d` on the shipped
    x86_64 wheel confirms it end to end: all 8 custom-op `.so`s carry
    `NEEDED libtensorflow_framework.so.2`. So far, gotcha 343.
    - **What changes the verdict from "blocked, revisit later" to "permanently blocked" is
      the archive status plus the pin window.** `github.com/tensorflow/addons` is
      `"archived": true` (one `/repos/<owner>/<repo>` read), 0.23.0 is the last of 35
      releases (Nov 2023), and `tensorflow_addons/version.py` pins
      `INCLUSIVE_MIN_TF_VERSION = "2.13.0"` / `EXCLUSIVE_MAX_TF_VERSION = "2.16.0"`, with
      `resource_loader.py` narrowing the *ABI* window for the compiled ops to
      `[2.15.0, 2.16.0)` and `WORKSPACE` pinning `org_tensorflow` to the 2.15.0 tarball.
      A read-only repo will never raise those numbers, so this port does not need "a riscv64
      tensorflow", it needs **a riscv64 tensorflow 2.15** — a 2023 release. This repo's
      `tensorflow` entry is 2.21.0, six minors outside the window, so unparking it would not
      unblock this. **For an archived dependent, resolve the pin to a concrete version before
      writing "revisit once the dep lands"** — otherwise the note promises an unblocking that
      the named work cannot deliver.
    - **Intersect the pinned dependency window's own *interpreter* coverage with this
      repo's default matrix; an empty intersection settles the port on its own.** TF
      2.13.1/2.14.0/2.15.0 ship `cp38`-`cp311` wheels and nothing later, while this repo
      builds cp312/cp313/cp314/cp314t — zero overlap, so no matrix row could be valid even
      with a riscv64 TF 2.15 in hand. This is a cheap PyPI-JSON check (`{f['filename']}`
      tags for the pinned dep), and unlike gotcha 248's it needs no build attempt.
    - **A dependency available on another non-x86 arch, still unused by upstream, is
      evidence there is no recipe to narrow (goal 2).** TF itself publishes
      `manylinux_2_17_aarch64` wheels for 2.13-2.15, yet tensorflow-addons shipped **zero**
      aarch64 Linux wheels across its entire 35-release history (macOS `arm64` only), and no
      sdist ever. Its `release.yml` builds `ubuntu-20.04` + `macos-12` only, via
      `tools/docker/build_wheel.Dockerfile` — `FROM tensorflow/build:2.15-python$PY_VERSION`
      with `TF_NEED_CUDA=1` and a hardcoded
      `--crosstool_top=@ubuntu20.04-gcc9_manylinux2014-cuda11.8-cudnn8.6-tensorrt8.4_config_cuda//crosstool:toolchain`,
      plus `install_bazelisk.sh` that hardcodes `bazelisk-linux-amd64`. There is no non-x86
      Linux path to mirror.
    - **CUDA is not the blocker in a TF custom-ops package** — don't stop there. Every
      `cuda_srcs` in `custom_op_library` sits behind `if_cuda`/`if_cuda_is_configured`, and
      `configure.py` only calls `configure_cuda()` when `TF_NEED_CUDA=1`, so the CPU-only
      build is a first-class upstream configuration. The wall is the CPU link against
      `libtensorflow_framework.so`, which CUDA-free builds need just as much.
    - **`configure.py`'s arch branches are a second, independent riscv64 gap worth
      recording even when the port is blocked upstream of them.** Its Linux branch writes
      `build --copt=-mavx` for everything that is not `ppc64le`/`arm`/`aarch64`
      (`is_linux_x86_64`, `is_linux_s390x`, `is_linux_ppc64le`, `is_linux_arm`,
      `is_linux_aarch64` — no riscv64 predicate exists), so riscv64 falls into the x86
      default and a riscv64 GCC rejects the flag. Same shape as gotcha 426's
      `release_cpu_linux`/`-mavx` finding in TF core: **an "is this arch excluded?" allowlist
      written as a negated x86-adjacent set silently mis-classifies riscv64.**
    - **`install_requires` can be clean while the import is not.** `setup.py` sets
      `install_requires` from `requirements.txt` (`typeguard>=2.7,<3.0.0`, `packaging`) and
      keeps `tensorflow` in `extras_require` only, so a wheel would *install* on riscv64 —
      but `tensorflow_addons/__init__.py` imports `ensure_tf_install`, which does
      `import tensorflow`, so there is nothing to smoke-test. Gotcha 343's tensorflow-text
      case fails the install; this one fails one line later, and both are untestable.
    - **`platform`-specific stub extensions explain a stray `.so` in the wheel**, not a
      packaging bug: `get_ext_modules()` returns `[Extension("_foo", ["stub.cc"])]` on Linux
      purely so `BinaryDistribution.has_ext_modules()` forces a platform wheel tag, which is
      why the released wheel carries a top-level `_foo.cpython-310-x86_64-linux-gnu.so`
      beside the 8 real op libraries.
    - **Also confirmed absent as an escape hatch**: Google's standalone libtensorflow
      C-library tarball has no riscv64 build at the pinned version either —
      `storage.googleapis.com/tensorflow/libtensorflow/libtensorflow-cpu-linux-riscv64-2.15.0.tar.gz`
      → 404 against `…-x86_64-2.15.0.tar.gz` → 206, and the newer
      `versions/2.16.1/libtensorflow-cpu-linux-{x86_64,riscv64}.tar.gz` pair is 206/404.
      Note the two URL layouts: the `versions/<ver>/` path only exists for newer releases, so
      re-test the legacy `libtensorflow/<name>-<ver>.tar.gz` form before reading a 404 as
      "no build" (at 2.15.0 the `versions/` path 404s for x86_64 too).
    - **Marked `blocked-on-dependency`, matching its two siblings** rather than `parked`:
      the scope is small (8 op libraries, a few thousand lines of C++), so the note has to
      say the blocker is a missing target-architecture ELF and a frozen pin, not build size.
      No worktree, branch, workflow or patch — the whole verdict came from the PyPI JSON, one
      GitHub repo-metadata read, `raw.githubusercontent.com` reads of `setup.py`,
      `configure.py`, `WORKSPACE`, `tf_configure.bzl`, `BUILD.tpl`, `tensorflow_addons.bzl`
      and `release.yml`, and `readelf -d` on the released x86_64 wheel.
480. **A non-NVIDIA accelerator vendor can hide its whole toolkit dependency behind `dlopen`, so
    the released wheel's `readelf -d` looks perfectly portable — and the vendor-agnostic build
    mode its CMake advertises is stamped by upstream's own `setup.py` as a *different
    distribution version*, which is what actually shuts the door (the memfabric-hybrid / Huawei
    Ascend case).** Gotcha 471 is the same shape for NVIDIA, but every tell it teaches is absent
    here: the project is fully open (Mulan PSL v2), there is no vendored blob, no `libcuda.so.1`
    equivalent in `DT_NEEDED`, and the CMake even offers a CPU backend. Ascend is Huawei's NPU
    line; CANN is its closed toolkit, and the family reaches five `.queue.yml` entries
    (memfabric-hybrid, memfabric-zbal, memcache-hybrid, triton-ascend, torch-npu).
    - **`readelf -d` is clean; the vendor lives in `strings`.** All five `.so` in the x86_64
      wheel need only `libstdc++`/`libm`/`libgcc_s`/`libc`/`librt`/`libpthread`/`libdl` plus each
      other. The CANN dependency appears only as `dlopen` names inside `libmf_hybm_core.so` —
      `libascendcl.so`, `libascend_hal.so`, `libhccl.so`, `libruntime.so`, `libtsdclient.so` —
      emitted by a `csrc/under_api/dl_hybrid_api.h` wrapper switched on `-DASCEND_NPU` /
      `-DNVIDIA_GPU` / `-DNO_XPU`. So for a dlopen-style vendor binding, run
      `strings -a <lib> | grep -oE 'lib[a-z_]+\.so[0-9.]*'` beside `readelf -d`, and read the
      pure-Python entry point as gotcha 452 says: `__init__.py` ends in `provision()`, which
      installs an AICPU kernel into CANN's `opp/vendors/cust/op_impl/aicpu` (silently skipped
      when `ASCEND_HOME_PATH` is unset, so the package *imports* on a CANN-less host and proves
      nothing).
    - **A three-valued backend selector is not automatically gotcha 459's rescue — check what
      the packaging does to the version string.** `cmake/config_xpu.cmake` really does accept
      `XPU_TYPE=NONE` (`-DNO_XPU`), with live `#if defined(NO_XPU)` code paths, so the backend
      selector alone reads like bitsandbytes (gotcha 411). But `setup.py` has
      `if xpu_type == "NONE": current_version += "+cpu"` (and `"+gpu"` for GPU), and PyPI's 76
      files across 14 releases are *all* plain-versioned manylinux aarch64/x86_64 NPU builds —
      no `+cpu` or `+gpu` local version has ever been published. Upstream's own packaging
      therefore declares the CPU build a different distribution version than the one queued, so
      "build it with the CPU flag" cannot produce `<pkg> <queued version>` at all. That is a
      sharper, packaging-level form of gotcha 452's "does upstream ship this flag?" test: when a
      build mode renames the artifact, the answer is in `setup.py`, not in the wheel list.
    - **Behind the CPU mode sits a second Huawei stack, not CANN.** The only host transport is
      hcom (`libhcom.so`, `FetchContent` of `atomgit.com/openeuler/ubs-comm` @
      `br_BeiMing_MF_Poc`), and its build is a two-arch switch, not an allowlist:
      `src/hcom/umq/CMakeLists.txt` sets `aarch64 → -march=armv8-a+crc -DUB_ARCH_ARM64` and
      **everything else → `-msse4.2 -DUB_ARCH_X86_64`**, so riscv64 fails on the first compiler
      flag (gotcha 478's negated-x86 allowlist, one step worse — here the x86 arm is the
      `else`). Its Bazel `copts.bzl` selects on `@platforms//cpu:x86_64` / `aarch64` with no
      default, hardware CRC is aarch64 `crc32cx` inline asm vs SSE4.2, `urpc_get_cpu_cycles` is
      `rdtsc`/`cntvct_el0`, the `NO_XPU` branches carry `URMA_EID_LENGTH` keys, and the repo rule
      wants Huawei UMDK urma headers from `/usr/include/ub/umdk/urma`. A "CPU-only" mode of an
      accelerator-vendor package is often still vendor-interconnect-only.
    - **The arch axis is one line of the README, and the toolkit layout confirms it.**
      `平台：aarch64/x86`, hardware `Atlas 800I/800T A2/A3`, `CANN 8.1.RC1及之后版本`, plus Ascend
      HDK driver/firmware. CANN's own layout is `${ASCEND_HOME_PATH}/aarch64-linux/{include,lib64}`
      and its AICPU cross-compiler is `toolkit/toolchain/hcc/bin/aarch64-target-linux-gnu-g++`,
      i.e. aarch64-only by construction; `grep -ri riscv` over the whole tree returns nothing.
    - **gitcode.com is an ordinary git host — triage from the tree, not from the org name.**
      `git clone --depth 1 --branch release/1.2 https://gitcode.com/Ascend/<repo>.git` and
      `git fetch --depth 1 origin tag v1.2.0` both work through the agent proxy, as does
      `git ls-remote https://atomgit.com/openeuler/ubs-comm.git`; add both to the artifact-index
      collection beside NVIDIA's redist manifests and conda `repodata.json`. A Chinese-vendor
      host being unfamiliar is not evidence, and the release branch head can be a version ahead
      of the queued release (`VERSION` said 1.2.1 on `release/1.2`), so check out the tag.

481. **A `[tool.poetry.build] script` makes poetry-core stamp a full `cpXY-cpXY-<platform>`
    tag whatever the script does — and compiling i18n catalogs is the commonest reason
    (the jsonschema2md case).** Gotcha 464 found a fabricated `cpXY-cpXY` tag behind
    setuptools' hardcoded `has_ext_modules()`; poetry-core has its own one-line trigger and
    it fires on projects that never touch a compiler: declaring a build script makes the
    distribution non-pure, full stop. jsonschema2md 1.7.0 publishes exactly one Linux wheel,
    `cp313-cp313-manylinux_2_39_x86_64`, `Root-Is-Purelib: false`, with eleven entries that
    are all `.py`, `.po` and `dist-info` — zero `.so`, no `PyInit_*`. Its `scripts/build.py`
    only runs babel's `CompileCatalog` over `jsonschema2md/locales/*`, turning `.po` into
    `.mo`; gettext catalogs are arch-independent data.
    - **The release history dates the fabricated tag, for free, before any download.**
      0.1.0 through 1.5.2 are all `py3-none-any`; the tag flips to `cp313-cp313-manylinux_…`
      at exactly 1.6.0, the release that added i18n (the `[tool.poetry.build]` stanza plus
      `babel` in `build-system.requires` — 1.5.2's `pyproject.toml` has neither).
      `ci_scripts/queue_triage.py <pkg>` prints that per-version table in one read. A tag
      that changes shape in a release adding no C source is fabricated — read the change
      that introduced it, not the tag.
    - **The tag follows the publishing runner, not the content.** `pip wheel <sdist>
      --no-deps` on a 3.11 x86_64 host produces `…-cp311-cp311-linux_x86_64.whl` in about a
      second with no compiler: both halves of the tag are simply whatever built it. Upstream
      confirms it — `main.yaml` publishes with one `tag-publish` step on `ubuntu-24.04`, no
      cibuildwheel, no arch matrix and no macOS/Windows wheels at all, so *every*
      non-x86_64-Linux user already installs from the sdist today.
    - **Verdict is gotcha 27's watchdog clause, once gotcha 383's sdist check is actually
      run.** Every release ships an sdist; the three runtime deps and the whole
      poetry-core/poetry-dynamic-versioning/babel build closure resolve to riscv64 wheels
      (`ci_scripts/check_riscv64_deps.py`), so riscv64 `pip install` already works in
      seconds and a `manylinux_2_39_riscv64` wheel would carry byte-identical content —
      a packaging convenience, not a port. `parked`, no workflow or `docs/packages` entry.
    - **A build script that emits *data* can even leave the published wheel worse than the
      sdist.** The 1.7.0 wheel (poetry-core 2.1.3) ships the `.po` sources and **none** of
      the `.mo` files its own build script compiles, while a local build with poetry-core
      2.5.0 includes them — and the package's `get_locales()` globs
      `locales/*/LC_MESSAGES/messages.mo`, so the released x86_64 wheel silently has no
      translations where a from-sdist riscv64 install does. Check what the script's output
      actually contributes to the wheel before crediting the tag with meaning.
483. **Gotcha 125's "a dependency with no riscv64 wheel is only a blocker if it cannot build
    from its sdist" has to be *executed*, and the bar is `pip install <pkg>` on a clean
    riscv64 box — not a green CI job (the cmeel-urdfdom case).** Everything about the
    dependency looked like gotcha 125's preshed/cymem profile and one command disproved it.
    - **Read the closure per package: a member of a blocked family can be two leaves deep,
      not eleven.** cmeel-urdfdom 6.0.0 is one of the 11 unported distributions gotcha 470
      counted under pin, but its own closure is tiny: `[project] dependencies` and
      `[build-system] requires` both name only `cmeel-console-bridge` and `cmeel-tinyxml2`
      (plus `cmeel` and `cmeel-urdfdom-headers`, `py3-none-any` off public PyPI), and
      `readelf -d` on the released aarch64 wheel confirms it — `liburdfdom_{model,world,
      sensor}.so.6` NEED `libconsole_bridge.so.1.0` and `libtinyxml2.so.11` with
      `RUNPATH $ORIGIN`, nothing bundled. Triage the member, not the family.
    - **Both siblings have gotcha 125's exact profile — and one of them still fails.** Each
      sdist vendors its upstream source (no download) and declares `requires =
      ["cmeel[build]"]` alone, i.e. seconds of C++ with no external toolchain question. Run
      it anyway: `pip wheel <sibling>.tar.gz --no-deps` builds cmeel-tinyxml2 11.0.0 clean,
      and **fails** on cmeel-console-bridge 1.0.2.3 with "Compatibility with CMake < 3.5 has
      been removed from CMake" — console_bridge 1.0.2's `cmake_minimum_required(VERSION
      3.0.2)` against the CMake 4 that `cmeel[build]` resolves (`cmake` 4.4.3 has riscv64
      wheels on public PyPI) and that the manylinux images put first on `PATH` anyway
      (gotchas 207/257/358). A package can be simultaneously trivial to compile and
      unbuildable from its published sdist.
    - **An env-var workaround in `CIBW_ENVIRONMENT` is not a rescue, because it does not ship
      with the wheel.** `CMAKE_POLICY_VERSION_MINIMUM=3.5` does make the whole chain build —
      verified end to end on an x86 host, `PIP_NO_BINARY=cmeel-console-bridge,cmeel-tinyxml2
      pip wheel cmeel_urdfdom-6.0.0.tar.gz --no-deps` produces
      `cmeel_urdfdom-6.0.0-0-py3-none-manylinux_2_39_x86_64.whl` in about a minute — so CI
      *could* be made green. The user who then runs `pip install cmeel-urdfdom` on riscv64
      gets the same configure error, because the missing sibling is still resolved from
      sdist on their machine. Publishing that wheel would put an entry on the index that the
      index cannot install (structural goal 1), so the port is sequenced behind the sibling's
      own port — which is where the fix belongs, the sibling being outside this port's commit
      scope in any case.
    - **The one-line test.** For a shared-prefix family, ask "does `pip install <pkg>` succeed
      on riscv64 with only public PyPI plus our index, no extra environment?", and answer it
      by actually building each unported dependency's sdist. "Can I get CI green?" is the
      wrong question and has a more generous answer.

484. **A large C++ project with its own architecture abstraction layer concentrates the whole
    port into a handful of `#error` gates in that one directory — and the build config the
    *wheel* uses decides how many of them you ever reach (the usd-core/OpenUSD case; see
    `build-usd-core.yml`).** OpenUSD is ~1330 translation units for the non-imaging build, and
    a first look is discouraging: `grep -rn '#error' pxr/` returns 40+ hits. Nearly all are
    noise. Separate them on what they switch on, because only one class blocks a port:
    - **CPU-gated vs OS-gated is the whole triage.** `pxr/base/arch/{systemInfo,fileSystem,
      assumptions}.cpp` end in `#error Unknown system architecture` too, but each is selecting
      on `ARCH_OS_LINUX`/`ARCH_OS_DARWIN`/`ARCH_OS_WINDOWS` and is satisfied on any Linux. The
      three that actually fire on riscv64 all select on the CPU: `arch/defines.h` (`#error
      "Unsupported architecture.  x86_64 or ARM64 required."`, which kills *every* TU before
      anything else compiles), `arch/math.h` (a CPU gate around portable IEEE-754 bit
      twiddling), and `nonLockingLinux__execve()` in `arch/stackTrace.cpp` (hand-written
      syscall asm for aarch64 and x86_64). One patch covers all three; nothing else in the
      tree needed touching.
    - **Grep `ARCH_CPU_`/the project's own CPU macro, not just `#error`** — a gate can compile
      to a silently wrong branch instead of failing. Here exactly one such site existed outside
      `arch/` (`pxr/exec/vdf/executorDataVector.cpp`), and it is excluded because upstream's
      own wheel build passes `-DPXR_BUILD_EXEC=OFF`. **Read the wheel's build flags before
      auditing the tree**: imaging, MaterialX, tutorials, examples, tools and exec are all off,
      which removes ~1700 of the 3050 TUs and every OpenGL/Vulkan/X11 `find_package` along
      with them.
    - **The arch layer is also where the *absence* of a problem gets confirmed.** timing.h
      reaches `rdtsc` only behind `PXR_ARCH_PREFER_TSC_TIMING` and otherwise uses
      `std::chrono::steady_clock`; `ARCH_SPIN_PAUSE()` has a no-op `#else`; the vendored
      double-conversion already lists `__riscv`; `gf/nc/nanocolor.c` gates SIMD on
      `__SSE2__`/`__ARM_NEON` with a scalar path (*not* the gotcha-442 shape). Checking those
      four costs minutes and is what separates "needs a 20-line patch" from "park it".
    - **A cache-line warning is not a failure.** `Arch_ObtainCacheLineSize()` is
      `sysconf(_SC_LEVEL1_DCACHE_LINESIZE)`, which the riscv64 runners do not answer with 64,
      so every `import pxr` prints `ArchWarn: ARCH_CACHE_LINE_SIZE !=
      Arch_ObtainCacheLineSize()`. It is `ARCH_WARNING`, not `ARCH_ERROR`; the endianness check
      beside it is the one that would abort, and riscv64 is little-endian. Leave upstream's own
      diagnostic alone rather than spending a multi-hour rebuild to silence it.

492. **A declared dependency the build never actually links against still blocks the port —
    pip enforces the *metadata*, not the linkage (the cmeel-assimp/cmeel-zlib case).** Gotcha
    483 sequenced cmeel-urdfdom behind two siblings whose `.so` files it genuinely NEEDs.
    cmeel-assimp 6.0.5 looks like the same shape and is not: `pyproject.toml` names
    `cmeel-zlib` in both `[build-system] requires` and `[project] dependencies`, yet nothing
    in the built wheel depends on it.
    - **Two cheap artefacts settle "nominal or real", and they disagree with the metadata.**
      The package's `cmeel.patch` replaces `TARGET_LINK_LIBRARIES(assimp ${ZLIB_LIBRARIES} …)`
      with a bare `-lz`, so `FIND_PACKAGE(ZLIB)` finding the *image's* zlib is enough: the
      installed `lib/pkgconfig/assimp.pc` in a local rehearsal records
      `Libs.private: … /usr/lib/x86_64-linux-gnu/libz.so` (the host's, not the dependency's),
      and `readelf -d` on both the released and the locally built `libassimp.so.6.0.5` shows
      `NEEDED libz.so.1` with `RUNPATH $ORIGIN` while cmeel-zlib ships its copy in
      `cmeel.prefix/lib64` — *off* that RUNPATH. So `libz.so.1` resolves from the system at
      run time under the manylinux allowlist, and the dependency is a build-time formality.
      Contrast gotcha 470's `readelf`, where every `NEEDED` line named a sibling distribution.
    - **Block anyway.** pip resolves `[build-system] requires` before the build and
      `Requires-Dist` at install, neither of which asks the linker anything. On the target arch
      the build env has no wheel for the dependency, and a published wheel would carry a
      `Requires-Dist` the index cannot satisfy binary-only, so gotcha 483's one-line test
      ("does the end user's `pip install` succeed?") still answers no — here worse than for
      cmeel-urdfdom, because the sibling's sdist is an `ExternalProject_Add` that *downloads*
      its upstream tarball, needing network **and** a toolchain on the user's machine.
    - **Do not "fix" it by editing the dependency out of `pyproject.toml`.** It is the one
      tempting shortcut once you know the dependency is nominal, and it fails goal 2 twice
      over: the wheel's metadata would no longer match the same distribution published for
      every other arch, and in a shared-prefix ecosystem the declaration *is* the contract its
      consumers resolve through. Sequence behind the sibling's own port instead — and say in
      the note that the dependency is nominal, so whoever returns knows the unblock is pure
      metadata and the recipe needs no `CIBW_BEFORE_BUILD` dance.
    - **Worth the five minutes even when the answer changes nothing**, because it tells the
      next agent whether a missing sibling means "the library will not load" or only "pip will
      refuse" — and only the first of those can still bite after the sibling lands.

503. **Triage a framework's dependency closure by each node's *own published artifacts*, not
    by who publishes it — and count exact-pin *version* gaps as blockers (the angr case).**
    angr 9.3.3 sits on a stack of same-org siblings (archinfo, pyvex, cle, claripy, ailment)
    plus third-party engines (capstone, unicorn, keystone), and every intuition about which
    layer blocks was inverted by one walk of `info.requires_dist` plus the released filenames.
    - **The siblings that look like the native core are pure Python; the leaves block.**
      `archinfo`, `claripy`, `cle` and `angr-data` all publish exactly two files, a
      `py3-none-any` wheel and an sdist — they install on riscv64 as-is and need no port at
      all. The blockers are `pyvex` (VEX/libvex C), `pypcode` (Ghidra SLEIGH C++ via
      nanobind+cmake), `pydemumble` (C++ via scikit-build-core+nanobind), `pyxdia` and
      `uefi-firmware` (C extension), reached partly *through* the pure-Python siblings —
      `cle`'s own `Requires-Dist` is what drags in `pyxdia` and `uefi-firmware`. Classify
      every node by the wheels it actually ships; family membership predicts nothing.
    - **The queue's `abi:` note can be right about the top-level package and still not be the
      reason it is blocked.** angr really is compiled — `cp312-abi3` from setuptools-rust
      (`angr.rustylib`, pyo3 `abi3-py312`) plus a make-built `native/unicornlib` — so there
      was nothing misattributed to correct; the port is blocked anyway, one layer down.
    - **An exact `==` pin turns a package we already publish into a blocker.** angr pins
      `lmdb==2.1.1` (registry has 2.3.0 and 1.7.x only) and `claripy` pins
      `z3-solver==4.13.0.0` (registry has 4.12.x/4.14.x/4.15.x/4.16.0.0; upstream PyPI ships
      riscv64 only from 5.0.0.0). `riscv64_resolve.py` says so in its `from versions: …`
      line — read that list rather than stopping at "we host this name" (gotcha 30's sharper
      form). This is the cheapest class of unblock: one `- version:` entry in the *other*
      package's `docs/packages/<pkg>.yaml`, so name the exact versions in the queue note.
    - **`--only-binary` resolvers false-positive on sdist-only pure Python.** `arpy` 1.1.1 and
      `mulpyplexer` 0.09 publish no wheel for *any* platform, so `riscv64_resolve.py` reports
      them unresolvable while they install identically from sdist on x86_64 and riscv64.
      Separate "no riscv64 wheel" from "no wheel at all" before a name enters a blocking list.
    - **An sdist with zero native sources can be the hardest blocker of the set.** `pyxdia`
      0.1.1's sdist is 21 pure-Python files, yet its wheels are `py3-none-<platform>`: a
      custom `build` sub-command *downloads* prebuilt binaries (`xdia.zip`, `xdialdr.tar.xz`)
      and, for any non-x86_64 Linux, a prebuilt `blink` x86-64 emulator to run them under.
      Its table covers `darwin-x86_64`/`darwin-arm64`/`linux-aarch64` and `assert`s otherwise,
      so riscv64 fails at *build* time (gotcha 35/183's blob class, arrived at from a file
      list that looked pure). Read the custom build command before calling an sdist portable.
    - **`[build-system] requires` can repeat the runtime blocker, which doubles it.** angr's
      `native/unicornlib/Makefile` links `-lpyvex` against `PYVEX_INCLUDE_PATH`/
      `PYVEX_LIB_PATH` taken from the *installed* pyvex distribution, so the missing wheel
      stops the build itself and not only the end user's install — gotcha 249 with the
      build-time dep being the same package as the runtime one. Check the build list for a
      second, build-only gap while you are there (`grpcio-tools~=1.80.0` here against 1.83.1
      on the registry) and record whether it is patchable, so the next agent knows which
      items are hard and which are a pin relaxation.

505. **A cmeel queue note's build number is not always `0`, and one listing *several*
    (`abi: 4,5`) means a single wheel version was packaged more than once — build the
    highest `.cN` tag (the cmeel-octomap case).** Gotcha 470 established that a cmeel note's
    `abi:` field is PEP 427's build number rather than an ABI tag; every cmeel package
    ported before this one happened to read `abi: 0`, which made the field look constant.
    - cmeel-octomap 1.10.0 publishes nine Linux wheels split across two build numbers,
      because `[tool.cmeel] build-number` was bumped 4 -> 5 and both packaging passes are
      still on PyPI under the same `1.10.0`. The scanner reports the set it saw, `4,5`,
      which reads like an ABI list and is not one. It still says nothing about the wheel
      shape — that is `has-sitelib` (gotcha 487), here `false`, one `py3-none` wheel.
    - **Tag, key and wheel agree, so checking one checks all three.**
      `git ls-remote --tags` shows `v1.10.0.c0 … v1.10.0.c5`; `pyproject.toml` at
      `v1.10.0.c5` reads `build-number = 5`; the released
      `cmeel_octomap-1.10.0-5-py3-none-*.whl` carries `Build: 5` in `dist-info/WHEEL`.
      Checking out the **highest** `.cN` is what reproduces the current release. The
      sibling ports' hardcoded `.c0` is simply their own highest, not a convention — never
      assume `.c0` and never guess the suffix, since the `.cN` series is per package and
      skips nothing.
    - The wheel *version* is untouched by any of this (`1.10.0`), so
      `docs/packages/<pkg>.yaml` still carries one plain `- version:` entry, and
      `_publish-wheel.yml` — which reads `Name`/`Version` out of `METADATA` — never sees
      the build tag at all.

506. **Gotcha 263's "closed wheel, open project inside" rescue is per *package*, not per vendor —
    before reusing it on another wheel from the same vendor, check that the version maps to an
    open tag and that the *largest* payload's `DT_NEEDED` list stays inside that open project
    (the intel-openmp case).** tbb (gotcha 263) is the standing precedent that an Intel-built,
    sdist-less, EULA-covered wheel can still be portable, because its `2023.1.0` was Apache-2.0
    oneTBB `v2023.1.0` rebuilt. With nine more Intel oneAPI distributions on the queue
    (`intel-cmplr-lib-{ur,rt}`, `intel-cmplr-lic-rt`, `intel-sycl-rt`, `intel-opencl-rt`,
    `dpcpp-cpp-rt`, `mkl`, `mkl-static`, `mkl-include`) that precedent is the expensive wrong
    turn to take by analogy. Two checks separate a repackaged open project from a compiler
    vendor's own output:
    - **A version that is a *release train* number, not a project tag, is the first tell.**
      intel-openmp's `2026.1.1` is a oneAPI compiler release; no `llvm-project` `openmp` tag
      carries it, unlike tbb's exact tag match. The payload's own banner says who built it:
      `strings -a libiomp5.so | grep '@(#)'` gives `build compiler: Intel(R) oneAPI DPC++/C++
      Compiler 2024.2.0`, `build time 2026-02-13`, i.e. Intel's closed toolchain on Intel's
      machine — gotcha 431's builder-path tell in banner form.
    - **`readelf -d` the biggest file in the wheel, not the eponymous one.** `libiomp5.so` — the
      part with an open ancestor — is 2.8 MB of the 141 MB unpacked (2%); `libomptarget.so` is
      131.8 MB (93%) and needs `libimf.so`, `libsvml.so`, `libirng.so`, `libintlc.so.5` (Intel's
      proprietary compiler runtimes, published only as x86_64 binaries through the equally
      x86_64-only `intel-cmplr-lib-rt`) plus `libur_loader.so.0` from the hard-pinned
      `Requires-Dist: intel-cmplr-lib-ur==2026.1.1`. SVML is an x86 SIMD vector-math library by
      construction, and none of the four has public source anywhere. So "build the open part"
      reproduces LLVM's `libomp` under a different name, not this distribution — and LLVM's
      openmp runtime *does* build on riscv64 (`openmp/runtime/cmake/LibompGetArchitecture.cmake`
      has a `__riscv && __riscv_xlen == 64` arm), which is exactly what makes the analogy
      tempting and wrong. riscv64 manylinux already ships GCC's `libgomp`; a renamed second
      OpenMP runtime is not the package anyone declared a dependency on.
    - **A wheel that is 100% `.data/data/` with an empty `top_level.txt` has no port surface at
      all.** intel-openmp ships zero Python modules — prebuilt `.so`/`.a`/`.o`/`.bc`, `omp.h`
      and a `pkgconfig` file under `.data/data/{lib,opt/compiler}`, no build system, `readelf
      -h` → `Advanced Micro Devices X86-64` throughout. Same "the binary *is* the source" shape
      as 453/465, reached without `strings`.
    - **Gotcha 465's inverted riscv tell repeats, one LLVM further out.** `strings -a
      libomptarget.so | grep -ci riscv` → 1106 (`R_RISCV_*`, `EF_RISCV_*`, `RISCVISAInfo.cpp`),
      all of it LLVM `BinaryFormat`/`TargetParser` tables linked in with the offload JIT: the
      only registered target is `LLVMInitializeNVPTX*`, and `libiomp5.so` itself has **0** riscv
      strings. The offload backends are Intel GPU ones (`level_zero`, OpenCL, `spir64`).
    - **The vendor's non-PyPI index settles the arch question in one line** (gotcha 453's second
      table): `apt.repos.intel.com/oneapi/dists/all/Release` says `Architectures: all amd64 i386
      i686`. Intel builds oneAPI for no non-x86 architecture at all — not even aarch64, which
      makes "they'd have to add riscv64" a two-step ask, not one.
    - **The EULA blocks the rehost independently, and its redistribution clause is the one to
      read.** The Intel End User License Agreement for Developer Tools §3.1 forbids
      distributing or publicly displaying the Materials, modifying/adapting/translating them and
      reverse engineering them; the lone grant (§2.1.D) covers "Redistributables" in Executable
      Code "only as part of Your Product" under a downstream licence that itself bars reverse
      engineering. Publishing the bytes on an index is not "as part of Your Product" — gotcha
      453/465's licence stop, in Intel's wording.
    - **Check who would even load it before writing the note.** intel-openmp's only PyPI consumer
      is `mkl` (itself an x86_64-only Intel blob), and every OpenMP/MKL consumer already ported
      here takes the non-Intel path on riscv64 anyway: ctranslate2 builds `WITH_MKL=OFF` with
      `OPENMP_RUNTIME=COMP`, clarabel swaps the mkl-backed pardiso, scs links OpenBLAS. A park
      with no downstream cost is worth stating as such — it closes the "but numpy/torch might
      want it" question the family's name invites.
