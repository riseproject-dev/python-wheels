# Gotchas — cibuildwheel mechanics, the matrix & abi3

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/cibuildwheel-matrix-and-abi3.md`.

## In this file

- **5** — cibuildwheel `{project}` vs `{package}`.
- **7** — Heredoc inside a YAML `run: |` block.
- **11** — abi3 wheels collapse the matrix.
- **12** — Scope an env var to one phase with the right knob.
- **13** — `build-frontend = "build[uv]"` crashes the audit step on the riscv runner.
- **34** — A third way a project gets abi3: `setup.py` sets the `bdist_wheel` option itself.
- **93** — A `>-` folded scalar keeps the newline on any line indented *deeper* than the
- **96** — An abi3 wheel must be built on the OLDEST interpreter its tag claims — building
- **102** — A `build.py` at the project root shadows the `build` module and kills
- **107** — `CIBW_ENVIRONMENT` *replaces* upstream's `[tool.cibuildwheel] environment` table
- **134** — cibuildwheel's default abi3 audit rejects a wheel for exporting its *own*
- **204** — cibuildwheel 4.2.0 doesn't offer cp313t as a build target on *any* platform —
- **221** — `quay.io/pypa/musllinux_1_2_riscv64` is a real, working image — every prior port
- **225** — `CIBW_BEFORE_ALL_LINUX` and `CIBW_BEFORE_BUILD_LINUX` are two different hooks —
- **227** — A build that touches `PyObject` internals directly (`ob_refcnt`, `ob_type`,
- **245** — `actions/checkout` must run before `actions/download-artifact` in the same
- **247** — A folded `>-` scalar's `python -c "` on its own line puts a leading space
- **209** — A multi-grammar tree-sitter-`<lang>` repo does not necessarily need a
- **56** — `py-build-cmake` projects: the free-threaded job dies at *configure* unless
- **201** — When `package-dir` is a monorepo subdirectory and the package's own build script
- **216** — An abi3 build's own mandatory floor interpreter (gotcha 96) can itself be the one
- **217** — Upstream's own `repair-wheel-command` commonly re-runs abi3audit itself via
- **251** — When `package-dir` is a `.tar.gz`, cibuildwheel extracts it to a temp dir and
- **262** — Gotcha 201's vendoring step is only needed when the sibling sources are
- **270** — Gotcha 134's "leaked `Py`-prefixed symbol" failure has a real fix, not just
- **281** — Gotcha 251 recurs even when the port's own notes cite gotcha 104 — a
- **313** — A dynamic abi3 floor (`setup.py` tags whichever interpreter builds it) lets you
- **324** — `{project}` is exactly the on-disk root of the checkout with no `path:` —
- **331** — A platform-specific `[tool.cibuildwheel.<platform>].environment` table already
- **356** — A pybind11 3.x CMake build can silently target the wrong Python on cp314t.
- **360** — A `setup.py`'s own `bdist_wheel --plat-name` insertion can hardcode
  `manylinux1_` + `platform.machine()` regardless of the actual container libc, making
  musllinux unbuildable no matter how the CMake/C++ side is patched.
- **396** — A `cpXY-none-<platform>` wheel is the third plat-name shape: `setup.py` declares
  no `ext_modules` at all, and a sibling CMake build both compiles the extension modules and
  hands `bdist_wheel` the tag.
- **391** — A project's real cibuildwheel recipe can live in a *separate packaging repo* that the
  source tree never references — the source repo can carry no GitHub Actions at all.
- **402** — A two-leg abi3 + free-threaded matrix expressed only through `include:` collapses
  into a single job, so the abi3 wheel is never built and nothing fails.
- **408** — A `setup.py` that reaches for `wheel.bdist_wheel` behind a `try/except ImportError`
  still gets its abi3 tag under modern setuptools.
- **468** — An upstream `build = ["cp3??-*"]` glob excludes every free-threaded interpreter by
  character count, so the project ships no `cp3NNt` wheel at all.
- **469** — An abi3 build *tests* on its floor interpreter, so a package using a
  newer-Python-only API fails our CI while upstream's own CI stays green.
- **487** — `[tool.cmeel] has-sitelib` decides whether a cmeel port needs an interpreter
  matrix at all.
- **514** — A tool that models a *target* Python version caps the matrix itself; its extension
  compiles on every interpreter, so only running the tool shows it.
- **536** — A removed cibuildwheel option makes 4.2.0 reject upstream's whole
  `[tool.cibuildwheel]` table before any build starts; `--print-build-identifiers` catches it
  in a minute.

---

5. **cibuildwheel `{project}` vs `{package}`.**
   `{project}` = invocation dir (`/project`); `{package}` = path passed to CLI
   (`cibuildwheel ./<subdir>` → `/project/<subdir>`). When you pass a subdir,
   **everything in it — including bundled `tests/` — is under `{package}`, not
   `{project}`**. Reference test suites and staged helpers via `{package}`.
   Symptoms: exit **127** (script not found) or exit **4** + `no tests ran` (pytest
   aimed at wrong dir). **Local-repro trap:** `cd <subdir> && cibuildwheel .` makes
   `{project}==subdir` and masks the bug — always invoke from the parent dir.

7. **Heredoc inside a YAML `run: |` block.** YAML strips the common indent, *then*
   bash needs the `EOF` terminator at column 0. Use `<<'EOF'` (quoted) to stop the
   shell expanding `$…` inside the script. Verify by parsing the YAML and checking the
   `EOF` line de-indents to column 0. The `run:` default shell is `bash` on Linux, but
   word-splitting differs from zsh — test shell snippets under real `bash`, not your
   interactive zsh.

11. **abi3 wheels collapse the matrix.** If `pyproject.toml` sets `wheel.py-api = "cpXY"`
    (or otherwise builds abi3/limited-API), one `cpXY` build loads on every newer
    non-free-threaded CPython, so the matrix is just `[cpXY, cp3Nt]` — the abi3 build
    plus a free-threaded build (free-threaded can't use the stable ABI). Tell from the
    PyPI wheel names: `…-cp312-abi3-…` + `…-cp314-cp314t-…` = exactly two builds (same
    shape as onnx/hf-xet, and apache-tvm-ffi). Don't add cp313/cp314 — they'd duplicate
    the cp312 abi3 wheel.
    Some packages ship **only** the abi3 wheel with no cp314t variant (litellm: upstream
    publishes `cp310-abi3` only, no free-threaded wheel). In that case the matrix
    collapses to a single build; run it on cp312 (our minimum) and test-reuse on
    cp313/cp314 via cibuildwheel's `find_compatible_wheel` logic.
    - **maturin abi3 is a pyproject/Cargo feature; setuptools-rust abi3 is a
      build-time *flag* you must inject.** For maturin the abi3 tag comes from
      `wheel.py-api`/the `pyo3/abi3-pyNN` crate feature — set once, inherited. But
      **setuptools-rust** projects (bcrypt, pyca/cryptography) commonly set
      `py-limited-api = "auto"` on the ext, which only turns on abi3 **when
      `bdist_wheel` is passed `--py-limited-api=cpNN`** — and *cibuildwheel does not
      set that itself*. So a plain cibuildwheel run of such a project yields
      per-interpreter `cpNN-cpNN` wheels despite the "auto"; you must inject the flag:
      `CIBW_CONFIG_SETTINGS: --build-option=--py-limited-api=cp312`. It works *with*
      build isolation (setuptools-rust comes from `build-system.requires`), so no
      `--no-build-isolation` needed. Verify locally: build once with the flag (→
      `cpNN-abi3`) and once without (→ `cpNN-cpNN`). The abi3 + free-threaded split
      then needs **two build configs, not one matrix**: the abi3 job passes the flag
      and selects `cp312-* cp313-* cp314-*` (one wheel, reused+tested on each); the
      free-threaded job passes **no** flag and selects `cp314t-*` (pyo3 auto-disables
      abi3 under `Py_GIL_DISABLED`, so it can't be forced). See `build-bcrypt.yml`.
      Heads-up: the `manylinux_2_39_riscv64` image ships cp39–cp315 incl. cp314t/cp315t
      but **no cp313t**, so cp314t is the only free-threaded target even when upstream
      also publishes cp313t.
    - **The `publish` job's dry run is where you catch a missed abi3 tag — read the wheel
      filename it prints, not the artifact name you chose.** `_publish-wheel.yml` echoes the
      real `dist/<pkg>-<ver>-<tag>-<plat>.whl` and the `docs/packages/` diff it would write, so
      a run that is otherwise green still tells you whether you shipped `cpNN-abi3` or
      `cpNN-cpNN`. The vllm CPU port went green with `cp312-cp312` while its PR body and its
      `upload-artifact` name both said "abi3" — neither is evidence, and nothing else in the
      log mentions the tag. Compare it against upstream's own published tag on
      `pypi.org/pypi/<pkg>/json` before calling a port done.
    - **For a project whose only wheel build is a Dockerfile, the flag lives in that
      Dockerfile's `bdist_wheel` line** (gotcha 460's point, applied to the tag rather than to
      a system package): vllm's `docker/Dockerfile.cpu` runs `setup.py bdist_wheel
      --dist-dir=dist --py-limited-api=cp38`, which is the *only* place the abi3 intent is
      recorded — `setup.py` merely sets `py_limited_api` on each extension, and the PyO3 half
      declares `features=["pyo3/abi3-py38"]`. Grep upstream's Dockerfiles for
      `py-limited-api` whenever a project's `.so` files come out named `*.abi3.so` but the
      wheel does not.
    - **Pick the `cpNN` from your own build floor, not from upstream's flag**, or you
      reintroduce gotcha 96: upstream tags `cp38`, but `torch==2.13.0` has no riscv64 wheel
      below cp312, so cp312 is the oldest interpreter the wheel can *ever* be compiled on here
      and a `cp38` tag would claim eight releases it was never built against. Diverging from
      upstream's literal flag is correct in that case — say so in the PR.

12. **Scope an env var to one phase with the right knob.** `CIBW_ENVIRONMENT` applies to
    **both** build and test; `CIBW_TEST_ENVIRONMENT` is test-only. This bites with
    `only-binary`: putting `PIP_ONLY_BINARY=:all:` in `CIBW_ENVIRONMENT` to stop a heavy
    *test* dep (torch) from source-building also starves the **build backend**, and
    `cython` (a common build requirement) has no riscv64 wheel anywhere — it must
    compile from sdist. So keep registry index URLs in `CIBW_ENVIRONMENT` (both phases
    need them) but put `only-binary` in `CIBW_TEST_ENVIRONMENT` alone.

13. **`build-frontend = "build[uv]"` crashes the audit step on the riscv runner.**
    cibuildwheel's post-build "Auditing wheel…" step makes a venv *on the host* and, for
    a uv frontend, asserts a host `uv` exists (`venv.py: assert uv_path is not None`) —
    the self-hosted runner has none, so the wheel builds and auditwheel-repairs fine and
    *then* dies with a bare `AssertionError`. Fix: `CIBW_BUILD_FRONTEND: build` (plain
    pip/virtualenv, the default onnx/cffi/tiktoken already use).

34. **A third way a project gets abi3: `setup.py` sets the `bdist_wheel` option itself.**
    Gotcha 11 splits abi3 into maturin (pyproject/Cargo feature, inherited) vs
    setuptools-rust (a `--py-limited-api` flag *you* must inject via
    `CIBW_CONFIG_SETTINGS`). Plain setuptools has a third form — `setup(options={'bdist_wheel':
    {'py_limited_api': 'cpNN'}})` computed in `setup.py` — which needs **no** cibuildwheel
    config at all, and which upstream commonly guards with
    `if not sysconfig.get_config_var('Py_GIL_DISABLED')` so the free-threaded build silently
    drops back to a per-interpreter wheel. Two consequences:
    - Don't add `CIBW_CONFIG_SETTINGS` "to be safe" — it's redundant divergence. Settle it by
      building the sdist once on any host: pycryptodome yields
      `pycryptodome-3.23.0-cp37-abi3-macosx_....whl` with no flags.
    - **The abi3 floor is upstream's, not ours.** The wheel is tagged `cp37-abi3` even when
      cibuildwheel builds it on cp312, so name the job/artifact after the tag the wheel
      actually carries (`cp37-abi3-manylinux_riscv64`), not after the interpreter that built
      it — `build-bcrypt.yml`'s `cp312-abi3` naming only fits when *we* pick the floor.

93. **A `>-` folded scalar keeps the newline on any line indented *deeper* than the
    first — which silently splits a cibuildwheel command into several (the pyodbc case).**
    The repo's own examples write multi-word cibuildwheel options as
    `CIBW_REPAIR_WHEEL_COMMAND: >-` followed by continuation lines, and the natural
    instinct is to indent the flags under the command for readability. YAML folds a `>-`
    block into spaces only across lines at the **same** indent; a more-indented line keeps
    its `\n` verbatim. So

    ```yaml
    CIBW_REPAIR_WHEEL_COMMAND_LINUX: >-
      auditwheel repair
        --exclude "libodbc.so.*"      # extra indent => newline survives
        --wheel-dir {dest_dir}
        {wheel}
    ```

    reaches cibuildwheel as four `sh -c` lines, and the log reads
    `auditwheel repair: error: the following arguments are required: WHEEL_FILE`,
    `sh: line 2: --exclude: command not found`, `sh: line 3: --wheel-dir: command not
    found`, exit code **126**. It looks like an auditwheel/permissions problem; it is
    purely the YAML.
    - **Neither `yaml.safe_load` nor `actionlint` catches it** — the document is valid and
      the step is well-formed. Add one line to the gotcha-9 checklist that prints the
      *resolved* values instead of just parsing:
      ```
      python3 -c "import yaml;[print(repr(k),'=>',repr(v)) for k,v in yaml.safe_load(open('<wf>'))['jobs']['<job>']['steps'][<i>]['env'].items()]"
      ```
      Any `\n` in the output is the bug. Cheaper than the CI cycle it costs, and it also
      catches the inverse (a `|` literal block where you wanted folding).
    - Distinct from gotcha 7, which is about a heredoc's `EOF` needing column 0 *after*
      YAML strips the common indent. This one needs no heredoc and bites plain `env:`
      values.

96. **An abi3 wheel must be built on the OLDEST interpreter its tag claims — building
    it on a newer one can silently produce a wheel that is broken on the older ones (the
    zopfli case).** Gotchas 11/34 cover *how* a project gets its abi3 tag; this is about
    *which interpreter you build it on*. The stable ABI guarantees a wheel built against
    3.N headers runs on 3.N+, not on 3.10 — but the wheel is tagged `cpXY-abi3` from the
    project's `py_limited_api` setting regardless, so pip on 3.10 will happily install it.
    Concretely: `PY_SSIZE_T_CLEAN` selects the `PyArg_Parse*_SizeT` aliases, which CPython
    **3.13 removed**, so an extension using a `"s#"` format compiled against 3.13+ headers
    calls the plain entry point and every call dies at runtime with
    `SystemError: PY_SSIZE_T_CLEAN macro must be defined for '#' formats` on 3.10-3.12.
    The build is green, `abi3audit --strict` is clean, and the breakage only appears when
    an *older* interpreter imports the wheel.
    - **Mirror upstream's build list rather than starting at our cp312 floor.** Upstream
      orders theirs oldest-first (`cp310-* cp311-* ... cp314-*`) precisely so cibuildwheel
      builds once on the floor and then only *re-tests* on the rest via
      `find_compatible_wheel`. Trimming the leading entries to match this repo's
      per-interpreter default silently changes which headers compile the wheel. The
      riscv64 manylinux image has cp310/cp311, and the extra entries cost one short test
      run each.
    - **Reproduces on any host in minutes, no QEMU** — same discipline as gotchas 23/29:
      build the sdist once per interpreter (`uv build --wheel --python 3.1N`) and run the
      suite from each of the others against each wheel. A full N x N grid of
      pass/fail is the evidence; here only the 3.12-built wheel passed on 3.12, 3.13 and
      3.14.
    - **`abi3audit` does not catch it.** It answers "does this use only limited-API
      symbols, and from which version" (`baseline 3.10, computed 3.10`) — the failing call
      goes through `PyArg_ParseTupleAndKeywords`, which *is* in the 3.10 limited API. Only
      running the suite on an old interpreter finds it.

102. **A `build.py` at the project root shadows the `build` module and kills
    cibuildwheel's default frontend (the dbt-extractor case).** cibuildwheel's default
    `build-frontend` is `build`, and `platforms/linux.py` invokes it as
    `python -m build /project --wheel` with the container's **cwd set to `/project`**
    (`OCIContainer(..., cwd=container_project_path)`). `python -m` puts the cwd at
    `sys.path[0]`, so a repo-root `build.py` — a very common name for a dev helper
    (grammar codegen, asset generation, a poetry `build-system` hook script) — is
    imported *instead of* the `build` package. dbt-extractor's opens with
    `from tree_sitter import Language, Parser`, so every wheel build died with
    `ModuleNotFoundError: No module named 'tree_sitter'` before maturin was ever reached
    — a traceback that names a module the port has nothing to do with, from a file the
    build should never execute.
    - **Fix is one env var, not a patch:** `CIBW_BUILD_FRONTEND: pip`. `python -m pip
      wheel /project` is immune (nothing shadows `pip`), and pip runs the PEP 517 hooks in
      a subprocess whose `sys.path[0]` is the in-process wrapper's directory, not the cwd,
      so the backend import is clean too. Deleting or renaming `build.py` would be
      divergence for no gain.
    - **`ls <checkout>/build.py` is the whole check** — do it while reading upstream's
      build docs (playbook step 1), together with `grep -n build-frontend pyproject.toml`.
      Upstream never hits this when their own CI calls the backend directly
      (`maturin build`, `PyO3/maturin-action`), so their green CI proves nothing here.
    - **Reproduce in one container run, no riscv64 needed** (gotcha 101's aarch64
      rehearsal, minus cibuildwheel): `cd /project && python -m build /project --wheel`
      fails while `python -m pip wheel /project --wheel-dir=/out --no-deps` succeeds. The
      shadowing is cwd-dependent, so a local build run from *outside* the tree passes and
      hides it.

107. **`CIBW_ENVIRONMENT` *replaces* upstream's `[tool.cibuildwheel] environment` table
    rather than merging into it (the spacy case).** Inheriting a project's own
    cibuildwheel config is the whole point of the build-from-checkout shape, but the one
    override every port adds — `PIP_EXTRA_INDEX_URL` so the registry is reachable — is
    also the one that silently drops config. cibuildwheel resolves each option through
    `_resolve_cascade` (`options.py`), which keeps the **last non-None** value; only a
    pyproject-side `inherit` rule (`APPEND`/`PREPEND`) concatenates, and an environment
    variable never carries one. So `CIBW_ENVIRONMENT: PIP_EXTRA_INDEX_URL=…` discards
    every key upstream had set there — spaCy's `environment = { PIP_CONSTRAINT =
    "build-constraints.txt" }`, which is what pins numpy for the build. Read the
    `environment` table before writing the env var and repeat its keys:
    ```yaml
    CIBW_ENVIRONMENT: >-
      PIP_CONSTRAINT=build-constraints.txt
      PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple/
    ```
    Same cascade explains gotcha 51's `CIBW_BEFORE_BUILD: ''` trick from the other
    direction: replacement is exactly what clears an inherited value.
    - **`only:` clears `skip`, so upstream's `skip` is not protecting you.** With
      `--only`, cibuildwheel sets `skip_config = ""` and enables every group, so a tag
      upstream deliberately excludes (spaCy: `cp3??t-*`, i.e. no free-threaded wheels
      anywhere) will build if you put it in the matrix. The matrix *is* the selector —
      read upstream's `skip` and mirror it there.

134. **cibuildwheel's default abi3 audit rejects a wheel for exporting its *own*
    `Py`-prefixed symbols (the awscrt case).** cibuildwheel >=3 runs
    `audit-command = "abi3audit --strict --report {abi3_wheel}"` after `auditwheel repair`
    on every wheel whose tag is abi3, and abi3audit decides what is "CPython API" **by
    name**. A project that gives its own internal helpers CPython-looking names —
    awscrt's `source/module.h` declares `PyErr_AwsLastError`, `PyObject_GetAttrAsBool`,
    `PyUnicode_FromAwsString`, 17 in all — trips it, and the job dies at
    `Audit command failed with exit code 1` *after* a full build, before the tests ever
    run. Nothing about it is arch-specific and there is no exit code to relax: abi3audit
    returns 1 with **and without** `--strict`.
    - **Prove it is a false positive from the ELF, not from the report.** abi3audit's own
      JSON already says `"is_abi3_baseline_compatible": true` with `baseline` == `computed`;
      the clincher is that the flagged names are *defined* in the extension rather than
      imported from libpython — `st_shndx` points at a real section instead of `UND`:
      ```python
      from elftools.elf.elffile import ELFFile   # pyelftools comes with abi3audit
      for sym in ELFFile(open(so,'rb')).get_section_by_name('.dynsym').iter_symbols():
          print(sym.name, sym['st_shndx'])       # a number, not 'SHN_UNDEF'
      ```
    - **Then check upstream's released wheel for another arch** — one `pip download` and
      one `abi3audit` run on any host. If `…-cpXY-abi3-manylinux…_aarch64.whl` fails with
      the same symbol list, the finding is a property of the project, not of the port, and
      the honest fix is `CIBW_AUDIT_COMMAND: ''` (cibuildwheel parses an empty string to an
      empty command list and prints "No audit configured"; `auditwheel repair` is a separate
      step and still runs). Do not reach for it before that comparison: a *real* abi3
      violation is a genuine defect in the wheel you are about to publish.
    - Free-threaded jobs never see this — their wheels are not abi3, so the
      `{abi3_wheel}` command is skipped. A matrix where only the abi3 entries fail at the
      audit step, with cp3XXt green, is the signature.

56. **`py-build-cmake` projects: the free-threaded job dies at *configure* unless
    `cmake.minimum_version` is raised, and the gotcha-32/44 licence fix does not
    transfer verbatim (the amazon-ion case; see `build-amazon-ion.yml`).** A
    `build-backend = "py_build_cmake.build"` project drives CMake over the extension
    plus whatever C tree the pyproject points at, and provisions its own `cmake`/`ninja`
    from PyPI (both publish riscv64 wheels, gotcha 51), so the port is an ordinary
    build-from-checkout. Two traps are specific to the backend, and both are settled on
    any host — neither is arch-related:
    - **CMake grew free-threaded support in FindPython in 3.30, and py-build-cmake only
      adds the `t` flag to `Python3_FIND_ABI` when `[tool.py-build-cmake.cmake]
      minimum_version` lets it assume that release** (`commands/cmake.py:
      get_native_python_abi_tuple`). The key defaults to 3.15, so a project that never
      sets it — i.e. any project whose upstream ships no free-threaded wheels — logs
      `CMake version 3.15 does not support the free-threaded ABI` as a *warning* and
      then fails with `Could NOT find Python3 (missing: Development.Module) (found
      suitable exact version 3.14.7)`: CMake was looking for the default ABI's headers
      and library, not the `t` ones. Fix is one line in `pyproject.toml`,
      `minimum_version = "3.30"`; it gates nothing else, so the GIL-ful builds are
      untouched (their ABI tuple is all-OFF and never passed to CMake). Prefer the patch
      over `CIBW_CONFIG_SETTINGS`: py-build-cmake's `-C override=` grammar needs the
      value **quoted** (`cmake.minimum_version="3.30"` parses, bare `3.30` is a
      `NUMBER` followed by junk), and cibuildwheel's shlex pass eats the quotes.
    - **PEP 639 `license-files` is rejected while `license` is a table.** Gotcha 44's
      "drop `LICENSE.<dep>` at the project root" trick is a *setuptools* default-glob
      behaviour and does nothing here: py-build-cmake copies exactly
      `project.license-files` into `.dist-info/licenses/`, preserving each entry's
      relative path, and pyproject-metadata refuses the key unless `project.license` is
      an SPDX expression (`"project.license-files" must not be used when
      "project.license" is not a SPDX license expression`). So the licence patch is two
      coupled edits — `license = "<SPDX>"` *and* the file list — which also moves the
      licence text out of METADATA's `License:` into `License-Expression:`/
      `License-File:`. Same shape applies to any Metadata-2.4 backend, not just this one.
    - **Reproduce a manylinux_riscv64 configure/build failure on `manylinux_2_39_aarch64`
      first** (gotcha 47's advice, generalised): identical Rocky-10 image family, same
      `/opt/python/cp3XX*` layout and the same pipx `cmake`, so a
      `docker run --platform linux/arm64 … python -m build --wheel` reproduced the cp314t
      failure and proved the fix in ~4 minutes on an arm64 laptop — versus a ~25-minute
      round trip on the self-hosted riscv64 runner. Reach for it whenever the failure is
      in *configure* or in Python-ABI detection rather than in generated code.

201. **When `package-dir` is a monorepo subdirectory and the package's own build script
     vendors sibling source trees into itself, run that vendoring step as a plain host-side
     workflow step *before* cibuildwheel runs — not inside `CIBW_BEFORE_ALL`/`BEFORE_BUILD`
     (extends gotcha 5).** `{project}` being the whole checkout doesn't help if the
     package's own tooling expects those sibling sources to already be physically staged
     *inside* `package-dir` — MANIFEST.in/pyproject.toml only pick up what already exists
     on disk there at sdist-assembly time, which cibuildwheel does per-interpreter from
     `package-dir`'s current contents. The grpcio-tools case:
     `tools/distrib/python/make_grpcio_tools.py` copies `src/compiler`, `include/`, and
     `third_party/{protobuf,abseil-cpp}` from the checkout root into `grpc_root/` and
     `third_party/` *inside* `tools/distrib/python/grpcio_tools/` (both gitignored —
     upstream's own `install_all_python_modules.sh` runs the same script before building).
     A single `run: python3 tools/distrib/python/make_grpcio_tools.py` step placed right
     after checkout, before `uses: pypa/cibuildwheel@…` with
     `package-dir: tools/distrib/python/grpcio_tools`, is enough: by the time cibuildwheel
     packages that subdirectory per matrix job, the vendored trees are already there.

204. **cibuildwheel 4.2.0 doesn't offer cp313t as a build target on *any* platform —
     sharpens gotcha 11's "the riscv64 image ships no cp313t" from an image gap to a tool
     gap.** Porting pyyaml-ft (a free-threading fork of PyYAML whose own upstream CI
     matrix is exactly `cp313`/`cp313t`), `python -m cibuildwheel --print-build-identifiers
     --platform linux --archs aarch64 --enable cpython-freethreading` on the *native*
     `manylinux_2_39_aarch64` image (no riscv64 involved at all) lists `cp313`, `cp314`,
     `cp314t`, `cp315`, `cp315t` and no `cp313t`, `--enable cpython-freethreading` included.
     Confirmed at the source: cibuildwheel's own bundled
     `cibuildwheel/resources/build-platforms.toml` has zero `cp313t` entries under *any*
     of its linux/macos/windows/pyodide/android/ios platform tables — cp313 stops at the
     GIL build, and cp314t is the oldest free-threaded identifier cibuildwheel 4.2.0 knows
     how to build, full stop. So even a hypothetical riscv64 image that *did* ship a
     `cp313t-cp313t` interpreter under `/opt/python` would not fix this — cibuildwheel
     itself has no `cp313t-manylinux_riscv64` build identifier to select. The fix is
     gotcha 11's: build `cp313` (matches upstream's GIL wheel) and substitute `cp314t` for
     upstream's `cp313t` free-threaded wheel, same two-job split as `build-bcrypt.yml`. Re-check
     this gate on every cibuildwheel version bump — a future release could reinstate cp313t
     (or drop cp314 the way this one already dropped cp313t's free-threaded pairing), and
     `--print-build-identifiers` costs nothing to re-run before committing to a matrix.

209. **A multi-grammar tree-sitter-`<lang>` repo does not necessarily need a
     `CIBW_BUILD`/wheel per grammar — read `setup.py`'s `ext_modules` to see whether the
     grammars share one extension.** tree-sitter-php (PR #855) has two separate
     `Extension()` entries (`php._binding`, `php_only._binding`), one per grammar, but both
     still land in a single wheel from one `cibuildwheel` invocation — no matrix change
     needed either way. tree-sitter-typescript (0.23.2) instead declares *one*
     `Extension(name="_binding", sources=[...typescript/src..., ...tsx/src...])`: both
     grammars' `parser.c`/`scanner.c` compile into the same `tree_sitter_typescript._binding`
     shared object, which exports two functions (`language_typescript()`, `language_tsx()`)
     via one `PyMethodDef` table — confirmed by reading `bindings/python/tree_sitter_typescript/binding.c`
     and `__init__.py`'s `from ._binding import language_typescript, language_tsx`. Either
     shape gets the same `build-tree-sitter-<lang>.yml`: one `cibuildwheel` step, `CIBW_TEST_SOURCES:
     bindings/python/tests`, `CIBW_TEST_COMMAND: python -m unittest discover`, and upstream's
     own `test_binding.py` already exercises every grammar function it exposes — don't add
     a second build identifier or a second wheel artifact just because a repo advertises
     more than one grammar.

216. **An abi3 build's own mandatory floor interpreter (gotcha 96) can itself be the one
     identifier our registry can't test — skip only that identifier's test, don't drop it
     (the timezonefinder case).** timezonefinder's `setup.py` sets `py_limited_api="cp311"`
     unconditionally, so gotcha 96 says build there. But `h3` and `numpy` — genuine runtime
     dependencies (`Requires-Dist`, not just build-time) — publish riscv64 wheels starting
     at cp312 on both PyPI and `pypi.riseproject.dev`; nothing exists for cp311 on either.
     cibuildwheel always runs `pip install {wheel}` before the test phase (gotcha 122), so
     that install fails to resolve `h3`/`numpy` under cp311 even though the **build** phase
     is unaffected (it only needs `cffi`, which the registry does cover at cp311). The
     wheel that ships is unaffected either way — it is genuinely `cp311-abi3` — only its
     *test coverage* has a gap.
     - **Keep cp311 in `CIBW_BUILD`** (it must stay the first/oldest identifier so
       cibuildwheel compiles there per gotcha 96), list the newer interpreters your
       registry *does* cover alongside it so `find_compatible_wheel` reuses+retests the
       same wheel there, and add `CIBW_TEST_SKIP: cp311-*` so only the untestable identifier
       skips install-and-test — the other entries keep full coverage.
     - **Distinguish from gotcha 84's matrix trimming.** There, a dependency gap removes
       whole matrix *entries* because each is independently optional. Here the affected
       entry is not optional — it is the only one that actually compiles the wheel — so the
       fix is a test-only skip on that one identifier, never a `CIBW_BUILD` deletion.
     - Confirm the gap is real per gotcha 30, per interpreter tag, on *both* indexes before
       reaching for `CIBW_TEST_SKIP` — a registry addition later is a one-line revert, not a
       reason to guess now.

217. **Upstream's own `repair-wheel-command` commonly re-runs abi3audit itself via
     pipx/uvx, which the riscv64 image doesn't carry — and it is redundant besides,
     because cibuildwheel's default `audit-command` already abi3audits every abi3-tagged
     wheel natively (gotcha 134) once `auditwheel repair` finishes.** Seen twice
     independently: rustworkx's `[tool.cibuildwheel.linux]` pipes `auditwheel repair`
     into a pipx-installed abi3audit, timezonefinder's pipes it into
     `uvx abi3audit --strict --summary {wheel}`. Both tools are typically absent from the
     manylinux_riscv64 image, so the inherited `repair-wheel-command` fails at the second
     step even though `auditwheel repair` itself succeeds.
     - **Override `CIBW_REPAIR_WHEEL_COMMAND_LINUX` to just
       `auditwheel repair -w {dest_dir} {wheel}`**, dropping the redundant tool
       invocation, rather than installing pipx/uv into the container to satisfy upstream's
       version. cibuildwheel's own post-repair audit step still runs unconditionally on
       every abi3-tagged wheel, so nothing about abi3 conformance checking is actually
       lost.
     - Setting `CIBW_REPAIR_WHEEL_COMMAND_LINUX` (not the bare `CIBW_REPAIR_WHEEL_COMMAND`)
       leaves any macOS/Windows repair command upstream might also declare untouched —
       irrelevant to riscv64 but keeps the diff minimal against the pyproject you copied
       from.

221. **`quay.io/pypa/musllinux_1_2_riscv64` is a real, working image — every prior port
     that mentioned musllinux riscv64 dropped it not because the image is broken, but
     because a *runtime* dependency (almost always numpy) has no musllinux riscv64
     wheel on either PyPI or our registry (workflow-anatomy.md's "dropping musllinux is
     an accepted outcome" is about that gap, not the image itself).** ckzg has zero
     `requires_dist` and its only test dependency (PyYAML) builds fine from sdist with
     no libyaml-dev present, so it hit no such wall: a `python: [...] x libc:
     [manylinux, musllinux]` matrix (`CIBW_BUILD:
     ${{ matrix.python }}-${{ matrix.libc }}_riscv64`, both
     `CIBW_MANYLINUX_RISCV64_IMAGE`/`CIBW_MUSLLINUX_RISCV64_IMAGE` set unconditionally)
     built and tested clean on cp312/cp313/cp314/cp314t for both libcs in one pass —
     the first confirmed musllinux riscv64 success in this repo. Check the package's
     own dependency footprint (`requires_dist`, `CIBW_TEST_REQUIRES`) against the
     registry before assuming musllinux riscv64 needs to be dropped by default; try it
     when nothing pulls in a numpy-shaped blocker.

225. **`CIBW_BEFORE_ALL_LINUX` and `CIBW_BEFORE_BUILD_LINUX` are two different hooks —
     overriding the one upstream *doesn't* use leaves theirs running too (the uamqp
     case).** Both env vars replace their matching `[tool.cibuildwheel.linux]` key
     independently (gotcha 107's cascade, one level more specific); they don't share a
     slot, so setting `CIBW_BEFORE_ALL_LINUX` while upstream's own pyproject sets
     `before-build` doesn't touch it at all — cibuildwheel runs **both**, yours first,
     then theirs. uamqp's `before-build` builds OpenSSL from source for manylinux2014;
     the riscv64 override installed `openssl-devel` via `before-all` to skip that, but
     upstream's still-present `before-build` then `yum remove`d it again and tried the
     source build anyway (failing separately on missing `perl-FindBin`, gotcha 46).
     Both jobs looked like they ran (the openssl-devel install step's log was right
     there) which made the real cause — the wrong hook name — easy to miss.
     - **Read which key upstream's `[tool.cibuildwheel.linux]` table actually sets**
       before choosing which `CIBW_*_LINUX` var to override; `before-all` runs once per
       container, `before-build` once per interpreter, and only the matching one
       replaces upstream's list.
     - When in doubt, grep the job log for upstream's own command line (here,
       `install_openssl.sh`) — if it's still present after your override step, you
       overrode the wrong hook, not the right one with a bug in it.

227. **A build that touches `PyObject` internals directly (`ob_refcnt`, `ob_type`,
     etc.) instead of through the stable/limited API fails to *compile* under
     free-threaded Python, and the failure is identical on every architecture — trim
     the matrix, don't patch around it (the uamqp case).** Several of uamqp's `.pyx`
     files read `context_pyobj.ob_refcnt == 0` inside a C callback to guess whether the
     Python-side context object is mid-garbage-collection before touching it. Free-threaded
     builds replace `PyObject`'s single `ob_refcnt` field with a different
     layout (per-thread local/shared reference counts), so the field plain doesn't exist
     and the cp314t build fails at `gcc: error: 'PyObject' {aka 'struct _object'} has no
     member named 'ob_refcnt'` — a compile error, not a runtime one, so it can't be
     waved off with `CIBW_TEST_SKIP` the way gotcha 216's coverage gaps can.
     - **Check whether upstream ships a cp314/cp314t wheel at all before assuming this
       needs a patch.** uamqp's own PyPI releases stop at cp313 — nobody has hit this
       upstream because nobody has built it free-threaded yet. Dropping `cp314t` from
       the matrix (keeping `cp312`/`cp313`/`cp314`, all of which built and passed tests
       clean) mirrors upstream's own supported set rather than inventing support they
       don't have.
     - **This is a real correctness gap, not a riscv64 build quirk** — the same source
       would fail identically compiling cp314t on x86_64/aarch64. Reaching for the
       pattern of gotcha 26 (bump the toolchain) or 107/226 (fix `CFLAGS`) doesn't apply;
       there's no flag that makes a nonexistent struct member exist.

245. **In a matrix job that downloads a sdist artifact and separately checks out
     something else (e.g. a test file `pull_request` excludes from the sdist),
     `actions/checkout` must run *before* `actions/download-artifact` — its default
     `clean: true` runs `git clean -ffdx` on the whole `$GITHUB_WORKSPACE`, not just
     repo-tracked paths, and deletes anything already sitting there (the quickjs
     case).** A `build_wheels` job downloaded `quickjs-<ver>-sdist` into `dist/`, then
     ran `actions/checkout` with `sparse-checkout: test_quickjs.py` to fetch a test file
     that upstream's own `MANIFEST.in` excludes from the sdist. The download-artifact
     log showed `Artifact download completed successfully`; the very next step's log
     showed `Deleting the contents of '/home/runner/work/<repo>/<repo>'` — checkout's
     clean step doesn't know or care that `dist/quickjs-*.tar.gz` came from a different
     action, so it wiped it. Every downstream job then died at
     `cibuildwheel`'s `TarFile.open(package_dir)` with `FileNotFoundError`, while the
     consumer's own log showed nothing wrong beyond the missing file — the real cause
     was one step earlier, in the same job, not in the sdist-producing job at all.
     Fix is pure step reordering: checkout (which starts from an empty workspace on a
     matrix runner and cleans nothing that matters) first, artifact download second.
     The download-artifact action's own settings echo, `digest-mismatch: error`, is
     just a config default logged on every run — it is not evidence of what actually
     failed and shouldn't be chased as a lead.

247. **A folded `>-` scalar's `python -c "` on its own line puts a leading space inside
     the script — cp3.9-3.13 reject it with `IndentationError`, but cp3.14+ silently
     tolerates it, so the *same* broken YAML looks fine on one matrix leg and fails on
     another (the ua-parser-rs case).** Unlike gotcha 93 (a *deeper*-indented
     continuation line keeping its literal `\n`), this bites when every line sits at the
     *same* indent, which is exactly what folds correctly per the YAML spec:
     ```yaml
     CIBW_TEST_COMMAND: >-
       python -c "
       import foo;
       assert foo.__file__.endswith('.so')" &&
       python -m pytest
     ```
     folds the newline after the opening `"` into a single space, so the resolved
     command is `python -c " import foo; assert ...` — a lone leading space before the
     first statement. `python -c " import sys"` raises `IndentationError: unexpected
     indent` on 3.9 through 3.13 (verified on both), because `-c` source isn't
     dedented before tokenizing. CPython 3.14's tokenizer no longer treats that leading
     space as significant, so the identical string runs to completion there — a
     cp310-abi3 leg (tested down to its floor interpreter, gotcha 96) died on a syntax
     error while the cp314t leg ran the actual test body and hit a *different*,
     legitimate assertion failure, making the two failures look unrelated when they
     shared one root cause. Fix: keep the first statement on the same source line as the
     opening quote (`python -c "import foo;` — no line break before `import`); every
     later `;`-joined statement can still start its own line, since folding a newline
     *between* two already-`;`-terminated statements is harmless.
     - **Resolve the YAML and read the string back, not the source** — gotcha 93's
       `yaml.safe_load(...)['env']['CIBW_TEST_COMMAND']` check catches this too; a
       `repr()` of the resolved value shows the stray leading space directly (`'python
       -c "import foo...'` vs the broken `'python -c " import foo...'`).
     - **A syntax error on the older interpreter and a clean run to a real assertion on
       cp314t in the same matrix is the tell** — don't debug them as two unrelated
       failures (one YAML/syntax, one logic) when the log for the younger interpreter's
       job still shows the identical malformed one-liner.

251. **When `package-dir` is a `.tar.gz`, cibuildwheel extracts it to a temp dir and
     `chdir`s the whole build into it — so `CIBW_TEST_SOURCES` (resolved against
     `Path.cwd()`, gotcha 104) can never see a sibling file staged next to the sdist
     in `$GITHUB_WORKSPACE` (the quickjs case).** `cibuildwheel/__main__.py` special-cases
     a package-dir ending in `tar.gz`: it extracts the archive to `mkdtemp(prefix=
     "cibw-sdist-")`, sets that as the new `package_dir`, and runs the entire
     `build_in_directory(args)` call inside `with contextlib.chdir(project_dir):`. Every
     later `Path.cwd()` call for the rest of the build — including
     `platforms/linux.py`'s `copy_test_sources(test_sources, Path.cwd(), test_cwd, ...)`
     — now resolves against that temp extraction, not the directory cibuildwheel was
     launched from. A workflow that downloads a built sdist tarball as `package-dir` and
     separately checks out a test file that the sdist deliberately excludes (gotcha 245's
     same shape) builds the wheel successfully and only fails minutes later, deep in the
     "Testing wheel" phase, with `cibuildwheel: Test source test_quickjs.py does not
     exist.` — a bare-tarball `package-dir` is not equivalent to a directory one for
     `CIBW_TEST_SOURCES` purposes, even though both work identically for the build step.
     - **Fix by extracting the sdist yourself and pointing `package-dir` at the
       resulting directory** (`tar zxf dist/<name>.tar.gz -C dist` then `package-dir:
       dist/<name>-<version>`), matching `build-lightgbm.yml`'s existing pattern — with
       a real directory, `args.package_dir.is_file()` is false and the name doesn't end
       `tar.gz`, so cibuildwheel calls `build_in_directory(args)` directly with no
       `chdir`, and `Path.cwd()` stays at the workspace root for the whole run.
     - **Read `cibuildwheel/__main__.py`'s own dispatch, not just `platforms/linux.py`**,
       when a `test-sources` failure doesn't match gotcha 104's directory-package-dir
       story — the `chdir` happens one layer up, before either platform module runs, and
       nothing in `platforms/linux.py` alone explains it.

262. **Gotcha 201's vendoring step is only needed when the sibling sources are
     *generated or gitignored* — a monorepo subdirectory whose build script reaches
     outside itself for sources that are ordinary, git-tracked files needs no extra
     step at all (the capstone case; see `build-capstone.yml`).** capstone's
     `bindings/python/setup.py` computes `BUILD_DIR = ROOT_DIR/../..` (two levels up
     from `package-dir`) whenever `bindings/python/src` doesn't already exist, and
     builds the vendored C library from there via `CAPSTONE_BUILD_CORE_ONLY=yes bash
     ./make.sh`. That looks exactly like gotcha 201's grpcio-tools shape — a
     `package-dir` pointing into a monorepo, with the actual build reaching outside it
     — but grpcio-tools needed a host-side `run:` step first because its sibling trees
     (`third_party/protobuf`, `third_party/abseil-cpp`) are gitignored and only appear
     after `make_grpcio_tools.py` copies them in. capstone's `arch/`, `include/`, and
     `Makefile` are ordinary files checked into the repo root, so an unmodified
     `actions/checkout` (no `path:`, matching the checkout convention every
     build-from-checkout workflow already uses) leaves them sitting right where
     `../..` expects them — `package-dir: bindings/python` passed straight to
     `pypa/cibuildwheel`, no vendoring step, reproduced upstream's own
     `python-publish-release.yml` line for line. **The question that decides which
     case you're in: `git status --ignored` (or just `ls`) the sibling path the build
     script reaches for.** Present and tracked → nothing to do; absent or gitignored
     → gotcha 201's pre-build `run:` step is what's missing.

270. **Gotcha 134's "leaked `Py`-prefixed symbol" failure has a real fix, not just
     `CIBW_AUDIT_COMMAND: ''`, when the flagged names are internal helpers used only
     within their own translation unit (the libsass case; see `build-libsass.yml`).**
     libsass-python's `_sass.c` defines `PySass_make_enum_dict()` and
     `PySass_init_module()` at file scope with no `static` keyword, so they get
     external linkage and land in the `.abi3.so`'s ELF `.dynsym` with `GLOBAL`
     binding; abi3audit's by-name check (gotcha 134) flags both as `not ABI3` because
     neither is on the stable-ABI symbol list, even though only `PyInit__sass` is
     ever meant to be an entry point. Unlike awscrt's 17 API-shaped names woven
     through the project (where disabling the audit was the honest call), both
     libsass symbols are called exclusively from the same file that defines them
     (`grep -rn PySass_make_enum_dict\|PySass_init_module` across the checkout turns
     up only `_sass.c`) — textbook internal linkage that upstream simply never
     declared. A one-line patch (`PyObject* PySass_make_enum_dict()` →
     `static PyObject* PySass_make_enum_dict()`, same for `PySass_init_module`)
     removes both from `.dynsym` entirely: `nm -D _sass.abi3.so | grep PySass` finds
     them before the patch and finds nothing after, and `abi3audit --strict` goes
     from 2 violations to 0 on the same build. **Before reaching for `static`, confirm
     every call site is in-file** — a symbol referenced from another translation unit
     in the same extension needs `__attribute__((visibility("hidden")))` or a linker
     version script instead, since `static` there would break the build; a symbol
     genuinely needed across many files (awscrt's shape) is when disabling the audit
     is the more honest fix. Verifying the fix does not need riscv64 or even the
     manylinux image: an ordinary Linux container with `build-essential` reproduces
     the identical ELF-level symptom (gcc plain-C linkage, the actual path this
     project's `setup.py` takes on Linux — the Darwin/BSD branch of the same file
     forces the C++ compiler and mangles both names, which hides the leak entirely
     and makes macOS a false-negative host for this specific check).

281. **Gotcha 251 recurs even when the port's own notes cite gotcha 104 — a
     `build_sdist` job's tarball artifact, downloaded and handed straight to
     `package-dir` in the `build_wheels` job, is still a `.tar.gz` (the biotite
     case; see `build-biotite.yml`).** biotite's sdist->bdist split follows gotcha
     104's shape correctly — `build_wheels` checks the tag out at the workspace root
     so `CIBW_TEST_SOURCES: tests benchmarks pyproject.toml` has something to stage —
     but `package-dir: dist/${{ needs.build_sdist.outputs.sdist_name }}` still points
     straight at the downloaded `.tar.gz`, not a directory. The build phase never
     notices (gotcha 251's "both work identically for the build step"); the wheel
     compiles and installs fine on all three interpreters, and the job dies 40-50
     minutes later, deep in "Testing wheel", with `cibuildwheel: Test source tests
     does not exist.` — the same message and the same `chdir`-into-the-extracted-
     sdist root cause as the quickjs case gotcha 251 already documents, just reached
     through a different workflow shape (an artifact download standing in for
     quickjs's local tarball). **Citing gotcha 104 for the re-checkout half of the
     fix is not enough — a `package-dir` ending in a downloaded sdist filename needs
     a second look through gotcha 251's lens specifically**, because 104 explains why
     the checkout-at-root trick works at all and says nothing about what `package-dir`
     itself must be shaped like. Fix is identical to 251's: add a step that extracts
     the tarball (`tar zxf "dist/${sdist_name}" -C dist`) and change `package-dir` to
     the resulting `dist/<pkg>-<version>` directory, matching `build-lightgbm.yml`.
     - **The two failure sites look the same on the surface (`Test source <path> does
       not exist`) but the fix differs by why the path is missing** — gotcha 251's
       root shape is "nothing was ever staged into the wrong place" (`Path.cwd()` is a
       temp dir with nothing beside it); a partially-correct port like this one instead
       staged the tests fine at the *real* workspace root and still fails, because
       cibuildwheel's own `chdir` (not the workflow) moved `Path.cwd()` out from under
       them. Don't stop debugging at "did the checkout step run" — confirm which
       directory `copy_test_sources` actually resolved against before concluding the
       staging step itself is broken.

313. **When `setup.py` computes `py_limited_api` from the *building* interpreter itself
     (not a fixed constant), gotcha 96's "build on the oldest claimed interpreter" risk
     does not apply — the tag always matches whichever interpreter you choose, so pick
     your own floor freely (the onigurumacffi case).** Gotchas 34/96 cover a project that
     hardcodes one abi3 floor in `setup.py` (`py_limited_api='cp37'`) or via Cargo/pyproject
     — build on the OLDEST interpreter the fixed tag claims, or older callers get a broken
     wheel (gotcha 96). onigurumacffi's `bdist_wheel` override instead does
     `self.py_limited_api = f'cp3{sys.version_info[1]}'`: whatever CPython runs the build
     becomes the tag (`cp312-abi3` if built under 3.12, `cp313-abi3` if built under 3.13),
     same shape as brotlicffi's `cp39-abi3`. There is no "upstream's floor" to discover or
     respect here — since the tag is self-consistent by construction, any interpreter you
     build with produces a wheel that is honest about its own floor. Treat it exactly like
     gotcha 11's fixed-floor collapse: put `CIBW_BUILD` entries for the repo's *own* minimum
     interpreter (`cp312`) first plus the newer ones (`cp313`, `cp314`), and cibuildwheel
     builds once on `cp312` and reuses+retests that wheel via `find_compatible_wheel` — do
     not build separately on `cp313`/`cp314`, which would just produce redundant
     `cp313-abi3`/`cp314-abi3` wheels. Free-threaded builds need their own job regardless:
     the override is commonly guarded with `sysconfig.get_config_var('Py_GIL_DISABLED')`,
     so `cp314t` silently falls back to a plain per-interpreter wheel outside the collapse.
     - **A cffi/setuptools project vendoring a C library with no source in the checkout at
       all** (unlike gotcha 32/53's statically-linked case) **can often skip
       `autogen.sh`/autoreconf entirely by fetching the upstream project's official GitHub
       *Release* tarball instead of a git clone or tag archive** — a `make dist` release
       tarball (oniguruma's `onig-<ver>.tar.gz`, distinct from GitHub's auto-generated
       `archive/vX.Y.Z.tar.gz`) ships a pre-generated `./configure`, so
       `CIBW_BEFORE_ALL_LINUX` only needs `curl` + `sha256sum -c` + `./configure && make
       install` — no libtool/autoconf version questions (contrast build-cffi.yml's libffi
       step, which clones a tag archive and needs `autogen.sh`). Confirm before writing the
       step: `tar tzf <tarball> | grep -x '<dir>/configure'`.

324. **`{project}` (gotcha 5) is *exactly* the on-disk root of whatever checkout has no
     `path:` — copying another port's `cd {project}/foo/foo`-style sibling-directory path
     into a differently-shaped monorepo silently breaks it (the mecab case).** mecab-python3
     (PR #1117) has no native sources of its own, so its `CIBW_BEFORE_ALL_LINUX`
     `git clone`s the *separate* taku910/mecab repo into a scratch `/tmp/mecab`, whose own
     top-level layout nests the C library one level down — `/tmp/mecab/mecab`. Porting the
     plain `mecab` package (shogo82148/mecab, a *monorepo* checked out directly at the
     workspace root with `repository: shogo82148/mecab` and no `path:`) by copying that
     `cd {project}/mecab/mecab` pattern verbatim fails: this repo's own top-level `mecab/`
     dir already *is* the C library (`mecab/configure.ac`, `mecab/src`, `mecab/python`), so
     the right path is `cd {project}/mecab` — one level, not two. Symptom: cibuildwheel's own
     `Copying project into container...` step succeeds (fast, no error) because the whole
     checkout genuinely is present under `{project}`; the failure comes seconds later from
     the shell itself — `sh: line N: cd: {project}/foo/foo: No such file or directory`,
     `cibuildwheel: Command [...] failed with code 1` — a red herring that looks like a
     `{project}` mounting bug (it isn't; gotcha 5's mapping is exact) when it is really a
     wrong assumption about a *different* repo's directory depth carried over verbatim.
     **Don't guess the layout from a sibling port's precedent when the checkout shape
     differs — spend one CI cycle on a throwaway `find {project} -maxdepth 2` (or
     `ls -la {project}`) in `CIBW_BEFORE_ALL_LINUX` to see the real tree**, then delete the
     diagnostic once the real path is confirmed.

331. **A platform-specific `[tool.cibuildwheel.<platform>].environment` table already
     replaces the global `[tool.cibuildwheel].environment` table on that platform, with no
     env var needed to trigger it (refines gotcha 107; the ansible-pylibssh case; see
     `build-ansible-pylibssh.yml`).** Gotcha 107 says `CIBW_ENVIRONMENT` replaces upstream's
     `environment` table rather than merging into it. The same replace-not-merge rule
     already applies *before* any env var is read: cibuildwheel's `_resolve_cascade`
     (`options.py`) walks `default → default_platform → config (global table) → config_platform
     (the platform-specific table) → overrides → CIBW_ENVIRONMENT → CIBW_ENVIRONMENT_<PLATFORM>`
     and each non-null step **fully replaces** the running value unless that step's `inherit`
     rule is APPEND/PREPEND — which a plain `[tool.cibuildwheel.linux.environment]` table
     never carries (only a `[[tool.cibuildwheel.overrides]]` entry can opt into that). So a
     project whose Linux table sets a couple of build-only keys (ansible-pylibssh's
     `STATIC_DEPS_DIR`/`CFLAGS`/`LDFLAGS`, pointing at its own custom manylinux images) has
     *already* dropped every key from its global table on Linux — `PIP_CONSTRAINT`, colour
     toggles, whatever else — with no port-added `CIBW_ENVIRONMENT*` involved at all. Two
     consequences: (1) don't assume a global-table value (e.g. a version pin) still applies
     on a platform that has its own table — check `pyproject.toml` for a
     `[tool.cibuildwheel.<platform>]` section before relying on the global one; (2) setting
     `CIBW_ENVIRONMENT_LINUX` yourself to replace an unusable platform table (as
     ansible-pylibssh does, to drop `STATIC_DEPS_DIR` paths that don't exist in the riscv64
     container) costs nothing extra beyond what the platform table had already cost —
     nothing from the global table survives to lose.

356. **A pybind11 3.x CMake build can silently target the wrong Python on cp314t —
     `find_package(Python ...)` ignores a `setup.py`'s legacy `-DPYTHON_EXECUTABLE` hint, and
     free-threaded is the one build where that goes unnoticed until import, not configure
     (the kaldi-native-fbank case; see `build-kaldi-native-fbank.yml`).**
     `cmake/cmake_extension.py` passes `-DPYTHON_EXECUTABLE={sys.executable}` (the
     pre-modern `FindPythonInterp` variable name) into its own `cmake`+`make install`
     invocation; pybind11 3.0.0's CMake has moved entirely to `find_package(Python ...)`,
     which reads `Python_EXECUTABLE` (capital P) and silently drops the old name instead of
     erroring. On cp312/cp313/cp314 this goes unnoticed because CMake's own PATH/venv search
     happens to land on the right interpreter anyway; on cp314t it instead resolved an
     unrelated `/usr/local/bin/python3.15` present in the manylinux_riscv64 image, configured
     pybind11 against it, and linked `_kaldi_native_fbank.cpython-315-riscv64-linux-gnu.so` —
     a file the actual cp314t interpreter can never import. The job "succeeds" through
     `make install` and wheel repair; only cibuildwheel's own test phase catches it, with
     `ModuleNotFoundError: No module named '_kaldi_native_fbank'` on every test file, which
     reads like a packaging bug rather than the real ABI mismatch.
     - **Confirm from the configure log, not from the import failure alone**: grep for
       `-- Found Python:` and compare the reported path/version against the interpreter
       cibuildwheel actually selected for that matrix entry — a path outside the build venv,
       or a version one above the target, is the tell.
     - **Fix through the project's own override, no patch needed, when one exists**:
       kaldi-native-fbank's `cmake_extension.py` reads `KALDI_NATIVE_FBANK_CMAKE_ARGS` from
       the environment and skips its own `-DPYTHON_EXECUTABLE=`/`-DCMAKE_BUILD_TYPE=Release`
       defaults whenever that var is set at all, so the replacement has to repeat both:
       `CIBW_ENVIRONMENT: KALDI_NATIVE_FBANK_CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release
       -DPython_EXECUTABLE=$(command -v python)"`. A project with no such env-var escape
       hatch needs the same `-DPython_EXECUTABLE=` flag added as a patch instead.
     - **Not inherently free-threading-specific** — any `setup.py` still speaking the legacy
       `PYTHON_EXECUTABLE` name to a modern-CMake pybind11/nanobind build could hit this on
       any interpreter if a same-or-higher-versioned Python happens to be independently
       discoverable; cp314t is just where it surfaced here, because the image's bundled
       Python outranked every GIL-ful target's own version but not (correctly) itself.

360. **A `setup.py`'s own `bdist_wheel --plat-name` insertion can hardcode `manylinux1_` +
    `platform.machine()` regardless of the actual container libc, making musllinux
    unbuildable no matter how the CMake/C++ side is patched (the keystone-engine case).**
    Gotcha 34 covers a project's own `--plat-name` insertion as a *matrix-collapsing*
    device; this is the same mechanism causing a *matrix-shrinking* failure instead.
    keystone-engine's setup.py — written before musllinux (PEP 656) existed — does
    `if 'linux' in get_platform(): sys.argv.insert(idx+1, 'manylinux1_' +
    platform.machine())` unconditionally, so the wheel it hands to `auditwheel repair`
    is always named `..._manylinux1_riscv64.whl`, even when the actual build ran inside
    the musllinux image and produced a musl-linked `.so`. `auditwheel repair` trusts the
    filename's plat tag as the *source* libc family, not the binary's actual linkage, and
    refuses outright: `error: can't repair wheel ..._manylinux1_riscv64.whl with GLIBC
    libc to a wheel targeting MUSL` — a red herring that reads like a real glibc/musl
    toolchain mismatch but isn't one; the C++ build itself is unaffected and correctly
    musl-linked.
    - **Check whether a same-author sibling project already carries the fix before
      writing a patch.** capstone-engine (keystone-engine's own sibling, same maintainer,
      near-identical `bindings/python/setup.py` history) fixed this exact bug upstream
      (capstone#2445) by dropping the hardcoded `manylinux1_` prefix entirely and just
      using `get_platform().replace('.', '_').replace('-', '_')` — i.e. `linux_riscv64`,
      a libc-neutral tag `auditwheel repair` can freely retarget to either family. A
      pinned older release that predates a sibling's fix can't take it via upgrade, and
      backporting the one-line diff via `patches/<pkg>/<version>/` is an option — but
      dropping musllinux from the matrix entirely (matching upstream's own CI, which for
      keystone-engine never built musllinux either — see gotcha 34's "the default four"
      logic) is the lower-risk, upstream-faithful choice when this is caught on the first
      port rather than treated as a regression to fix.

391. **A project's real cibuildwheel recipe can live in a *separate packaging repo* that
    the source tree never references — the source repo can carry no GitHub Actions at all
    (the cassandra-driver case).** `pyproject.toml` has no `[tool.cibuildwheel]` table, the
    release tag has no `.github/` directory, and the only CI file is a `Jenkinsfile` that
    builds no wheel (it is the CCM/DSE integration matrix, installing the driver
    `--editable`). Read only the source repo and the port looks like it has no upstream
    recipe to mirror, which is how a workflow ends up invented from scratch — exactly the
    divergence goal 2 forbids. Here it was `datastax/python-driver-wheels`, a `multibuild`
    repo carrying the driver as a git submodule, named once in `README-dev.rst`'s release
    checklist ("Update the `python-driver` submodule of `python-driver-wheels` … Trigger
    the Github Actions necessary to build wheels"); its `build_wheels_linux.yml` holds the
    whole recipe — `CIBW_BUILD`, `CIBW_SKIP`, `CIBW_BEFORE_ALL`, `CIBW_ENVIRONMENT` and the
    `CIBW_TEST_*` set.
    - **Where to look, in order**: the developer/release doc (`README-dev`,
      `CONTRIBUTING`, `RELEASING`) for the name of a wheels/packaging repo; then that
      repo's `.github/workflows/`; then its `config.sh`/`build_wheel.sh` if it is a
      `multibuild` project — the pre-cibuildwheel hooks (`pre_build`, `run_tests`) often
      still hold the *real* wheel-verification script that the cibuildwheel workflow later
      replaced with a stub, which is the gotcha 94 answer for that package handed over
      ready-made.
    - Distinct from gotcha 338: there the packaging fork *is* where the released wheels
      come from and it drags in a sibling dependency of its own; here the packaging repo is
      upstream's and only holds the recipe, so the port still builds the source tag.

396. **A `cpXY-none-<platform>` wheel is the third plat-name shape: `setup.py` declares no
    `ext_modules` at all, and a sibling CMake build both compiles the extension modules and
    hands `bdist_wheel` the tag (the coremltools case; see `build-coremltools.yml`).**
    Gotcha 27 reads `py3-none-<platform>` as "the platform half was forced by hand, nothing
    is compiled"; gotcha 81 adds the ctypes-payload exception. Neither covers a wheel tagged
    `cpXY-**none**-<platform>` — an interpreter tag with no ABI tag — which is what you get
    when the compiled modules are real, per-interpreter pybind11 `.so`s, but setuptools never
    sees them: coremltools' `setup.py` has zero `ext_modules` and ships
    `libmilstoragepython.so`/`libmodelpackage.so` through `package_data` globs, while
    `CMakeLists.txt` builds them and then invokes `setup.py bdist_wheel
    --plat-name=<plat> --python-tag=cp${MAJOR}${MINOR}` itself. Read the interpreter half
    before concluding anything from the missing ABI tag: `cpXY-none` means per-interpreter
    content that setuptools was not told about, whereas gotcha 27's `py3-none` means no
    per-interpreter content at all.
    - **The architecture of the whole wheel is then one string in the build system, not a
      `platform.machine()` call.** Gotcha 360's keystone-engine case at least interpolated
      the real machine; coremltools' CMakeLists is `elseif(... MATCHES "Linux")
      set(PLAT_NAME "manylinux1_x86_64")` — a literal, so a riscv64 build silently produces
      an x86_64-tagged wheel that installs on the wrong machine. Grep the build system for
      `plat-name`/`plat_name`, not just `setup.py`, whenever `setup.py` has no `ext_modules`
      but the released wheels carry a platform tag.
    - **Patch it to a libc-neutral `linux_<arch>` and let `auditwheel repair` retag**, the
      same resolution gotcha 360 points at, and keep the existing x86_64 branch byte for
      byte so the diff is upstreamable: `if(${CMAKE_SYSTEM_PROCESSOR} MATCHES "x86_64")` →
      the old literal, `else()` → `linux_${CMAKE_SYSTEM_PROCESSOR}`.
    - **cibuildwheel is the wrong tool for this shape.** It drives a PEP 517 build, which
      here would run `setup.py` on its own and emit a `py3-none-any` wheel containing
      riscv64 `.so`s — worse than a wrong platform tag. Drive the container yourself
      (gotcha 15) and run the project's own `dist` target.

402. **A two-leg abi3 + free-threaded matrix expressed only through `include:` collapses
    into a *single* job, and the abi3 wheel is never built (the primp/arro3-core case).**
    The idiom several workflows here use is a base matrix of just
    `version: ${{ fromJSON(needs.setup.outputs.versions) }}` plus two `include:` objects
    that each introduce the same brand-new keys (`tag`, `build`, `features`). GitHub only
    *adds* an include object's keys to the existing combinations when none of them
    overwrites an **original** matrix value — `tag` is not an original key, so the first
    include adds `tag: cpNN-abi3` to the one combination and the second overwrites it with
    `tag: cp314t`. One job runs, the free-threaded wheel publishes, and nothing fails: the
    abi3 leg simply does not exist. `build-primp.yml` shipped only
    `primp-2.0.0-cp314-cp314t` and `primp-2.0.1-cp314-cp314t` that way (run 35310255186
    has exactly two build jobs, both `cp314t-manylinux_riscv64`), and
    `build-arro3-core.yml` did the same for 0.8.2 after publishing both wheels for 0.8.1.
    - **Fix: make the leg a real matrix dimension**, so each include *updates* the
      matching combination instead of adding a key:
      ```yaml
      matrix:
        version: ${{ fromJSON(needs.setup.outputs.versions) }}
        tag: [cp310-abi3, cp314t]
        include:
          - tag: cp310-abi3
            build: cp312-manylinux_riscv64 cp313-manylinux_riscv64
            features: --features abi3-py310
          - tag: cp314t
            build: cp314t-manylinux_riscv64
            features: ''
      ```
    - **A single `include:` object is safe** (`build-css-inline.yml`): the collapse needs
      two entries competing for the same new key. It is also why this only became latent
      when the `version` vector replaced the older per-interpreter base vector — with
      `python:` or `tag:` in the base matrix the includes only ever *updated* legs.
    - **Diagnose it from the job list, not the log**: count the `Build <pkg> <ver>
      <tag>-manylinux_riscv64` jobs against the legs declared before believing a green
      run. `docs/packages/<pkg>.yaml` is the after-the-fact tell — a published version
      carrying only the free-threaded wheel where an earlier version carried both.
    - **It is not an abi3/free-threading shape, it is any include-only leg set.**
      `build-grain.yml` expressed a plain per-interpreter set that way —
      `include: [{tag: cp312, python: '3.12'}, {tag: cp313, ...}, {tag: cp314, ...}]`
      over a `version`-only base — and PR #2124's run 35492217884 went green with one
      build job, `Build grain 0.2.18 cp314-manylinux_riscv64`, no cp312/cp313 wheel at
      all. It was copied from `build-array-record.yml`, which carries the same three
      entries (0.8.3 shipped all three wheels from the older base matrix, so the loss
      only shows on its next rebuild).
    - **The rule that decides it**: an include entry that keys on *no* real dimension
      attaches to every base combination, so two such entries sharing a key overwrite
      each other; an entry that keys on a real dimension only updates the combinations
      it matches, which is the correct use (`build-lz4.yml`'s `- python: "cp314t"` over
      `python: ["cp312", "cp313", "cp314", "cp314t"]` — all four wheels published).
    - **It is repo-wide, not a two-package slip**: applying that rule to every
      `.github/workflows/*.yml` flags 58 jobs whose declared legs collapse into one
      (2 to 5 legs each, `build`/`tag`/`python`/`features`/`test_requires` the usual
      shared keys). Already visible on the registry: `protobuf-py-ext` 0.4.0/0.5.0 and
      `primp` 2.0.0/2.0.1 and `arro3-core` 0.8.2/0.8.3 carry only their cp314t wheel,
      and `rigour` 2.5.0 carries only cp314 where 2.4.1 carried five. Fix the workflow
      you are touching; the rest need a sweep of their own.
    - **`docs/packages/rfc3161-client.yaml` dates the regression in situ**, which is the
      cheapest way to show a reviewer it is the `version` vector and not the package:
      1.0.8, built before commit e7b2b20a74 replaced the per-interpreter base vector,
      carries both `cp39-abi3` and `cp314t` wheels; 1.0.9, built after, carries only
      `cp314t`. Same workflow file, same crate, one wheel lost to a refactor.
    - **The 58 are also the natural *templates*, so the bug reproduces into new ports.**
      An abi3 + free-threaded maturin port has no better starting point than
      `build-rfc3161-client.yml` / `build-semantic-text-splitter.yml` / `build-primp.yml`,
      and copying any of them carries the collapse in — kernels-data 0.16.1 did exactly
      that and its first run was green with one `cp314t` job. Copy the *matrix shape* from
      a workflow on the safe list instead (`build-datafusion.yml`, `build-grain.yml`,
      `build-lz4.yml`), and check the shape of whatever you copy: `python3 -c` over the
      YAML, comparing the `include:` entries' keys against the base matrix's, answers it
      before the first push. Then count the build jobs in run 1 rather than reading the
      conclusion — a collapsed matrix never fails.

408. **A `setup.py` that reaches for `wheel.bdist_wheel` behind a `try/except ImportError`
     still gets its abi3 tag under modern setuptools — do not "fix" it by adding `wheel`
     to `build-system.requires` (the leidenalg case).** Gotcha 34's third abi3 route is a
     `bdist_wheel` subclass defined in `setup.py`; a common variant guards the import
     (`try: from wheel.bdist_wheel import bdist_wheel / except ImportError: bdist_wheel =
     None`) and then *silently* drops to a per-interpreter wheel when the import fails.
     Since setuptools 70.1 `wheel` is no longer returned by
     `setuptools.build_meta.get_requires_for_build_wheel()`, so the PEP 517 isolated env
     built from `requires = ["setuptools>=45", "setuptools_scm[toml]>=6.2"]` installs no
     `wheel` distribution at all — which reads like a guaranteed silent abi3 loss and
     invites a pyproject patch (plus gotcha 31's `SETUPTOOLS_SCM_PRETEND_VERSION` fallout
     for the dirtied tree). It is not: setuptools still ships a `wheel.bdist_wheel` shim
     re-exporting `setuptools.command.bdist_wheel`, so the guarded import resolves and the
     subclass is installed.
     - **Settle it in one minute on any host, no target arch involved**: a throwaway
       project with the same `build-system.requires` and a `setup.py` that prints the
       import result, built with `python -m build --wheel`, prints
       `<class 'setuptools.command.bdist_wheel.bdist_wheel'>` (setuptools 84). Do this
       *before* writing a patch — the wheel filename from the real build is the other
       proof, and a `cpNN-abi3` tag means the path is live.
     - **Re-check it when the shim goes away.** It is a compatibility shim, so the negative
       outcome (a `cpNN-cpNN` wheel from a project whose PyPI files are `cpNN-abi3`) is the
       signal to revisit; the fix then is upstream's pyproject, not a cibuildwheel knob,
       because `CIBW_CONFIG_SETTINGS` cannot reach a `cmdclass` that was never registered.

468. **An upstream `[tool.cibuildwheel] build` glob of `cp3??-*` excludes every
     free-threaded interpreter by *character count*, so the project ships no `cp3NNt`
     wheel even though nothing in its config mentions free-threading — and if its
     `setup.py` sets `py_limited_api` unconditionally, adding this repo's default
     `cp314t` leg would ship a mislabelled wheel (the qiskit case).** Gotcha 34's
     `setup.py`-side abi3 form is normally guarded with
     `if not sysconfig.get_config_var('Py_GIL_DISABLED')`, and gotcha 107's spaCy note
     covers the *explicit* exclusion (`skip = ["cp3??t-*"]`). Qiskit 2.5.2 has neither:
     `setup.py` does a bare `options={"bdist_wheel": {"py_limited_api": "cp310"}}`, and
     the only selector is `build = ["cp3??-*"]` — five characters after `cp`, which
     `cp310`…`cp315` match and the six-character `cp314t` cannot. The exclusion is
     invisible in `skip`, and PyPI confirms it: one `cp310-abi3` wheel per platform and
     no free-threaded wheel anywhere. Adding a `cp314t` leg would not merely diverge
     from upstream, it would tag a `Py_GIL_DISABLED` build `cp310-abi3`.
     - **Count the `?`s in `build`/`skip` before inferring the free-threading story from
       either.** `cp3??-*` and `cp3??t-*` differ by one character and mean opposite
       things about which of the two upstream wrote down. Settle it in seconds on any
       host, against upstream's unmodified config:
       `cibuildwheel --platform linux --archs riscv64 --print-build-identifiers` printed
       `cp310`…`cp315-manylinux_riscv64` and no `t` tag. Free-threading is no longer an
       `--enable` group in cibuildwheel 4.x (that name now errors), so a missing `cp3NNt`
       identifier is the glob's doing, not a disabled group.
     - **The same glob makes the abi3 floor mandatory rather than chosen** (gotcha 96):
       `cp310` is the first identifier the glob matches, and it is also the only
       interpreter the fixed `py_limited_api="cp310"` tag may be compiled against.

469. **An abi3 build *tests* on its floor interpreter, so a package that uses a
     newer-Python-only API fails our CI while upstream's own CI stays green (the
     oai-statsig-python-core `co_qualname` case).** Gotcha 96 is about the *wheel* being
     broken on interpreters older than the one it was compiled on; this is the mirror
     image, and no compiler is involved — the wheel is fine, and it is the project's
     **own Python code** that cannot run on the oldest interpreter it claims. A
     `pyo3/abi3-py310` project built with `only: cp310-manylinux_riscv64` has cibuildwheel
     build *and run the whole test suite* under CPython 3.10, the floor of the abi3 range,
     which is very often older than anything upstream tests on.
     oai-statsig-python-core 0.29.0 reads `frame.f_code.co_qualname` in a pure-Python
     exposure-callsite walk; `code.co_qualname` exists only from CPython 3.11, while the
     package declares `requires-python >= 3.10` and ships exactly one `cp310-abi3` wheel.
     Upstream's CI runs 3.12/3.13, so the bug shipped.
     - **The symptom names the wrong layer.** Two tests failed because callsite metadata
       came back `"unknown"`, preceded on stdout by `Statsig SDK Error (Python Bindings):
       _find_exposure_callsite 'code' object has no attribute 'co_qualname'`. "Python
       Bindings" plus a PyO3 package invites a hunt through the Rust crate for a
       version-gated C-API call; the culprit was six lines of Python in `py_src/`.
       `grep -rn <attribute>` the unpacked sdist before theorising, and when a failure
       names a *missing attribute on a builtin object*, look up the version it was added
       in and compare that against the interpreter the job actually runs — not the one you
       rehearsed on.
     - **A broad `except` turns it into a silent wrong answer instead of a crash.** The SDK
       wraps every method in an error boundary that prints the exception and returns
       `None`, so the `AttributeError` became a fallback value plus a stdout warning. Only
       the assertion failed; nothing in the log mentioned 3.10, and `--reruns 3` did not
       move it — deterministic, not flaky.
     - **Rehearse on the abi3 floor, not your host's default interpreter.** This port's
       x86_64 rehearsal ran cp312 and reported the whole suite green; cp312 is precisely
       the interpreter that hides the bug. Against upstream's own published
       `cp310-abi3-manylinux_2_17_x86_64` wheel the two tests fail on x86_64 under 3.10
       and all pass under 3.11: one venv per interpreter, two minutes, no QEMU, and it
       settles "riscv64-specific or not" before a CI cycle is spent. For any abi3 port,
       make the floor interpreter the one you rehearse with.
     - **Fix the code, don't skip the tests.** They assert real product behaviour that is
       meant to work on 3.10, so the patch is
       `getattr(code, "co_qualname", code.co_name)` in the source rather than an xfail on
       the pair — `co_name` is identical for a module-level function and only loses the
       class prefix for a method, which beats `"unknown"`.

487. **`[tool.cmeel] has-sitelib` decides whether a `cmake-wheel`/cmeel port needs an
    interpreter matrix at all — read that one key before copying the sibling workflow's
    matrix.** Every cmeel distribution reads `abi: 0` in a queue note (gotcha 470: that is
    PEP 427's build number), so the note cannot tell the two shapes apart, and the two
    shapes differ by a factor of N jobs.
    - `has-sitelib = false` (cmeel-tinyxml2, cmeel-urdfdom, cmeel-console-bridge): the wheel
      holds no Python extension at all, only `cmeel.prefix/{include,lib}` — headers, the
      `.so`, `lib/cmake` and `lib/pkgconfig`. The backend tags it `py3-none-<platform>`, so
      **one** cibuildwheel job (`only: cp312-manylinux_riscv64`) produces the wheel every
      interpreter installs; an interpreter matrix would build N byte-identical wheels whose
      filenames collide in `wheelhouse/`.
    - `has-sitelib` unset/true with Python bindings (cmeel-boost's boost_python/boost_numpy,
      eigenpy): the `.so` links the version-specific CPython ABI, so the matrix is real.
    - The filename on PyPI is the fastest confirmation:
      `cmeel_urdfdom-6.0.0-0-py3-none-manylinux_2_28_x86_64.whl` (one wheel per platform)
      versus `cmeel_boost-1.90.0-0-cp312-cp312-...` (one per interpreter). Upstream's own
      `release.yml` is *not* the signal — it pins a single `python: ["cp314"]` either way,
      because for the `py3-none` shape any interpreter builds the same wheel.
    - `CIBW_REPAIR_WHEEL_COMMAND: ""` still applies to both: cmeel links its libraries with
      an `$ORIGIN` RUNPATH into the shared cmeel prefix, and auditwheel would only re-tag
      them, which is why upstream's own release workflow disables repair.


514. **A tool that models a *target* Python version caps the matrix by itself — its extension
    still compiles everywhere, so only running the tool shows it (the pytype case).** pytype
    2024.10.11 builds and installs cleanly on cp313: its pybind11 typegraph extension uses no
    version-specific C API, and `pytype --version` prints. The first real analysis then raises
    `UsageError: Python versions > 3.12 are not yet supported` from `validate_version` in
    `pytype/utils.py`, because the target version defaults to the host's and the opcode tables
    stop at 3.12. Upstream's cp310-cp312-only wheel set is the tell, and the matrix has to
    follow it (`python: ["cp312"]` here) even though cp313/cp314 wheels would build and pass
    an import check. Exercise the tool's front door — the CLI on a two-line file, not
    `import <pkg>` — on the newest interpreter of the default matrix before committing to it.
    Applies to anything that consumes the bytecode or AST details of the interpreter it runs
    on: type checkers, bytecode rewriters, coverage/debug tooling.

536. **An option cibuildwheel has since *removed* makes it reject the whole
    `[tool.cibuildwheel]` table before it selects anything, so every interpreter fails
    identically and the log shows no compiler at all (the spacy-pkuseg case).** cibuildwheel
    4.2.0 validates the config file up front and exits with
    `cibuildwheel: error: Option '<name>' not supported in a config file`. `only:` does not
    bypass it — selection happens after parsing — so all four matrix legs die in seconds with
    a message that looks like a workflow typo rather than a project problem. Three ports have
    hit it so far, all on names dropped in cibuildwheel 3.0: `free-threaded-support = false`
    (thinc 9.1.1, spacy-pkuseg 1.0.1) and `enable = ["cpython-freethreading"]` (decord2
    3.4.0). The release itself is not broken — upstream's own workflow pins an older
    cibuildwheel (`pypa/cibuildwheel@v2.21.3` for spacy-pkuseg) where the option is still
    valid — which is exactly why an otherwise-healthy tag carries it: the pin freezes the
    config's vocabulary at the release date, and any tag more than a couple of years old is a
    candidate.
    - **Pre-flight, on any host, in about a minute:**
      `cibuildwheel --print-build-identifiers --only cp312-manylinux_riscv64 .` in the
      checkout. It parses the config and prints the identifier, nothing else — no container,
      no runner, no build. Run it right after checking out the tag, before writing the YAML.
      (`--platform` cannot be combined with `--only`; the identifier implies it.)
    - **Fix with a one-line patch that comments the option out**, as
      `patches/thinc/9.1.1/` and `patches/spacy-pkuseg/1.0.1/` do, not with a run-time
      `config-file:` override — an override replaces upstream's whole table, silently dropping
      its `repair-wheel-command`, `skip` and `build` settings, and goal 2 wants our recipe to
      stay upstream's.
    - `Upstream-Status` depends on whether upstream already fixed it: `Backport` when there
      is a commit to cite (explosion did exactly this in thinc as 6f3a08b1), `To upstream`
      when there is not (spacy-pkuseg's master still carries the line three commits past the
      tag).
