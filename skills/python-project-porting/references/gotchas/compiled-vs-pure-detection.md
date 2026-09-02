# Gotchas — Compiled-vs-pure detection & the require-extension knob

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/compiled-vs-pure-detection.md`.

## In this file

- **19** — mypyc-compiled wheels behind a `flit_core` pyproject (the tomli pattern; see
- **20** — Optional C extensions silently degrade to a mislabeled pure-Python wheel
- **28** — mypyc-by-default is the other half of gotcha 19 — verify the `.so`, don't add
- **33** — Not every `.so` in a wheel is an extension module — some are ctypes/cffi-loaded
- **49** — Before injecting gotcha 20's `REQUIRE_*_EXT` knob, check whether upstream already
- **56** — The module a compiled package exposes under a private-looking name is often a
- **91** — An optional C extension whose *release predates the interpreters we build* silently
- **127** — A C extension that does not declare free-threading support turns upstream's
- **129** — Copying upstream's require-extension env var verbatim ships a degraded wheel —
- **55** — A `cffi_modules` project is a normal port, and cffi itself is registry-only on

---

19. **mypyc-compiled wheels behind a `flit_core` pyproject (the tomli pattern; see
    `build-tomli.yml`).** Some pure-Python-*looking* packages publish
    mypyc-compiled binary wheels (a `.so` per module, big speedup) *alongside* the
    `py3-none-any` wheel — so riscv64 is worth building even though the sdist is
    pure Python. The compiled build is **opt-in and gated on an env var**, and the
    committed `pyproject.toml` declares `flit_core` (which can only make
    pure-Python wheels). Tell-tale: a `setup.py` sits next to the flit pyproject
    doing `if os.environ.get("<PKG>_USE_MYPYC")=="1": ext_modules =
    mypycify(glob("src/**/*.py"))`, plus a `scripts/use_setuptools.py`-style helper
    that rewrites `[build-system]` to `setuptools + mypy[mypyc]`. Two things must
    both happen to get compiled wheels — reproduce upstream's release job exactly:
    - **Run upstream's backend-swap script on the host** before cibuildwheel
      (`uv pip install -r scripts/requirements.txt && python
      scripts/use_setuptools.py`). It edits the checkout's `pyproject.toml` in
      place; the host interpreter (setup-uv) only runs the swap — the wheels
      compile in-container.
    - **Forward the mypyc env var into the container:**
      `CIBW_ENVIRONMENT_PASS_LINUX: <PKG>_USE_MYPYC` + `<PKG>_USE_MYPYC: '1'`.
      Without the pass-through the container build silently produces a *pure-Python*
      wheel (mypycify never fires) — you'd ship a no-op.
    There's usually **no `[tool.cibuildwheel]` table**, so supply
    `CIBW_MANYLINUX_RISCV64_IMAGE` and the test command yourself from the upstream
    release workflow's `env:` (grep `.github/workflows/*.y*ml` for `mypyc` /
    `use_setuptools` / `cibuildwheel`). Matrix is **per-interpreter**
    `[cp312, cp313, cp314, cp314t]` — mypyc wheels are *not* abi3 (confirm: PyPI
    shows separate `cpXY-cpXY` wheels, no `-abi3-` tag). The manylinux image already
    has the C toolchain + `Python.h`, so no `before-build`/`dnf` is needed — but a
    bare host (WSL) that lacks Python dev headers *will* fail the local `python -m
    build` with `fatal error: Python.h`; validate under QEMU/docker instead, where
    the container has them.

20. **Optional C extensions silently degrade to a mislabeled pure-Python wheel
    (the SQLAlchemy pattern; see `build-sqlalchemy.yml`).** When `setup.py` declares
    `Extension(..., optional=True)` — or gates it on an env var, SQLAlchemy uses
    `optional=not REQUIRE_SQLALCHEMY_CEXT` over 5 `.pyx` modules — a Cython/compile
    failure is **swallowed**: setuptools finishes and ships a wheel that still
    carries the `cp3XX-…-manylinux_riscv64` tag but contains **no `.so`**, just the
    pure-Python fallback. The job goes green and the "riscv64 wheel" is worthless
    (identical to the `py3-none-any` PyPI already ships). Fix: force the project's
    "require extension" knob so any build failure hard-fails — SQLAlchemy:
    `CIBW_ENVIRONMENT: REQUIRE_SQLALCHEMY_CEXT=1` (build phase needs it). **Always
    verify the `.so` is actually in the output wheel** (`unzip -l wheel.whl | grep
    '\.so$'`) — a green build is not proof. (These packages are pure-Python +
    *optional* speedups, so PyPI ships both a `py3-none-any` wheel *and*
    per-interpreter compiled wheels; the compiled riscv64 ones are the value-add,
    and the matrix is per-interpreter `[cp312, cp313, cp314, cp314t]`, not abi3.)

28. **mypyc-by-default is the other half of gotcha 19 — verify the `.so`, don't add
    the env var (the pytokens case; see `build-pytokens.yml`).** Gotcha 19's tomli
    shape has the mypyc build *opt-in* (`<PKG>_USE_MYPYC=1`) behind a `flit_core`
    pyproject with no `[tool.cibuildwheel]` table. The commoner shape inverts all
    three: `setup.py` sets
    `USE_MYPYC = platform.python_implementation() == "CPython"` unless the env var
    is present, `build-system.requires` already lists `mypy`, and upstream ships a
    real `[tool.cibuildwheel]` table (`build-frontend`, `MYPYC_OPT_LEVEL`, `skip`).
    The port is then a plain build-from-checkout with **one** override,
    `CIBW_MANYLINUX_RISCV64_IMAGE` — forcing `<PKG>_USE_MYPYC=1` yourself would be
    divergence, not insurance. What does need doing is gotcha 20's proof that the
    wheel is compiled: mypyc turns `src/<pkg>/__init__.py` into
    `<pkg>/__init__.cpython-3XX-….so`, so chain
    `python -c "import <pkg>; assert <pkg>.__file__.endswith('.so'), <pkg>.__file__"`
    ahead of pytest — `__file__` is the direct tell, no `has_c()`-style probe needed.
    - **`CIBW_TEST_SOURCES` cuts both ways on `pyproject.toml` (refines gotcha 25).**
      Gotcha 25 says stage it or lose `[tool.pytest.ini_options]`. The mirror trap:
      staging it imports `addopts` wholesale, and a dev-oriented
      `addopts = "--cov --cov-report=term-missing"` then kills the run with
      `unrecognized arguments: --cov` unless `pytest-cov` is also in
      `CIBW_TEST_REQUIRES`. Read `addopts` before deciding: stage `pyproject.toml`
      only if the suite needs its config, otherwise leave it out
      (`CIBW_TEST_SOURCES: tests`) and the coverage flags go with it. Upstream's tox
      `commands = pytest` is the reference for what the suite actually needs.

33. **Not every `.so` in a wheel is an extension module — some are ctypes/cffi-loaded
    raw shared libraries (the pycryptodome case; see `build-pycryptodome.yml`).**
    Gotchas 20/25/28 all reach for an import probe to prove the wheel is compiled
    (`import <pkg>; assert <pkg>.__file__.endswith('.so')`). That probe is invalid for a
    project that declares `Extension(...)` purely to get the C compiled and then `dlopen`s
    the result itself: pycryptodome's 40 `Crypto/*/_raw_*.abi3.so` have no `PyInit_*`, so
    `from Crypto.Cipher import _raw_aes` dies with **`ImportError: dynamic module does not
    define module export function (PyInit__raw_aes)`** — a probe failure that looks like a
    broken build but isn't. Tell-tale in 5 seconds: `grep -rl PyInit src/` returns nothing
    while the project has dozens of `Extension`s, and the loader (`Crypto/Util/_raw_api.py`)
    uses `ctypes.CDLL`/`cffi.dlopen`.
    - **The same fact removes the need for a probe.** Such a loader has no pure-Python
      fallback — it raises `OSError: Cannot load native module` — and the `Extension`s are
      not `optional=`, so a missing or unbuilt `.so` is a hard failure the moment the test
      suite imports anything. Use upstream's own test command unmodified and keep the
      gotcha-20 `unzip -l <whl> | grep '\.so$'` check as your proof instead.

49. **Before injecting gotcha 20's `REQUIRE_*_EXT` knob, check whether upstream already
    gates it on `CIBUILDWHEEL` (the simplejson case; see `build-simplejson.yml`).**
    cibuildwheel sets `CIBUILDWHEEL=1` in its own process environment and forwards it into
    the build container — `oci_container.py` passes `--env=CIBUILDWHEEL` to
    `docker/podman create`, so it is visible to **both** the build and the test phase.
    Upstreams that ship an optional C extension increasingly key their "the extension is
    mandatory here" switch off exactly that variable rather than a private one:
    simplejson's `setup.py` reads
    `REQUIRE_SPEEDUPS = os.environ.get('CIBUILDWHEEL') == '1' or os.environ.get('REQUIRE_SPEEDUPS') == '1'`,
    and its bundled suite adds a `TestMissingSpeedups` case that *fails* (rather than
    skipping) under the same condition. Adding `CIBW_ENVIRONMENT: REQUIRE_SPEEDUPS=1`
    would be redundant divergence, the same mistake gotcha 28 warns about for mypyc.
    - **Two greps settle it** before you write any `CIBW_ENVIRONMENT`:
      `grep -rn CIBUILDWHEEL setup.py <pkg>/` and the `optional=`/`BuildFailed` handler in
      `setup.py`. If the require-knob is reachable from `CIBUILDWHEEL`, you need no env var
      at all; if it is only reachable from a project-specific variable, gotcha 20 applies
      unchanged.
    - **Keep the `.so` assertion regardless** — it costs one step and is the only thing
      that proves the gate actually fired. The repo's existing shape is the
      `python3 - wheelhouse/*.whl <<'EOF'` / `zipfile.namelist()` check in
      `build-snowflake-connector-python.yml`.
    - **Related, and worth not rediscovering:** cibuildwheel >=3 runs `test-command` in an
      **empty** `test_cwd` even when `test-sources` is unset (`platforms/linux.py`:
      `test_cwd = testing_temp_dir / "test_cwd"`). So a suite that ships *inside* the wheel
      and is invoked as `python -m <pkg>.tests...` cannot be shadowed by the checkout —
      gotcha 25 only bites when the command names a path back into `{project}`/`{package}`
      and pytest's rootdir insertion drags the source tree onto `sys.path`.

56. **The module a compiled package exposes under a private-looking name is often a
    pure-Python re-export shim — probe the extension by its real name (the onnxruntime
    case).** Gotchas 20/25/28 all end in `assert <mod>.__file__.endswith('.so')`, and the
    second gotcha 33 warns the probe is invalid when the `.so` has no `PyInit_*`. A third
    way it misfires: the name that *looks* like the extension is a `.py` that re-exports
    it. onnxruntime ships both `onnxruntime/capi/_pybind_state.py` (a 1.5 KB shim doing
    `from onnxruntime.capi.onnxruntime_pybind11_state import *`, plus the provider
    diagnostics) and `onnxruntime/capi/onnxruntime_pybind11_state.cpython-3XX-….so` — the
    underscore-prefixed one is the shim, the verbose one is the extension. A probe aimed at
    `_pybind_state` asserts on `…/_pybind_state.py` and fails a wheel that is completely
    fine. Cost here: four jobs that each compiled ~9h of C++, auditwheel-repaired, uploaded
    the artifact and installed the wheel, then died on the assertion.
    - **Settle the name from the published wheel before writing the probe**, never from the
      import path that reads naturally:
      `unzip -l <upstream wheel> | grep '\.so$'` names the extension exactly, and it costs
      one `pip download --platform … --only-binary=:all:` on any host (gotcha 9). Anything
      the listing shows as `.py` cannot be the probe target however private its name looks.
    - **Import it directly rather than via the shim** —
      `from <pkg>.capi import <real_ext_name> as s` — so the assertion is about the object
      you actually care about; going through the shim would pass on `__file__` only by
      accident.
    - Costs nothing to get right, and the failure mode is the expensive kind: a *false
      negative* on a good wheel, at the very end of the longest job in the matrix. For a
      build measured in hours, put every cheap assertion where it runs first, and make sure
      each one is testing what you think.

91. **An optional C extension whose *release predates the interpreters we build* silently
    degrades even when nothing about the port is wrong (the pyrsistent case; see
    `build-pyrsistent.yml`).** Gotcha 20's SQLAlchemy shape and gotcha 49's simplejson
    shape both assume the project offers a "the extension is mandatory here" knob you can
    force. Many don't: pyrsistent's `setup.py` has only a *skip* knob
    (`PYRSISTENT_SKIP_EXTENSION`) and a `custom_build_ext` that catches every exception
    and prints a warning, so there is nothing to force on — the `.so` assertion is the
    only defence, and it has to be a **separate host step** (a green cibuildwheel run
    proves nothing). The failure here isn't riscv64 or our config: the newest PyPI wheel
    for the version we build stops at an older `cpXY`, and the C source calls a private
    CPython API that a later interpreter removed — `_PyList_Extend`, dropped from the
    3.13 headers — so cp313/cp314 compile-fail, get swallowed, and ship a platform-tagged
    wheel containing only the pure-Python fallback.
    - **Pre-flight it on any host in two minutes, before writing YAML.** Whenever the
      package's newest PyPI wheels stop below our matrix's newest interpreter, build the
      tag once per matrix interpreter and diff which ones produce a `.so`:
      `for v in 3.12 3.13 3.14; do uv build --wheel --python $v --out-dir out-$v .; unzip -l out-$v/*.whl | grep '\.so'; done`.
      Silence on the newer ones *is* the bug; the compiler error is in the build log above
      the swallowed-failure banner, not in the exit status.
    - **The fix is a `Backport`, and the version you build is still the PyPI one.** Check
      upstream's later tags for the fix (`git log <ourtag>..<newertag> -- <the C file>`) —
      pyrsistent fixed it in `c876adc`, which sits in the **v0.21.0 tag that was never
      released to PyPI**. Don't switch to the unreleased tag: gotcha 18's nightly
      `check_versions.py` compares the workflow's `version:` default against PyPI, so
      build the released version and carry the commit under
      `patches/<pkg>/<ver>/`. (No `SETUPTOOLS_SCM_PRETEND_VERSION` needed here — gotcha 31
      only bites projects that derive their version from git; pyrsistent's is a literal in
      `_pyrsistent_version.py`.)
    - **`sys._is_gil_enabled()` settles free-threading in one line** — a concrete probe to
      put beside gotcha 33's three upstream signals. An extension built with single-phase
      init (`PyModule_Create`, as opposed to `PyModuleDef_Init` + a `Py_mod_gil` slot)
      makes the runtime re-enable the GIL at import:
      `RuntimeWarning: The global interpreter lock (GIL) has been enabled to load module
      '<mod>'` and `sys._is_gil_enabled()` → `True`. Grep the C file for `PyModule_Create`
      before adding `cp314t` — a wheel that re-enables the GIL is a build upstream ships
      nowhere with none of the benefit.

127. **A C extension that does not declare free-threading support turns upstream's
    `-Werror` into a cp314t-only collection error — `PYTHON_GIL=1` is the honest fix
    (the srsly case).** Gotcha 33 settles *whether* `cp314t` belongs in the matrix from
    upstream signals; this is the separate problem of a package that legitimately ships
    a free-threaded wheel whose extensions have no `Py_mod_gil` slot. CPython 3.14t
    re-enables the GIL on first import of such a module and warns —
    `RuntimeWarning: The global interpreter lock (GIL) has been enabled to load module
    '<pkg>.<ext>', which has not declared that it can run safely without the GIL` — and
    any suite the upstream runs under `-W error` (srsly's `pytest --pyargs srsly
    -Werror`) then dies at *collection*, on every module that imports the package. The
    tell is that only the `cp314t` job fails while cp312/cp313/cp314 are green and the
    failures are import errors rather than assertion failures.
    - **Fix is one test-phase env var, not a weakened `-Werror`:**
      `CIBW_TEST_ENVIRONMENT: PYTHON_GIL=1` (gotcha 12 — test-only; it is additive to
      `CIBW_ENVIRONMENT`, so a registry `PIP_EXTRA_INDEX_URL` there still applies, as
      `build-grpcio.yml` shows). Asking for the GIL up front is the same runtime
      behaviour the warning describes, and it is silently ignored on the GIL builds, so
      one uniform value covers the whole matrix — no `include:` split needed. Do **not**
      reach for `PYTHON_GIL=0`: that keeps the GIL disabled for a module that declared
      it is not safe without it.
    - **Reproduces on any host in a minute** — `uv venv -p 3.14t`, `pip wheel .`, then
      `python -W error -c "import <pkg>"`. Arch-independent, so settle it before the
      first riscv64 cycle rather than after a 50-minute cp314t job.

129. **Copying upstream's require-extension env var verbatim ships a degraded wheel —
    a job-level `env:` on the cibuildwheel action never reaches the Linux container
    (the maxminddb case; see `build-maxminddb.yml`).** Gotcha 20 says to force the
    project's "require extension" knob and gotcha 49 says to check whether upstream
    already keys it off `CIBUILDWHEEL` first. There is a third case both miss: upstream
    *does* set a private knob, but sets it the way that only works on the runners where
    cibuildwheel builds natively. maxminddb's `release.yml` passes
    `MAXMINDDB_REQUIRE_EXTENSION: 1` as a plain `env:` on the `pypa/cibuildwheel` step,
    which works on macOS/Windows and is silently inert on Linux — `oci_container.py`
    (checked in 4.2.0) passes exactly `--env=CIBUILDWHEEL` and `--env=SOURCE_DATE_EPOCH`
    to `docker/podman create`, and everything else has to arrive through
    `CIBW_ENVIRONMENT` or `CIBW_ENVIRONMENT_PASS_LINUX`. So the line reads as inherited
    upstream behaviour while doing nothing, `setup.py`'s `BuildFailed` handler swallows
    any compile error, and the job goes green shipping the pure-Python fallback under a
    `manylinux_riscv64` tag.
    - **Promote it, don't copy it**: `CIBW_ENVIRONMENT: <PKG>_REQUIRE_EXTENSION=1`. That
      is a *smaller* divergence than it looks — it is upstream's own intent, expressed in
      the only spelling that reaches a Linux build — so say that in the comment rather
      than leaving a reader to wonder why the workflow differs.
    - **The same reasoning applies to any build-phase variable read off upstream's CI**
      (`CFLAGS`, `*_USE_SYSTEM_*`, feature toggles): a job-level `env:` is a Linux no-op.
      Grep upstream's wheel job for bare `env:` keys under the cibuildwheel step and route
      each one through `CIBW_ENVIRONMENT` deliberately.
    - **Prove the gate fired rather than trusting the flag.** Gotcha 20's
      `unzip -l | grep '\.so$'` works, but for a package whose extension is a real module
      the stronger one-liner is to assert the *loaded* module is the compiled file, chained
      ahead of the suite: `python -c "import <pkg>.<ext> as e; assert
      e.__file__.endswith('.so'), e.__file__" && python -m pytest tests`. Necessary here
      because the extension tests are guarded by `try: import <pkg>.<ext> / except
      ImportError` and *skip* rather than fail when the `.so` is missing — 278 tests pass
      either way.
    - **`test-sources` may need non-test files from the project root.** Gotcha 36 covers
      staging sibling *data* at its original relative path; the same staging can be needed
      for ordinary repo files a test happens to open. maxminddb's `test_nondatabase` opens
      `README.rst` as a deliberately-not-a-database input, so `CIBW_TEST_SOURCES: tests
      pyproject.toml README.rst` — without the README, 8 tests die with `FileNotFoundError`.
      Settle the list by running upstream's suite against the *released* PyPI wheel in a
      staged cwd on any host first (gotcha 52), which surfaces every such file in seconds.

55. **A `cffi_modules` project is a normal port, and cffi itself is registry-only on
    riscv64 (the xattr case; see `build-xattr.yml`).** A package whose `setup.py` is four
    lines and declares no `Extension` at all still compiles a C module when it carries
    `cffi_modules=["<pkg>/lib_build.py:ffi"]` — cffi's out-of-line API mode generates and
    builds the source at wheel-build time. Read `setup.py` for `cffi_modules` before
    applying gotcha 24/27's "nothing to compile" triage; PyPI confirms it the usual way
    (per-interpreter `cpXY-cpXY` platform wheels, `cp314t` included).
    - **cffi publishes no riscv64 wheel on PyPI**, and it is almost always *both* a
      `build-system.requires` entry and a runtime dependency — so it must resolve from our
      registry in the build phase *and* the test venv. That means `CIBW_ENVIRONMENT:
      PIP_EXTRA_INDEX_URL=…`, never `CIBW_TEST_ENVIRONMENT` (gotcha 12's split cuts the
      other way here). Without it pip silently source-builds cffi in-container, which
      works but only because upstream's `before-all` happened to install `libffi-devel`.
      Confirm the registry version is PyPI's current latest (gotcha 30) — as of 2.1.1 it
      is, for cp312/cp313/cp314/cp314t.
    - **An `.abi3.so` inside the wheel does NOT mean an abi3 wheel** — refines gotchas
      11/34. cffi names its module `_lib.abi3.so` and compiles it against the limited API,
      yet the wheel is tagged `cpXY-cpXY` because setuptools is never passed
      `--py-limited-api`. Read the **wheel tag**, not the `.so` filename, when deciding
      whether the matrix collapses; here it stays per-interpreter.
    - **Rocky 10 riscv64 facts** (adds to gotcha 46's list): `libffi-devel` resolves from
      appstream (`3.4.4-10.el10`) and `/usr/bin/yum` still exists as the dnf symlink, so an
      upstream `before-all = "yum install -y libffi-devel"` runs unchanged — check with a
      60MB `docker run --platform linux/riscv64 rockylinux/rockylinux:10 dnf -q list <pkg>`
      rather than a multi-GB manylinux pull.
