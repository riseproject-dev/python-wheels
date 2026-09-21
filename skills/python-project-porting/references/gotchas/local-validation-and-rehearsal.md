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
- **223** — For a `bindings = "bin"` CLI's test assertions, `cargo build --release` the tool
- **298** — A local rehearsal's `pip`-resolved cibuildwheel can be too old for
- **369** — Without docker, fetch Rocky 10's own dnf repodata over plain HTTPS to
- **384** — `dnf` failing in the image with `Curl error (60) ... self-signed certificate` is
- **394** — A libtorch-linking project cannot be rehearsed on x86_64 with PyPI's `torch`
- **417** — A QEMU riscv64 rehearsal of a cibuildwheel job needs `CI=1` for
  scikit-build-core's CMake probe, and needs `CIBW_BEFORE_ALL`'s staging replayed.
- **412** — When no riscv64 image or cross-toolchain is reachable, exercise a C/C++ source's
  your egress proxy, not the image — install the proxy CA into the container trust store
- **403** — Prove which build *variant* you are about to produce by stubbing the build
  backend's `setup()` on the host
- **404** — For a from-source C++ world, a *full CMake configure* inside the real riscv64
  image is the honest local ceiling
- **410** — Gotcha 188's "lower the optimisation level for the local rehearsal only" can
  silently produce a broken wheel when the project has a C99 `inline` helper with no
  `static` — and the suite still passes, because the pure-Python fallback catches it.
- **430** — A `-k`/`--ignore` change is verifiable offline with no wheel at all: rebuild the
  failed run's node ids into a synthetic test tree, then run the YAML-folded
  `CIBW_TEST_COMMAND` through `sh -c`.
- **444** — Verify a hand-edited `.patch` with `git apply --check`, never with `patch`:
  a wrong `@@` line count makes GNU `patch` silently swallow the *next* hunk and exit 0.
- **490** — An ecbuild/CMake project that installs its generated config header into the
- **495** — A Bazel port's loading phase rehearses on x86_64 in minutes, even in a sandbox
  that cannot fetch the dependencies.
  wheel hands you a byte-comparable feature oracle

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

223. **For a `bindings = "bin"` CLI's test assertions, `cargo build --release` the tool
    *natively on the dev host* (any arch — the CLI's exit-code/output logic is
    architecture-independent) instead of guessing exit codes from docs (the zizmor
    case).** zizmor's own docs describe severity-scaled exit codes ("11-14, informational
    through high") but not which value maps to which severity. Rather than writing a CI
    test step with a guessed range check, `cargo build --release --locked --manifest-path
    crates/zizmor/Cargo.toml` on the arm64/x86_64 dev machine (already has `cargo`/`rustc`
    installed — this is *using* existing tooling, not installing anything) produced a real
    `target/release/zizmor` in a few minutes, and running it against upstream's own
    known-bad fixture (`crates/zizmor/tests/integration/test-data/artipacked.yml`, the
    same file `tests/integration/audit/artipacked.rs` snapshot-tests) gave the exact exit
    code (`13`) and output shape to assert on, plus confirmation that a hand-written
    known-clean workflow really does exit `0`. Do this from a scratch clone under
    `.git/pw-scratch/<pkg>/` (gotcha 9's validation loop, not a new location) — never from
    the PR worktree. This only substitutes for the *riscv64* build/CI cycle when the
    behaviour under test is host-arch-independent (CLI logic, exit codes, stdout shape); it
    proves nothing about whether the crate graph actually compiles for
    riscv64gc-unknown-linux-gnu — pair it with gotcha 78's `cargo metadata
    --filter-platform` check for that.

298. **A local rehearsal's `pip`-resolved cibuildwheel can be too old for
    `CIBW_TEST_SOURCES` to do anything, and it fails silently, not loudly (the
    mecab-python3 case).** Gotcha 101's venv-under-`.git/pw-scratch/<pkg>/` install is
    usually just `pip install cibuildwheel`, which resolves whatever the *venv's own*
    Python floor allows — a venv built from a pre-3.11 interpreter caps out at
    cibuildwheel 2.23.x, which predates the `test-sources`/`CIBW_TEST_SOURCES` option
    entirely. It is not rejected as an unknown key: cibuildwheel 2.x silently ignores it,
    tests run from an empty `test_cwd`, and the run fails with cibuildwheel's own built-in
    `test_fail.py` scaffold ("cibuildwheel executes tests from a different working
    directory... use the `{project}` placeholder") — a message that reads like *your*
    `CIBW_TEST_COMMAND` is wrong, not like a tooling-version mismatch, and sends you
    hunting through path/glob logic for nothing. Rebuild the rehearsal venv from a
    Python ≥3.11 interpreter (`/opt/homebrew/bin/python3.12 -m venv`, say, alongside a
    default `python3` that is older) and pin the same major `cibuildwheel` version the
    target workflow uses (`pip install cibuildwheel==4.2.0`) before trusting a green
    (or this particular red) local run.

369. **Without docker, fetch Rocky 10's own dnf repodata over plain HTTPS to answer
    "is package X available", "which version", and "what file does it actually
    install" for `manylinux_2_39_riscv64` — no container runtime needed (the
    imagecodecs case; see `build-imagecodecs.yml`).** `quay.io/pypa/manylinux_2_39_riscv64`
    is a Rocky 10 riscv64 image with `baseos`/`appstream`/`crb` enabled (gotcha 100);
    that means its exact package set is Rocky's own public riscv64 SIG mirror, fetchable
    straight from a plain `curl` on any host, x86 laptop included:
    `https://dl.rockylinux.org/pub/rocky/10/<Repo>/riscv64/os/repodata/repomd.xml` names
    the current `primary.xml.gz` (package names/versions/`Requires:`) and
    `filelists.xml.gz` (every installed file path per package) for `<Repo>` in
    `BaseOS`/`AppStream`/`CRB`. `grep -n '<name>libfoo-devel</name>'
    primary.xml` settles "is it packaged and in which repo" in seconds; the matching
    block in `filelists.xml` gives the exact `.so` name and include paths the `-devel`
    package installs, and the `<rpm:requires>` list gives the other shared libraries it
    was linked against (gotcha 368's container-format-codec check). This is a real
    dnf/EPEL fact-check, not a guess from package-name convention — no riscv64 binary
    ever runs, so it works identically on macOS/Linux/any arch host with no QEMU/binfmt
    setup at all, and settles in under a minute what would otherwise cost a full CI
    cycle to discover as a build or link failure.
    - **The `filelists.xml` files are large (100-200MB uncompressed)** — download once
      per port into a scratch directory (`.git/pw-scratch/<pkg>/`, gotcha 9), `grep -n`
      by package `name=` attribute to jump straight to its block rather than loading
      the whole file, and delete it when done; it is Rocky's own public mirror data,
      not anything project-specific worth keeping.

384. **`dnf` failing inside the image with `Curl error (60) ... self-signed certificate in
    certificate chain` is a fact about *your session's egress proxy*, not about the image —
    install the proxy CA into the container's trust store instead of recording "in-image dnf
    is impossible".** A sandbox whose outbound HTTPS goes through a TLS-intercepting proxy
    gives the host a CA bundle, but a container gets neither that bundle nor the host's
    loopback proxy, so every `dnf makecache`/`repoquery` dies on `mirrors.rockylinux.org`
    and it looks like the image cannot reach its own repos. Three things fix it together,
    and all three are needed:
    ```
    docker run --rm --network host \
      -e HTTPS_PROXY -e HTTP_PROXY -e https_proxy -e http_proxy \
      -v "$PWD/.git/pw-scratch/<pkg>:/s" "$MANYLINUX_RISCV64_IMAGE" bash -c '
      cp /s/ca-bundle.crt /etc/pki/ca-trust/source/anchors/proxy.crt
      update-ca-trust extract
      dnf repoquery --qf "%{name}|%{version}|%{reponame}\n" "qt6*"'
    ```
    `--network host` is what lets the container reach a proxy listening on the host's
    loopback; the env vars are not inherited unless named; and `update-ca-trust extract`
    (Rocky's anchors directory, *not* `/etc/ssl/certs`) is what makes curl inside `dnf`
    accept the intercepted chain. This matters because two queue entries had already
    recorded the proxy failure as an image limitation and fallen back to gotcha 369's
    raw-repodata parse — which is still the right tool for "is it packaged, in which repo",
    but cannot answer what `dnf` actually *resolves*, and cannot show you the installed
    on-disk layout (`/usr/lib64/cmake/Qt6*`, `ClangConfig.cmake`, real `.so` names) that a
    CMake `find_package` will or will not hit.
    - **Use `repoquery` for inventory and reserve `install` for layout questions.** A
      `repoquery` is metadata-only and answers in seconds even under QEMU — and it returns
      the SDK's *version*, which is the field most likely to be assumed rather than checked
      (gotcha 383). Actually installing a large `-devel` set is emulated `rpm` scriptlet
      work and can take tens of minutes on a loaded host, so do not put it on the critical
      path of a triage decision; note how far it got and move on.
    - This is the container half of the rule already stated for the host: never disable TLS
      verification or unset the proxy variables to make a fetch succeed.

394. **A project that links libtorch cannot be rehearsed on an x86_64 host with the
    `torch` wheel PyPI serves, because that one is a CUDA build: `find_package(Torch)`
    pulls in `Caffe2Config.cmake`, which hard-fails with "Your installed Caffe2 version
    uses CUDA but I cannot find the CUDA libraries" before CMake reaches a single line
    of the project's own configuration (the torchcodec case).** The failure has nothing
    to do with the project or with riscv64 — the riscv64 `torch` on our registry is a
    `+cpu` build whose `Caffe2Config.cmake` has the CUDA branch compiled out, so the same
    configure succeeds there. Two consequences worth knowing before spending a rehearsal
    cycle on it:
    - **A CPU-only torch is the prerequisite for any local rehearsal of a libtorch
      extension**, and PyPI has none for linux x86_64 (the CPU variants live on
      `download.pytorch.org/whl/cpu`, a separate index); linux aarch64's PyPI `torch`
      *is* CPU-only, which is one more reason gotcha 101's aarch64 rehearsal is the right
      host for this family of packages.
    - **Everything before `find_package(Torch)` still validates cheaply on x86**, and for
      a scikit-build-core/CMake project that is most of the interesting surface: the
      build frontend and `--no-build-isolation` wiring, `pkg-config` discovery of a
      source-built native dependency, the backend finding `pybind11`, and any
      licence-guard/env-var gate the project puts in front of a wheel build. Run it and
      read how far the configure got rather than treating the CUDA error as a dead end.

403. **Prove which build *variant* you are about to produce by stubbing the build
    backend's `setup()` on the host — it costs seconds and is the only cheap guard on
    gotcha 79's trap, where the wrong sibling compiles for hours under your artifact
    name.** For a sibling port selected by env vars plus a pre-stamped generated file
    (`ENABLE_CONTRIB`/`ENABLE_HEADLESS` + `cv2/version.py`), put a fake module in
    `sys.modules` exposing whatever `setup.py` imports, have its `setup(**kw)` record
    `kw["name"]`/`kw["version"]`/`kw["license"]`/`cmake_args` and raise `SystemExit`, then
    `runpy.run_path("setup.py", run_name="__main__")`. It is arch-independent, needs no
    toolchain, and works with `.git` already deleted — exactly the tree the container sees.
    Two habits make it worth the five lines:
    - **Assert the negative too.** Re-run with the generated file stamped `False` and the
      env vars still set: if the name does not change, the env vars are decorative and the
      stamp is the real selector — the fact the workflow's `grep -Fqx` guards. Getting plain
      `opencv_python` back from a contrib+headless environment turns gotcha 79's warning
      into something measured rather than quoted.
    - **Read the `cmake_args` list it captured** instead of re-deriving the flags from the
      `setup.py` source; a variant's flags are assembled across several conditionals and the
      captured list is the authoritative answer.

404. **For a from-source C++ world (OpenCV+contrib and friends), a *full CMake configure*
    inside the real riscv64 image is the honest local ceiling — budget ~40 minutes for it
    and report what it proved rather than that "a build" was attempted.** Under
    `qemu-riscv64` binfmt on a loaded 4-core x86_64 host, `cmake` over opencv +
    opencv_contrib reported `Configuring done (2365.7s)` / `Generating done`; the compile of
    the ~50 modules that follows is days of emulation and is not a local task. The configure
    summary carries most of what a reviewer would otherwise take on trust — the
    extra-modules path and its submodule SHA, the module list, `GUI: NONE` for a headless
    variant, the baseline `-march=rv64gc` and which SIMD kernels were dropped, and which
    third-party libraries are vendored (`build (…)`) rather than external. Two setup notes
    that each cost a restart:
    - **Mount the source tree read-write.** OpenCV's `OpenCVDownload.cmake` writes a
      `.cache/` directory *into the source dir*, so a `:ro` mount fails the configure at
      once with "Read-only file system" — which reads like a real port problem.
    - **Give the container the egress proxy.** Those same third-party fetches go to
      `raw.githubusercontent.com`: run with `--network host`, pass the host's `HTTPS_PROXY`,
      and mount the proxy CA (gotcha 384). Without it the downloads fail and the modules
      needing them quietly drop out of the summary you are reading.

410. **Gotcha 188's "lower the optimisation level for the local rehearsal only" can
    silently produce a *broken* wheel when the project has a C99 `inline` helper with no
    `static`: the extension links, ships, and passes the suite, because the package's own
    pure-Python fallback catches the ImportError (the cassandra-driver case).**
    `cassandra/cmurmur3.c` defines `inline int64_t rotl64(...)` — under C99/gnu11 that
    emits no out-of-line definition, so at `-O3` the call is inlined and at `-O0` the
    `.so` keeps an undefined `rotl64`. The rehearsal's wheel therefore contained all
    twenty `.so` files, passed gotcha 20's presence check, passed auditwheel repair, and
    ran the whole unit suite green — 618 passed — while `cassandra.murmur3`'s
    `try: from cassandra.cmurmur3 import murmur3 / except ImportError` had quietly fallen
    back to Python. The identical `-O3` wheel differed by only two tests (the two that
    skip when the C murmur3 is missing), which is far too small a delta to notice.
    - **Fix the *check*, not just the rehearsal**: presence in the zip is not proof, so
      have `CIBW_TEST_COMMAND` **import** every extension and assert `__file__` ends in
      `.so`, plus one real call per hand-written extension
      (`murmur3("key") == -6847573755651342660`, `libevwrapper.Loop()`). Then a degraded
      or unimportable build fails the job instead of passing it. `readelf --dyn-syms -W
      <ext>.so | grep UND` on the built wheel is the direct confirmation, and it works on
      a riscv64 `.so` from an x86 host.
    - **Prefer `-O1`/`-O2` over `-O0`** when trading fidelity for QEMU time, and re-run the
      import assertions against a wheel built with upstream's real `CFLAGS` before
      believing a green rehearsal.

412. **When no riscv64 image or cross-toolchain is reachable, exercise a C/C++ source's
    *generic* architecture path natively by renaming the arch macros in a scratch copy —
    `-U__x86_64__` cannot do it, because glibc's own headers key off the same macro.**
    Gotchas 9/101/180 all assume a container: `quay.io` for the manylinux images,
    `deb.debian.org`/`dl-cdn.alpinelinux.org` for a compiler inside a `--platform
    linux/riscv64` base. A restricted-egress host can have working QEMU/binfmt and still
    reach none of them, leaving no way to compile a single line for riscv64. The
    substitute question is nearly as good: *does the source's non-x86, non-aarch64 branch
    compile at all?* — which is the branch riscv64 takes, and it compiles on any host.
    The obvious spelling fails: `g++ -U__x86_64__` dies in `/usr/include/gnu/stubs.h`
    with `fatal error: gnu/stubs-32.h: No such file or directory`, because undefining the
    macro flips glibc's own multilib selection, not just the project's `#if`s. Rename the
    macros in the project's sources instead, in a copy under `.git/pw-scratch/<pkg>/`:
    ```bash
    cp -a <checkout>/csrc .git/pw-scratch/<pkg>/csrc && cd .git/pw-scratch/<pkg>/csrc
    sed -i 's/__x86_64__/__FAKE_X86__/g; s/_M_X64/FAKE_M_X64/g;
            s/__aarch64__/__FAKE_A64__/g; s/_M_ARM64/FAKE_M_ARM64/g;
            s/__i386__/__FAKE_I386__/g' *.cpp *.h
    g++ -std=c++17 -O2 -fopenmp -I. -c <each source> -o /dev/null
    ```
    The system headers keep their real macros, the project's guards all evaluate false, and
    what compiles is the scalar fallback path. For bitsandbytes this settled in seconds that
    every `immintrin.h`/`arm_neon.h` block in `csrc/cpu_ops.{cpp,h}` has a working generic
    `#else` — the one real riscv64 unknown — without a single emulated instruction.
    - **It proves compilability, not codegen or correctness**, so it substitutes for the
      *pre-flight*, never for the CI build: an arch-specific miscompile, an alignment
      assumption or a numeric divergence (gotcha 172's territory) still only shows up on the
      real runner. Pair it with the `pip download --platform manylinux_2_39_riscv64` check
      (gotcha 101) so the dependency side is settled on the host too.
    - **Check what the egress policy actually allows before giving up on the container**:
      `mirror.gcr.io` proxies Docker Hub and often survives a policy that blocks `quay.io`
      and Docker Hub's own CDN, which is enough to install binfmt
      (`docker run --privileged --rm mirror.gcr.io/tonistiigi/binfmt --install riscv64`,
      after `mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc` if the host has not
      mounted it) and to pull `mirror.gcr.io/riscv64/debian`. A riscv64 shell with no
      reachable package mirror still cannot compile anything, which is what sends you here.

417. **Rehearsing a cibuildwheel job by hand under docker+QEMU: the two things that fail
    for reasons that have nothing to do with the port (the torchcodec rehearsal).**
    Running the workflow's steps yourself inside `quay.io/pypa/manylinux_2_39_riscv64`
    (rather than through cibuildwheel) is the honest way to reproduce a riscv64 failure on
    an x86 host — it is how the `decode_avif` undefined symbol of gotcha 415 was found and
    fixed without spending a CI cycle. Two traps sit in front of it:
    - **Export `CI=1`, or scikit-build-core cannot find CMake.** Its `cmake --version`
      probe runs under a short timeout (`scikit_build_core/program_search.py`'s
      `compute_timeout`, whose base value is *quadrupled* when `CI` is set). Emulated
      riscv64 blows through the base value, and the build dies with
      `scikit_build_core.errors.CMakeNotFoundError: Could not find CMake with version
      >=3.18` — preceded by the real tell, `WARNING - Accessing CMake timed out,
      ignoring` — even though `cmake` is in the image and works fine when you run it.
      GitHub Actions sets `CI=true` for every step, so real CI never sees this and it is
      purely a rehearsal artifact. Same reasoning applies to any other tool that scales a
      timeout by `CI`.
    - **Replay `CIBW_BEFORE_ALL` in full, including anything it stages into `{project}`.**
      Skipping the licence-staging half of torchcodec's before-all made the *metadata*
      step fail with `Every pattern in "project.license-files" must match at least one
      file: 'LICENSE.*' did not match any`, because PEP 639 requires every declared
      pattern to match — a build error that exists only because the rehearsal was
      incomplete (see gotcha 105 for the patch that adds that pattern). A before-all that
      writes files into the project directory is part of the build, not setup.
    - **You can cut the rehearsal's own dependencies down as long as you keep the
      interfaces.** FFmpeg was built `--disable-everything` here: torchcodec's image
      library links no FFmpeg at all and the core libraries only need the full `libav*`
      API surface, which is exported whatever codecs are enabled. That turned a 36-minute
      FFmpeg build into a few minutes and changed nothing about the bug under
      investigation — but say so in the PR, because it does mean the *decode* tests were
      left to CI.

430. **A `-k`/`--ignore` change is verifiable offline with no wheel at all: rebuild the
    failed run's node ids into a synthetic test tree, then run the YAML-folded
    `CIBW_TEST_COMMAND` through `sh -c` (the torchcodec case).** Dropping a couple of
    hundred failing tests by name risks two silent mistakes, each costing a full CI cycle:
    a clause that misses some failures (job still red) and a substring that also matches a
    test that *passed* (coverage lost quietly, job green). Both are decidable on the host.
    Scrape `FAILED <nodeid>` out of the failed job's log, generate one throwaway module per
    test file — a class per class, and for a parametrised test
    `@pytest.mark.parametrize("p", [pytest.param(0, id="<the exact param string>")])` so
    the ids match character for character — add a handful of ids you know passed, and run
    `pytest --collect-only -q -k "<expr>"` in a plain `python:3.x-slim` container: the
    deselected count must equal the failures in scope, and every known-passing id must
    still be selected. Then close the loop on the workflow file itself rather than on your
    draft of the expression: `yaml.safe_load()` it, pull `CIBW_TEST_COMMAND` out of the
    `cibuildwheel` step's `env`, assert `cmd.count("\n") == 0` (gotcha 93's folding trap)
    and run `subprocess.run(["sh", "-c", cmd], cwd=<synthetic tree>)` — which is exactly
    how cibuildwheel invokes it, so this also catches a shell-quoting bug in the `-k`
    string. One artefact to expect: the log truncates a long parametrised id in its
    `FAILED` line, so the generated tree grows both a truncated and a full variant of the
    same test and the "passing test dropped" list fills with truncated twins — compare
    names, not counts, before believing you have collateral damage.

444. **When you hand-edit a hunk in `patches/<pkg>/<version>/*.patch`, validate it with `git
    apply --check`, not with `patch --dry-run`: if the `@@ -a,b +c,d @@` counts disagree with
    the hunk body, GNU `patch` does not fail — it consumes `b` lines, treats the remainder as
    trailing garbage, silently drops every *following* hunk in that file, writes no `.rej`,
    and exits 0.** Adding a one-line hunk to paddlepaddle's patch 1/5 with `@@ -356,4 +357,4
    @@` over a five-line body cost a full debug loop: `patch -p1 -F 0` printed only `patching
    file CMakeLists.txt`, and the *third* hunk — the whole `if(WITH_RISCV)` block — was
    simply absent from the result. `git apply` rejects the same file outright, which is also
    what the workflow's `git apply ../python-wheels/patches/...` step would have done, in CI,
    an hour into the job.
    - **Rehearse against the pristine upstream files, off-target, in seconds.** Fetch just
      the files the patch touches from `raw.githubusercontent.com/<org>/<repo>/<tag>/<path>`
      into a scratch tree, then `git apply --check --directory=<scratch> -p1 <patch>` from
      inside this repo (git resolves paths from the worktree root, so `--directory` is what
      makes a scratch subtree work). Expect one `has type 100644, expected 100755` warning
      when the source file is executable upstream and `curl` dropped the bit — that is
      cosmetic, and `--check` still exits 0.
    - **Grep the applied result for the symbol you added, do not trust the exit code.**
      `grep -n '<new option>' <file>` after a real apply is the cheap confirmation that every
      hunk landed; a count of hunks in the patch versus `grep -c '^@@' <patch>` catches the
      same class of error before you even run anything.
    - **Better still, generate hunks rather than writing them.** Gotcha 435's note on this
      port already records a hand-written hunk whose context matched byte-for-byte being
      rejected; producing the diff with `difflib` from the pristine and edited files, and
      then pasting it in, removes both failure modes at once.
    - **A *blank* context line is a line containing one space, and transcribing a diff by
      hand eats it.** Re-typing a generated diff into stpyv8's patch 0003 silently turned its
      three empty context lines into truly empty ones; `git apply` then failed with nothing
      but `error: patch failed: setup.py:236`, which reads like bad context rather than lost
      whitespace. Assemble the file mechanically instead — write the commit message and the
      `git diff` output to separate files and concatenate the *bytes* — and audit any patch
      you did edit with `awk '/^diff --git/{d=1} d && /^$/{print NR}'`, which must print
      nothing.
    - **Apply the whole directory the way the workflow does, not patch by patch.** The step
      is one `git apply patches/<pkg>/<version>/*.patch`, and a later patch's context has to
      match the tree *after* the earlier ones land, so a single-patch rehearsal can pass
      where CI fails. Rehearse with the same glob against a pristine scratch checkout, and
      note that a failed multi-patch `git apply` does not roll the earlier patches back —
      re-checkout the scratch tree before retrying or the next run fails on already-applied
      hunks and sends you chasing the wrong file.

490. **An ecbuild/CMake project that installs its generated config header into the wheel
    hands you a byte-comparable feature oracle — configure once under QEMU and diff, before
    compiling anything (the eckitlib/eccodeslib case).** ECMWF publishes a family of "binary
    wrapper" distributions (`eckitlib`, `eccodeslib`, `odclib`, `fdblib`, ...) whose wheels
    hold only the compiled C/C++ libraries; the Python bindings are a *separate* distribution
    (`eckit`, `eccodes`). Three things follow for a port.
    - **Upstream's real recipe is public even when its wheel job is not.** The release
      workflow calls `ecmwf/reusable-workflows`' `python-wrapper-wheel.yml` plus a private
      "wheelmaker" image, but the inputs it consumes sit in the source repo under
      `python/<pkg>lib/` (older layout: `python_wrapper/`): `buildconfig` carries the exact
      `CMAKE_PARAMS`, `pre-compile.sh` the extra system dependencies and licence fetches, and
      `post-build.sh` whether the wheel goes through `auditwheel repair` — eckit's does, and
      its comment records that eccodes' was replaced with a no-op. Read all three rather than
      inferring flags from the released wheel.
    - **The released wheel already carries the answer sheet.** ecbuild installs
      `include/<pkg>/<pkg>_config.h` and `<pkg>_ecbuild_config.h` into the wheel, and between
      them they record every `HAVE_*` feature, the build type, the compiler and its flags
      (`MinSizeRel`, `-Os`, GNU 14.2.1 for eckitlib 2.1.1.26). One `cmake` *configure* in the
      real `manylinux_2_39_riscv64` image with upstream's `CMAKE_PARAMS` (~4 minutes under
      QEMU — gotcha 404's cheap ceiling) produced an `eckit_config.h` byte-identical to the
      released x86_64 wheel's, `HAVE_MPI 0`/`HAVE_EIGEN 0`/`HAVE_LAPACK 0`/`HAVE_ECKIT_SQL 1`
      included. That settles "does riscv64 get upstream's feature set?" before a 630-file C++
      build, and where a flag *does* differ the header names the `find_package` that fell
      through, so the fix is usually one `dnf` package.
    - **`ENABLE_PYTHON=1` in such a buildconfig is not this wheel's extension.** It builds the
      Cython module but installs it to a `PYTHONEXT_INSTALL_DIR` aimed at the *sibling*
      distribution's source tree, so those bytes never reach the wrapper wheel and the flag can
      be dropped (keeping it also means cython in the container). The per-interpreter wheel
      list is a mirage for the same reason — cp310..cp314 differ only in tag, nothing links the
      Python C API — so build one `py3-none` wheel, as `build-eccodeslib.yml` already does.

495. **A Bazel port's loading phase rehearses on x86_64 in minutes, even in a sandbox that
    cannot fetch the dependencies.** Two checks, both arch-independent, both cheaper than the
    hours-long riscv64 cycle they replace:
    - **The project's `.bazelrc` against the bazel version you actually bootstrap.** Copy it
      into an empty workspace (`touch WORKSPACE`) and run `bazel build --nobuild` with the
      same `--config`s the upstream script passes. An old tree pinned to bazel 6 may name
      flags a newer bazel deleted, and an unknown one is a startup failure, not a warning —
      `--experimental_cc_shared_library`, `--experimental_link_static_libraries_once` and
      `--incompatible_enforce_config_setting_visibility` all still parse in 7.5.0, which is
      one reason these trees want 7.x and not 8 (which also dropped WORKSPACE `bind()`).
      With no targets bazel exits 0 on "requested an empty set of targets", so the run is
      purely a flag check.
    - **WORKSPACE evaluation on the real checkout, with the real repository overrides.**
      Everything up to the first `http_archive` fetch is host-independent: it proves the
      overrides resolve, every `load()` finds its symbols, and no repository rule shells out
      to an interpreter that isn't there (gotcha 494's failure mode lands here). Where egress
      blocks `codeload.github.com` the run dies on the first archive with a 403 — *after* that
      whole block, which is the part worth testing; read the traceback's `WORKSPACE:<line>` to
      confirm how far it got.
    - Point `--output_user_root` at `.git/pw-scratch/<pkg>/` and delete it afterwards: a
      bazel install base plus a shallow clone of a monorepo is ~700MB on a disk other agents
      share.
