# Gotchas — Testing: pytest config, servers & test selection

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/pytest-config-servers-and-selection.md`.

## In this file

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

---

6. **Running a real test suite through cibuildwheel:**
   - Stage helper files inside the package dir (cibuildwheel copies that tree into
     the container); reference them via `{package}`.
   - `CIBW_TEST_REQUIRES: <deps>` and `CIBW_TEST_COMMAND: bash {package}/.../run.sh`.
   - `CIBW_ENVIRONMENT_PASS_LINUX: PIP_EXTRA_INDEX_URL` + set
     `PIP_EXTRA_INDEX_URL: https://pypi.riseproject.dev/simple/` so test deps that
     lack riscv64 wheels on public PyPI (e.g. numpy) resolve from our registry
     inside the container. (build-onnx.yml uses the same mechanism.)
   - **Check whether tests ship in the sdist.** protobuf's don't — upstream builds a
     separate `protobuftests` wheel (`py3-none-any`, via Bazel
     `//python/dist:test_wheel`, not published to PyPI) that bundles the `*_test.py`
     files + generated test protos. Build it alongside the sdist on x86, upload it as
     a second artifact, install it in the test step. Then discover+run like upstream:
     ```bash
     tests="$(pip show -f protobuftests | grep _test.py \
       | grep -v -e _pybind11_test.py -e proto_api_test.py \
       | sed 's,[/\\],.,g' | sed -E 's,.py$,,g')"
     rc=0; for t in $tests; do python -m unittest -v "$t" || rc=1; done; exit $rc
     ```
   - **The easy inverse: the sdist bundles both its tests and the `[tool.cibuildwheel]`
     config** (apache-tvm-ffi ships `tests/` + `test-command`, `test-groups`,
     `build-frontend`). Passing the sdist as `package-dir` inherits all of it unchanged
     — you get upstream's exact test invocation for free and only add the riscv
     overrides (`CIBW_ARCHS`, image, registry env; see gotchas 12–14). GPU-only tests
     usually self-skip via `torch.cuda.is_available()`.
   - Collect **all** failures per run (`|| rc=1`), don't stop at the first — each CI
     cycle is expensive, so surface the whole list. For genuinely-incompatible tests,
     exclude with an explicit justification comment (build-onnx.yml documents its
     skipped `maxpool` test this way).

48. **A package whose runtime dependency tree doesn't exist on riscv64 is still
    portable — smoke-test the extension modules off disk instead of importing the
    package (the sglang case).** Gotchas 20/25/28 all assume `import <pkg>` works, so the
    compiled `.so` is reachable through the package. Some ports can never satisfy that:
    sglang's `pyproject.toml` lists ~300 runtime dependencies (torch, flashinfer, the
    CUDA stack), so no importable environment exists on riscv64 at all. That is not a
    reason to skip the port — the wheel's value is its PyO3 `cdylib`s, and those can be
    exercised directly off the unpacked wheel
    (`python -m zipfile -e dist/*.whl unpacked/`):
    ```python
    loader = importlib.machinery.ExtensionFileLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    ```
    Assert the *set* of `.so` names found equals the expected one: that is gotcha 20's
    "the extension is really in the wheel" proof plus a real dynamic-link and module-init
    check (unresolved symbols and a broken `PyInit` both fail here), with no package
    import.
    - **A multi-hour build is a shared-infrastructure decision, not only yours.**
      sglang's cargo workspace needs >1.5h per interpreter at
      `opt-level=3`/`codegen-units=1`, times four jobs, on the handful of
      `ubuntu-24.04-riscv` runners every other open port is queued on. Maintainers
      cancelled the run twice and **deleted the `Trigger:` line from the PR
      description**. A stripped `Trigger:` line or a human-cancelled run is a stop
      signal, not a flake — re-adding it just takes the runners back. Land the
      workflow, report plainly that CI was never proven green, and leave the dispatch
      to the maintainers.

64. **A daemon that refuses to run as root is usually a packaging question, not a patch
    (the mysql-connector-python case), and QEMU cannot verify it locally.** Gotcha 39 notes
    the test phase runs as root in the container. When the suite bootstraps a *server* that
    refuses to start as root, patching in `--user=root` is the tempting fix, but check two
    things first: (a) what upstream actually does — mysql-connector-python's `CONTRIBUTING.md`
    says the suite can bootstrap a server or use an external one and that the external one is
    **preferred**, with a `--use-external-server` flag, which is precisely why upstream never
    hits this; and (b) whether the distro's *server* package exists for riscv64 — Rocky 10
    ships `mysql8.4-server` and `mariadb-server` for riscv64, and installing either creates the
    `mysql` system user (uid 27), so `mysqld --user=mysql` needs no patch at all.
    - **File capabilities make a local QEMU check impossible, and the error looks like a
      broken build.** `/usr/libexec/mysqld` carries `cap_sys_nice=ep`; QEMU user-mode emulation
      cannot honour file caps, so `exec` fails with a bare
      `/usr/sbin/mysqld: Operation not permitted` while every other binary from the same RPM
      runs fine. That asymmetry — one binary failing to exec, its siblings working — is the
      tell. Confirm with `rpm -q --filecaps <pkg> | grep <binary>` rather than concluding the
      package is broken on riscv64, and verify on the real runner (gotcha 9's fallback).

74. **A file capability makes a binary unexecutable inside the build container
    (`Operation not permitted` on `execve`, as root).** Distro packages routinely carry
    capabilities — `mysqld` ships `cap_sys_nice=ep` — and when the container's
    capability bounding set does not include the capability, `execve` fails with
    **EPERM**, not EACCES, and with no message naming capabilities. It reads like a
    corrupt binary or a mount problem; `getcap` settles it in one command:
    ```bash
    getcap /usr/libexec/mysqld           # -> cap_sys_nice=ep
    setcap -r /usr/libexec/mysqld        # needs `dnf install libcap`
    ```
    Do the `setcap -r` in `CIBW_BEFORE_TEST_LINUX` (or `BEFORE_ALL`) beside the
    `dnf install` that put the binary there. Dropping a scheduling-priority capability
    costs nothing in a throwaway container.

75. **Running upstream's suite against a real server the distro also ships is often
    cheaper than it looks — but scope it, and stop the harness rebuilding the thing
    under test.** A database/driver port whose test harness bootstraps its own server
    (`tests/mysqld.py` + `unittests.py --with-mysql=<basedir>`) is usually written for a
    developer machine, and three things stand between it and a container:
    - **It runs as root.** Servers that refuse root (`mysqld`: *"Please read Security
      section of the manual to find out how to run mysqld as root!"*) need an explicit
      `--user=root`, in *both* the bootstrap argv and the generated option file the
      started server reads back via `--defaults-file`. That is a two-line
      `Inappropriate` patch, and cheaper than making cibuildwheel's test phase drop
      privileges (its venv and temp dirs are mode-700 root).
    - **`CIBW_ENVIRONMENT` reaches the test phase (gotcha 12), and a harness that
      reinstalls the project in-tree will use it.** `unittests.py` runs
      `setup.py install` into `build/testing` and prepends that to `sys.path`; with the
      build's `MYSQL_CAPI` still set it recompiles the extension there and **shadows the
      wheel's**. Clear the build-only variables for tests —
      `CIBW_TEST_ENVIRONMENT: MYSQL_CAPI= SKIP_VENDOR= EXTRA_LINK_ARGS=` (cibuildwheel
      layers `test_environment` on top of `environment`, `platforms/linux.py`) — and
      assert what actually got imported:
      `assert 'site-packages' in m.__file__, m.__file__`.
    - **Select the modules that test your delta.** The full suite here was 1318 tests
      with 19 failures — all TLS-cipher and unix-socket cases, artefacts of testing
      against the distro's older server rather than the version upstream targets, and
      all reproducing on aarch64. Harnesses of this kind have module-level selection
      (`--test-regex '^cext_'`) but no pytest-style deselect, so a module regex is the
      only lever: run the C-extension modules (87 tests, seconds) and report the
      full-suite numbers in the PR rather than shipping a knowingly red job or a
      hand-maintained exclusion list.

82. **A `pytest.skip()` raised from inside the generator that feeds `@parametrize`
    deletes the whole module, and the run stays green (the fastavro case).** pytest consumes
    that generator at *collection* time, so the `Skipped` exception propagates out of module
    collection rather than out of one test — every test in the file disappears, including the
    ones that never touched the missing dependency, and the summary line says `1 skipped`.
    Nothing in the output names the module or the count you lost. That makes an "optional"
    test dependency load-bearing: fastavro's `_test_files()` skips when the snappy codec is
    absent, and dropping `cramjam` (no riscv64 wheel anywhere, so it builds from its maturin
    sdist) would have silently taken **152 of 709 tests** — most of the core reader/writer
    coverage — off a green job.
    - **Reproduce in 30 seconds on any host**, no QEMU: a `_cases()` generator that calls
      `pytest.skip()` on one value, plus a second unrelated test in the same module. With the
      dep present the file reports `4 passed`; without it, `1 skipped`. The 4 -> 1 collapse
      *is* the whole tell.
    - **So compare collected counts across the dependency, never just the exit status.** This
      is the counterpart to gotcha 39's `comm -13` diff of test ids: there the runner changed,
      here the dependency set did, and both fail by quietly collecting less.
    - **Weigh that against the cost of the dep before trimming `CIBW_TEST_REQUIRES`.** Gotcha
      52's dry-run against upstream's released PyPI wheel prices this out directly — it shows
      the pass/skip counts each candidate dependency list actually produces. A `pytest.importorskip`
      at module top has the same collapsing effect and is easier to spot; the generator form is not.
    - pytest warns `Passing a non-Collection iterable to parametrize is deprecated`
      (`PytestRemovedIn10Warning`), so this shape is on its way out — but it is still what
      released suites ship today.

88. **An upstream `CIBW_TEST_COMMAND` that shells out to `tox` has to be translated, not
    copied — and `tox-direct` caps tox below 4 (the lazy-object-proxy case).** Projects
    generated from ionelmc's `cookiecutter-pylibrary` (lazy-object-proxy, hunter, and
    friends) run their cibuildwheel tests as
    `cd {project} && tox --skip-pkg-install --direct-yolo -e py3XX-nocov`. Copying that
    line drags in `tox-direct`, whose metadata is `tox (<4,>=3.12)`, so `pip install tox
    tox-direct` silently downgrades to the 2023-era tox 3 inside the container — on the
    newest interpreters in our matrix that is its own failure mode, and it buys nothing.
    Read the testenv instead and run its `commands` line directly: `nocov: {posargs:pytest
    -vv --ignore=src}` becomes `CIBW_TEST_COMMAND: cd {project} && pytest -vv --ignore=src`.
    Same reasoning as gotcha 36's `setup.py test`, one layer up.
    - **`deps` in `[testenv]` is not the list of test requirements.** tox envs habitually
      install the author's whole dev shelf; only what the suite actually imports belongs in
      `CIBW_TEST_REQUIRES`. lazy-object-proxy's env lists `pytest pytest-benchmark Django
      objproxies==0.9.4 hunter setuptools setuptools_scm`, but `Django`/`objproxies` are
      reached only through `pytest.importorskip` from fixture params upstream has commented
      out, and `hunter` — which has no riscv64 wheel and would compile Cython in-container —
      is imported nowhere under `tests/`. `grep -n 'import\|benchmark' tests/*.py` settles
      the whole list in one command; `pytest-benchmark` stayed because a `benchmark` fixture
      and a `pytest.mark.benchmark` are used and `--strict-markers` is on.
    - **A src-layout project needs no `test-sources` for this** (contrast gotcha 25): the
      importable package lives in `src/`, which pytest's rootdir insertion does not put on
      `sys.path`, so `cd {project}` cannot shadow the installed wheel. Confirm with
      `python -c "import <pkg>; print(<pkg>.__file__)"` before pytest rather than assuming.

92. **A root `conftest.py` that imports the world is optional — `test-sources` decides
    whether pytest ever sees it (the pyiceberg case; see `build-pyiceberg.yml`).** Gotcha 25
    reaches for `CIBW_TEST_SOURCES` to stop the checkout shadowing the wheel, and gotcha 36
    notes that *what you leave out* is half the tool. The third use is the cheapest: pytest
    only auto-loads a `conftest.py` that exists on the path from its rootdir down to the
    test file, so a conftest you do not stage is a conftest that never runs. Upstream wheel
    jobs commonly test **one** module (pyiceberg's runs `pytest tests/avro/test_decoder.py`,
    which imports the Cython `CythonBinaryDecoder` directly) while `tests/conftest.py`
    imports `boto3`, `moto` and `pytest-lazy-fixture` at module level for the *other*
    thousands of tests. Staging `tests/avro/test_decoder.py pyproject.toml` instead of the
    whole `tests` tree drops that dependency tree entirely — `CIBW_TEST_REQUIRES` collapses
    to upstream's `pytest` pin — and keeps `[tool.pytest.ini_options]` (gotcha 28: check
    `addopts` first).
    - **Prove the module needs no fixture from it before you drop it**, in 30 seconds on any
      host and with no QEMU: copy just that file plus `pyproject.toml` into an empty dir,
      `pip install <pkg>==<ver>` from PyPI, and run it (gotcha 52's dry-run, narrowed). A
      missing fixture shows up as an `E fixture '<name>' not found`, not as a silent skip.
    - **The same run tells you where the real ceiling is.** Widening to the sibling modules
      in that directory failed on `import pyiceberg.io.pyarrow`, and pyarrow has no riscv64
      wheel on PyPI or on our registry (gotcha 30) — so "run more of the suite" was settled
      by one local command rather than by a multi-hour riscv64 cycle.
    - **Mirror upstream's own interpreter cap while you are reading their wheel job.**
      pyiceberg's sets `CIBW_PROJECT_REQUIRES_PYTHON: ">=3.10,<3.14"` and
      `CIBW_SKIP: "cp3*t-*"`, and the classifiers stop at 3.13 — so the matrix is
      `[cp312, cp313]`, not the repo default. Building `cp314`/`cp314t` there would ship
      riscv64 an interpreter upstream ships on no platform, which is the goal-2 divergence,
      not extra coverage.

94. **Upstream's wheel jobs testing nothing is not a reason to ship an import-only
    smoke test — check whether the service its real suite needs is packaged for riscv64
    (the pyodbc case; see `build-pyodbc.yml`).** A database/broker/server client library
    typically splits its CI in two: cibuildwheel jobs with no `test-command` at all, and a
    separate workflow that gets the servers as GitHub Actions `services:` on
    `ubuntu-latest` — which the self-hosted riscv64 runner cannot provide. Copying the
    wheel job verbatim then yields a green build that never executed a line of the
    extension. The recoverable middle ground is to start the service **inside the
    cibuildwheel container** in `before-test`: Linux builds run every phase in one
    container, so a daemon started there is still up for `test-command`. pyodbc's suite
    needs SQL Server, PostgreSQL and MySQL; Rocky 10 ships `postgresql-server` *and*
    `postgresql-odbc` for riscv64, so one of the three upstream test files runs unmodified
    (40 tests: connect, DDL, every type binding, unicode/bytea fenceposts, `executemany`,
    transactions) against a server in the container.
    ```yaml
    CIBW_BEFORE_TEST_LINUX: >-
      dnf -y install postgresql-server postgresql-odbc &&
      install -d -o postgres -g postgres /run/postgresql /var/lib/pgsql/data &&
      su postgres -c "/usr/bin/initdb -A trust -D /var/lib/pgsql/data" &&
      su postgres -c "/usr/bin/pg_ctl -D /var/lib/pgsql/data -l /tmp/pg.log -o '-c listen_addresses=127.0.0.1' -w start" &&
      su postgres -c "/usr/bin/createdb test"
    ```
    - **The client-side plugin usually registers itself** — installing `postgresql-odbc`
      drops a `[PostgreSQL]` stanza into `/etc/odbcinst.ini`, so `odbcinst -q -d` lists it
      with no config of our own. Check that before hand-writing a driver config, and use
      the distro's name (`DRIVER=PostgreSQL`) rather than the Debian one upstream's CI uses
      (`{PostgreSQL Unicode}`); **avoid the braces** in `CIBW_TEST_ENVIRONMENT` anyway,
      since `{...}` is cibuildwheel's placeholder syntax elsewhere (gotcha 5).
    - **Everything here is verifiable locally in one `docker run`** — the whole recipe
      (dnf, `pip wheel`, `initdb`, 40 tests) finished under QEMU riscv64 in the manylinux
      image before the first push, gotcha 9's discipline applied to the *test* environment
      rather than the build.
    - Related to gotcha 64 (a daemon refusing to run as root is a packaging question):
      here `su postgres` plus `install -d -o postgres` is the whole answer, because the
      `postgres` system user comes from the RPM.

108. **A `test-command` carrying `-W error` needs the project's pytest ini staged, or
    collection dies on unregistered marks (refines gotchas 25/28).** Gotcha 25 stages
    `pyproject.toml` so `[tool.pytest.ini_options]` survives, gotcha 28 warns that doing
    so can import a hostile `addopts`. The third case: a suite that ships *inside* the
    wheel and is run with `--pyargs` needs no staging at all for imports (gotcha 49) —
    but cibuildwheel's empty `test_cwd` then has no rootdir, so the ini is not read, its
    `markers = ` list is not registered, and every `@pytest.mark.<custom>` raises
    `PytestUnknownMarkWarning`. Harmless normally; fatal under `-W error`, which is
    exactly what upstreams that set `filterwarnings = error` pass on the command line.
    spaCy: `python -m pytest --pyargs spacy -W error` collects 57 errors in an empty cwd
    and runs clean with `CIBW_TEST_SOURCES: setup.cfg`. The ini file is whichever one
    holds the config — `setup.cfg` (`[tool:pytest]`), `pytest.ini`, or `pyproject.toml`
    — and staging just that one file adds nothing that can shadow the wheel.
    - **Costs 30 seconds to check on any host**, no QEMU: `pytest --pyargs <pkg> -W error
      --collect-only` from an empty directory versus from one holding the ini file.

109. **A dry run on a networked host cannot tell you which tests "need no server" — run
    the selection under `docker run --network none` (the temporalio case).** When a suite
    stands up its own backend by *downloading a prebuilt binary at test time* (temporalio's
    `WorkflowEnvironment` pulls the Temporal dev server from `temporal.download`), the
    server-dependent tests are invisible in a local dry run: on macOS or x86 the download
    succeeds, the server starts, and they pass. Gotcha 85's "dry-run the test phase" is
    still right, it just has to be run **without a network**, or the riscv64 job is the
    first thing that ever exercises the claim — a 100-minute Rust build followed by
    `RuntimeError: Failed starting Temporal dev server: Unsupported arch: riscv64` x173.
    - **Two `docker run`s and a volume**, no QEMU: one *with* network to `pip install` the
      wheel plus the test requires into a venv in a named volume, one with
      `--network none` mounting that volume and the checkout read-only to run the exact
      `CIBW_TEST_COMMAND`. On aarch64 this reproduced the riscv64 job's counts to the test
      (228 passed, 8 deselected, 173 errors) in 12 seconds, and `grep -oE '^ERROR
      tests/[^ ]+' | sed 's/::.*//' | sort | uniq -c` turns that into the module list.
    - **Static analysis under-counts.** Scanning for tests whose signature names the
      `client`/`env` fixture misses everything that reaches the fixture indirectly (a
      package-level `conftest.py` fixture, a fixture-of-a-fixture) — here it found 6 of
      173. Fixture closures and helper-constructed environments only show up when the
      thing actually cannot start.
    - **Prefer dropping whole modules to deselecting nodes.** 15 of 21 `tests/nexus`
      modules were entirely server-dependent; listing the 6 that survive is far shorter
      than 173 `--deselect`s, and costs only the handful of passing tests stranded inside
      the dropped modules (9 of 228 here) — say the number in the PR rather than growing
      the command.
    - Distinct from gotcha 35/41's `not-feasible` triage: the missing riscv64 binary is
      the suite's *test harness*, not anything the wheel ships, so the port is unaffected.

110. **A conftest that `pytest.exit()`s on a missing credential env var hides the
    service-free subset entirely (the oracledb case; refines gotcha 109).** Gotcha 109
    partitions a suite by running it with no server reachable — which only works if the
    suite *runs*. Database-driver suites commonly validate credentials at session start:
    python-oracledb's `tests/conftest.py` resolves `MAIN_PASSWORD` through a helper whose
    `required=True` branch is `pytest.exit(msg, 1)`, so with no `PYO_TEST_*` set you get
    `no tests ran` and nothing to partition, which reads like "every test needs a
    database". Set the variable to any dummy value (`PYO_TEST_MAIN_PASSWORD=unused` via
    `CIBW_TEST_ENVIRONMENT`): the session then builds and only the fixtures that actually
    open a connection fail, one test at a time.
    - **The partition falls out of a single `-rA --tb=no` run** against upstream's
      released wheel (gotcha 52's dry run):
      `awk '{split($2,a,"::"); print a[1], $1}' | sort | uniq -c` groups the
      PASSED/FAILED/ERROR lines by module, and the modules that are 100% PASSED are the
      service-free ones. oracledb: 342 of 2808 tests pass with no database, 324 of them
      in five modules (module attributes, type objects, connect-param parsing,
      pool-param parsing, tnsnames.ora parsing) — all of which live in the compiled
      Cython extensions, so they are worth running. Name those modules in
      `CIBW_TEST_COMMAND` and `-k "not <test>"` the one straggler inside them that opens
      a connection.
    - **Upstream shipping no wheel tests at all is not licence to ship untested.**
      python-oracledb's release workflow only builds — there is no database in their CI
      either — so there is nothing to mirror, and the service-free subset is the only
      thing that proves the riscv64 extension works. Say which modules and how many tests
      in the PR, since a reviewer cannot tell a deliberate subset from an accident.
    - **A hard *runtime* dependency with no musl riscv64 wheel settles musllinux on its
      own** (the reason clause gotcha 30 asks for): oracledb requires cryptography, our
      registry hosts it for manylinux only, so a musl wheel could be neither installed
      nor tested. That is a one-line justification in the workflow header, not a
      judgement call.

128. **A release tag's test suite may never have been run by upstream CI — check the
    trigger before you debug the failure.** The common release layout is a wheel
    workflow on `push: tags:` and a test workflow that *excludes* tags (srsly's
    `tests.yml` has `on: push: tags-ignore: ['**']`). Nothing then tests the release
    commit itself, so a suite that is broken at the tag can ship anyway. srsly's
    `release-v2.5.3` commit bumped the vendored cloudpickle to 3.1.2 without updating
    the vendored cloudpickle tests, which still import `srsly.cloudpickle.compat` and
    `cloudpickle.cell_set` — both removed in cloudpickle 3.x — so `pytest --pyargs
    srsly` cannot even collect, on any architecture.
    - **Two commands separate "upstream is broken here" from "our port is broken":**
      read the test workflow's `on:` block for a `tags-ignore`/`branches` filter, and
      `gh run list --repo <upstream> --workflow <tests>.yml --json headSha,conclusion`
      for the release SHA. A tag SHA absent from that list means the suite is unproven
      at the version you are building.
    - **Then confirm arch-independence and exclude, don't patch.** Restoring a shim for
      the first missing symbol just moves the error to the next one — a test suite left
      behind by a vendored-dependency bump needs an upstream rewrite, not a port patch.
      Exclude the subtree with gotcha 14's absolute `--ignore` (note `--ignore-glob`
      silently no-ops under `--pyargs`, computing the path from the *installed* package:
      `--ignore="$(python -c 'import <pkg>, os; print(os.path.join(os.path.dirname(<pkg>.__file__), "tests", "<subdir>"))')"`),
      and say in a comment that it fails identically on x86_64.

144. **A compiled "speedups" package: don't differential-test it against the pure-Python
    implementation it replaces (the textual-speedups case).** A package whose entire
    purpose is to reimplement another library's classes in Rust/C invites an obvious test —
    import both and assert they agree — and upstream often ships no tests of its own, so it
    looks like the only real option. Two independent traps make it the wrong one, and both
    are settled on any host in minutes:
    - **The consumer may already import the speedups by default, so the "reference" *is* the
      candidate and the suite is vacuously green.** textual's `geometry.py` ends with
      `if os.environ.get("TEXTUAL_SPEEDUPS", "1") == "1": from textual_speedups import
      Offset, Region, Size, Spacing` — install the wheel and `textual.geometry.Size` becomes
      `<class 'builtins.Size'>` (a pyo3 class reports `builtins` when `#[pyclass]` names no
      module — that is the tell). Every assertion then compares the Rust class with itself.
      Check with `assert reference_module.X is not candidate_module.X` before trusting a
      single passing run, and grep the consumer for the opt-out env var.
    - **With the swap disabled the two legitimately diverge**, because the speedups track a
      snapshot of semantics upstream never promised to freeze: `Size.__sub__` clamps at 0 in
      Python but not in Rust, `Spacing.horizontal` is a property one side and a method the
      other, `Size.__contains__` accepts an `Offset` only in Rust. Pinning the consumer to
      the release contemporary with the speedups does **not** fix it (identical failures on
      textual 6.11.0 and 8.2.8) — these are upstream's own inconsistencies. Asserting them
      would make our CI hostage to a third package's evolution.
    Write a self-contained smoke suite instead, with expected values derived from a local
    build on your own arch — then any riscv64 difference is a real codegen or integer-width
    bug rather than a drifting expectation. Stage it into the checkout from a `run:` heredoc
    (gotcha 7) and point `CIBW_TEST_SOURCES` at it; keep gotcha 20's `unzip -l | grep '\.so$'`
    proof beside it.
    - **maturin honours the same default licence glob as setuptools, so gotcha 44's one-file
      patch works unchanged there** — verified by building the tag twice: without a root
      `LICENSE` the wheel has no `dist-info/licenses/` at all, with one it appears, and no
      `pyproject.toml`/`Cargo.toml` edit is needed. Worth checking on any young Rust project:
      a tag cut before upstream got round to adding a licence file publishes wheels carrying
      no licence text whatsoever, which is a compliance gap we inherit by redistributing.
      If upstream has since added it on `main` with no release, that is `Backport`.
    - **Gotcha 31 does not apply to maturin**: the version comes from `Cargo.toml`, not
      `git describe`, so `git apply`-ing a patch leaves the wheel filename alone and no
      `SETUPTOOLS_SCM_PRETEND_VERSION`-style pin is needed.

176. **`log_level` is the third pytest ini key that decides whether a staged suite passes,
    after `addopts` and `markers` — and the failure it produces looks like a compiled-vs-pure
    bug (extends gotchas 25/28/108).** `caplog` captures at **WARNING** unless the ini sets
    `log_level`, so a suite whose assertions read `caplog.text` for DEBUG/INFO messages
    (`assert "Waiting for adapter to initialize" in caplog.text`) fails the moment
    `CIBW_TEST_SOURCES` staging drops the project's `pyproject.toml`. The traceback shows the
    *other* records the test did emit, which reads like the extension logging differently from
    the pure-Python fallback — exactly the gotcha-20 failure you are primed to look for. It is
    not: nothing about it is arch- or build-dependent.
    - **Separate "our port" from "our staging" by running the identical staged command against
      upstream's *released* wheel** (gotcha 52's dry run, aimed at a different question). Six
      failures reproducing byte-for-byte against habluetooth's own PyPI wheel settled it in one
      container run, before any riscv64 cycle.
    - **Then supply the one key rather than staging the file**, when `addopts` is coverage-only
      (gotcha 28): `python -m pytest tests -o log_level=NOTSET` avoids pulling in `pytest-cov`,
      `pytest-timeout` and — the real hazard — an ini `timeout = 5` sized for upstream's x86 CI
      that would flake on the riscv64 runner (gotcha 38). `-o <key>=<value>` overrides or
      supplies any ini key without a rootdir.

177. **Narrowing an upstream test suite because its heavy requirements file has no
    riscv64 wheels is almost always unnecessary — the modules that need those libraries
    skip themselves (the pyinstaller case; see `build-pyinstaller.yml`).** A project with
    a two-tier test-requirements split (`requirements-base.txt` for the framework,
    `requirements-libraries.txt` pinning Qt/numpy/scipy/pandas/matplotlib/Django) invites
    the conclusion that only a hand-picked module can run on riscv64, and the port then
    ships one file out of forty. It reads as prudent and is a large, silent coverage loss:
    every module reaching those libraries is already guarded by `pytest.importorskip` or
    an equivalent, so installing only the base requirements makes them **skip**, not
    error, and the whole suite runs. pyinstaller's port tested `tests/unit` plus
    `tests/functional/test_basic.py` (417 tests) where upstream's `ci.yml` runs
    `tests/unit tests/functional`; widening it to upstream's own selector took the job to
    773 tests — multiprocessing, signals, symlinks, ctypes, the import hooks, splash,
    reproducibility and security, i.e. most of what a bootloader port exists to prove.
    - **Price it before deciding, on aarch64 in minutes** (gotcha 101's rehearsal, aimed
      at the *test* phase): build the wheel in an `ubuntu:24.04` arm64 container with the
      same uv-provisioned interpreter, install only the base requirements, and run the
      full suite. The pass/skip/fail split falls straight out — here 452 passed, 396
      skipped, 12 failed — and the 12 failures are the exact deselect list, each one
      reproducing off riscv64 and therefore not a port defect.
    - **The guard's strength is where the residue clusters.** A module gated on
      *importability* rather than *usability* is the one that fails instead of skipping:
      pyinstaller's `test_splash.py` checks `tcltk_info.tkinter_fully_usable` and skips,
      while `test_libraries.py` checks only `can_import_module("tkinter")` — true under
      an interpreter that ships the Python package without the Tcl/Tk shared libraries —
      so its two tkinter tests fail. Grep the suite for the weaker predicate rather than
      inferring the list from a failing run.
    - **Deselect per matrix entry, never globally** (gotcha 33). These failures track the
      *interpreter build*, and one entry usually has a different one — the riscv64
      runner's own 3.12 has shared `_ctypes`, a shared libssl and no tkinter at all, so it
      passes the reclassification and multipackage tests and skips the tkinter ones, while
      the PBS 3.13/3.14 entries need all seven deselects.
    - **Extends gotcha 169's list of what python-build-standalone folds into the
      interpreter: OpenSSL too.** `_ssl` is builtin with no `libssl.so` to collect, so a
      test asserting that a frozen application bundles a shared OpenSSL —
      `'.*<app>:.*ssl.*'` in an expected-contents manifest — fails on every PBS
      interpreter and on no distro one. Settle it with
      `python -c "import sys; print('_ssl' in sys.builtin_module_names)"` rather than from
      the failure text, which only says an expected entry was missing.

212. **An unavailable optional dependency (no riscv64 wheel) doesn't only fail tests
    that import it at module scope — grepping for those under-counts (the lancedb
    case).** lancedb's suite already excluded six files that `import polars`/`import
    lance` (pylance) unconditionally at module scope, since neither has a riscv64
    wheel; the wheel still built and every excluded file's absence looked complete.
    But 12 more tests scattered across four *other, otherwise-passing* files import
    one of the two lazily inside the test body (`from lance...` a few lines into the
    function) — those collect fine and only fail at runtime with
    `ModuleNotFoundError`/`ImportError`, invisible to any static `grep -rl '^import
    polars'` sweep of the suite.
    - **The full set only falls out of actually running the suite once** (refines
      gotcha 109's "static analysis under-counts" from fixture closures to plain
      imports) — `grep -oE '^FAILED [^ ]+'` on that run's output gave all 12 nodeids
      directly, no further investigation needed once each traceback's
      `ModuleNotFoundError: No module named 'lance'`/`'polars'` confirmed the cause.
    - **Deselect the nodes, not the files** (opposite call from gotcha 109's "prefer
      whole modules"): here the four files carry far more passing tests than failing
      ones (e.g. one deselect each out of dozens of tests in `test_query.py`/
      `test_permutation.py`), so individual `--deselect=<file>::<test>` entries lose
      nothing, where `--ignore=<file>` would strand every passing test alongside them.
      Gotcha 109's "drop whole modules" call was the reverse ratio (15 of 21 modules
      100% server-dependent) — check which side of that ratio a suite falls on before
      picking the tool.
    - **Copy the nodeid string verbatim from the FAILED line of the exact
      `CIBW_TEST_COMMAND` you're patching**, not a hand-typed guess at the path: gotcha
      14 warns that a path-based `--deselect` silently no-ops when it doesn't match
      pytest's rootdir-relative nodeid. Since the fix reruns the identical command
      (same cwd, same `CIBW_TEST_SOURCES` layout), the nodeids the failing run printed
      are exactly what the rerun will report, with no absolute-vs-relative mismatch to
      chase.
    - A 13th failure in the same run, a project-metadata sanity test that reads
      `Cargo.toml` relative to its own file's path, deselects for an unrelated reason:
      `CIBW_TEST_SOURCES` stages only `pyproject.toml` and the test tree, so the file
      it needs was never copied in — a repo-layout gap, not a missing-dependency one,
      but the same fix (`--deselect`) applies since it verifies source-tree metadata
      consistency, not anything an installed wheel need prove.
