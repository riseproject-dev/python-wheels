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
- **379** — A test asserting a specific cross-thread ordering (a `gc.collect()`-on-one-thread-
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
- **286** — A vendored-ARPACK eigensolver test failing only on musllinux, not manylinux, can
- **297** — A test harness's own unbounded `readline()`-until-marker wait turns any slow or
- **304** — A hardcoded exact-equality assertion on a neural-network/matmul-heavy
- **316** — A hardcoded timing threshold on a metric that measures raw wall-clock
- **317** — A pure-Python, allocation-heavy test suite running ~8x slower on musllinux
- **323** — Gotcha 127's GIL-reenable safety net only rules out concurrency races — a
  single-phase-init C extension can still segfault on cp314t with no threading involved.
- **362** — A `multiprocessing.Process().join()` regression test for a native threadpool's
  fork safety can hang the full length of its `pytest.mark.timeout` deterministically,
  not flakily, on the riscv64 runner.

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

323. **Gotcha 127's GIL-reenable safety net only rules out concurrency races —
     a single-phase-init C extension can still segfault on cp314t with no
     threading involved at all (the mwparserfromhell case).** mwparserfromhell's
     tokenizer extension calls `PyModule_Create` (no `Py_mod_gil` slot), so by
     gotcha 127 it should be immune: CPython re-enables the GIL at import and
     warns, which is supposed to serialize every call into it. It still
     segfaulted deterministically inside `Tokenizer_parse`, on a plain
     single-worker `pytest` run (no `-n`, no xdist frames on the stack, no
     concurrency of any kind) — proof this was never a race gotcha 127's
     safety net could have caught. Confirmed by an open upstream tracking
     issue (`earwig/mwparserfromhell#343`, "Enable mwparserfromhell for use
     with thread-free Python releases") rather than by chasing the C bug:
     free-threading support is genuinely unimplemented, not a build artifact,
     and PyPI itself ships no `cp314`/`cp314t` wheel for the package either.
     Don't treat "no `Py_mod_gil` slot" as proof cp314t is safe to ship — it
     only means races get serialized, not that the extension behaves
     correctly under the free-threaded build's other differences. Drop the
     interpreter and cite the upstream issue in a one-line matrix comment,
     same as gotcha 14's "settled by upstream signals, not by debugging the
     crashes" rule.

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

282. **A matplotlib `image_comparison` test failing only on riscv64 is a font-rendering
    divergence, not a logic bug — deselect that one test, don't touch the module (the
    igraph case).** python-igraph's `test_labels` renders vertex labels with matplotlib
    and diffs the PNG against a bundled baseline via `image_comparison(tol=4.0)`; on the
    riscv64 manylinux image the failure is `ImageComparisonFailure: images not close (RMS
    6.084)` with every other test in the module (522 of them) passing. `remove_text=True`
    strips titles/ticks but deliberately leaves "more deliberate" text like vertex labels
    in the diff, so any FreeType/fontconfig difference between the image that produced the
    baseline and the manylinux riscv64 image's font stack pushes the RMS over the
    tolerance. Upstream's own CI doesn't special-case this on aarch64 either — its
    aarch64 runners just happen to anti-alias close enough to the baseline.
    - **Confirm it's pixel-diff, not a crash or wrong-value assertion**, before treating it
      as cosmetic: the traceback should bottom out in
      `matplotlib.testing.exceptions.ImageComparisonFailure`, not an `AssertionError` on
      igraph's own output.
    - **Fix with a targeted `--deselect` in `CIBW_TEST_COMMAND`**, e.g. `--deselect
      tests/drawing/matplotlib/test_graph.py::GraphTestRunner::test_labels`, with a
      one-line comment naming the mechanism (font-rendering divergence, not a functional
      bug). Do not skip the whole `test_graph.py` module or drop matplotlib from the test
      extras — every other image-comparison test in the same file (`test_basic`, etc.)
      passes and stays covered.

283. **A `cp314t`-only `PicklingError` from a `multiprocessing.Process(target=<local
    function>)` can be a side effect of an *earlier* `--ignore`, not a free-threading bug
    in the target itself (the thriftpy2 case).** CPython 3.14 changed the default
    multiprocessing start method on POSIX from `fork` to `forkserver` (all interpreter
    builds, GIL or free-threaded) specifically to avoid multithreaded fork
    incompatibilities; unlike `fork`'s copy-on-write child, `forkserver` (like `spawn`)
    must pickle the `Process` target to hand it to the forkserver, so a locally-defined
    closure passed as `target=` now fails with
    `_pickle.PicklingError: Can't pickle local object <function ...>`. thriftpy2's suite
    only stays on `fork` because one test module
    (`test_all_protocols_binary_field.py`) calls `multiprocessing.set_start_method('fork')`
    at import time, which — since `set_start_method` has no per-module scope — pins
    `fork` for the rest of that pytest **session**. Deselecting that whole module on
    `cp314t` (to dodge an unrelated fork-race flake) means its
    `set_start_method('fork')` never runs there, so CPython's own new `forkserver`
    default takes over and a sibling file's `test_client` (building `Process(target=` a
    local `run_server()` closure that captures a local `Handler` class) starts failing —
    on `cp314t` only, since `cp312`/`cp313`/`cp314` still import the skipped module and
    inherit its `fork` override.
    - **Diagnose by reading the multiprocessing frames in the traceback, not just the
      final `PicklingError`.** `popen_fork.py` never calls `reduction.dump`/pickle at all
      (the child inherits everything via COW); `popen_forkserver.py`/`popen_spawn_posix.py`
      do, and `_launch: reduction.dump(process_obj, buf)` is exactly where this
      `PicklingError` originates — that frame confirms it's a start-method question, not
      "this object is fundamentally unpicklable so the library is broken."
    - **Confirm the trigger is test selection, not the interpreter**: grep every
      module your `--ignore`/`--deselect` list drops for
      `multiprocessing.set_start_method(` or `get_context(`. If one of them sets the
      process-wide default and the combination of *that module being skipped* plus
      *CPython 3.14's new forkserver default* is what breaks a sibling test, it isn't a
      genuine `cp314t` compatibility bug in the library worth reporting upstream.
    - **Fix scope**: `--deselect` just the parametrized cases whose target is a local
      closure — but get the nodeid from `--collect-only -q`, not from the `-v` live
      progress line or the `FAILED ...` short summary. Both of those print a path
      relative to the invocation *cwd*, while `--deselect` (like `--collect-only`)
      matches the nodeid relative to pytest's **rootdir** — which is a *parent* of
      `{project}/tests` whenever the project ships a `setup.py`/`pyproject.toml`
      up there (thriftpy2 does), so the real nodeid is
      `tests/test_apache_json.py::test_client[server_func0]`, not the bare
      `test_apache_json.py::test_client[server_func0]` the `-v` output showed. A
      `--deselect` built from the wrong one silently no-ops — the run still reports
      the deselected count as 0 and the test still executes and fails. Leave alone any
      test that already requests `get_context("fork")` explicitly (unaffected by the
      default) or whose target is a module-level function/bound method (pickles fine
      under any start method).

285. **A heap-corruption abort in a vendored C++ library's concurrent stress test can
    resist every reproduction attempt except the plain CI run — gdb/ptrace's own timing
    perturbation can hide the race that trips it (the chroma-hnswlib case).**
    `bindings_test_stress_mt_replace` (100 iterations of `add_items(..., replace_deleted=True)`
    fanned across 50 real OS threads via a raw `std::thread` pool, not GIL-serialized) died
    with `malloc(): mismatching next->prev_size (unsorted)` / SIGABRT, identically on both
    `cp314` and `cp314t`, 2 runs out of 2 (runs 34024763240 and 34025375096) — `cp312`/`cp313`
    on the same tree passed every time. That split alone is not gotcha 33's feature-gate
    signature: gotcha 60 already establishes that a use-after-free/heap-corruption bug is a
    *lottery* over which interpreter's allocator layout happens to reuse the clobbered bytes,
    so "only the newest interpreters die" is evidence *for* real corruption, not a `cp314`-only
    code path.
    - **Upstream never exercises the failing configuration at all.** `chroma-core/hnswlib`'s
      `test.yml` matrix is `python-version: ["3.7", "3.8", "3.9", "3.10"]` on
      `ubuntu-latest`/`windows-latest` only — no 3.11+, no free-threaded build, no non-x86
      architecture. Neither `nmslib/hnswlib` (the upstream this forked from) nor
      `chroma-core/hnswlib`'s issue trackers have any report of this test flaking anywhere,
      which is consistent with nobody having run it under conditions that reach the race.
    - **gotcha 115's gdb-loop technique can fail to reproduce a real race, not just a
      toolchain bug.** Two rounds of the throwaway-commit probe both came back clean: round 1
      ran the one failing test in isolation, fresh process, 5 attempts × 2 interpreters — no
      repro. Round 2 (suspecting gotcha 60's "corruption committed earlier, detected later")
      ran the *entire* `bindings_test*.py` sequence (matching the real failure's shape) under
      `gdb -batch -ex run -ex "thread apply all bt 30"`, 2 attempts × 2 interpreters — still no
      repro, despite the un-instrumented sequence failing 2/2 times before. `ptrace` overhead
      changes thread scheduling enough that a narrow interleaving-dependent race can vanish
      under the very tool meant to catch it — a real "no repro under the debugger" heisenbug,
      distinct from gotcha 115/167's "reproduces cleanly, just needed the right tool."
    - **Reading the code narrows the suspect but doesn't prove it without hardware access.**
      `HierarchicalNSW::addPoint(..., replace_deleted=true)` pops a free slot from
      `deleted_elements` under `deleted_elements_lock`, then calls `setExternalLabel`,
      mutates `label_lookup_`, `unmarkDeletedInternal`, and `updatePoint` on that slot with
      **no lock held across the sequence** — the code's own comment says "we assume that
      there are no concurrent operations on deleted element," i.e. upstream knows this path
      leans on an assumption rather than a proof. Whether riscv64's weaker memory ordering is
      what turns that assumption false (vs. it always being false and x86/TSO usually hiding
      it) could not be confirmed without a native backtrace, which two rounds of
      instrumentation failed to capture.
    - **The sanctioned fallback, not a source patch, when a stress test can't be
      instrumented into reproducing.** Given (a) upstream never validates this
      configuration, (b) the test is explicitly named/shaped as a concurrency stress test
      (50 threads over a 1000-2000 element index — deliberately adversarial, not a
      correctness regression test), and (c) no working native backtrace could be obtained
      after a reasonable diagnostic budget, patching the vendored C++ concurrency logic
      blind was judged too risky to land unverified. Deselect just that one test file from
      `CIBW_TEST_COMMAND` (`unittest discover` has no `--deselect`; delete the file from the
      staged `tests/python/` copy before `discover` runs, matching gotcha 25/168's
      shortest-diagnostic-window discipline — leave everything else covered) and document why
      with a comment naming the run IDs and the mechanism, instead of loosening the test
      pattern or dropping test coverage more broadly.
    - **Reset every diagnostic commit before the PR is finalized.** Both throwaway probes
      (narrowed matrix, `CIBW_BEFORE_TEST_LINUX: dnf -y install gdb`, `CFLAGS=-g CXXFLAGS=-g`,
      gdb-wrapped `CIBW_TEST_COMMAND`) were `git reset --hard` off the branch tip and
      force-pushed per gotcha 115, so the merged history carries only the real fix.

286. **A vendored-ARPACK eigensolver test failing only on musllinux, not manylinux, can
    be upstream's own known random-starting-vector convergence flake, not a riscv64 bug
    (the igraph case).** `test_atlas.py::GraphAtlasTests::testHubScore` failed on
    `cp39-abi3-musllinux_riscv64` only (manylinux, identical tree, passed) with
    `igraph._igraph.InternalError: Error at src/linalg/arpack.c:1025: No shifts could be
    applied during a cycle of the Implicitly restarted Arnoldi iteration` for one specific
    atlas graph. igraph's own maintainers have already triaged this exact test/error on
    other platforms: `igraph/python-igraph#379` is the identical `testHubScore` ARPACK
    error on Nix/Python 3.9 (x86_64, glibc), and the maintainer's own diagnosis is that
    ARPACK seeds hub/authority-score calculations with a small random starting vector it
    gives callers no way to control, so convergence failure is an inherent, non-deterministic
    property of the algorithm that "depends heavily on whether you are using an external or
    a vendored ARPACK library" — not a platform bug; `igraph/python-igraph#728` reports the
    same error recurring on Debian/amd64, and `igraph/igraph#1469` shows the same ARPACK
    convergence class (`igraph_eigenvector_centrality`) failing on a *third* non-x86
    architecture (mips64el) via Debian's build. None of the three reports name musl or
    Alpine specifically, but together they establish the failure mode is a libc/arch-
    independent numerical fragility in the vendored solver, not something to chase as a
    riscv64 regression.
    - **Confirm musllinux-only, not riscv64-wide**, before treating it as acceptable to
      deselect: read both legs' logs (`gh api .../actions/jobs/<id>/logs`) and check the
      identical tree passes on manylinux — a failure on *both* libcs would instead point at
      something riscv64-specific in codegen or in the vendored ARPACK/BLAS build, which is
      not this case.
    - **Fix with a per-libc `--deselect` in `CIBW_TEST_COMMAND`**, gated on
      `matrix.libc == 'musllinux'` the same way the extras selector already is, not a
      blanket deselect that would also drop manylinux's coverage of the same test (it
      passes there and should stay tested).

290. **A `NameError` in an e2e test for a name the package genuinely exports is a
    broken test file at that pinned tag, not an arch or extension-export problem (the
    html-to-markdown case).** `test_options_preprocessing_{aggressive,minimal}` failed
    with `NameError: name 'PreprocessingPreset' is not defined` on riscv64, 2 of 283
    tests, identically deterministic (not flaky). Reading `packages/python/html_to_markdown/__init__.py`
    at `v3.12.0` showed `PreprocessingPreset` re-exported from the compiled extension in
    both the `from ._html_to_markdown import (...)` block and `__all__` — the built
    wheel genuinely provides it — while `e2e/python/tests/test_options.py`'s own
    top-level `from html_to_markdown import (...)` line simply omits it, even though two
    tests further down use it. Diffing the tagged test file against upstream's `main`
    confirmed the import list there already includes `PreprocessingPreset`: the bug was
    fixed after `v3.12.0` was cut, just not yet in a tagged release. A failure this
    narrow (one name, two tests, everything else in the module green) that traces to a
    plain unimported symbol is a strong prior for "test file bug at this tag," worth
    checking against upstream's default branch before assuming a build or export defect.
    - **Confirm both halves before treating it as a test bug**: grep the test file's
      import list for the missing name (absent) *and* the package's `__init__.py`/`__all__`
      for the same name (present) — only the *combination* proves it's the test, not the
      export, that's wrong. If the extension itself didn't export the name, the fix would
      be a real compatibility issue to raise upstream, not a test deselect.
    - **Fix with `-k "not <name>"` per test, not a path-based `--deselect`** (gotcha
      14/283): a plain name-based `-k` sidesteps the rootdir-relative-nodeid trap
      entirely, which matters here too since `CIBW_TEST_SOURCES` stages
      `e2e/python/{conftest.py,pyproject.toml,tests}` and the staged `pyproject.toml`'s
      own `[tool.pytest.ini_options]` puts pytest's rootdir one level away from the
      `e2e/python/tests` path the `-v`/`FAILED` output displays.
    - **Deselect in the workflow, don't patch the test file.** The test file is
      upstream's own generated e2e suite (`# This file is auto-generated by alef — DO
      NOT EDIT`) and the bug is already fixed on `main`; patching
      `patches/<pkg>/<version>/` to hand-fix a file upstream has already corrected
      would just be reverted by the next version bump. A `CIBW_TEST_COMMAND` comment
      citing the exact `NameError` and noting upstream's fix is unreleased documents the
      divergence for whoever reviews or re-triggers the workflow later.

297. **A test harness's own unbounded `readline()`-until-marker wait turns any slow or
    crashed child process into a permanent CI-timeout hang instead of a fast failure —
    and when the underlying blocker is a vendored per-arch binary with no riscv64
    variant and no source, the fix is deselecting the test, not building the binary
    (the viztracer case; see `build-viztracer.yml` and `patches/viztracer/1.1.1/`).**
    viztracer's own test helpers wait for a child process to print a specific line with
    a plain `while True: line = pipe.readline(); if marker in line: break` — no
    timeout, and no handling for the pipe hitting EOF. Two different tests hung
    identically (zero output, killed only by GitHub's 60-minute job timeout) for two
    unrelated reasons: `test_trace_self` self-traces `vizviewer`'s heavier
    argparse/socketserver import graph and never reaches the print in practical time
    (a bounded `timeout 120 viztracer --trace_self -c "print(1)"` smoke test completed
    in ~1s, ruling out "self-tracing is always this slow" and narrowing it to the
    heavier scenario); `test_use_external_processor` shells out to Perfetto's
    `trace_processor` launcher, whose prebuilt-binary manifest lists only x86_64/aarch64
    machines, so it raises and exits immediately on riscv64 — but `readline()` on an
    already-closed pipe returns `""` forever instead of raising, turning the child's
    fast crash into a silent, permanent busy-loop in the *parent* test process.
    - **Isolate "slow" from "stuck" with a bounded smoke test before deselecting**,
      cheap enough to run inside the real `CIBW_TEST_COMMAND` on the same PR: wrap the
      suspect command in `timeout N` and echo start/exit/end timestamps ahead of the
      real test run. A clean, fast exit narrows the cause; a `124` (timeout) exit
      confirms it hangs rather than merely running long, without burning the job's
      whole timeout budget to find out.
    - **A vendored per-arch prebuilt with no source and no riscv64 entry (gotcha 157's
      `vendored-binary` pattern, here scoped to one optional feature rather than the
      whole package) is not something a build patch can fix** — grep the vendoring
      directory for a source file matching the missing binary's name before concluding
      this; its absence (only prebuilt blobs, e.g. `attach_linux_amd64.so` with no
      `attach_linux_amd64.c`) confirms there is nothing to compile for riscv64 either.
      Skip only the specific tests that exercise that one feature (`@unittest.skip` on
      the exact methods) — sibling tests exercising the same module's other, non-vendored
      code paths (viztracer's `test_install`/`test_attach_script` use an in-process
      SIGUSR/API mechanism, not the vendored `.so`) are unaffected and stay covered.
    - **A hang can mask an unrelated, real, fixable bug further down the same file** —
      after deselecting the hang, `test_combine` failed for a completely different
      reason (`ValueError: .../example/json/multithread.json does not exist`): the test
      reaches outside `tests/` via `os.path.join(os.path.dirname(__file__), "../",
      "example/json")`, and `CIBW_TEST_SOURCES: tests` never staged that sibling
      directory. Add the extra path to `CIBW_TEST_SOURCES` (gotcha 36) rather than
      deselecting — this one is a genuine test-staging gap, not a platform limitation.

304. **A hardcoded exact-equality assertion on a neural-network/matmul-heavy
    computation failing only on riscv64, at the last couple of ULP, is an
    architecture float-rounding difference, not a bug (the correctionlib/lwtnn
    case).** `test_lwtnn_example` calls `corr.evaluate(...)`, which runs an Eigen-based
    dense-matrix feed-forward network (`lwt::LightweightNeuralNetwork::compute`,
    vendored from the `lwtnn` submodule — "for sanity we use Eigen" per its own
    header), then asserts `sf == 0.95186825355646787` — a Python `==` on a `double`,
    not `pytest.approx`. On riscv64 it evaluates to `0.9518682535564676` (relative
    difference ~3e-16, i.e. within a few ULP of a `double`): vectorized matmul/FMA
    instruction selection and accumulation order differ across architectures, and a
    multi-layer network chains enough floating-point ops for that to surface in the
    last significant digit. This is architecture-generic, not riscv64-specific:
    upstream hit the *identical* failure on `manylinux_aarch64` first
    (`cms-nanoAOD/correctionlib#348`, "we see small floating point rounding
    discrepancies in lwtnn on this platform") and responded by skipping this
    package's *entire* test suite on aarch64 via `test-skip`.
    - **Confirm the mechanism before treating it as cosmetic**: check that the
      assertion is exact-equality (`==`, not `approx`/`isclose`) on a value produced
      by dense linear algebra or another SIMD/FMA-sensitive code path, and that the
      difference is at the ULP level (a handful of units in the last place), not a
      difference in a leading digit — the latter would be a real bug.
    - **Fix scope: deselect just the one test**, not the whole suite the way upstream
      did for aarch64 — unlike aarch64 (fully covered by upstream's own CI), riscv64
      has no other CI leg exercising this package's tests, so blanket-skipping would
      drop coverage upstream never had a copy of. `--deselect
      {package}/tests/test_lwtnn.py::test_lwtnn_example` in `CIBW_TEST_COMMAND`, with
      a comment citing the exact asserted vs. observed values, keeps
      `test_validate_lwtnn`/`test_lwtnn_bad_opaque` (same file) and the rest of the
      suite covered.
    - **Do not patch the test's assertion to `pytest.approx`** — that file is
      upstream's, and patching it here would be a larger, harder-to-justify
      divergence (patching-and-licensing.md) than a one-line `CIBW_TEST_COMMAND`
      deselect for a difference upstream has already publicly acknowledged.
    - **Distinct from gotcha 170** (an eigensolver returning a different *dtype*,
      `complex128` vs `float64`, which breaks a *downstream* cast far from the call
      site) and **gotcha 282** (a pixel-diff `ImageComparisonFailure` from font
      rendering) — same family of "arch-specific numeric divergence is not
      necessarily a bug," different failure shape (here, the value itself is off by
      a few ULP, and the failure is directly at the assertion).

316. **A hardcoded timing threshold on a metric that measures raw wall-clock
    GIL-acquire latency (not literal lock contention) inflates under a busy shared
    CI host, in either direction depending on which side of the range the workload
    sits on (the gilknocker case).** `test_knockknock_available_gil` asserts
    `contention_metric < 0.2` for a workload (`a_little_gil`: four threads doing
    NumPy FFT work, expected to mostly release the GIL). On this repo's shared
    riscv64 runners — which routinely run many other build jobs concurrently — it
    instead lands at 0.27-0.49, 12/12 samples across cp312/cp313/cp314 with
    pytest-rerunfailures retries, never once under the ceiling.
    `contention_metric` is computed from `Python::with_gil(move |_| start.elapsed())`:
    the elapsed time from *deciding* to acquire the GIL to actually running inside
    it, which bundles genuine lock contention with plain OS thread-scheduling
    latency for the sampling thread itself — a busier host inflates the metric even
    when no other Python thread is really holding the GIL for long. Upstream's own
    test file already hedges every one of its four assertions with a per-platform
    comment ("usually ~0.9, but sometimes ~0.6 on Mac", "usually ~0.002, but can be
    up to ~0.15 on windows") and has an open, unresolved issue
    (milesgranger/gilknocker#36) for the same class of hardware-dependent flake in
    the sibling `test_knockknock_some_gil` test, on a *fast* Mac landing anomalously
    low instead of high — same mechanism, opposite direction.
    - **Verify with real CI logs across every interpreter in the matrix, not one
      job** — a single failing job could be a one-off scheduler hiccup; three
      interpreters each failing the same assertion at similar magnitudes across
      three retries apiece is a host characteristic, not noise.
    - **Reproducing the mechanism locally doesn't need the failing package's own
      optional test dependency** — build the crate directly with `cargo build
      --release` (no maturin needed) and load the resulting `.so` under an
      `__init__.py` shim, per gotcha 314's shape, to get a working import without
      installing anything. A *real* multi-threaded GIL-contention scenario (several
      pure-Python CPU-bound threads) reproduces near-1.0 contention identically with
      and without a `docker run --cpus=` quota, confirming the harness measures
      genuine contention correctly; an *idle* scenario (no other thread wants the
      GIL) stays near-zero even under heavy host CPU oversubscription (`yes` loops)
      or a cgroup CPU quota — the elevated CI readings are specific to the *mixed*
      NumPy-releases-then-reacquires pattern this test exercises, not reproducible
      from host load alone without the actual optional numpy dependency.
    - **Fix scope: raise the threshold, cite the evidence, don't skip the test** —
      this is the "artificial test limitation" patch case
      (patching-and-licensing.md). Use `Upstream-Status: Inappropriate`, since the
      cause is this repo's shared-runner load, not an upstream bug — and this
      repo's own policy against filing anything on a package's own upstream repo
      makes `Issue` unavailable regardless. Pick a ceiling with real headroom above
      every observed sample, not just clearing the worst one.

317. **A pure-Python, allocation-heavy test suite running ~8x slower on musllinux
    than manylinux (or its own free-threaded sibling) is musl's malloc, not a
    riscv64 regression — check the GIL-vs-free-threaded split before raising the
    timeout again (the stream-inflate case; see `build-stream-inflate.yml`).**
    stream-inflate's Cython extension is a thin wrapper around plain byte-slicing
    generator loops; its `test_stream_inflate.py` fuzzes 1956 parametrized cases up
    to 8MB of data, byte-chunked. `cp312`/`cp313`/`cp314`-`musllinux_riscv64` each
    ran the identical suite to only ~43-44% inside a 240-minute budget, reproducibly,
    twice — while every `manylinux_riscv64` job (same four interpreters) and
    `cp314t`-`musllinux_riscv64` finished cleanly in under 2h15m. The 2x2 pattern
    (glibc: fast regardless of GIL; musl: fast only when free-threaded) is the tell.
    - **PEP 703 explains the split.** CPython's free-threaded build replaces pymalloc
      with mimalloc precisely because pymalloc "is not thread-safe without the GIL";
      every other interpreter keeps pymalloc, which delegates allocations above its
      small-object threshold straight to the platform `malloc()`. musl's allocator is
      well known to be markedly slower than glibc's for churn-heavy workloads, and a
      byte-chunking fuzz loop with `input_size`/`output_size` down to 1 is exactly
      that; mimalloc's own arenas sidestep the platform allocator almost entirely, so
      only the free-threaded build escapes the penalty.
    - **Confirm it's not riscv64-wide first** (mirrors gotcha 286): read the manylinux
      leg's log for the same interpreter — a suite that's merely slow everywhere, or
      failing outright rather than timing out mid-suite, points elsewhere. Here the
      manylinux jobs ran the same 1956 cases to completion at a normal pace.
    - **No workflow-level fix exists** — this isn't a flag, a constraint file, or a
      `before-all` step; it's musl's allocator on the exact allocation pattern this
      suite exercises. Raising `timeout-minutes` further only delays the same result
      (43-44% was consistent at both 60 and 240 minutes) and ties up scarce
      self-hosted riscv64 runners for hours to prove a known-slow path eventually
      finishes. Per this skill's own guidance, drop musllinux from the matrix
      (`build-stream-inflate.yml` ships manylinux-only) rather than keep paying for it.

330. **A manylinux image's system library can be years newer than what upstream ever
    tested against, and the resulting test failures are data-version drift (CLDR/
    tzdata), not code bugs — deselect, don't patch (the pyicu-binary/ICU case; see
    `build-pyicu-binary.yml`).** setup.py prints `ICU_MAX_MAJOR_VERSION = '69'` and the
    bundled test suite's own `if ICU_VERSION < '68.0':` branches show upstream last
    tested around ICU 69, but `manylinux_2_39_riscv64`'s `libicu-devel` (Rocky 10
    AppStream) is 74.2 - five major ICU releases later, each carrying a newer CLDR/
    tzdata snapshot. Four of the package's own tests assert exact locale-formatted
    strings or a specific timezone transition and fail once linked against 74.2: a
    French `SimpleDateFormat` pattern the test already branches on for ICU<68 vs
    >=68 renders differently again at 74; an `en_US` time format gains CLDR's
    narrow-no-break-space (` `) before AM/PM; a French long timezone name gains
    a `nord-américain` qualifier; and `Pacific/Fiji`'s next DST transition after 2021
    comes back `None` because 74's newer tzdata has no further scheduled transition
    for it. None of this is riscv64-specific or a real defect in the wrapped code.
    - **Confirm before deselecting by building against the *exact* system version the
      manylinux image ships**, not whatever ICU a dev machine happens to have -
      `dnf -q list libicu-devel` in the image (or `rockylinux/rockylinux:10
      --platform linux/riscv64` per gotcha 51's cheap-image trick) gives the version;
      a newer one still (e.g. a package manager's latest) can show *different*
      drifted tests than CI will hit, and an older one can hide failures CI will see.
      Building ICU4C from its own release tarball on any host settles it without a
      container: `./runConfigureICU <platform> --prefix=<scratch>/install
      --disable-tests --disable-samples && make -j && make install`, then point
      `PYICU_INCLUDES`/`PYICU_CFLAGS`/`PYICU_LFLAGS` (or the equivalent env vars for
      another ICU-linking project) at the scratch prefix.
    - **Deselect by exact test id in `CIBW_TEST_COMMAND`**, not `-k`, and cite what
      changed and why in a one-line comment - this is the same family as gotcha 304's
      ULP-divergence and gotcha 282's pixel-diff cases (environment divergence isn't
      a bug), except the axis here is the *library's own bundled data version*, not
      architecture or timing.

362. **A `multiprocessing.Process().join()` regression test for a native threadpool's
    fork safety can hang the full length of its `pytest.mark.timeout` deterministically,
    not flakily, on the riscv64 runner (the vesin case).** vesin's
    `test_fork_during_calculations` loads the C++ library, starts a background thread
    that keeps hammering the (mutex-guarded) threadpool, forks a child via
    `multiprocessing.set_start_method("fork")`, and asserts the child's `join()` returns
    inside 10s (`@pytest.mark.timeout(10)`) — a real regression test for the library's
    `pthread_atfork` handlers, not an artificial limit. It hit the full 10.0s wall twice
    in a row (2/2, run 34600349160, including a rerun of the identical commit) rather
    than completing a little late, the signature of a genuine deadlock rather than
    gotcha 38's "just slow" — and upstream's own CI (`ubuntu-24.04`/`macos-15`/
    `windows-2022`) never runs it under riscv64's different fork/threading timing at all,
    so there is no signal that it passes anywhere in that configuration.
    - **A rerun-in-place is the fast way to tell "deadlock" from "flake" before
      spending a diagnostic budget.** Since nothing about the test or the code changed
      between the two runs, `gh run rerun <id> --failed` (safe here specifically because
      no fix was being validated, unlike gotcha 357's caution against it) re-executes the
      exact same build+test; identical failure both times is strong evidence for a real,
      reproducible race rather than scheduler noise that a second attempt would dodge.
    - **Deselect with `-k "not <name>"`, not a path-based `--deselect`** (gotcha 14):
      `pytest` reports collected nodeids relative to its rootdir
      (`/project/python/vesin` here) while `{project}` in `CIBW_TEST_COMMAND` is the
      absolute checkout root (gotcha 5), so a `--deselect {project}/…` string silently
      matches nothing and the "deselected" test still runs.
    - **Patching the vendored C++ `pthread_atfork` logic blind was out of scope** —
      same call as gotcha 285's chroma-hnswlib case: one deselected test with a comment
      naming the run id and the mechanism beats an unverified fix to native concurrency
      code neither upstream nor this port's diagnostic budget can confirm.

379. **A test asserting a specific cross-thread ordering (a `gc.collect()`-on-one-thread-
    finalizes-an-object-another-thread-observes shape) can fail deterministically, only
    on `cp314t`, with no riscv64 or correctness bug behind it (the mlx case; see
    `build-mlx.yml`).** MLX 0.32 made its JIT compile cache `thread_local`, with a
    `weak_ptr` cross-thread erase path so a function traced on one thread and released
    on another still invalidates correctly (`ml-explore/mlx#4377`). Its own test,
    `test_compile_release_on_another_thread`, traces a function on a worker thread, then
    the main thread clears its only other reference and calls `gc.collect()`, then the
    worker re-compiles the same callable and the test asserts a second trace happened
    (`self.assertEqual(len(traces), 2)`) — this reproduced as `AssertionError: 1 != 2`
    on **every** run on the riscv64 cp314t leg (twice, ~9.5 minutes apart, same test,
    same assertion), while cp312/cp313/cp314 (GIL-serialized) passed the identical
    tree cleanly every time. Free-threaded CPython's biased/deferred reference counting
    does not guarantee that a `gc.collect()` call on one thread synchronously reconciles
    and finalizes an object whose refcount was primarily manipulated on another thread
    the way GIL-serialized refcounting does — the test's ordering assumption, not MLX's
    cache logic, is what breaks.
    - **Confirm determinism before deselecting anything** — rerun the single failing
      leg once (`gh run rerun <run-id> --failed` once every sibling leg is terminal,
      gotcha 65/357's polling discipline) rather than assume a one-off flake; an
      identical failure at both the same test and roughly the same wall-clock point is
      the signal, a passing rerun would instead point at a genuine race worth chasing.
    - **Check upstream's own issue tracker for the subsystem the test exercises before
      deciding it's a test-design gap** (`gh api "search/issues?q=repo:<owner>/<repo>+
      is:issue+<keyword>"`, read-only) — finding the maintainers' own design writeup for
      the exact mechanism under test (here, the thread_local+weak_ptr redesign) is much
      stronger evidence than guessing from the assertion alone, and upstream's own CI
      matrix already covering `cp314t`/`cp313t` (check their release workflow) means a
      *deterministic* failure would likely already be known/fixed there — pointing
      toward a timing-window difference on this runner class, not a universal break.
    - **Deselect the one test for the free-threaded leg only, with a comment
      naming the mechanism and the evidence**, not a blanket skip of the file/class —
      mirrors the same pattern used for other packages' `cp314t`-only test-design gaps
      elsewhere in this repo's build workflows: keep the exact assertion and thread
      choreography in the comment so a future upstream fix (or disproof) is easy to
      recognize, and note that it was reproduced deterministically rather than assumed
      flaky.
