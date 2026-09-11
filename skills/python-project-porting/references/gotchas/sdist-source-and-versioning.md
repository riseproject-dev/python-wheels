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
- **352** — A gitlink with no `.gitmodules` entry breaks `actions/checkout`'s own
  persist-credentials cleanup, not the checkout itself.
- **213** — Gotcha 103's timestamp-proximity trick can point at the wrong commit when
- **242** — A third-party tree-sitter grammar's release tag can omit the generated
- **258** — A hardcoded download URL in a project's own build script can 403 automated
- **293** — The newest git tag is not necessarily the version to port — check whether
- **254** — A build-from-checkout can pick up a maintainer-only dev/coverage cflags
- **261** — A package can require its own compiled extension, plus a large downloaded
- **265** — A project's own version-detection script can read `GITHUB_REF` directly,
- **268** — A vendored C-core git submodule can have its own `git describe`-based
- **274** — A build-from-checkout package can tag releases in a format the version
- **319** — A release tag can exist, be reachable, and check out cleanly, yet still be the
- **315** — `versioneer` has no `SETUPTOOLS_SCM_PRETEND_VERSION` equivalent for gotcha 31's

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

275. **A live, legitimate `project_urls` repo link is not proof it holds the released
    sdist's source — it can belong to a same-family sibling project instead (the
    PyQt6-sip case).** Distinct from gotcha 154 (link is dead) and gotcha 156 (no
    repository exists at all): PyQt6-sip 13.12.0's PyPI metadata points at
    `github.com/Python-SIP/sip`, a real, actively-maintained repo by the same author —
    but that repo is the `sip` build-tool/code-generator (PyPI package `sip`, versioned
    independently at 6.x) and its tree has no `sip_core.c`/`sip_voidptr.c`, the actual
    C sources of the `PyQt6.sip` runtime module PyPI ships. The two projects share a
    maintainer and a name prefix, which is exactly what makes the link look right.
    Confirm before trusting it: `tar tzf` the PyPI sdist and check whether the linked
    repo's tree (`gh api repos/<o>/<r>/contents/`) contains the files the sdist actually
    ships, not just a plausible-sounding path. When it doesn't and no other repo search
    (gotcha 43/154's `gh api search/repositories`) turns one up either, treat it as
    gotcha 156's no-public-repository case — fetch the sdist directly and say so in the
    workflow header and queue notes, so a reviewer doesn't waste time on the dead-end
    link.

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

242. **A third-party tree-sitter grammar's release tag can omit the generated
    `src/parser.c` — only the official `tree-sitter/tree-sitter-*` repos commit it
    at every tag.** tree-sitter-ruby/php/typescript/embedded-template (all
    `tree-sitter/`-org) ship `parser.c` at their `vX.Y.Z` tags, so their workflows
    check out the tag and hand it straight to cibuildwheel. `alex-pinkus/tree-sitter-swift`
    does not: at plain tag `0.7.3`, `src/` holds only `grammar.json`/`node-types.json`/
    `scanner.c` — `parser.c` appears only on the separate `0.7.3-with-generated-files`
    tag, and that tag's `pyproject.toml` is stale (`version = "0.0.1"`, wrong
    `Homepage`), so checking it out instead of the real release is a trap, not a
    shortcut. Two more things don't transfer from the official-org precedent either:
    the tag itself has **no `v` prefix** (`ref: 0.7.3`, not `ref: v0.7.3` — check
    `gh api repos/<owner>/<repo>/tags` rather than assuming), and upstream's own
    `publish-pypi.yml` (via `tree-sitter/workflows`' reusable `package-pypi.yml`)
    regenerates the parser on every build with `tree-sitter generate` before
    packaging — that step, not the tag, is what makes the official repos' committed
    `parser.c` reproducible.
    - **The generator has no riscv64 binary.** `tree-sitter/setup-action/cli` downloads
      a prebuilt `tree-sitter-<os>-<arch>.gz` from the `tree-sitter/tree-sitter`
      release when the ref is a `v*` tag; the release only ships `linux-arm`/`arm64`/
      `powerpc64`/`x64`/`x86` (checked against `v0.27.0`) — no `linux-riscv64`, so the
      action 404s on the riscv64 runner. `tree-sitter generate` is pure codegen with no
      target-architecture dependence, so run it once in its own job on `ubuntu-latest`
      (gotcha 4's pattern), then hand the completed checkout to the riscv64 job as a
      plain tarball — a real PEP 517 sdist doesn't help here since the project's
      `MANIFEST.in` only adds `src/*.c`/`*.h` and never packages `bindings/python/tests`,
      so a `python -m build --sdist` (confirmed against the real PyPI sdist) silently
      drops the test suite `CIBW_TEST_SOURCES` needs.
    - No Node.js/npm setup is needed for `tree-sitter generate` itself (recent CLI
      releases embed their own JS runtime), and this project's `package.json` lists
      `tree-sitter-cli` as its only `tree-sitter-*` dependency, which upstream's own
      `npm i` gate excludes — so upstream's own workflow does not install npm packages
      before generating, either.

254. **A build-from-checkout can pick up a maintainer-only dev/coverage cflags
    file the real sdist never ships (the rjsmin case; see `build-rjsmin.yml`).**
    rjsmin's `setup.py` appends the contents of `debug.unix.cflags` to
    `extra_compile_args` whenever the `CFLAGS` env var is unset — a convenience for
    the maintainer's own `tox`/gcov workflow, gating `-Wall -Wdeclaration-after-statement
    -Werror -pedantic -std=c99` plus `-ftest-coverage -fprofile-arcs`. `MANIFEST.in`
    never lists the file, so it is absent from the real PyPI sdist and from any sdist
    built with `python -m build --sdist` — but checking out the git tag directly for
    cibuildwheel (this repo's usual build-from-checkout shape, gotcha 1's opposite
    case) puts it right back at the project root, where `setup.py` finds it
    unconditionally. The pedantic `-Werror` set turns a warning in CPython 3.14's own
    free-threaded `refcount.h` (mixed declaration-and-code) into a hard
    `CompileError` — cp312/cp313/cp314 build fine, only cp314t fails, and the failure
    is entirely upstream's header plus upstream's own dev flags, nothing riscv64-specific.
    Fix: build the sdist yourself first (gotcha 1's playbook step) even for a project
    with no packaging quirks — `tar tzf` the result and confirm the dev-only file is
    gone before wiring it into `cibuildwheel`'s `package-dir`. Reproduces on any
    x86/aarch64 host with a cp314t interpreter: `git clone` the tag, `gcc -std=c99
    -pedantic -Werror -Wdeclaration-after-statement -c rjsmin.c -I
    $(python3.14t -c 'import sysconfig; print(sysconfig.get_path("include"))')`
    fails identically; building from `python -m build --sdist`'s output does not.

258. **A hardcoded download URL in a project's own build script can 403 automated
    clients — confirm from more than one network before blaming a transient outage or
    riscv64, then swap to another official channel with byte-identical content, not
    just any host that happens to answer (the freetype-py case; see
    `build-freetype-py.yml`).** freetype-py's `setup-build-freetype.py` downloads the
    FreeType tarball it bundles from a single hardcoded `FREETYPE_HOST`
    (`mirrors.sarata.com`, one of the GNU project's many `non-gnu` mirrors). That mirror
    returns a Cloudflare-fronted `HTTP 403 Forbidden` to a plain `urllib`/`curl` request
    with no cookie or JS challenge solved — reproduced identically from two unrelated
    networks, immediately and deterministically (not a `502`/`504` gateway hiccup, which
    reads as transient overload instead of a deliberate block). GitHub Actions runner
    IP ranges are exactly the kind of datacenter ASN such bot-management rules target,
    so there is no reason to expect the block clears inside CI just because it isn't
    riscv64-specific.
    - **A `sha256` already in the script is the fastest way to prove a replacement
      mirror is safe**: `setup-build-freetype.py` carries `FREETYPE_SHA256` for exactly
      this kind of verification. SourceForge's direct-file endpoint for the same release
      (`.../files/freetype2/<ver>/<file>/download`) hashed identically — confirmed with
      the project's own `urllib.request.urlopen()` call, not just `curl`, since a
      redirect chain or TLS quirk can behave differently between clients.
    - **Don't assume every alternative "official" mirror is reachable either** — GNU's
      own `ftpmirror.gnu.org` redirector 502'd repeatedly in the same session that
      SourceForge answered cleanly on the first try; test the actual replacement before
      committing to it rather than picking whichever name sounds most canonical.
    - **The patch is the narrowest edit that fixes the URL, not a rewrite of the
      download logic** — SourceForge's path shape doesn't fit the script's
      `HOST + TARBALL` string concatenation, so the fix touches `FREETYPE_HOST` and
      appends the one extra `"/download"` suffix `FREETYPE_URL` needs, leaving
      `FREETYPE_SHA256` and everything else untouched. Tag it `Upstream-Status: To
      upstream` when the real fix (pointing upstream's own script at a better mirror)
      is something only they can land — this repo's policy against filing on other
      repos means the patch has to be carried, not submitted, in that case.

261. **A package can require its own compiled extension, plus a large downloaded
    dataset, just to produce the sdist MANIFEST.in ships as a static file (the biotite
    case; extends gotcha 242's "the generator, not the tag, makes it reproducible").**
    biotite's `MANIFEST.in` has `prune tests/` and `prune doc/` (ordinary, gotcha 6's
    territory) but also `include src/biotite/structure/info/components.bcif` — a 65 MB
    BinaryCIF file that upstream's own `build-internal` CI job generates fresh with
    `python -m biotite.setup_ccd`, not something committed to git. That script imports
    `biotite.structure.io.pdbx`, so it only runs against an *already-built* biotite —
    upstream's own dependency chain is `_pip-install-editable` (compiles the
    Cython+Rust extensions) → `_setup-ccd` (downloads and reshapes a ~113 MB CCD file
    from `files.wwpdb.org`) → `build-sdist`. Skipping straight to `python -m build
    --sdist` from a bare checkout produces a metadata-valid but incomplete sdist: the
    `MANIFEST.in include` line silently matches nothing, and the eventual bdist install
    breaks at import time or first use of `biotite.structure.info`.
    - **Reproduce upstream's own prerequisite chain on `ubuntu-latest` (gotcha 4),
      not the riscv64 runner** — none of it is architecture-dependent, it just needs a
      working local toolchain and network access, both of which are cheaper and faster
      on x86. `pip install -e .` (or `uv pip install -e .`) is enough to make the
      generator's own imports resolve; the generator then writes its output directly
      into the checkout because editable installs keep `__file__` pointing at the
      source tree, which is exactly where `MANIFEST.in`'s `include` line expects it.
    - **A second upstream-generated file can ride along the same way.** biotite's
      `[project] license-files` names `THIRDPARTY.yml`, produced by `cargo
      bundle-licenses --format yaml --output THIRDPARTY.yml` (a Rust dependency
      license bundle, gotcha 10's territory) — also absent from a bare checkout, also
      just another prerequisite step before `python -m build --sdist`, not a patch.
    - **The generator step being expensive (network + CPU) is not a reason to reach
      for the released PyPI sdist instead** — the hard rule against wiring in the
      published sdist as the CI build input (see the playbook's step 3) still applies;
      pay the cost once on `ubuntu-latest` rather than diverge from how the artifact is
      actually produced.
    - **Pruning `tests/`/`benchmarks/` from the sdist (this entry) and re-checking the
      tag out for `CIBW_TEST_SOURCES` (gotcha 104) is only half the fix** — the
      `build_wheels` job's `package-dir` also has to point at a directory, not the
      downloaded `.tar.gz` this job's sibling artifact produces, or `CIBW_TEST_SOURCES`
      resolves against cibuildwheel's own temp extraction instead of the checkout
      (gotcha 251/281 — this exact port hit it).

265. **A project's own version-detection script can read `GITHUB_REF` directly, not
    through `setuptools_scm` — reproduce the env var, not just the checkout (the
    pmdarima case).** Gotcha 112 covers `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_<NAME>` for
    the common case; not every project defers to that machinery. pmdarima's
    `meson.build` calls `run_command(['build_tools/get_tag.py'])` for its `version:`,
    and that script only prints a real version when `CIRCLECI`+`CIRCLE_TAG` are set
    (their CircleCI build) or when `GITHUB_REF` starts with `refs/tags/` — anything
    else silently falls back to a hardcoded `0.0.0`. cibuildwheel's container starts
    with none of the host's environment (no GitHub Actions context leaks in), so a
    bare `actions/checkout` at the tag builds a wheel stamped `0.0.0` with no error
    anywhere in the log.
    - **Set the var the script actually checks, shaped the way it expects**:
      `CIBW_ENVIRONMENT: GITHUB_REF=refs/tags/v${{ env.PKG_VERSION }}` satisfies
      `get_tag.py`'s `startswith('refs/tags/')` check and its `v`-stripping — read the
      script before guessing the shape, since not every project uses the `v` prefix.
    - **A wrong-but-present version doesn't fail the build or the tests** — check the
      wheel filename or `dist-info/METADATA` after a local `pip wheel` (playbook step
      2) rather than assuming a successful build proves the version came through
      correctly.

268. **A vendored C-core git submodule can have its own `git describe`-based
    version detection, independent of the outer package's version (the igraph
    case).** python-igraph vendors the igraph C library as a `vendor/source/igraph`
    submodule; its `CMakeLists.txt` (`etc/cmake/version.cmake`) only trusts an
    `IGRAPH_VERSION` file (present in release tarballs, absent from a git checkout)
    or falls back to `find_package(Git)` + `git_describe()`. `actions/checkout`'s
    default `fetch-depth: 1` also caps the *submodule* clone depth (the action passes
    the same `--depth` to `git submodule update`), so the C core has no tags reachable
    and cmake's `configure` step dies with `Cannot find out the version number of
    this package; IGRAPH_VERSION is missing.` — a plain `git describe`/setuptools_scm
    failure (gotcha 3) doesn't apply here because it isn't the outer repo's version at
    stake, it's a nested submodule's own CMake build erroring out entirely.
    - **`fetch-depth: 0` on the outer `actions/checkout` step fixes it**, exactly as
      upstream's own `build.yml` does (`actions/checkout@v5` with `fetch-depth: 0` and
      `submodules: true`) — `fetch-depth: 0` means "all history for all branches and
      tags" and is threaded through to the submodule clone too, so `git describe`
      inside the submodule has tags to find.
    - **Check upstream's own CI for this exact pattern before guessing at env vars or
      version files** — a project vendoring a CMake C core via git submodule has
      almost certainly already solved "how do I make `git describe` work in CI" for
      itself, and the fix is usually visible directly in their checkout step.

274. **A build-from-checkout package can tag releases in a format the version
    input doesn't match, and GitHub Actions expressions have no string-replace or
    split function to bridge the two (the netifaces case).** netifaces (archived
    upstream, still builds cleanly with a modern setuptools/distutils shim) tags
    releases `release_0_11_0`, not `0.11.0` or `v0.11.0` — unlike the plain-prefix
    case (`ref: v${{ env.PKG_VERSION }}`, as `build-yappi.yml`/`build-pyinstaller.yml`
    do), the dots themselves need to become underscores. GitHub Actions expression
    syntax only offers `contains`/`startsWith`/`endsWith`/`format`/`join` — no
    `replace()` or `split()` — so this can't be done inline in the `ref:` field the
    way gotcha 3's sdist-filename derivation is done in a `run:` step.
    - **Fix: a `run:` step before `actions/checkout` that does the substitution in
      bash and exports it via `GITHUB_ENV`**, since no earlier workflow in this repo
      needed a computed value before its very first step:
      ```yaml
      - name: Determine upstream git tag
        run: echo "PKG_TAG=release_${PKG_VERSION//./_}" >> "$GITHUB_ENV"
      - name: Checkout pkg ${{ env.PKG_TAG }}
        uses: actions/checkout@...
        with: { repository: owner/pkg, ref: ${{ env.PKG_TAG }} }
      ```
      Bash's `${VAR//./_}` is safe here because `.` has no special meaning in
      `${var//pattern/string}` glob-style matching — it matches only a literal dot.
    - **Distinct from gotcha 3**: that one derives the *version* from a *built
      sdist's filename* (sdist→bdist shape, version flows tag→sdist→version).
      This one derives the *tag* from the *version input* (build-from-checkout
      shape, no sdist stage exists to read a filename from) — the dependency
      direction is reversed, and the fix has to live before the checkout instead
      of after a build step.

293. **The newest git tag is not necessarily the version to port — check whether
    upstream's own CI actually built and published it (the tree-sitter-markdown
    case).** tree-sitter-markdown's repo tags v0.5.1, v0.5.2, v0.5.3, but PyPI only
    has 0.5.1: the repo is mid-migration (default branch literally named
    `split_parser`) to split its two grammars (`markdown`, `markdown_inline`) into
    separate packages, and the root `setup.py` at v0.5.2/v0.5.3 only compiles one
    grammar's `src/parser.c` even though `binding.c` still needs symbols from both —
    a checkout of either tag fails to build a working wheel.
    - **The tell was in the PyPI JSON, not the repo**: `curl -s
      https://pypi.org/pypi/<pkg>/json | jq '.info.version, (.releases|keys)'` showed
      `0.5.1` as latest with no 0.5.2/0.5.3 releases at all, despite both tags
      existing upstream.
    - **Confirmed, not just inferred, via upstream's own Actions history**:
      `gh api repos/<owner>/<repo>/actions/workflows/publish.yml/runs` showed the
      v0.5.1 tag's run succeeded end-to-end (pypi build + publish jobs green); the
      v0.5.2 and v0.5.3 runs both show the pypi wheel-build job failing and the
      publish step skipped. Diffing `setup.py` at each tag (`gh api
      "repos/<owner>/<repo>/contents/setup.py?ref=vX.Y.Z"`) confirmed why: v0.5.1's
      `Extension.sources` lists both grammars' `src/parser.c`/`scanner.c` with
      `include_dirs=["tree-sitter-markdown/src"]`; v0.5.2/v0.5.3 replaced it with a
      single-grammar template (`sources=["src/parser.c"]`, no top-level `src/` in
      the checkout at all) left over from an in-progress repo split.
    - **Don't trust the GitHub-rendered default branch's files either** — its
      `setup.py`/`pyproject.toml` reflect the in-progress migration, not any
      released tag; always fetch file contents pinned `?ref=<tag>` (or `git show
      <tag>:<path>`), never the bare default-branch path, when a repo's own CI
      history suggests something is mid-flight.

299. **Gotcha 103's "no tag, but a real commit does the bump" can be missing
    entirely — the maintainer edits the version locally and never commits it
    (the pyfarmhash case).** `veelion/python-farmhash` has no tags and no
    releases; its `setup.py` has read `VERSION = (0, 4, 0)` on `master` since
    commit `954c61f3` (2024-05-02), yet PyPI has since shipped 0.5.0 and then
    0.5.1 sdists. Unlike gotcha 103 (dbt-extractor) and gotcha 213 (lru-dict),
    `gh api "repos/<o>/<r>/commits?path=setup.py"` here shows **no candidate
    commit at all** whose diff touches `VERSION` to `0.5.1` — the maintainer
    bumps the tuple locally before running the release build and uploading,
    then discards the change instead of pushing it.
    - **Prove the rest first, same discipline as 103/213**: download the
      released sdist and diff every file against the HEAD commit's tree
      (`gh api repos/<o>/<r>/tarball/<sha>`). If everything but the version
      string is byte-identical, the port is otherwise a plain build-from-HEAD
      case — the only gap is the one line git never got.
    - **Patch it yourself rather than searching harder for a commit that does
      not exist.** Pin the checkout to HEAD (or whatever commit the diff
      proved identical) as `<PKG>_REF`, and add a one-line
      `patches/<pkg>/<version>/` patch bumping the `VERSION`
      tuple/`version = "..."` string to match, tagged `Upstream-Status:
      Inappropriate [...]` (there is no upstream commit to backport and
      nothing to submit — the maintainer's own workflow is "edit locally,
      never commit"). Verify the patched checkout actually builds a wheel
      reporting the target version before pushing (`python setup.py
      bdist_wheel` / `python -m build --sdist` locally is enough — gotcha 9).

315. **`versioneer` has no `SETUPTOOLS_SCM_PRETEND_VERSION` equivalent for gotcha 31's
    dirty-tree problem — `git update-index --skip-worktree` on just the patched files
    fixes it instead (the crick case).** Backporting two upstream bugfixes onto crick's
    `0.0.8` tag means `git apply`-ing a patch that touches tracked files, which dirties
    the tree exactly like gotcha 31 describes for `setuptools_scm`. But crick uses
    `versioneer`, not `setuptools_scm`, and `versioneer.py`'s `git_pieces_from_vcs` always
    runs `git describe --tags --dirty --always --long` with no environment-variable escape
    hatch — grepping the whole file for `getenv`/`environ`/`PRETEND`/`OVERRIDE` turns up
    nothing. Gotcha 31 also shows that committing the patch doesn't help (`git describe`
    then reports a nonzero distance instead of dirty), and there is no `versioneer`
    mechanism to fake a distance of zero at a moved tag either.
    - **`git update-index --skip-worktree <files>` hides exactly the patched files from
      `git diff-index`/`git describe --dirty`, without touching their on-disk content.**
      Verified with a throwaway repo: tag a commit, modify a tracked file,
      `git describe --tags --dirty --always --long` reports `...-dirty`; run
      `git update-index --skip-worktree <file>` on it and the same describe command
      reports clean again, while the file's patched content is untouched and still what
      the build compiles. This is more surgical than gotcha 31's fix (no env var needed,
      no `fetch-depth: 0` becomes dead weight) and generalizes to any version scheme whose
      only dirty-detection path is `git describe --dirty` with no pretend-version knob.
    - **Skip-worktree only the files the patch actually touches**, listed explicitly
      (`git update-index --skip-worktree crick/stats_stubs.c crick/space_saving_stubs.c.in`)
      — not a blanket `git update-index --skip-worktree .`, which would also hide a
      genuine accidental modification from `git status` during debugging.
    - **This is orthogonal to which patch-application step dirties the tree.** The
      mechanism dirtying the tree here is the same `git apply` gotcha 31 warns about for
      `setuptools_scm`; the fix differs only because `versioneer` offers no pretend-version
      variable to short-circuit its own git calls the way `setuptools_scm` does.

319. **A release tag can exist, be reachable, and check out cleanly, yet still be the
    wrong commit — because it is not even an ancestor of the default branch (the
    memory-allocator case).** Gotcha 103 covers upstream shipping no tag at all; this is
    subtler because `ref: v${{ env.<PKG>_VERSION }}` succeeds and produces *a* build, just
    the wrong one. sagemath/memory_allocator's `v0.2.0` tag checks out fine, but its
    `pyproject.toml` still reads `version = "0.1.4"` at that commit — a squash-merge around
    the meson-build migration left the tag pointing at a pre-version-bump commit, and
    neither `git merge-base --is-ancestor v0.2.0 origin/main` nor the reverse answers `yes`.
    Run that check whenever a tag's checked-out version disagrees with what PyPI actually
    published (or as routine due diligence): `git log --oneline origin/main -20` plus
    `git show origin/main:pyproject.toml | grep version` usually finds the real bump within
    a handful of commits, and gotcha 103's proof step (diff the built wheel/sdist
    byte-for-byte against the one PyPI hosts) confirms it before pinning the SHA over the
    tag, same as `<PKG>_REF`/`<PKG>_VERSION` for a no-tag upstream.

352. **A gitlink with no `.gitmodules` entry breaks `actions/checkout`'s own
    persist-credentials cleanup, not the checkout itself (the hdf5plugin case, second
    occurrence after espeakng-loader's espeak-ng submodule).** `actions/checkout@v7`
    fetches and checks out the ref fine even with `submodules: false` — the failure comes
    later, in a step the log labels "Removing auth": its cleanup runs `git submodule
    foreach --recursive sh -c "... git config --local --unset-all 'core.sshCommand' ..."`
    unconditionally, which walks every `160000`-mode tree entry (gitlink) regardless of
    whether `.gitmodules` mentions it, and dies with `fatal: No url found for submodule
    path '<path>' in .gitmodules` the moment it hits one that doesn't. hdf5plugin 7.0.0
    carries three such gitlinks committed straight into the tree with no `.gitmodules`
    file at all (`lib/bitshuffle/zstd`, `lib/snappy/third_party/{benchmark,googletest}`);
    `git ls-tree -r HEAD | awk '$1=="160000"'` finds them, and a plain `git clone` of the
    same tag succeeds locally because plain git never runs this submodule-cleanup pass.
    None of the three are needed by the actual build (bitshuffle's plugin uses the
    project's own shared `zstd` clib, not its vendored copy; snappy's `third_party/` only
    holds its own test/benchmark deps) — checking whether the build even reaches them is
    the first thing to confirm before treating this as anything more than a checkout-step
    nuisance. Fix (same shape as `build-espeakng-loader.yml`'s `git init`/`git remote
    add`/`git fetch --depth=1`/`git checkout FETCH_HEAD` sequence): replace
    `actions/checkout` for the *upstream* repo with plain git commands, which never invoke
    the submodule-cleanup routine in the first place — no patch to the upstream tree
    needed, and `persist-credentials: false`'s only purpose (not leaking the checkout
    token into the built artifact) is moot for plain, unauthenticated `git clone`/`fetch`.
