# Gotchas — Testing: test-sources & shadowing

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/testing-and-shadowing.md`.

## In this file

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

---

21. **`python -s` (no-user-site) does NOT propagate to pytest-xdist workers.** A
    project whose `test-command` runs `python -s -m pytest -n4` to force importing
    the *installed* wheel over a local source tree has a latent bug on riscv:
    the `-s` flag sets `sys.flags.no_user_site=1` on the **controller**, but execnet
    respawns each `-n` worker **without** it (`no_user_site=0`). SQLAlchemy's
    `test/conftest.py` injects `{project}/lib` onto `sys.path` *unless* no_user_site
    is set — so on the workers pytest imports the **pure-Python source** (no `.so`),
    not the compiled wheel. Combined with gotcha 20's `REQUIRE_*_CEXT` (whose test
    plugin then asserts the extension is present) every worker hard-crashes at
    `pytest_sessionstart` → `RuntimeError: Unexpectedly no active workers available`.
    Fix: set no-user-site as the **`PYTHONNOUSERSITE=1` env var**, which xdist *does*
    inherit into workers, and scope it to the test phase (`CIBW_TEST_ENVIRONMENT`,
    gotcha 12) so it can't touch the build. Verify arch-independently on any host: a
    5-line `conftest.py` that prints `sys.flags.no_user_site` from inside a test,
    run under `python -s -m pytest -n2` — the workers report `0`, the env var flips
    them to `1`.

25. **Build-from-checkout + pytest = the repo's source package shadows the wheel you
    just built (the pymongo case; fix with `test-sources`).** In the
    build-from-checkout shape the importable package sits at the **repo root**
    (`bson/`, `pymongo/`), and cibuildwheel runs `test-command` from the checkout. If
    the suite is a *package* (`test/__init__.py` exists — check it), pytest's default
    prepend import mode puts the **rootdir** on `sys.path[0]`, so `import <pkg>`
    resolves to the source tree and never touches the installed wheel. The job goes
    green having tested pure Python — the exact failure gotcha 20 warns about, reached
    by a different route (there the `.so` was never built; here it was built and then
    not imported). Fix: `CIBW_TEST_SOURCES: test tools pyproject.toml` — cibuildwheel
    ≥3 copies just those paths into an empty temp cwd, so the shadowing source packages
    aren't there. Then use **paths relative to that cwd** in `CIBW_TEST_COMMAND`
    (`python -m pytest test/...`), not `{project}`/`{package}` (gotcha 5) — those
    still point at the full checkout. Stage `pyproject.toml` too or `[tool.pytest.ini_options]`
    is lost.
    - **Verify, don't assume** — same rule as gotcha 20's `unzip -l | grep '\.so$'`,
      one level up: assert the *import* is the compiled one. Many projects ship a
      ready-made probe (pymongo: `tools/fail_if_no_c.py`, which asserts `bson.has_c()`);
      chain it with `&&` ahead of pytest so a shadowed import is fatal.
    - **Reproduces on any host in 30 seconds**, no QEMU: two dirs with the same package
      name (one "SOURCE" at a fake repo root, one "INSTALLED" on `PYTHONPATH`) plus a
      `test/__init__.py` — run pytest from the repo root (imports SOURCE) and from a
      staged cwd holding only `test/` (imports INSTALLED).
    - Distinct from gotcha 21, which is about `python -s` failing to reach xdist
      workers and a conftest that *explicitly* injects a lib dir. This one is pytest's
      own rootdir insertion and needs no conftest cooperation at all.
    - While you're there, **pin floating test deps the same way gotcha 23 pins build
      tools**. A project with `filterwarnings = ["error", ...]` turns any new
      DeprecationWarning from a freshly-resolved plugin into a hard failure — pymongo
      needed `pytest-asyncio==1.3.0` (upstream's `uv.lock` version) because 1.4 made
      its own `event_loop_policy` override warn. Take the version from upstream's lock
      file, not from "latest".

36. **`test-sources` preserves each path's position relative to the project root —
    which is what makes `__file__`-relative fixture lookups survive the staging (the
    brotli case; see `build-brotli.yml`).** cibuildwheel (>=3, checked in 4.2.0
    `platforms/linux.py`) runs `test-command` in an **empty** temp dir, not in the
    checkout, and `copy_test_sources` copies each entry to `test_cwd/<same relative
    path>`. So a suite that locates its data by walking up from its own file —
    `project_dir = dirname(dirname(dirname(__file__)))` then `project_dir/tests/testdata`,
    a common unittest idiom — keeps working if you stage the sibling data at its original
    relative path: `CIBW_TEST_SOURCES: python/tests python/bro.py tests/testdata`.
    Stage the data under a flattened name and every lookup breaks.
    - **Choosing what *not* to stage is the shadowing fix (cheaper than gotcha 25's).**
      brotli's importable `brotli.py` lives in `python/` beside `python/tests/`; staging
      only `python/tests` leaves `test_cwd/python/` without it, so `import brotli` can
      only resolve to the wheel. Same reasoning applies to `unittest discover -s <dir>`,
      which inserts `<dir>` at `sys.path[0]` exactly like pytest's rootdir insertion —
      so what sits in that directory decides which copy gets imported.
    - **`setup.py test` is gone (removed in setuptools 72), so an upstream whose CI is
      `python setup.py test` needs translating, not copying.** Read the `test_suite`
      entry point and reproduce it directly — brotli's
      `test_loader.discover("python", pattern="*_test.py")` becomes
      `python -m unittest discover -s python -p '*_test.py'`. Closer to upstream than
      inventing a pytest invocation, and it needs no test-requires at all.

39. **Testing a unittest-native suite against the installed wheel: three traps past
    gotcha 25 (the dulwich case; see `build-dulwich.yml`).** `CIBW_TEST_SOURCES` stops the
    checkout's source package from shadowing the wheel, but a suite written to run against
    an *in-place* `build_ext -i` then breaks in three new ways.
    - **Fixture data resolved relative to the package, not the rootdir.** dulwich's
      *shipped* `dulwich/tests/utils.py` opens `<pkg>/tests/../../testdata`, and
      `tests/test_source.py` walks `<rootdir>/dulwich` — with only `tests/` staged, 95
      tests error. Staging the *installed* package into the test cwd fixes both at once
      and still exercises the compiled wheel:
      ```
      cp -a "$(python -c 'import <pkg>, os; print(os.path.dirname(<pkg>.__file__))')" <pkg>
      ```
      Keep gotcha 20's proof beside it (`python -c "import <pkg>._ext"`) — the copy is
      worth nothing if it has no `.so`.
    - **An upstream `test_suite()` callable can't be filtered, and pytest is not the way
      out.** `python -m unittest -k` has no negation and never reaches a suite built by a
      module-level callable. Switching to pytest as the filtering runner loses tests
      *silently*: **pytest never collects `__init__.py`, even when you name it explicitly**
      — dulwich keeps 591 of its 4620 tests in `tests/porcelain/__init__.py`, and only
      `-o python_files="test_*.py __init__.py"` sees them. Run upstream's exact suite minus
      one test with a flatten-and-filter one-liner instead (flattening preserves order, so
      `setUpClass` grouping survives):
      ```
      python -c "import sys, unittest, tests; flat = lambda s: [t for x in s for t in (flat(x) if isinstance(x, unittest.TestSuite) else [x])]; sys.exit(not unittest.TextTestRunner().run(unittest.TestSuite(t for t in flat(tests.test_suite()) if not t.id().endswith('.<test>'))).wasSuccessful())"
      ```
      Before switching runners at all, diff the two collections — `comm -13` over sorted
      test ids exposed the missing 591 in one run.
    - **The test phase runs as root, in a container that is not upstream's CI runner.**
      Two symptoms: a test asserting a mode-0 file is unreadable can never fail for root
      (deselect it), and tests shelling out to CLIs the image lacks *error* rather than
      skip — dulwich's `test_signature` needs `ssh-keygen`/`gpgsm`. Install those in
      `CIBW_BEFORE_TEST_LINUX` (`dnf -y install openssh-clients gnupg2-smime`) rather than
      deselecting: upstream's runners have them, so installing is the smaller divergence.
      And don't trust a local `docker run` of the image to settle what's present — the
      self-hosted riscv64 runner used an older cached `manylinux_2_39_riscv64` than a fresh
      `docker pull`, with `gpgsm` in one and not the other.

83. **A test that asserts on a traceback's *source text* passes only inside a source
    checkout, so `test-sources` staging is what breaks it (the fastavro case).** Gotchas 25/36
    stage a minimal test cwd precisely so the checkout cannot shadow the installed wheel. The
    bill for that arrives here: `traceback.extract_tb()` fills `FrameSummary.line` from
    **linecache**, and a Cython extension embeds the **relative** path of its `.pyx`
    (`fastavro/_write.pyx`, not an absolute one) as the code object's filename. linecache
    resolves that against the **current working directory**, so the source text is recoverable
    only when cwd happens to be a checkout carrying those sources — which is exactly what
    upstream's own `build_ext --inplace` CI provides and what a staged `test_cwd` deliberately
    does not. Against any installed wheel the frame reads back `line=''` and the assertion
    fails, on every architecture.
    - **Confirm the mechanism rather than the symptom, in two runs against the *released* PyPI
      wheel on your own host.** From an empty dir the frame is
      `filename='fastavro/_write.pyx' lineno=409 line=''`; create a decoy `fastavro/_write.pyx`
      of 500 numbered lines at cwd and the same frame reports `line='line 409'`. A traceback
      whose text is dictated by an unrelated file at cwd is proof the assertion is
      cwd-dependent, not arch-dependent — deselect it and say so.
    - **Read the *relativeness* of the filename, not just the failure.** An absolute path in
      the frame would survive any cwd and the test would be portable; a relative one is the
      signal that upstream assumes an in-place build. `python -c` over the installed wheel
      prints it in one line.
    - Generalises past Cython to anything that assertion-checks rendered traceback text
      (`format_exc()` output, `assert "foo = bar" in tb`) — the source line is never carried
      *in* the exception, it is looked up afterwards, so it is a property of the filesystem at
      raise-render time and not of your build.

87. **A test module that force-registers a synthetic package can never test an installed
    wheel (extends gotchas 25/36).** Gotcha 25's shadowing comes from pytest's rootdir
    insertion, and staging a minimal `test_cwd` fixes it. A stronger form is immune to that
    fix: a test that constructs the package object itself so it can run "without a build
    step" —
    ```python
    _thrift_pkg = types.ModuleType('thrift'); _thrift_pkg.__path__ = [_src_dir]
    sys.modules.setdefault('thrift', _thrift_pkg)
    ```
    Under `test-sources` the relative `_src_dir` is absent and the module dies with
    `ModuleNotFoundError: No module named '<pkg>.<sub>'`; stage the source next to it and it
    silently exercises the pure-Python tree instead of your compiled wheel. Either way it is
    not a wheel test — exclude it rather than staging more paths to satisfy it.
    - **Upstream's own test list is the arbiter, not the sdist's file list.** thrift ships
      `test_sasl_transport.py` in its sdist but `lib/py/Makefile.am`'s `check-local` never
      runs it — the confirmation that it is a source-tree-only unit test rather than coverage
      you dropped. A `Makefile.am`/`tox.ini`/`noxfile.py` target is worth reading in full
      before deciding which shipped test files belong in `CIBW_TEST_COMMAND`.

104. **`test-sources` is resolved against cibuildwheel's *cwd*, not against
    `package-dir` — which is what lets an sdist->bdist port run the checkout's test suite
    (the lightgbm case; see `build-lightgbm.yml`).** Gotcha 36 says `test-sources` preserves
    each path's position "relative to the project root". The root in question is
    `Path.cwd()` — `platforms/linux.py` calls `copy_test_sources(..., Path.cwd(), test_cwd)`
    just as it calls `container.copy_into(Path.cwd(), "/project")` — and cwd is wherever the
    cibuildwheel action runs, *not* the directory passed as `package-dir`. So the two can be
    different trees: check the upstream repo out at the workspace root, extract the sdist a
    job built earlier into a subdirectory, point `package-dir` at that, and still stage the
    checkout's `tests/`. The sdist needing to contain the tests is the constraint that made
    protobuf build a separate `protobuftests` wheel (gotcha 6); it is not actually a
    constraint.
    - **Stage the sibling data at its original relative path** — gotcha 36's rule, with a
      second reason to matter. lightgbm's tests read their training data as
      `Path(__file__).parents[2] / "examples" / ...`, so `CIBW_TEST_SOURCES: tests examples`
      is what reproduces the checkout's layout inside the otherwise empty `test_cwd`.
    - **Shadowing answers itself in this shape**: neither the checkout root nor the sdist's
      importable package reaches `test_cwd`, so `import <pkg>` can only resolve to the
      installed wheel. Nothing from gotchas 21/25 is needed.

111. **A build product made *inside* the container never reaches `test_cwd` — the trap side
    of gotcha 104 (the JPype1 case; see `build-jpype1.yml`).** 104 reads
    `copy_test_sources(..., Path.cwd(), test_cwd)` as an enabler: cwd is the host checkout,
    so it need not be the tree `package-dir` points at. The same line is a trap whenever the
    build *generates* something the suite needs, because the staging is a fresh copy of your
    `actions/checkout` and not of the tree the build just ran in. JPype1's CMake build shells
    out to Apache Ant to compile a Java test harness into `test/classes/`, which its conftest
    loads as `Path(__file__).parent / '../classes'`; staged through `test-sources` the whole
    1670-test suite cannot start a JVM. Fix: don't stage anything, and run upstream's own
    invocation against the in-container checkout —
    `CIBW_TEST_COMMAND: cd {project}/test && python -m pytest ...`.
    - **`cd` into a *subdirectory* of the checkout is its own shadowing fix**, and usually
      the one upstream already uses (jpype's azure step is commented "cd to test first, so
      avoid to import jpype from the project working dir"). `python -m pytest` puts the cwd
      on `sys.path[0]`, and that cwd is `{project}/test`, which does not contain the
      importable package — so `import jpype` can only reach the installed wheel. The proof is
      free: the checkout's `jpype/` holds no compiled `_jpype` (scikit-build-core stages the
      extension into the wheel, never in place), so importing the source would error the
      suite outright rather than pass quietly. Contrast gotcha 25, where the suite sits *at*
      the root and only an empty staged cwd can save it.
    - **`--deselect` prefixes match the nodeid, which is relative to the pytest *rootdir*,
      not to the directory you run from** — the precise rule behind gotcha 14's "path-based
      deselect silently no-ops". Running from `{project}/test` while `pyproject.toml` sits
      at `{project}` puts rootdir at the checkout, so `--deselect jpypetest/t.py::C::x`
      matches nothing while `--deselect test/jpypetest/t.py::C::x` deselects it — *even
      though the short summary prints the short form*, which is what makes the wrong
      spelling so convincing. Never trust either without reading the `N deselected` count
      back.
    - **A Java-side test dependency needs the same riscv64 check as a Python one, and the
      JDK is pinned by the base image.** jpype stages JDBC drivers with Apache Ivy
      (`ivy.xml`, resolved by a dedicated upstream CI stage); upstream's pinned `sqlite-jdbc`
      3.27.2.1 bundles `org/sqlite/native/Linux/<arch>/libsqlitejdbc.so` for nine arches and
      no riscv64, so its 87 tests fail outright rather than skip — 3.46.1.3 is the first
      release carrying one, and `unzip -l <jar> | grep riscv64` answers it per version.
      Rocky 10, the `manylinux_2_39_riscv64` base, packages only `java-21-openjdk-devel` plus
      `ant` in appstream (`java-11-`/`java-17-openjdk-devel` do not resolve), so an upstream
      recipe naming an older JDK has to be bumped — one line in the workflow, not a patch.
      `dnf -q list <pkg>` in `rockylinux/rockylinux:10` under `--platform linux/riscv64`
      settles availability in a minute (gotcha 51), and a five-line JDBC `main()` under QEMU
      proves the native library actually loads before you spend a CI cycle.

119. **A local `test-sources` rehearsal lies if any ancestor of your staging dir holds a
    config file (the time-machine case).** Gotchas 25/28 tell you *whether* to stage
    `pyproject.toml`; this is about the local check that answers that question quietly
    giving the wrong answer. cibuildwheel runs `test-command` in an empty `test_cwd` with
    nothing above it, but your local mock-up sits inside a scratch tree — and pytest's
    rootdir search walks **up** until it finds `pyproject.toml`/`setup.cfg`/`tox.ini`, so
    the copy of the project's own `pyproject.toml` you curled for the playbook's step-2
    inspection, sitting one directory above, gets picked up and the run passes with config
    the container will not have. time-machine's suite went green that way locally and then
    failed **all four** riscv64 jobs with `fixture 'testdir' not found`, because upstream's
    `addopts = ["-p", "pytester"]` never reached pytest in the container.
    - **Read the session header, not just the summary line.** `rootdir:` and `configfile:`
      are printed on every run; if `rootdir` is not the directory you staged, the rehearsal
      is invalid and proves nothing. The same check catches an inherited `conftest.py`.
    - **Keep downloaded upstream files out of the parent chain** — give the inspection copy
      its own subdirectory, or stage the test cwd somewhere with nothing above it.
    - **`[tool.pytest]` is a real table, not a typo for `[tool.pytest.ini_options]`.**
      pytest 9 reads the new-style `[tool.pytest]` table, so grepping a project for
      `ini_options`, finding none, and concluding its `pyproject.toml` carries no pytest
      config is wrong — and that config may be the only thing loading a plugin the suite
      needs.

148. **The test suite lives *inside* the importable package, so `test-sources` cannot
    separate them — rename the staged package directory in the test command (the
    fastparquet case; see `build-fastparquet.yml`).** Gotcha 36's shadowing fix is
    choosing what *not* to stage; that only works when the suite is a sibling of the
    importable package. When the suite is `<pkg>/test/` **and** its fixtures are resolved
    from the working directory (`TEST_DATA = "test-data"`, joined with no `__file__`
    anchor), you are forced to stage both `<pkg>/test` and `test-data` at their original
    relative paths (gotcha 36) — which recreates a `<pkg>/` directory in `test_cwd` that
    pytest's rootdir insertion turns into a namespace package shadowing the wheel.
    Upstream usually already has the answer in its *wheel-test* job: fastparquet's
    `test_wheel.yaml` does `mv ./fastparquet ./fastparquet-src` before pytest, with the
    comment "in order to avoid conflicts between the fastparquet directory and the
    fastparquet installed module". Reproduce it verbatim in `CIBW_TEST_COMMAND`:
    ```yaml
    CIBW_TEST_SOURCES: fastparquet/test test-data pyproject.toml
    CIBW_TEST_COMMAND: mv fastparquet fastparquet-src && python -m pytest fastparquet-src/test
    ```
    The rename keeps the relative-import package (`test/__init__.py` → `from .util import
    tempdir`) intact, keeps `test-data` where the suite looks for it, and leaves nothing
    named `<pkg>` on `sys.path[0]`.
    - **Read upstream's wheel-test workflow, not only its main CI.** Projects that test
      wheels separately (`test_wheel.yaml` beside `wheel.yml`) have already solved
      "installed wheel vs source checkout" for you, and copying their solution is both
      less thinking and less divergence than inventing one. Their main CI job usually
      does `pip install -e .` and hits none of this.

151. **A test runner that *discovers* work by walking `<testdir>/..` fails silently, not
    loudly, when `test-sources` under-stages — count the tests, don't read the exit code
    (the biopython case; see `build-biopython.yml`).** Gotchas 25/36/39 all treat
    `CIBW_TEST_SOURCES` as a shadowing fix and reach for minimal staging. The opposite
    failure is quieter: biopython's `Tests/run_tests.py` builds its doctest list with
    `setuptools.find_packages(testdir + "/..")` and resolves fixtures through `../Bio` and
    `../Doc`, so `CIBW_TEST_SOURCES: Tests` leaves the parent directory empty, collects
    **209** tests instead of 501, and — because a suite of this shape *skips* whatever it
    cannot import — exits 0 on a subset you never chose. Staging `Tests Bio BioSQL Doc`
    reproduces upstream's checkout layout and collects 501. Measure the count at each
    staging choice against the released PyPI wheel (gotcha 52) and keep the number in the
    commit message; it is the only evidence the job tests what you think it does.
    - **Staging the *source* package alongside the tests is safe here, and is the
      closest-to-upstream answer** — precisely because such a runner `os.chdir`es into
      `Tests/` and `sys.path[0]` is the script's own directory, so `import <pkg>` still
      resolves to the wheel. That is upstream's own arrangement (`pip install .` leaves an
      unbuilt `Bio/` at `Tests/..`), so reproducing it wholesale beats hand-picking data
      subdirectories.
    - **But the *directory each command runs from* decides shadowing, so put your
      extension probe inside the same `cd`.** A `python -c "import <pkg>..."` executed at
      the `test_cwd` root puts `''` on `sys.path[0]`, and the staged source wins —
      biopython's probe died with `ImportError: cannot import name '_aligncore' from
      partially initialized module`, which reads like a broken wheel and is not. Write the
      test command as one chain, `cd Tests && python -c "<probe>" && python run_tests.py`,
      and verify by printing `<pkg>.__file__` from that directory.

152. **An sdist's `tests/` directory can be a partial copy — count the files before you
    pick the sdist as your test source (the geventhttpclient case).** Gotcha 6 asks whether
    the tests ship in the sdist at all; the quieter answer is "some of them". A `MANIFEST.in`
    that never mentions tests still yields a `tests/` entry in the tarball, because setuptools
    auto-includes files matching `test*.py` — and *only* those. geventhttpclient 2.3.9's sdist
    carries all twelve `tests/test_*.py` and none of `__init__.py`, `common.py`, `conftest.py`
    or the TLS fixtures, so every module doing `from tests.common import ...` dies at
    collection with `ModuleNotFoundError: No module named 'tests.common'`. That reads like a
    missing test dependency or a staging mistake (gotcha 25) and is neither.
    - **`diff <(tar tzf sdist.tar.gz | grep tests/) <(tar tzf tag.tar.gz | grep tests/)`
      settles it in one command**, before any venv. The signature is a residue that is exactly
      the `test*.py` glob: no `__init__.py`, no `conftest.py`, no data files.
    - **It also decides the port's shape**: only a checkout can run the real suite, so the
      build-from-checkout form is mandatory even where an sdist->bdist job would otherwise be
      natural — and gotcha 104's "stage the checkout's tests beside an sdist `package-dir`"
      trick is the alternative when you need both.
    - Reach for it as the first explanation whenever gotcha 52's dry run against the released
      PyPI wheel returns collection errors on *helper* imports while the same files run fine
      from a git checkout.

174. **A `<pkg>/` directory at the checkout root is only a shadowing hazard when it holds
    an `__init__.py` (bounds gotchas 25/36/148).** Those three all treat a same-named
    directory beside the tests as something to stage away from, and reach for
    `CIBW_TEST_SOURCES` or a rename to do it. The rule is narrower than that: `PathFinder`
    treats a directory *without* `__init__.py` as a namespace **portion**, which it records
    and then keeps scanning `sys.path` for a concrete loader — a real module or extension
    found at any later entry wins, and the namespace package is only materialised when
    nothing else matches. So a checkout root carrying `<pkg>/` purely as a typing stub
    holder (`__init__.pyi` + `py.typed`, packaged alongside a top-level
    `Extension("<pkg>", ...)` — ciso8601's layout, and a common one for C extensions that
    want inline types) cannot shadow the installed wheel, however the tests are run.
    - **`ls <pkg>/__init__.py` is the whole check**, and it is worth doing before adding
      staging or a rename you do not need — both are divergence, and a rename in
      particular breaks relative imports inside the suite.
    - **The inverse still holds and is the common case**: gotcha 25's `test/__init__.py`
      and gotcha 148's `<pkg>/test/` are regular packages, so the directory *is* a concrete
      loader and does win.
    - Confirm rather than reason about it: `python -c "import <pkg>; print(<pkg>.__file__)"`
      from the directory in question, on any host, in one second — and keep that as the
      test command's first link (gotcha 20) so a regression is loud.
