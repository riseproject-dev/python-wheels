# Gotchas index — router for the themed gotcha files

The porting gotchas (548 of them) live in [`references/gotchas/`](gotchas/), split by theme so only the relevant slice loads. Every gotcha keeps a **permanent number** cited elsewhere as "gotcha N" (and in workflow comments as "CLAUDE.md gotcha N"). Numbers are stable IDs — **not sequential**, and four are **reused** with different content (two each of 33, 55, 56, 57), disambiguated by theme below.

## How to find the gotcha you need

1. **Know the number?** Look it up in the *Number → file* table below, then `grep -n '^N\. ' references/gotchas/<file>`. For a reused number, both rows are listed — pick by theme.
2. **Have a symptom, not a number?** Use the *Topic router* to choose a file, then read that file's own `## In this file` list (each themed file leads with one).
3. **Searching by keyword across everything:** `grep -rn '<term>' references/gotchas/`.

## Topic router — pick a file by what you're doing

- **Is this even worth porting? all-`py3-none-*` wheels, vendored blobs, conda/CUDA-blocked deps, source-only distros** → [`gotchas/feasibility-and-triage.md`](gotchas/feasibility-and-triage.md)
- **Where does the sdist come from, git-tag≠version, dirty-tree/`setuptools_scm`/`tag_build` version poisoning, no-tag upstreams** → [`gotchas/sdist-source-and-versioning.md`](gotchas/sdist-source-and-versioning.md)
- **cibuildwheel knobs: `{project}` vs `{package}`, the interpreter matrix, abi3 tag collapse, `CIBW_ENVIRONMENT` cascade, YAML folding, heredocs** → [`gotchas/cibuildwheel-matrix-and-abi3.md`](gotchas/cibuildwheel-matrix-and-abi3.md)
- **Rust: maturin/setuptools-rust/pyo3, rustup targets, `MATURIN_PEP517_ARGS`, cargo features, cross-compile pre-flight** → [`gotchas/rust-maturin-and-pyo3.md`](gotchas/rust-maturin-and-pyo3.md)
- **Bazel bootstrap on riscv64, driving the container yourself (`docker run`), rules_python, per-interpreter loops, vcpkg-image replacement** → [`gotchas/native-build-bazel-and-drivers.md`](gotchas/native-build-bazel-and-drivers.md)
- **The manylinux_riscv64 image itself: Rocky 10 packages, EPEL/CRB, GCC/binutils versions, RVV/SIMD gates, perl/gconv** → [`gotchas/manylinux-image-and-toolchain.md`](gotchas/manylinux-image-and-toolchain.md)
- **Linking native deps: build-once C++, dep-wheel pattern, static-vs-shared, auditwheel `--exclude`, `patchelf` RPATH, missing symbols** → [`gotchas/native-deps-and-linking.md`](gotchas/native-deps-and-linking.md)
- **Is the wheel actually compiled? `.so` proof, mislabeled pure-Python wheels, the require-extension knob, free-threading declaration** → [`gotchas/compiled-vs-pure-detection.md`](gotchas/compiled-vs-pure-detection.md)
- **Dependencies & our registry: check pypi.riseproject.dev, per-interpreter coverage, `PIP_ONLY_BINARY`, matrix trimming, test-venv rebuilds** → [`gotchas/dependencies-and-registry.md`](gotchas/dependencies-and-registry.md)
- **Build-tool version drift: Cython/setuptools/numpy pins, `--no-build-isolation`, `PIP_BUILD_CONSTRAINT`, a published wheel breaking another package** → [`gotchas/build-tool-drift-and-pins.md`](gotchas/build-tool-drift-and-pins.md)
- **Tests import the checkout instead of the wheel: `CIBW_TEST_SOURCES`, rootdir shadowing, renaming the staged package, in-container build products** → [`gotchas/testing-and-shadowing.md`](gotchas/testing-and-shadowing.md)
- **pytest/test-run mechanics: staging the ini (`addopts`/`markers`/`log_level`), servers in `before-test`, `-W error`, choosing which tests run** → [`gotchas/pytest-config-servers-and-selection.md`](gotchas/pytest-config-servers-and-selection.md)
- **A job fails/segfaults/flakes: refcount bugs, xdist crashes, slow-runner races, libgomp/OpenMP, arch-specific numeric divergence, native backtraces** → [`gotchas/test-failures-and-flakes.md`](gotchas/test-failures-and-flakes.md)
- **Licensing: vendored-dep LICENSE files, PEP 639 vs setuptools globs, REUSE `LICENSES/`, the `gpl_sources` job, SBOMs** → [`gotchas/licensing-and-gpl.md`](gotchas/licensing-and-gpl.md)
- **Validate before pushing: local `pip wheel`, QEMU, the aarch64 rehearsal and its traps, `pip download` resolution checks** → [`gotchas/local-validation-and-rehearsal.md`](gotchas/local-validation-and-rehearsal.md)
- **PR/CI/publishing: registering a new workflow, version globs, action-SHA pins, maintainer holds/cancellations, post-merge publish** → [`gotchas/pr-ci-and-maintainer.md`](gotchas/pr-ci-and-maintainer.md)

## Number → file (every gotcha)

### Feasibility & triage — [`gotchas/feasibility-and-triage.md`](gotchas/feasibility-and-triage.md)

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
- **183** — `vendored-binary` is a category, not a verdict — the disposition still has to be
- **185** — A sibling distribution can be selected by an upstream *source-transform script*
- **186** — A sibling package's riscv64 vendor doesn't transfer if it publishes a different
- **187** — Gotcha 40's numba wall catches more than numba itself — check a candidate
- **203** — A `py2.py3-none-<platform>` wheel bundling a runtime can be the *opposite* of
- **214** — Not being Bazel-blocked doesn't mean a build is in scope — count the
- **230** — "CMake" isn't always a hand-maintained build — a project's own CMakeLists can be a
- **236** — An "LLVM-based" port is not automatically libclang-scale — check which CMake target
- **246** — A `pyO3`/uniffi "binding" package can vendor a closed-source Rust core as a git-committed
- **248** — An "inactive"/deprecated package's own PyPI ceiling can be a real ABI wall, not
- **249** — Gotcha 40/187's `Requires-Dist` check can pass clean while a *build-time-only*
- **263** — A PyPI wheel with no sdist and a closed-binary redistribution licence can still be
- **273** — A pinned transitive crate can lack riscv64 support outright, and `cargo check
- **276** — A hand-written-SIMD C library that looks x86/aarch64-only can still have a
- **284** — A package whose C/C++ extension calls CUDA/HIP/cuFile is not automatically
- **303** — A "Python 2 only" classifier is a stop sign the project's own `setup.py` may
- **310** — A package's algorithmic pedigree does not describe its current toolchain —
- **311** — A transitive crate's `compile_error!` gated on `target_feature` (not
- **318** — An explicit `python_requires` *upper* bound is a harder wall than an
- **334** — A stdlib-absorbed backport can fail to build on a modern interpreter for a
- **335** — Gotcha 273 generalizes: a pinned embedded-engine crate (deno_core/rusty_v8)
- **338** — A package whose real PyPI wheels are produced by a *packaging fork*, not its own
  source repo, can hard-depend at runtime on a sibling package from that same packaging
  ecosystem — and that sibling can itself be the actual blocker (the eigenpy/cmeel-boost case).
- **340** — Gotcha 335 generalizes past deno_core/rusty_v8 to a second embedded-engine family:
  a Rust FFI crate that itself only *downloads* a prebuilt native core, never builds it, can
  leave riscv64 with no build path at all even though the wrapper crate is pure Rust (the
  livekit case).
- **341** — A build-time transpiler binary from a *third* language ecosystem can block a port
  even when the extension itself is pure, portable C++ (the prophet/cmdstanpy/stanc3 case).
- **342** — A proprietary shared library downloaded and *linked* by `setup.py` itself fails
  closed on an unrecognised arch instead of degrading (the ibm-db case).
- **343** — A Bazel-built package can clear every dependency-tree check (gotcha 132/214) and
  still be blocked because its `WORKSPACE` links the extension directly against a *live,
  pip-installed* sibling package's compiled library, not just its headers (the
  tensorflow-io-gcs-filesystem case).
- **366** — A genuinely-compilable CMake C++ library can still be `not-feasible` when its
  kernel code is gated to specific SIMD ISAs with no portable/scalar fallback anywhere in the
  build (the embreex/Embree case).
- **372** — Zero sdist ever published, plus a license that independently bars redistribution
  even if a riscv64 build existed, is a double lock, not one (the hdbcli case).
- **373** — A binding whose own C-extension source is fully open can still be `not-feasible`
  when the thing it `dlopen()`s at runtime is proprietary with zero source and no riscv64
  build at the vendor, official or unofficial (the cx_Oracle case).
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
  `requires_dist` (not the most "core-sounding" name) fix the order; complements gotcha 380
  (how to publish them once the combined port exists) (the
  pyside6/pyside6-essentials/pyside6-addons case).
- **383** — The *umbrella* distribution of a split family carries no compiled code at all,
  gets its platform+`abi3` tag from a deliberately fake `Extension`, and its payload is
  generated stubs for the union of its siblings' modules — so it cannot be cut from a
  different build than they were; also, check the in-image SDK's *minor version* against the
  binding release (the pyside6 meta-wheel case).
- **385** — A no-sdist vendor wheel can still have a fully public build recipe — read
  `dist-info/WHEEL`'s `Generator:` before parking it for "no source anywhere"; a
  vendor-named generator is usually a *repackager*, which moves the stop to whether the
  vendor publishes the payload for our arch (the pyqt6-qt6 case).
- **386** — A GPU-only package can be small, source-open and blob-free and still be
  unportable: in a JIT kernel library the compiled part is a few-hundred-KB shim, so gotcha
  41's vendor-payload tell is absent and the wall is what that shim links — `libtorch_cuda.so`,
  which our CPU-only riscv64 torch can never provide; refines gotchas 249 and 284 (the
  humming-kernels case).
- **387** — A GPU-toolkit-suffixed distribution name (`-cuda12x`, `-rocm-7-0`) is a toolkit
  selector whose name can be injected from a *separate* release-tools repo; check the vendor's
  redist index for our arch, and treat a documented stub/no-CUDA build mode as a docs build,
  not a port (the cupy-cuda12x case).
- **388** — The queue entry's wheel shape is a snapshot — re-read the *latest* release's tag
  set before triaging the queued version, because upstream can delete the arch-specific
  payload and erase the gap outright; also, a `py3-none-any` dependency can be a facade for
  platform-only payload wheels (the tokenspeed-mla case).
- **392** — With no project URL and a stock `Generator:`, the *conda-forge feedstock* is the
  cheapest source-availability oracle (a feedstock whose `source:` is the PyPI wheels is a
  repackager, so there is nothing to build); `readelf -S` splits a real compiled extension
  into engine vs embedded model weights (`.text` ~280 KB, `.rodata` ~34.8 MB); a compound
  `License: <permissive> AND LicenseRef-*` is gotcha 372's second lock; and an open-source
  org's monorepo hits can all be the closed-source package's *consumer*
  (the livekit-local-inference case).
- **393** — The bindings half of a "bindings wheel + vendored-SDK wheel" pair looks unblocked
  from its sdist and is not: the blocking pin is added by the vendor's release step, not by the
  sources, and the coupling is a `RUNPATH` into the sibling wheel's directory; a distro-SDK
  build is defeated by the sibling's dlopened plugin/QML payload (the pyqt6 case).
- **405** — An NVIDIA-owned, profiler-adjacent package can have no CUDA dependency whatsoever:
  no CUDA header, no `libraries=`, the GPU only ever the *consumer* of the annotations — and
  parking it fakes a blocker for every portable consumer that depends on it (the nvtx case).
- **407** — An upstream recipe can stop being conda-based between releases: the tag the queue
  entry names built its C++ SDK inside micromamba (conda-forge has no `linux-riscv64`
  freeimage) while the newest tag uses `dnf` plus uv, so read the recipe — and the component
  versions in its workflow `env:` block — at the newest tag before pricing the port or
  recording a conda blocker; `api.anaconda.org/package/conda-forge/<name>` answers subdir
  coverage per package, and micromamba itself does ship a riscv64 binary
  (the cadquery-ocp-novtk case).
- **418** — An upstream wheel for another non-x86 architecture is only a precedent for the parts
  of it that are actually that architecture: the released paddlepaddle `linux_aarch64` wheel
  ships x86-64 `liblapack.so.3`/`libblas.so.3`/`libgfortran.so.3` beside a real aarch64
  `libopenblas.so.0`, because one prebuilt tarball covers all of Linux — `file`/`readelf -h`
  every `.so` in the sibling wheel before mirroring its build (the paddlepaddle case).
- **419** — Gotcha 411's "is the CPU backend the default?" test can pass and still not yield
  a port: a torch extension's non-CUDA branch can compile operator *schemas* with no
  implementations, so the build succeeds in seconds against a CPU-only torch and the wheel
  is a dead stub — count the sources that branch globs, diff the built `.so` against the
  published CUDA one, and call an op instead of trusting a "did the extension load" flag
  (the xformers case).
- **426** — A `-cpu` sibling can be an *x86_64-only label* rather than a portable CPU variant:
  where the base package's wheel is already CPU-only on every non-x86 arch, the sibling closes
  no riscv64 gap, is never cheaper than the base, and inherits the base's park — scan the
  sibling's whole release history for platform tags, compare the base's per-arch wheel sizes,
  and re-verify any sibling-family blocker at the revision your target actually pins
  (the tensorflow-cpu case).
- **431** — When a distribution has **never** published an sdist, gotcha 35/157's "grep the
  build script for the fetch" has nothing to grep: count sdists across every release, then
  `strings -a` the vendored blob — private builder paths (`/.conan/data/…@vendor/prod`,
  `/home/jenkins/`, `/vcpkg/buildtrees/`) prove a closed vendor with no riscv64 source, and
  open-source crates in the same output are only the shim around it
  (the livekit-plugins-noise-cancellation case).
- **436** — A big CMake project's whole non-x86 story can be a single `uname -m == aarch64`
  boolean, so a third arch silently takes the x86_64 path: `grep` every site of that boolean to
  enumerate the prebuilt-x86_64 downloads (all fixable), then triage the one site whose
  `aarch64` branch works only because the dep itself ships an ARM SIMD shim — a mandatory dep
  with no off switch and no scalar path (gotcha 366) is the verdict, and the same branch's
  configure failure reproduces on any x86 host (the Open3D case).
- **438** — A "redistributable `<vendor binary>`" distribution can repack a vendor blob on some OSes
  and build genuinely from source on the one a port needs, so apply gotcha 35/157/431 per OS by
  reading the build scripts rather than the download script; includes the minutes-long check that
  depot_tools/gn/CIPD already support riscv64 (302-vs-404 probes against chrome-infra-packages,
  `detect_host_arch.py`, `gcc_toolchain("riscv64")`) and the only two CIPD packages missing for
  `linux-riscv64` — siso and reclient — which `.gclient` `custom_deps` nulls out (the
  comfy-angle/ANGLE case).
- **442** — A vendored dependency's build system can silently omit a capability flag its other
  build system defaults on: XNNPACK's Bazel build never defines `XNN_ENABLE_RISCV_VECTOR` where
  its CMake build defaults it ON, so half its riscv64 RVV dispatch sites (no runtime
  `getauxval(AT_HWCAP)` check) compile out to scalar only by that omission — re-verify on every
  XNNPACK version bump, since fixing it upstream would make the ungated blocks go live (the
  mediapipe case).
- **449** — A prebuilt riscv64 binary an upstream downloads for you can be built for a *vendor*
  ISA — `file`/`e_machine 243` says riscv64, not *which* riscv64: openvino's bundled oneTBB is a
  T-Head Xuantie build (`xtheadc` in `Tag_RISCV_arch`, 906+892 CUSTOM-0 `0x0B` instructions
  against zero in the 17 libraries built locally), so the wheel runs only on T-Head cores and a
  green run on a T-Head runner fleet does not prove a `manylinux_riscv64` wheel is portable.
- **450** — A vendored native payload can be a *GraalVM Native Image* (`GraalVM CE …`,
  `com.oracle.svm`, `.svm_heap` in `strings`), which moves the wall from "is there source?" to
  "does the AOT toolchain target riscv64?": Native Image ships no riscv64 build from Oracle,
  GraalVM CE or Mandrel, and `Platform.LINUX_RISCV64`/`ELFMachine.RISCV64` existing in graal's
  source is a research LLVM-backend port, not shipping support — plus a published source drop
  with zero build files is not a from-source path (the saxonche/SaxonC-HE case).
- **452** — A GPU-only package can enforce the GPU from its *pure-Python* `__init__.py`: an
  import-time probe module that `dlopen`s `libnvidia-encode.so.1` and selects which of two
  prebuilt extensions to load from the driver's reported version, while the probe's own
  `readelf -d` shows no CUDA at all — and a documented CUDA-free build flag (`DEMUX_ONLY`)
  that upstream never ships, whose product still would not import and is not what the package
  does, rescues nothing; plus the unauthenticated NGC source-zip API (the pynvvideocodec case).
- **453** — A closed commercial engine is not one build recompiled per arch: gurobipy's 49.6 MB
  x86_64 `libgurobi130.so` links Intel MKL and its 168.5 MB aarch64 twin links Arm Performance
  Libraries, so the wheel-size diff names the closed BLAS a vendor port would need for riscv64
  (there is none) — plus a vendor's package server and conda channel are the same two platform
  tables as an open project's, and a `.lic` key check in the payload kills gotcha 35's
  swap-in-another-build escape hatch (the gurobipy case).
- **459** — A CUDA-only PyPI wheel does not make the *project* CUDA-only: a device-selecting
  build env var can produce a genuinely portable CPU distribution from the same tree, and
  upstream may already carry riscv64 kernels for it (the vllm case).
- **462** — A `<pkg>-core` split sibling is still its own port after the main package shipped in
  the *non-split* shape: the self-contained wheel closes the Python gap but not the
  native-consumer one, and the missing piece is two tiny files (the sherpa-onnx-core case).
- **464** — A full `cpXY-cpXY-<platform>` tag can be fabricated by a `has_ext_modules()` that
  hardcodes `True`, with no extension module anywhere (PyPy tags beside CPython ones and
  byte-identical wheel sizes across ABIs are the tells); and the payload behind it can be a
  foreign-language runtime the package only shells out to, whose unknown-arch fallback quietly
  swaps in an arch-neutral build instead of failing (the artifacts-keyring case).
- **465** — A closed vendor accelerator blob can be *full* of `riscv` strings and carry a whole
  LLVM RISC-V code generator while shipping x86_64-only wheels, because the ISA runs on cores
  inside the accelerator: the registered `LLVMInitialize*Target` set, the device-side proto
  paths and the Bazel `k8-fastbuild` builder path tell host support apart from a device target
  (the libtpu case).
- **467** — Gotcha 341's foreign-ecosystem code generator, one step harder: a generator that
  runs at *runtime* over arbitrary user input has no "pre-generate the output on x86_64 and
  vendor it as a patch" escape hatch, so it is `blocked-on-dependency` however portable the
  rest of the C++ is; also, an exact compiler-version pin (`ocaml {= "4.14.1"}`) stops the
  distro's own newer package from short-circuiting the bootstrap, and a `.so`-presence check
  can pass on a vendored library while no extension module is shipped at all; also, a
  `--platform linux/riscv64` container on an x86_64 host runs an x86_64 bundled binary
  *natively*, so it cannot demonstrate an arch mismatch (the httpstan/stanc3 case).
- **470** — A `.queue.yml` note reading `abi: 0` is a wheel *build tag* (PEP 427's build
  number, stamped by `Generator: cmeel`), not an ABI tag: the wheels are ordinary
  per-interpreter compiled ones. For a co-installed-prefix ecosystem like cmeel, `readelf -d`
  on one released wheel of any arch names every sibling distribution that needs its own port,
  because the shared `cmeel.prefix` `RUNPATH` means nothing is bundled; measure the closure
  over `requires_dist` + our registry and hand over the tiers (pin: 11 unported packages,
  leaves first), capped by cmeel-boost's interpreter coverage (the pin/pinocchio case).
- **471** — A GPU package's architecture axis is bounded by its *accelerator vendor's* toolkit
  axis, so a freshly added aarch64 wheel is no sign riscv64 is next: read the body of the arch
  branch (`LIBCUDA_ARCH="sbsa"`, `pytorch/manylinuxaarch64-builder:cuda*`), not the wheel list.
  And read a forced-platform env var's accepted *values* before treating it as gotcha 459's
  rescue — `hip`/`cuda`/`xpu` with a `#error` default is a vendor selector, not a device-class
  one; also, an `LD_PRELOAD` hook can be a hook on `cudaMalloc` over the CUDA VMM driver API
  rather than on a generic allocator (the torch-memory-saver case).
- **475** — A package that vendors a whole database engine can pass every architecture check
  (`ARCH_RISCV64`, a riscv64 toolchain file, an upstream riscv64 CI job, riscv64 branches in the
  jemalloc/LLVM contrib CMakes, the image's own clang 21) and still be a park on runner-hours:
  price it in ninja edges × this fleet's measured per-edge cost (VTK ≈21 core-s, V8 ≈117),
  check whether the build script runs the whole tree twice behind a flag that lands in a
  generated header, and note that an upstream arch port guarded by `if (CMAKE_CROSSCOMPILING)`
  gives a native build none of its accommodations (the chdb-core/ClickHouse case).
- **476** — A CMake project whose CI submits to CDash has already published its build cost per
  platform: `open.cdash.org/api/v1/index.php?project=<p>&date=<d>` gives configure/compile/test
  seconds per submission, the release-tag rows are the full builds, and the per-language rows
  say whether the interpreter leg is cheap (the simpleitk/ITK case).
- **478** — Gotcha 343's "revisit once `<dep>` has a riscv64 build" is wrong for an *archived*
  dependent: a read-only upstream can never widen its pin, so the port is blocked on a
  historical version of the dep (TF 2.15, not this repo's 2.21.0), the pin window's own
  interpreter coverage can miss the default matrix entirely, CUDA is not the blocker in a TF
  custom-ops package, and a negated-x86 arch allowlist mis-classifies riscv64 into `-mavx`
  (the tensorflow-addons case).
- **480** — A non-NVIDIA accelerator vendor (Huawei Ascend/CANN) can keep its whole toolkit
  behind `dlopen`, so the released wheel's `DT_NEEDED` is clean and the tell is in `strings`
  plus an import-time `provision()`; a three-valued `XPU_TYPE=NONE/NPU/GPU` selector is not
  gotcha 459's rescue when `setup.py` appends `+cpu` to the version, because a build mode that
  renames the artifact cannot yield the queued version; and the CPU mode's only transport is
  Huawei's UB/urma `hcom`, whose CMake sends everything that is not aarch64 to `-msse4.2`
  (the memfabric-hybrid case).
- **481** — A `[tool.poetry.build] script` makes poetry-core stamp a full
  `cpXY-cpXY-<platform>` tag whatever the script does — jsonschema2md's only compiles gettext
  `.po` into `.mo` — so the wheel holds zero `.so`, the tag halves are whatever runner
  published it, and the release history dates the flip to the release that added i18n
  (the jsonschema2md case).
- **483** — Gotcha 125's "a dependency with no riscv64 wheel is only a blocker if it cannot
  build from its sdist" must be executed, per package and against the end user's
  `pip install`: a member of a blocked shared-prefix family can be two leaves deep rather than
  eleven, and a sibling that looks trivially compilable (vendored source, `cmeel[build]` its
  only build requirement) can still fail from sdist because its vendored
  `cmake_minimum_required` is below CMake 4's floor — and the `CMAKE_POLICY_VERSION_MINIMUM`
  that fixes that in `CIBW_ENVIRONMENT` does not ship with the wheel, so a green CI run would
  publish an index entry the index cannot install (the cmeel-urdfdom case).
- **484** — A large C++ project with its own architecture abstraction layer concentrates the
  whole port into a handful of `#error` gates in that one directory, and the CPU-gated ones are
  a small minority of them; the build config the wheel uses decides how many you ever reach
  (the usd-core/OpenUSD case).
- **492** — A declared dependency the build never actually links against still blocks the port,
  because pip enforces the metadata and not the linkage; the wheel's own `.pc` and `readelf -d`
  say which it is, and editing it out of `pyproject.toml` is the shortcut to refuse (the
  cmeel-assimp/cmeel-zlib case).
- **503** — Triage a framework's closure by each node's own published artifacts: same-org
  siblings that look like the native core can be `py3-none-any` while the leaves block, an
  exact `==` pin makes an already-ported package a blocker at the *version* level,
  `--only-binary` resolvers false-positive on sdist-only pure Python, and an sdist with no
  native sources can still be unbuildable (the angr case).
- **505** — A cmeel note's build number need not be `0`, and `abi: 4,5` means one wheel
  version was packaged twice: build the highest `.cN` tag, never an assumed `.c0`.
- **506** — Gotcha 263's "closed wheel, open project inside" rescue is per package, not per
  vendor: a version that is a release-train number rather than an open tag, and a largest
  payload whose `DT_NEEDED` names the vendor's own closed runtimes, mean there is nothing to
  rebuild — plus the vendor's apt index and EULA as independent stops (the intel-openmp case).
- **509** — A riscv64 prebuilt of the blocking crate can exist and still not unblock the port:
  resolve the asset name the *consumer's* cargo features produce (`_ptrcomp_sandbox`), and in a
  Bazel build read `SUPPORTED_EXECS`, not just `SUPPORTED_TARGETS` (the openai-codex-cli-bin/
  rusty_v8 case).
- **522** — Gotcha 35's prebuilt payload can be *committed to a separate packaging repo* rather
  than downloaded at build time, which leaves no fetch to grep: `file` the committed binary and
  match its `BuildID` against the released wheel's, build the sibling C++ repo at the same tag,
  and drive the container yourself because a PEP 517 frontend discards the wrapper script's
  `--plat-name`; also, `EXCLUDE_FROM_ALL` does not keep a vendored library out of `all` when an
  `all` target links it (the lib3mf case).
- **523** — Clearing a layered ecosystem's leaf tier does not make the next-named package
  actionable: gotcha 470's `abi: 0` notes make every tier look alike, so recompute the frontier
  from each candidate's own `[build-system] requires` (a missing sibling there means no build to
  attempt, unlike one in `[project] dependencies` alone), `readelf -d` the candidate's *own*
  released wheel for link-time `NEEDED` siblings, and run the resolver oracle a second time with
  the known-missing requirements dropped because it stops at the first failure
  (the libpinocchio case).
- **524** — A vendored payload that builds fine for riscv64 *elsewhere* (Debian ships `adb` for
  it) is still a park when this repo would be the one building it: an unpinned `-latest-` fetch
  URL means a self-built substitute can never be version-matched to the other platforms' wheels
  of the same release, the vendor's package manifest
  (`dl.google.com/android/repository/repository2-{1,3}.xml`, no `host-arch` at all) is the
  platform table when the URL has no arch segment, and the pure-Python sdist plus a
  `$PATH`/env-var resolver already serves the arch; also gotcha 503's resolver false positive,
  concretely (the adbutils case).
- **528** — An open upstream and a permissive licence do not rescue a vendor runtime wheel
  (the intel-cmplr-lib-ur case): the unstripped `.so`'s debug paths name the vendor's internal
  release branch rather than a public ref, so gotcha 263's "PyPI version == open tag" premise
  fails; the loader's `dlopen` backend list minus the adapters actually shipped shows the vendor
  withholding the arch-neutral ones; and the reverse dependencies (plus a hard-pinned, equally
  x86-only payload dep) mean nothing on riscv64 could ever pull the rebuilt library in.
- **516** — Link-time *stub* shared libraries let a vendor-SDK package build with the SDK
  absent, so a clean local build proves nothing: the released wheel's `DT_NEEDED` read against
  `setup.py`'s `auditwheel --exclude` list is the real test, and the toolkit's arch axis comes
  from the vendor's image registry (the torch-npu / Huawei CANN case).
- **518** — A commercial vendor's package with a complete, buildable sdist but no licence
  declared anywhere — not in its own metadata, not in the parent distribution's — is a
  licensing question for the maintainer, not a feasibility verdict: record `license: Unknown`,
  flag it in the PR, and port it (the chalkpy-rs case).
- **529** — Gotcha 524 with the opposite answer: a vendored prebuilt binary whose upstream
  already publishes riscv64, named by the wrapper's own version string (`1.9.0.67.0` = wrapper
  + fzf 0.67.0, the first fzf release carrying `linux_riscv64`); the port is then the two
  platform-table rows the packaging backend is missing, plus a warning not to adopt upstream's
  wheel smoke test without running it (the iterfzf case).
- **530** — A `setuptools-golang`/cgo extension is an ordinary port, not a vendored-binary
  case: the per-interpreter tags are honest (a real `PyInit_*` extension), and feasibility is
  a Go question — check the toolchain's own arch-support table for the buildmode used, confirm
  go.dev ships the target tarball, and cross-build the import graph with `GOOS`/`GOARCH` set on
  x86 rather than assuming a wall (the certbot-dns-multi case).
- **531** — Inside an already-parked accelerator-vendor family, the next package's verdict is
  usually in its dependency list, not its source: `requires_dist` naming a parked sibling plus
  an unconditional top-level import of it is a complete stop, and the sibling is normally a
  build input too (submodule, header globs, `LD_LIBRARY_PATH` for auditwheel) — corroborate
  with the family's recurring negated-x86 `else()` one dependency down (the memcache-hybrid
  case).
- **532** — Gotcha 481's poetry-core build-script tag with the wrinkle that makes it look
  port-worthy: the script's output can be conditional on a host tool (`msgfmt`), so the
  released wheel carries catalogs a from-sdist install silently drops — and a wandering
  interpreter/glibc tag across the release history proves the tag follows the publishing
  runner (the reuse case).
- **534** — A vendor artifact bucket can answer `403 AccessDenied`, not `404`, for a key that
  was never published, so the riscv64 probe needs a bogus control name — and the spelling to
  probe with is in the payload's own `RPATH`/builder path; plus a FLEXlm gate as a second
  closed vendor, a licence that lives only behind a URL, and the vendor's retired packaging
  repo naming the download-and-repack method (the mosek case).
- **544** — A CMake option named after a GPU vendor (`..._CUDA_PROVIDER`,
  `..._LEVEL_ZERO_PROVIDER`) does not by itself mean the build needs that vendor's SDK — check
  whether the code behind it `dlopen()`s the runtime at call time instead of linking it at
  build time before disabling it; gotcha 480's dlopen tell used in the opposite direction, plus
  a technique for recovering a library's exact upstream CMake flags from a self-describing
  build-config string embedded in the shared library itself (the umf case).
- **556** — A closed-source vendored runtime can leave *zero* public indices to check — not
  even the fetch script itself, one notch past gotcha 157: a legitimate, real upstream repo
  whose wheels bundle a per-platform binary built entirely inside the vendor's own internal
  build with no source, no fetch script and no downstream artifact index published anywhere
  (the google-antigravity case).
- **557** — When PyPI's own metadata is blank, search for the project's own site/blog before
  doing wheel forensics — the maintainer's own words ("not open source today") and the
  wheel's own bundled LICENSE ("does not grant access to... the source code") can both
  independently settle closedness (the frisky case).
- **558** — A SWIG/pybind11-bound extension over a *stack* of large native libraries can be
  correctly source-available and buildable in principle, and still be a park purely on
  runner-hours — check what upstream's own CI actually re-builds, not just what it lists as a
  dependency, and use a smaller already-ported OpenCASCADE consumer's real CI timings as the
  scale yardstick (the ifcopenshell case).
- **560** — A GPU-vendor binding package that only `dlopen`s its runtime library at call time
  (deferring the missing-library problem) can still be build-time blocked by the same
  vendor's SDK headers — the SDK's own platform matrix, not the binding's link graph, is what
  settles it (the hip-python case).
- **561** — A pybind11 project whose Python API has nothing to do with GUI toolkits can still
  hit the same Qt5-on-riscv64 wall as a PyQt/PySide port — check every mandatory
  `find_package` in the CMake tree the extension actually builds, not just what the
  package's name or API surface suggests (the pymeshlab case).
- **562** — Existing non-x86_64 wheels (aarch64/arm64) are real portability evidence, but don't
  outweigh a scale check against this repo's own comparable precedents — a package can clear
  the "does upstream already support another architecture" bar and still be impractical (the
  drake case).

### Sdist source & versioning — [`gotchas/sdist-source-and-versioning.md`](gotchas/sdist-source-and-versioning.md)

- **1** — Not every project can build an sdist from its git checkout.
- **2** — The PyPI sdist is often self-contained and architecture-independent
- **3** — Git tag ≠ Python package version.
- **4** — Build arch-independent artifacts on `ubuntu-latest`, not the riscv runner.
- **18** — The wheel-filename version is canonical; keep three places in sync
- **22** — A release-branch checkout can carry `[egg_info] tag_build = dev` in
- **31** — `git apply` onto a `setuptools_scm` checkout renames the wheel (the lz4 case).
- **43** — Upstream may not be on git at all — look for the author's own read-only git
- **103** — An upstream on GitHub that publishes releases without ever pushing a git tag —
- **135** — A version placeholder that upstream's *release script* stamps is a fourth way to
- **154** — A PyPI `project_urls` repository link can 404 — search for the live repo before
- **156** — An upstream that exists only as a PyPI sdist is still an ordinary port — but
- **213** — Gotcha 103's timestamp-proximity trick can point at the wrong commit when
- **242** — A third-party tree-sitter grammar's release tag can omit the generated
- **254** — A build-from-checkout can pick up a maintainer-only dev/coverage cflags
- **258** — A hardcoded download URL in a project's own build script can 403 automated
- **293** — The newest git tag is not necessarily the version to port — check whether
- **261** — A package can require its own compiled extension, plus a large downloaded
- **265** — A project's own version-detection script can read `GITHUB_REF` directly,
- **268** — A vendored C-core git submodule can have its own `git describe`-based
- **274** — A build-from-checkout package can tag releases in a format the version
- **275** — A live, legitimate `project_urls` repo link is not proof it holds the released
- **299** — Gotcha 103's "no tag, but a real commit does the bump" can be missing entirely —
- **315** — `versioneer` has no `SETUPTOOLS_SCM_PRETEND_VERSION` equivalent for gotcha 31's
  dirty-tree problem — `git update-index --skip-worktree` on just the patched files fixes
  it instead.
- **319** — A release tag can exist, be reachable, and check out cleanly, yet still be the
  wrong commit — check `git merge-base --is-ancestor <tag> origin/main` before trusting it.
- **352** — A gitlink with no `.gitmodules` entry breaks `actions/checkout`'s own
  persist-credentials cleanup, not the checkout itself.
- **406** — Gotcha 103's byte-for-byte sdist proof cannot come out clean when upstream cuts
  releases from a non-public tree: a `[tool.cibuildwheel]`-only difference is not a wrong pin,
  and the released sdist's `test-command` can name a script that never existed (the nvtx case).
- **466** — Gotcha 2's counter-case: an sdist can omit `CMakeLists.txt` and the C sources
  entirely, and `pip wheel` on it still exits 0 — producing a `py3-none-any` wheel with no
  extension that imports fine and dies on first use (the piper-tts case).

- **521** — A SWIG/autotools binding can publish wheels and no sdist at all because the
  generated wrapper lives only in upstream's `make dist` tarball: mirror upstream's own
  tarball job (SWIG from source, `autogen.sh && configure && make dist` on both the library and
  the bindings repo) on x86 and hand the pair to the riscv job (the quantlib case).
- **546** — A project can ship its C++ dependency-manager (CPM) cache inside the sdist, so the
  from-sdist build is hermetic where a from-checkout build is not: run the project's own
  cache-populating step on `ubuntu-latest` and hand the tarball to the riscv job, and patch the
  extracted sdist rather than the checkout when a target sits inside a submodule
  (the couchbase case).
- **569** — A tag can check out clean and still hand a build literal Git LFS pointer stubs
  instead of real content, when upstream squash-merges former git submodules into the main
  tree without resolving their LFS objects first — verify by sha256 against the pointer's own
  `oid` before trusting a same-content fetch from the pre-merge submodule (the semgrep
  v1.177.0 case).

### cibuildwheel mechanics, the matrix & abi3 — [`gotchas/cibuildwheel-matrix-and-abi3.md`](gotchas/cibuildwheel-matrix-and-abi3.md)

- **5** — cibuildwheel `{project}` vs `{package}`.
- **7** — Heredoc inside a YAML `run: |` block.
- **11** — abi3 wheels collapse the matrix.
- **12** — Scope an env var to one phase with the right knob.
- **13** — `build-frontend = "build[uv]"` crashes the audit step on the riscv runner.
- **34** — A third way a project gets abi3: `setup.py` sets the `bdist_wheel` option itself.
- **93** — A `>-` folded scalar keeps the newline on any line indented *deeper* than the
- **96** — An abi3 wheel must be built on the OLDEST interpreter its tag claims — building
- **102** — A `build.py` at the project root shadows the `build` module and kills
- **107** — `CIBW_ENVIRONMENT` *replaces* upstream's `[tool.cibuildwheel] environment` table
- **134** — cibuildwheel's default abi3 audit rejects a wheel for exporting its *own*
- **56** — `py-build-cmake` projects: the free-threaded job dies at *configure* unless *(reused number — this theme)*
- **201** — When `package-dir` is a monorepo subdirectory and the package's own build script
- **204** — cibuildwheel 4.2.0 doesn't offer cp313t as a build target on *any* platform —
- **209** — A multi-grammar tree-sitter-`<lang>` repo does not necessarily need a
- **216** — An abi3 build's own mandatory floor interpreter (gotcha 96) can itself be the one
- **217** — Upstream's own `repair-wheel-command` commonly re-runs abi3audit itself via
- **221** — `quay.io/pypa/musllinux_1_2_riscv64` is a real, working image — every prior port
- **225** — `CIBW_BEFORE_ALL_LINUX` and `CIBW_BEFORE_BUILD_LINUX` are two different hooks —
- **227** — A build that touches `PyObject` internals directly (`ob_refcnt`, `ob_type`,
- **245** — `actions/checkout` must run before `actions/download-artifact` in the same
- **247** — A folded `>-` scalar's `python -c "` on its own line puts a leading space
- **251** — When `package-dir` is a `.tar.gz`, cibuildwheel extracts it to a temp dir and
- **262** — Gotcha 201's vendoring step is only needed when the sibling sources are
- **270** — Gotcha 134's "leaked `Py`-prefixed symbol" failure has a real fix, not just
- **281** — Gotcha 251 recurs even when the port's own notes cite gotcha 104 — a
- **313** — A dynamic abi3 floor (`setup.py` tags whichever interpreter builds it) lets you
- **324** — `{project}` is exactly the on-disk root of the checkout with no `path:` —
- **331** — A platform-specific `[tool.cibuildwheel.<platform>].environment` table already
- **356** — A pybind11 3.x CMake build can silently target the wrong Python on cp314t —
- **360** — A `setup.py`'s own `bdist_wheel --plat-name` insertion can hardcode
  `manylinux1_` + `platform.machine()` regardless of the actual container libc, making
  musllinux unbuildable no matter how the CMake/C++ side is patched.
- **391** — A project's real cibuildwheel recipe can live in a *separate packaging repo* that the
  source tree never references — the source repo can carry no GitHub Actions at all.
- **396** — A `cpXY-none-<platform>` wheel is the third plat-name shape: `setup.py` declares
  no `ext_modules` at all, and a sibling CMake build both compiles the extension modules and
  hands `bdist_wheel` the tag (the coremltools case).
- **402** — A two-leg abi3 + free-threaded matrix expressed only through `include:` collapses
  into a single job, so the abi3 wheel is never built and nothing fails — make the leg a real
  matrix dimension (the primp/arro3-core case: two already-published packages are quietly
  shipping only their free-threaded wheel). Any include-only leg set does it, not just abi3
  ones — grain's cp312/cp313/cp314 set collapsed to cp314, and 58 jobs repo-wide still carry
  the shape.
- **408** — A `setup.py` that reaches for `wheel.bdist_wheel` behind a `try/except ImportError`
  still gets its abi3 tag under modern setuptools — setuptools ships a `wheel.bdist_wheel`
  shim, so do not add `wheel` to `build-system.requires` to "fix" it.
- **468** — An upstream `build = ["cp3??-*"]` glob excludes every free-threaded interpreter by
  character count, so the project ships no `cp3NNt` wheel and an unguarded `py_limited_api`
  would mis-tag one if a `cp314t` leg were added.
- **469** — An abi3 build *tests* on its floor interpreter, so a package using a
  newer-Python-only API (`code.co_qualname`, 3.11+) fails our CI while upstream's own CI
  stays green; rehearse on the abi3 floor, not your host's default interpreter.
- **487** — `[tool.cmeel] has-sitelib` decides whether a cmeel port needs an interpreter
  matrix: `false` means one `py3-none-<platform>` wheel and a single cibuildwheel job,
  bindings mean a real per-interpreter matrix; the queue note's `abi: 0` cannot tell them
  apart.
- **514** — A tool that models a *target* Python version caps the matrix itself — the extension
  compiles and imports on every interpreter, so run the tool's CLI, not `import`, to find the
  ceiling (the pytype case).
- **536** — An option cibuildwheel *removed* (3.0 dropped `free-threaded-support` and the
  `cpython-freethreading` enable group) makes 4.2.0 reject upstream's entire
  `[tool.cibuildwheel]` table before it selects anything, so every interpreter fails in
  seconds with no compiler in the log; upstream's own older cibuildwheel pin is why a healthy
  tag carries it, `cibuildwheel --print-build-identifiers --only <id> .` catches it on any
  host, and the fix is a one-line patch rather than a `config-file:` override
  (the spacy-pkuseg case).
- **542** — A `setup.py` that itself `raise SystemExit`s above a hardcoded max Python minor
  version blocks the *build*, not just runtime behavior — trim the matrix to match rather
  than exporting the documented override env var (the cocotb case).
- **549** — A queue note's odd-looking interpreter tag (a CPython minor with no public stable
  release yet, an unfamiliar PyPy triple) is not evidence of scraped garbage — verify it
  against the live PyPI JSON `releases` dict and the extension crate's own `pyo3` dependency
  line before discounting the matrix (the ignore-python case).
- **564** — `pypa/cibuildwheel`'s action has no `build:` input (only `package-dir`,
  `output-dir`, `config-file`, `only`, `extras`); passing one is silently dropped, and
  cibuildwheel falls back to its default matrix floor instead of the intended abi3
  build list (the vegafusion case) — use `CIBW_BUILD`/`only:` instead.

### Rust, maturin & PyO3 — [`gotchas/rust-maturin-and-pyo3.md`](gotchas/rust-maturin-and-pyo3.md)

- **10** — Rust/PyO3 packages (maturin *or* setuptools-rust) — traps.
- **59** — Crate features and a pinned Rust channel reach a maturin build through
- **78** — Rust ports: `cargo metadata --filter-platform <triple>` settles which crates a target
- **117** — A maturin `bindings = "bin"` project ships one wheel per platform, no interpreter
- **181** — A pyo3 crate can carry `abi3` unconditionally in its own dependency declaration —
- **182** — Cross-compiling a pyo3 crate as a riscv64 pre-flight needs
- **141** — A maturin project built through PEP 517 inherits `[tool.maturin] profile` — which
- **147** — A Rust crate that downloads a prebuilt native library almost always has an
- **155** — maturin abi3 can be an opt-in Cargo *feature*, so a plain PEP 517 build silently
- **179** — A pinned *git* dependency that does not build on riscv64: redirect it with a cargo
- **187** — A `bindings = "bin"` project that ships no wheel-level test suite at all (the
- **224** — `python -m <name>` is not a given for every `bindings = "bin"` wheel — it only
- **228** — A crate graph far smaller than gotcha 141's polars-runtime/deltalake examples can
- **237** — A pyo3 `#[pymodule_init]` can eagerly `import` a platform-specific companion
- **238** — A repo-root `rust-toolchain.toml` pinning nightly for lint-only use can still
- **239** — A maturin project inside a Cargo workspace can have its `pyproject.toml` at a
- **259** — A maturin `bindings = "bin"` project can declare two `[[bin]]` targets where
- **260** — `puccinialin` (and similar rust-bootstrap-on-demand helpers) has no riscv64 entry
- **266** — A vendored-C build script's own "require SIMD" default feature can turn
- **287** — A repo-root `.cargo/config.toml` can unconditionally point `PYO3_CONFIG_FILE`
  at a file only a task-runner's activation hook generates, breaking every cargo
  invocation outside that task runner.
- **300** — A crates.io dependency with no riscv64-compatible release can be patched via
  `[patch.crates-io]` at a vendored, fixed copy — but a git checkout of its monorepo
  nested inside the referencing workspace's own directory tree confuses cargo's
  workspace-boundary detection; the crate's own crates.io tarball (already flattened,
  no `[workspace]`) sidesteps it.
- **306** — A pyo3 release that predates a newer CPython by years does not necessarily
  fail to build against it — `pyo3-build-config` only floors the supported version, it
  has no ceiling.
- **312** — A maturin `bindings = "bin"` project's published sdist can carry a
  `pyproject.toml` that exists nowhere in the git checkout at all, not even in a
  subdirectory — building the tag directly silently ships the wheel under the Cargo
  crate's name instead of the real distribution name.
- **314** — A maturin *library* project (`bindings` unset/`pyo3`) with no `python-source`
  and no `<name>/` directory anywhere in the git checkout can still ship a wheel with an
  auto-generated `<name>/__init__.py` re-export shim wrapping a `<name>.<name>` compiled
  submodule — probing `import <name>; <name>.__file__.endswith('.so')` fails on the shim.
- **322** — A pyo3 release old enough to hand-roll CPython's legacy `PyUnicode_KIND`/
  `PyUnicode_DATA` macros as raw struct-offset reads can compile clean against a newer
  CPython and still segfault the first time a string crosses the FFI boundary — bisect by
  interpreter in the matrix (a segfault on only the newest leg is the diagnosis) and drop it.
- **326** — Gotcha 306's "pyo3-build-config has no ceiling" is not universal — a newer pyo3
  release can hard-error at build time against an interpreter it postdates; verify per
  release rather than assuming, and check whether a version bump is low-risk (a clean local
  `cargo check`) before choosing it over dropping the interpreter.
- **325** — A maturin `[tool.maturin] include` list is scoped to the wheel, not the sdist,
  so a project whose list omits `tests/` ships a tests-less sdist; when the project's
  `Cargo.lock` is already committed (no gotcha 10 floating-deps risk), drop the sdist job
  and build straight from the git checkout instead of staging tests via gotcha 104.
- **344** — `PyO3/maturin-action` reads the target crate's `pyproject.toml`
  `[build-system] requires` for its maturin version unless `maturin-version:` overrides it;
  a stale exact pin that upstream's own CI never exercises (it calls the action directly,
  bypassing PEP 517) can predate riscv64 release assets and 404 the action's own "Install
  maturin" step with `gzip: stdin: not in gzip format` before your build ever runs.
- **345** — Inside a driven-yourself `before-script-linux`, `PyO3/maturin-action`'s own
  hardcoded `PATH` additions for manylinux's per-interpreter `/opt/python/cp3XX-cp3XX/bin`
  stop at cp312; a `pip`-installed console-script (e.g. `protoc-gen-mypy`) for cp313+ is
  invisible to a PATH-based `which`/`shutil.which()` even from that same interpreter —
  resolve its scripts directory via `sysconfig.get_path("scripts")` instead.
- **364** — Patching a checked-out workspace `Cargo.toml`'s placeholder version (to match
  a static `pyproject.toml` version) stales `Cargo.lock`'s local-package entries, so
  `PyO3/maturin-action`'s `--locked` fails `cargo metadata` before any build starts; drop
  `--locked` instead (matches upstream's own release workflow, which never sets it either
  when it patches the version the same way).
- **365** — A `bindings = "bin"` project with a heavy dependency tree (async runtime + TLS
  + LSP framework) can stall on the riscv64 self-hosted runner for hours past the default
  360-minute `timeout-minutes` with no new log output, then get cancelled with no
  diagnostic — while an otherwise-identical retry finishes in under an hour; set a
  generous timeout margin (1440, matching other heavy Rust ports) as insurance rather than
  relying on the happy-path duration.
- **371** — pyo3 0.22's version ceiling (gotcha 306) is a hard ceiling for a non-abi3,
  per-interpreter build too, one minor above its own release-time latest (cp314 against a
  0.22.0-pinned crate fails outright); `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` clears it
  without turning abi3 on, verified to build and run correctly, but cp314t stays a real
  wall since 0.22.0 predates PEP 703 entirely.
- **425** — An aya/eBPF crate cannot build its BPF half on the riscv64 runner: `bpf-linker`
  dlopens LLVM from the Rust toolchain's shared library, which only the x86_64/aarch64
  dists ship (riscv64 hides it inside `librustc_driver`), and no system LLVM new enough for
  a current toolchain's bitcode exists for riscv64 — cross-compile the object on an x86_64
  job (gotcha 4) and patch the build script to embed a staged one.
- **479** — maturin `bindings = "cffi"` is a fourth `py3-none-<platform>` shape (a real Rust
  cdylib that cffi's ABI mode `dlopen`s, gotchas 27/35/81/145's missing branch), and one
  `CIBW_BUILD` list — not a `python:` matrix with `only:` — builds it once and re-tests it on
  every interpreter, free-threaded included, because cibuildwheel reuses an `abi == "none"`
  wheel where it refuses an abi3 one.
- **527** — Gotcha 371's `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` escape hatch is not free:
  `is_abi3()` reads it with no version condition, so `Py_LIMITED_API` is set on every
  interpreter and pyo3's `not(Py_LIMITED_API)` conversion modules — chrono among them —
  are cfg-removed, breaking the build on interpreters that never needed the flag; the
  failure impersonates gotcha 10's dependency drift (the pyvrl case).
- **537** — Gotcha 344 inverted: the stale maturin pin can live in upstream's own workflow
  step (`maturin-version: v1.7.1`) while `[build-system] requires` carries a harmless range,
  and the fix is to drop the input so `findReleaseFromManifest` resolves a release that ships
  riscv64 assets; plus a `bindings = "bin"` crate in a workspace subdirectory usually wants
  `working-directory:` rather than gotcha 312's write-a-pyproject-at-root step, and a linter
  CLI exits non-zero under its JSON reporter too (the squawk-cli case).
- **541** — `rustls` does not imply `aws-lc-sys`: when the tree resolves `ring` instead, riscv64
  needs no asm, no `cmake` and no perl — ring's `ASM_TARGETS` matches nothing and
  `include/ring-core/target.h` falls through `__LP64__` to `OPENSSL_64_BIT`/`OPENSSL_SMALL`
  portable C without reaching its `#error`, so grepping the crate for `riscv` (zero hits) reads
  as unsupported when it is supported by fallthrough; plus `pcre2-sys`'s `enable_jit()` is a
  deny-list that keeps a genuine riscv64 JIT (`sljitNativeRISCV_64.c`) on. The other half of
  gotcha 539: there `ring` was only a dev-dependency, here it survives the filter and is still
  not a blocker (the fastokens case).
- **539** — A Cargo workspace's root `Cargo.lock` can be dominated by a sibling crate's
  *dev*-dependencies (176 crates resolved for riscv64, 30 actually compiled), so gotcha 78's
  `cargo metadata --filter-platform` must also drop `{"dev"}`-only `dep_kinds` edges before the
  graph describes what the wheel builds — read unfiltered, it manufactures a ring/tokio-shaped
  blocker no `maturin build` ever reaches (the chonkie-core case).
- **551** — A "`<tool>-format`"/"`<tool>` bindings" package's implied runtime dependency on
  `<tool>` itself is not real when the binding is PyO3/maturin pulling the underlying crates as
  git dependencies straight from upstream's own repo — check `Cargo.toml`'s `[dependencies]`
  table for a `git = "https://github.com/..."` source with no matching PyPI `Requires-Dist`,
  not the crate names, before treating the CLI tool's own riscv64 status as a blocker
  (the ruff-format case).
- **555** — Gotcha 181's unconditional `abi3-pyNN` feature has no `MATURIN_PEP517_ARGS`/
  `--py-limited-api` knob to retag with when `NN` names an interpreter the riscv64 image
  doesn't ship at all — the tag comes straight from the Cargo feature regardless of which
  interpreter compiles it, so the fix is a one-line source patch bumping the feature to the
  image's real floor (`abi3-py38` → `abi3-py39`), verified locally with `cargo check` plus
  a `maturin build --release` whose printed floor and wheel filename both track the patch
  (the baseten-performance-client case).

### Bazel & driving the build container — [`gotchas/native-build-bazel-and-drivers.md`](gotchas/native-build-bazel-and-drivers.md)

- **8** — Pin Bazel to a version that actually exists.
- **15** — Heavy C++ ports: drive the build container yourself, build the C++ once.
- **47** — A bazel-built project on riscv64: there is no bazel binary, so bootstrap one
- **69** — Looping interpreters inside one bazel output base: a repository rule re-runs
- **95** — OCaml/opam projects are ordinary ports — but the manylinux image is the wrong
- **131** — A bzlmod project that gets its Python deps from `rules_python`'s pip extension
- **132** — Google's ML Bazel stack (XLA/TSL/jax/TensorFlow) already carries riscv64 config
- **133** — bazel 7.x pins the same rules_python/rules_java across the whole minor series, so
- **136** — Upstream builds its wheels in a vcpkg image: replace the image, keep the workflow
- **142** — cibuildwheel copies the
- **202** — A monorepo's "regenerate deps from Bazel" helper may already tolerate a missing
- **219** — GDAL's cmake build produces no `gdal-config` script — a second consumer of the
- **233** — A package can have no Python build backend at all — the wheel comes from an
- **397** — A CMake build that shells out to a bare `python3` for one vendored sub-extension
  silently builds it for the container's default interpreter, not the one the wheel is for
  (the coremltools/kmeans1d case).
- **421** — `pierotofy/set-swap-space` is a no-op on the riscv64 runners (`/` is overlayfs, so
  `swapon` fails and the action soft-passes): a heavy link gets 15GB of RAM and nothing behind
  it.
- **423** — A depot_tools/gclient checkout (V8/Chromium/Skia) downloads no `dep_type: 'gcs'`
  dependency and runs no `download_from_google_storage` hook on riscv64 until
  `VPYTHON_BYPASS` is set — gsutil's vpython venv pins `crcmod==1.7+chromium.4`, which has no
  riscv64 wheel; the cipd-bootstrap error in the same log is a relative-path red herring.
- **424** — Audit a chromium-style DEPS for riscv64-less CIPD packages with
  `cipd describe <pkg>/linux-riscv64` (and `gclient_eval.EvaluateCondition`) before spending a
  build cycle discovering them one abort at a time.
- **427** — `VPYTHON_BYPASS` also picks the interpreter gsutil runs on, and a chromium-style
  checkout holds two gsutils: the one its DEPS pins (4.68, vendoring six 1.12) cannot import on
  python ≥ 3.12, so its `download_from_google_storage` hooks fail — reproducible on x86 in
  seconds, fixed by conditioning those test-data hooks off.
- **432** — A monorepo that vendors C++ deps as submodules and has its CMake "fix up" their
  versions with `git checkout <tag>` builds the stale recorded commit in CI: `actions/checkout`
  clones submodules without tags, so the checkout fails (`error: pathspec '<tag>' did not
  match`) and is never checked — move the submodule to the tag from the workflow.
- **434** — Under `EXTERNAL_PROJECT_LOG_ARGS`/`LOG_CONFIGURE 1` a failed `ExternalProject`
  prints only `Command failed: 1`, with the real diagnostic in a stamp log that dies with the
  runner — add an `if: failure()` step that tails
  `build/third_party/*/src/*-stamp/*-*-*.log`.
- **437** — The same `git checkout <tag>` in an `ExternalProject_Add` `PATCH_COMMAND` aborts
  the build instead of building the stale tree quietly; check the gitlink against the tag
  (usually equal, so only the ref is missing — `git fetch --depth 1 origin tag <tag>`), and
  sweep every `cmake/external/*.cmake` at once, splitting `*_TAG` names from SHAs.
- **440** — Gotcha 133's version-only bazel cache key is shared repo-wide, so a new
  workflow's bootstrap step is skipped on its first run and a broken variable reference in a
  copied bootstrap stays latent — check every `${VAR}` against the `docker run -e` list.
- **441** — `VPYTHON_BYPASS` (gotcha 423) also takes `gclient.py`'s own vpython venv away, so
  depot_tools' imports must be on the ambient interpreter: `pip install httplib2==0.13.1`
  (unpinned drops the `httplib2.socks` gerrit_util needs), and nothing else is missing.
- **443** — An upstream CMake per-arch block can `set(<OPT> OFF CACHE ... FORCE)` *after*
  `include(third_party)` already ran the matching `add_definitions()`, so the feature is
  compiled in and not linked — check the include line numbers and use the project's own
  early default switch instead.
- **445** — Companion to 424: a `.gclient` `custom_deps: None` drops a *git* dep and is
  silently ignored for a `cipd` one, so a riscv64-less CIPD package survives into the
  `cipd ensure` that ends `gclient sync` — edit the checkout's `DEPS` instead, and add
  `use_siso=false` to the gn args when siso is one of them.
- **451** — bazel 7.7.0/7.7.1 cannot be bootstrapped from source on any architecture: they
  are the first 7.x releases whose `MODULE.bazel` reaches `bazel_features`, which reads the
  version-less bootstrap binary as newer than bazel 8 and generates a `globals.bzl`
  re-exporting `macro()`. Bootstrap 7.5.0; an upstream `.bazelversion` is bazelisk's file,
  not a gate.
- **456** — A per-interpreter loop in one bazel output base amortizes nothing when the build
  is reconfigured per interpreter (tensorstore: 5 x 5h35), and the job that overruns
  `timeout-minutes` is reported as `cancelled`, not `failed`. Matrix the interpreters.
- **477** — A CMake SuperBuild forwards only a whitelist of variable *names* into its nested
  ExternalProjects, so `-D<vendored dep option>` on the top-level line reaches nothing and no
  warning says so; prove the forwarding off-target by grepping the child's
  `CMakeCacheInit.txt` (the simpleitk/ITK/zlib-ng `WITH_RVV` case).
- **493** — cmeel's own `-DCMAKE_INSTALL_LIBDIR=lib` does not reach an `ExternalProject_Add`
  child, so a cmeel distribution that delegates its whole build to one ships into
  `cmeel.prefix/lib64/` rather than `lib/`; read the released wheel's namelist, not the sibling
  workflow (the cmeel-zlib case, and the mechanism behind gotcha 492).
- **494** — A hermetic Python predating riscv64 is a *two*-repository problem — Python headers
  and numpy headers both come from it — and in a WORKSPACE tree `--override_repository` over two
  run-time-written repos settles it with no patch (the tflite-runtime/TensorFlow 2.14 case).
- **497** — Drive an upstream build script through the env hooks it already exposes
  (`CUSTOM_BAZEL_FLAGS`, `BAZEL_STARTUP_OPTIONS`), and use the fact that the later flag wins to
  cancel one it hardcodes, such as `-s`.
- **500** — Gotcha 233's packer-script shape, cheap variant: when the packer is *upstream's
  own* and takes locally built binaries (`--files austin:src/austin`), the port is a
  from-source build plus a one-entry platform-table patch (the austin-dist case).
- **563** — A CMake macro (`add_go_lib()`) that shells out to `go build -buildmode=c-shared`
  in a driven-container port (no cibuildwheel) needs `git config --global --add
  safe.directory` for `-buildvcs=true`'s VCS stamping against the bind-mounted checkout,
  `chmod` on any binary it writes while still root (a later unprivileged host step can't), and
  the package's own `[test]` extra typed out by hand since there is no `CIBW_TEST_EXTRAS`
  (the adbc-driver-flightsql case).
- **567** — Installing clang for gotcha 132's `--config=clang_local` is not enough by
  itself: without `CC`/`CXX` exported, Bazel's local toolchain autodetection still picks
  plain `gcc`, and `com_google_highway`'s unconditional riscv64
  `-menable-experimental-extensions` copt (Clang-only, no GCC equivalent) is the target
  that finally exposes it (the xprof case).
- **573** — `gn gen` evaluates every `BUILD.gn` any root target reaches, `gn_check`/test
  groups included, so a forked file's `assert(false, "Unsupported target CPU riscv64")`
  blocks a cross-build of a library that never links it (PDFium's `skia/BUILD.gn` via
  `group("gn_check")`). Read the "which caused the file to be included" line, diff the fork
  against Chromium's copy (which has an empty riscv64 branch) and carry that as a patch
  (the liteparse/pdfium case).
- **575** — `--config=clang_local` also drops the hermetic linker: without `lld` installed,
  Bazel's `local_config_cc` probe falls back to GNU `ld`, so an upstream `-Wl,--icf=all`
  (lld/gold-only; gold has no riscv64) fails at the final `CppLink` hours in. `dnf install
  lld` next to `clang` and Bazel adds `-fuse-ld=lld` itself (the xprof case).

### The manylinux image & toolchain — [`gotchas/manylinux-image-and-toolchain.md`](gotchas/manylinux-image-and-toolchain.md)

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
- **243** — The `manylinux_2_39_riscv64` container's IPv6 loopback binds but can't send:
- **250** — A vendored C library's strict-aliasing UB can miscompile *silently* under a
- **252** — Rocky 10 (the riscv64 manylinux image's base) names the Wayland client
- **257** — `CMAKE_POLICY_VERSION_MINIMUM` also works as an environment variable, not just a
- **267** — A vendored C++ library's own architecture-dispatch macro (not a SIMD gate,
- **271** — `AVIF_CODEC_AOM_DECODE=OFF` and `-DCONFIG_AV1_HIGHBITDEPTH=0` are a normal
- **272** — A riscv64 project's own `getauxval(AT_HWCAP)` runtime dispatch can still
- **279** — Gotcha 272's zlib-ng `vsetvli` SIGILL recurs whenever a *second*, independent
- **288** — Rocky/AlmaLinux 10 dropped the classic SDL2-devel package entirely, on every
- **289** — A CMake `ExternalProject_Add` patch step can shell out to `wget`, which the
- **294** — An upstream CMakeLists' own `-fPIC` allowlist can name only `x86_64`/`aarch64`,
- **327** — A project's own `before-all`/`before-build` can already "fix" gotcha 138's
- **328** — A vendored SIMD library with no portable/generic implementation at all can
- **332** — A SIMDe SSE-emulation port can compile clean, pass its own project's
- **333** — A vendored C++ library's architecture-fallback stub can have a genuinely
- **337** — lexbor, re2 and uchardet are absent from Rocky 10's baseos/appstream/crb on
- **351** — A project's own build script can gate a sibling vendored library's SIMD
  macros on `platform.machine() != "ppc64le"`, assuming "not ppc64le" means "x86 or ARM".
- **358** — `dnf`/`apk` installing an older cmake to satisfy gotcha 257 doesn't necessarily
  make it the one that runs: both manylinux and musllinux riscv64 images carry a
  pipx-installed cmake >= 4 earlier on `PATH` by default.
- **359** — A CMake project forked from old LLVM sources can validate the host
  architecture through two independent mechanisms — the vendored `utils/llvm-build`
  Python tool has its own separate check and its own escape hatch.
- **374** — `find_package(Python3 REQUIRED COMPONENTS Interpreter Development)` fails on
  manylinux's static-libpython CPython, on any architecture — only `Development.Module`
  is ever needed to build an extension module, not the `Development.Embed` half.
- **377** — Rocky's `lib64` `GNUInstallDirs` default can make a hardcoded `"lib"`
  packaging check silently drop the one compiled library a split-package wheel exists
  to ship, on any Rocky-based manylinux arch, not just riscv64.
- **378** — A newer libstdc++ on the manylinux image can deprecate calls a project's own
  `-DCMAKE_COMPILE_WARNING_AS_ERROR=ON` CI flag then turns into hard errors, purely from
  a toolchain-version gap upstream's own (older) runners never see.
- **390** — libev is one of the `-devel` packages that *is* in Rocky 10's riscv64 repos, so an
  upstream `yum install -y libev libev-devel` needs no replacement — but its header is
  `/usr/include/ev.h`.
- **401** — Rocky 10 riscv64 ships OpenBLAS, LAPACK and FFTW but no SuiteSparse, GSL or
  GLPK, and a numeric package's optional-extension set has to be cut along that line
  (Alpine riscv64 has all of them, but ships no licence texts).
- **420** — Gotcha 139's binutils-too-old trap recurs inside a Bazel dependency's microkernel
  library (XNNPACK's `zvfh` kernels), where the fix is that dependency's own feature
  `--define` rather than an `-march` probe — and `--keep_going` hides a single-cause failure
  behind five hours of unrelated progress, making it look like a timeout.
- **428** — A project still on the deprecated `find_package(PythonLibs REQUIRED)` has no
  `Development.Module` way out of gotcha 374's static-libpython wall: satisfying it with
  manylinux's non-PIC `libpython3.XX.a` only moves the failure to the final link after hours,
  the project may already strip libpython from its own non-Windows link lines (making the
  `REQUIRED` vestigial), and the header-only fix rehearses locally on x86_64 in a minute.
- **435** — `libquadmath` does not exist on riscv64 or aarch64 — GCC builds it only where
  `__float128` differs from `long double`, so `dnf install libquadmath` fails outright. A project
  that copies it beside `libgfortran` unconditionally needs that copy made conditional; and never
  pad a `dnf install` with unconfirmed runtime packages, since one bad name fails the transaction.
- **433** — OpenBLAS built from source stops at `getarch.c: #error "This arch/CPU is not
  supported by OpenBLAS."` on riscv64 whatever the version: its riscv64 definitions are reached
  only through `TARGET=`, so pass `TARGET=RISCV64_GENERIC` (the rv64gc baseline) as the twin of
  the `TARGET=ARMV8` the project already has — and first ask whether gotcha 401's Rocky
  `openblas` package would do.
- **446** — The image's free-threaded interpreter directory is `/opt/python/cp3XX-cp3XXt`
  (`<implementation tag>-<ABI tag>`), not `cp3XXt-cp3XXt`, so a hand-written per-interpreter
  loop that doubles the `t` exits 127 — derive it as `${TAG%t}-${TAG}`, and confirm any
  `/opt/python` path with a `grep` over the green workflows rather than a CI round.
- **447** — riscv64 forces a clang-only codebase (V8) onto GCC, and its source incompatibilities
  surface one translation unit per multi-hour build: take the fix from a later upstream release
  rather than inventing one, kill the warning class wholesale with
  `treat_warnings_as_errors=false`, sweep the rest of the bug class out of the arch-specific
  sources off-target, and run `ninja -k` until the class is closed.
- **448** — "Genuine upstream riscv64 support" can still mean "requires RVV 1.0 hardware": openvino
  built for 12h18m, produced all four wheels, then died 2m12s into the test step with exit 132
  (SIGILL) inside `ov.Core()` — its CPU plugin is the only library in the wheel whose
  `Tag_RISCV_arch` carries `v1p0`, with 64,554 vector instructions against zero in the other 19,
  and upstream's own riscv64 CI only ever tests under `qemu -cpu rv64,v=true,vext_spec=v1.0`, so
  read the artifact's ELF attributes rather than trusting the upstream CI's existence. **Corrected
  by a later round in the same entry**: the vector code traced to oneDNN's own unconditional
  `-march=rv64gcv` (a real off switch exists, `-DCAN_COMPILE_RVV_INTRINSICS=OFF`), not to the
  plugin's own riscv64 kernel/emitter objects or to the runtime probe's SIGILL recovery failing —
  confirmed by reproducing under QEMU with vector support toggled off and pinning the exact
  faulting instruction, after a first fix landed on the wrong hypothesis.
- **454** — The image's LLVM is a whole toolchain *minus Clang's static libraries*: `llvm-static`
  installs 304 `libLLVM*.a`, `clang-devel` installs none, so a project that links Clang statically
  has to build LLVM+Clang from source (the warp-lang case).
- **455** — Rocky 10's zlib is `zlib-ng-compat`, whose CMake package config names a `libz.a` only
  the `-static` subpackage installs, so a *lowercase* `find_package(zlib)` hard-errors on the
  riscv64 image; `-DCMAKE_DISABLE_FIND_PACKAGE_zlib=ON` routes the project back to its own
  `find_library` fallback (the pulsar-client case).
- **460** — An upstream Dockerfile's `apt-get install` line is a build-dependency manifest
  nothing else in the tree declares: translate its `-dev` packages to Rocky names before the
  first run, or the image's missing header stops the compile (the vllm `numa.h` case).
- **485** — CMake's `find_package(Python3 COMPONENTS Development)` cannot configure in the
  manylinux image because PEP 513 forbids shipping `libpython`; the fix is a zero-byte file at
  the path FindPython validates, and upstream probably already carries it (the usd-core case).
- **496** — Gotcha 420's XNNPACK fp16 define does not belong in an older tree: at a 2023 pin the
  riscv64 *production* microkernels are scalar-only and every RVV gate sits in a bench/test
  target, so attribute each `riscv` line to its target before adding a define.
- **499** — `-lfoo` and `-l:libfoo.a` are different questions: Rocky's binutils-devel ships
  `libiberty.a`/`libsframe.a` with no shared twin (probe passes, static link works) while
  xz-devel ships only `liblzma.so`, so an unconditional `-l:liblzma.a` fails; `demangle.h`
  also sits outside `libiberty/` there (the austin-dist case).
- **515** — Gotcha 46's minimal perl also breaks a package that shells out to perl at
  *runtime*: the wheel builds and the tests then die on a missing `Safe.pm`, so the fix is
  `CIBW_BEFORE_TEST: dnf -y install perl-Safe` (the systemrdl-compiler case).
- **525** — The image's GCC 14 makes implicit-function-declaration/implicit-int/int-conversion
  hard errors and `-w` cannot suppress them; OpenBLAS's generated prototype-less `linktest.c` is
  the usual first casualty, fixed through `COMMON_OPT` (never a command-line `CFLAGS=`), and a
  `-fsyntax-only` sweep predicts the whole tree in a minute (the vosk case).
- **526** — An asymmetry between two upstream invocations of the same command is load-bearing
  until proven otherwise: vosk's `ONLY_CBLAS=1` on `all` but not `install` is what installs
  `lapacke.h`, and normalising the two lines broke Kaldi eleven minutes in (the vosk case).
- **543** — A distro `-devel` package pulled in as a dependency (e.g. `jasper-devel` needing
  `libjpeg-turbo-devel`) can leave a stale multilib `jconfig-64.h` that CMake's `FindJPEG` glob
  reads before a from-source libjpeg-turbo's own `jconfig.h`, silently reporting the distro's
  older `JPEG_LIB_VERSION` (the rawpy case); `rm -f jconfig-{32,64}.h` after the custom install.
- **548** — `-Wcast-align` under `-Werror` is a latent riscv64-only wall for any C++ project
  that decodes a wire protocol out of a byte buffer, because GCC emits it only on
  strict-alignment targets and upstream's x86_64/aarch64 CI never sees it; `CXXFLAGS` cannot
  undo it, so demote it in the project's own warning CMake (the couchbase case).
- **576** — Rocky 10's `libjpeg-turbo-devel` CMake config declares `libjpeg-turbo::turbojpeg`
  but that library ships in the separate CRB `turbojpeg` package, so any
  `find_package(libjpeg-turbo)` (OpenImageIO's included) fails at configure until `turbojpeg` is
  installed too (the pycolmap case).

### Native dependencies & linking — [`gotchas/native-deps-and-linking.md`](gotchas/native-deps-and-linking.md)

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
- **278** — A vendored, direct-copy (not submodule) header can be missing riscv64 from its
- **363** — A `libraries=[...]` entry can go missing from the link line with *no* error —
- **368** — Linking several codecs against Rocky 10's system libraries instead of
- **395** — When a project dlopen()s a differently-named shared library per major
- **400** — A `setup.py` knob that feeds a downloaded dependency's *sources* into
  `Extension(sources=...)` needs a path relative to the project root, so the tarball has
  to be extracted inside the checkout, not into `/tmp`.
- **415** — Turning an optional native codec OFF can select a stub whose signature has
  drifted from its declaration; the ELF links anyway and the first `dlopen` is where it
  dies.
- **461** — A dependency wheel *shipping* a library is not a promise that it exports the symbol
  a build gates on: a presence-of-file probe must become a presence-of-symbol probe, or the
  extension links clean and fails at import (the vllm/OpenBLAS `sbgemm_` case).
- **463** — Substituting our dep wheel for an upstream prebuilt can change the SONAME: when the
  package's own linker-flag emitter says `-l<name>`, re-soname the staged copy instead of
  shipping a symlink farm (the sherpa-onnx-core/onnxruntime case).
- **486** — Legacy TBB 2020.x (the hand-written makefile build, not oneTBB's CMake one) needs no
  riscv64 patch — `uname -m` fallback, `findstring 64` export prefix, generic GCC atomics — so
  do not switch a project to `--onetbb` on suspicion (the usd-core case).
- **547** — A vendored BoringSSL produced by `generate_build_files.py` needs no
  `OPENSSL_NO_ASM` on an architecture its CMake does not list: every generated `.S` is
  self-guarded on `OPENSSL_X86_64`/`OPENSSL_AARCH64` and `crypto/` picks its portable C off the
  same macros — check `target.h` for `OPENSSL_RISCV64`, then assert the backend from the built
  wheel (the couchbase case).
- **550** — When a vendored downloader's unknown-platform branch is a graceful PATH search
  rather than a hard failure, gotcha 77's patch is unnecessary — build the binary yourself and
  drop it on `PATH` in `CIBW_BEFORE_BUILD` (the shfmt-py case).
- **554** — When the *wheel-building tool itself* (not a downloader) lacks riscv64 in its own
  hardcoded platform table, import it and extend the table in a `run:` step instead of
  patching it — and check separately whether it embeds a LICENSE at all (the mcp-grafana /
  go-to-wheel case).

### Compiled-vs-pure detection & the require-extension knob — [`gotchas/compiled-vs-pure-detection.md`](gotchas/compiled-vs-pure-detection.md)

- **19** — mypyc-compiled wheels behind a `flit_core` pyproject (the tomli pattern; see
- **20** — Optional C extensions silently degrade to a mislabeled pure-Python wheel
- **28** — mypyc-by-default is the other half of gotcha 19 — verify the `.so`, don't add
- **33** — Not every `.so` in a wheel is an extension module — some are ctypes/cffi-loaded *(reused number — this theme)*
- **49** — Before injecting gotcha 20's `REQUIRE_*_EXT` knob, check whether upstream already
- **56** — The module a compiled package exposes under a private-looking name is often a *(reused number — this theme)*
- **91** — An optional C extension whose *release predates the interpreters we build* silently
- **127** — A C extension that does not declare free-threading support turns upstream's
- **129** — Copying upstream's require-extension env var verbatim ships a degraded wheel —
- **55** — A `cffi_modules` project is a normal port, and cffi itself is registry-only on *(reused number — this theme)*
- **280** — When there's no require-extension knob to force (gotcha 91's shape), check
- **292** — Gotcha 81's "diff the wheel `size` field" test can pass on a real per-arch binary
- **295** — A require-extension knob that reaches the container correctly (gotcha 129's
- **308** — A maturin shim whose star-import name collides with the compiled submodule's
- **559** — A pure-Rust maturin project's top-level `__file__` never points at the `.so` —
- **398** — Reproducing a `py3-none-<platform>` wheel takes an explicit retag — setuptools'
- **457** — On cp314t our registry can hand a package a *compiled* dependency wheel where
- **510** — A cffi *ABI-mode* payload keeps its `py3-none` tag through `auditwheel repair` —

### Dependencies & the registry — [`gotchas/dependencies-and-registry.md`](gotchas/dependencies-and-registry.md)

- **30** — Check our own registry before dropping a dependency as "no riscv64 wheel".
- **55** — A pure-Python test dependency can go binary mid-stream, and free-threaded x riscv64 *(reused number — this theme)*
- **67** — A *build*-time dependency that we ship only for some interpreters caps the matrix
- **70** — `CIBW_TEST_EXTRAS` is a blunt instrument: an extra can drag in a *compiled*
- **84** — A build-only dependency that our registry ships for *some* interpreters caps the
- **90** — The committed `pyproject.toml` may be only one of several *variants* upstream
- **97** — A test dependency that went from pure Python to an abi3 extension strands the
- **122** — A runtime dependency with no riscv64 wheel *and no sdist* blocks cibuildwheel's wheel
- **125** — A dependency with no riscv64 wheel anywhere is only a blocker if it cannot build
- **149** — cp314t can be un-*testable* while staying perfectly buildable — skip its tests,
- **172** — An abi3 build compiles the wheel once but rebuilds the *test venv* per
- **200** — A monorepo sibling ported in a separate PR can pin `install_requires` to its own
- **210** — A test dependency our registry already carries as a wheel can still fail from
- **215** — A registry gap for one interpreter can be narrowed to just the one optional
- **232** — Matching upstream's newest interpreter tier can silently trade a fast port for a
- **234** — A stock distro `pip` can be too old to *recognize* a riscv64 manylinux wheel at
- **240** — A registry-hosted wheel that builds and installs cleanly can still be missing an
- **244** — `uv pip install` only honors `UV_*` env vars, never the `PIP_*` names — a step
- **291** — A `CIBW_TEST_REQUIRES` package with no riscv64 wheel of its own can still need
- **336** — A custom `CIBW_BEFORE_TEST` does not cancel a project's own `test-extras`
- **353** — Gotcha 30's registry check has moved off redirects: unhosted packages now
  answer plain `404`, not `302` — the check logic is unaffected, but scripts written
  against the old behavior may misread it.
- **354** — `PIP_PREFER_BINARY` (not `PIP_ONLY_BINARY`) is the fix when our registry
  hosts a wheel for only *some* matrix interpreters and an unpinned test dependency
  keeps resolving to a newer, wheel-less release.
- **375** — `uv` can reject a real `abi3` wheel resolved by name from an index as "has no
  usable wheels" even though the identical wheel installs fine as a local file.
- **399** — A dependency we already publish can satisfy a dependent's *runtime* link and still
  be unusable as its *build* input: a wheel ships `.so` files, not headers or a CMake package,
  and the upstream recipe's header source can be conda-forge (the cadquery-ocp/VTK case).
- **422** — A build container you drive yourself needs `PIP_EXTRA_INDEX_URL` on the *build*
  `podman run`, not only on the test one — otherwise its `pip install -r requirements.txt`
  source-builds numpy and dies on Pillow (the paddlepaddle case).
- **482** — `pypi.riseproject.dev/simple/<dep>/` is case-sensitive (a static GitHub Pages
  tree, no PEP 503 normalization), so gotcha 30/353's `curl` check and
  `queue_triage.py --deps` both report "not on RISE" for a package we publish whenever the
  dependency's PyPI spelling is not normalized — `PyYAML` 404s where `pyyaml` 200s; settle
  it with `check_riscv64_deps.py`, which drives pip.
- **488** — `PIP_ONLY_BINARY=:all:` in the test environment can silently *downgrade* a
  pure-Python dependency whose newer releases are sdist-only; the symptom is a failing test,
  not a resolution error, and the `:all:` + `PIP_NO_BINARY=<pkg>` escape hatch is
  order-dependent.
- **511** — An abi3-only *runtime* dependency is a permanent free-threading gap: abi3 never
  applies under `Py_GIL_DISABLED`, so no pin and no test-skip fixes it — read the
  dependency's wheel tags and drop `cp314t` before the first CI cycle.
- **574** — A bare `cpXY-*` `CIBW_BUILD` also builds musllinux in the same job, where
  `PIP_ONLY_BINARY=:all:` fails the test install on a dependency we ship for manylinux only
  (cffi, bitarray) — split on `libc` and gate only-binary per libc, naming only the sdist
  `:all:` was steering around.
- **577** — A musllinux leg that source-builds PyYAML (riscv64 wheels are manylinux-only)
  silently gets a pure-Python build with no `CSafeLoader` when libyaml headers are absent —
  `apk add yaml-dev` in `CIBW_BEFORE_TEST` on musllinux and set `PYYAML_FORCE_LIBYAML=1`.

### Build-tool drift & pins — [`gotchas/build-tool-drift-and-pins.md`](gotchas/build-tool-drift-and-pins.md)

- **23** — A floating *build tool* can break code the release-era tool compiled fine
- **29** — setuptools 82 deleted `pkg_resources`; any `setup.py` importing it breaks under
- **58** — Cython does publish a `py3-none-any` wheel, so it never compiles from sdist on riscv64
- **76** — A `build-system.requires` pin can exclude every riscv64 wheel of a build tool —
- **99** — setuptools 79 silently dropped `-shared` from distutils' C++ link, breaking build
- **112** — `PIP_CONSTRAINT` no longer reaches isolated build environments — pin build
- **118** — A pinned-old build *tool* and a floating build *dependency* are a two-sided
- **57** — `before-build` runs outside the isolated build env, so an upstream *(reused number — this theme)*
- **171** — A green wheel we publish can break a *different* package's build the moment it lands
- **175** — One `PIP_BUILD_CONSTRAINT` file covers the project's build tool *and* every
- **184** — `[tool.cibuildwheel] enable` is an enum, not a free-form list — a pinned older
- **211** — `pip install wheel` does not restore `distutils` on Python 3.12+ — only
- **222** — A dependency's own `build-system.requires` floor can be past the point its
- **225** — `wheel>=0.44.0` dropped `wheel.bdist_wheel.get_platform` — a hand-rolled
- **256** — setuptools 81 dropped the `dry_run` keyword from its vendored
- **269** — A project's own `build-system.requires` floor can be looser than what its
- **277** — A CMake-backed `pyproject.toml` build dependency with no upper bound can still be
- **346** — The `clang` PyPI package gained a `File.__eq__` with no matching `__hash__` in the
- **361** — Gotcha 29's `pkg_resources` removal also bites `CIBW_TEST_REQUIRES`, not just a
- **367** — A `setup.py`'s own "distributor customization" import hook can go silently

### Testing: test-sources & shadowing — [`gotchas/testing-and-shadowing.md`](gotchas/testing-and-shadowing.md)

- **21** — `python -s` (no-user-site) does NOT propagate to pytest-xdist workers.
- **25** — Build-from-checkout + pytest = the repo's source package shadows the wheel you
- **36** — `test-sources` preserves each path's position relative to the project root —
- **39** — Testing a unittest-native suite against the installed wheel: three traps past
- **83** — A test that asserts on a traceback's *source text* passes only inside a source
- **87** — A test module that force-registers a synthetic package can never test an installed
- **104** — `test-sources` is resolved against cibuildwheel's *cwd*, not against
- **111** — A build product made *inside* the container never reaches `test_cwd` — the trap side
- **119** — A local `test-sources` rehearsal lies if any ancestor of your staging dir holds a
- **148** — The test suite lives *inside* the importable package, so `test-sources` cannot
- **151** — A test runner that *discovers* work by walking `<testdir>/..` fails silently, not
- **152** — An sdist's `tests/` directory can be a partial copy — count the files before you
- **174** — A `<pkg>/` directory at the checkout root is only a shadowing hazard when it holds
- **218** — Gotcha 25's shadowing condition ("suite is a package") has a second, independent
- **229** — A test suite that calls GitPython's `Repo(..., search_parent_directories=True)`
- **253** — A ctypes/dlopen GUI-toolkit wrapper with no upstream pytest suite at all still has
- **296** — Upstream test fixtures checked in via git-lfs can't assume the self-hosted
- **329** — A test suite that shells out to the package's own installed CLI binaries at a
- **347** — A test that asserts "you're running against an editable/in-place install" can
- **348** — A `glcontext`-based package's `create_context(standalone=True)` defaults to the
- **389** — A test `.pyx` that Cython-`include`s a checkout-root-relative path can be satisfied by
  staging just those files; a staged package dir with no `__init__.py` is a namespace
  portion and does not shadow the wheel.
- **501** — A separate test job checks the upstream tree out again and needs the same
  `git apply` the build job has; the tell is a failure returning byte-for-byte after you
  fixed it (the austin-dist case).
- **513** — The wheel ships the tests but not the `<pkg>.tests` helpers they import: stage the
  helper modules with `test-sources` and copy them into the installed package from
  `test-command` (the pytype case).

### Testing: pytest config, servers & test selection — [`gotchas/pytest-config-servers-and-selection.md`](gotchas/pytest-config-servers-and-selection.md)

- **6** — Running a real test suite through cibuildwheel:
- **48** — A package whose runtime dependency tree doesn't exist on riscv64 is still
- **64** — A daemon that refuses to run as root is usually a packaging question, not a patch
- **74** — A file capability makes a binary unexecutable inside the build container
- **75** — Running upstream's suite against a real server the distro also ships is often
- **82** — A `pytest.skip()` raised from inside the generator that feeds `@parametrize`
- **88** — An upstream `CIBW_TEST_COMMAND` that shells out to `tox` has to be translated, not
- **92** — A root `conftest.py` that imports the world is optional — `test-sources` decides
- **94** — Upstream's wheel jobs testing nothing is not a reason to ship an import-only
- **108** — A `test-command` carrying `-W error` needs the project's pytest ini staged, or
- **109** — A dry run on a networked host cannot tell you which tests "need no server" — run
- **110** — A conftest that `pytest.exit()`s on a missing credential env var hides the
- **128** — A release tag's test suite may never have been run by upstream CI — check the
- **144** — A compiled "speedups" package: don't differential-test it against the pure-Python
- **176** — `log_level` is the third pytest ini key that decides whether a staged suite passes,
- **177** — Narrowing an upstream test suite because its heavy requirements file has no
- **212** — An unavailable optional dependency (no riscv64 wheel) doesn't only fail tests
- **241** — A dry run against upstream's *released* wheel (gotcha 52) settles whether a
- **264** — Gotcha 94's "is the service packaged for riscv64" check needs a pin, not just a
- **307** — A release whose own official wheels are generated by a patched, pinned SWIG
- **321** — When the excluded boundary is a whole submodule reachable by name, stub its
- **339** — An unpinned `pytest` in `CIBW_TEST_REQUIRES` can resolve to a pytest new enough
- **350** — A suite's own `try: import X except ImportError: X = None` plus
- **355** — Gotcha 339 generalizes past `pytest` to any unpinned runtime dependency whose
  own heuristic changed across a major version — pin it for the test venv only.
- **429** — A media project's suite is written against upstream's *full* FFmpeg; an FFmpeg
  you configure yourself has no H.264/HEVC/VP9/AV1/MP3 encoder at all, and the failures
  blame the wrong codec.
- **439** — A Bazel project runs one process per `py_test` target, so one `pytest --pyargs`
  over the whole package invents failures: run each file as its own absltest script, and take
  the `env`/`args` from the `py_test` rules (per-target, not globally).
- **489** — A hundreds-of-MB upstream test-data tree can be left out of the checkout with
  non-cone sparse-checkout (which also switches `actions/checkout` to a `blob:none` clone),
  and the suite selected as the complement of the modules that grep for the data constant.
- **512** — `--ignore`/`--ignore-glob` are silently inert under `pytest --pyargs <pkg>`; cut
  tests with `--deselect`, whose nodeids are relative to the package directory rather than the
  rootdir pytest prints, and confirm the count with `--co -q`.
- **565** — A crashed `multiprocessing.Process` child's parent blocking forever on
  `Queue.get()` with no timeout turns one segfault into a full job hang; bound it with
  `CIBW_TEST_REQUIRES: pytest-timeout` plus `PYTEST_ADDOPTS="--timeout=<n>"` folded into
  `CIBW_ENVIRONMENT`, which applies to both the build and test phases.

### Test failures, flakes & arch-specific bugs — [`gotchas/test-failures-and-flakes.md`](gotchas/test-failures-and-flakes.md)

- **14** — torch-dependent tests flake two ways on the riscv runner — deselect, don't chase.
- **33** — One green interpreter beside identically-failing others is a CPython feature *(reused number — this theme)*
- **37** — pytest-xdist's controller can SIGSEGV under the free-threaded interpreter;
- **38** — A slow runner turns a latent test race into a hard failure — simulate the
- **60** — A SIGSEGV in a port's test run is usually an ordinary upstream refcount bug —
- **61** — A callback that stays armed past the assertion fires again during teardown (the
- **115** — A SIGSEGV that will not reproduce off the runner: get the native backtrace *in CI*
- **120** — Hypothesis' `too_slow` health check is a wall-clock budget on *input generation*,
- **164** — A test helper with a per-architecture syscall table falls back to a fixed sleep on
- **166** — The riscv64 runners' libgomp faults on the `dynamic` and `guided` OpenMP
- **167** — A riscv64-only intermittent SIGSEGV: climb the control ladder before you debug
- **168** — Running a diagnostic on the riscv64 runner: drive it from `CIBW_TEST_COMMAND`, and
- **169** — `astral-sh/setup-uv` hands you a python-build-standalone interpreter, and PBS links
- **170** — `np.linalg.eig` on a symmetric matrix returns *real* eigenvalues on x86_64 and
- **205** — A follow-up commit that fixes a broken `Upstream-Status:` line does not clear
- **282** — A matplotlib `image_comparison` test failing only on riscv64 is a font-rendering
- **283** — A `cp314t`-only `PicklingError` from a `multiprocessing.Process(target=<local
- **285** — A heap-corruption abort in a vendored C++ library's concurrent stress test can
- **286** — A vendored-ARPACK eigensolver test failing only on musllinux, not manylinux, can
- **290** — A `NameError` in an e2e test for a name the package genuinely exports is a
- **297** — A test harness's own unbounded `readline()`-until-marker wait turns any slow or
- **304** — A hardcoded exact-equality assertion on a neural-network/matmul-heavy
- **316** — A hardcoded timing threshold on a metric that measures raw wall-clock GIL-acquire
- **317** — A pure-Python, allocation-heavy test suite running ~8x slower on musllinux
- **323** — Gotcha 127's GIL-reenable safety net only rules out concurrency races — a
- **330** — A manylinux image's system library can be years newer than what upstream ever
- **362** — A `multiprocessing.Process().join()` regression test for a native threadpool's
- **379** — A test asserting a specific cross-thread ordering (a `gc.collect()`-on-one-
  thread-finalizes-an-object-another-thread-observes shape) can fail deterministically,
  only on `cp314t`, with no riscv64 or correctness bug behind it — free-threaded
  CPython's deferred reference counting doesn't guarantee the ordering GIL-serialized
  builds do.
- **416** — A conftest-time `ImportError` is reported by pytest *without* the exception
  chain, so a `dlopen` failure reaches the log stripped of its cause.
- **414** — A stochastic test whose native RNG is seeded from `time(NULL)` is a wall-clock
  lottery, not an arch or libc difference — replay consecutive epoch seconds through the
  library's own seed setter to measure the real failure rate.
- **472** — A project's own runner buffers each module's output, so a hang or SIGSEGV
  loses the test's identity — `python -u` names the module, `python -X faulthandler -m
  unittest -v <module>` names the test, and a subprocess-per-test sweep names them all.
- **473** — A `faulthandler.dump_traceback_later(..., exit=True)` watchdog stops at the
  first bad test, so it never proves the rest of the module is clean.
- **474** — Before skipping tests your build's missing backends fail, look for the
  system-dependency marker upstream already honours (`PG_DEPS_FROM_SYSTEM` and friends) —
  it usually exists, and usually needs extending to its siblings rather than replacing.
- **502** — One binary of a multi-binary wheel can be unshippable while the others pass
  everything: austinp segfaults on riscv64 in austin's own MOJO emitter and inside
  libunwind's riscv64 symbol lookup, so the wheel ships `austin` alone — the shape
  upstream's own musllinux wheels already have (the austin-dist case).
- **504** — A discrete wrong count, not a last-ULP value, can still be floating point:
  `-ffp-contract=fast` fuses `a*b+c` into an FMA on riscv64 and moves quantised coordinates
  into other buckets; reproduce it on x86 with `-march=haswell` (the cmeel-octomap case).
- **507** — A SIGSEGV out of a hand-written `ctypes` smoke test is usually the test's own
  declaration — `c_char_p.in_dll` on a C char array dereferences the string's first bytes as
  a pointer, and a call with no `restype`/`argtypes` returns garbage; reproduce on x86 first.
- **519** — A mass upstream-test failure is upstream's defect, not the port's, when the
  vendor's own released x86_64 wheel fails the same suite: prove it with one
  `pip install --only-binary :all: <pkg>==<ver>`, bisect across sibling distributions, then
  ship a functional smoke test instead of a half-suite deselect list (the fasttext-numpy2 case).
- **535** — A release tag can ship tests its own source does not satisfy: diff the failing
  test against upstream's post-release `master`, and `git cherry-pick -x` the fix that
  landed after the tag was cut into an `Upstream-Status: Backport` patch (the
  scylla-driver 3.29.11 case).
- **545** — *(retracted, see 552)* A source-only root-cause theory that reads convincingly
  is still a theory — confirm it against a fresh CI run on the target architecture before
  calling it fixed (the umf 1.1.0 IPC case; the padding/`memcmp()` theory this entry
  originally documented did not apply to the actual failing line).
- **552** — Docker's default seccomp profile blocks `pidfd_getfd(2)` with `EPERM` unless the
  container has `CAP_SYS_PTRACE`, even for a process duplicating a fd of its own — the real
  cause of the failure gotcha 545 misdiagnosed (the umf 1.1.0 IPC case).
- **553** — A SIGBUS in a doubly-nested tracking-provider pool stack's aligned-allocation
  path is real but unresolved on riscv64 without hardware to reproduce interactively, and is
  not threading-specific even though it first looked that way (the umf 1.1.0 case).
- **566** — A from-source compiled binary segfaulting on *every* invocation across
  independent runners (pgserver's `initdb`, PostgreSQL 16.2, plain `-O2`/GCC 14.3.1) is real
  and unresolved without riscv64 hardware to debug interactively — not scenario-specific to
  whichever test happened to be running, and distinct from an already-open pgsql-hackers
  riscv64/GCC memory-failures thread (that one is sporadic; this one is deterministic).
- **568** — A subprocess-exit self-test's hardcoded `TIMEOUT` failing only on `cp314t` for
  one version, with byte-identical test source and no relevant code change across versions,
  is free-threading's per-object overhead tipping an existing margin on a shared riscv64
  runner (awscrt 0.37.0's `test_appexit`) — patch the timeout with headroom, don't skip the
  test that proves the extension doesn't crash the interpreter on exit.
- **570** — A hardcoded `sys.getrefcount()` baseline is an interpreter-version contract, not
  a fixed constant — CPython 3.14's `LOAD_FAST_BORROW` optimization lowers it by one per
  affected call site (stpyv8's `testReferenceCount`, cp314 only) — branch the expected value
  on `sys.version_info`, don't skip the test. Also: a cache key over a whole patches
  directory pays a rebuild for changes the cached step can't have read from — key it on only
  the files that step actually applies.
- **571** — A test that hangs only on free-threaded CPython (cp314t), intermittently, and
  only on some releases of the same package (awscrt's `test_stream_lives_until_complete_*`,
  0.36.3/0.36.4) is a deferred-object-freeing race in the test, not a riscv64 bug: freeing an
  object whose last reference was dropped on a native thread is deferred under free-threading
  until some thread next runs Python bytecode, so a test that drops the reference then
  immediately blocks the main thread on that object's side effect (a socket it owns closing)
  can deadlock forever. Fix the test to wait for the object to actually free before blocking;
  don't drop cp314t from the matrix — free-threading support is real in these releases.
- **572** — This fleet's riscv64 cores are Sv39-only, a real ~256GB ceiling on one process's
  virtual address space — a database/allocator that reserves a huge range up front on the
  "virtual memory is free" assumption (kuzu's `Database()` defaulting to an 8TB `mmap`) fails
  outright here, not just slowly. Reproduces identically on x86_64 under `ulimit -v 256GB`, so
  it's this fleet's real ceiling, not riscv64-specific weirdness. Fix: retry with a halved
  reservation on mmap failure rather than hardcoding a 256GB cap (some riscv64 hardware has
  more). Worth a quick smoke test for any database/allocator/mmap-cache port with a multi-TB
  default reservation.

### Licensing & GPL sources — [`gotchas/licensing-and-gpl.md`](gotchas/licensing-and-gpl.md)

- **32** — Vendored C libraries are the usual licensing gap — and upstream often has the fix
- **44** — Naming a vendored dependency's licence `LICENSE.<dep>` at the project root
- **53** — A dependency that is *downloaded and compiled at build time* is invisible from
- **57** — An explicit `license_files=[...]` turns off setuptools' default glob, so gotcha 44's *(reused number — this theme)*
- **66** — A wheel that vendors the image's `libgomp` is the standard GPL-sources trigger —
- **86** — A monorepo's Python package builds from a subdirectory, so the project's *own*
- **105** — A `[project] license-files` list has no default glob behind it, so gotcha 44's
- **123** — gotcha 44 is not setuptools-specific — PEP 639 gave every backend the same default
- **130** — A REUSE-compliant vendored dependency ships a whole `LICENSES/` directory — declaring
- **137** — Ship the licence of everything auditwheel vendors without hand-listing it.
- **140** — The `gpl_sources` job must run on the riscv64 runner, and RHEL 10 dropped
- **153** — A `dist-info/sboms/*.cyclonedx.json` is not a licence notice — and the notice
- **146** — maturin auto-globs licence files only next to `pyproject.toml`, so a monorepo
- **161** — A vendored prebuilt stack can be GPL while every library in it reports LGPL — read
- **162** — A sibling build repo pins every source by URL and SHA-256, which makes the GPL/LGPL
- **165** — Three ways gotcha 137's licence sweep silently under-collects, and one image fact that
- **255** — A project's own build hook that hand-parses a *build-time* dependency's dist-info
- **301** — Gotcha 146's licence auto-glob only fires for a `pyproject.toml` with a `[project]`
- **309** — A wrapper's own permissive licence (LGPL, MIT, ...) does not launder a vendored
- **320** — gotcha 123's PEP 639 default license glob is not implemented by meson-python —
  check the built wheel, don't assume it is backend-agnostic.
- **349** — The legacy `[project.license]` table form (`{file = "..."}`) not only suppresses
  setuptools' PEP 639 default glob — combining it with an explicit `license-files` key
  is a hard error on recent setuptools.
- **409** — The `gpl_sources` trigger can come from the *musllinux* leg alone: auditwheel's
  musllinux policy does not allowlist the GCC runtime, so a C++ extension's musl wheel
  vendors `libstdc++`/`libgcc_s` where its manylinux sibling vendors nothing.
- **491** — Collecting the licences of auditwheel-grafted system libraries from RPMs has
  three failure modes — a runtime subpackage with no `%license` file, a text that lives in a
  different subpackage of the same source RPM, and a licence directory holding the wrong text
  for the bundled `.so` — and the same SBOM sizes the `gpl_sources` job (the eckitlib case).
- **533** — A GitLab `-/archive/` tarball is not byte-stable, so gotcha 162's pinned-SHA-256
  source collection flakes at random (dav1d/x264 returned three different digests before one
  matched); retry the download rather than relaxing the check (the decord2/pyav-ffmpeg case).
- **538** — scikit-build-core reads every setting from `SKBUILD_<SECTION>_<KEY>` too (lists split
  on `;`), so a project whose `wheel.license-files = ["LICENSE"]` leaves its statically linked
  fmt/pybind11 and vendored headers unnotified needs a `CIBW_ENVIRONMENT` entry, not a patch —
  the env source outranks `pyproject.toml` and the override replaces the list (the pyslang case).
- **578** — setuptools copies `license_files` relative to the *cwd* at `bdist_wheel` time, so a
  `setup.py` cmdclass that `os.chdir()`s into a CMake build tree makes a correct relative entry
  fail with `[Errno 2] No such file or directory: 'LICENSE.txt'` after the whole compile; absolute
  paths are rejected, so copy the files into the chdir target (the dynet38 case).

### Local validation & the aarch64/QEMU rehearsal — [`gotchas/local-validation-and-rehearsal.md`](gotchas/local-validation-and-rehearsal.md)

- **9** — Validate before every push
- **52** — Dry-run the *test* phase against upstream's released PyPI wheel before you build
- **85** — Dry-run the test phase at the dependency versions the *container* will resolve,
- **101** — Validate a riscv64 cibuildwheel workflow by running it verbatim on
- **113** — The aarch64 validation run (gotcha 101) does NOT exercise from-source dependency
- **178** — Run gotcha 101's riscv64 `pip download` check inside a *Linux* container, and run
- **180** — The aarch64 rehearsal defaults to the *wrong* base image — pass
- **188** — A fat-LTO maturin release profile makes a full QEMU riscv64 build-rehearsal too
- **223** — For a `bindings = "bin"` CLI's test assertions, `cargo build --release` the tool
- **298** — A local rehearsal's `pip`-resolved cibuildwheel can be too old for
- **369** — Without docker, fetch Rocky 10's own dnf repodata over plain HTTPS to
- **384** — `dnf` failing in the image with `Curl error (60) ... self-signed certificate` is
  your egress proxy, not the image — install the proxy CA into the container trust store
- **394** — A libtorch-linking project cannot be rehearsed on x86_64 with PyPI's `torch`
- **403** — Prove which build *variant* you are about to produce by stubbing the build
  backend's `setup()` on the host
- **404** — For a from-source C++ world, a *full CMake configure* inside the real riscv64
  image is the honest local ceiling
- **410** — Gotcha 188's "lower the optimisation level for the local rehearsal only" can
  silently produce a broken wheel when the project has a C99 `inline` helper with no
  `static` — and the suite still passes, because the pure-Python fallback catches it.
- **417** — A QEMU riscv64 rehearsal of a cibuildwheel job needs `CI=1` for
  scikit-build-core's CMake probe, and needs `CIBW_BEFORE_ALL`'s staging replayed.
- **412** — When no riscv64 image or cross-toolchain is reachable, rename a C/C++ source's
  arch macros in a scratch copy to exercise its generic architecture path natively — a
  restricted-egress host can still prove compilability without a container (the
  bitsandbytes case).
- **517** — For a `setup.py`/distutils C++ world, `-fsyntax-only` every translation unit
  inside the real riscv64 image using the flags `setup.py` itself computes — a ~20-minute
  preflight that catches gotcha 226's GCC-14 errors a GCC 13 host cannot (the pybullet case).
- **430** — A `-k`/`--ignore` change is verifiable offline with no wheel at all: rebuild the
  failed run's node ids into a synthetic test tree, then run the YAML-folded
  `CIBW_TEST_COMMAND` through `sh -c`.
- **444** — Validate a hand-edited `.patch` with `git apply --check`, never `patch`: a wrong
  `@@` line count makes GNU `patch` drop every following hunk in that file with no `.rej` and
  exit 0.
- **490** — An ecbuild/CMake project that installs its generated config header into the
  wheel hands you a byte-comparable feature oracle: configure once under QEMU and diff it
  against the released wheel's before compiling anything; also where an ECMWF binary-wrapper
  distribution's real build recipe lives when its wheel job is private (the eckitlib case).
- **495** — A Bazel port's loading phase rehearses on x86_64 in minutes: check the project's
  `.bazelrc` flags against the bazel you bootstrap in an empty workspace, then evaluate the real
  WORKSPACE with the real overrides — blocked egress only stops it at the first archive fetch.
- **498** — The manylinux image bakes `SSL_CERT_FILE=/opt/_internal/certs.pem`, so gotcha
  384's trust-store fix reaches `dnf` and not `curl`/`pip`; a sampling profiler cannot be
  rehearsed under QEMU (an emulated process's `/proc/<pid>/exe` is the host `qemu-<arch>`);
  and a throwaway unstripped CI run with core dumps buys the backtrace (the austin-dist case).

- **520** — A giant generated translation unit is rarely the dominant cost: time it on x86
  (a SWIG wrapper of 35 MB / 791k lines cost 588 s at `-O3` vs 152 s at `-O0`, a 4x ratio, and
  the `-O3` object was smaller) before copying upstream's constrained-arch `-O0` and shipping a
  divergence nobody needed (the quantlib case).

### PR, CI, triggers, publishing & maintainer signals — [`gotchas/pr-ci-and-maintainer.md`](gotchas/pr-ci-and-maintainer.md)

- **45** — A brand-new `build-<pkg>.yml` cannot be dispatched from a PR — GitHub only knows
- **54** — A `build-<pkg>.yml` that is not yet on the default branch cannot be
- **62** — A multi-hour job's log can be dropped by GitHub entirely — quiet the build tool
- **65** — Resuming another agent's in-flight port: re-check the branch against *today's*
- **68** — A pinned action SHA that does not exist kills the job in "Set up job", after the
- **80** — When a maintainer parks a port, stop pushing to the branch entirely — the
- **89** — No workflow runs at all after pushing a PR may be GitHub, not your triggers — check
- **158** — Editing a PR's *description* is free on a parked port; pushing a commit is not
- **163** — A maintainer hold that *names* a condition is an instruction to come back and
- **173** — `gh pr list --state open --head <pkg>` does not see a *merged* PR, so a finished
- **208** — A fresh `main` publish dispatch finishing green does not mean
- **370** — `.queue.yml` lives on `main` in a checkout shared by every concurrently
  running agent — edit it from an ephemeral detached worktree off fresh `origin/main`
  per state transition, and re-read the entry back after every push to catch a
  concurrent stale-based commit reverting it.
- **380** — A project that splits every release into two independently-named PyPI
  packages from one build needs two `_publish-wheel.yml` calls with disjoint artifact
  patterns, not two patterns on one call — the reusable workflow asserts a single
  normalized name and version per invocation.
- **413** — `git -C <dir> apply <glob>` hands git the literal glob (the shell expands it
  in the step's cwd, which `-C` does not change) — use `working-directory:` so shell and
  git share one base; an x86_64 rehearsal cannot catch a runner-layout bug.
- **458** — A failed job with no log at all (`404 BlobNotFound`) and its steps still
  `in_progress` is a dead runner, not a failed build; the check-run annotations endpoint
  still holds the dying process's message. Correlate the shape across packages, then
  `rerun-failed-jobs` rather than pushing a fix.
- **508** — A job is not hung because your own sense of elapsed time says so: an agent's
  `sleep` does not track the runners' clock, so compare the job's `started_at` with
  `date -u`, let `timeout-minutes` do the killing, and re-run a run rather than cancel it.
- **540** — `Failed to FinalizeArtifact … (403) Forbidden: Error from intermediary` on a job
  whose build, tests and wheel summary are all green is a GitHub artifact-service flake, not a
  port defect: re-run that leg with `rerun-failed-jobs`, which itself answers `403 "This
  workflow is already running"` until every sibling matrix leg has finished (the chonkie-core
  case).
