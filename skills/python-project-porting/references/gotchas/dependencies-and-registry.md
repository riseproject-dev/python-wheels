# Gotchas — Dependencies & the registry

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/dependencies-and-registry.md`.

## In this file

- **30** — Check our own registry before dropping a dependency as "no riscv64 wheel".
- **55** — A pure-Python test dependency can go binary mid-stream, and free-threaded x riscv64
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
  *optional* component another test dependency imports unconditionally.
- **244** — `uv pip install` only honors `UV_*` env vars, never the `PIP_*` names — a step
  written with `PIP_EXTRA_INDEX_URL`/`PIP_ONLY_BINARY` silently no-ops and source-builds.
- **291** — A `CIBW_TEST_REQUIRES` package with no riscv64 wheel of its own can still need
  `PIP_ONLY_BINARY` for packages you never named, because *its* runtime deps are the ones
  that break (the moyopy/pymatgen case).
- **336** — A custom `CIBW_BEFORE_TEST` does not cancel a project's own `test-extras`
  cascade — the two install paths are independent, and `test-extras` runs regardless.
- **353** — Gotcha 30's registry check has moved off redirects: unhosted packages now
  answer plain `404`, not `302` — the check logic is unaffected, but scripts written
  against the old behavior may misread it.
- **354** — `PIP_PREFER_BINARY` (not `PIP_ONLY_BINARY`) is the fix when our registry
  hosts a wheel for only *some* matrix interpreters and an unpinned test dependency
  keeps resolving to a newer, wheel-less release.
- **375** — `uv` can reject a real `abi3` wheel resolved by name from an index as "has no
  usable wheels" even though the identical wheel installs fine as a local file.

---

30. **Check our own registry before dropping a dependency as "no riscv64 wheel".**
    `pypi.riseproject.dev` **302-redirects to pypi.org for anything it doesn't host**, so
    one call answers the question: `curl -s https://pypi.riseproject.dev/simple/<dep>/` —
    an HTML link list means we ship it (read the filenames for the interpreter tags), a
    302 means we don't. asyncpg's port initially deleted `uvloop` from upstream's `test`
    dependency-group and hand-copied the remaining requirements, assuming no riscv64
    uvloop existed; we ship 0.22.1 for cp312/cp313/cp314/cp314t. Inheriting upstream's
    `test-groups` unchanged and adding
    `CIBW_ENVIRONMENT: PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/` was both
    less YAML and closer to upstream — the divergence goal 2 warns about, introduced for
    a reason that wasn't true.
    - **The version has to line up, not just the name.** With `PIP_EXTRA_INDEX_URL` pip
      picks the highest version across *both* indexes and only then picks a file, so our
      riscv64 wheel gets used only when our version is the one pip resolves to. If PyPI's
      latest is newer than what we host, pip takes that and compiles it from sdist (or
      fails). Check with
      `curl -s https://pypi.org/pypi/<dep>/json | python3 -c 'import json,sys;print(json.load(sys.stdin)["info"]["version"])'`
      before relying on it.

55. **A pure-Python test dependency can go binary mid-stream, and free-threaded x riscv64
    is where that first bites (the hypothesis case).** Gotchas 23/25 pin floating build
    tools and test plugins for *behaviour* drift; this is the packaging variant — a dep that
    shipped `py3-none-any` for years starts shipping per-interpreter Rust wheels, and its
    arch/ABI matrix will not cover riscv64 free-threading for a while. hypothesis 6.156+
    publishes `cp310-abi3` (unusable under `Py_GIL_DISABLED`), `cp315-abi3.abi3t` (needs
    3.15+) and `cp314-cp314t` for x86_64/aarch64 only — so on cp314t riscv64 pip finds no
    wheel, falls back to the sdist, and the Rust build dies computing
    `riscv64-unknown-linux-gnu`, a triple rustup does not have (gotcha 10: it is
    `riscv64gc-`). The tell is a failure *after* your wheel built and installed cleanly,
    inside `pip install <test deps>`, on the free-threaded job only.
    - **Find the last pure-Python release rather than dropping the interpreter**: walk the
      PyPI JSON back for the newest version with a `py3-none-any.whl`
      (`hypothesis<6.156`) and pin that in `CIBW_TEST_REQUIRES`, restating the rest of
      upstream's list unchanged. Dropping cp314t would diverge from an upstream that does
      ship it.
    - Setting `CIBW_TEST_REQUIRES` replaces the project's `[tool.cibuildwheel] test-requires`
      wholesale, so copy every entry across. cibuildwheel shlex-splits the value and passes
      it as argv, so `hypothesis<6.156` needs no shell escaping — but quote the YAML scalar.

67. **A *build*-time dependency that we ship only for some interpreters caps the matrix
    — and `PIP_ONLY_BINARY` is what makes the older registry version win (the
    scikit-learn/scipy case).** Gotcha 30 says to check our registry before declaring a
    dep unavailable, and gotcha 40 covers a dep that is unavailable outright. The middle
    case is commoner and quieter: `pypi.riseproject.dev` carries the dep for `cp312`
    and `cp313` but not `cp314`/`cp314t`, so the default four-entry matrix cannot be
    used. Read the interpreter tags out of the index listing before writing `python:`:
    ```
    curl -s https://pypi.riseproject.dev/simple/<dep>/ | grep -oE '<dep>-[0-9.]+-cp[0-9t]+-[^"]*\.whl' | sort -u | tail
    ```
    Trim the matrix to those tags and say in a one-line comment *why*, naming the dep —
    otherwise the next agent re-adds cp314 and burns a multi-hour cycle discovering it.
    - **It is a build requirement, not just a runtime one, when the extension cimports
      it** (`scipy.linalg.cython_blas`) — so `PIP_EXTRA_INDEX_URL` has to be in
      `CIBW_ENVIRONMENT` (both phases, gotcha 12), not `CIBW_TEST_ENVIRONMENT`.
    - **`PIP_ONLY_BINARY` scoped to the dep names is what makes gotcha 30's
      "the version has to line up" bullet stop mattering.** PyPI's latest scipy is far
      newer than the 1.15.2 we host, and pip picks the highest version across both
      indexes — but with `PIP_ONLY_BINARY=numpy,scipy,pandas` the newer PyPI releases
      have no riscv64 *binary*, so they are not candidates at all and resolution lands
      on our wheel. Scope it to the dep names, never `:all:`: `cython` and
      `meson-python` have no riscv64 wheel anywhere and must build from sdist in the
      same build env.

70. **`CIBW_TEST_EXTRAS` is a blunt instrument: an extra can drag in a *compiled*
    transitive dependency whose newest release outruns our registry (the
    confluent-kafka case).** Gotcha 30 says check `pypi.riseproject.dev` before writing a
    dep off, and that the version has to line up as well as the name. The trap here is
    that you never named the dep at all -- you named an *extra*, and pip resolved it three
    levels down. confluent-kafka's `avro` extra pulls `authlib`, which requires
    `cryptography`; PyPI's newest cryptography has no riscv64 wheel and our registry is
    one release behind, so with `PIP_EXTRA_INDEX_URL` set pip picks PyPI's newer version
    and tries a Rust build inside a container with no cargo. The extra looked like the
    *closer-to-upstream* choice, which is what makes it easy to reach for.
    - **Derive the minimum dep set from collection errors, not from the extras table.**
      Run gotcha 52's dry-run against upstream's released wheel with only `pytest`
      installed and read what collection actually complains about:
      `pytest <paths> -q 2>&1 | grep -E "ModuleNotFoundError|ImportError" | sort -u`.
      confluent-kafka wanted exactly `avro`, `requests`, `urllib3` and `pyflakes` -- all
      pure Python, none of them `cryptography`. Naming those (plus upstream's own
      `requirements-tests.txt`, which supplies urllib3 and pyflakes) ran the same 670
      tests with no compiled test dep at all.
    - **Then sweep every *resolved* dep, not just the ones you typed.** `pip freeze` the
      dry-run venv and ask PyPI, per package, whether the latest release has a `-any.whl`
      *or* a riscv64 wheel; anything with neither is a source build waiting to happen.
      That surfaced `ast-serialize` and `librt` -- new `mypy` dependencies that are
      compiled but do publish riscv64 wheels, so they were fine, and you only know that
      because you looked.

84. **A build-only dependency that our registry ships for *some* interpreters caps the
    matrix — trim it, don't drop the port (the statsmodels/scipy case).** Gotcha 40 covers a
    dependency that is unavailable outright (conda-blocked llvmlite) and correctly says the
    port is blocked. The commoner and much milder shape is a dependency we already ship, just
    not for every interpreter: statsmodels' `build-system.requires` has `scipy>=1.13,<2` and
    scipy is a runtime requirement too, PyPI publishes **no** riscv64 scipy for any version
    (checked through 1.18.1), and `pypi.riseproject.dev` tops out at 1.15.2 for cp312/cp313.
    So `cp314`/`cp314t` have nothing to resolve at build time *or* test time, while cp312 and
    cp313 are fine. Ship the two that work and say why in a one-line matrix comment; the
    entries drop back in the day the dependency's own port lands.
    - **Run gotcha 30's registry check per *interpreter tag*, not per package name.** The
      simple index's filenames carry the tags — `curl -s https://pypi.riseproject.dev/simple/<dep>/
      | grep -oE '<dep>-[0-9][^-]*-cp3[0-9]+t?-'` — and the highest version is often available
      for fewer interpreters than the package as a whole. A bare "yes we ship it" answer will
      send you to a cp314 job that cannot resolve its own build requirements.
    - **`PIP_ONLY_BINARY=<dep1>,<dep2>` is the right scope here, not `:all:`.** With
      `PIP_EXTRA_INDEX_URL` set, pip picks the highest version that has a *compatible wheel*,
      so naming only the heavy scientific deps pins them to our riscv64 wheels while leaving
      `cython` (which has no riscv64 wheel anywhere and must compile from sdist, gotcha 12)
      free to build. Listing `:all:` starves the build backend instead.

90. **The committed `pyproject.toml` may be only one of several *variants* upstream
    publishes — and upstream usually ships the generator (the xgboost case; see
    `build-xgboost.yml`).** A project that publishes the same code under more than one
    distribution name or dependency flavour (CPU vs CUDA, `<pkg>` vs `<pkg>-cpu`) commonly
    commits the *GPU* flavour and rewrites it in CI per target. xgboost's checked-in
    `python-package/pyproject.toml` is the CUDA variant and declares
    `nvidia-nccl-cu13 ; platform_system == "Linux"`, which has no riscv64 wheel — so the
    wheel installs nowhere on riscv64 even though the build is clean. That is **not** a
    patch: `ops/script/pypi_variants.py --use-suffix=na --require-nccl-dep=na` is
    upstream's own generator, producing exactly the NCCL-free metadata they already ship
    for macOS and `win_arm64`. Run the generator in the workflow; hand-editing the
    dependency (or patching it out) diverges from a variant upstream supports.
    - **The tell is a marker that is `platform_system == "Linux"`-wide on a dependency
      that is really vendor-specific.** Read `info.requires_dist` from the PyPI JSON
      before writing YAML (the gotcha-40 dependency sweep), then grep the source tree for
      that requirement string: finding it in a *generated-looking* pyproject beside a
      `ops/script/*variant*.py`, a `PACKAGE_NAME`-style env switch (gotcha 50), or a CI
      `sed` means the flavour is a build-time choice, not a fact about the package.
    - **`wheel.py-api = "py3"` collapses the matrix further than abi3 does.** A
      scikit-build-core project whose extension is a plain `dlopen`ed shared library
      (gotcha 33's shape) needs no CPython ABI at all, so one build yields
      `py3-none-manylinux_riscv64` serving *every* interpreter — a single job, no
      `cp3XX` matrix, and the job/artifact names should say `py3-none-…` rather than
      naming the interpreter that happened to build it (same reasoning as gotcha 34).

97. **A test dependency that went from pure Python to an abi3 extension strands the
    free-threaded job alone (the pyroaring/hypothesis case).** Gotcha 25 says to pin
    floating test deps; the version-drift shape it warns about is a new warning turning
    into a hard failure. There is a second shape that is invisible until a matrix comes
    back with cp312/cp313/cp314 green and **only** cp314t red, in the *test-requires
    install*, before a single project test runs. A dependency that used to publish one
    `py3-none-any` wheel can start shipping compiled wheels — hypothesis became a Rust
    extension in 6.156 — and the riscv64 files it publishes are then typically
    `cpNN-abi3-manylinux_..._riscv64` only. abi3 wheels do not load under free threading
    (gotcha 11), so pip finds no compatible wheel for `cp314t` alone, falls back to the
    sdist, and dies in the dependency's build backend. The traceback names the dependency,
    not your package, and the wheel under test has already built and auditwheel-repaired
    successfully by then.
    - **Read the dependency's file list rather than its build error.** One PyPI JSON call
      (`[f['filename'] for f in urls]`) shows the whole story: `cp310-abi3-…riscv64`
      covers every GIL-ful interpreter you build, and the free-threaded tag is either
      absent or gated behind a Python you do not have (hypothesis's is
      `cp315-abi3.abi3t`). No need to work out why rustup was invoked.
    - **Fix by pinning the last pure-Python release, per matrix entry.** Find it by
      walking the releases for the newest one still shipping `-py3-none-any.whl`
      (hypothesis: 6.155.7). Then use gotcha 33's `include:` shape so only the affected
      entry carries the pin and the others keep resolving whatever upstream's own
      workflow would — `CIBW_TEST_REQUIRES: ${{ matrix.hypothesis }} pytest`. Pinning
      globally would be divergence on three jobs to fix one.
    - `CIBW_TEST_REQUIRES` is passed to pip as argv, not through a shell, so a specifier
      like `hypothesis<6.156` needs no quoting or escaping — unlike gotcha 23's
      `CIBW_BEFORE_BUILD` string, which does.
    - **Check our own registry before reaching for the pin (gotcha 30), and check it per
      interpreter.** The pin is the fallback, not the first move: we now publish
      hypothesis 6.165.10 for cp312/cp313/cp314/cp314t, so a workflow that already sets
      `PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/` in `CIBW_ENVIRONMENT`
      resolves the free-threaded wheel from us and needs no per-entry `include:` at all
      (cramjam's cp314t job installed
      `hypothesis-6.165.10-cp314-cp314t-manylinux_2_34_riscv64…whl`). Tell ours from
      PyPI's by the platform tag — ours are `manylinux_2_34_riscv64.manylinux_2_39_riscv64`,
      PyPI's abi3 one is `manylinux_2_31_riscv64` — and read the tags, not the package
      name: a `200` from the registry says we host *something*, not that we host a wheel
      for the interpreter that is red.

122. **A runtime dependency with no riscv64 wheel *and no sdist* blocks cibuildwheel's wheel
    install, not just the tests - `PIP_NO_DEPS` in the test environment is the way through.**
    cibuildwheel always runs `pip install <wheel>` before `test-command`, so one unsatisfiable
    `Requires-Dist` (pymupdf-layout pins `onnxruntime`, which publishes no riscv64 wheel and
    no sdist at all) turns the whole test phase red however narrow your `test-command` is.
    Gotcha 48's answer - skip the install and exercise the `.so` off the unpacked wheel - is
    right when *nothing* is installable; when most of the dependency tree is fine, keep the
    real install and drop only the resolution:
    ```yaml
    CIBW_TEST_ENVIRONMENT: PIP_NO_DEPS=1
    CIBW_BEFORE_TEST_LINUX: PIP_NO_DEPS=0 pip install pytest <deps the runnable tests need>
    ```
    `before_test` runs with the same environment as the wheel install (`linux.py`:
    `virtualenv_env = build_options.test_environment.as_dictionary(...)`, applied before
    both), so the inline `PIP_NO_DEPS=0` on that one `sh -c` line is what lets the staged
    dependencies resolve normally while the wheel itself installs bare.
    - **Then say which tests the gap costs you, in the workflow.** Follow the import chain
      and name it: pymupdf-layout's `tests/test_general.py` is unrunnable because
      `pymupdf.layout.__init__` calls `activate()` at module scope, which reaches
      `import onnxruntime` - while `tests/test_tgif.py` drives the C extension over a real
      PDF on pymupdf alone. `--noconftest` may be needed alongside `--ignore`: a `conftest.py`
      that pip-installs helpers for the excluded module (this one installs `opencv-python`)
      still runs at collection.
    - **Nothing about the port changes when the dependency lands** - that is the test of
      whether this is the right shape rather than a workaround.

125. **A dependency with no riscv64 wheel anywhere is only a blocker if it cannot build
    from its sdist (bounds gotcha 40).** Gotcha 40's dependency check — PyPI has no riscv64
    wheel *and* `pypi.riseproject.dev` 302s — is the right first question, but a `no` on both
    is not by itself a stop: pip will build the dep from sdist inside the manylinux container,
    for the isolated build env *and* for the `pip install <wheel>` the test phase runs. That is
    fatal only when the sdist needs something riscv64 doesn't have (llvmlite: a patched LLVM
    that only exists as a conda artifact). preshed cimports `.pxd` headers from **cymem** and
    **murmurhash** at build time and imports them at runtime; neither publishes a riscv64 wheel
    on PyPI or ours, and both are small Cython/C++ packages that compile from sdist in seconds
    — the port needed no `CIBW_BEFORE_BUILD` and no dep-wheel pattern (gotcha 17) at all.
    - **Ask what the dep's own sdist build requires, not just whether a wheel exists.** Read
      its `build-system.requires`; if that resolves on riscv64 (setuptools/Cython/a C
      compiler), the dep is a non-issue. A `pip wheel <pkg-sdist> --no-deps` on *any* host,
      with build isolation left on, exercises the whole chain in one command — it resolves and
      compiles the deps too, so a green run is evidence for every arch with a toolchain.
    - **Still set `CIBW_ENVIRONMENT: PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/`**
      even when nothing resolves from the registry today: it costs one line and the dep
      switches from a per-build source compile to our wheel the moment someone ports it.

149. **cp314t can be un-*testable* while staying perfectly buildable — skip its tests,
    do not drop the entry.** Gotcha 33 drops `cp314t` when upstream ships no free-threaded
    wheel; gotcha 55 pins a test dependency back to its last pure-Python release; gotcha 84
    drops matrix entries whose dependency is missing *on riscv64*. A fourth case needs none
    of those: the package's own **hard runtime requirement** publishes no free-threaded
    wheel on **any** architecture, so the wheel cannot even be installed under cp314t
    anywhere in the world — fastparquet requires `pandas>=1.5.0`, and pandas (checked
    through 3.0.5) publishes cp311–cp314 only, no `cp314t`, for every platform. Since
    upstream *does* ship a `cp314-cp314t` wheel of the package itself, dropping the entry
    would ship riscv64 less than upstream ships; the honest shape is to build it and skip
    only its tests.
    - **Drive it from the matrix, the way gotcha 33 drives per-entry deselection**, so the
      GIL-ful entries keep their full suite:
      ```yaml
      matrix:
        python: ["cp312", "cp313", "cp314", "cp314t"]
        include:
          - python: "cp314t"
            test_skip: "*"
      ...
          CIBW_TEST_SKIP: ${{ matrix.test_skip }}
      ```
      An unset matrix key interpolates to the empty string, and cibuildwheel's `test-skip`
      selector treats `""` as "skip nothing" (same `_resolve_cascade` behaviour gotcha 51
      relies on for `before-build`), so the other entries need no second command shape.
    - **Keep gotcha 20's `.so` assertion as a separate post-build step, not inside
      `CIBW_TEST_COMMAND`** — it is the only proof the untested interpreter produced a real
      wheel. Assert the exact *set* of extension names (gotcha 48), so a half-built wheel
      fails as loudly as an empty one.
    - Distinguishing question, cheap to answer: does the blocking dependency lack the
      free-threaded wheel *on riscv64* (a port to sequence — gotcha 84) or *everywhere*
      (nothing to wait for — skip the tests)? One PyPI JSON read on the dependency settles
      which.

172. **An abi3 build compiles the wheel once but rebuilds the *test venv* per
    interpreter, so a source-built test dependency costs 3x (the chromadb case; see
    `build-chromadb.yml`).** Gotchas 11/34/155 all sell the abi3 collapse as "one build,
    re-tested on each interpreter" — true of the wheel and false of everything around it.
    cibuildwheel creates a fresh venv and re-runs `pip install <test-requires> <wheel>`
    for every identifier in `CIBW_BUILD`, and pip's wheel cache is keyed by interpreter
    tag, so any dependency without a riscv64 wheel is compiled once per entry. chromadb's
    test phase resolved **grpcio** and **pandas** from PyPI — whose newest releases are
    ahead of what our registry hosts and have no riscv64 build — turning a 3-line
    `CIBW_TEST_REQUIRES` into six heavy source builds bolted onto an already multi-hour
    Rust compile, against a 720-minute timeout.
    - **Gotcha 67's `PIP_ONLY_BINARY=<names>` is the fix, but it belongs in
      `CIBW_TEST_ENVIRONMENT` here** (gotcha 12's split): it is a test-phase concern only,
      and `test_environment.as_dictionary(prev_environment=...)` layers it *on top of*
      `CIBW_ENVIRONMENT`, so the registry `PIP_EXTRA_INDEX_URL` set there still applies.
      Scope it to the names the registry actually hosts for your interpreters — a
      dependency with no riscv64 wheel *anywhere* (chroma-hnswlib, mmh3) must stay
      source-built, and naming it would make resolution impossible.
    - **Before accepting a source build, read the dependency's own release workflow for
      the flags its published wheels carry.** chroma-hnswlib's `setup.py` appends
      `-march=native` unless `HNSWLIB_NO_NATIVE` is set, while its `release.yml` sets
      `CIBW_ENVIRONMENT: HNSWLIB_NO_NATIVE=true` — so reproducing that is *less*
      divergence than letting the sdist take its default, and it removes an arch-specific
      unknown (whether the image's GCC accepts `-march=native` on riscv64) for free. One
      `gh api repos/<o>/<r>/contents/.github/workflows/<f>` settles it.
    - **`[profile.release] debug = 2` next to maturin's `strip = true` is pure waste on a
      slow runner** (extends gotcha 141, which covers picking the *profile*): the DWARF is
      generated for the whole crate graph and then thrown away by the strip, so
      `CARGO_PROFILE_RELEASE_DEBUG=0` in `CIBW_ENVIRONMENT` changes no shipped byte and
      cuts both compile time and target-dir size. Read `[profile.release]` in the
      workspace root before budgeting the build.
    - **Activate the venv in your local dry run, or it invents failures.** cibuildwheel
      runs `test-command` with the test venv's `bin` first on `PATH`, so a suite that
      shells out (`subprocess.run(["python", "-m", ...])` — a common way to test import
      behaviour in a clean process) works in CI. Running gotcha 52's rehearsal as
      `../venv/bin/python -m pytest` instead leaves `python` unresolvable and that test
      fails with a bare `FileNotFoundError` deep inside `subprocess`. The trap is that the
      obvious response is to deselect it: this port arrived carrying a PR-description note
      claiming exactly that test "needs network", when re-running it with the venv on
      `PATH` passes in 0.4s.

200. **A monorepo sibling ported in a separate PR can pin `install_requires` to its own
     exact version, so testing the wheel needs a package that is itself mid-port (the
     grpcio-tools/grpcio case).** grpcio-tools 1.83.1's `install_requires` reads
     `grpcio>={version}` with `{version}` filled in as grpcio-tools' *own* tag, so
     `pip install`-ing the freshly built wheel needs grpcio 1.83.1 specifically - not just
     "some grpcio" - even though grpcio and grpcio-tools are two separately ported
     packages from the same source tree. If the sibling hasn't published that exact
     version yet (its own patch-version-bump PR still open), `CIBW_TEST_ENVIRONMENT:
     PIP_ONLY_BINARY=:all:` turns the gap into a fast, legible failure - `ERROR: Could not
     find a version that satisfies the requirement grpcio>=1.83.1 (from versions: 1.72.0,
     1.75.1, 1.76.0, 1.78.0)` - at the automatic wheel-install-for-test step, instead of a
     multi-hour from-source rebuild of the sibling's C++ core on shared riscv64 runners.
     - **Confirm the build is sound first.** All three interpreters compiling and
       auditwheel-repairing cleanly is what turns the test-phase failure into proof of a
       registry gap rather than a broken workflow - grep the log for `Successfully built
       <pkg>` before trusting the failure's cause.
     - **Open as a draft citing the exact blocking PR**, per the existing "blocked on an
       unpublished dependency" convention (see PR/CI conventions in
       `pr-and-publishing.md`). It goes green on its own once the sibling merges and
       publishes - no workflow change needed, just re-running CI.

210. **A test dependency our registry already carries as a wheel can still fail from
     source, because pip resolves to whatever version is *newest*, not whatever version
     has a wheel (the pikepdf/hypothesis case).** pikepdf's `test` dependency group pins
     only `hypothesis>=6.36`; our registry ships `hypothesis-6.165.10` for
     cp312/cp313/cp314/cp314t, well above that floor, but a plain `pip install` during
     `CIBW_TEST_ENVIRONMENT` still pulled `hypothesis-6.167.1.tar.gz` from PyPI - a
     newer release with no riscv64 wheel anywhere - because pip's resolver picks the
     highest version satisfying the constraint across *all* indexes and does not prefer
     a wheel over a same-or-lower-priority sdist. hypothesis 6.167.1 also switched its
     `[build-system]` to `build-backend = "maturin"`, and building it from sdist prints
     `Target triple not supported by rustup` before trying (and failing) to auto-install
     a Rust toolchain - a dead end distinct from gotcha 179/182's cross-compile cases,
     since this is a *native* riscv64 build machine that rustup simply doesn't recognise
     as an install target at all.
     - **Pin the dependency to binary-only, not a version ceiling.** `CIBW_TEST_ENVIRONMENT:
       PIP_ONLY_BINARY=hypothesis` (gotcha 12: the test-only knob, not `CIBW_ENVIRONMENT`)
       makes pip stop at the newest version our registry actually has a wheel for,
       without hand-pinning a version that will silently go stale as the registry adds
       newer builds.
     - **hypothesis is a near-universal test dependency** across this repo's ports, so any
       future port whose test suite pulls it in fresh (rather than relying on a cached
       resolution) can hit the same wall once PyPI's hypothesis crosses whatever release
       made the maturin switch - check `pypi.org/pypi/hypothesis/<version>/json` for
       `requires_dist`/build-backend drift before assuming a version bump is free.

215. **A registry gap for one interpreter can be narrowed to just the one optional
     test-extra it gates, instead of the whole test phase (bounds gotcha 149; the
     python-calamine/pandas case).** Gotcha 149 skips the entire test phase
     (`CIBW_TEST_SKIP: "*"`) for a `cp314t` job whose hard runtime dependency has no
     free-threaded wheel *anywhere*. A softer, commoner shape needs a lighter touch: the
     dependency is only an optional integration extra (`pandas[excel]>=2.2`) that a handful
     of tests guard with `@pytest.mark.skipif(not pd, ...)`, and the gap is not upstream's —
     `pypi.riseproject.dev` simply hasn't built it yet for that one interpreter (pandas ships
     cp312/cp313/cp314 riscv64 wheels but no cp314t one, while PyPI itself does). Dropping
     just that entry's `CIBW_TEST_REQUIRES` value, rather than skipping the whole run, keeps
     every non-pandas test executing and self-skips only the pandas-gated ones:
     ```yaml
     matrix:
       include:
         - python: cp312
           pandas: 'pandas[excel]>=2.2'
         - python: cp314t
           pandas: ''
     ...
         CIBW_TEST_REQUIRES: pytest~=9.0 ${{ matrix.pandas }}
     ```
     - Two questions settle which shape applies: does the *package itself* fail to install
       without the dependency (gotcha 149 — skip everything), or does only some tests import
       it behind a guard (this one — narrow the extra)? Read the test file for the
       try/except or skipif before reaching for `CIBW_TEST_SKIP`.
     - The gap here is registry-only, not upstream's: re-check
       `pypi.riseproject.dev/simple/<dep>/` before the next version bump — the day our
       registry ships a cp314t wheel, the matrix field becomes redundant, unlike gotcha
       149's permanent everywhere-gap.

232. **Matching upstream's newest interpreter tier can silently trade a fast port for a
    from-source build of a heavy dependency — check whether it's a hard blocker or just an
    unplanned cost (the blosc2 cp315t case).** Gotchas 67/84 cover a registry-only gap that
    caps the *low* end of the matrix; the newest tier is a different shape: neither
    `pypi.riseproject.dev` nor public PyPI has published a riscv64 wheel for it *anywhere*
    yet, for anyone, because the interpreter itself is bleeding-edge (here, CPython 3.15
    pre-release). python-blosc2 4.11.0 upstream builds three wheels — `cp311-abi3`,
    `cp314t`, `cp315t` — and numpy (a build **and** runtime requirement) has no riscv64
    wheel for `cp315`/`cp315t` on either index, checked both ways: `curl -s
    https://pypi.riseproject.dev/simple/numpy/` and the public
    `https://pypi.org/pypi/numpy/json`. This is **not** automatically a blocker the way
    gotcha 40's conda-only dependency is: `build-rasterio.yml`'s `cp315`/`cp315t` legs
    (PR #912) resolved `numpy==2.5.2` and passed by letting pip build it from sdist inside
    the container, costing roughly 23 extra minutes over a wheel install (visible as a
    `numpy` sdist-build gap in the job log timestamps) — riscv64 CI has apparently already
    absorbed a from-source numpy build once. The choice is then a scope/cost call, not a
    feasibility one: paying that cost (and the shared-runner time, gotcha 48) to match
    upstream's exact three-wheel shape, or dropping the newest tier and documenting why, the
    way this port did (`cp311-abi3` + `cp314t` only, no `cp315t`, one PR-description bullet
    naming numpy as the reason). Re-check both indexes before the next version bump — the
    day numpy ships a `cp315` riscv64 wheel anywhere, the dropped tier costs nothing to add
    back.

234. **A stock distro `pip` can be too old to *recognize* a riscv64 manylinux wheel at
    all — the fix is upgrading pip itself, not the wheel (the sqlite-vec case).**
    manylinux tag compatibility is computed from pip's own **vendored** copy of
    `packaging`, not any `packaging` installed into the venv's site-packages —
    `pip install -U packaging` does nothing for this, and neither does a correct
    `platform.libc_ver()`/`packaging._manylinux._get_glibc_version()` reading (both
    already report `2.39` when this fails). Ubuntu 24.04's apt `python3-pip` (24.0) lists
    **zero** `manylinux_*_riscv64` tags in `pip debug --verbose` — only bare
    `linux_riscv64` — so `pip install <riscv64 wheel>` fails outright with `... is not a
    supported wheel on this platform`, and `pip install numpy` (which *is* on our
    registry) silently falls back to a from-source build that cascades into missing
    build tools (`ninja`→`cmake`→`Could not find OpenSSL`) instead of failing cleanly.
    `pip install --upgrade pip` first (26.2.1, checked) fixes both: `pip debug --verbose`
    then lists 690 compatible tags headed by `cp312-cp312-manylinux_2_39_riscv64`.
    - **This is a property of the *installing* pip, not of the wheel or the registry** —
      the identical riscv64 wheel that fails under old pip installs cleanly once pip is
      upgraded, for a self-built wheel exactly as much as for anything already on
      `pypi.riseproject.dev`. Any workflow step (or real end user) invoking system `pip`
      directly on `ubuntu-24.04-riscv` — i.e. outside the manylinux container, gotcha
      235's territory — needs the upgrade first.
    - **Two different old-pip environments, same root cause.** Rocky 10's own system
      `python3` (inside the manylinux image, distinct from `/opt/python`) shows the
      identical zero-manylinux-tags symptom with its bundled pip 23.3.2; `/opt/python/
      cpXY-cpXY`'s bundled pip is unaffected because it ships current. Grep `pip debug
      --verbose | grep -c manylinux` before trusting any install step that runs outside
      `/opt/python`.

240. **A registry-hosted wheel that builds and installs cleanly can still be missing an
    *optional* component another test dependency imports unconditionally (the
    pyiceberg-core/pyarrow case).** `pypi.riseproject.dev` ships a real riscv64 pyarrow
    wheel, and `pip install pyarrow` succeeds without complaint — but `build-pyarrow.yml`
    sets `ARROW_S3: "OFF"` for riscv64, so the wheel carries no `pyarrow._s3fs` extension
    module at all. That's invisible until something imports it: `pyiceberg.io.pyarrow`
    (a hard dependency of `pyiceberg`, not an extra) does `from pyarrow._s3fs import
    S3RetryStrategy` at module level, unconditionally, so `import pyiceberg.io.pyarrow`
    — and anything that transitively imports it — raises `ModuleNotFoundError: No module
    named 'pyarrow._s3fs'` on riscv64 even though the identical code runs fine wherever
    pyarrow ships S3 support. This is a different shape than gotcha 84's "wrong version"
    or gotcha 122's "no wheel at all": the *right* version of the *right* wheel installs,
    and the gap is a disabled optional feature inside it, so `PIP_ONLY_BINARY` and version
    pins do nothing to fix it.
    - **Diagnose by checking the specific submodule, not just the package**: `python -c
      "import pyarrow._s3fs"` against the installed wheel reproduces the exact error a
      test file's import chain hits, cheaper than tracing a full pytest collection
      failure back to its cause.
    - **Read the *dependent's* import, not just the registry's build flags** — a project's
      own `build-<dep>.yml` documents *what* is disabled (`grep ARROW_S3
      .github/workflows/build-pyarrow.yml`), but only the failing test's traceback shows
      *which* downstream consumer needs it unconditionally. `pyiceberg`'s own optional-
      dependency story (`pyiceberg[pyarrow]`, `try: import pyarrow`) does not apply here:
      `pyiceberg.io.pyarrow` is imported by `pyiceberg.catalog` and other core paths
      whenever pyarrow is present at all, with no feature flag gating the `_s3fs` import
      specifically.
    - **The fix is scoping the test suite, not chasing the missing feature.** Rebuilding
      pyarrow with S3 support for riscv64 is a separate, much larger port question (the
      AWS C++ SDK's own riscv64 story); dropping the one test file that needs the
      unconditional import and noting why in the PR (naming the module and the disabled
      flag) is the same move gotcha 215 makes for a per-interpreter registry gap, applied
      to a per-feature one instead.

244. **`uv pip install` only honors `UV_*` env vars, never the `PIP_*` names — a step
    written with `PIP_EXTRA_INDEX_URL`/`PIP_ONLY_BINARY` silently no-ops and source-builds
    (the daft port).** A "Test wheel" step ran `uv pip install pandas==2.3.3 numpy==2.3.4
    pyarrow==25.0.1 dist/*.whl` with `PIP_EXTRA_INDEX_URL: https://pypi.riseproject.dev/
    simple/` and `PIP_ONLY_BINARY: numpy,pandas,pyarrow` set as step `env:` — the same
    variable names gotcha 30 and friends use everywhere else in this repo, because most
    other test steps run inside cibuildwheel's `CIBW_TEST_ENVIRONMENT`, which shells out to
    plain `pip` and does read them. `uv`'s pip-compatible subcommand does not: it reads
    `UV_EXTRA_INDEX_URL`, `UV_INDEX_STRATEGY`, and `UV_ONLY_BINARY` instead (`uv help pip
    install` lists the `[env: UV_…]` name for every pip-shaped flag). With the `PIP_*` names
    unrecognized, uv silently fell back to its defaults — default index only (public PyPI,
    no riscv64 wheels), no only-binary restriction — resolved `pyarrow==25.0.1` against
    PyPI's sdist, and source-built it. pyarrow's sdist needs the real Apache Arrow C++
    library and its CMake config (`FindArrow.cmake`/`ArrowConfig.cmake`) to configure at
    all, which the manylinux image doesn't carry, so the failure surfaced ~6.5 hours later
    as `CMake Error … Could not find a package configuration file provided by "Arrow"` —
    a red herring that looks like a missing native C++ dependency of the package under
    test, when the actual break is a silently-ignored env var one step earlier. The
    registry already had the exact riscv64 wheel needed
    (`pyarrow-25.0.1-cp312-cp312-manylinux_2_39_riscv64.whl`); it was simply never
    consulted.
    - **The fix is renaming the three vars, not touching indexes or CMake.** Swap to
      `UV_EXTRA_INDEX_URL` / `UV_ONLY_BINARY`, and add `UV_INDEX_STRATEGY:
      unsafe-best-match` alongside them — uv's default `first-index` strategy stops at
      the first index that lists the package *name* at all (here, PyPI, which lists
      pyarrow but not a riscv64 build of it) and never reaches a second index for a
      platform-specific wheel, the same reasoning build-matplotlib.yml's and
      build-onnx.yml's `env:` blocks already document for their own `uv pip install`/
      `uv pip download` steps.
    - **Any bare `uv pip install`/`uv pip download` step is a signal to check this** —
      not just ones added fresh. cibuildwheel-driven steps (`CIBW_TEST_ENVIRONMENT`,
      `CIBW_ENVIRONMENT`) are unaffected since those still shell out to `pip`; the risk is
      specifically a workflow step that invokes `uv` directly (`setup-uv` + `uv pip
      install`, as build-daft.yml's and build-polars-runtime.yml's "Test wheel" steps do)
      and reuses the `PIP_*` names out of habit from the cibuildwheel case elsewhere in
      the same file.

291. **A `CIBW_TEST_REQUIRES` package with no riscv64 wheel of its own can still need
    `PIP_ONLY_BINARY` for packages you never named, because *its* runtime deps are the ones
    that break (the moyopy/pymatgen case).** Gotchas 67/84 cover the mechanism —
    `PIP_EXTRA_INDEX_URL` alone lets pip pick the highest version across *both* indexes, and
    if PyPI's latest release of a heavy scientific package is newer than what our registry
    hosts, pip takes PyPI's sdist-only release over our older riscv64 wheel — but both frame
    it as a *build-time* dependency capping the matrix per interpreter. moyopy's
    `CIBW_TEST_REQUIRES: pytest numpy pymatgen ase>=3.23` hits the same mechanism from a
    different angle: pymatgen itself has no riscv64 wheel anywhere (confirmed sdist-only,
    correctly so — gotcha 125 says that alone isn't a blocker) and installs fine from
    source, but its own `install_requires` pulls in scipy, and transitively numpy and
    pandas, plus orjson from a sibling dependency (bibtexparser) — none of which were named
    in `CIBW_TEST_REQUIRES` at all. Our registry has riscv64 wheels for all four across
    every interpreter this port builds, but with only `PIP_EXTRA_INDEX_URL` set, pip
    resolved PyPI's newer `scipy==1.15.3`, `numpy==2.2.6`, and `pandas==2.3.3` sdists
    instead (each one higher than our registry's ceiling for at least one interpreter) and
    tried to compile them one after another — numpy took ~16 minutes and happened to
    succeed, but scipy's meson build failed outright with `Dependency "OpenBLAS" not found
    (tried pkg-config and cmake)`, since the manylinux image carries no OpenBLAS.
    - **The failing package's name is not in your `CIBW_TEST_REQUIRES` line — read the pip
      log for `Collecting <dep> (from <other-dep>)` to find what's actually being resolved
      before assuming the listed package is the problem.** The traceback here named scipy;
      the workflow only lists pymatgen.
    - **List every transitive heavy scientific dependency in `PIP_ONLY_BINARY`, not just the
      one you added to test-requires.** `PIP_ONLY_BINARY=numpy,scipy,pandas,orjson` (in
      `CIBW_ENVIRONMENT_LINUX`, both phases per gotcha 12 — there is no build-time
      dependency here to starve) makes pip pick the highest version that has a riscv64
      wheel per package, which is our registry's, for every interpreter in the matrix.
      Find the full set by watching which `Collecting <dep>` lines download a `.tar.gz`
      instead of a `.whl` in a dry run, then check each one against the registry
      (gotcha 30) before naming it.
    - **This is a recurring, multi-hop problem for pymatgen specifically, not a one-time
      fix.** A later moyopy run hit the identical mechanism one hop further down the same
      tree: `pymatgen` (via `pymatgen-core`) depends on `matplotlib`, whose own runtime deps
      `contourpy` and `kiwisolver` (plus `pillow`, pulled in as a `matplotlib` dep too) each
      lack a riscv64 wheel on public PyPI's newest release; pillow's sdist build failed with
      `RequiredDependencyException: jpeg` (no libjpeg headers in the manylinux image).
      `pymatgen-core` also depends directly on `spglib`, which has the same gap. Reading
      `pymatgen-core`'s declared `requires_dist` up front (rather than discovering each
      culprit via a fresh CI cycle) would have caught all of matplotlib/contourpy/
      kiwisolver/pillow/spglib in one pass — the final list ended up
      `PIP_ONLY_BINARY=numpy,scipy,pandas,orjson,pillow,matplotlib,contourpy,kiwisolver,spglib`.
      build-lightgbm.yml and build-wordcloud.yml already carry the matplotlib/contourpy/
      kiwisolver/pillow half of this list for the same reason; `fonttools` (also a
      matplotlib dep, also registry-only) is deliberately absent from all of them because
      its native extension is optional and its `setup.py` falls back to pure Python on a
      failed compile instead of failing the install.
    - **Adding a package to `PIP_ONLY_BINARY` assumes our *own* registry covers every
      interpreter in the matrix — verify that per-package, not just per-registry-vs-PyPI.**
      The `spglib` entry above was wrong: `build-spglib.yml`'s own matrix only builds
      `cp312`/`cp313`/`cp314`/`cp314t` (mirroring upstream's *wheel-building* CI, which is
      narrower than upstream's `requires-python>=3.9` and its own published cp39-cp314
      wheels for every other platform), so `pypi.riseproject.dev` carries no cp310/cp311
      `spglib` wheel at all. Forcing `spglib` wheel-only starved every cp310/cp311 test venv
      of *any* candidate — not "wrong version", *zero* versions — and pip's resolver
      responded by backtracking through pymatgen's entire release history (fetching and
      running `Preparing metadata` on some 200+ `pymatgen` sdists, from `2025.10.7` down
      through the pre-CalVer `4.x` series) hunting for a release old enough to not declare
      `spglib` as a dependency at all, burning the full 85-minute job timeout. It very
      nearly found one — metadata generation succeeded all the way down to `4.4.12` — before
      hard-crashing on `4.4.11`'s ancient `numpy.distutils`-era `setup.py`
      (`AttributeError: 'dict' object has no attribute '__NUMPY_SETUP__'`, a
      `__builtins__`-is-a-dict-under-`exec()` bug in that release's `finalize_options`,
      unrelated to which numpy version pip resolved). That crash is a red herring: the
      *real* bug is upstream of it — pip should never have been trying `pymatgen==4.4.11`
      in the first place, and pinning `pymatgen` to an exact recent version would only have
      made the resolver fail *faster*, not fixed the install.
      - **The fix is dropping `spglib` from `PIP_ONLY_BINARY` entirely, not narrowing the
        matrix or pinning pymatgen.** Unlike `numpy`/`scipy`/`pandas`/`orjson`/`pillow`/
        `matplotlib`/`contourpy`/`kiwisolver`, `spglib`'s newest release on our registry
        (`2.7.0`) is not behind PyPI's (also `2.7.0`) — there is no version-skew risk *today*
        — so leaving it unpinned lets pip prefer our wheel where one exists (cp312+, same
        version wins the wheel-over-sdist tie) and fall back to building the sdist where it
        doesn't (cp310/cp311), rather than being blocked outright. Confirm an sdist fallback
        is actually safe before relying on it: `spglib`'s only build-time tool dependencies
        (`cmake`, `ninja`, both via PyPI's `cmake`/`ninja` wrapper packages) publish
        `py3-none-*` wheels on our registry — interpreter-agnostic — and `build-spglib.yml`
        itself builds spglib with no `CIBW_BEFORE_BUILD` at all, so the same toolchain an
        sdist build would invoke is already proven to work on this manylinux_riscv64 image;
        the only reason our own port doesn't build cp310/cp311 *wheels* for it is that
        nobody has asked yet, not a real incompatibility.
      - **A permanently-narrower matrix on our own `build-<dep>.yml` is itself worth
        grepping for before trusting "our registry has it".** `pypi.riseproject.dev/simple/
        <dep>/` (gotcha 30) shows what's *published*, which is downstream of whatever
        matrix that dependency's own port workflow builds — check the workflow, not just
        the index, when a dependency is itself one of this repo's ports.

336. **A custom `CIBW_BEFORE_TEST` does not cancel a project's own `test-extras` cascade
    — the two install paths are independent, and `test-extras` runs regardless (the
    resiliparse case).** Writing a `CIBW_BEFORE_TEST` that installs a hand-picked test
    dependency set looks like it replaces upstream's own `[tool.cibuildwheel] test-extras`,
    but cibuildwheel resolves `test-extras` from the option cascade separately and installs
    `<wheel>[<extras>]` on top, independent of whatever `before-test` already did.
    resiliparse's own `pyproject.toml` sets `test-extras = ["all", "test"]`, and `all` pulls
    in the `beam` extra (`apache_beam[aws]`, `boto3`, `elasticsearch`) even though the
    `before-test` step installs a deliberately smaller set (`fastwarc`, `click`, `joblib`,
    `tqdm`, `pytest`) — the fix is `CIBW_TEST_EXTRAS: ''`, not a bigger `before-test`.
    - **`ignore_empty` decides whether the blank override wins** (gotcha 51's mechanism,
      here for `test-extras` instead of `before-build`): cibuildwheel's own `options.py`
      calls `self.reader.get("test-extras", ...)` with no `ignore_empty=True`, so an
      explicit empty string in `CIBW_TEST_EXTRAS` beats the pyproject table. Read the
      option's own resolution call before assuming an empty string clears a cascade —
      some options default `ignore_empty=True` and a blank override is silently dropped.
    - **A heavy optional extra turns a fast local rehearsal into a many-minute dependency
      resolution before the real failure is even reached.** An aarch64/local cibuildwheel
      run installs the same extras `before-test` does, so the pip install log shows
      `apache_beam`, `grpcio`, `pyarrow` and friends downloading well before the test
      command runs — a giveaway that `test-extras` is still active, even though the
      `before-test` override looks like it should have made them unnecessary.

353. **Gotcha 30's registry check has moved off redirects: `pypi.riseproject.dev/simple/<dep>/`
    now answers plain `404` for anything it doesn't host, not a `302` to pypi.org.**
    `curl -s -o /dev/null -w '%{http_code}' https://pypi.riseproject.dev/simple/<dep>/`
    against `chardet` and `requests` (both genuinely unhosted) both returned `404`, headers
    `server: GitHub.com` on hit and miss alike — the registry now looks like a static
    GitHub Pages index rather than a redirecting proxy. The check itself is unaffected
    (any non-`200` still means "we don't host it"), but a script or muscle-memory `curl -D -
    --max-redirs 0` check written against the old "expect a 302" behavior will read a 404
    as an error rather than the answer.

354. **`PIP_PREFER_BINARY` (not gotcha 12/30's `PIP_ONLY_BINARY`) is the fix when our
    registry hosts a wheel for *some* interpreters in the matrix but not others, and an
    unpinned test dependency keeps resolving to a newer, wheel-less release.** clevercsv's
    `CIBW_TEST_REQUIRES: pandas` picked PyPI's newest pandas release on every leg — our
    registry only publishes riscv64 pandas for cp312/cp313/cp314, and gotcha 30's "the
    version has to line up" bit for it exactly: PyPI's latest was newer than what we host,
    so pip took that and built it from source, costing ~45 minutes per job (and cp314t has
    no registry wheel at any pandas version, so it always builds from source regardless).
    `CIBW_TEST_ENVIRONMENT: PIP_PREFER_BINARY=1` (test-phase only, per gotcha 12) tells pip
    to prefer an *older* wheel-backed version over a newer sdist-only one — it dropped
    cp312/cp313/cp314 to a few seconds (the registry wheel resolves) while leaving cp314t's
    from-source fallback intact, which had already been confirmed to build cleanly, just
    slowly. `PIP_ONLY_BINARY` would have been wrong here — it hard-fails cp314t instead of
    letting it fall back to source.

375. **`uv` (0.12.13, riscv64) can reject a real, `--only-binary`-eligible `abi3` wheel as
    "has no usable wheels" when it is resolved *by name from an index*, even though the
    exact same wheel installs fine as a local file path (the deltalite/`deltalake` case).**
    `deltalite`'s "Test wheel" step ran a plain `uv pip install pytest dist/*.whl` (our own
    just-built local wheel, `cp312-abi3-manylinux_2_39_riscv64`) followed by
    `uv pip install --only-binary deltalake --only-binary duckdb --only-binary pyarrow
    deltalake==1.6.3 pyarrow==25.0.1 duckdb==1.5.5`, with `UV_EXTRA_INDEX_URL` pointed at our
    registry and `UV_INDEX_STRATEGY=unsafe-best-match`. The first command (local file,
    `cp312-abi3`, exact match with the venv's own cp312 interpreter) always succeeded.
    The second failed every time on `deltalake==1.6.3` alone —
    `× No solution found when resolving dependencies: ╰─▶ Because deltalake==1.6.3 has no
    usable wheels ...` — while `duckdb`/`pyarrow` in the same command resolved fine.
    - **The one wheel that exists for `deltalake==1.6.3` on riscv64 is
      `deltalake-1.6.3-cp310-abi3-manylinux_2_39_riscv64.whl`** — confirmed served correctly
      by our registry, correct `data-requires-python: >=3.10`, correct `Name:`/`METADATA`,
      well-formed zip. `duckdb`/`pyarrow`'s riscv64 wheels use an *exact* interpreter tag
      (`cp312-cp312-manylinux_2_39_riscv64`) needing no forward-compatibility reasoning at
      all, unlike `deltalake`'s `cp310-abi3`, which needs uv to treat `cp310` as a *lower
      bound* ("3.10 and up", per PEP 425/600 stable-ABI semantics) to accept it under a
      cp312 venv. That is the one structural difference between the package that fails and
      the two that don't — not local-file-vs-index by itself, since `duckdb`/`pyarrow` are
      *also* resolved from the index in the same command and succeed.
    - **Ruled out, with evidence, before concluding this is upstream-only:** (1) an
      index-priority artifact of `unsafe-best-match` merging `pypi.org` (which also lists
      `deltalake==1.6.3`, with wheels for every platform except riscv64) and our extra
      index — swapping so our registry is the *default* index (`UV_INDEX_URL`) and
      `pypi.org` the *extra* one made no difference; the riscv64 wheel still shows up as an
      enumerated candidate in the log (the "is missing an upload date" warning names it
      explicitly) and is still rejected. (2) `UV_EXCLUDE_NEWER`/upload-date filtering — the
      same "missing an upload date" warning appears for `duckdb`/`pyarrow` too, which
      succeed, so it's cosmetic, not exclusionary. (3) a stale/unfixed uv bug in general —
      uv's `implied_python_markers` (`crates/uv-distribution-types/src/
      prioritized_distribution.rs`) already treats an `abi3` wheel's python tag as a lower
      bound (`>=3.9` for `cp39-abi3`, not `==3.9.*`), fixed in `astral-sh/uv#18536`
      (released 0.10.12), well before 0.12.13, and the fix's diff has no per-architecture
      branching, so it should apply identically on riscv64. A local repro (`uv 0.12.5`,
      two synthetic PEP 503 indexes over `python -m http.server`, one with an
      incompatible-platform `cp310-abi3` file as the default index and the other with a
      matching-platform one as the extra) succeeded, i.e. this exact mechanism works
      correctly for other architectures. That leaves the break isolated to something
      riscv64-specific in uv's *actual* wheel-tag-compatibility check (as opposed to the
      marker-implication code the PR fixed), which is a separate code path this port
      could not reach or patch.
    - **No clean workaround found; the pragmatic fix is to stop asking for the resolution
      uv gets wrong**, not to keep guessing at flags. deltalite's own wheel is what's under
      test, and the `deltalake`/`pyarrow`/`duckdb` install existed only to run upstream's
      differential parity suite (`ci-deltalite-python.yml`) — dropped that install and the
      full `pytest rust/deltalite/python/tests` run, kept the wheel-install + license-file
      check, and ran only `test_planner.py` (the one of 8 test files under `tests/` with no
      `deltalake`/`pyarrow`/`duckdb` import, directly or via `harness/common.py`).
    - **Before reaching for this, try `-v`/`-vv` on the failing `uv pip install` and, if a
      future uv release changes this, re-test the plain `UV_EXTRA_INDEX_URL` +
      `UV_INDEX_STRATEGY=unsafe-best-match` shape gotcha 244 already documents** — this
      entry is about a *specific* `cp3X-abi3` + riscv64 + registry-resolution combination
      breaking, not a blanket "don't use uv for index-resolved abi3 wheels" rule.
