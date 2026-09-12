# Gotchas index — router for the themed gotcha files

The porting gotchas (363 of them) live in [`references/gotchas/`](gotchas/), split by theme so only the relevant slice loads. Every gotcha keeps a **permanent number** cited elsewhere as "gotcha N" (and in workflow comments as "CLAUDE.md gotcha N"). Numbers are stable IDs — **not sequential**, and four are **reused** with different content (two each of 33, 55, 56, 57), disambiguated by theme below.

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
