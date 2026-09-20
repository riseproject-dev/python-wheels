# Gotchas — Bazel & driving the build container

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/native-build-bazel-and-drivers.md`.

## In this file

- **8** — Pin Bazel to a version that actually exists.
- **15** — Heavy C++ ports: drive the build container yourself, build the C++ once.
- **47** — A bazel-built project on riscv64: there is no bazel binary, so bootstrap one
- **69** — Looping interpreters inside one bazel output base: a repository rule re-runs
- **95** — OCaml/opam projects are ordinary ports — but the manylinux image is the wrong
- **131** — A bzlmod project that gets its Python deps from `rules_python`'s pip extension
- **132** — Google's ML Bazel stack (XLA/TSL/jax/TensorFlow) already carries riscv64 config
- **133** — bazel 7.x pins the same rules_python/rules_java across the whole minor series, so
- **136** — Upstream builds its wheels in a vcpkg image: replace the image, keep the workflow
- **142** — cibuildwheel copies the
- **202** — A monorepo's "regenerate deps from Bazel" helper may already tolerate a missing
- **219** — GDAL's cmake build produces no `gdal-config` script — a second consumer of the
- **233** — A package can have no Python build backend at all — the wheel comes from an
- **397** — A CMake build that shells out to a bare `python3` for one vendored sub-extension
  silently builds it for the container's default interpreter, not the one the wheel is for.
- **421** — `pierotofy/set-swap-space` is a no-op on the riscv64 runners — a heavy link gets
  the runner's 15GB of RAM and nothing behind it.
- **423** — A depot_tools/gclient checkout downloads no GCS dependency on riscv64 until
  `VPYTHON_BYPASS` is set (gsutil's vpython venv pins a crcmod wheel that has no riscv64 build).
- **424** — Audit a chromium-style DEPS for riscv64-less CIPD packages with `cipd describe`
  before spending a build cycle finding them one at a time.
- **427** — Under `VPYTHON_BYPASS` the checkout's own *DEPS-pinned* depot_tools breaks next:
  its gsutil 4.68 vendors a six that cannot import on python ≥ 3.12.
- **432** — A vendored submodule whose version the project's CMake "fixes up" with `git
  checkout <tag>` stays on its stale recorded commit in CI, because `actions/checkout`
  clones submodules without tags.
- **434** — `EXTERNAL_PROJECT_LOG_ARGS` (or any `LOG_CONFIGURE 1`) hides the only useful
  line of a third_party failure in a stamp log — print the stamp logs on failure.
- **437** — The same `git checkout <tag>` inside an `ExternalProject_Add` `PATCH_COMMAND`
  aborts the build outright — fetch the missing tag, and sweep every dependency at once.

---

8. **Pin Bazel to a version that actually exists.** bazelisk reads
   `USE_BAZEL_VERSION`. I guessed `8.5.2` (doesn't exist) → 404 → instant fail. There
   is no `.bazelversion` at protobuf release tags. Verify a candidate is real before
   pushing:
   ```
   curl -sI https://releases.bazel.build/<ver>/release/bazel-<ver>-linux-x86_64   # want 200
   ```
   Use a version the project's own CI uses (grep their workflows) that satisfies their
   `MODULE.bazel` `bazel_compatibility`. Install bazelisk yourself; don't assume the
   runner has Bazel. Bazel's `system_python` needs a host interpreter, so run
   `actions/setup-python` before Bazel.

15. **Heavy C++ ports: drive the build container yourself, build the C++ once.**
    When the extension links a big C++ tree whose sources sit *beside* the Python
    package (e.g. Cython over a sibling `cpp/`), cibuildwheel's copy-the-package-dir
    model can't see them, and the manylinux image ships no Node so a `container:` job
    can't run JS actions. So: checkout + upload-artifact on the host, and a `docker run`
    step that bind-mounts the source and an inline-written build script into
    `$MANYLINUX_RISCV64_IMAGE`. Build the C++ lib **once** into a prefix, then loop the
    interpreters (`for pytag in $PYTHON_TAGS`) building only the bindings against it —
    don't rebuild C++ per Python.
    - **Feed dep sources from the OS, not vcpkg.** Upstreams that vcpkg their deps
      rely on a binary cache baked into *their* x86/arm images; the riscv image has
      none. Use the project's from-source path instead (Arrow:
      `-DARROW_DEPENDENCY_SOURCE=BUNDLED`, which downloads+compiles each pinned dep).
    - **The image is Rocky 10 (`dnf`), missing `ninja-build`, OpenSSL dev headers,
      and `zip`** — `dnf install` them in the script; it already has cmake/gcc/
      auditwheel/git. Enable heavy features (network storage, LLVM) incrementally
      from a small green core, one env flag per feature — each drags in a dep tree
      that may not have been built on riscv64 before.
    - **A full qemu build is impractical, but `cmake` *configure* under
      `--platform linux/riscv64` finishes in minutes** and catches most flag/dep/
      toolchain mistakes (missing lib, unresolved target) before you spend a
      multi-hour native CI cycle. Do that as your gotcha-9 local check for these.

47. **A bazel-built project on riscv64: there is no bazel binary, so bootstrap one
    from the dist archive inside the manylinux image (the ray case).** Gotcha 8 assumes
    `releases.bazel.build` has a binary for your arch; for riscv64 it never does — bazel
    ships only `linux-x86_64`/`linux-arm64` (checked on the 7.5.0 and 9.2.0 release
    assets), so bazelisk has nothing to fetch. Bootstrapping from `bazel-<ver>-dist.zip`
    works, and the recipe is cheap to validate on **aarch64** first (~5 min in
    `quay.io/pypa/manylinux_2_39_aarch64`, the same Rocky 10 image family) before
    spending a riscv64 cycle:
    ```bash
    dnf install -y java-21-openjdk-devel zip unzip    # the image has gcc/curl/python3
    export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")"
    EXTRA_BAZEL_ARGS="--tool_java_runtime_version=local_jdk" bash ./compile.sh
    ```
    - **`compile.sh` builds `src:bazel_nojdk`, which needs a real JDK at *run* time, not
      a JRE.** With `java-21-openjdk-headless` the binary dies on `WARNING: Ignoring
      JAVA_HOME, because it must point to a JDK` → `FATAL: Could not find system
      javabase`. Install `-devel` in the job that *uses* bazel as well as the one that
      builds it.
    - **bazel 7.x cannot bootstrap on riscv64 unpatched.** It pins rules_python 0.33.2,
      whose `PLATFORMS` table has no riscv64 entry, so fetching `@pythons_hub` aborts
      with `No platform declared for host OS linux on arch riscv64`
      (bazelbuild/bazel#23018). Upstream fixed riscv64 bootstrapping in **8.2.0**
      (bazelbuild/bazel#25745); the 7.x backport (#26986) is still open. Point the module
      at a patched copy rather than carrying a diff — `--override_module=rules_python=<dir>`
      (a documented bzlmod flag, present in 7.5.0) after a one-line `sed` avoids a
      heredoc-in-heredoc patch file, and `EXTRA_BAZEL_ARGS` reaches the right bazel
      invocation (`scripts/bootstrap/bootstrap.sh` appends it):
      ```bash
      sed -i 's|fail("No platform declared for host OS {} on arch {}".format(os_name, arch))|return "x86_64-unknown-linux-gnu"|' \
        <dir>/python/private/toolchains_repo.bzl
      ```
      The host toolchain it names is never *selected* on riscv64 — its
      `constraint_values` don't match — so any linux entry is a safe stand-in.
    - **"Just use bazel 8" usually isn't available**: a project's WORKSPACE can pin the
      exact version (ray: `versions.check(minimum_bazel_version = "7.5.0",
      maximum_bazel_version = "7.5.0")`), so the bootstrapped 7.x is mandatory. Read that
      gate before picking a version. A bootstrapped binary reports `bazel 7.5.0-
      (@non-git)` and bazel_skylib's check accepts the trailing dash — settle it with a
      3-line workspace rather than by guessing.
    - **The project's own hermetic Python is the next trap, one level down.** ray's
      WORKSPACE calls `python_register_toolchains(python_version = "3.10")` and then
      `load("@python3_10//:defs.bzl", …)`, which *forces* a python-build-standalone fetch
      for the host platform at load time — same failure, different repo. Note PBS now
      publishes riscv64 CPython (3.10 included, checked on the 20260825 release), so
      bumping the project's rules_python is a real alternative to patching the hermetic
      toolchain out.

69. **Looping interpreters inside one bazel output base: a repository rule re-runs
    only when a var it declares in `environ` changes (the ray/`local_config_python`
    case).** Building the heavy C++ core once and then looping `cpXY` for the bindings
    (gotcha 15's shape, and what makes a bazel port affordable at all) means every
    interpreter shares one output base. Bazel's *actions* re-run when their inputs or
    `--action_env` change, but a **repository rule** is cached against the values of the
    vars its `environ =` list names, and nothing else — not `PATH`, not what a symlink on
    `PATH` points at. grpc's `python_configure` (which ray, and anything using
    `pyx_library`, pulls in for `@local_config_python//:python_headers`) declares exactly
    `["BAZEL_SH", "PYTHON3_BIN_PATH", "PYTHON3_LIB_PATH"]` and otherwise falls back to
    `repository_ctx.which("python3")`. So upstream's `ln -sf /opt/python/$PY/bin/python3
    /usr/local/bin/python3` re-points the *toolchain* but leaves `Python.h` resolved to
    the first interpreter of the loop — every wheel gets a `.so` compiled against cp312
    headers, and cp313/cp314 fail at import after the whole multi-hour build.
    - **Export the declared var, don't rely on the symlink**: `export
      PYTHON3_BIN_PATH="/opt/python/${python}/bin/python3"` inside the loop. ray's own
      `.bazelrc` header asks for that variable by name — it is upstream's documented knob,
      not a divergence.
    - **Upstream varying a stamp var is not the invalidation mechanism**, so don't copy it
      and assume you are covered. ray sets `RAY_BUILD_ENV=manylinux_py$PY` under
      `build --action_env=RAY_BUILD_ENV`; that re-runs every action but never re-runs a
      repository rule. Keeping it constant (so the C++ core is built once) is the right
      call for a riscv64 port — it just is not what was making upstream's per-interpreter
      `.so` correct.
    - **Settle "is this artifact really per-interpreter?" from upstream's published wheels
      without downloading them** — gotcha 41's HTTP-range trick applied to a correctness
      question rather than a triage one. Read each wheel's zip central directory (last
      ~1 MB, `Range:` request) and compare the **CRC32 and uncompressed size** of the
      files you care about across the `cpXY` wheels. For ray 2.58.0 that showed
      `ray/_raylet.so` differing in both CRC *and* size across cp312/cp313/cp314 (so it
      must be rebuilt per interpreter) while `core/src/ray/raylet/raylet` was byte
      identical on all five (so the C++ core genuinely is shared) — the two facts that
      together justify the build-once-loop-bindings shape and expose the trap above.

95. **OCaml/opam projects are ordinary ports — but the manylinux image is the wrong
    container for them (the semgrep case; see `build-semgrep.yml`).** A package whose
    wheel is a compiled OCaml binary reads like a blocker and is not: opam publishes an
    official **`opam-<ver>-riscv64-linux`** release binary (checked on 2.5.2), and OCaml
    has had a native riscv64 backend with natdynlink since the 5.x line —
    `configure.ac` at 5.3.0 matches `riscv64-*-linux*` and sets `has_native_backend=yes`.
    So `opam init --bare --disable-sandboxing` + `opam switch create` + the project's own
    `make install-deps` works unchanged; the port is heavy (compiler, ~250 opam packages,
    generated parsers), not infeasible.
    - **A per-arch opam lockfile is one line of difference.** Projects that vendor
      `opam-lockfiles/<pkg>.opam.linux-{amd64,arm64}.locked` and pick one from `uname -m`
      have no riscv64 case, and the picker is usually called `--strict` so it hard-fails.
      Diff the two committed lockfiles first — semgrep's differ in exactly
      `"host-arch-x86_64"` vs `"host-arch-arm64"` — and derive yours with `sed`, after
      confirming `packages/host-arch-riscv64/` exists at the *pinned* opam-repository
      commit (raw.githubusercontent 200). That keeps every version pin upstream tested
      against, where re-solving without `--locked` would not.
    - **Rocky 10 riscv64 is missing dev packages Ubuntu 24.04 has**, and for a
      non-cibuildwheel build there is no reason to suffer that: `libunwind-devel` and
      `patchelf` are absent from Rocky's riscv64 repos (`libev-devel`, `gmp-devel`,
      `pcre2-devel`, `libcurl-devel`, `elfutils-devel` are all present), while
      `riscv64/ubuntu:24.04` carries every one of them in `main`. Ubuntu 24.04 is glibc
      2.39 — the same as the `ubuntu-24.04-riscv` runner — so a `podman run` against it
      still yields a legitimate `manylinux_2_39_riscv64` tag. It is also usually *closer*
      to upstream, whose own core build runs on a bare `alpine`/`debian` image rather
      than in manylinux.
    - **`actions/collect-gpl-sources` is dnf/rpm-only**, so a Debian-based build needs the
      `apt-get source` equivalent inline: flip `Types: deb` to `Types: deb deb-src` in
      `/etc/apt/sources.list.d/ubuntu.sources`, map the shipped libraries back to source
      packages with `dpkg -S` + `dpkg-query -W -f='${source:Package}\n'`, and tar the
      result for `_publish-wheel.yml`' `gpl-sources-artifact`. ports.ubuntu.com does carry
      `main/source/Sources.gz`, so this works on riscv64.
    - **Validate the bootstrap half under QEMU even when the full build is impossible.**
      The apt list, the opam binary, `opam init`, the repository pin and
      `opam show <compiler-variant> <host-arch-riscv64>` all run in a
      `riscv64/ubuntu:24.04` container in minutes and cover every step that fails *fast*
      — which on a job measured in hours is most of the value a local check can give.

131. **A bzlmod project that gets its Python deps from `rules_python`'s pip extension
    has no riscv64 branch at all — patch `default_platforms()`, then narrow
    `target_platforms` to the host (the jaxlib/XLA case; see `build-jaxlib.yml`).**
    Gotcha 47 covers getting *bazel itself* onto riscv64; the next wall is
    `@pypi//<pkg>`. rules_python (checked in 2.2.0) knows riscv64 as a *toolchain*
    platform — `python/private/pypi/pep508_env.bzl`, `whl_target_platforms.bzl` and the
    python-build-standalone manifest all list it, and PBS publishes riscv64 CPython for
    every version `MINOR_MAPPING` selects (3.12.13/3.13.13/3.14.4, freethreaded
    included). But `default_platforms()` in `python/private/pypi/extension.bzl` builds
    its Linux entries from a literal `for cpu in ["x86_64", "aarch64"]`, so no
    `linux_riscv64` platform exists, every `@pypi//...` alias's `select()` is missing a
    branch for the host, and the build dies in **analysis**, before a single object file.
    A one-line change to that loop is the whole fix, and it drops in as one more
    `single_version_override` patch if the project already carries them.
    - **Then cut `pip.parse`'s `target_platforms` down to `"{os}_{arch}"`.** Projects
      hardcode a cross-compilation list (`"{os}_x86_64", "{os}_aarch64"`); adding
      riscv64 to it makes rules_python resolve riscv64 wheels for *every* pinned
      requirement, and the lock's hashes only cover the arches upstream ships. Resolving
      the host alone leaves `whl.srcs` empty for exactly the packages that have no
      riscv64 wheel on the index — which is the state a local-wheel override needs, and
      is harmless for anything the build never uses. `_platforms()` de-dupes through a
      dict, so `"{os}_{arch}"` is safe to leave in place on x86 too.
    - **Look for a `local_wheels`-style escape hatch before regenerating a lock file.**
      jax's MODULE.bazel already maps `numpy`/`scipy`/`ml_dtypes` to `dist/<name>-*.whl`
      (upstream uses it to inject a TSAN-instrumented numpy), so dropping our registry's
      riscv64 wheels into `dist/` at the workspace root feeds the build without touching
      the 1800-line hash-pinned `requirements_lock_3_*.txt`. Grep MODULE.bazel for
      `local_wheels` / `whl_modifications` / `override_repo` before writing YAML.

132. **Google's ML Bazel stack (XLA/TSL/jax/TensorFlow) already carries riscv64 config
    settings — read them before triaging the port as infeasible.** A 190 MB wheel over a
    Bazel-built C++ world looks like gotcha 41's territory, but XLA is the opposite case:
    `//xla/tsl:linux_riscv64` and `riscv64_or_cross` are real `config_setting`s,
    `if_llvm_riscv_available()` wires `@llvm-project//llvm:RISCVCodeGen` into
    `xla/backends/cpu/codegen` and `xla/service/cpu`, `xla/tsl/framework/contraction`
    has explicit riscv64 branches that turn oneDNN off, and XNNPACK's pinned commit
    gates RVV kernels on `//build_config:riscv`. Three greps over the *downloaded*
    archive (`grep -rIn riscv --include=BUILD --include='*.bzl'`) settle it in minutes.
    - **The hermetic C++ toolchain is the part that has no riscv64**, not the code:
      `rules_ml_toolchain`'s `cc/impls/` covers only linux_x86_64/linux_aarch64/darwin,
      and its `cc/llvms/BUILD` selects fall through to `:empty`. The projects anticipate
      this — jax's `build/build.py` switches to `--config=clang_local` and hunts for a
      local `clang` on any host that is not linux x86_64/aarch64, so the fix is to
      install a compiler in the build container rather than to patch the toolchain.
      Rocky 10 riscv64 ships **clang/clang-devel/llvm 21.1.8** in AppStream (checked with
      gotcha 51's `dnf -q list` in `rockylinux/rockylinux:10` under
      `--platform linux/riscv64`), which is newer than the hermetic clang 18 upstream
      uses.
    - **The wheel/platform plumbing is separate from the compiler and fails earlier.**
      A per-arch `PLATFORM_TAGS_DICT`-style table plus a `cpu = select({...})` with no
      `//conditions:default` is the usual shape; both need a riscv64 entry or analysis
      aborts. Grep the wheel rule for `select(` over `@platforms//cpu:` before assuming
      the build is compiler-bound.

133. **bazel 7.x pins the same rules_python/rules_java across the whole minor series, so
    gotcha 47's bootstrap script is version-portable — and it belongs in its own cached
    job.** bazel 7.7.1's `MODULE.bazel` pins `rules_python` 0.33.2 and `rules_java`
    7.6.5, byte-identical to 7.5.0's, so the riscv64 bootstrap recipe carries over by
    changing one env var. Confirm with
    `curl -sL https://raw.githubusercontent.com/bazelbuild/bazel/<ver>/MODULE.bazel | grep rules_` —
    cheaper than downloading the 250 MB dist archive. Put the bootstrap in a separate job
    keyed on the bazel version with `actions/cache` + `upload-artifact`: a warm cache
    turns a fresh bootstrap into a ~40 s restore, so every later iteration on the real
    build starts immediately instead of rebuilding bazel.

136. **Upstream builds its wheels in a vcpkg image: replace the image, keep the workflow
    (the pyogrio case; see `ci/pyogrio/manylinux_riscv64-gdal.Dockerfile`).** A project
    wrapping a big C/C++ library often ships a `ci/*-vcpkg-<lib>.Dockerfile` that
    `vcpkg install`s the whole dependency tree, plus a `[tool.cibuildwheel]`
    `manylinux-<arch>-image` pointing at it. vcpkg *does* carry `riscv64-linux` community
    triplets, but there is no binary cache and no port testing for them, so following that
    path means compiling an unvetted port tree. Building the same libraries from their own
    release tarballs is faster and far less risky, and every other part of upstream's
    recipe survives: the shape stays `docker/build-push-action` + `CIBW_MANYLINUX_RISCV64_IMAGE`,
    exactly as `build-shapely.yml` uses upstream's own `ci/Dockerfile`.
    - **Put the replacement Dockerfile in *this* repo (`ci/<pkg>/`), not in a patch.**
      `docker/build-push-action`'s `file:` is workspace-relative, so a second
      `actions/checkout` into `python-wheels/` is enough
      (`file: python-wheels/ci/<pkg>/<name>.Dockerfile`, `context:` the same directory).
      Patching it into the upstream checkout would leave that tree dirty and rename the
      wheel — gotcha 31 for `setuptools_scm`, and **versioneer** does the same thing
      (`git describe --tags --dirty`). Untracked files are safe there; tracked edits are not.
    - **Build the image in a job of its own**, with `cache-to`, and give the wheel jobs
      `cache-from` + `load: true` only. Matrix entries start together, so without the extra
      job each of them compiles the whole tree before any cache entry exists — N multi-hour
      C++ builds on the handful of shared riscv64 runners (gotcha 48).
    - **Dry-run the entire image on aarch64 first.** `quay.io/pypa/manylinux_2_39_aarch64`
      is the same Rocky 10 family and runs natively on an arm64 laptop:
      GEOS+PROJ+libspatialite+GDAL took 5.5 minutes there. Every mistake in this port — a
      missing rpm, a 2009 `config.sub`, absent gconv modules, a licence step that failed on
      three separate packages — surfaced in 5-minute cycles instead of hour-long riscv64
      ones. Then reproduce upstream's whole wheel job by hand in that image
      (`python -m build` -> `auditwheel repair` -> install -> upstream's `test-command`):
      same evidence gotcha 52 asks for, one stage earlier.
    - **Read the dependency configuration out of upstream's vcpkg manifest instead of
      guessing.** `ci/vcpkg.json`'s `"default-features": false` on libspatialite is what
      said to configure it `--disable-freexl --disable-rttopo`; matching it keeps the
      wheel's feature set upstream's rather than one you invented.

142. **cibuildwheel copies the **whole working directory** into the container, not just
    `package-dir` — which is what makes a sibling C/C++ tree buildable from `before-all`
    (the google-re2 case; see `build-google-re2.yml`).** Gotcha 5 distinguishes
    `{project}` from `{package}` but leaves the impression that a `package-dir`
    subproject is all the container sees. It is not: `platforms/linux.py` does
    `container.copy_into(Path.cwd(), "/project")` and then sets
    `container_package_dir = /project/<package-dir relative to cwd>`. So for a repo whose
    Python bindings live in `python/` beside the C++ library they link, `cibuildwheel
    python` gives `before-all` the *entire* checkout at `{project}` — enough to
    `cmake -S {project}` the library, install it, and have the ordinary setuptools build
    of the bindings link it. No sdist juggling, no second checkout.
    - **`test-sources` paths are relative to the cwd, not to `package-dir`**
      (`copy_test_sources(..., Path.cwd(), test_cwd, ...)`), and keep their position
      relative to it exactly as gotcha 36 describes. With `package-dir: python`, staging
      upstream's suite is `CIBW_TEST_SOURCES: python/re2_test.py` and the command is
      `python python/re2_test.py` — and because only that one file is staged,
      `test_cwd/python/` has none of the checkout's importable modules, so the wheel is
      necessarily what gets imported (gotcha 25's fix, for free).
    - **The container's environment is not the runner's**: `oci_container.py` passes only
      `--env=CIBUILDWHEEL` and `--env=SOURCE_DATE_EPOCH`, and the rest of `env` comes from
      running `env` *inside* the container. Gotcha 49 uses the forwarded `CIBUILDWHEEL`;
      the complement matters just as often — **`GITHUB_ACTIONS` is absent in there**. A
      `setup.py` that branches on it (`if 'GITHUB_ACTIONS' not in os.environ: return
      super().build_extension(ext)` — re2 shells out to Bazel otherwise) therefore takes
      its non-CI path on its own, with nothing to override. Read that branch before
      concluding a Bazel-only upstream needs gotcha 47's bootstrap: the fallback is often
      the plain setuptools build every distro packager uses, and on riscv64 it is the only
      one that can run at all.

202. **A monorepo's "regenerate deps from Bazel" helper may already tolerate a missing
     bazel binary — check its exception handling before bootstrapping Bazel just to run it
     (the inverse of gotcha 47).** grpc's `tools/distrib/python/make_grpcio_tools.py`
     copies the C++/proto sources grpcio-tools' `setup.py` needs (step 1, plain file
     copies, no Bazel), then tries to regenerate `protoc_lib_deps.py` via `bazel query`
     (step 2) — wrapped in a bare `except Exception: return` that leaves the
     already-committed deps file untouched on failure. Confirmed by running it for real
     against a fresh `v1.83.1` checkout with no bazel installed: it printed a non-fatal
     traceback and kept going, and every one of the 369 `CC_FILES` + 15 `PROTO_FILES` the
     pre-generated `protoc_lib_deps.py` references still resolved against the checkout.
     Verify a script's fallback directly — run it, read the `except` clause — rather than
     assuming a Bazel-adjacent monorepo always needs Bazel bootstrapped for a build step
     that only *regenerates* a file already checked in for the tag you're building.

219. **GDAL's cmake build produces no `gdal-config` script — a second consumer of the
     gotcha-136 image needs `BUILD_APPS=ON`, not the flags that already worked for the
     first one (the rasterio case; see `build-rasterio.yml`).** Gotcha 136 replaces
     upstream's vcpkg image with one that compiles GEOS/PROJ/SpatiaLite/GDAL from source,
     and pyogrio's version of that image sets `-DBUILD_APPS=OFF` because pyogrio's own
     build script reads `GDAL_INCLUDE_PATH`/`GDAL_LIBRARY_PATH` env vars directly. rasterio
     links the same GDAL but has no such env-var path: `setup.py` calls `gdal-config`
     first, and GDAL's modern cmake build — unlike its old autotools one — never generates
     that script (confirmed: `gdal-config.in`/`gdal-config` are absent from the v3.12.4
     tag entirely, and GDAL's own docs say the cmake config-file approach replaced it).
     `setup.py`'s fallback is the `gdalinfo` binary on `PATH`, which only exists with
     `BUILD_APPS=ON` — so a source-built GDAL image tuned for one riscv64 consumer is not
     automatically right for the next one, and the two projects' own build mechanisms (not
     a version bump) are what decide the flag.
     - **Reusing the version pins is still worth it even when the image itself must
       differ.** GEOS/PROJ/SpatiaLite/GDAL version numbers that already proved they
       compile together on riscv64 (a prior port's merged workflow) de-risk a second image
       even though `BUILD_APPS` differs and the two Dockerfiles cannot share a GHA cache
       scope (every `RUN` layer after the first difference invalidates).
     - **`gdal_data`/`proj_data` need no env var either**, once `gdalinfo` exists:
       `setup.py`'s `fill_gdal_build_options_using_executable` derives `GDAL_DATA` as
       `<prefix>/share/gdal` from the binary's own path, and its `PROJ_DATA` default
       (`/usr/local/share/proj`) matches a plain `CMAKE_INSTALL_PREFIX=/usr/local` build —
       so `PACKAGE_DATA=1` alone is enough in `CIBW_ENVIRONMENT`, no `GDAL_DATA`/`PROJ_LIB`.
     - **A raster-format project needs the image's codec `-devel` packages that a
       vector-format one (pyogrio: OGR only) does not.** GDAL's cmake falls back to an
       *internal* vendored copy for some optional codecs (PNG, GIF — `gdal_internal_library`
       in `CheckDependentLibraries.cmake`) but not others (JPEG, WebP, OpenJPEG, zstd, lz4 —
       `CAN_DISABLE` only, silently dropped with no system lib), so a raster test suite
       needs `libjpeg-turbo-devel libpng-devel giflib-devel libwebp-devel openjpeg2-devel
       libzstd-devel lz4-devel json-c-devel` (all present in Rocky 10 appstream/crb on
       riscv64) added to the image's `dnf install`, or entire driver families silently
       aren't there to test.

233. **A package can have no Python build backend at all — the wheel comes from an
    external packer tool with its own platform table (the sqlite-vec case; see
    `build-sqlite-vec.yml`).** Gotcha 15's "drive the container yourself" is for a
    *heavy* C++ build cibuildwheel can't reach; this is the opposite shape: sqlite-vec's
    repo carries no `setup.py`/`pyproject.toml` at all. `make loadable` compiles one C
    file (`sqlite-vec.c`, linked against a vendored SQLite amalgamation fetched by
    `scripts/vendor.sh`) into a loadable `.so`, and a *separate* Rust CLI in its own repo,
    `asg017/sqlite-dist`, assembles the actual pip wheel by hand-writing dist-info files
    and zipping them. That tool's `src/targets/pip.rs::platform_target_tag()` is a bare
    `match (os, cpu)` over `{macos,linux,windows}×{x86_64,aarch64}` ending `_ =>
    unreachable!()`, so it cannot target riscv64 at any version. cibuildwheel doesn't
    apply — there is no `pip wheel` invocation for it to wrap — so the workflow
    reproduces the packer's own templates (`base_init_py`, `dist_info_metadata`/`WHEEL`/
    `RECORD`) inline as a `run:` heredoc Python script, matching its exact wheel shape
    (`py3-none-<platform>` tag, `<pkg>/__init__.py` plus the loadable file,
    `.dist-info/licenses/`) so the artifact is indistinguishable from one the real tool
    would produce for a supported arch.
    - **Read the *wheel*, not the repo, to find the packer.** `unzip -p <whl> '*/WHEEL'`
      names it (`Generator: sqlite-dist 0.0.1-alpha.22`); its GitHub repo is then one
      `gh repo view` away, and — if public, as here — its wheel-writing source is the
      spec to copy, far cheaper than reverse-engineering the dist-info layout from wheel
      bytes alone.
    - **Validate the hand-written wheel by running upstream's own test suite against
      it**, not just `unzip -l`. `make loadable && uv sync --directory tests && make
      test-loadable` is upstream's real CI step; running it against the riscv64-built
      `.so` (91 passed, 4 skipped here, matching the x86_64/aarch64 jobs' skip count) is
      stronger evidence than a green build, since the packaging step itself carries zero
      test coverage anywhere in upstream's own pipeline — `release.yaml` runs
      `sqlite-dist build` and uploads straight to PyPI with no test in between.
    - **The rebuilt tool needs only the one code path this port exercises, not feature
      parity.** `sqlite-dist`'s `pip` target also emits `datasette`/`sqlite_utils`
      sibling wheels and `entry_points.txt` shims for other targets; only
      `write_base_packages` (the base `pip` wheel) matters here, so the heredoc
      reproduces that function alone and ignores the rest of the tool.

397. **A CMake build that shells out to a bare `python3` for one vendored sub-extension
    silently builds it for the container's default interpreter, not the one the wheel is
    for (the coremltools/kmeans1d case).** Driving the container yourself means every
    per-interpreter loop iteration passes the interpreter explicitly — `-DPYTHON_EXECUTABLE`,
    `$PYBIN/python3`, a venv — and that covers the targets CMake compiles itself. It does not
    cover an `execute_process(COMMAND python3 setup.py build_ext --inplace WORKING_DIRECTORY
    ${DEPS}/kmeans1d)` buried in the same `CMakeLists.txt`: that resolves `python3` from
    `PATH` at *configure* time, so a `-DPYTHON_EXECUTABLE=/opt/python/cp312-cp312/bin/python3`
    build happily ships `_core.cpython-311-<arch>-linux-gnu.so` inside a cp312 wheel. It is
    invisible in a green build and a green import — the module is only imported by the
    palettization code path, so the whole suite can pass — and `unzip -l <whl> | grep '\.so'`
    is what catches it.
    - **Upstream never sees it** because its own build script activates a conda env first,
      making `python3` and `PYTHON_EXECUTABLE` the same binary. Reproducing that is one line
      in the build script — `export PATH="$PYBIN:$PATH"` before `cmake` — and is strictly
      safer than auditing every `execute_process` for the hardcoded name.
    - **Grep for the bare interpreter name, not for `PYTHON_EXECUTABLE`.** `grep -rn
      'COMMAND python' CMakeLists.txt cmake/` finds both this and the `python -m lib2to3`
      style post-processing steps that protobuf codegen rules commonly carry; the ones that
      use `${PYTHON_EXECUTABLE}` are already correct, and the ones that do not are the list
      the PATH export exists to cover.

421. **`pierotofy/set-swap-space` is a no-op on the riscv64 runners — a heavy link gets
    the runner's 15GB of RAM and nothing behind it.** The step goes green in under a
    second either way: the action creates and `mkswap`s `/swapfile`, then swallows
    `swapon: /swapfile: swapon failed: Invalid argument` behind its own
    `WARNING: swapon failed ... Continuing without swap.` line. The cause is one line
    above it in the log — `Creating swapfile at /swapfile on filesystem type: overlay`
    — and a swap file has to live on a block-backed filesystem, so no size, no
    allocation method and no `swap-size-gb` value fixes it. Two different runners in the
    fleet (a failed paddlepaddle build and a *green* deltalake one) report it
    identically, so treat it as the whole fleet.
    - **Copying the step from `build-vtk.yml` does not buy the headroom its comment
      claims.** Ten workflows carry it today and every one of them is really building
      inside `free -h`'s 15Gi. Size the link to that instead: shared libraries rather
      than one monolithic `.so` (Paddle's `WITH_SHARED_PHI`/`WITH_SHARED_IR`, VTK's
      per-module objects), and expect to cap the parallel job count if the tail of the
      build is what OOMs.
    - **Read a soft-failing action once instead of trusting its conclusion.** A
      `##[end-action ... outcome=success` sitting next to a `WARNING:` in the same step
      is the shape; `swapon --show` in the action's own "after" report printing `0B` is
      the proof.

423. **A depot_tools/gclient checkout (V8, Chromium, Skia, ANGLE) cannot download a
    single GCS dependency on riscv64 until `VPYTHON_BYPASS` is set.** `gclient sync`
    dies minutes in, on whichever `dep_type: 'gcs'` entry it reaches first (for V8 that
    is `third_party/llvm-build/Release+Asserts`), with the resolver error nested inside
    a gclient traceback:
    ```
    Exception: 1: [E...] Creating virtual environment at: .../vpython-root.0/store/uv_venv-...
      × No solution found when resolving dependencies:
      ╰─▶ Because crcmod==1.7+chromium.4 has no wheels with a matching
          platform tag (e.g., `manylinux_2_39_riscv64`) ...
    ```
    Every gcs dep *and* every `download_from_google_storage.py` hook (V8's
    `wasm_spec_tests`, `wasm_js`, `bazel`, `gcmole`, ...) is run as
    `vpython3 gsutil.py`, and `depot_tools/gsutil.vpython.toml` pins
    `crcmod==1.7+chromium.4`, which chromium's wheel mirror builds for
    x86_64/aarch64/arm/mac/windows only. It is the *venv* that is unbuildable, not the
    tool.
    - **The fix is depot_tools' own escape hatch**, as a job-level env var:
      `VPYTHON_BYPASS: manually managed python not supported by chrome operations`
      (the literal string `vpython3` compares against — anything else is ignored).
      `vpython3` then execs `python3` from `PATH`, and gsutil uses crcmod only as an
      optional hash accelerator, so the download just works. It also makes the DEPS
      `vpython3_common` hook (`vpython3 -vpython-tool install`), which would resolve the
      same riscv64-less wheel set, exit 0 — the bypass short-circuits any
      `-vpython-tool*` argument.
    - **Nothing else in depot_tools is missing for riscv64**, so do not conclude the
      approach is dead: `cipd_client_version.digests` carries a `linux-riscv64` line, and
      `infra/3pp/tools/cpython3/linux-riscv64` (the hermetic python) and
      `infra/tools/luci/vpython3/linux-riscv64` both exist. A
      `Platform linux-riscv64 is not supported by the CIPD client bootstrap` line in the
      same log is a **red herring from a relative invocation**: `cipd` derives
      `DEPOT_TOOLS_DIR` from `$0`, so `depot_tools/gclient --version` leaves it looking
      for `depot_tools/cipd_client_version.digests` after it has cd'd into depot_tools.
      Invoke these entry points through an absolute path (`"${PWD}/depot_tools/gclient"`).
    - **Rehearse it for the price of a clone**, no source checkout and no build: in
      `quay.io/pypa/manylinux_2_39_riscv64` under qemu-riscv64, clone depot_tools and run
      gclient's own gcs code path against the one object that failed —
      `python3 -c "import download_from_google_storage as d;
      print(d.Gsutil(d.GSUTIL_DEFAULT_PATH).check_call('cp', '<gs://url>', '/tmp/o'))"`
      is literally what `gclient.py`'s `DownloadGoogleStorage` calls. It reproduces the
      resolver error bare and returns 0 under the bypass.

424. **Audit a chromium-style DEPS for riscv64-less CIPD packages with `cipd describe`
    before you spend a build cycle discovering them one at a time.** gclient aborts on
    the first unavailable package, so a checkout with three missing ones costs three
    cycles — and for a project like V8 each cycle is the whole fetch+sync. Two commands
    settle it from an x86 host, because the CIPD *registry* is arch-independent:
    `depot_tools/cipd describe <pkg>/linux-riscv64 -version <the pin from DEPS>` and
    `depot_tools/cipd ls <pkg-prefix>` for the list of platforms that do exist. For V8
    13.1.201.22: `gn/gn/linux-riscv64` and `infra/3pp/tools/ninja/linux-riscv64` are
    published, while `infra/rbe/client` (reclient), `infra/build/siso` and
    `infra/tools/luci/{isolate,swarming}` are not.
    - **Enumerate the candidates mechanically rather than by eye**, with depot_tools'
      own evaluator: for every `cipd`/`gcs` block in DEPS,
      `gclient_eval.EvaluateCondition(cond, {"host_os": "linux", "host_cpu": "riscv64",
      "build_with_chromium": False, ...})` says whether riscv64 will try to fetch it.
      That is also the check that proves a DEPS patch does what it claims: the same
      evaluation after the edit must leave gn and ninja `True` and the unpublished ones
      `False`.
    - **You cannot fix this by lying about `host_cpu`**, because the conditions gating
      the packages that *are* published have the same shape
      (`host_cpu != "s390" and host_os != "zos" and ...`) as the ones that are not —
      excluding riscv64 wholesale would drop gn and ninja too. Append
      `and host_cpu != "riscv64"` to the conditions of the missing packages only, and
      keep them in one list so the next version bump has one place to re-verify.

427. **`VPYTHON_BYPASS` decides *which interpreter* gsutil gets, and a chromium-style
    checkout carries two gsutils of different ages — the one its DEPS pins is the one that
    breaks on python ≥ 3.12.** Gotcha 423's bypass is what makes gsutil runnable on riscv64
    at all, but it also replaces vpython's hermetic 3.8 with whatever `python3` is on PATH
    (in `manylinux_2_39_riscv64` that is 3.12). V8's DEPS pins its own
    `third_party/depot_tools`, whose `gsutil.py` bootstraps **gsutil 4.68**, which vendors
    **six 1.12**, whose `_SixMetaPathImporter` only implements the legacy `find_module()`
    that CPython **removed in 3.12** — so every hook shelling out to
    `third_party/depot_tools/download_from_google_storage.py` dies half an hour into the
    sync, long past the gotcha 423/424 walls:
    ```
    File ".../external_bin/gsutil/gsutil_4.68/gsutil/gslib/__main__.py", line 36
        from six.moves import configparser
    ModuleNotFoundError: No module named 'six.moves'
    ```
    - **Nothing about this needs riscv64 to reproduce** — it is purely the interpreter, so
      settle it on the x86 host in seconds instead of in CI:
      `curl -sO https://storage.googleapis.com/pub/gsutil_4.68.zip && unzip -q gsutil_4.68.zip`,
      then `python3.11 gsutil/gsutil version` prints `4.68` while `python3.12 gsutil/gsutil
      version` raises the CI traceback verbatim.
    - **The first-class `dep_type: 'gcs'` deps are unaffected**, which is exactly why the
      sync now gets as far as the hooks: those run through the gsutil of the *outer*
      depot_tools clone driving the sync (5.35, six 1.17). Read the gsutil version out of the
      traceback path, not out of your own clone. That the deps came down is also how you
      learn the container's `python3` is 3.12 — gsutil 5.35 dies on 3.13 in its vendored
      `cryptography`, so a newer container python moves this wall rather than removing it.
    - **Condition the offending hooks off; do not chase interpreters.** With V8
      13.1.201.22's default DEPS vars only `wasm_spec_tests` and `wasm_js` reach gsutil, and
      both only unpack test suites a `v8_monolith` build never reads. Inject
      `'condition': 'host_cpu != "riscv64"'` into those two hook dicts from the same
      post-checkout DEPS edit that carries gotcha 424's CIPD conditions, and prove it the
      same way — `gclient_eval.Parse` then `EvaluateCondition` over `local_scope["hooks"]`
      must drop exactly those two for `host_cpu: riscv64` and change nothing for x64.
    - **Audit the hooks that run *after* the failing one in the same pass**, since they own
      the next unattended half hour, and rehearse them locally for free: V8's `lastchange`
      is pure git, `vpython3_common` exits 0 because depot_tools' `vpython3` wrapper returns
      0 for any `-vpython-tool*` argument under the bypass, and `configure_reclient_cfgs
      --skip_remoteexec_cfg_fetch` and `configure_siso` each only template one cfg file —
      copy those two scripts out of `buildtools`/`build` (plus
      `reclient_cfgs/reproxy_cfg_templates/`) and run them with the arguments DEPS passes.

432. **A monorepo that vendors its C++ dependencies as git submodules *and* has CMake
    "fix up" their versions with `git checkout <tag>` builds the stale recorded commit in
    CI, because `actions/checkout` clones submodules without tags — and the only sign is a
    one-line warning hundreds of lines before the real error (the paddlepaddle case).**
    Paddle's `cmake/external/openblas.cmake` runs `git describe --abbrev=6 --always --tags`
    in `third_party/openblas`, compares it to `CBLAS_TAG` (`v0.3.28` on Linux) and, on a
    mismatch, runs `git checkout ${CBLAS_TAG}` — with `execute_process` and **no
    `RESULT_VARIABLE`**, so nothing checks that it worked. In a CI checkout it cannot:
    `submodules: true` fetches the pinned commit and no tags, so `describe` returns a bare
    abbreviated hash and the checkout fails with `error: pathspec 'v0.3.28' did not match
    any file(s) known to git`. Configure then completes normally against whatever commit
    the monorepo actually recorded — for Paddle v3.3.1 that is `5f36f18`, a 0.3.7-era
    OpenBLAS whose `getarch.c` has no riscv64 target at all, so 33 minutes later the build
    dies at `getarch.c: error: #error "This arch/CPU is not supported by OpenBLAS."`
    against a version that has supported riscv64 for years.
    - **Read the configure output for `checkout`/`pathspec`/`describe` noise before
      reading the compiler error.** `error: pathspec '<tag>' did not match` and a
      `version is not <hash>, checkout to <tag>` warning are the same event, and they name
      the dependency whose source tree is not what the version numbers in the build log
      claim. Grepping the job log for `did not match any file` costs nothing and is worth
      doing on *every* submodule-vendoring project, since upstream never notices: on
      x86-64 the stale tree still autodetects the host and builds.
    - **Fix it in the workflow, not the patch: move the submodule to the tag the project's
      own CMake asks for.** One shallow tag fetch in the submodule (`git fetch --depth 1
      origin tag <tag>` then `git checkout <tag>`, under `working-directory:`) makes
      `describe` agree with `CBLAS_TAG`, so upstream's own version logic goes quiet
      instead of being patched out. Do not `git fetch --tags` — that pulls every tag's
      tree. The alternative, deleting the submodule directory so the project's
      `file(GLOB)`-guarded `git clone -b <tag>` branch runs instead, costs a full clone of
      the dependency inside the configure step.
    - **Check the *recorded* submodule commit against the version the build advertises.**
      The checkout step prints `Submodule path 'third_party/<dep>': checked out '<sha>'`;
      resolve that sha upstream before believing any tag name in the CMake. A file's line
      count is enough to tell two releases apart — the `#error` in the failing
      `getarch.c` was at line 1193 where v0.3.28 has it at 1853.

434. **Any `ExternalProject_Add` under a project-wide log-to-file setting (`LOG_CONFIGURE
    1`, Paddle's `EXTERNAL_PROJECT_LOG_ARGS`) reports a failed dependency as `Command
    failed: 1` and nothing else — add an `if: failure()` step that prints the stamp logs,
    or the round costs you the diagnosis as well as the build.** The job log gives the full
    `cmake` command line and the path of the log it *would* have told you about
    (`<build>/third_party/<dep>/src/<dep>-stamp/<dep>-configure-*.log`), which is on the
    runner's disk and gone when the job ends. The steps that are logged to file are exactly
    the cheap ones (configure, install) — `LOG_BUILD 0` means the compiler errors you can
    already see are the ones that were never hidden.
    - **The dump is one step, and it applies to every dependency at once**, because the
      stamp-log layout is fixed: `tail -n 40 -v <build>/third_party/*/src/*-stamp/*-*-*.log
      || true`, guarded by `if: failure()`. Put it straight after the build step; a
      container build that bind-mounts the source tree leaves the logs on the host, so the
      step needs no container of its own.
    - **Do not spend a round proving which of several candidate causes it was.** A
      dependency you can take from the image (gotcha 401's Rocky packages) instead of
      building removes the failure class rather than diagnosing it, and one fewer
      `ExternalProject` is a real saving on a 4-core riscv64 runner.

437. **When gotcha 432's `git checkout <tag>` sits in an `ExternalProject_Add`
    `PATCH_COMMAND` instead of an unchecked `execute_process`, the tagless submodule clone
    does not build the stale tree quietly — it aborts the whole build, and there is one of
    these per dependency, so enumerate them all in one round instead of paying a CI cycle
    each.** Paddle's `gloo.cmake` sets `PATCH_COMMAND git checkout -- . && git checkout
    ${GLOO_TAG}`, so run 5 of the paddlepaddle port died 40 minutes in, at 6% with the
    project's own C++ tree still untouched, on `Performing patch step for 'extern_gloo'` /
    `error: pathspec 'v0.0.3' did not match any file(s) known to git`. Same cause as 432,
    opposite symptom: fatal and named, rather than silent and diagnosed hours later.
    - **Check whether the recorded commit already *is* the tag before moving anything.**
      `git ls-tree <tag> third_party/<dep>` in a `--filter=blob:none --no-checkout --depth 1`
      clone of the monorepo gives the gitlink, and `git ls-remote <dep-url> refs/tags/<tag>
      refs/tags/<tag>^{}` gives the tag's commit — for gloo both were `8b6b61d`, and for
      protobuf the gitlink `f0dc78d` was `refs/tags/v21.12^{}`. When they match, the tree is
      already right and only the *ref* is missing: `git fetch --depth 1 origin tag <tag>` in
      the submodule is the whole fix, with no checkout of your own and no tree change.
      Prefer that fetch over `git tag <tag>` pointing at HEAD — the fetch stays correct, and
      keeps failing loudly, if a later version bump moves the gitlink off the tag.
    - **Sweep every `cmake/external/*.cmake` for the pattern in one pass, then split the
      hits by whether the tag is a name or a commit.** `grep -rn 'checkout'
      cmake/external/` plus the `set(<DEP>_TAG ...)` lines is enough: a `*_TAG` that is a
      SHA is safe, because the recorded commit is the one `actions/checkout` fetched, while a
      tag or branch *name* is a live failure unless its `if()` is false in your
      configuration. For Paddle v3.3.1 on riscv64 that left exactly two live (gloo,
      protobuf — the second being an unconditional `cd <src> && git checkout v21.12` in
      `build_protobuf()`, which `find_package` only skips if the image ships that exact
      version), against tag-name checkouts already gated off by `GCC < 9` (pybind11),
      `APPLE` (pocketfft), `WITH_TESTING OR WITH_DISTRIBUTE` (gtest), CUDA (cub, cccl, the
      `paddle/fluid/fp8` cutlass switch), `WITH_OPENVINO`, and the parameter-server tree
      (rocksdb).
    - **Rehearse it off-target in seconds: the CI state is reproducible exactly.** `git init`,
      `git remote add origin <url>`, `git fetch --depth 1 origin <recorded-sha>`, `git
      checkout FETCH_HEAD` is what `git submodule update --init` leaves behind; the tag
      checkout then fails with the identical `pathspec` line, the tag fetch fixes it, and
      `git rev-parse HEAD` proves the commit did not move. No riscv64 runner needed.
