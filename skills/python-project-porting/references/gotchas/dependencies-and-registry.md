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
