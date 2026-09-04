# Gotchas index — router for the themed gotcha files

The porting gotchas (200 of them) live in [`references/gotchas/`](gotchas/), split by theme so only the relevant slice loads. Every gotcha keeps a **permanent number** cited elsewhere as "gotcha N" (and in workflow comments as "CLAUDE.md gotcha N"). Numbers are stable IDs — **not sequential**, and four are **reused** with different content (two each of 33, 55, 56, 57), disambiguated by theme below.

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
- **PR/CI/publishing: registering a new workflow, `Trigger:` lines, action-SHA pins, maintainer holds/cancellations, post-merge publish** → [`gotchas/pr-ci-and-maintainer.md`](gotchas/pr-ci-and-maintainer.md)

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

### Local validation & the aarch64/QEMU rehearsal — [`gotchas/local-validation-and-rehearsal.md`](gotchas/local-validation-and-rehearsal.md)

- **9** — Validate before every push
- **52** — Dry-run the *test* phase against upstream's released PyPI wheel before you build
- **85** — Dry-run the test phase at the dependency versions the *container* will resolve,
- **101** — Validate a riscv64 cibuildwheel workflow by running it verbatim on
- **113** — The aarch64 validation run (gotcha 101) does NOT exercise from-source dependency
- **178** — Run gotcha 101's riscv64 `pip download` check inside a *Linux* container, and run
- **180** — The aarch64 rehearsal defaults to the *wrong* base image — pass
- **188** — A fat-LTO maturin release profile makes a full QEMU riscv64 build-rehearsal too

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
