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
- **238** — A repo-root `rust-toolchain.toml` pinning nightly for lint-only use can still
  hijack a riscv64 build built from the git checkout, not the sdist.
- **239** — A maturin project inside a Cargo workspace can have its `pyproject.toml` at a
  different path in the git checkout than in the PyPI sdist.
- **259** — A maturin `bindings = "bin"` project can declare two `[[bin]]` targets where
- **260** — `puccinialin` (and similar rust-bootstrap-on-demand helpers) has no riscv64 entry
- **371** — pyo3 0.22's version ceiling (gotcha 306) is a hard ceiling for a non-abi3,
  per-interpreter build too, one minor above its own release-time latest — the
  `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` escape hatch works without turning abi3 on.
  the second execs the first over `$PATH`, not a sibling path.
- **266** — A vendored-C build script's own "require SIMD" default feature can turn
  upstream's documented non-SIMD fallback into a fatal error on any arch the vendored
  code has no kernels for.
- **287** — A repo-root `.cargo/config.toml` can unconditionally point `PYO3_CONFIG_FILE`
  at a file only a task-runner's activation hook generates, breaking every cargo
  invocation outside that task runner.
- **300** — A crates.io dependency with no riscv64-compatible release can be patched via
  `[patch.crates-io]` at a vendored, fixed copy — but a git checkout of its monorepo
  nested inside the referencing workspace's own directory tree confuses cargo's
  workspace-boundary detection; the crate's own crates.io tarball (already flattened,
  no `[workspace]`) sidesteps it.
- **364** — Patching a workspace `Cargo.toml`'s placeholder version stales `Cargo.lock`'s
  local-package entries, breaking `PyO3/maturin-action`'s `--locked`.
- **365** — A heavy `bindings = "bin"` dependency tree can stall for hours on the riscv64
  runner past the default timeout, with a retry alone finishing in under an hour.
- **306** — A pyo3 release that predates a newer CPython by years does not necessarily
  fail to build against it — `pyo3-build-config` only floors the supported version, it
  has no ceiling.
- **312** — A maturin `bindings = "bin"` project's published sdist can carry a
  `pyproject.toml` that exists nowhere in the git checkout at all, not even in a
  subdirectory — building the tag directly silently ships the wheel under the Cargo
  crate's name instead of the real distribution name.
- **314** — A maturin library project with no `python-source` and no `<name>/` directory
  in the git checkout can still ship an auto-generated `<name>/__init__.py` shim around a
  `<name>.<name>` compiled submodule.
- **322** — A pyo3 release old enough to hand-roll CPython's legacy `PyUnicode_KIND`/
  `PyUnicode_DATA` macros as raw struct-offset reads can compile clean against a newer
  CPython and still segfault the first time a string crosses the FFI boundary.
- **325** — A maturin `[tool.maturin] include` list is scoped to the wheel, not the sdist,
  so omitting `tests/` there ships a tests-less sdist even though every port needs one.
- **344** — `PyO3/maturin-action` reads the target crate's own `pyproject.toml`
  `[build-system] requires` for its maturin version unless `maturin-version:` overrides it —
  a stale pin (`maturin==0.14.17`, never actually exercised by upstream's own release job,
  which calls the action directly) predates riscv64 release assets and 404s.
- **345** — Inside a driven-yourself `before-script-linux`, `PyO3/maturin-action`'s own
  hardcoded `PATH` addition for manylinux's per-interpreter console-scripts stops at cp312 —
  a `pip`-installed plugin (e.g. `protoc-gen-mypy`) for cp313+ is invisible to a PATH-based
  `which`/`shutil.which()` lookup even from that same interpreter; resolve its scripts
  directory via `sysconfig.get_path("scripts")` instead.

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

238. **A repo-root `rust-toolchain.toml` pinning nightly for lint-only use can still
    hijack a riscv64 build built from the git checkout, not the sdist (the
    pyiceberg-core/iceberg-rust case).** rustup resolves the active toolchain by walking
    up from cwd for a `rust-toolchain(.toml)` file, and that lookup outranks whatever a
    plain `rustup-init.sh -y` installed as the default. iceberg-rust's own file pins
    `channel = "nightly-2026-03-05"` for `clippy`/`rustfmt`, with a comment that this
    "will not affect downstream users" — true for anyone who `pip install`s from the
    PyPI sdist, which genuinely excludes the file (verified: absent from the extracted
    tarball). It is not true for a riscv64 port: checking out the git tag is required
    anyway to reach the workspace's sibling crates (gotcha 239 covers why the checkout's
    layout also isn't a drop-in for the sdist's), and that checkout puts
    `rust-toolchain.toml` right at the root maturin's `cargo build` inherits from. The
    result is cargo trying to provision a **nightly** riscv64 host
    toolchain for whatever date is pinned, which may take much longer than a stable
    install or may not exist as a riscv64 host build at all (gotcha 59's channel-manifest
    check settles which). Fix: `RUSTUP_TOOLCHAIN=stable` in `CIBW_ENVIRONMENT_LINUX` — the
    env var outranks the toolchain file in rustup's resolution order, so it forces the
    already-installed stable toolchain (satisfying MSRV) without touching the file.
    Upstream's own release job dodges the same file more elaborately, with a
    `setup-builder` composite action that runs `rustup toolchain install <msrv> && rustup
    override set <msrv>` before ever invoking maturin — same fix, expressed as an
    override instead of an env var.
    - **Two greps settle whether a project needs this**: `cat rust-toolchain.toml` (or a
      `[toolchain]` table in a bare `rust-toolchain`) for a pinned channel, and whether
      that channel is `nightly-*` — a pinned `stable` or an MSRV-matching channel is
      harmless to inherit as-is.
    - **Diagnose it from the log**: `info: syncing channel updates for
      nightly-<date>-riscv64gc-unknown-linux-gnu` appearing right after `maturin pep517
      build-wheel` starts (not from the `before_all` rustup-install step, which correctly
      reports installing `stable`) is the tell — the toolchain file overrode the install
      the moment cargo ran inside the checkout.

239. **A maturin project inside a Cargo workspace can have its `pyproject.toml` at a
    different path in the git checkout than in the PyPI sdist — inspecting the sdist to
    plan `package-dir` gives the wrong answer (the pyiceberg-core/iceberg-rust case).**
    `maturin sdist` for a workspace member hoists that member's `pyproject.toml` to the
    **sdist root** and synthesizes a `manifest-path` (pointing back at the crate's
    `Cargo.toml`) plus a `python-source` that wasn't in the original file, so a locally
    built or downloaded sdist's `pyproject.toml` sits beside `Cargo.lock`/`Cargo.toml`
    at the top level. The real git repository has no such file at its root: iceberg-rust's
    `pyproject.toml` lives at `bindings/python/pyproject.toml`, beside the crate's own
    `Cargo.toml`, with no `manifest-path` key at all (maturin defaults to the `Cargo.toml`
    next to `pyproject.toml` when one isn't given) and a `python-source = "python"` that
    resolves relative to that subdirectory, not the workspace root. Building an sdist
    (`pip download --no-binary`, or `uv build --wheel` against it) to inspect the layout —
    gotcha 2's normal move — plans a `package-dir: .` that then fails in CI with
    `Could not find any of {setup.py, setup.cfg, pyproject.toml} at root of package`
    against the real checkout, because the workflow checks out the git tag (needed for
    the workspace's sibling crates), not the sdist.
    - **Two greps settle which shape applies before writing `package-dir`**: `find . -iname
      pyproject.toml -maxdepth 3` on a fresh git clone of the tag (not the sdist) to see
      where it actually lives, and `grep manifest-path` in that file — present means the
      sdist's synthesized version, absent alongside a `python-source` means the checkout's
      original, subdirectory-relative one.
    - **`CIBW_TEST_SOURCES` still resolves against the checkout root** (gotcha 104), not
      `package-dir`, so staging `bindings/python/tests` and `bindings/python/pyproject.toml`
      (for `[tool.pytest.ini_options]`) is unaffected by which `package-dir` is correct —
      only the cibuildwheel `package-dir` value and the `cd bindings/python` a
      `CIBW_TEST_COMMAND` needs before running pytest depend on it.

259. **A maturin `bindings = "bin"` project can declare two `[[bin]]` targets where the
    second execs the first over `$PATH`, not a sibling path — testing it standalone gives
    a misleading `No such file or directory` (the ast-grep-cli case).** ast-grep-cli's
    `crates/cli/Cargo.toml` builds both `ast-grep` and `sg`; maturin packages both into
    `<dist>.data/scripts/`, same as gotcha 117 describes for one binary. But `sg`
    (`crates/cli/src/bin/alias.rs`) is a thin Unix launcher: its `main()` prints a
    deprecation notice, then `Command::new("ast-grep").spawn()`s — resolved through the
    process's `$PATH`, never through `std::env::current_exe()`'s own directory. Running
    the extracted binary directly (`target/release/sg --version`, or unzipping the wheel
    and invoking the script in isolation) fails with a plain `No such file or directory`
    that reads like a broken build, not a test-ordering issue. It works as soon as both
    console scripts are installed together (`pip install`/`uv pip install` put them in the
    same venv `bin` dir, already on `PATH`), so write the CI test step against the
    installed wheel, never against a bare extracted binary. `grep -n 'Command::new'
    crates/cli/src/bin/*.rs` confirms the relationship before assuming a second `[[bin]]`
    is a second self-contained executable.
    - **Also settles which maturin invocation shape a project needs.** ast-grep-cli's
      `pyproject.toml` lives at the workspace **root** with `[tool.maturin] manifest-path =
      "crates/cli/Cargo.toml"`, so `maturin build` from the checkout root needs no
      `--manifest-path` argument — maturin reads it from the pyproject table. Contrast
      zizmor (gotcha 117's precedent), whose `pyproject.toml` is colocated with the crate
      under `crates/zizmor/`, so the *workflow* passes `--manifest-path
      crates/zizmor/Cargo.toml` explicitly. `grep -A3 '\[tool.maturin\]' pyproject.toml`
      settles which shape a new port is in before copying either workflow verbatim.

260. **`puccinialin` (and similar rust-bootstrap-on-demand helpers) has no riscv64 entry
    in its own target list, but it never runs at all once `cargo` is already on `PATH`
    (the biotite case).** biotite's `setup.py` (`setuptools-rust`, not maturin) only calls
    `cargo` directly when it finds one: `if not shutil.which("cargo"): setup_rust()`, where
    `setup_rust()` comes from the `puccinialin` build-system dependency and downloads a
    matching rustup-style toolchain when none is installed. `puccinialin`'s target-triple
    detection (`_target.py`) hardcodes a `rustup_targets` allowlist copied from
    rustup.rs's install docs, and it has no `riscv64gc-unknown-linux-gnu` entry — calling
    `setup_rust()` on riscv64 prints "Target triple not supported by rustup" and
    `sys.exit(1)`. The fix is the same one-liner every other setuptools-rust/maturin port
    already needs (gotcha 10): install rustup yourself in `CIBW_BEFORE_ALL_LINUX` and put
    `$HOME/.cargo/bin` on `PATH` via `CIBW_ENVIRONMENT` — `shutil.which("cargo")` then
    finds it, the whole `puccinialin` branch is skipped, and its missing riscv64 target
    never matters. No patch needed.
    - **Read the helper's source, not just its name, before assuming it blocks the port.**
      `pip download puccinialin --no-deps` (it is pure-Python, `py3-none-any`) and grepping
      `_target.py` for `rustup_targets` is a 30-second check against guessing from the
      "Target triple not supported" message alone, which names the *symptom* (a rustup
      target) rather than the *cause* (a helper's allowlist, not rustup itself — rustup.rs
      has shipped `riscv64gc-unknown-linux-gnu` as a Tier 2 target for years).
    - **This is a build-system dependency, not a runtime one** — it is resolved into pip's
      isolated build environment regardless of whether `setup_rust()` ever executes, so it
      needs no registry entry and no `CIBW_ENVIRONMENT` mention of its own.

266. **A vendored-C build script's own "require SIMD" default feature can turn upstream's
    documented non-SIMD fallback into a fatal error on any arch the vendored code has no
    kernels for — read the actual CMake/build option before assuming the crate is
    unbuildable (the kornia-rs case; see `build-kornia-rs.yml`).** kornia-py's default
    `turbojpeg` feature pulls in `turbojpeg-sys`, which vendors libjpeg-turbo and builds it
    with cmake; `turbojpeg-sys`'s own default features include `require-simd`, which passes
    `-DREQUIRE_SIMD=ON`. libjpeg-turbo's `simd/CMakeLists.txt` only ships SIMD kernels for
    x86/x86-64, Arm, MIPS and PowerPC — every other `CPU_TYPE` (riscv64 included) falls
    through to a `simd_fail()` macro that is a hard `message(FATAL_ERROR ...)` when
    `REQUIRE_SIMD` is on. The `option(REQUIRE_SIMD ...)` line's own help text says the
    *default* (off) is "to fall back to a non-SIMD build" with just a warning, so this is
    not a missing riscv64 port in libjpeg-turbo, just a Rust crate's default feature
    forcing a stricter mode than the C project itself defaults to. Fix: drop the dependent
    crate's default features and re-list the ones still wanted, in the workspace member
    that actually declares the dependency (`kornia-io`'s `Cargo.toml`, not `kornia-py`'s,
    which only re-exports the feature by name):
    ```toml
    turbojpeg = { version = "1.2", optional = true, default-features = false, features = ["cmake", "pkg-config"] }
    ```
    - **Two reads settle it before assuming a hand-rolled patch to the vendored C is
      needed**: the Rust wrapper crate's `[features] default = [...]` list (does it turn on
      a `require-*`/`strict-*` feature that isn't load-bearing for the functionality this
      port needs?), and the vendored build's own option help text (does it name a graceful
      fallback that the wrapper's default simply forecloses?). Both were a `pip download
      --no-binary` and a `grep -n option\(` away, no riscv64 CI cycle spent.
    - **The change is a no-op on every already-supported target.** x86/x86-64/Arm/PowerPC
      all have real SIMD kernels bundled, so `simd_fail()` is never reached there regardless
      of `REQUIRE_SIMD` — the patch only changes behaviour on architectures that would have
      hit the fatal branch anyway, which is also the argument for tagging it `To upstream`
      rather than `Inappropriate`: it is a genuine portability fix, not a riscv64-only hack,
      simply not filed upstream because this port's session policy is to not open external
      issues/PRs.

287. **A repo-root `.cargo/config.toml` can unconditionally point `PYO3_CONFIG_FILE` at a
    file only a task-runner's activation hook generates, breaking every cargo invocation
    outside that task runner (the rerun-sdk case; see `build-rerun-sdk.yml`).** rerun's
    `[env] PYO3_CONFIG_FILE = { value = "rerun_py/pyo3-build.cfg", relative = true }`
    applies to *every* cargo build cargo config picks up from that checkout — not just
    `pixi run py-build` — because `.cargo/config.toml` env entries have no conditional
    scoping. The repo's own pixi tasks generate that file as a side effect of environment
    activation (`ensure-pyo3-build-cfg`), so a plain `maturin build`/cibuildwheel run that
    never invokes pixi hits `pyo3-build-config`'s build script erroring with `failed to
    open PyO3 config file ... No such file or directory` before a single dependency
    compiles. The fix is not to unset the env var (pyo3-build-config trusts it completely
    once set, and rerun's own `build.rs` even *requires* it be set in a wheel build to
    avoid a different isolated-build-environment check) but to write the file by hand:
    upstream ships the generator as an installable package in the checkout
    (`rerun_pixi_env/src/rerun_pixi_env/pyo3_config.py`), callable with no extra
    dependencies (`sys`, `sysconfig`, `struct`, `pathlib` only):
    ```yaml
    CIBW_BEFORE_BUILD_LINUX: |
      python -c "
      import sys; sys.path.insert(0, 'rerun_pixi_env/src')
      from pathlib import Path
      from rerun_pixi_env.pyo3_config import generate_config_file
      generate_config_file(Path('rerun_py/pyo3-build.cfg'))"
    ```
    - **Two greps settle whether a project needs this**: `grep -n PYO3_CONFIG_FILE
      .cargo/config.toml` for an unconditional `[env]` entry, and whether the path it
      names exists fresh from a plain git checkout (it won't, since task-runner-generated
      files are gitignored).
    - **The generated file's exact values rarely matter for an abi3 extension-module
      build.** rerun's generator hardcodes `version` to the crate's abi3 floor regardless
      of which interpreter runs it, and pyo3/extension-module builds link nothing against
      libpython on Unix, so `executable`/`lib_dir` being stale (pointing at whichever
      interpreter's `CIBW_BEFORE_BUILD` happened to run) does not break the build. Do not
      over-invest in matching the exact interpreter per matrix leg before confirming the
      build actually needs it.
    - **This is a different failure from gotcha 238's `rust-toolchain.toml` hijack** even
      though both are repo-committed cargo-adjacent config files silently overriding a
      port's environment — that one picks a toolchain, this one aborts the build outright
      with a missing-file error, and the fix is authoring the missing file, not overriding
      an env var.

300. **A crates.io dependency with no riscv64-compatible release can be patched via
    `[patch.crates-io]` at a vendored, fixed copy — but a git checkout of its monorepo
    nested inside the referencing workspace's own directory tree confuses cargo's
    workspace-boundary detection; the crate's own crates.io tarball (already flattened, no
    `[workspace]`) sidesteps it (the rerun-sdk/lance-core case; see
    `build-rerun-sdk.yml`).** `lance-core` 9.0.0's SIMD-tier-detection closure has
    `#[cfg(target_arch = "...")]` arms for aarch64/x86_64/loongarch64 with no catch-all
    (gotcha 78's second signature), so it evaluates to `()` instead of the declared return
    type on riscv64 — `error[E0308]: mismatched types`. No later 9.0.x release fixes it
    (checked 9.0.1), and forking the crate publicly is off the table (this session's
    policy against opening external repos), so the fix is a `[patch.crates-io]` pointing
    at a locally vendored, riscv64-fixed copy, materialized by the workflow itself
    (gotcha 179's pattern, extended from git dependencies to registry ones):
    ```yaml
    - run: |
        curl -fsSL -o lance-core.tar.gz https://crates.io/api/v1/crates/lance-core/9.0.0/download
        mkdir lance-core-9.0.0-riscv64
        tar xzf lance-core.tar.gz -C lance-core-9.0.0-riscv64 --strip-components=1
        patch -p1 -d lance-core-9.0.0-riscv64 < python-wheels/patches/<pkg>/<version>/0001-....patch
        git apply python-wheels/patches/<pkg>/<version>/0002-cargo-patch-....patch  # adds [patch.crates-io]
    ```
    - **The first attempt vendored the crate from its real git monorepo instead
      (`git clone lancedb/lance`, sparse-checkout the one member crate) and hit a wall
      gotcha 179 doesn't warn about**: `cargo metadata --locked` from the *referencing*
      workspace's root failed with `error inheriting 'keywords' from workspace root
      manifest's 'workspace.package.keywords'` / `'workspace.package.keywords' was not
      defined` — even though the vendored crate's own monorepo root plainly defines
      `keywords` in `[workspace.package]`, and running `cargo metadata` *directly inside*
      that vendored checkout resolves it correctly. The vendored monorepo's `[workspace]`
      is a real one (its own `members` list includes the crate), but placing it as a
      subdirectory *inside* the outer (referencing) workspace's own directory tree makes
      cargo attribute the inner package's workspace-inherited fields to the **outer**
      workspace's `[workspace.package]` instead of the inner one's — cargo does not
      genuinely nest workspaces, and a `[workspace]` table found only by directory descent
      from a `[patch]` path is not treated as authoritative the way it is for a direct
      invocation. This reproduced identically across two cargo versions (1.96.0, 1.97.0),
      so it is not a version-specific bug to wait out.
    - **The fix is to avoid the nested `[workspace]` entirely, not to route around it.**
      A crate's crates.io-published `Cargo.toml` is not the same file as the one in its
      git repo: `cargo package`/`cargo publish` "normalizes" it, rewriting every
      `field.workspace = true` (both `[package]` fields and every dependency) to a literal
      value and every intra-monorepo path dependency to a pinned registry version (the
      tarball's own header comment says as much: "Cargo will automatically 'normalize'
      Cargo.toml files ... and also rewrite path dependencies to registry dependencies").
      The result has no `[workspace]` table anywhere, so vendoring the crate from its
      **crates.io tarball** instead of its git repo sidesteps the nested-workspace
      confusion completely — `cargo metadata --locked` from the outer workspace resolves
      it immediately once the source is the tarball's flattened manifest, no `exclude`
      entry or workspace restructuring needed on either side.
    - **Diff the tarball against the git tag first to keep the patch minimal and
      git-`apply`-able elsewhere.** `pip download`'s `--no-binary` equivalent for crates is
      `curl .../api/v1/crates/<name>/<version>/download | tar xz`; diffing that against a
      `git clone --filter=blob:none` of the same tag at the one file that matters
      (`diff lance-core-tarball/src/utils/cpu.rs lance-core-git/rust/lance-core/src/utils/cpu.rs`)
      showed the two are byte-identical apart from the normalized manifest, so the same
      unified diff applies cleanly to either source — generate it against the git tag
      (cleaner paths, matches how the crate's own repo is laid out for anyone checking the
      patch against upstream) and apply it to the tarball extraction with `patch -p1`
      (there is no `.git` in a tarball extraction for `git apply` to use).
    - **Regenerate the `Cargo.lock` delta by hand, not with `cargo update`.** Running
      `cargo update -p <crate> --precise <version>` after adding the `[patch]` re-resolves
      the *entire* graph against the current registry index snapshot, not just the patched
      package — on this workspace it silently downgraded a dozen unrelated crates
      (`windows-sys`, `itertools`, `unicode-width`, ...) to whatever the index considered
      minimal-but-compatible that day, none of which upstream ever pinned. The actual delta
      a `[patch]` needs is mechanical and tiny: delete the `source =` and `checksum =`
      lines from the patched package's `[[package]]` block (a path dependency has neither),
      leave every other line untouched, and confirm with `cargo metadata --locked` (exit 0,
      no re-resolution) rather than trusting the edit by eye.
    - **crates.io's download endpoint 403s a plain `curl` with no `User-Agent`** —
      `curl -fsSL https://crates.io/api/v1/crates/<name>/<version>/download` fails with
      `curl: (22) The requested URL returned error: 403` both locally and from the runner;
      add `-A "<anything descriptive>"` and it succeeds. Cheap to catch locally before
      relying on this pattern in a `run:` step at all (this cost one full CI queue-and-fail
      cycle on the runner to notice).
    - **The same `[patch.crates-io]`-at-a-vendored-copy technique extends past a missing
      cfg *arm* (gotcha 78's signature) to a type that does not exist on the target
      architecture at all.** lance-linalg 9.0.0's `f32x8`/`f32x16`/`f64x4`/`f64x8`/`i32x8`
      each have three `#[cfg(target_arch = "...")]`-gated struct *definitions*
      (x86_64/aarch64/loongarch64) with **unconditional** trait impls (`Add`, `Mul`,
      `Debug`, the crate's own `SIMD` trait, ...) referencing them — riscv64 gets
      `error[E0425]: cannot find type 'f32x16' in this scope` at every impl, not a type
      mismatch inside one closure. The same crate's `u8x16` (in a sibling file) already
      ships a fourth, portable `#[cfg(not(any(x86_64, aarch64)))] pub struct
      u8x16([u8; 16])` arm with a scalar-loop body for every method — grep sibling files
      in the same `simd`-shaped module for this pattern before writing one from scratch;
      copying its shape (one array-backed struct, one added `#[cfg(not(any(...)))]` arm
      per method, per operator impl) turned an initially-daunting ~2,700-line, five-type
      gap into a mechanical, low-risk patch.
    - **Validate a scalar-fallback SIMD patch by borrowing an architecture you don't have,
      not by trying to cross-compile.** No local cross C toolchain reproduces the riscv64
      runner, but the fallback code itself is architecture-agnostic — temporarily rename
      the *real* `target_arch = "aarch64"` guards in a scratch copy (e.g. to
      `"aarch64_disabled_for_local_check"`, an unrecognized cfg value that never matches)
      and widen the new fallback's `not(any(...))` to no longer exclude aarch64. `cargo
      test` then runs the crate's own SIMD unit tests through the new scalar path for
      real, using a fully working native toolchain (no cross-compiler, no QEMU) — this
      caught nothing here (24/24 passed unmodified) but would have caught a transposed
      index or wrong accumulator before spending a riscv64 CI cycle on it.

306. **A pyo3 release that predates a newer CPython by years does not necessarily fail to
    build against it — pyo3-build-config only floors the supported version, it has no
    ceiling (the murmurhash2 case; see `build-murmurhash2.yml`).** murmurhash2-py's
    released v0.2.10 tag pins `pyo3 = "0.15.1"` (`abi3-py36`), a release whose own
    `ABI3_MAX_MINOR` constant tops out at Python 3.9 and whose changelog never mentions
    anything past 3.10 — reasoning from that alone suggests the crate can't compile
    against a cp312+ interpreter at all. It does: `pyo3-build-config`'s only
    interpreter-version check is `assert!(self.version >= MINIMUM_SUPPORTED_VERSION)`
    (3.6), with no matching upper bound, and it happily emits
    `cargo:rustc-cfg=Py_3_{6..N}` for any newer minor — an unrecognized cfg is just
    unused, not an error. Confirmed by building the actual checkout locally
    (`cargo build --release` with `PYO3_PYTHON` pointed at a 3.12 interpreter) before
    writing any YAML: it compiled clean and the resulting extension imported and ran
    correctly under 3.12.
    - **Verify empirically, not from the crate's changelog or a version-support constant
      grepped out of its source** — a constant like `ABI3_MAX_MINOR` caps which
      `abi3-pyNN` *feature* values exist, not which interpreter the crate can be compiled
      against; those are two different checks and only the second one matters here
      (gotcha 96 covers which interpreter to pick once building is known to work).
    - **The same old pyo3 release can still be a real, unrelated blocker for
      free-threading**: a version old enough to predate PEP 703 entirely has no
      `Py_GIL_DISABLED` handling at all, so cp314t is not just untested but
      architecturally unsupported — drop it from the matrix outright (same outcome as
      gotcha 11's litellm case, but for a version-age reason rather than a deliberate
      upstream choice) rather than assuming the abi3 build's success implies the
      free-threaded one would also compile.

312. **A maturin `bindings = "bin"` project's published sdist can carry a `pyproject.toml`
    that exists nowhere in the git checkout at all, not even in a subdirectory — building
    the tag directly silently ships the wheel under the Cargo crate's name instead of the
    real distribution name (the taplo case; see `build-taplo.yml`).** Gotcha 239 covers a
    maturin sdist hoisting `pyproject.toml` to its root when the git checkout has one at a
    *different* path (a workspace member's subdirectory). taplo is a step further: its
    GitHub repo's own CI (`ci.yaml`/`releases.yaml`) has no PyPI wheel job at all, and
    `find . -iname pyproject.toml` across a fresh clone of `release-taplo-cli-0.9.3`
    returns nothing anywhere in the tree — the file is synthesized by whatever out-of-repo
    process the maintainer runs to cut the PyPI release, and only the downloaded sdist
    (`pip download taplo==0.9.3 --no-binary :all:`) has one, at its root, declaring
    `[project] name = "taplo"` and `[tool.maturin] manifest-path =
    "crates/taplo-cli/Cargo.toml"`. Building the git tag with `maturin build
    --manifest-path crates/taplo-cli/Cargo.toml` and no `pyproject.toml` anywhere on the
    ancestor walk falls back to `Cargo.toml`'s own package name, so the wheel comes out
    `taplo_cli-0.9.3-py3-none-manylinux_2_39_riscv64.whl` — it builds and installs fine,
    so nothing fails until the *test* job's `uv pip install --no-index --find-links . taplo`
    reports `taplo was not found in the provided package locations`, not a build error.
    - **Two checks settle it before writing the workflow**: `find . -iname pyproject.toml`
      on a fresh clone of the tag (gotcha 239's check, but read for "nothing at all" as a
      distinct outcome from "present at a different path"), and diffing the checked-out
      `Cargo.toml`'s `[package] name` against the actual PyPI project name — a mismatch
      here (`taplo-cli` vs `taplo`) is the tell.
    - **Fix: recreate the release's own `pyproject.toml` verbatim via a `run:` heredoc at
      the checkout root**, right before the `maturin-action` step — this is missing
      packaging metadata the job needs, not a source defect, so gotcha 7's sanctioned
      "write it at run time" mechanism applies, not a `patches/` entry. Source the exact
      content from the real sdist (gotcha 2's inspection step), not a hand-written guess.
    - **Verified against maturin's own resolver, not assumed**: `project_layout.rs`'s
      `resolve_manifest_paths` walks `path.ancestors()` from the `--manifest-path` CLI
      argument's directory upward, checking each level for `pyproject.toml`, and the walk
      continues up to and including the Cargo *workspace* root before stopping (it only
      breaks once a candidate directory is no longer inside the workspace root's parent).
      A file written at the checkout root (the workspace root here) is therefore found even
      though it sits several directories above the crate `--manifest-path` names — no
      `--manifest-path` change needed alongside it.

314. **A maturin library project (`bindings` unset, i.e. plain `pyo3`) with no
    `python-source` and no `<name>/` directory anywhere in the git checkout can still ship
    a wheel with an auto-generated `<name>/__init__.py` re-export shim around a compiled
    `<name>.<name>` submodule — a `.so` probe against the top-level import fails on a
    perfectly good wheel (the rbloom case; see `build-rbloom.yml`).** rbloom's
    `pyproject.toml` has no `[tool.maturin] python-source`, and `find . -iname
    '__init__.py'`/`find . -maxdepth 1 -name rbloom` on a fresh clone come up empty — only
    `src/lib.rs` and a root-level `rbloom.pyi` stub exist. Gotcha 224 uses exactly this
    signature (no `python-source`, no package directory) to conclude a `bindings = "bin"`
    wheel ships *bare*, with nothing to import as a package. That conclusion doesn't
    transfer to an ordinary library binding: maturin's default (non-`bin`) mixed-layout
    detection still synthesizes a `<name>/__init__.py` at build time —
    ```python
    from .rbloom import *

    __doc__ = rbloom.__doc__
    if hasattr(rbloom, "__all__"):
        __all__ = rbloom.__all__
    ```
    — wrapping the real extension at `rbloom/rbloom.abi3.so`, and hoists the root
    `rbloom.pyi` stub into `rbloom/__init__.pyi` alongside a generated `py.typed`. None of
    this exists as a file in the repository; `unzip -l` on the built wheel is the only way
    to see it (gotcha 56's "probe the extension by its real name" applies once you know to
    look, but nothing in the checkout hints that a shim will appear). A probe written from
    the checkout's apparent bare shape — `python -c "import rbloom; assert
    rbloom.__file__.endswith('.so')"` — asserts on the shim's `__init__.py` and fails a
    wheel where `import rbloom` and the whole upstream test suite (`from rbloom import
    Bloom`) work perfectly, because the shim's `from .rbloom import *` re-exports
    correctly.
    - **One local `maturin build` on any host settles it before writing `CIBW_TEST_COMMAND`**
      (gotcha 9's discipline, extended past sdist inspection to the *built wheel*):
      `unzip -l dist/*.whl` shows the real layout in seconds, no riscv64 cycle needed.
    - **Probe the submodule, not the package**: `import <name>.<name> as m;
      assert m.__file__.endswith('.so')`, then let the actual test suite (which imports the
      public name normally) exercise the shim.

322. **A pyo3 release old enough to hand-roll CPython's legacy `PyUnicode_KIND`/`PyUnicode_DATA`
    macros as raw struct-offset reads can compile clean against a newer CPython and still
    segfault the first time a string crosses the FFI boundary (the markdown-it-pyrs case; see
    `build-markdown-it-pyrs.yml`).** Gotcha 306 shows an old pyo3 (0.15.1) compiling *and*
    running correctly against a CPython it predates by years, because `pyo3-build-config`'s
    only version check is a floor, never a ceiling. markdown-it-pyrs's pyo3 0.19.2 looks like
    the same shape at compile time — `cp312`/`cp313`/`cp314` all build clean — but only
    `cp312`/`cp313` pass their test suite; `cp314` SIGSEGVs inside the compiled `.so` on the
    very first `MarkdownIt().render()` call, right after an earlier test in the same file that
    only calls `enable()`/`enable_many()` (no string crosses the FFI boundary there) passes
    clean. The tell that this is a Unicode-layout break, not a riscv64 arch bug: a *newer*
    pyo3-ffi, which generates its raw FFI declarations by parsing the real installed headers,
    fails to even find `PyUnicode_KIND`/`PyUnicode_New`/`PyUnicode_DATA`/`PyUnicode_1BYTE_KIND`
    against Python 3.14 headers (`PyO3/pyo3#4662`) — those were never real exported C-ABI
    symbols, they were header macros that read `PyASCIIObject`/`PyCompactUnicodeObject` fields
    directly, and pyo3-ffi 0.19.2 reimplements that read in Rust against a struct layout frozen
    from ~2023. CPython 3.14 changed that internal layout enough to break the frozen offsets,
    so a 3.14 string handed back through pyo3 0.19.2's fast path reads a garbage `kind`/`data`
    pointer.
    - **Bisect by interpreter, not by rebuilding once.** cibuildwheel's matrix already builds
      one wheel per interpreter for a non-abi3 pyo3 crate (gotcha 10/11), so a segfault on only
      the newest leg while the identical riscv64 image/toolchain builds the siblings clean *is*
      the diagnosis — no separate x86_64/aarch64 rehearsal is needed to rule out an arch-specific
      asm bug (contrast gotcha 78/179, where a crash reproduces identically on every arch and is
      a genuine dependency-tree issue instead).
    - **Drop the broken interpreter — there is no source-level knob to reach for.** Unlike
      gotcha 237's opt-in Cargo feature, the fix here lives in a pyo3 upgrade upstream hasn't
      shipped. `CIBW_BUILD`/the matrix simply excludes `cp314` alongside the free-threaded
      exclusion gotcha 306 already covers, and the PR's **Matrix** line should name both reasons
      since they are independent (no abi3 feature, `Py_GIL_DISABLED` absent, *and* this
      Unicode-layout break all apply to the same crate).

325. **A maturin `[tool.maturin] include` list is scoped to the *wheel*, not the sdist — a
    project whose list omits `tests/` ships a tests-less sdist even though the sdist->bdist
    shape (gotcha 6) needs one (the typeid-python case; see `build-typeid-python.yml`).**
    typeid-python's `pyproject.toml` declares `include = ["LICENSE", "README.md",
    "typeid/**", "rust-base32/**"]` with no `tests/**` entry; `python -m build --sdist`
    honors that list for the sdist too, not just the wheel, so `tar tzf` on the built
    tarball shows zero `tests/` matches. cibuildwheel's build and install steps succeed
    normally — the failure only surfaces at the test step, and only because the extracted
    sdist is what `CIBW_TEST_COMMAND` points at: `ERROR: file or directory not found:
    /project/typeid-python/tests`. Gotcha 104 already covers the general fix (check out the
    tag *alongside* the extracted sdist, at cibuildwheel's cwd, and stage `tests/` from
    there via `CIBW_TEST_SOURCES`), but a maturin project has a simpler option when it
    applies: **the sdist job existed only to guard against gotcha 10's floating-dependency
    trap, and that trap needs an upstream-gitignored `Cargo.lock`.** When `Cargo.lock` is
    committed to git instead (`git show <tag>:rust-base32/Cargo.lock` succeeds), there is
    nothing left for the sdist step to protect against, so drop the whole `python_sdist` job
    and build straight from the git checkout (`build-fastnanoid.yml`'s shape) — `tests/` is
    simply present there, no `CIBW_TEST_SOURCES` staging needed either.
    - **Two greps settle which fix applies before writing the workflow**: `git show
      <tag>:<manifest-dir>/Cargo.lock >/dev/null` (present -> build-from-checkout is safe
      and simplest) and `grep -A5 '\[tool.maturin\]' pyproject.toml` for an `include` list
      that omits `tests/**` (absent entirely, or a `tests/**` entry present, means the
      sdist already carries tests and neither fix is needed).
    - **Confirm from the artifact, not from the pyproject read alone.** `gh run download
      <run-id> -n <pkg>-<version>.tar.gz && tar tzf *.tar.gz | grep -c tests/` on the
      actual sdist your `python_sdist` job produced is what turns "the include list looks
      like it might exclude tests" into certainty, cheaper than a second failed riscv64
      matrix leg.

326. **Gotcha 306's "pyo3-build-config only floors the version, it has no ceiling" stopped
    being universally true at some point — a newer pyo3 release can hard-error at build time
    for an interpreter it postdates (the pyrage case; see `build-pyrage.yml`).** pyrage
    v1.4.0 pins `pyo3 = "0.24.2"` (`abi3-py310`, unconditional per gotcha 181); its `cp314t`
    leg (no abi3 under `Py_GIL_DISABLED`) fails in-container with `error: The configured
    Python interpreter version (3.14) is newer than PyO3's maximum supported version
    (3.13)` — an explicit ceiling check, not the silent-cfg floor-only behavior gotcha 306
    documented for pyo3 0.15.1. The two gotchas aren't contradictory, they're evidence that
    this check's presence/strictness has changed across pyo3's own history — **verify
    empirically per pyo3 release, don't assume either behavior from a citation.** The
    `cp310-abi3` leg is unaffected: only the interpreter actually *compiling* hits this
    check (cp310, well under the 3.13 ceiling), and cibuildwheel's `find_compatible_wheel`
    reuses that build to merely *install and test* on cp311-cp314 with no second compile.
    - **A version bump to clear the ceiling is not automatically low-risk — verify the
      cascade before choosing it over dropping the interpreter.** A local `cargo check`
      with `pyo3` bumped to the release upstream's own `main` branch later moved to
      (0.29.2, confirmed via the upstream repo's post-v1.4.0 `Cargo.toml`) first fails
      dependency resolution (`pyo3-file 0.12.0` pins `pyo3 = ">=0.24, <0.25"`, so it needs
      bumping too), and bumping `pyo3-file` to 0.17.0 then surfaces 13 real compile errors
      across every `src/*.rs` file (`Python::with_gil` was renamed to `try_attach` in a
      later pyo3 release) — a source-level API migration, not a patch-worthy one-liner.
      Dropping the interpreter (gotcha 322's fix) stays correct here; reach for a bump only
      when the local `cargo check` comes back clean.

344. **`PyO3/maturin-action` does not always use the maturin version you'd expect from the
    action's own defaults — its `findVersion()` reads the *target crate's* `pyproject.toml`
    `[build-system] requires` for a `maturin==X.Y.Z`/`maturin>=X.Y.Z` entry first, and only
    falls back to `latest` when there is none (the `valkey-glide` async client port).**
    `python/glide-async/pyproject.toml` pins `requires = ["maturin==0.14.17"]` — a pin
    upstream's own CI never actually exercises, because their release job calls
    `PyO3/maturin-action` directly (bypassing PEP 517 / pip's build-system resolution
    entirely), so the pin is stale dead config that looks harmless until something reads it
    literally. `maturin-action` does read it literally: it resolves `v0.14.17`, builds a
    download URL (`.../releases/download/v0.14.17/maturin-riscv64gc-unknown-linux-musl.tar.gz`),
    and that release predates riscv64 having any release assets at all (maturin only started
    publishing a `riscv64gc-unknown-linux-musl` asset around 1.x; 0.14.17 is a 2023-era
    release). The download 404s, `curl | tar -xz` gets an HTML error page instead of a
    gzip stream, and the job dies in the action's own "Install maturin" group with `gzip:
    stdin: not in gzip format` — before your `before-script-linux` or `args` ever run, so
    the failure looks unrelated to the crate at first glance.
    - **The fix is a one-line override, not a source patch**: pass `maturin-version:
      '1.15.0'` (or whatever current release you've confirmed ships a riscv64 asset) on
      the `PyO3/maturin-action` step. `findVersion()` checks `core.getInput('maturin-
      version')` before ever touching `pyproject.toml`, so this is a real override, not a
      hint.
    - **Two greps settle whether this applies before you hit it**: `grep -A3
      '\[build-system\]' <manifest-dir>/pyproject.toml` for a `maturin==` (not `>=`,
      `<2.0`, etc.) exact pin, and `curl -sI https://github.com/PyO3/maturin/releases/
      download/v<pinned>/maturin-riscv64gc-unknown-linux-musl.tar.gz` for a 404. An
      unpinned or range-pinned `requires` resolves through `findReleaseFromManifest`
      against the actual release list and is far less likely to land on a pre-riscv64
      version.

345. **Driving `PyO3/maturin-action`'s `before-script-linux` yourself to build auxiliary
    native artifacts (a separate cdylib, a second maturin-built extension) runs into a
    PATH gap the action's own environment setup leaves behind: its hardcoded
    `/opt/python/cp3XX-cp3XX/bin` additions stop at cp312 (the `valkey-glide` async
    client's `glide-shared` companion extension build).** The async client bundles a
    second pyo3 extension (`glide_shared._fast_response`, built by a separate `maturin
    build` invocation inside `before-script-linux`, once per target interpreter) plus a
    protobuf-codegen step needing a `mypy-protobuf`-provided `protoc-gen-mypy` plugin,
    `pip install`ed with the same target interpreter. For cp312 this works — maturin-
    action's own command list literally appends `/opt/python/cp312-cp312/bin` to `PATH`
    before running the user script — but cp313/cp314/cp314t are never added, so a
    `shutil.which("protoc-gen-mypy")` run from *that same interpreter* still returns
    `None`: the console-script exists on disk (in that interpreter's own `bin/`) but isn't
    on `PATH`. `protoc --plugin=protoc-gen-mypy=None ...` then fails with `None: program
    not found or is not executable`, `--mypy_out: protoc-gen-mypy: Plugin failed with
    status code 1` — three of four matrix legs died here identically while cp312 (the one
    interpreter the hardcoded PATH covers) sailed through to a genuine multi-hour compile.
    - **Fix: never resolve a same-interpreter console-script via `PATH`/`shutil.which()`
      inside a manylinux `before-script-linux` — compute its directory directly.**
      `"$PY_BIN" -c 'import sysconfig; print(sysconfig.get_path("scripts"))'` returns the
      exact `bin/`-equivalent directory for whichever interpreter ran it, independent of
      what any wrapper action has or hasn't added to `PATH`; append the script name to
      that instead of shelling out to `which`.
    - **The failure signature is a fast, clean one to misdiagnose as something else**: it
      happens within the first couple of build-log lines after `pip install` succeeds, well
      before any `cargo build` output, so it is easy to mistake for a protoc/protobuf
      version problem rather than a PATH problem — check for a literal `None` in the error
      text (the smoking gun that a Python-side path lookup silently failed) before
      suspecting the protoc invocation itself.

364. **Patching a checked-out workspace `Cargo.toml`'s placeholder version (to match a
    static, non-`dynamic` `pyproject.toml` `[project] version`, e.g. `tombi`) makes the
    committed `Cargo.lock` stale for every *local* workspace-member package, and
    `PyO3/maturin-action`'s `args: --locked` then fails before any compilation starts.**
    `tombi`'s root `pyproject.toml`/`Cargo.toml` both ship the literal placeholder
    `version = "0.0.0-dev"` (upstream's own `cargo xtask set-version` rewrites both from
    `GITHUB_REF` at release time — see gotcha 239's sibling case); sedding just those two
    lines to the real version leaves `Cargo.lock`'s per-crate `version = "0.0.0-dev"`
    entries for `tombi-cli` and its ~20 in-workspace path dependencies mismatched against
    the new `Cargo.toml`. `cargo metadata` (which `maturin build` runs first) detects the
    drift and needs to rewrite the lock file to fix it up; `--locked` forbids exactly that
    and the job dies immediately in "Build wheel": `error: cannot update the lock file
    ... because --locked was passed to prevent this`, `Caused by: Cargo metadata failed`.
    - **Fix: drop `--locked`, don't patch `Cargo.lock`.** This matches upstream's own
      `release_pypi.yml` maturin-action `args`, which never passes `--locked` either — for
      the same reason: it runs the identical `cargo xtask set-version` version-patch step
      immediately beforehand. `build-taplo.yml`/`build-git-cliff.yml` keep `--locked`
      safely only because neither one touches `Cargo.toml` at all.
    - **Check before copying `--locked` from another `bindings = "bin"` port**: `grep -n
      "0.0.0-dev\|dynamic.*version" pyproject.toml Cargo.toml` in the upstream checkout —
      a static placeholder version needing a patch is incompatible with `--locked`.

365. **A `bindings = "bin"` project whose Cargo dependency tree is unusually heavy (an
    async runtime + TLS stack + LSP framework, not just a CLI-argument-parsing binary)
    can stall on the riscv64 self-hosted runner for hours past the default 360-minute
    `timeout-minutes` with zero new log output, then get killed at the timeout with no
    diagnostic beyond `The operation was canceled` — while an otherwise-identical retry
    (same commit, just a longer timeout) can complete in under an hour.** `tombi-cli`
    pulls in `tokio` (full), `reqwest`+`rustls`+`ring`, `tower-lsp`, and `rayon` on top of
    ~20 in-workspace crates; one run's build log went silent for over five hours right
    after the last dependency ("Compiling env_logger") with `tombi-cli`'s own final
    compile+link never printing, then hit `timeout-minutes: 360` and was cancelled — the
    very next run of the same commit (only `timeout-minutes: 1440` changed) finished the
    same `build_wheel` job in under an hour. This reads as riscv64 self-hosted runner
    contention/flakiness, not a genuine multi-hour compile requirement, but a retry alone
    is not a reliable fix since the same stall could recur.
    - **Fix: set a generous `timeout-minutes` margin (1440, matching
      `build-daft.yml`/other heavy Rust ports) rather than sizing it to the happy-path
      duration** — the cost of an idle timeout is cheap compared to a job dying at 359
      minutes into a build that would have finished at 361.

371. **pyo3 0.22's version ceiling (gotcha 306) is a hard ceiling for a non-abi3,
    per-interpreter build too, one minor above its own release-time latest — the
    `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` escape hatch works without turning abi3 on
    (the flpc case).** flpc's `Cargo.toml` pins plain `pyo3 = "0.22.0"` with no `abi3-pyNN`
    feature, so gotcha 306's "no ceiling, only a floor" claim (pyo3 0.15.1 against a
    murmurhash2 cp312 interpreter) looked like it should generalize. It doesn't: building
    the identical crate against a cp314 interpreter fails outright with `error: the
    configured Python interpreter version (3.14) is newer than PyO3's maximum supported
    version (3.13)` — 0.22.0 does carry a ceiling, one minor past its own
    `ABI3_MAX_MINOR` (12), evidently to tolerate the next CPython that was in
    pre-release when 0.22.0 shipped. cp312/cp313 both compile and run clean with no
    special handling; only cp314 trips it.
    - **`PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` (`CIBW_ENVIRONMENT_LINUX`) clears the
      ceiling without touching the crate's feature set.** The name suggests it only
      matters for abi3 builds, but it also unblocks a plain per-interpreter build: the
      resulting wheel is still tagged `cp314-cp314` (not `cp314-abi3`), and — verified
      locally by unzipping the wheel into a `python3.14 -m venv --without-pip` site-packages
      and running the module directly (no network `pip install` needed) — `compile`/
      `search`/`fmatch`/`findall`/`sub` all behave identically to the cp312 build. Setting
      the var unconditionally across the whole matrix is harmless: it is a no-op on
      cp312/cp313, which never hit the ceiling it exists to bypass.
    - **cp314t is a separate, real wall** (gotcha 306's free-threading half): pyo3 0.22.0
      predates PEP 703 entirely, so no forward-compatibility flag substitutes for the
      missing `Py_GIL_DISABLED` support — drop it from the matrix rather than trying the
      same escape hatch on it.
    - **Verify empirically per pyo3 release, not by re-applying gotcha 306's conclusion**:
      the two gotchas' crates are three years of pyo3 releases apart (0.15.1 vs 0.22.0),
      and only a local build against the actual next-ceiling interpreter (`cargo build
      --release` / `maturin build` with `PYO3_PYTHON` pointed at it) settles which
      behavior — no ceiling, a hard error, or a flag-gated one — the pinned version
      exhibits.
