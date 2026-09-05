# Gotchas — Rust, maturin & PyO3

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/rust-maturin-and-pyo3.md`.

## In this file

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
- **187** — A `bindings = "bin"` project that ships **no** wheel-level test suite at all (the
- **224** — `python -m <name>` is not a given for every `bindings = "bin"` wheel — it only
- **228** — A crate graph far smaller than gotcha 141's polars-runtime/deltalake examples can
  still SIGABRT rustc with an alloc failure on the 4-core riscv64 runners.
- **237** — A pyo3 `#[pymodule_init]` can eagerly `import` a platform-specific companion
  package, blocking `import <pkg>` itself, not just one function.

---

10. **Rust/PyO3 packages (maturin *or* setuptools-rust) — traps.** Two build
    backends show up: **maturin** (fastuuid, litellm, tiktoken, hf-xet) and
    **setuptools-rust** (bcrypt, and the whole pyca/cryptography family —
    `build-backend = setuptools.build_meta`, crate wired via
    `[[tool.setuptools-rust.ext-modules]]`). The toolchain/musl traps below apply
    to both; the abi3 mechanism differs (see gotcha 11).
    - **Floating deps in a locally-built sdist.** If upstream gitignores `Cargo.lock`
      (common for libraries), a fresh `python -m build --sdist` re-resolves crates to
      today's latest semver-compatible versions. With `#![deny(warnings)]`, a newly
      deprecated API in a bumped dep becomes a hard compile error. Fix: pin the
      offending crate to the version upstream released against *before* building the
      sdist, so maturin captures it into the bundled lock (see `build-fastuuid.yml`):
      ```bash
      cargo update -p <crate> --precise <version>
      python -m build --sdist
      ```
      Diagnose: grep CI log for `use of deprecated` / `could not compile`. If upstream
      commits `Cargo.lock` into the repo (litellm does), this trap doesn't apply —
      the lock is bundled into the sdist verbatim.
    - **Rust toolchain must be installed inside the manylinux container.** If the
      project's `pyproject.toml` has a `[tool.cibuildwheel] before-all` that does this
      (tiktoken does), it's inherited automatically. Otherwise supply it yourself:
      `CIBW_BEFORE_ALL_LINUX: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y`
      and `CIBW_ENVIRONMENT_LINUX: PATH="$PATH:$HOME/.cargo/bin"`. rustup provisions a
      native `riscv64gc-unknown-linux-gnu` toolchain in the container.
    - **musllinux can't build** — rustup.rs ships no riscv64 musl toolchain. Restrict
      `CIBW_BUILD` to `*-manylinux_riscv64` (or `CIBW_SKIP: '*-musllinux_*'`). Whether
      the matrix is per-interpreter `[cp312, cp313, cp314, cp314t]` or collapses to
      `[cpXY-abi3, cp3Nt]` depends on whether the extension is built abi3 — see
      gotcha 11, which covers both maturin and setuptools-rust.
    - **The rustc target triple is not `riscv64`.** Upstream maturin matrices usually carry
      a short `target:` field (`x86_64`, `aarch64`, `armv7`, `ppc64le`); there is no
      `riscv64` target, it is `riscv64gc-unknown-linux-gnu` (`rustup target list | grep
      riscv64`), so adding `target: riscv64` just fails. Make the matrix entries explicit
      instead — `{runner: ubuntu-24.04-riscv, target: riscv64gc-unknown-linux-gnu,
      arch: riscv64}` — and switch the upload step's artifact name to interpolate the new
      `arch` field rather than `target`.

59. **Crate features and a pinned Rust channel reach a maturin build through
    `MATURIN_PEP517_ARGS`, not through cibuildwheel (the ormsgpack case; see
    `build-ormsgpack.yml`).** Gotcha 10 covers installing rustup in the container;
    what it doesn't cover is how to hand the *build* extra maturin arguments when
    upstream's own CI passes them to `maturin build`/`maturin-action` (`args:
    --release -i pythonX.Y --features <feat>`) rather than putting them in
    `pyproject.toml`. cibuildwheel has no maturin knob, and `CIBW_CONFIG_SETTINGS`
    is the wrong lever; maturin's PEP 517 backend reads the env var itself
    (`maturin/__init__.py`: `env_args = os.getenv("MATURIN_PEP517_ARGS", "")`), so
    it just goes in `CIBW_ENVIRONMENT` beside the `PATH` entry:
    ```yaml
    CIBW_ENVIRONMENT: >-
      PATH="$PATH:$HOME/.cargo/bin"
      MATURIN_PEP517_ARGS="--features unstable-simd"
    ```
    Drop the `-i pythonX.Y` half — the PEP 517 backend already builds for the
    interpreter cibuildwheel is running.
    - **Pin the toolchain to the exact nightly upstream releases with**, when a
      feature needs one (`#![cfg_attr(feature = "…", feature(core_intrinsics))]`,
      a dep on `portable_simd`): grep upstream's workflow `env:` for
      `RUST_TOOLCHAIN` and pass it to the installer —
      `sh -s -- -y --profile minimal --default-toolchain <nightly-YYYY-MM-DD>`.
      Floating to today's nightly is gotcha 23's build-tool drift with a much
      bigger blast radius.
    - **Settle host-toolchain availability from the rust channel manifest, not
      from memory.** `curl -s https://static.rust-lang.org/dist/<date>/channel-rust-nightly.toml`
      and grep for the target: `pkg.rustc.target.<triple>` / `pkg.cargo.target.<triple>`
      present means rustup can install a *host* toolchain there.
      `riscv64gc-unknown-linux-gnu` has both; `riscv64gc-unknown-linux-musl` has
      only `pkg.rust-std` (a cross target), which is the concrete evidence behind
      gotcha 10's "musllinux can't build" — quote it in the workflow comment
      instead of asserting it.
    - **An upstream arch that drops the feature is not a precedent for dropping it
      on riscv64.** ormsgpack's armv7 job builds without `unstable-simd`, but the
      feature is architecture agnostic (`core::intrinsics::unlikely`, bytecount's
      `portable_simd` backend), so riscv64 keeps it. Settle it with a
      `cargo check --features <feat>` in the manylinux riscv64 image — 1m23s under
      QEMU on an arm64 laptop, versus a queued CI cycle.
    - **A small Rust extension is cheap enough to validate end to end under QEMU.**
      Same container: `python -m build --wheel` (2m06s at `opt-level=3`/`lto=thin`),
      `auditwheel repair`, then install into an empty cwd staged the way
      `test-sources` does and run upstream's suite (5.5s). That produced the exact
      516-passed/1-skipped count CI later reproduced on all four interpreters, so
      the PR shipped with evidence rather than hope. Contrast gotcha 48's sglang,
      where the build is hours long and this is not an option.

78. **Rust ports: `cargo metadata --filter-platform <triple>` settles which crates a target
    would actually compile — from any host, with no cross toolchain.** A big Rust dependency
    tree hides its arch limits in build scripts and `#[cfg(target_arch)]` arms, and the only
    honest way to enumerate what riscv64 pulls in is to ask cargo:
    `cargo metadata --format-version 1 --filter-platform riscv64gc-unknown-linux-gnu
    --features <what setup.py enables> --locked`, then walk `resolve.nodes` from the root.
    It resolves target-specific `[target.'cfg(...)'.dependencies]` blocks exactly as a real
    build would, needs only the manifests and the lock, and takes seconds — so it is also how
    you *verify a patch*: before/after the change, the offending crate must disappear for
    riscv64 and stay for aarch64.
    - **Two signatures mean "this crate cannot build here", and both are greppable:** a
      `panic!` in `build.rs` keyed off `CARGO_CFG_TARGET_ARCH`
      (libdatadog's `libdd-otel-thread-ctx`: *"Only x86_64 and aarch64 are currently
      supported"*), and a **two-arm `#[cfg(target_arch)]` binding with no fallback**
      (`#[cfg(target_arch = "x86_64")] let arch = ...;` / `#[cfg(target_arch = "aarch64")]
      let arch = ...;`), which leaves the name undefined everywhere else. Grep
      `target_arch` across the dependency's sources and count the arms before assuming a
      compile is worth starting.
    - **Patch the *feature*, not the dependency.** A crate reached through a git dependency
      cannot be fixed without vendoring it, but the project usually gates it behind a Cargo
      feature that `setup.py` turns on — narrowing that one condition
      (`if not SERVERLESS_BUILD and platform.machine() in CRASHTRACKER_ARCHS:`) removes the
      crate and everything under it. Check the Python side first: a project that already
      writes `try: from ._native import X ... except ImportError: is_available = False`
      is telling you the component is optional, and the patch is then one file.
    - **A dependency whose whole purpose is an ISA feature is a legitimate drop, not a
      shortcut.** libdatadog's thread-context crate exists to emit a **TLSDESC** thread-local;
      RISC-V TLSDESC needs GCC 14 *and* binutils 2.42 *and* **glibc 2.40**, while
      `manylinux_2_39_riscv64` and `ubuntu-24.04-riscv` are both on glibc 2.39 — so even a
      shim that compiled could not be resolved at load time. Say that in the patch header;
      it is the difference between `To upstream` and hand-waving.

117. **A maturin `bindings = "bin"` project ships one wheel per platform, no interpreter
    matrix, and its `py2.py3-none-<platform>` tag is real (the py-spy case; see
    `build-py-spy.yml`).** Gotchas 27 and 35 read an all-`py3-none-*` wheel set as a stop
    sign — 27 because the platform half was forced by hand over pure Python, 35 because
    the payload is a downloaded prebuilt runtime. There is a third shape, and it is an
    ordinary port: the wheel's payload is a **single executable compiled from source in
    the repo**, so there is no ABI tag because nothing is *imported*, not because nothing
    is compiled. Two reads settle it before any triage guesswork: `[tool.maturin] bindings
    = "bin"` in `pyproject.toml`, and `unzip -l <whl>` showing one file under
    `<dist>-<ver>.data/scripts/<name>` with no `.so` and no importable package. Same
    applies to setuptools' `scripts=`/`entry_points` shipping a compiled helper. What
    changes versus a normal Rust port is the *shape*, not the difficulty:
    - **Drop the interpreter matrix.** The wheel is interpreter-agnostic, so
      `python: ["cp312", …]` would build four identical artifacts. One build job, one
      artifact, one `artifact-pattern`. A matrix still belongs on the **test** job, where
      it varies which interpreter the tool is pointed *at* — mirror upstream's own
      test-wheels matrix there, narrowed to our interpreters.
    - **cibuildwheel is the wrong tool; `PyO3/maturin-action` is the right one.** Use
      `target: riscv64gc-unknown-linux-gnu` with `manylinux: '2_39'`, which the action maps
      to `quay.io/pypa/manylinux_2_39_riscv64` for a riscv64 host — its `auto` and `2_31`
      entries map to a *cross* image instead, so pass `2_39` explicitly.
      `build-polars-runtime.yml` is the in-repo precedent and shows the
      `before-script-linux: git config --global --add safe.directory "*"` that a
      bind-mounted checkout needs.
    - **Keep upstream's wheel-renaming step if it has one.** py-spy's release job runs
      `wheel.replace('py3', 'py2.py3')` over `dist/*.whl` on every platform including
      Linux, which is why PyPI shows `py2.py3-none-manylinux…`; matching it is gotcha 18's
      filename-convention rule, and it is free — `update_doc.py` reads METADATA from inside
      the wheel, so the tag never reaches the docs.
    - **`maturin build` needs no `--compatibility` argument in the manylinux image**: it
      runs its own auditwheel and tags from the glibc it finds, so the 2_39 image yields
      `manylinux_2_39_riscv64` on its own.
    - **`astral-sh/setup-uv` silently reuses the runner's *system* CPython when its version
      matches, so one matrix entry can test a different interpreter build than the rest.**
      The riscv64 runner image ships Python 3.12.3, so the `3.12` entry got Ubuntu's
      statically-linked build while `3.13`/`3.14` got python-build-standalone downloads —
      and py-spy resolved every worker thread's name on it but returned `''` for
      `MainThread`, a failure the other two entries could not show. `UV_PYTHON_PREFERENCE:
      only-managed` makes every entry use the same kind of interpreter and is *closer* to
      upstream, which provisions all of its own with setup-python; the same tree then went
      green on 3.12.14. The tell is in the log: a `Got version 3.12.3`/`/usr/lib/python3.12`
      path where the sibling jobs show a `~/.local/share/uv/python/cpython-…` one. This
      refines the Anatomy note that setup-python falls back to a host interpreter — setup-uv
      does too, just less obviously.
    - **When a local emulated test fails, get a control before believing it.** A tool that
      *inspects other processes* (a profiler, a debugger, anything reading
      `/proc/<pid>/maps` or `process_vm_readv`) cannot work under qemu-user: the target is
      really `qemu-riscv64 <program>`, so `/proc/<pid>/exe` names the emulator and the
      guest's memory layout is not the one on disk. py-spy's suite failed 3 of 4 tests in
      `manylinux_2_39_riscv64` with `Failed to find python version from target process`.
      **Run the identical suite, under the identical emulation, against upstream's own
      published wheel for an arch upstream supports** — `--platform linux/amd64` +
      `pip install <pkg>==<ver>` in `manylinux_2_28_x86_64` on this arm64 host reproduced
      the same three errors exactly. That one run converts "our riscv64 build is broken"
      into "qemu cannot host this test", costs two minutes, and is the evidence a reviewer
      needs when the port's functional testing can only happen on the real runner.
      Generalises to any port whose local QEMU rehearsal (gotcha 9) goes red.

181. **A pyo3 crate can carry `abi3` unconditionally in its own dependency declaration —
    read `[dependencies] pyo3` before reaching for `MATURIN_PEP517_ARGS` (the primp case;
    see `build-primp.yml`).** Gotcha 155 covers the maturin project whose `abi3-pyNN` is an
    opt-in Cargo *feature* that nothing enables, so the flag has to be passed per matrix
    entry. The commoner form is the inverse and needs no cibuildwheel config at all:
    `pyo3 = { version = "0.28", features = ["abi3-py310", ...] }` in the extension crate's
    `Cargo.toml`, with `[tool.maturin] features = []` and no `--features` in upstream's
    release job. Every build is then abi3 automatically, and the free-threaded build needs
    no second shape either — pyo3 disables abi3 under `Py_GIL_DISABLED`, so the same
    invocation yields `cpXY-abi3` on the GIL-ful interpreters and `cp314-cp314t` on the
    free-threaded one. Adding `MATURIN_PEP517_ARGS="--features abi3-pyNN"` would be the
    redundant divergence gotchas 28/49 warn about elsewhere.
    - **The matrix is still two entries, and the abi3 one still has to build on the floor
      the crate names** (gotcha 96): `abi3-py310` tags the wheel `cp310-abi3`, so
      `CIBW_BUILD` lists `cp310..cp314` and cibuildwheel builds once on cp310 and re-tests
      the same wheel on each newer interpreter. Name the job and artifact after the tag the
      wheel carries, not after this repo's cp312 floor (gotcha 34).
    - **Three greps settle which of the three maturin forms you are in**: `abi3` in the
      extension crate's `[dependencies] pyo3` line (unconditional — nothing to pass),
      `[features]` for an `abi3-py*` entry no default enables (gotcha 155 — pass it), and
      `[tool.maturin] features` / upstream's `maturin build --features` for what upstream
      actually does.

182. **Cross-compiling a pyo3 crate as a riscv64 pre-flight needs
    `--features pyo3/extension-module`, or it dies at the link on `-lpython3.NN`.** Gotchas
    124/156 use a cross `cargo build` on a fast host to prove every crate in a Rust tree has
    a riscv64 path before spending runner time. For a pyo3 extension the obvious invocation
    fails at the very last step — `cannot find -lpython3.10` — because *maturin* is what
    normally adds `pyo3/extension-module` (which suppresses the libpython link), and a bare
    `cargo build` does not. It reads like a missing cross sysroot and is nothing of the
    kind. Add the feature and the same command links a real riscv64 `.so`:
    ```bash
    apt-get install -y gcc-riscv64-linux-gnu cmake
    rustup target add riscv64gc-unknown-linux-gnu
    export CARGO_TARGET_RISCV64GC_UNKNOWN_LINUX_GNU_LINKER=riscv64-linux-gnu-gcc
    export CC_riscv64gc_unknown_linux_gnu=riscv64-linux-gnu-gcc \
           CXX_riscv64gc_unknown_linux_gnu=riscv64-linux-gnu-g++ \
           AR_riscv64gc_unknown_linux_gnu=riscv64-linux-gnu-ar
    export PYO3_CROSS=1 PYO3_CROSS_PYTHON_VERSION=3.10
    cargo build --release --locked --target riscv64gc-unknown-linux-gnu \
      --manifest-path <crate>/Cargo.toml --features pyo3/extension-module
    ```
    `cmake` in the image is load-bearing for any tree pulling `aws-lc-sys` (rustls' default
    provider), which cross-builds its C for riscv64 from the prebuilt
    `src/riscv64gc_unknown_linux_gnu_crypto.rs` bindings with no bindgen. primp's ~310-crate
    workspace linked in 75 s this way on an arm64 laptop — cheap enough to run before the
    gotcha-101 aarch64 rehearsal, and it is the only local check that exercises riscv64
    codegen at all.

141. **A maturin project built through PEP 517 inherits `[tool.maturin] profile` — which
    is very often `dev`, so the wheel is a *debug* build and no `.so` check catches it
    (the deltalake case; see `build-deltalake.yml`).** Gotcha 59 covers handing maturin
    extra arguments via `MATURIN_PEP517_ARGS`; the trap it doesn't cover is that you may
    have to pass one you'd never think to look for. Upstreams whose release workflow runs
    `maturin build --profile <name>` routinely leave the pyproject default at `dev` for
    local iteration, so a plain cibuildwheel/`pip wheel` run ships an unoptimised
    extension that imports, passes the whole test suite, and is worthless in production.
    `maturin pep517 build-wheel` *does* call `ensure_release_profile`, but only when **no**
    profile is set (`src/commands/pep517.rs`), and `build_options.rs` lets the pyproject
    value win only when `--profile` is absent — the CLI wins, so supply it:
    ```yaml
    CIBW_ENVIRONMENT_LINUX: >-
      PATH="$PATH:$HOME/.cargo/bin"
      MATURIN_PEP517_ARGS="--profile release --strip"
    ```
    Two reads settle whether you need this: `grep -A3 '\[tool.maturin\]' pyproject.toml`
    for the default, and upstream's release job for what they actually ship.
    - **`MATURIN_PEP517_ARGS` is an environment variable, so it applies to every *other*
      maturin sdist pip builds in that container too.** In this port cryptography,
      arro3-core and arro3-io were all built from sdist during the test phase and each one
      was invoked with the same `--profile release --strip`. A profile name that exists
      only in *your* project's `Cargo.toml` (delta-rs' `python-release`) would therefore
      break those unrelated builds with "unknown profile". Name a profile cargo defines
      everywhere (`release`) and express the tuning with `CARGO_PROFILE_RELEASE_*` env
      vars, the way `build-polars-runtime.yml` overrides LTO without renaming the profile.
    - **Decide how much of upstream's profile the riscv64 runner can afford.** delta-rs'
      `python-release` adds `lto = "fat"` + `codegen-units = 1` on top of `release`; both
      were dropped, and `--strip` recovers most of the size. For calibration, these runners
      have **4 cores**: `build-polars-runtime.yml` takes ~4.5 h at `opt-level = 1` with
      `CARGO_BUILD_JOBS=2`, and deltalake's ~840-package graph took **8.1 h** at
      `opt-level = 3` with the same job cap plus 10 GB of swap.
    - **Validate the argument string without compiling anything**: the metadata hook parses
      it identically, so from the package dir
      `MATURIN_PEP517_ARGS="…" python -c "import maturin; maturin.prepare_metadata_for_build_wheel('out')"`
      prints the exact `maturin pep517 build-wheel …` command line and fails fast on a bad
      flag — seconds instead of an eight-hour cycle.

147. **A Rust crate that downloads a prebuilt native library almost always has an
    env-var escape to a locally built one — read its build script's variable table before
    calling the port infeasible (the `ort` case).** `ort`/`ort-sys` (ONNX Runtime bindings,
    used by magika and a growing number of ML CLIs) enables `download-binaries` by default,
    and `build/download/dist.txt` lists only `x86_64-unknown-linux-gnu`,
    `aarch64-unknown-linux-gnu` and the Apple/Windows/Android targets — zero riscv64, which
    reads like gotcha 41's vendor-blob dead end. It is not: `build/vars.rs` declares
    `SYSTEM_LIB_PATH: &["ORT_LIB_PATH", "ORT_LIB_LOCATION"]`, checked ahead of the download,
    so pointing it at a from-source build is the whole fix. Note that turning the feature
    off is *not* an alternative: `--no-default-features` applies to the crate you name, and
    a dependency's default features are declared in the dependent's `Cargo.toml`, so
    disabling them needs a manifest patch — reach for the env var instead.
    - **Upstream has usually solved this already for their own manylinux wheels**, because
      the prebuilt binaries' glibc floor is too new for their oldest supported image.
      magika ships `rust/onnx/build.sh` (clone ONNX Runtime, build it static, append
      `[env] ORT_LIB_PATH` to the repo's `.cargo/config.toml`) and wires it in as
      maturin-action's `before-script-linux`. The port is then re-running that script in
      the riscv64 image — and any knob it already exposes (`ONNX_RUNTIME_BUILD_FLAGS`) is
      the right place for arch-specific flags rather than a patch. `--skip_tests` alone is
      worth hours: the wheel needs the dependency's libraries, never its gtest suite.
    - **Split what upstream bundles into one before-script.** Such a script often also runs
      the project's own `cargo fmt --check` / `clippy --deny=warnings` (magika's
      `rust/cli/test.sh`). Leave that out of a multi-hour riscv64 build — it is gotcha 23's
      floating-build-tool risk aimed at the most expensive job you have — and exercise the
      built wheel in the test job instead.

155. **maturin abi3 can be an opt-in Cargo *feature*, so a plain PEP 517 build silently
    ships per-interpreter wheels where upstream ships one abi3 wheel (the arro3-core case;
    see `build-arro3-core.yml`).** Gotcha 11 splits abi3 into "maturin: a pyproject/Cargo
    feature, set once and inherited" versus "setuptools-rust: a flag you must inject". The
    maturin half has a third form that behaves like the setuptools-rust one: the crate
    declares `[features] abi3-py311 = ["pyo3/abi3-py311"]` and **nothing turns it on** —
    `[tool.maturin] features` lists only `pyo3/extension-module`, and upstream's release
    job passes `--features abi3-py311` on the `maturin build` command line. cibuildwheel
    inherits none of that, so the wheels come out `cpXY-cpXY` while PyPI's are
    `cp311-abi3`: four builds of the same code under tags upstream never publishes.
    - **Two greps settle it before you write the matrix**: `[features]` in the crate's
      `Cargo.toml` (an `abi3-py*` entry that no default enables) and the `--features` list
      in upstream's wheel job. `[tool.maturin] features` is *not* the whole story — read
      the CLI args too.
    - **Hand it over with gotcha 59's `MATURIN_PEP517_ARGS`**, per matrix entry, since the
      free-threaded build must *not* get it (pyo3 disables abi3 under `Py_GIL_DISABLED`):
      ```yaml
      matrix:
        include:
          - tag: cp311-abi3
            build: cp311-manylinux_riscv64 cp312-manylinux_riscv64 cp313-manylinux_riscv64 cp314-manylinux_riscv64
            features: --features abi3-py311 --features extension-module
          - tag: cp314t
            build: cp314t-manylinux_riscv64
            features: --features extension-module
      ...
          CIBW_ENVIRONMENT_LINUX: >-
            PATH="$PATH:$HOME/.cargo/bin"
            MATURIN_PEP517_ARGS="${{ matrix.features }}"
      ```
      Restate the project's own `[tool.maturin] features` on the CLI (here the crate's
      `extension-module`, which is `["pyo3/extension-module"]`) exactly as upstream does —
      a CLI `--features` may replace rather than extend the pyproject list, and losing
      `extension-module` links libpython into the wheel.
    - **The build interpreter is gotcha 96's question, and the answer is upstream's, not
      ours.** The tag comes from the abi3 floor the feature names (`cp311-abi3`), so the
      wheel must be built on cp311 even though this repo's floor is cp312 — `CIBW_BUILD`
      with the whole `cp311..cp314` list lets cibuildwheel build once and re-test the same
      wheel on each newer interpreter (`Found previously built wheel ... Skipping build
      step`). `only:` cannot express that; it takes a single identifier.
    - **The negative case is free evidence**: the free-threaded entry, built with no abi3
      feature from the identical tree, comes out `cp314-cp314t` — which is what every
      entry would have looked like had the feature not been passed.

179. **A pinned *git* dependency that does not build on riscv64: redirect it with a cargo
    `[patch]` and keep `--locked` (the pyroscope-io/py-spy case; see
    `build-pyroscope-io.yml`).** Gotcha 78 says a crate reached through a git dependency
    cannot be fixed without vendoring it, and points at narrowing the Cargo feature that
    pulls it in. When the crate is a core dependency with no feature gate — py-spy, whose
    `pyruntime::get_tstate_current_offset` has one definition per architecture and none
    matching riscv64, so the build dies with `error[E0425]: cannot find function
    'get_tstate_current_offset' in module 'pyruntime'` — there is a third way that is
    neither vendoring the whole tree nor forking: clone the pinned revision beside the
    project, patch it, and add to the root manifest
    ```toml
    [patch."https://github.com/<owner>/<crate>"]
    <crate> = { path = "../<crate>" }
    ```
    **The entire `Cargo.lock` delta is the one `source = "git+..."` line**, so every other
    dependency stays pinned exactly as upstream released it and a `--locked` build
    (setuptools-rust's `cargo_manifest_args=["--locked"]`, maturin's `--locked`) keeps
    working once that line is in the patch too. Generate the delta rather than writing it:
    apply the `[patch]`, run `cargo metadata`, `git diff Cargo.lock`.
    - **Clone on the host, not from `before-all`** — cibuildwheel copies the whole cwd into
      the container (gotcha 142), so a sibling directory created by a `run:` step is present
      when cargo resolves, and `git apply` can reach the patch file from this repo's second
      checkout.
    - **Settle the arch question for the whole dependency tree before writing any YAML**,
      with `cargo check --target riscv64gc-unknown-linux-gnu` in a `rust:trixie` container —
      no cross linker needed, `check` does not link. Two environment facts get a real tree
      past its first build script: `dpkg --add-architecture riscv64 && apt-get install
      libssl-dev:riscv64 gcc-riscv64-linux-gnu` satisfies **openssl-sys**, whose build script
      shells out to `<triple>-gcc` to expand headers (`failed to find tool
      "riscv64-linux-gnu-gcc"` otherwise), and `PYO3_CROSS_PYTHON_VERSION=3.12` satisfies
      **pyo3**, which otherwise stops with `PYO3_CROSS_PYTHON_VERSION or either an
      abi3-py3* or abi3t-py3* feature must be specified when cross-compiling`. 230 crates
      type-checked in 12 seconds that way, which is what turned "py-spy may need porting"
      into a one-line change.

187. **A `bindings = "bin"` project that ships no wheel-level test suite at all (the prek
    case; see `build-prek.yml`): exercise the tool's own self-contained functionality
    instead of settling for a bare `--version` check.** py-spy at least has
    `tests/integration_test.py` to mirror (gotcha 117). Some CLI ports have nothing —
    prek's `crates/prek/tests/*.rs` are Rust integration tests run by upstream's own
    `cargo nextest`, never packaged into the wheel — so "same as upstream" is not an
    option and `prek --version` alone would prove only that the binary starts. The fix is
    to find the tool's own no-dependency demo path and drive it for real: prek's
    `sample-config` subcommand writes a config whose hooks are all **builtin** (Rust code
    compiled into the binary, not cloned from a hooks repo), so `prek run --all-files`
    against it in a scratch git repo is a genuine end-to-end exercise — config parsing,
    hook dispatch, file mutation — with no network dependency to flake on a shared runner.
    Assert on behaviour, not just exit code: write a file with the defect each builtin
    hook fixes (trailing whitespace, missing final newline), run once expecting the
    pre-commit convention of "exit 1, files modified", `git diff --stat` to prove the
    fix actually happened, then run again expecting a clean pass. A step that only checks
    `--version` would go equally green whether the hook engine works or is entirely
    broken.

224. **`python -m <name>` is not a given for every `bindings = "bin"` wheel — it only
    works when *upstream's own source tree* ships a hand-written `<name>/__init__.py` +
    `__main__.py` shim; verify by inspecting the built wheel, not by copying the test
    step from another `bin` port (the zizmor case).** Gotcha 117 identifies a `bindings =
    "bin"` wheel by "one file under `<dist>-<ver>.data/scripts/<name>` with no `.so` and
    no importable package" — but that description covers two different shapes. prek and
    pyrefly both carry an extra `<name>/` Python package in their own repos solely to make
    `python -m <name>` work (`unzip -l` on their wheels shows `prek/__init__.py`,
    `prek/__main__.py`, `prek/_find_prek.py`; `pyrefly/__init__.py`, `__main__.py`,
    `py.typed`), so a workflow copied from either one that includes `python -m <name>
    --version` in the test step happens to pass. zizmor's `pyproject.toml` declares no
    `python-source` and its repo has no such package, so its wheel is the *bare* shape —
    `unzip -l` shows only `zizmor-<ver>.data/scripts/zizmor` plus `.dist-info/` — and
    `python -m zizmor --version` fails every interpreter with `No module named zizmor`,
    even though `zizmor --version` (the installed console script) works fine. This is a
    same-day repeat of gotcha 223's point from the opposite angle: don't guess the
    behaviour of the *actual artifact* your workflow builds, download the already-built
    wheel from your own PR's `build_wheel` job (`gh run download <run-id> -n
    <pkg>-<ver>-manylinux_riscv64`) and `unzip -l` it before deciding what the test step
    can assert — cheaper than finding out from four failed matrix legs.

228. **A crate graph far smaller than gotcha 141's polars-runtime/deltalake examples can
    still SIGABRT rustc with an alloc failure on the 4-core riscv64 runners, and only one
    matrix leg needs to fail (the tach case).** tach's Cargo.toml pulls in ruff's own
    `ruff_linter`/`ruff_python_parser`/etc as git dependencies — not a huge graph by that
    gotcha's standard, and well inside its 360-minute default timeout — but the
    `cp37-abi3` and `cp314t` matrix legs compile that same graph **concurrently** on
    (evidently) shared/limited memory, and one leg died mid-`ruff_linter` with `rustc
    ... (signal: 6, SIGABRT: process abort signal)` while its sibling, compiling the
    identical dependency tree, finished clean. Rust's default allocator aborts (not
    `SIGKILL`) on allocation failure, so a SIGABRT during codegen on a modest crate graph
    is still worth reading as OOM first, especially when a sibling matrix job building
    the same code succeeded. Fix tried first, before touching `opt-level` or profile
    (which gotcha 141 already covers for the harder cases): add `CARGO_BUILD_JOBS=2` to
    `CIBW_ENVIRONMENT_LINUX`, which halves concurrent rustc processes and their peak
    memory without changing the produced binary's optimization level. The retry (same
    commit, same matrix, `CARGO_BUILD_JOBS=2` added) built and tested both legs clean, at
    roughly the same wall-clock cost as the failed attempt — cheap enough to reach for
    on any multi-leg riscv64 matrix that compiles a nontrivial dependency tree per leg,
    not just the graphs already known to be enormous.

237. **A pyo3 `#[pymodule_init]` can eagerly `import` a platform-specific companion
    package, which blocks `import <pkg>` itself — not just one function — and gotcha 122's
    `PIP_NO_DEPS` only fixes the install, not this (the mitmproxy-rs case).** mitmproxy-rs
    depends on `mitmproxy_linux` on Linux (no riscv64 wheel), but the failure isn't limited
    to `Requires-Dist` resolution: `lib.rs`'s `#[pymodule_init]` runs `m.py().import
    ("mitmproxy_linux")?` unconditionally on Linux "so that missing dependencies are
    raising immediately," so even a `PIP_NO_DEPS=1` install of the wheel dies at `import
    mitmproxy_rs` with `ModuleNotFoundError: No module named 'mitmproxy_linux'` — no test
    ever gets to run. Read the actual function that needs the companion package before
    concluding the whole port needs a source patch: `start_local_redirector()` re-imports
    `mitmproxy_linux` itself at call time and raises the identical error, so the eager
    module-init check is a fail-fast convenience, not the only place the dependency is
    enforced. The crate already shipped the escape hatch as an opt-in Cargo feature
    (`docs = []`, gating the init-time import with `not(feature = "docs")` — clearly built
    for doc generation without the platform binaries) that needed no patch, just restating
    it alongside upstream's own `[tool.maturin] features` on the CLI (gotcha 155's rule):
    `MATURIN_PEP517_ARGS="--features pyo3/extension-module,docs"`. Every other exported
    function keeps working; only the one function that genuinely needs the missing
    companion package still fails, now at call time instead of at import.
    - **Two greps settle whether this pattern applies**: `#[pymodule_init]` (or
      `#[pyo3(init)]`/`fn init` in the pymodule macro) for an eager `py.import(...)`, and a
      second call site for the same import inside the function that actually uses it — the
      second one is the tell that the eager check is redundant with a real one, not the
      only enforcement point.
    - **Validate the fix outside the riscv64 queue** (gotcha 101): the aarch64 rehearsal
      reproduced `ModuleNotFoundError` on the first run with only `PIP_NO_DEPS` applied,
      and a second run with `--features docs` added went green with all 9 smoke tests
      passing — settled in minutes on a native aarch64 container rather than a riscv64
      cycle.
