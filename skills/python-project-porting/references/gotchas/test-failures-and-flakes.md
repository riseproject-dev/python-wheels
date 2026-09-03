# Gotchas — Test failures, flakes & arch-specific bugs

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/test-failures-and-flakes.md`.

## In this file

- **14** — torch-dependent tests flake two ways on the riscv runner — deselect, don't chase.
- **33** — One green interpreter beside identically-failing others is a CPython feature
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

---

14. **torch-dependent tests flake two ways on the riscv runner — deselect, don't chase.**
    torch is usually gated `python_version < '3.14'`, so these bite your `cp312`/abi3
    build but not `cp314t` — a tell it's torch, not your wheel. (a) torch's libcpuinfo
    can't parse this runner's `/sys/.../core_id` (reads `-1`) and writes
    `Error in cpuinfo: failed to parse … core_id` to **stderr**, so any test asserting a
    subprocess's `stderr == ""` fails nondeterministically — deselect the whole module.
    (b) tests spawning many workers under a hard timeout (16 subprocesses,
    `wait(timeout=60)`) blow it on the slower runner. To drop tests, override
    `CIBW_TEST_COMMAND` with **`--ignore <abspath>`** (whole module) and
    **`-k "not <name>"`** (single test) — *not* path-based `--deselect {package}/…`,
    which silently no-ops because pytest reports collected nodeids relative to its
    rootdir while your path is absolute. Verify locally by running pytest from a
    different cwd and checking the deselected count is non-zero.

33.  **One green interpreter beside identically-failing others is a CPython feature
    gate, not a build bug (the debugpy case).** When a per-interpreter matrix comes back
    with cp314 fully green while cp312 and cp313 each fail the *same* N tests, suspect a
    runtime capability that newer CPython provides natively and older ones reach through
    arch-specific native code that has no riscv64 build. debugpy attaches to a running
    process by injecting a shim from a prebuilt per-arch library —
    `pydevd_attach_to_process/add_code_to_python_process.py` accepts only
    `arm64/amd64/x86/x86_64/i386` — but on 3.14 it goes through **`sys.remote_exec()`
    (PEP 768)** and needs no shim, so the 100 `attach_pid` failures were riscv64-real on
    3.12/3.13 and genuinely absent on 3.14.
    - **Read the failure *set* before any failure text.**
      `grep -oE 'FAILED [^ ]+' <log> | sort -u` then count how many carry the suspect
      parametrisation — 100 of 100 is a gate, a scattered mix is not. That one command
      separates "upstream doesn't support this on riscv64" from "our wheel is broken",
      and it costs nothing next to re-reading tracebacks.
    - **Deselect per matrix entry, not globally.** Turn `python: [cp312, ...]` into
      `include:` with a per-entry filter and interpolate it into the test command
      (`-k "${{ matrix.pytest_k }}"`), so the interpreter that *can* exercise the
      feature keeps testing it — dropping it everywhere would have thrown away 105
      real tests on cp314. `-k ""` is a valid no-op filter, so the unrestricted entry
      needs no second command shape.
    - **Free-threading is settled by upstream signals, not by debugging the crashes.**
      Three cheap checks decide whether `cp314t` belongs in the matrix at all: does PyPI
      list a `cp3XXt` wheel, does `tox.ini`/upstream CI carry a free-threaded env, do the
      classifiers mention free threading. debugpy answers no to all three, and its cp314t
      job crashed 40 pytest-xdist workers spread evenly over *every* test module —
      breakage of that shape means the configuration is unsupported, not that one feature
      is broken. Shipping it would give riscv64 a build upstream ships nowhere; drop the
      entry and say why in a one-line comment. (A *coherent subset* of failures would
      mean the opposite — keep digging.)

37. **pytest-xdist's controller can SIGSEGV under the free-threaded interpreter;
    `-n 0` sidesteps it (the snowflake-connector-python case).** A suite that runs
    green on `cp312`/`cp313`/`cp314` can kill the **cp314t** job with
    `Fatal Python error: Segmentation fault`, and the traceback is entirely
    *pure-Python execnet frames* — `gateway_base._read_int4` →
    `_thread_receiver`, under `<Cannot show all threads while the GIL is
    disabled>`, with `OSError: cannot send (already closed?)` from the workers
    trailing behind it. No project code on the stack, no `.so` involved, and it
    is **intermittent**: the same job on the same tree completed the whole suite
    on an earlier run. That is xdist's own gateway machinery, which only exists
    when `-n` is on, so the fix is to take execnet out of the picture for that
    one interpreter rather than to chase the crash.
    - **`-n 0` is the clean off switch, not `-p no:xdist`.** xdist's
      `pytest_cmdline_main` special-cases it: `numprocesses == 0` forces
      `dist = "no"` and `tx = []`, so no gateway is created and no receiver
      thread spawns — while the plugin stays loaded, so `pytest.mark.xdist_group`
      is still a registered marker (`-p no:xdist` deregisters it and trips
      `--strict-markers`). It also overrides an inherited `--dist loadfile`, so
      the flag can stay in a shared command string.
    - **Vary it per matrix entry, not globally** — serial costs real time (30min
      vs 18min here), so keep upstream's `-n auto` on the GIL-ful interpreters.
      Switch the matrix from a bare `python:` list to `include:` entries carrying
      the flags, and interpolate `${{ matrix.pytest_dist }}` into
      `CIBW_TEST_COMMAND`.
    - Distinct from gotchas 21 and 25, which are about what the xdist *workers*
      import. This one is the **controller** process crashing outright, and no
      amount of `PYTHONNOUSERSITE`/`test-sources` touches it.

38. **A slow runner turns a latent test race into a hard failure — simulate the
    slowness on your fast host instead of guessing.** Test suites are full of
    timing assumptions that hold on the x86 CI upstream sizes them for. Three
    shapes showed up in one port, all of them *arch-independent bugs* that only
    riscv64 was slow enough to reach:
    - **A fixed timeout constant sized for fast hardware** — a wiremock
      standalone server given 12s to answer `/__admin/health` while four xdist
      workers each boot their own JVM; a `platform_detection_timeout_seconds=1`
      budget that a first `boto3.client("sts", …)` service-model load overshoots.
      Both are the playbook's "artificial test limitation" patch case: raise the
      ceiling, note that the wait returns early so faster hardware pays nothing.
    - **A thread the code under test deliberately abandons.** The nastiest one:
      `Auth.authenticate()` runs its MFA wait in a daemon `Thread` and gives up
      with `t.join(timeout=…)`, so the request mock keeps running after the call
      returns — and reaches its trailing `mock_cnt += 1` ~9s later, inside the
      *next* sub-case, which has already reset that global to stage its own
      response. Result: a wrong branch and a `KeyError` instead of the expected
      exception. Fix the mock to complete its mutation of shared state **before**
      it sleeps (read-and-advance in one step at the top), leaving branch
      selection unchanged — not to widen the assertion.
    - **Reproduce it on any host by inserting the delay yourself.** Find the
      window the failure needs and `time.sleep()` it open — here, an 11s sleep
      right after the next sub-case's counter reset reproduced the exact CI
      `KeyError` on macOS/arm64, and the patch flipped it to green. Same
      30-second, no-QEMU discipline as gotchas 23/25/29, applied to timing: it
      proves the bug is upstream's rather than the port's, and it is the evidence
      that justifies the patch in review.
    - **Look for upstream's own admission.** A `skipif(IS_WINDOWS, reason="…race
      condition issues with the global …")` on the very test that fails is
      upstream telling you the race is known and merely platform-dependent —
      quote it in the commit message and tag the patch `To upstream`, not
      `Inappropriate`.
    - **Keep `Upstream-Status:` on ONE physical line.** `ci_scripts/check_patch.py`
      matches `^Upstream-Status: *(.*)$` and then validates the bracketed comment
      with `^(\[.*\])?$` — a bracket wrapped across two lines leaves the value
      unbalanced and fails `check_patches`, costing a push. Verify before pushing
      with `uv run --python 3.13 python ci_scripts/check_patch.py origin/main HEAD`
      (the script needs ≥3.12 for its nested-quote f-strings).

60. **A SIGSEGV in a port's test run is usually an ordinary upstream refcount bug —
    reproduce it on your own host's interpreter before blaming riscv64 (the
    confluent-kafka case).** A cp314 job died with `Fatal Python error: Segmentation
    fault` whose Python traceback was entirely stdlib and pytest —
    `re/_compiler.py:_generate_overlap_table` compiling the literal pattern in
    `ex.match('expected configuration dict')` — with no project frame anywhere. The
    same crash, same file and same line, reproduced on macOS/arm64 under CPython
    3.14.7 against upstream's **released** wheel in about a second.
    - **faulthandler names the frame that was running when the fault was *hit*, not the
      code that caused it.** A traceback made only of stdlib/pytest frames is the
      signature of heap corruption committed earlier; mining it for a cause is wasted
      time. Read the test *ordering* instead — here the fault landed on the first
      statement of the first test of the module that ran immediately after
      `tests/test_Admin.py`.
    - **One job red and the others green is not gotcha 33's feature gate when the
      failure is a fault.** Gotcha 33's "read the failure set" separates a CPython
      capability gate from a broken wheel, and it assumes *test failures*. A
      use-after-free only manifests when the freed allocation happens to be reused, so
      which interpreter dies is a lottery — cp313 passing the identical tree is
      evidence *for* corruption, not against it.
    - **Reproduce on the host before anything else.** `uv python list --only-installed`
      usually already has the interpreter, `pip install <pkg>==<ver>` gets upstream's
      released wheel, and running the two adjacent test modules costs seconds. No QEMU,
      no rebuild — and if it reproduces, the bug is upstream's and arch-independent,
      which is the whole finding.
    - **Bisect twice.** First over the test ids (`--collect-only`, then `head -n N` of
      that list); then over the *body* of the offending test — truncate the function at
      line N and append `pass`. That narrowed 4600 tests to one statement,
      `admin.delete_records([TopicPartition("topic", 0, 10)])`.
    - **Prove the mechanism against the released wheel with `sys.getrefcount`**, holding
      a second strong reference so the over-decref cannot actually free the object:
      3 before the call, 2 after ⇒ the function drops a reference it does not own.
      `PyArg_ParseTuple*`'s `O` targets are **borrowed**; `Admin_delete_records()` never
      `Py_INCREF`ed `topic_partition_offsets` and `Py_XDECREF`ed it on both the success
      and the `err:` path. The fix is deleting the two decrefs.
    - **Sweep for siblings before writing the patch.** ~20 lines of Python over the
      extension's `.c` files, pairing each `PyArg_ParseTuple*` target with a
      `Py_(X)DECREF` of that same name and no matching `Py_INCREF`, found exactly one
      real hit — the others decref `future`, which those functions deliberately
      `Py_INCREF` because the options struct hands it to a background callback. Say so
      in the commit message; it is what makes the patch obviously right.
    - **`python repro.py | head` swallows the evidence.** stdout is block-buffered when
      piped and a SIGSEGV loses the buffer, so the script looks like it crashed *before*
      its first `print` and faulthandler prints `<no Python frame>`. Run it with `-u`;
      the real story was that the script completed and faulted during interpreter
      shutdown, which is itself the tell that the damage was done earlier.

61. **A callback that stays armed past the assertion fires again during teardown (the
    event-API sub-shape of gotcha 38).** Gotcha 38's shapes are a fixed timeout
    constant, an abandoned thread reaching a trailing mutation, and "insert the delay
    yourself". A fourth recurs in wrappers around C event loops: the test registers a
    callback that *always* raises, asserts the exception surfaces out of the one call it
    cares about, then closes the handle **with the callback still registered**. The
    native library keeps queueing that event for the object's lifetime and `close()`
    dispatches whatever is queued, so the callback raises a second time and the
    exception escapes `close()` instead of the call under test.
    confluent-kafka's `test_callback_exception_no_system_error` does it with a
    `stats_cb` at `statistics.interval.ms=100` and an `error_cb` on the broker-resolve
    retry backoff: the handful of statements between the assertion and `close()` cost
    under 100ms on x86 and more than that on the riscv64 runner, so one interpreter's
    job fails while another's passes on the identical tree.
    - **Fix it with "raise once"** — guard the callback on its own accumulator
      (`if called: return`) — not by widening the assertion. Every assertion in the test
      stays untouched and only the redundant later raises disappear.
    - **Reproduce with gotcha 38's delay trick on the *real* test**, not a hand-written
      excerpt: copy the module, insert `time.sleep(1.2)` before each `close()`, run it
      against upstream's released wheel. Fails unpatched, passes patched, on any host,
      in seconds — and that is the evidence a reviewer wants for the patch.

115. **A SIGSEGV that will not reproduce off the runner: get the native backtrace *in CI*
    with a throwaway gdb commit (the lightgbm case, and the other half of gotcha 60).**
    Gotcha 60's rule is to reproduce a fault on your own host before blaming riscv64, and when
    it works it is the whole diagnosis. When it does not — the same tree runs clean under QEMU
    and on aarch64 — the next cheapest evidence is still a *native* backtrace, and CI is the
    only place to get one. Two settings make it possible and are worth knowing before you spend
    the cycle:
    - **The wheel is stripped by default**, so a backtrace is addresses only. scikit-build-core
      strips via `install.strip`; override both it and the build type from `CIBW_ENVIRONMENT`:
      `SKBUILD_CMAKE_BUILD_TYPE=RelWithDebInfo SKBUILD_INSTALL_STRIP=false` (setuptools
      projects: `CFLAGS=-g` and a `CIBW_REPAIR_WHEEL_COMMAND` without `--strip`).
    - **gdb works inside the cibuildwheel container on the real runner** (`dnf -y install gdb`
      in `CIBW_BEFORE_TEST_LINUX`) but **not under QEMU**, where it dies with
      `ptrace: Function not implemented` — so do not spend time debugging the emulated case.
    Then stage a loop as the test command, because an intermittent fault needs several attempts
    (lightgbm's took 4 of 6, ~2 min each):
    ```bash
    for i in 1 2 3 4 5 6; do
      gdb -batch -ex run -ex "thread apply all bt 25" --args python -m pytest -q -x <the tests> \
        > /tmp/gdb-$i.log 2>&1
      grep -q SIGSEGV /tmp/gdb-$i.log && { tail -120 /tmp/gdb-$i.log; exit 1; }
    done
    ```
    Commit it, read the trace, then `git reset --hard` back and force-push so the PR keeps a
    clean history — the debug commit must not be named `revertme`/`DO NOT MERGE`, which
    `pr-checks.yml` rejects outright.
    - **`thread apply all bt` is the point, not `bt`.** The faulting thread's own frame is often
      inside the OpenMP runtime (`gomp_iter_guided_next`) and says nothing; the *sibling*
      threads show which parallel region and which loop body were live, and the main thread
      shows the C API entry point and its `parameters` string — which is what identifies the
      failing call from Python.
    - **Before concluding "toolchain bug", exhaust the cheap instrumented rebuilds under QEMU**,
      since they detect latent corruption even when the crash itself does not reproduce:
      `-D_GLIBCXX_ASSERTIONS` (bounds-checks `std::vector::operator[]`, the usual suspect when a
      loop indexes a per-thread buffer by `omp_get_thread_num()`) costs one rebuild. **ASan is
      not an option on riscv64 today** — it aborts in its own allocator with
      `CHECK failed: sanitizer_allocator_primary32.h:292 "((res)) < ((kNumPossibleRegions))"`
      before running any user code, so don't budget for it.

120. **Hypothesis' `too_slow` health check is a wall-clock budget on *input generation*,
    and a slow runner trips it (a fourth shape for gotcha 38).** `@settings(deadline=None)`,
    which such suites apply liberally, does **not** cover it: `FailedHealthCheck: Input
    generation is slow: Hypothesis only generated N valid inputs after X seconds` fires
    before any assertion runs. time-machine's culprit was `st.timezones()` — each example
    constructs a `ZoneInfo`, and the first construction per key parses a TZif file off disk,
    ~0.37s per draw on the riscv64 runners against microseconds on upstream's x86 CI. It
    surfaced on `cp314t` alone, and on the one test in the module carrying no `@settings`
    at all, which reads like a free-threading bug and is not.
    - **The failure output names the scope for you**: it prints a per-argument table of
      slowest draws, so you can see which strategy is slow. Patch every test whose
      strategies can reach it (here `zoneinfos` directly, plus the composite that mixes it
      with UTC) — patching only the one that failed leaves the same flake to reappear
      elsewhere next run.
    - **Scope the suppression to those tests, not the module:**
      `@settings(suppress_health_check=[HealthCheck.too_slow])`, leaving `deadline` and
      `max_examples` untouched, so it is a no-op on hardware fast enough never to trip it.
      There is no env var for this — Hypothesis profiles have to be registered from a
      `conftest.py` — so it is a patch, `Upstream-Status: Inappropriate [native runner
      specific]`.

164. **A test helper with a per-architecture syscall table falls back to a fixed sleep on
    riscv64 — and riscv64's numbers are aarch64's (the memray case).** Test suites that need
    "wait until the child is actually blocked" commonly poll `/proc/<pid>/syscall` against a
    hardcoded table, with an `else: time.sleep(1.0)  # hope for the best` arm for unknown
    architectures. That arm is gotcha 38's fixed-timeout shape in disguise, and it is the only
    one riscv64 ever reaches: memray's `_wait_until_process_blocks` gave the `memray live`
    client one second to reach its `connect()`, the runner needed longer, and the SIGINT the
    test then sent hit the default handler — `assert -2 == 0`, on every interpreter, with
    nothing about the wheel at fault.
    - **riscv64 uses the unified `scripts/syscall.tbl` (abi `64`/`common`), the same table
      aarch64 uses, so adding `riscv64` to the existing aarch64 branch is the whole patch** —
      nanosleep 101, clock_nanosleep 115, accept 202, connect 203. Confirm rather than assert
      it: `curl -s https://raw.githubusercontent.com/torvalds/linux/v6.12/scripts/syscall.tbl`,
      then `dnf install linux-libc-dev`/`apt-get install linux-libc-dev` in a riscv64 container
      and grep `/usr/include` for `__NR_*`. Both take seconds and the second one is the real
      header the kernel ships.
    - **Widening the branch is safer than widening the sleep.** These loops have no timeout, so
      a wrong number hangs the job until the workflow's `timeout-minutes` — check the arch
      selects `HAVE_ARCH_TRACEHOOK` (riscv does, so `/proc/<pid>/syscall` is populated) before
      trusting the poll at all.
    - Grep for it while reading the suite: `platform.machine()` or `uname -m` next to a literal
      number table is the tell, and the same shape shows up wherever a project maps arch →
      syscall/ABI constants (seccomp filters, ptrace helpers, `libc` fallbacks).

166. **The riscv64 runners' libgomp faults on the `dynamic` and `guided` OpenMP
    schedules — `static` is unaffected (the lightgbm case; see `patches/lightgbm/4.7.0/0002-*`).**
    A 40-line C program that allocates nothing in the loop body segfaults 3 times out of 3
    under `schedule(guided)` and `schedule(dynamic)`, on the bare `ubuntu-24.04-riscv` runner
    with GCC 13.3.0 *and* inside `manylinux_2_39_riscv64` with GCC 14.3.1, while
    `schedule(static)` on the same program and 30M concurrent `malloc`/`free` per thread are
    clean. The identical binaries pass under QEMU riscv64 and on `manylinux_2_39_aarch64` at
    4, 16 and 64 threads. Tracked as riseproject-dev/python-wheels#617.
    - **So an OpenMP-heavy port can fail with a SIGSEGV that has nothing to do with the
      package.** The signature is a fault *inside* libgomp — `gomp_iter_guided_next()` or
      `gomp_iter_dynamic_next()` at frame #0 with the project's `._omp_fn.N` at #1 — hitting
      the packages that run a very large number of small parallel regions. lightgbm reaches
      it once per boosting iteration through the ranking objective and once per sparse
      dataset through `FeatureGroup::FinishLoad`.
    - **Two env vars separate it from a bug in the package, in minutes on the runner**:
      `OMP_NUM_THREADS=1` and `OMP_WAIT_POLICY=passive GOMP_SPINCOUNT=0` each take it from
      9/10 failures to 0/10. A codegen bug would not care about the wait policy, and a race
      in the package would not be reproduced by a C program containing none of it.
    - **`grep -rho 'schedule([a-z]*' src include | sort | uniq -c` prices the workaround
      before you write it.** LightGBM asks for dynamic or guided in 13 of ~230 parallel
      regions, so a patch moving those to static is small and costs only load balancing on
      loops whose iterations differ in cost. Tag it `Inappropriate` with the issue link and
      say to revert it when the toolchain is fixed — it is our infrastructure's defect, not
      upstream's.

167. **A riscv64-only intermittent SIGSEGV: climb the control ladder before you debug
    anything.** Gotcha 60 says to reproduce a fault on your own host before blaming the
    architecture, and gotcha 115 gets a native backtrace from CI when that fails. Between
    them sit three controls that say *architecture, toolchain, or code* — none needs the
    runner, and each costs minutes:
    - **QEMU riscv64 executes the same instructions but serialises atomics**, so a
      *miscompile* reproduces there and a *race* does not. lightgbm's whole suite ran green
      under QEMU while the same tree faulted on the runner — that alone ruled out codegen.
    - **`manylinux_2_39_aarch64` on an arm64 host is real parallelism on a weakly-ordered
      machine** (gotcha 101's rehearsal used as a race control). Oversubscribe it —
      `OMP_NUM_THREADS` at 4, 16 and 64 — and loop the failing tests. 36 clean runs there
      put the fault on riscv64 rather than on the code's threading.
    - **Then a standalone C reproducer of whatever the backtrace names**, run on the bare
      runner *and* in the manylinux image. Whether a 40-line `#pragma omp parallel for`
      faults on its own is the whole difference between "our wheel is broken" and "the
      toolchain is", and it is a two-minute job that needs no wheel build.
    **ThreadSanitizer is not one of the controls.** GCC's libgomp carries no TSan
    annotations, so its barriers are invisible and every cross-region access is reported:
    lightgbm produced 80 warnings, all of them allocator reuse. The tell is that *every*
    `SUMMARY:` line names `operator new`/`delete`/`memcpy`/`memmove`/`memset`/`free` rather
    than a project line — check with `grep '^SUMMARY: ThreadSanitizer' tsan.out | sed
    's|.*data race ||' | sort | uniq -c` before reading a single report. It is usable only
    with an annotated runtime (LLVM libomp + Archer), and the aarch64 manylinux image ships
    no clang.

168. **Running a diagnostic on the riscv64 runner: drive it from `CIBW_TEST_COMMAND`, and
    never leave the branch in that state.** Gotcha 115 commits a throwaway gdb loop; the
    same shape carries any experiment that needs the real hardware — a rebuild at another
    optimisation level, `MALLOC_CHECK_=3`, an instrumented library swapped over the
    installed one. Five mechanics, each of which cost a cycle to learn:
    - **A maintainer can merge while you are mid-experiment.** #481 was merged with the
      probe job still in the workflow and an `if:` guard switching the build off, so `main`
      briefly carried a workflow that built nothing. Gotcha 115's "reset and force-push
      afterwards" is not enough — between pushes the branch head *is* the deliverable. Keep
      diagnostics to the shortest possible window, and check the PR is still open before
      pushing the next one.
    - **A bare `podman run` on `ubuntu-24.04-riscv` dies with `could not find slirp4netns,
      the network namespace can't be configured` (exit 127)** unless you pass
      `--network=host`, as `build-cryptography.yml` and `build-orjson.yml` do. It also
      re-pulls the manylinux image under podman even though cibuildwheel already has it —
      nine minutes, for nothing.
    - **Stage helper scripts into the workspace root with a `run:` heredoc before the
      cibuildwheel step** (gotcha 7) and reach them as `{project}/diag.sh`. `{project}` is
      the whole checkout inside the container even when `test-sources` has emptied the test
      cwd (gotcha 5), so an extracted sdist at `{project}/dist/<pkg>-<ver>` is right there
      to re-run `cmake` against. End the script `exit 0` so a red experiment still lets the
      job finish.
    - **Verify the path you are swapping the rebuilt library into.** A wrong path makes
      `cp` create a file nothing loads, and the experiment silently re-measures the
      original — a whole "rebuild at -O1" round was wasted that way. Ask the package where
      it loads from (`python -c 'from <pkg>.libpath import _find_lib_path; print(...)'`)
      rather than guessing, and print `ls -l` before and after.
    - **Rebuilding at another optimisation level needs `CMAKE_CXX_FLAGS_RELEASE`, not
      `CMAKE_CXX_FLAGS`**, when the project appends `-O3` to the latter itself: per-config
      flags land after `CMAKE_CXX_FLAGS` and the last `-O` wins. And **put anything that
      needs no wheel in its own job** — a libgomp probe answers in ten minutes instead of
      queueing behind a multi-hour build.

169. **`astral-sh/setup-uv` hands you a python-build-standalone interpreter, and PBS links
    statically what a distro ships as shared — which fails tests that assert on module
    *kind* or bundle system libraries (the pyinstaller case).** The Anatomy section mandates
    setup-uv because setup-python has no riscv64 support, and gotcha 117 notes it silently
    reuses the runner's system CPython when the versions match. The other half of the same
    fact is what PBS *builds*: from **3.13** on, `_ctypes` is compiled into the interpreter
    (`'_ctypes' in sys.builtin_module_names`) rather than shipped as `lib-dynload/_ctypes*.so`,
    and PBS's **Linux** builds carry no `libtcl*.so`/`libtk*.so` at all — Tcl/Tk is linked
    into `_tkinter.so`, while the macOS builds ship them as dylibs. Suites that introspect
    the interpreter fail on those facts with nothing wrong in the wheel: PyInstaller's
    `test_extension` asserts `_ctypes` is a `modulegraph.Extension`, and its splash-screen
    tests die with `Could not determine the path to Tcl and/or Tk shared library`.
    - **The tell is a matrix where the older interpreters pass and the newer ones fail
      identically** — the inverse of gotcha 33's shape, and it points at the interpreter
      *build*, not at a CPython feature gate. PBS 3.12 passes both here because it has
      `_ctypes` as a shared module and no `_tkinter` at all (so the splash tests skip).
    - **Settle it on any host in under a minute, no QEMU and no riscv64.**
      `uv run --no-project --python 3.13 python -c "import sys; print('_ctypes' in sys.builtin_module_names)"`
      answers the first, and for the second, untar the PBS **linux-x86_64** asset and look
      for `lib/libtcl*`: absent there too, so the failure is arch-independent. Both
      reproduced on macOS/arm64 before a single CI cycle was spent.
    - **Deselect per matrix entry** (gotcha 33), so the interpreter whose PBS build does not
      trip the assertion keeps running it — an unset `include:` key interpolates to the
      empty string, so the unaffected entries need no second command shape.

170. **`np.linalg.eig` on a symmetric matrix returns *real* eigenvalues on x86_64 and
    aarch64 and *complex* ones on riscv64 — a numeric-port trap with no numeric symptom
    (the statsmodels case).** LAPACK's general `dgeev` computes an imaginary part for every
    eigenvalue and numpy returns a `float64` array only when all of them are exactly zero.
    For a matrix that is symmetric by construction (`exog.T @ exog`) the x86_64 and aarch64
    OpenBLAS kernels land on exact zeros; the `riscv64_generic` ones do not, so the same
    call returns `complex128` and the failure surfaces far away as
    `_UFuncOutputCastingError: Cannot cast ufunc 'multiply' output from dtype('complex128')
    to dtype('float64')` on an in-place multiply several functions later. Nothing about the
    numbers is wrong — the imaginary parts are ~1e-17 — so it reads like a broken wheel.
    - **Grep the traceback's call chain for `linalg.eig(` before reading any values.** A
      complex dtype arriving where the code assumes real is the whole finding; `eigh`
      (`dsyevd`) is real by construction on every platform and agreed with `eig` to 3e-15 on
      the same inputs here. That makes it a genuine upstream bug rather than a riscv64
      workaround — statsmodels still calls `eig` on `main`.
    - **Reproduce the *mechanism*, not the failure**, since the failure needs the riscv64
      BLAS: instrument the function on any host and print `ev.dtype` alongside `evmin`. It
      printed `float64` on aarch64, which is the evidence that the divergence is the dtype
      and not the arithmetic.
    - **The neighbouring failure in the same job may be unrelated and needs the opposite
      treatment.** A maximum-likelihood fit that upstream itself logs as non-convergent
      (`ConvergenceWarning`) but that is asserted to `atol=1e-4` lands at 1.9e-3 here
      against 2.4e-8 on aarch64 — gotcha 38's artificial-test-limitation shape. Loosening
      that tolerance only uncovers the next assertion in the same test (`res.mae < 1e-6`),
      so drop the one parametrisation and keep the sibling that is exact.

205. **A follow-up commit that fixes a broken `Upstream-Status:` line does not clear
    `check_patches` — it checks the patch file's content at *every* commit that
    touched it, not just the final diff (extends gotcha 38's single-line rule).**
    `check_patch.py`'s `main()` walks `git rev-list start..end`, and for each commit
    re-extracts and re-validates every `.patch` file that commit added or modified
    (`git show <commit>:<path>`). A commit that adds a patch with the wrapped
    `Upstream-Status:` line, followed by a second commit that rewraps it onto one
    line, still fails: the first commit's snapshot is still broken, and the job
    replays it as its own check.
    - **Squash instead of appending a fix commit.** `git reset --soft` to the
      merge-base, recommit once with the corrected patch, then
      `git push --force-with-lease` — the PR isn't reviewed yet, so rewriting its
      own history is normal, not the "don't rewrite shared history" case the repo's
      git safety rules guard against.
    - **Run the exact CI invocation locally first**, on the full commit range, not
      just the working tree: `git log --oneline origin/main..HEAD` shows every
      commit `check_patches` will separately replay.
