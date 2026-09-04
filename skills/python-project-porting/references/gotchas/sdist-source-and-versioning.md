# Gotchas — Sdist source & versioning

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/sdist-source-and-versioning.md`.

## In this file

- **1** — Not every project can build an sdist from its git checkout.
- **2** — The PyPI sdist is often self-contained and architecture-independent
- **3** — Git tag ≠ Python package version.
- **4** — Build arch-independent artifacts on `ubuntu-latest`, not the riscv runner.
- **18** — The wheel-filename version is canonical; keep three places in sync
- **22** — A release-branch checkout can carry `[egg_info] tag_build = dev` in
- **31** — `git apply` onto a `setuptools_scm` checkout renames the wheel (the lz4 case).
- **43** — Upstream may not be on git at all — look for the author's own read-only git
- **103** — An upstream on GitHub that publishes releases without ever pushing a git tag —
- **135** — A version placeholder that upstream's *release script* stamps is a fourth way to
- **154** — A PyPI `project_urls` repository link can 404 — search for the live repo before
- **156** — An upstream that exists only as a PyPI sdist is still an ordinary port — but
- **213** — Gotcha 103's timestamp-proximity trick can point at the wrong commit when

---

1. **Not every project can build an sdist from its git checkout.** protobuf's
   `setup.py` only works from an already-assembled source package — the README says
   so explicitly: the real sdist is produced by Bazel and bundles generated code
   (`*_pb2.py`) + vendored C. Always check upstream docs before assuming.

2. **The PyPI sdist is often self-contained and architecture-independent** — it
   bundles generated sources so building the bdist from it needs **no** codegen
   toolchain, even though building from the repo does. Confirm with the local
   `pip wheel` test in step 2.

3. **Git tag ≠ Python package version.** protobuf tags are `vNN.M` (`v35.1`) but the
   package is `7.NN.M` (`7.35.1`). Never hardcode the version twice. Take the tag as
   input and derive the version from the sdist filename:
   ```bash
   package_version="$(echo "$sdist_name" | sed -En 's/<pkg>-(.+)\.tar\.gz/\1/p')"
   ```
   For `setuptools_scm` projects built from a *shallow* checkout (no tag history),
   `git describe` can't see the version — pin it with
   `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_<PKG>=<ver>` instead.

4. **Build arch-independent artifacts on `ubuntu-latest`, not the riscv runner.**
   The sdist and any `py3-none-any` helper wheels don't depend on arch — build them
   once on x86. Only the actual bdist needs `ubuntu-24.04-riscv`. Building a codegen
   toolchain (e.g. protoc via Bazel) on riscv is a dead-end; don't attempt it.

18. **The wheel-filename version is canonical; keep three places in sync** (see
    PR #246, which fixed broken doc links from exactly this). Whatever version ends
    up in the `.whl` filename (driven by `BUILD_VERSION`) must match, byte for byte:
    (1) the wheel filename, (2) the `docs/packages/<pkg>.yaml` `version:` key
    (auto-populated by `update_doc.py` from the wheel), and (3) the
    `patches/<pkg>/<version>/` directory name — `generate_packages_doc.py`
    links patches as the literal path `patches/{name}/{version}`, so a mismatch is a
    404. torch ships a **local segment** (`2.13.0+cpu`, pytorch's CPU-index
    convention) so its patches live under `patches/torch/2.13.0+cpu/`.
    **Match upstream's own PyPI filename convention** — if a package ships plain
    `X.Y.Z` on PyPI, build plain `X.Y.Z` (no `+cpu` or other local segment).
    Decoupled from all this: the nightly `check_versions.py` compares the workflow's
    `version:` **input default** against PyPI — keep that the plain upstream version,
    regardless of any local segment `BUILD_VERSION` adds.

22. **A release-branch checkout can carry `[egg_info] tag_build = dev` in
    `setup.cfg`, poisoning the wheel version with `.dev0`** (the SQLAlchemy variant
    of gotcha 3/18). `python -m build --sdist` from the tag then emits
    `<pkg>-<ver>.dev0.tar.gz`, and every wheel built from it inherits `.dev0` —
    breaking the wheel-filename-is-canonical rule (gotcha 18: docs YAML `version:`
    and `patches/<pkg>/<version>/` path both derive from it, and the nightly PyPI
    check compares against the clean upstream version). The released PyPI sdist has
    the tag blank because upstream strips it at release; do the same before building:
    ```bash
    sed -i '/tag_build = dev/d' setup.cfg
    ```
    Tell-tale: your locally-built sdist version has a `.dev0`/`.devN` suffix the PyPI
    sdist doesn't. Distinct from setuptools_scm dev suffixes (missing tag history —
    fix with `SETUPTOOLS_SCM_PRETEND_VERSION`, gotcha 3); this one is a literal line
    in `setup.cfg`. Confirm by diffing your sdist's `setup.cfg` against the released
    PyPI sdist's.

31. **`git apply` onto a `setuptools_scm` checkout renames the wheel (the lz4 case).**
    A third route to a poisoned version, distinct from gotcha 3 (shallow checkout, no tag
    history) and gotcha 22 (`tag_build = dev` in `setup.cfg`): patching the upstream tree
    leaves it **dirty**, and `setuptools_scm` reads a dirty tree at a tag as post-release —
    `4.4.5` silently becomes `4.4.6.dev0+g59b2d817.d20260825`. That flows straight into the
    wheel filename and breaks gotcha 18's three-way match (the docs YAML `version:`, the
    `patches/<pkg>/<version>/` directory the patch itself lives in, and the nightly PyPI
    check all key off it). Committing the patch instead of leaving it unstaged does **not**
    help — `git describe` then reports `4.4.6.dev1+g<sha>`. Pin the version explicitly:
    ```yaml
    CIBW_ENVIRONMENT: >-
      ... SETUPTOOLS_SCM_PRETEND_VERSION_FOR_<PKG>=${{ env.<PKG>_VERSION }}
    ```
    `<PKG>` is the *distribution* name upper-cased with `-`/`.` → `_`. Once it's set
    setuptools_scm never consults git, so a `fetch-depth: 0` that existed only to make the
    tag reachable becomes dead weight — drop it in the same commit rather than leaving two
    mechanisms fighting over the version. **Costs nothing to catch**: a `pip wheel .` on any
    host prints the filename, so the wrong version is visible before you push.

43. **Upstream may not be on git at all — look for the author's own read-only git
    mirror before building a fetch step (the ruamel.yaml.clib case).** PyPI's
    `project_urls` pointed only at a SourceForge **Mercurial** repo, which
    `actions/checkout` cannot fetch, and neither fallback is workable: SourceForge
    serves the anonymous hg endpoint over **http only** (https answers 401), and its
    snapshot-tarball URL returns the commit *page*, not an archive. Do not conclude
    from that that the sdist must be the CI input — check whether upstream keeps a git
    mirror, because a project whose own CI is GitHub Actions necessarily has one.
    `gh api "search/repositories?q=<name>+in:name&sort=updated"` found `ruamel/yaml.clib`
    (the author's, carrying every release tag and the `build_wheels.yaml` upstream
    actually runs); checking it out is *closer* to upstream than any sdist route, so the
    port collapses to the ordinary build-from-checkout shape.
    - **Rank candidates by freshness, not by name.** The obvious-looking mirror
      (`pycontribs/ruamel-yaml-clib`, "read-only git mirror from official hg repository")
      had stopped at 0.2.8 in 2023. Sorting the search by `pushed_at` is what surfaced
      the live one.
    - **Prove the tag is the release before trusting it**: `gh api repos/<m>/tarball/<tag>`
      and diff against the PyPI sdist (`setup.py`, `pyproject.toml`, `LICENSE`, the
      vendored C) — identical files mean the mirror is a faithful export, not a fork.
      Say so in the commit message; a reviewer will ask why the checkout isn't upstream.

103. **An upstream on GitHub that publishes releases without ever pushing a git tag —
    pin the release commit and prove it against the PyPI sdist (the dbt-extractor case).**
    Gotcha 43 covers upstream not being on git at all; this is the commoner, quieter shape:
    the repo is right there, its own release workflow is `workflow_dispatch`-only, and
    `gh api repos/<o>/<r>/git/refs/tags` answers **404** — dbt-labs/dbt-extractor has shipped
    six releases and zero tags. A `ref: v${{ env.<PKG>_VERSION }}` checkout then fails at
    the first step, and `main` is not a substitute: it drifts (dependabot bumps) and is not
    what PyPI holds.
    - **Find the release commit by timestamp, not by message.** The sdist's
      `upload_time_iso_8601` from the PyPI JSON brackets it: the version-bump/changelog
      commit minutes earlier is the one (`89d4672` "bump patch version, add changelog", sdist
      uploaded 12 minutes later). `gh api "repos/<o>/<r>/commits?path=Cargo.toml"` (or
      `setup.py`/`pyproject.toml`/`__init__.py`) narrows the candidates to a handful.
    - **Prove it, don't infer it** — same discipline as gotcha 43's mirror check:
      `gh api repos/<o>/<r>/tarball/<sha>` and diff the manifest, the lock file, `LICENSE`,
      all of the sources and the changelog against the released sdist. Byte-identical means
      the commit *is* the release; a diff means you picked the wrong one (or upstream
      post-processes at release time, which changes the port's shape).
    - **Keep the version and the ref as two env vars.** `<PKG>_VERSION` stays the plain
      upstream version so the nightly `check_versions.py` PyPI comparison and the artifact
      pattern keep working; `<PKG>_REF` carries the sha, with a comment saying to move both
      together. Do **not** collapse them by feeding the sha to the `version:` input — that
      poisons the wheel-filename/docs-YAML match of gotcha 18.

135. **A version placeholder that upstream's *release script* stamps is a fourth way to
    ship a mis-named wheel (the awscrt case).** Gotchas 3, 22 and 31 cover a version that
    goes wrong at build time — no tag history, a `tag_build = dev` line, a dirty tree under
    `setuptools_scm`. This one is simpler and easier to miss: the version in git is a
    deliberate placeholder (`awscrt/__init__.py`: `__version__ = '1.0.0.dev0'`) that
    `setup.py` reads verbatim, and the real value is written by a script upstream runs as
    the **first line of its release job**, not by the build backend
    (`continuous-delivery/update-version.py`, which rewrites the file from
    `git describe --tags`). Build from a checkout without it and every wheel is
    `<pkg>-1.0.0.dev0-…`, breaking gotcha 18's three-way match while the build itself is
    perfectly green.
    - **Read the release script top to bottom before copying its build lines.** The
      `python -m build` calls are the part that catches the eye; a preceding
      `update-version.py` / `set_version.sh` / `bump` step is the part that matters. Same
      for a checkout: `grep -n version <pkg>/__init__.py` against the tag you are building
      settles it in one command.
    - **Run upstream's own script rather than sed-ing the file** — it is the smaller
      divergence — but assert the outcome so a `git describe` that returns something else
      fails in seconds instead of after the compile:
      ```yaml
      - run: |
          python3 continuous-delivery/update-version.py
          grep -q "__version__ = '${PKG_VERSION}'" <pkg>/__init__.py
      ```
      `actions/checkout` with `ref: v<ver>` does fetch that tag ref, so `git describe --tags`
      works on the shallow clone; the grep is what proves it.

154. **A PyPI `project_urls` repository link can 404 — search for the live repo before
    concluding upstream is not on git (a lighter cousin of gotcha 43).** Gotcha 43 covers a
    project genuinely off GitHub; the commoner cause of a dead link is an org rename that
    the released metadata still points at. burner-redis 0.1.7 records
    `Homepage`/`Repository`/`Issues` all under `github.com/PrefectHQ/burner-redis`, which
    answers 404 to `curl` *and* to `gh api repos/...` — while `gh api
    "search/repositories?q=<name>"` returns `prefectlabs/burner-redis`, carrying every
    release tag (`v0.1.0`…`v0.1.7`), the release workflow, and the MIT licence. A `gh api
    repos/<o>/<r>` 404 says nothing about whether the code is public, only that *that*
    path is not.
    - Check the tag you need actually exists there (`gh api repos/<o>/<r>/git/refs/tags`)
      and diff the tarball against the PyPI sdist before trusting it, exactly as gotcha 43
      does for a mirror — then say in the PR body why the checkout `repository:` differs
      from the URL on the PyPI page, because a reviewer will otherwise read it as a typo.

156. **An upstream that exists only as a PyPI sdist is still an ordinary port — but
    handing that tarball to cibuildwheel as `package-dir` silently breaks
    `test-sources` (the lmnr-claude-code-proxy case; see
    `build-lmnr-claude-code-proxy.yml`).** Gotcha 43 covers an upstream on Mercurial with
    a git mirror to find; the plainer case is an upstream with *no* public repository at
    all — PyPI records no `project_urls`, the vendor's GitHub org carries none of the
    crate (`gh api "search/code?q=org:<org>+<crate>"`), and the sdist plus a sibling npm
    package are the only published forms. The playbook's "always build the sdist yourself
    from an upstream checkout" then has nothing to check out, so fetching the released
    sdist *is* the closest available thing to upstream, and it should be said in the
    workflow header so a reviewer does not go looking for the repo.
    - **Extract it yourself; do not pass the `.tar.gz` to `package-dir`.** cibuildwheel
      supports the tarball (gotcha 6), but `__main__.py` extracts it to a temp dir and
      runs the whole build under `contextlib.chdir(project_dir)` — and
      `CIBW_TEST_SOURCES` is copied with `copy_test_sources(..., Path.cwd(), test_cwd)`
      (gotcha 104), so a `tests/` you staged in the workspace is not under that cwd and
      the run dies with `cibuildwheel: error: Test source tests does not exist` — **after**
      the entire compile, the auditwheel repair and the test-venv install. A plain
      `tar xzf` plus `package-dir: <pkg>-<ver>` keeps cwd at the workspace root, where
      both the extracted tree and the staged tests live (`linux.py` computes
      `container_package_dir = container_project_path / abs_package_dir.relative_to(cwd)`,
      so the package dir only has to sit *under* cwd).
    - **Upstream shipping no tests is not a reason to ship an import-only check.** For a
      package whose extension *is* a server, a smoke suite staged from a `run:` heredoc
      (gotcha 144) can drive it end to end — start it, hit its own endpoints, forward a
      request through it to a local `http.server` and assert the body comes back — which
      exercises the async runtime, TLS stack and HTTP client that make up the whole wheel.
      Validate the suite against upstream's **released** wheel on your own host first
      (gotcha 52): passing there is what makes it a test of our build rather than of your
      guesses about the API.
    - **A pure-Rust PyO3 crate cross-compiles as a pre-flight in under a minute** (gotcha
      124, applied to a wheel rather than a Go binary): in a `rust:trixie` container,
      `apt-get install gcc-riscv64-linux-gnu`, `rustup target add
      riscv64gc-unknown-linux-gnu`, then `cargo build --release --features <feat> --target
      riscv64gc-unknown-linux-gnu` with `CARGO_TARGET_RISCV64GC_UNKNOWN_LINUX_GNU_LINKER`,
      `PYO3_CROSS=1` and `PYO3_CROSS_PYTHON_VERSION` set. 183 crates including `ring`
      0.17.14 linked in 38s on an arm64 laptop, which settles the one arch-specific risk
      in such a tree (does every dependency have a riscv64 path?) before any runner time
      is spent.

213. **Gotcha 103's timestamp-proximity trick can point at the wrong commit when
    upstream batches releases (the lru-dict case).** lru-dict 1.4.1 is on PyPI with no
    `v1.4.1` tag — but unlike dbt-extractor, the sdist's `upload_time_iso_8601`
    (2025-11-02) sits **three and a half months** after the commit that actually bumped
    `pyproject.toml` to `1.4.1` (2025-07-28): upstream tagged `v1.4.0` then `v1.5.0`
    around it and apparently queued the 1.4.1 upload until a later batch of releases,
    so "the commit minutes before the upload" would land on unrelated Android/iOS
    workflow changes instead. **Match the literal version string, not the clock**:
    `gh api "repos/<o>/<r>/commits?path=pyproject.toml"` (or `setup.py`/`__init__.py`)
    and diff each candidate's patch for `version = "<ver>"` — the commit whose diff
    shows `-version = "1.4.0"` / `+version = "1.4.1"` is unambiguous regardless of when
    it was released. Still finish with gotcha 103's proof step (`gh api
    repos/<o>/<r>/tarball/<sha>` diffed file-by-file against the PyPI sdist) — a version
    match alone doesn't rule out later content-only commits.
