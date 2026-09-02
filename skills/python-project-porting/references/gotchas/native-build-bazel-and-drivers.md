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
      result for `publish-wheels`' `gpl-sources-artifact`. ports.ubuntu.com does carry
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
