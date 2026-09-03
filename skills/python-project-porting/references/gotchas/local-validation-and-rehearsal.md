# Gotchas — Local validation & the aarch64/QEMU rehearsal

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/local-validation-and-rehearsal.md`.

## In this file

- **9** — Validate before every push
- **52** — Dry-run the *test* phase against upstream's released PyPI wheel before you build
- **85** — Dry-run the test phase at the dependency versions the *container* will resolve,
- **101** — Validate a riscv64 cibuildwheel workflow by running it verbatim on
- **113** — The aarch64 validation run (gotcha 101) does NOT exercise from-source dependency
- **178** — Run gotcha 101's riscv64 `pip download` check inside a *Linux* container, and run
- **180** — The aarch64 rehearsal defaults to the *wrong* base image — pass
- **188** — A fat-LTO maturin release profile makes a full QEMU riscv64 build-rehearsal too

---

9. **Validate before every push**. Cheap local checks that catch the dumb stuff:
   - `python -c "import yaml; yaml.safe_load(open('<wf>'))"` — YAML parses.
   - `actionlint <wf>` — it runs shellcheck on `run:` blocks too. The only expected
     warning is `label "ubuntu-24.04-riscv" is unknown` (custom self-hosted runner);
     every workflow trips it. Fix everything else (SC2011 `ls|xargs`, SC2129 repeated
     `>>` redirects, etc.) to match repo cleanliness.
   - Simulate shell pipelines against sample input under `bash`.
   - Run the wheel's import/smoke line against a locally-built wheel in a venv.
   - Use docker to run cibuildwheel on riscv64. For a heavy from-source C++ build
     (gotcha 15), a `cmake` *configure* under `--platform linux/riscv64` is a cheap
     proxy that catches flag/dep errors without the full multi-hour compile.
   - **Run cibuildwheel under QEMU** on a non-riscv host (a full build+smoke loop
     can be validated this way on an aarch64 machine):
     - Needs `qemu-riscv64` binfmt with the **`F` (fix-binary) flag** —
       `grep flags /proc/sys/fs/binfmt_misc/qemu-riscv64` should show `F`; that's
       what lets QEMU run *inside* the manylinux container.
     - Needs **cibuildwheel ≥ 3** (4.2.0 works) — older versions don't know the
       `manylinux_riscv64` arch and error out. `uv tool install cibuildwheel` may
       fetch a stale one; check `--print-build-identifiers --archs riscv64`.
     - Fetch a riscv64 wheel on a non-riscv host to inspect it with plain
       `pip download --platform manylinux_2_39_riscv64 --python-version 313
       --implementation cp --abi cp313 --only-binary=:all: <pkg>` (`uv pip
       download` does not exist).
     - Iterate fast: first pass with `CIBW_TEST_SKIP="*"` (build only), then
       validate the import in a raw `docker run --platform linux/riscv64 …`
       container — far quicker than a full cibuildwheel rebuild to re-run tests.

52. **Dry-run the *test* phase against upstream's released PyPI wheel before you build
    anything.** When a port replaces an unusable upstream test-dependency mechanism
    (duckdb exports `uv`'s lock, which resolves torch from `download.pytorch.org` and
    tensorflow — neither has riscv64), the reduced `CIBW_TEST_REQUIRES` you write in its
    place is a guess until something runs it. It can be settled in minutes on **any**
    host, no QEMU and no compile: `pip install <pkg>==<ver>` from PyPI, `cp -a` the
    checkout's test paths into an empty dir the way `test-sources` stages them, and run
    upstream's exact `test-command` there.
    - It catches the deps that are *not* optional: duckdb's spark tests are behind
      `importorskip("duckdb.experimental.spark")`, which fails on a missing
      **`typing_extensions`** — so leaving it out silently skipped ~100 tests and left
      3 collection errors, all invisible until a multi-hour riscv64 job ended.
    - It also proves the *omitted* deps are safely omitted (pyarrow/polars/torch/
      tensorflow-guarded tests skip rather than error), and gives you the pass/skip
      counts to quote in the PR — the same evidence a reviewer would otherwise have to
      take on trust.
    - Cheap enough to redo whenever you touch the dependency list; the whole duckdb
      suite ran in 26s on a laptop against the macOS wheel.

85. **Dry-run the test phase at the dependency versions the *container* will resolve,
    not at whatever pip hands your laptop (refines gotcha 52).** Gotcha 52's dry run installs
    the released PyPI wheel and runs upstream's `test-command` on any host — but on an
    unconstrained host pip fetches today's newest scientific stack, while inside the container
    `PIP_ONLY_BINARY` + our registry pin the deps several releases back. Running the two gives
    opposite answers: statsmodels 0.14.6 against scipy 1.18.1 fails **41** tests on removed
    private APIs (`ImportError: cannot import name '_lazywhere' from 'scipy._lib._util'`,
    `No module named 'scipy._lib.array_api_extra'`) plus derived numeric failures; the same
    command against scipy 1.15.2 — the version the registry actually offers — is
    `17037 passed, 726 skipped, 126 xfailed, 3 xpassed`, zero failures.
    - **Read the registry index first, then pin your local venv to match** before you conclude
      anything from a red local run. Otherwise you spend the cycle diagnosing upstream's
      incompatibility with a dependency your build will never install, or — worse — patch
      around it.
    - Note pip's own resolution does part of this for you: a pinned `scipy==1.15.2` caps
      `numpy<2.5`, so the container's numpy is 2.4.x even though the registry has 2.5.2.
      Reproduce the resolution, don't hand-pick each version.

101. **Validate a riscv64 cibuildwheel workflow by running it verbatim on
    `manylinux_2_39_aarch64` — same image family, native speed, minutes not hours.** The
    riscv64 and aarch64 manylinux images are the same Rocky 10 build, so a full
    `cibuildwheel --only cp3XX-manylinux_aarch64` run with *your* `CIBW_BEFORE_BUILD`,
    `CIBW_ENVIRONMENT`, `CIBW_TEST_SOURCES`, `CIBW_TEST_REQUIRES` and `CIBW_TEST_COMMAND`
    exercises every one of them for real: the `dnf`/`yum` package names, the option cascade
    (the log's `before_build:` line proves your env var actually beat the pyproject table),
    auditwheel repair, abi3audit, `test-sources` staging, and the full test command in a
    container. It is native on an arm64 host — a 190-crate Rust workspace with LTO took 7
    minutes — where the QEMU riscv64 equivalent is hours. Only arch-specific codegen goes
    unchecked. Install cibuildwheel into a venv under `.git/pw-scratch/<pkg>/` so nothing
    lands outside the repo.
    - **Settle the whole riscv64 test-dependency resolution on the host too**, which
      sharpens gotcha 30 from "do we host this name?" to "what will pip actually pick?":
      ```bash
      pip download --only-binary=:all: -d /dev/null \
        --platform manylinux_2_39_riscv64 --platform manylinux_2_31_riscv64 \
        --platform manylinux_2_34_riscv64 --platform manylinux_2_38_riscv64 \
        --python-version 310 --implementation cp --abi cp310 --abi abi3 --abi none \
        --extra-index-url https://pypi.riseproject.dev/simple/ <deps...>
      ```
      **`--abi abi3 --abi none` is load-bearing**: with only `--abi cp310` pip matches the
      literal ABI tag and silently rejects every `cpNN-abi3` and `py3-none-any` wheel, so a
      resolvable set looks impossible. Pass each `manylinux_2_NN_riscv64` variant the
      registry actually uses — our wheels are not all built against the same glibc floor.
      It prints the exact versions the CI test phase will install (and proves pip can
      backtrack to them), which is also what you quote in the PR.

113. **The aarch64 validation run (gotcha 101) does NOT exercise from-source dependency
    builds — force them with `PIP_NO_BINARY`.** aarch64 is the same Rocky 10 image family,
    but it is *not* in the same position on PyPI: every dependency that lacks a riscv64
    wheel and must be compiled in the real job usually has an aarch64 wheel that the
    validation run installs instead. So the rehearsal can be green while the riscv64 job
    fails inside a dependency's compiler run — which is what happened to spacy: preshed,
    cymem, srsly, thinc and blis were all wheels locally and all sdists on riscv64. Add
    the packages our registry does not host to the run's environment:
    `CIBW_ENVIRONMENT: ... PIP_NO_BINARY=preshed,murmurhash,cymem,srsly,thinc,blis`,
    and the local run reproduces the real dependency chain (spacy: 7 minutes became 9).
    - **Enumerate the list from the dependency check, not by guessing** — it is exactly
      the set that answered "no riscv64 wheel on PyPI, 302 from our registry" (gotcha 30).
    - Keep `PIP_NO_BINARY` out of the committed workflow: on riscv64 those packages have
      no wheel anyway, so it would be noise that also blocks a future registry wheel from
      being used.

178. **Run gotcha 101's riscv64 `pip download` check inside a *Linux* container, and run
    it over the resolved closure rather than the direct dependencies (the habluetooth case).**
    Gotcha 113 warns that the aarch64 rehearsal installs wheels where riscv64 would compile
    from sdist, and offers `PIP_NO_BINARY` as the corrective. That cannot catch the commoner
    inverse: a dependency two levels down whose newest release has **no riscv64 wheel at
    all**, so the aarch64 run resolves it silently and the riscv64 job dies in the
    *test-phase* `pip install <wheel>`, after a clean build and auditwheel repair.
    habluetooth -> `bluetooth-data-tools` -> `cryptography`: PyPI's newest cryptography ships
    no riscv64 file, so pip fell back to its sdist and died on `Target triple not supported by
    rustup: riscv64-unknown-linux-gnu` (gotcha 10's missing `gc`). Fix is gotcha 67's, applied
    to a name you never typed: `PIP_EXTRA_INDEX_URL` plus `PIP_ONLY_BINARY=<that one dep>`, so
    the newer PyPI release stops being a candidate and resolution lands on our wheel.
    - **`pip download --platform` does not override *marker* evaluation**, which is taken
      from the host, so running the check on macOS makes every `platform_system == "Darwin"`
      requirement real — bleak's `pyobjc-core` turned a fine dependency set into a
      `ResolutionImpossible` naming 60 versions of bleak. Run the same command in any Linux
      container (the aarch64 manylinux image will do) and the markers evaluate as the target
      does.
    - **Feed it the whole `requires_dist` closure, not the package's own list.** The gotcha-40
      sweep reads one level; the blocker here was three levels down and had no riscv64 file on
      either index, which is exactly what the download check reports in one line.

180. **The aarch64 rehearsal defaults to the *wrong* base image — pass
    `CIBW_MANYLINUX_AARCH64_IMAGE` explicitly (sharpens gotcha 101).** `cibuildwheel --only
    cpXY-manylinux_aarch64` uses cibuildwheel's default aarch64 image,
    `manylinux_2_28_aarch64`, which is **AlmaLinux 8** — a different distro generation from
    the Rocky 10 that `manylinux_2_39_riscv64` is built on, with a different package set and
    a much older toolchain. So the rehearsal whose whole purpose is to catch `dnf`/`yum` and
    toolchain differences quietly validates the wrong base and goes green on a recipe that
    fails in CI. Set `CIBW_MANYLINUX_AARCH64_IMAGE=quay.io/pypa/manylinux_2_39_aarch64` on
    the run. Concretely: the 2_28 run built, repaired and tested the wheel in two minutes,
    while the 2_39 run on the identical tree died at `/usr/bin/ld: cannot find -lstdc++`
    because RHEL 10 moved `libstdc++.a` into `libstdc++-static` (gotcha 77) — exactly the
    class of failure the rehearsal exists to find.

188. **A fat-LTO maturin release profile makes a full QEMU riscv64 build-rehearsal too
    slow to bother with — override it for the *local* run only, not the shipped
    workflow (the prek case).** Gotcha 9's "use docker to run a full build+smoke loop
    under QEMU" is cheap for most Rust ports, but a project whose `Cargo.toml` sets
    `[profile.release] lto = "fat"` + `codegen-units = 1` (prek, like the delta-rs/polars
    cases in gotcha 141's neighbourhood) turns that into a real multi-hour emulated
    build before you have learned anything a `cargo check` cross-compile (gotcha 179)
    didn't already tell you. Set `CARGO_PROFILE_RELEASE_LTO=off
    CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16 CARGO_PROFILE_RELEASE_OPT_LEVEL=0` as env vars
    on the `docker run` invoking `maturin build --release` — this is the same
    env-var-not-Cargo.toml mechanism gotcha 141 documents for shrinking a *shipped*
    workflow's build cost, just applied only to your throwaway rehearsal — and a
    ~400-crate riscv64gc-unknown-linux-gnu wheel (prek, `bindings = "bin"`) built end to
    end under `quay.io/pypa/manylinux_2_39_riscv64` via QEMU in **13 minutes** instead of
    however long fat LTO would have taken emulated. Confirms the same dependency graph,
    `cmake`/`aws-lc-sys` linkage, licence globbing and wheel tag that the real build
    produces — only the codegen cost differs. **Do not carry the override into the
    workflow** unless the real runner actually cannot afford upstream's profile (check
    gotcha 141's per-core timing table first): prek's native riscv64 build with the full
    fat-LTO profile still finished in under an hour on the shared 4-core runners, well
    inside the timeout, so shipping upstream's own profile unmodified was both correct
    (goal 2: mirror upstream) and affordable.
