# Gotchas — Build-tool drift & pins

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/build-tool-drift-and-pins.md`.

## In this file

- **23** — A floating *build tool* can break code the release-era tool compiled fine
- **29** — setuptools 82 deleted `pkg_resources`; any `setup.py` importing it breaks under
- **58** — Cython does publish a `py3-none-any` wheel, so it never compiles from sdist on riscv64
- **76** — A `build-system.requires` pin can exclude every riscv64 wheel of a build tool —
- **99** — setuptools 79 silently dropped `-shared` from distutils' C++ link, breaking build
- **112** — `PIP_CONSTRAINT` no longer reaches isolated build environments — pin build
- **118** — A pinned-old build *tool* and a floating build *dependency* are a two-sided
- **57** — `before-build` runs outside the isolated build env, so an upstream
- **171** — A green wheel we publish can break a *different* package's build the moment it lands
- **175** — One `PIP_BUILD_CONSTRAINT` file covers the project's build tool *and* every
- **184** — `[tool.cibuildwheel] enable` is an enum, not a free-form list — a pinned older

---

23. **A floating *build tool* can break code the release-era tool compiled fine
    (the Cython version-drift variant of gotcha 10; see `build-fonttools.yml`).**
    Gotcha 10 is about a package's *dependencies* floating; the same trap applies to
    the **build tool itself**. A project that compiles Cython extensions but pins
    Cython nowhere (`setup_requires=["cython"]`, no `[build-system]` table) will, on a
    fresh build, pull whatever Cython is newest *today* — often much newer than what
    upstream cut their wheels with. A newer Cython can change codegen semantics and
    break unchanged source. fonttools tripped this: **Cython 3.3.0** began enforcing
    PEP-484 argument annotations like `def f(quads: List[List[Point]])` as **strict
    runtime type checks** in compiled code; `qu2cu` passes a list-of-tuples there, so
    the compiled extension raised `TypeError: Expected list, got tuple` — 9 test
    failures on **all** interpreters. Cython 3.2.x (current when the release shipped)
    ignored the annotation.
    - **Looks like a port bug but reproduces on x86** — it's toolchain drift, not
      arch. Diagnose by comparing the package's sdist date against the tool's release
      timeline (`curl -s https://pypi.org/pypi/Cython/json`), then reproduce natively
      across the boundary versions (`pip install "cython==X"`) — far faster than QEMU
      and proves it's arch-independent.
    - **Fix mirrors the gotcha-17 preinstall shape, applied to a build tool:** pin
      below the breaking version (`CYTHON_SPEC: 'cython<3.3.0'`), preinstall it, and
      disable build isolation so the build actually uses it:
      ```yaml
      CIBW_BEFORE_BUILD: pip install "${CYTHON_SPEC}" setuptools wheel
      CIBW_BUILD_FRONTEND: "pip; args: --no-build-isolation"
      CIBW_ENVIRONMENT_PASS_LINUX: CYTHON_SPEC
      ```
      **Preinstall + `--no-build-isolation` is load-bearing, a pip pin alone is not:**
      `setup.py` appends `"cython"` to `setup_requires` only when Cython isn't already
      importable, and that fetch is an **easy_install that ignores pip specifiers** —
      so the pinned Cython must already be present for `setup.py`'s `has_cython` path
      to use it, and `--no-build-isolation` stops a fresh isolated env re-resolving to
      newest. Quote the spec so the shell doesn't read `<` as redirection. Revisit the
      ceiling when bumping the package version.

29. **setuptools 82 deleted `pkg_resources`; any `setup.py` importing it breaks under
    build isolation (the asyncpg case).** The setuptools instance of gotcha 23's
    floating-*build-tool* trap, and a common one — `pkg_resources` was removed outright
    in **setuptools 82.0.0** (2026-02-08). A project whose `pyproject.toml` only
    *floors* setuptools (`requires = ["setuptools>=77.0.3", ...]`) resolves to today's
    latest in the isolated build env, so a legacy `setup.py` that imports
    `pkg_resources` — asyncpg does, to version-check Cython on the cythonise path —
    dies inside `finalize_options` with `ModuleNotFoundError: No module named
    'pkg_resources'`, surfacing only as the generic `ERROR Backend subprocess exited
    when trying to invoke build_wheel`.
    - **Reproduces on any host** — drift, not arch. Settle the boundary without
      building anything: `unzip -l setuptools-8{1,2}.0.0-*.whl | grep -c 'pkg_resources/'`
      → 19 files on 81.0.0, 0 on 82.0.0.
    - **Fix is gotcha 23's shape** — preinstall the pin, disable isolation:
      ```yaml
      CIBW_BEFORE_BUILD: pip install "setuptools<82" "Cython>=3.2.1,<4.0.0" wheel
      CIBW_BUILD_FRONTEND: "build; args: --no-isolation"
      ```
      **The flag name is frontend-specific**: `build` takes `--no-isolation`, pip takes
      `--no-build-isolation`. Copying pip's spelling into a `build` frontend is an
      immediate argument error — match the frontend upstream declares in
      `[tool.cibuildwheel] build-frontend` (gotcha 13 explains why `build[uv]` is the
      one to avoid). Mirror the project's whole `build-system.requires` in the
      preinstall: `build --no-isolation` still *verifies* those requirements and fails
      on a missing one.
    - Revisit the ceiling when bumping the package version — upstream will eventually
      stop importing `pkg_resources`.

58. **Cython does publish a `py3-none-any` wheel, so it never compiles from sdist on riscv64
    (corrects gotcha 12).** Gotcha 12 says `cython` "has no riscv64 wheel anywhere — it must
    compile from sdist", and uses that to argue against `PIP_ONLY_BINARY=:all:` in
    `CIBW_ENVIRONMENT`. The premise is wrong: every Cython release since 0.29.15 (2020) ships
    `cython-<ver>-py3-none-any.whl` alongside the per-platform ones, and pip falls back to it
    when no platform wheel matches — `--only-binary=:all:` accepts it too. So a Cython build
    requirement is not a reason to keep `only-binary` out of the build phase (gotcha 12's
    conclusion — index URLs in `CIBW_ENVIRONMENT`, `only-binary` in `CIBW_TEST_ENVIRONMENT` —
    still stands on its own; only the Cython justification does not). Settle it for any build
    tool in one read: `curl -s https://pypi.org/pypi/<tool>/json` and look for a
    `py3-none-any` file, not just the platform tags.
    - Upstream's `NO_CYTHON_COMPILE=true` (a documented Cython env var) is therefore belt and
      braces on our arches, not load-bearing — it only matters if something forces a source
      build. Keep it when upstream sets it, but don't add it as a fix.

76. **A `build-system.requires` pin can exclude every riscv64 wheel of a build tool —
    pip's `--no-build-isolation` is the escape hatch `build --no-isolation` is not
    (refines gotcha 29).** Gotcha 29 pins a build tool *down* to dodge a breaking release;
    the mirror case is a project whose pin is too *low* for riscv64 to have a wheel at all.
    ddtrace's `pyproject.toml` requires `cmake>=3.24.2,<3.28` and `setup.py` invokes CMake
    through the **`cmake` PyPI package** (`cmake.CMAKE_BIN_DIR`), not through `PATH` — so a
    system cmake, or the one the manylinux image ships in `/usr/local/bin`, is irrelevant.
    The oldest riscv64 `cmake` wheel is **4.1.0**, so the isolated build env has nothing to
    resolve and falls back to compiling CMake itself from the sdist.
    - **The two `--no-*-isolation` flags differ in more than spelling.** `build
      --no-isolation` still *verifies* `build-system.requires` and fails on a pin it cannot
      satisfy (gotcha 29). **pip's `--no-build-isolation` does not check them at all**, so
      preinstalling a newer tool and passing
      `CIBW_BUILD_FRONTEND: "pip; args: --no-build-isolation"` builds the project with the
      version that exists for riscv64 and needs **no patch to `pyproject.toml`**. Prefer it
      to patching a pin: the pin stays visible to a reader, and there is nothing to refresh
      at the next version bump.
    - **Prove the newer tool actually works before relying on it**, on any host: read every
      `cmake_minimum_required` in the tree (cmake 4 only rejects `< 3.5`), then run one full
      `pip wheel . --no-deps --no-build-isolation` in a venv holding the preinstalled
      versions. ddtrace built clean with cmake 4.4.2 + setuptools 84 on macOS/arm64 in three
      minutes — arch-independent evidence that the pin, not the code, was the obstacle.

99. **setuptools 79 silently dropped `-shared` from distutils' C++ link, breaking build
    scripts that drive the compiler API directly (the tree-sitter-languages case).** Gotcha 29
    is setuptools drift seen through an *import* (`pkg_resources` gone in 82); this one is the
    same drift seen through a *runtime API*, and it hits a shape gotcha 23 does not cover: a
    `build.py` that calls `distutils.ccompiler.new_compiler()` itself to produce a helper shared
    library beside the extension (py-tree-sitter's `Language.build_library`, compiling 48 grammars
    into one `languages.so`). In setuptools 79.0.0 the class default for `linker_exe_cxx` became
    `["c++", "-shared"]`, and `unix.Compiler.link()` builds the C++ linker as
    `compiler_cxx + _linker_params(linker_so_cxx, linker_exe_cxx)` — the whole of
    `linker_so_cxx` (`c++ -shared`) is consumed as the prefix, the params come out empty, and the
    link runs `c++ <objs> -o foo.so`, dying with
    `crt1.o: in function '__wrap_main': undefined reference to 'main'`.
    - **No env var can fix it.** `LDCXXSHARED` is only read by `customize_compiler()`, which
      `setup.py` calls and a hand-rolled build script does not. Pin instead, in gotcha 23/29's
      shape: `CIBW_BEFORE_BUILD: pip install "setuptools<79" …` plus
      `CIBW_BUILD_FRONTEND: "pip; args: --no-build-isolation"`.
    - **Bisect it in seconds per version, no compile of the real project.** Monkeypatch the
      compiler's `call`, link one throwaway `.o` with `target_lang="c++"`, print the first three
      argv entries: 78.1.1 → `c++ -shared /tmp/x.o`, 79.0.1 → `c++ /tmp/x.o -o`. Arch-independent,
      so any host answers it.
    - **The inverse of gotcha 23 lives here too: an upstream pin can be too *old*.** Gotcha 23
      pins a floating build tool *down*; a frozen release pins one *up* — tree-sitter-languages
      names `cython==3.0.8` (Jan 2024), which predates free threading and cannot compile under
      cp314t though it still handles cp312–cp314. Check an exact upstream tool pin against every
      interpreter in the matrix, not just the ones upstream shipped, and bump rather than inherit
      when it cannot reach one.
    - **A release frozen against a pre-breaking-change dependency needs that pin in the test
      phase as well as the build.** `install_requires` floats, so upstream's own `pip install -e .`
      now resolves to an API the code cannot use — tree-sitter-languages needs `tree-sitter<0.22`
      both for `Language.build_library` at build time and for `Language(path, name)` at import
      time, i.e. in `CIBW_BEFORE_BUILD` *and* `CIBW_TEST_REQUIRES`.

112. **`PIP_CONSTRAINT` no longer reaches isolated build environments — pin build
    tools with `PIP_BUILD_CONSTRAINT` (the spacy case).** Gotcha 23's fix for a floating
    build tool is preinstall + `--no-build-isolation`, which only covers the *top-level*
    build. When the thing that must be pinned is the build tool of a **dependency** pip
    compiles from sdist, there is no `--no-build-isolation` to reach for, and the obvious
    lever is a constraints file. It does not work: pip 26 — the version cibuildwheel
    4.2.0 pins — passes `_PIP_IN_BUILD_IGNORE_CONSTRAINTS=1` into the build-env subprocess
    (`pip/_internal/build_env/installer.py`) precisely so inherited `PIP_CONSTRAINT` is
    ignored there. `--build-constraint` / `PIP_BUILD_CONSTRAINT` is the replacement, and
    its comment says it "also constrains any nested builds" — which is exactly what a
    chain of from-source packages needs.
    - **Prove it in 30 seconds before trusting either**: point `PIP_CONSTRAINT` at a file
      holding `cython==0.0.1` and build the package. If it succeeds, the constraint never
      reached the build env. Repeat with `PIP_BUILD_CONSTRAINT` and watch it fail.
    - **An upstream `environment = { PIP_CONSTRAINT = ... }` may therefore be dead code
      today** (spaCy pins numpy that way). Carrying it forward is still right — gotcha 107
      — but do not assume it is doing anything; add `PIP_BUILD_CONSTRAINT` pointing at the
      same file when you need the pin to bite.

118. **A pinned-old build *tool* and a floating build *dependency* are a two-sided
    constraint — pin the dependency down to meet the tool (the thinc case; see
    `build-thinc.yml`).** Gotcha 23 is about a build tool that floats *up* past what
    the source can take, and its fix is a ceiling on the tool. The mirror case is a
    project that already pins its tool low and whose *dependency* then drops support
    for it. **numpy 2.5.0** replaced the legacy `numpy/__init__.pxd` — the header every
    `cimport numpy` resolves to under Cython 0.29 — with a deliberate compile-time
    abort:
    ```
    DEF err = int('Build aborted: the NumPy Cython headers require Cython 3.0.0 or newer.')
    ```
    numpy 2.4.3 is the last release that still ships it. So any project pinning
    `cython<3.0` (thinc 9.1.1 does, and the pin is deliberate — upstream reverted to it
    over `noexcept` semantics) fails on a fresh build with a `ValueError: invalid
    literal for int()` from `__init__.pxd:12` followed by a wall of `'ndarray' is not a
    type identifier`. That second half is the misleading part: it reads like a broken
    `.pyx`, but every one of those errors is downstream of the first.
    - **Settle the boundary by reading the header out of the wheels, not by building.**
      `unzip -p numpy-<v>-cp312-…manylinux…x86_64.whl '*/numpy/__init__.pxd' | grep -c
      'Build aborted'` over a handful of versions bisects it in under a minute on any
      host, and it needs no riscv64 anything.
    - **Fix is gotcha 29's shape, aimed at the dependency**: preinstall
      `build-system.requires` verbatim with the one ceiling added, then disable
      isolation so the pin actually holds — `CIBW_BEFORE_BUILD: pip install … "numpy>=2.0.0,<2.5.0"`
      plus `CIBW_BUILD_FRONTEND: "build; args: --no-isolation"`. Leave the *test*
      environment unconstrained: numpy's C ABI is forward-compatible, so a wheel built
      against 2.4.3 imports fine under current numpy, and testing against what users
      will actually install is the more useful signal.
    - **The interpreter matrix follows from the same pin.** Cython 0.29 emits the
      pre-3.13 five-argument `_PyLong_AsByteArray` call, so `cython<3.0` also means no
      cp313+ — confirmed in seconds by cythonizing a two-line `.pyx` under 3.13 and
      compiling the result (`error: too few arguments to function call, expected 6,
      have 5`). Check upstream's own published wheel tags before writing the matrix:
      they stop at cp312 for exactly this reason.

57. **`before-build` runs outside the isolated build env, so an upstream
    `CIBW_BEFORE_BUILD: pip install <build-tool>` may be a no-op — find out before you
    trust it or "fix" a build with one (the clickhouse-driver case).** cibuildwheel runs
    `before_build` against the *container's* interpreter (`platforms/linux.py`:
    `container.call(["sh", "-c", …])` with that python first on `PATH`), and gives neither
    the `build` nor the `pip` frontend `--no-isolation`/`--no-build-isolation` by default.
    A package with **no `[build-system]` table** therefore gets pypa/build's fallback
    requires (`setuptools`, `wheel`) in a fresh venv, and whatever `before-build`
    installed is invisible to `setup.py`. Upstreams carry such lines for years without
    noticing, because checked-in generated sources make the build succeed either way:
    clickhouse-driver's release workflow sets `CIBW_BEFORE_BUILD: pip install cython`,
    yet its wheels — on every architecture — compile the `clickhouse_driver/*.c` that
    ship in the tag, since `setup.py` falls back to `ext = '.c'` when `Cython.Build`
    will not import.
    - **Keep upstream's line anyway when it is cheap** (Cython resolves to a
      `py3-none-any` wheel, gotcha 58 — no compile), because mirroring upstream is the
      point and the line is harmless. What matters is knowing it is inert, so you do not
      *add* one expecting it to change the build, and do not credit it when the build
      works.
    - **Two greps say which world you are in**: does the tag track the generated sources
      (`git ls-files '*.c'` beside the `.pyx`), and does `setup.py` degrade to them on
      `ImportError`. If it does not degrade — no `.c` in the tree, or the fallback raises
      — the tool is genuinely required and gotcha 23's preinstall + `--no-isolation`
      shape is the fix. If it does degrade, the `.c` header (`head -1`) names the version
      that actually produced your wheel, which is the one to reason about, not whatever
      `before-build` fetched.
    - Distinct from gotchas 23/29, which are about a build tool that *is* reached and
      resolves to a too-new version. This one is about a build tool that is never reached
      at all.

171. **A green wheel we publish can break a *different* package's build the moment it lands
    — Cython 3.3.0 reroutes C-integer subscripts through the sequence protocol (the
    preshed/spacy case).** spaCy's PR run was green on every interpreter and its `main`
    publish run 16 minutes later failed with **100** `OverflowError: Python int too large to
    convert to C ssize_t`, all inside `PreshMap`. Nothing about spaCy changed: our own
    `preshed` wheel was published in between, so pip stopped source-building preshed in the
    container and installed ours — and ours is broken. Cython **3.3.0** (2026-08-22) makes an
    extension type whose subscript special methods take a C integer implement the *sequence*
    protocol rather than the mapping one, so `def __setitem__(self, key_t key, size_t value)`
    with `key_t = uint64_t` is reached through `sq_ass_item`, whose index is a `Py_ssize_t`.
    Every key at or above `2**63` — half of them, since they are 64-bit hashes — raises.
    This is gotcha 23's build-tool drift with the blast radius pointing *outward*: the
    damaged package is not the one whose CI went red.
    - **Diff the artefact *filenames* between the green run and the failing one, not the
      versions.** Both logs said `preshed-3.0.13`; only the tags differed —
      `preshed-3.0.13-cp312-cp312-linux_riscv64.whl` (built in-container from the sdist) in
      the green run against `…-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl` (ours) in
      the failing one. `grep -oE '(Downloading|Using cached) [^ ]+\.(whl|tar\.gz)'` over both
      job logs is the whole diagnosis.
    - **Reproduce it on aarch64 with two `pip install`s** (gotcha 101's rehearsal, at its
      cheapest): upstream's PyPI wheel passes a five-line `PreshMap` probe and a
      `--no-binary` build of the *same version* fails it. That instantly rules out riscv64
      and names the build as the variable; bisecting `cython==3.2.9` vs `3.3.0` under
      `--no-isolation` then takes seconds per version. The codegen confirms it —
      `sq_ass_item` occurrences go 1 → 3.
    - **A package's own test suite is not evidence the wheel is good.** `pytest --pyargs
      preshed -Werror` passed on the broken wheel because no test uses a key above `2**63`.
      When a pin exists to stop a specific regression, add the assertion that regression
      would trip, ahead of the suite.
    - **The exposure is narrow and greppable**, so scan rather than pinning everywhere:
      `grep -rhE 'def __(get|set|del)item__\(self, +[a-z_]+ +[a-z_]' --include='*.pyx'
      --include='*.pxd'` over every Cython package we publish (261 files across 21 sdists)
      found preshed and nothing else. Only a subscript type wider than or unsigned relative
      to `Py_ssize_t` can fail; an `int`/`Py_ssize_t` subscript is unaffected.

175. **One `PIP_BUILD_CONSTRAINT` file covers the project's build tool *and* every
    dependency pip source-builds in the test phase — cheaper than gotcha 23's preinstall
    (the habluetooth case; see `build-habluetooth.yml`).** Gotchas 23/29/118 all fix a
    floating build tool by preinstalling a pin and disabling isolation, which reaches only
    the *top-level* build. A Cython/setuptools release that a new tool version breaks
    usually breaks its **siblings from the same author** too, and those arrive as ordinary
    runtime requirements that pip compiles from sdist during `pip install <wheel>` — a
    second, identical failure your preinstall cannot touch. habluetooth 6.26.7 and its
    `bluetooth-data-tools` dependency both fail on Cython 3.3.0 with `Signature not
    compatible with previous declaration` over their augmenting `.pxd` files. Write the
    file once in `before-all` and name it in both variables:
    ```yaml
    CIBW_BEFORE_ALL: echo 'Cython<3.3.0' > /cython-constraint.txt
    CIBW_ENVIRONMENT: >-
      PIP_CONSTRAINT=/cython-constraint.txt
      PIP_BUILD_CONSTRAINT=/cython-constraint.txt
    ```
    `before_all` runs in the container before any build, so the path exists by the time
    either phase reads it. The payoff over gotcha 23's shape is that **build isolation
    stays on**, so the build runs exactly as upstream's does — no `--no-isolation`, no
    restating `build-system.requires`, and nothing to refresh when upstream adds a
    requirement. Reach for the preinstall only when the tool must be *importable* by
    `setup.py` before the backend runs (gotcha 23's easy_install path).
    - **A poetry-core project is where this bites hardest**, because `[tool.poetry.build]
      script = "build_ext.py"` puts the cythonize call inside the backend: there is no
      `setup.py` to preinstall for, and the generated `setup.py` is executed by the
      *isolated* env's interpreter.

184. **`[tool.cibuildwheel] enable` is an enum, not a free-form list — a pinned older tag's
    value can be rejected by the newer cibuildwheel this repo pins (the pi-heif case; see
    `build-pi-heif.yml`).** This is the cibuildwheel-config mirror of gotcha 76: the *tool
    itself* drifted between the upstream tag being built and the SHA this repo pins, and
    the failure is a hard parse error, not a warning — `cibuildwheel: Failed to parse
    enable group. Unknown enable group: cpython-freethreading. Valid group names are:
    cpython-prerelease, graalpy, pypy, pypy-eol, pyodide-eol, pyodide-prerelease`, thrown
    before any container starts, for **every** interpreter in the matrix (the whole
    `[tool.cibuildwheel]` table is parsed up front, so `--only cp312-…` does not narrow
    around it). `cpython-freethreading` was cibuildwheel's opt-in for free-threaded
    (`cp3XXt`) wheels; newer cibuildwheel builds them without an enable flag at all, so the
    token was removed outright rather than renamed. pillow_heif's own next tag
    (`v1.5.0`) already carries the fix — dropping the token with no replacement — which is
    the tell that this is upstream's own bug, not a riscv64-only one: diff `pyproject.toml`
    between the pinned tag and the next one or two releases for the exact upstream commit,
    cite it as `Upstream-Status: Backport`, and patch just that line rather than
    hand-picking a "safe" enable list — the smallest correct patch is upstream's own diff.
    - **Reproduces on any host, no CI cycle needed**: `cibuildwheel --print-build-identifiers
      --only cp312-manylinux_x86_64` (or any target) against the unpatched checkout fails
      identically on macOS/Linux/x86/arm, since the parse happens before any platform or
      arch selection.
