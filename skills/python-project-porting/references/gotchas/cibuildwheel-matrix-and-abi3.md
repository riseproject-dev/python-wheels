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
- **56** — `py-build-cmake` projects: the free-threaded job dies at *configure* unless
- **201** — When `package-dir` is a monorepo subdirectory and the package's own build script

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
