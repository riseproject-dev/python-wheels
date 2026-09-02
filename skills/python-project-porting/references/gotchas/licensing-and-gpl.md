# Gotchas — Licensing & GPL sources

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/licensing-and-gpl.md`.

## In this file

- **32** — Vendored C libraries are the usual licensing gap — and upstream often has the fix
- **44** — Naming a vendored dependency's licence `LICENSE.<dep>` at the project root
- **53** — A dependency that is *downloaded and compiled at build time* is invisible from
- **57** — An explicit `license_files=[...]` turns off setuptools' default glob, so gotcha 44's
- **66** — A wheel that vendors the image's `libgomp` is the standard GPL-sources trigger —
- **86** — A monorepo's Python package builds from a subdirectory, so the project's *own*
- **105** — A `[project] license-files` list has no default glob behind it, so gotcha 44's
- **123** — gotcha 44 is not setuptools-specific — PEP 639 gave every backend the same default
- **130** — A REUSE-compliant vendored dependency ships a whole `LICENSES/` directory — declaring
- **137** — Ship the licence of everything auditwheel vendors without hand-listing it.
- **140** — The `gpl_sources` job must run on the riscv64 runner, and RHEL 10 dropped
- **153** — A `dist-info/sboms/*.cyclonedx.json` is not a licence notice — and the notice
- **146** — maturin auto-globs licence files only next to `pyproject.toml`, so a monorepo
- **161** — A vendored prebuilt stack can be GPL while every library in it reports LGPL — read
- **162** — A sibling build repo pins every source by URL and SHA-256, which makes the GPL/LGPL
- **165** — Three ways gotcha 137's licence sweep silently under-collects, and one image fact that

---

32. **Vendored C libraries are the usual licensing gap — and upstream often has the fix
    already.** The Licensing section's "does the wheel carry the licences of what it links"
    check almost always fails the same way: the wheel ships the *wrapper's* LICENSE while a
    bundled C tree (`lz4libs/`, a vendored zlib/zstd/xxHash) is compiled straight into the
    extension under its own BSD/MIT terms, whose binary-redistribution clause requires the
    copyright notice to travel with the binary. Two-command check on any host:
    ```bash
    unzip -l <wheel> | grep -i licen     # what actually ships
    ls <vendored-dir>                    # what got linked in
    ```
    setuptools only globs `LICEN[CS]E*` etc. at the **project root**, so a licence file
    inside the vendored subdir is *not* picked up automatically — it needs an explicit
    `license_files=[...]` listing every file, the wrapper's own included, or you drop the
    original while adding the new ones.
    - **Search upstream before writing anything**: `gh search issues --repo <upstream>
      license --include-prs`. python-lz4 had both an open issue *and* an open PR fixing
      exactly this; carrying that PR turned a hand-rolled patch into
      `Upstream-Status: Submitted [url]` — the strongest tag available, and it drops out
      cleanly when upstream merges. Refresh it onto the tag you build (theirs was anchored
      on a `license=` line added after the release) and note the refresh in the commit
      message.
    - **Reproduce the copyright notice the vendored source actually carries**, not the one
      in the dependency's current `LICENSE` — the bundled copy is usually several releases
      old and the year range differs.

44. **Naming a vendored dependency's licence `LICENSE.<dep>` at the project root
    needs no packaging change at all (refines gotcha 32).** Gotcha 32's fix is an
    explicit `license_files=[...]`, which is only necessary when the file lives inside
    the vendored subdirectory. setuptools' *default* `license_files` glob is
    `LICEN[CS]E*`/`COPYING*`/`NOTICE*`/`AUTHORS*` **at the root**, so a file added there
    as `LICENSE.libyaml` is picked up automatically and lands in
    `dist-info/licenses/` beside the project's own — a one-file patch with no
    `setup.cfg`/`setup.py` edit, and no way to accidentally drop the original by
    replacing the default glob with a hand-written list.
    - **Make the patch self-verifying**, since a licence patch that silently stops
      applying still produces a green build: assert it from the test command via the
      installed metadata rather than eyeballing the wheel —
      `[p for p in importlib.metadata.files('<dist>') if '.dist-info/licenses/' in str(p)]`
      compared against the expected set. Check it fails on an unpatched wheel before
      trusting it.

53. **A dependency that is *downloaded and compiled at build time* is invisible from
    the checkout — but it still has to have its licence in the wheel (extends gotchas
    32/44).** Gotcha 32's two-command check (`ls <vendored-dir>`) only finds statically
    linked code that upstream committed into the tree. The commoner packaging shape for
    a C client library is a `dev/build.py`-style script, run from
    `[tool.cibuildwheel] before-all`, that curls an upstream release tarball, configures
    it `--enable-static --disable-shared`, and links the resulting `.a` into the
    extension. Nothing about that is visible in `git ls-files`, so the licence gap reads
    as "no vendored deps" if you only look at the checkout. pymssql builds FreeTDS
    (LGPL v2 `libsybdb`) this way — the wheel is 4 MB of FreeTDS and ships only
    pymssql's own `LICENSE`.
    - **Find it in the build config, not the tree**: a `[tool.freetds]
      version_for_pypi_wheels = "1.4.27"`-style pin plus a `before-all` that runs a
      download script is the tell; the pinned version tells you exactly which release
      tarball to pull the licence text out of.
    - **Then it is gotcha 44's one-file patch** — drop the dependency's own
      `COPYING*`/`LICENSE*` at the *project* root as `LICENSE.<dep>` so setuptools'
      default `LICEN[CS]E*` glob lands it in `dist-info/licenses/` with no packaging
      change, and assert it from `CIBW_TEST_COMMAND` via
      `importlib.metadata.files('<dist>')` so the patch cannot silently stop applying.
    - **`git apply` then triggers gotcha 31** — the patched tree is dirty, so a
      `setuptools_scm` project renames the wheel `X.Y.(Z+1).dev0+g…`. Add
      `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_<PKG>` in the same change and drop any
      `fetch-depth: 0` that existed only to make the tag reachable.

57. **An explicit `license_files=[...]` turns off setuptools' default glob, so gotcha 44's
    drop-a-file-at-the-root trick silently does nothing (the gevent case).** Gotcha 44 leans
    on the default `LICEN[CS]E*`/`COPYING*`/`NOTICE*`/`AUTHORS*` glob at the project root. A
    project that names its licence explicitly — gevent's `setup(..., license_files=['LICENSE'])`
    — has *replaced* that glob, so a `LICENSE.<dep>` dropped beside it is not picked up: the
    build stays green and the wheel still ships one licence. The patch has to extend the list.
    - **Point at the vendored file in place; don't copy its text into the patch.** setuptools
      (PEP 639, >= 77) preserves each entry's path relative to the project root, so
      `'deps/libev/LICENSE'` lands as `dist-info/licenses/deps/libev/LICENSE`. That keeps the
      patch to a few lines and lets it track the dep when upstream re-vendors it, where a
      root-level copy freezes the text at whatever version you happened to read.
    - **A vendored tree may carry no licence file at all**, only per-file headers — gevent's
      `deps/c-ares` is a partial copy with the MIT notice solely in each `.c`. Restore the file
      the dependency itself ships, at the path it ships it at (`deps/c-ares/LICENSE.md` from
      c-ares 1.34.5, the version in `include/ares_version.h`), rather than inventing a name.
    - **`NOTICE` is a licence file too once the default glob is off.** gevent's carries the PSF
      licence covering the stdlib test files copied into `gevent/tests` and a third-party
      copyright for `gevent/libuv/_corecffi_*.c`, both of which ship in the wheel; the explicit
      list had dropped it along with everything else.
    - Verify the way gotcha 44 does — assert the expected set from
      `importlib.metadata.files('<dist>')` in the test command, and confirm it fails on an
      unpatched wheel first.

66. **A wheel that vendors the image's `libgomp` is the standard GPL-sources trigger —
    and there is no live example left in the tree to copy (the scikit-learn case).**
    The Licensing section says to add a `gpl_sources` job when the build links GPL
    components that come from *our* build environment, and names `build-numpy.yml` as
    the complete example. It no longer is: #178 removed that job (numpy's GPL concern
    was openblas, which upstream ships prebuilt), leaving only a dangling comment on
    `MANYLINUX_RISCV64_IMAGE`, and **zero** of the 43 build workflows on `main` use
    `actions/collect-gpl-sources` today. So the shape has to be reconstructed from
    `git show 1c45d16 -- .github/workflows/build-numpy.yml`. Reconstruct it rather than
    skipping — an OpenMP-using project is the commonest case and the check is two
    commands on an artifact you already have:
    ```bash
    gh run download <run-id> -n <pkg>-<ver>-<tag>-manylinux_riscv64 -D whl
    unzip -l whl/*.whl | grep -E '\.libs/|\.dylibs/'   # auditwheel's vendored-lib dir
    ```
    `<pkg>.libs/libgomp-<hash>.so.1.0.0` means the image's GCC OpenMP runtime is being
    redistributed by us. GPLv3 **with** the GCC Runtime Library Exception still carries
    the source-distribution obligation for the runtime library itself — the exception
    only permits the *combination* with non-GPL modules — so the sources must be
    published, not just the notice shipped.
    - **The job runs natively, on `ubuntu-24.04-riscv`, not `ubuntu-latest`.**
      `collect-gpl-sources` does `docker run` on the riscv64 manylinux image, which on
      an x86 runner needs binfmt that isn't registered there.
    - **Its artifact must not match the publish job's `artifact-pattern`.** Name it
      `<pkg>-<ver>-gpl-sources` and keep the pattern anchored on `*-manylinux_riscv64`,
      then pass it separately via `gpl-sources-artifact`/`-release-tag`/`-description`;
      `_publish-wheel.yml` attaches it to a GitHub Release and renders the URL as the
      version's docs `comment:`.
    - **Upstream usually tells you first.** A project shipping a
      `build_tools/wheels/LICENSE_*.txt` (or any "this binary distribution also bundles"
      notice) that names `libgomp*`/`libgfortran*` has already done the audit for you —
      and a `check_license.py`-style test asserting the notice made it into
      `dist-info/licenses/` is worth inheriting unchanged, since it fails loudly if the
      before-build step that appends it ever stops running.

86. **A monorepo's Python package builds from a subdirectory, so the project's *own*
    LICENSE never reaches the wheel (the thrift case; see `build-thrift.yml`).** Gotchas
    32/44/57 are all about a *vendored dependency's* licence going missing. The plainer
    failure is upstream shipping none of its own: when `setup.py` lives in a subdirectory of
    a multi-language repo (`lib/py`, `python/`, `bindings/python/`), setuptools' default
    `LICEN[CS]E*`/`COPYING*`/`NOTICE*`/`AUTHORS*` glob runs against **that** directory, not
    the repo root where the licence actually sits — so every wheel upstream publishes carries
    only a `License:` metadata string. apache/thrift's `manylinux2014_x86_64` wheel has no
    `LICENSE` and no `NOTICE` entry at all, while Apache-2.0 sections 4(a) and 4(d) require
    both to travel with a binary redistribution. RISE distributes these wheels, so the gap is
    ours to close, and it is worth sending upstream since it affects every architecture.
    - **The fix needs no patch file, because the files are already in the checkout.** One
      workflow step — `cp LICENSE NOTICE <subdir>/` before cibuildwheel — puts them where the
      default glob looks, and `dist-info/licenses/` is populated with no `setup.py` or
      `pyproject.toml` edit. Cheaper and more upstreamable than a `patches/<pkg>/<ver>/` diff
      that would have to embed the whole licence text, and it cannot trip gotcha 57 by
      replacing the default glob with a hand-written list.
    - **Diagnose on the *published* wheel, not the one you build**:
      `unzip -l <pypi-wheel> | grep -iE 'licen|notice'` returning nothing is the whole
      finding, and it is what proves this is upstream's gap rather than something your build
      dropped. One `curl` of the PyPI file list settles it before any checkout.
    - **`auditwheel repair` adds a `dist-info/licenses/` *directory* entry that a plain
      `bdist_wheel` does not**, so gotcha 44's self-verifying set-equality check built from
      `zipfile.namelist()` picks up an extra `""` after `rsplit("/", 1)` and fails — and only
      on the riscv64 job, because the wheel from a local `python -m build` has no such entry.
      Subtract `{""}`, and validate the assertion against a *repaired* wheel rather than the
      one your host produced.

105. **A `[project] license-files` list has no default glob behind it, so gotcha 44's
    drop-a-file-at-the-root trick never applies to a PEP 621 backend.** Gotcha 57 frames the
    explicit-list case as setuptools' default `LICEN[CS]E*` glob being *turned off* by
    `license_files=[...]`. With scikit-build-core, hatchling or flit the list lives in
    `[project]` (PEP 639) and there was never a glob to turn off — lightgbm's
    `license-files = ["LICENSE"]` is the entire rule — so extending the list is the only
    possible patch, and a `LICENSE.<dep>` added at the root would be silently ignored.
    - Two greps settle which world you are in before writing anything:
      `grep -n build-backend pyproject.toml` and `grep -n 'license.files' pyproject.toml setup.py setup.cfg`.
    - The list entries keep their relative paths, so point at the vendored files in place
      (`external_libs/nanoarrow/NOTICE.txt` lands as
      `dist-info/licenses/external_libs/nanoarrow/NOTICE.txt`) — gotcha 57's advice, and here
      it also means the patch is confined to `pyproject.toml`.
    - **A build script that assembles the sdist is where you find what got vendored** (a third
      route past gotcha 32's `ls <vendored-dir>` and gotcha 53's `before-all` download).
      lightgbm's `build-python.sh` copies a curated subset of `external_libs/` — including
      each dependency's `LICENSE*` — into the staging tree, so the licences are already in
      the sdist and only the metadata list is missing them.

123. **gotcha 44 is not setuptools-specific — PEP 639 gave every backend the same default
    licence glob, and a patched-in *untracked* file still reaches the sdist (the
    levenshtein case; see `build-levenshtein.yml`).** Gotcha 44 credits setuptools'
    default `license_files` glob for making a root `LICENSE.<dep>` land in
    `dist-info/licenses/` with no packaging change. That reasoning is backend-agnostic:
    PEP 639 makes `["LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]` the default whenever
    `pyproject.toml` carries no `license-files` key, and scikit-build-core (checked in
    1.0.3) implements it — so a Levenshtein-style project whose wheel ships only its own
    GPL `LICENSE` while `CMakeLists.txt` `add_subdirectory`s a bundled MIT header-only
    library (`extern/rapidfuzz-cpp`) is fixed by the same one-file patch, with no
    `[tool.scikit-build]` edit.
    - **The `git apply` step leaves the file untracked, and that is fine.** The obvious
      worry — that a backend building an sdist inside a git checkout uses `git ls-files`
      and would silently drop it — does not hold: scikit-build-core walks the tree and
      filters through `.gitignore`, so an untracked, unignored file is packaged. Settle it
      in one command rather than by reading backend source: `python -m build --sdist` after
      the patch, then `tar tzf dist/*.tar.gz | grep -i licen`.
    - **Check the version mechanism before worrying about gotcha 31.** Patching dirties the
      tree, which renames the wheel only under `setuptools_scm`. A project reading its
      version out of source — `[tool.scikit-build.metadata.version]` with the
      `scikit_build_core.metadata.regex` provider, here over `src/Levenshtein/__init__.py`
      — is immune, so no `PRETEND_VERSION` is needed.
    - Related, and the reason this port was three steps instead of ten: **an upstream whose
      own wheel jobs already pass their sdist tarball to cibuildwheel as `package-dir` hands
      you the whole recipe.** Levenshtein's sdist job cythonises `.pyx` → `.cxx` and applies
      its own `tools/sdist.patch` (which drops Cython from `build-system.requires`), so the
      riscv64 container compiles generated C++ with no Cython at all, and `test-requires` /
      `test-command` are inherited from the sdist's `[tool.cibuildwheel]` table. Mirroring
      that split is both closer to upstream and cheaper than a build-from-checkout rewrite.

130. **A REUSE-compliant vendored dependency ships a whole `LICENSES/` directory — declaring
    it wholesale puts GPL text in your wheel (the pycares/c-ares case).** Gotchas 44/57/105
    settle *how* to get a bundled dependency's licence into `dist-info/licenses/`; this is
    about *which* files to name. A dependency following the REUSE spec keeps one text per
    SPDX identifier its repository needs, covering build tooling as much as code, so
    c-ares' `LICENSES/` holds `GPL-3.0-or-later.txt` and `LGPL-2.1-or-later.txt` for
    imported autoconf m4 macros that no wheel ever contains. A convenient
    `license-files = [..., "deps/c-ares/LICENSES/*.txt"]` therefore publishes a wheel whose
    metadata advertises GPL — a licence claim every downstream scanner will act on, and an
    immediate objection on the upstream PR.
    - **Count SPDX tags over exactly the sources that get compiled**, which is one command
      and also tells you nothing was missed:
      `grep -rhno "SPDX-License-Identifier:.*" src/lib include | sed 's/.*SPDX/SPDX/' | sort | uniq -c`
      → 140 MIT + 1 BSD-3-Clause for c-ares 1.34.6. Declare those, plus any licence covering
      a platform-gated source the *other* platforms' wheels compile (c-ares'
      `src/lib/thirdparty/apple/dnsinfo.h` is APSL-2.0 and only builds on macOS) so the patch
      is correct for upstream as a whole, not just for riscv64.
    - **The dependency's own root `LICENSE`/`AUTHORS` still belong in the list** — c-ares'
      `LICENSE.md` names `AUTHORS` for the contributor copyright holders, so shipping one
      without the other leaves the notice incomplete.
    - Say in the commit message which texts you left out and why. That sentence is what turns
      a list that looks arbitrary into a reviewable decision.

137. **Ship the licence of everything auditwheel vendors without hand-listing it.**
    Gotchas 32/44/53 each add *one* known dependency's licence. When the extension links a
    library as large as GDAL, auditwheel vendors its entire shared-library closure — 42
    `.so`s here, most of them pulled in transitively by libcurl (krb5, openldap, libssh,
    nghttp2, libpsl, brotli, OpenSSL) — and hand-listing them is both tedious and silently
    wrong the moment a dependency's own deps change. Compute it instead, in the build image,
    and have `CIBW_BEFORE_BUILD` stage the result at the project root where setuptools'
    default `LICEN[CS]E*` glob picks it up (gotcha 44):
    ```bash
    mapfile -t libs < <(ldd /usr/local/lib/lib<dep>.so | tr ' ' '\n' | grep '^/' | sort -u)
    mapfile -t pkgs < <(rpm -qf --qf '%{NAME}\n' "${libs[@]}" 2>/dev/null \
        | grep -E '^[A-Za-z0-9._+-]+$' | sort -u | grep -vE '^(glibc|libgcc|libstdc\+\+|gcc)$')
    ```
    `ldd` is transitive, so one call covers the whole closure, and libraries you built from
    source come back "not owned by any package" — copy their `COPYING`/`LICENSE` at build
    time instead. Three traps, all of which cost a cycle each:
    - **`rpm -qf` writes `file X is not owned by any package` to *stdout*, not stderr**, so
      `2>/dev/null` does not filter it and the words end up in your package list. Keep only
      lines that are a bare package name (`grep -E '^[A-Za-z0-9._+-]+$'`).
    - **A subpackage may carry no licence of its own** — `pcre2` leaves it to `pcre2-syntax`.
      Fall back to the siblings sharing its `%{SOURCERPM}`
      (`rpm -qa --qf '%{SOURCERPM} %{NAME}\n' | awk -v s="$srpm" '$1==s{print $2}'`).
    - **Some packages genuinely ship none** (`sqlite-libs`, public domain), and a few mark
      the licence `%doc`, which the image's `tsflags=nodocs` drops — `dnf -y reinstall
      --setopt=tsflags= <pkg>` restores those. For the rest, record `%{LICENSE}` from the
      rpm metadata rather than failing the build or inventing a licence text.
    Then assert from `CIBW_TEST_COMMAND` that the from-source ones are present via
    `importlib.metadata.files()` (gotcha 44), so the whole mechanism cannot silently stop.

140. **The `gpl_sources` job must run on the riscv64 runner, and RHEL 10 dropped
    libunwind (the memray case).** Two separate facts, both cheap to get wrong:
    - **`collect-gpl-sources` does a `docker run` of the riscv64 manylinux image**, so the
      job that uses it has to sit on `ubuntu-24.04-riscv` like `build-mysql-connector-python.yml`
      does. On a GitHub-hosted `ubuntu-latest` there is no binfmt for riscv64 and the step
      dies instantly with `exec /usr/local/bin/manylinux-entrypoint: exec format error`
      (preceded by docker's "requested image's platform ... does not match" warning) — a
      confusing failure for a job that only downloads source RPMs. The action's own `dnf`
      work is trivial, so the riscv runner costs nothing; it is the *emulation* that is
      missing, not permissions.
    - **`libunwind` is not in Rocky 10 at all** — RHEL 10 moved it to EPEL, and manylinux
      sets `EPEL=` empty for riscv64 (gotcha 51), so `yum install -y libunwind-devel`
      inherited from an upstream `before-all` fails outright. Build it from source instead:
      1.8.3 has had riscv64 support since 1.7.0 (`src/riscv/`), configures and installs a
      working `libunwind.pc` with a plain
      `./configure --prefix=/usr --libdir=/usr/lib64 --disable-documentation --disable-tests
      --disable-minidebuginfo --disable-zlibdebuginfo`, and `unw_backtrace()` returns real
      frames. Note `--libdir=/usr/lib64` is load-bearing: autotools defaults to `/usr/lib`,
      which is not on the riscv64 linker/pkg-config path.
    - **The rest of an AlmaLinux-8-era `before-all` is usually dead weight on riscv64.**
      Upstreams pinned to `manylinux_2_28` build curl, zstd and elfutils from source purely
      because AlmaLinux 8 is old; Rocky 10 packages curl 8, zstd 1.5.5 and **elfutils 0.194**
      (with `elfutils-debuginfod-client-devel` shipping a real `libdebuginfod.pc`). Replacing
      three source builds with one `dnf install` is closer to what upstream *means*, not
      further from it — say so in a comment so a reviewer reads it as a base-image
      difference rather than a customisation.
    - **`rockylinux/rockylinux:10` under `--platform linux/riscv64` is the cheap oracle for
      all of this** (gotcha 51's trick, extended): it is a 60MB pull against the multi-GB
      manylinux image, shares the same repos, and is big enough to run a real
      `cmake -S . -B build` of the project once you `pip3 install cython ninja` — memray's
      full configure, including all three `pkg_check_modules`, finished in ~12s there and
      would otherwise have cost a queued multi-hour riscv64 CI cycle. Use
      `dnf -y download --source` in the same container to prove every package name you pass
      to `collect-gpl-sources` actually resolves.

153. **A `dist-info/sboms/*.cyclonedx.json` is not a licence notice — and the notice
    inventory an upstream generates is often shipped only in the sdist (the burner-redis
    case; see `build-burner-redis.yml`).** maturin (>= 1.9) writes a CycloneDX SBOM into
    every wheel, listing each Rust crate with an SPDX *expression* (`"licenses":
    [{"expression": "MIT OR Apache-2.0"}]`) and no licence text or copyright line. That
    reads like the third-party obligations are handled; they are not — MIT requires the
    copyright notice to travel with binary redistribution and Apache-2.0 4(a) requires a
    copy of the License. Meanwhile the project usually *does* have the full inventory: a
    `cargo-about`-style `THIRDPARTY.yml`/`about.hbs`/`LICENSE-THIRD-PARTY` at the repo
    root, complete with texts. burner-redis' release workflow even asserts the file is in
    the sdist (`tar -tzf … | grep -Fx "…/THIRDPARTY.yml"`) — and never puts it in the
    wheel, on any architecture.
    - **Two commands find both halves**: `unzip -l <upstream wheel> | grep -iE 'licen|sbom'`
      (what actually ships) and `ls <checkout> | grep -iE 'thirdparty|third-party|notice'`
      (what upstream already generated). A wheel with an SBOM and a single `LICENSE`, next
      to a repo carrying a half-megabyte notice file, is the signature.
    - **The fix is gotcha 44/146's one-file move, with no patch**: maturin's auto-discovery
      globs (`LICEN[CS]E*`, `COPYING*`, `NOTICE*`, `AUTHORS*` at the pyproject directory,
      used only when `[project] license-files` is absent — checked in maturin 1.15.0
      `src/metadata.rs`) will pick the inventory up under a `NOTICE*` name, so a
      `cp THIRDPARTY.yml NOTICE.THIRDPARTY.yml` workflow step before cibuildwheel is the
      whole change. It logs `📦 Including license file …`, which is the cheapest
      confirmation it fired.
    - **Assert the resulting *set*, and subtract the empty basename** — `auditwheel repair`
      adds a bare `dist-info/licenses/` directory entry that a plain maturin wheel has not
      got, so a `zipfile.namelist()` check built on `rsplit("/", 1)[1]` picks up a `''`
      and fails only on the repaired (i.e. CI) wheel (gotcha 86, reached from the maturin
      side).

146. **maturin auto-globs licence files only next to `pyproject.toml`, so a monorepo
    layout drops the repo-root LICENSE from every wheel (extends gotcha 44).** Gotcha 44
    is setuptools' default `LICEN[CS]E*` glob at the *project root*; maturin implements the
    same default set (`LICEN[CS]E*`, `COPYING*`, `NOTICE*`, `AUTHORS*` — `src/metadata.rs`,
    used only when `[project] license-files` is absent) rooted at the **pyproject
    directory**. A project whose packaging lives in `python/` while `LICENSE` sits at the
    repository root therefore publishes wheels carrying *no licence file at all*:
    magika 1.0.3's `dist-info/` holds only `METADATA`, `WHEEL`, `RECORD` and an SBOM,
    despite the binary statically linking an entire ONNX Runtime. `license-files =
    ["../LICENSE"]` is not the fix — maturin runs `check_pep639_glob`, which rejects `..`.
    Copy the files into the pyproject directory in the build step instead; maturin then
    writes them to `dist-info/licenses/`, and naming a bundled dependency's files
    `LICENSE.<dep>` / `NOTICE.<dep>` makes the default globs pick those up too.
    - **Prove it on any host in a minute**: `maturin build --release` on macOS or x86 and
      `unzip -l` the wheel. Nothing about this is arch-specific, so it never needs a CI cycle.
    - **A dependency compiled from source at build time is gotcha 53's shape, and its
      licence files exist only after upstream's own script fetches it** (here ONNX
      Runtime's `LICENSE` and `ThirdPartyNotices.txt`), so this is a workflow `cp`, not a
      patch under `patches/`.
    - **Assert it from the test command** (gotcha 44), matching on `.dist-info/` rather
      than `.dist-info/licenses/` so the check survives either packaging layout:
      `{p.name for p in importlib.metadata.files("<dist>") if ".dist-info/" in str(p)}`.

161. **A vendored prebuilt stack can be GPL while every library in it reports LGPL — read
    `DT_NEEDED`, not the licence string (the av case; see `build-av.yml`).** Gotcha 98 says a
    dependency bundle fetched from upstream's own sibling build repo is an ordinary port. The
    licensing half needs its own look, because the sibling repo may carry a patch that changes
    what the bundle *is*. pyav-ffmpeg patches FFmpeg's `configure` to move `libx264`/`libx265`
    out of `EXTERNAL_LIBRARY_GPL_LIST` into `EXTERNAL_LIBRARY_VERSION3_LIST`, so FFmpeg builds
    without `--enable-gpl` and every `libav*.so` answers `license: LGPL version 3 or later` —
    while `libavcodec` still has `DT_NEEDED` on `libx264.so.165` and `libx265.so.216`, both
    GPL-2.0-or-later, both shipped in `av.libs/`. Reading the version string, or the
    `configure` line embedded in the binary (which shows no `--enable-gpl`), gives the wrong
    answer twice over.
    - **Settle it from the ELF, on any host, off the wheel you already built**: pyelftools
      ships with abi3audit, so
      `ELFFile(open(so,'rb')).get_section_by_name('.dynamic').iter_tags('DT_NEEDED')` over the
      biggest bundled library names every GPL dependency in one call. Do this before writing
      the PR's **License** section for any wheel whose `.libs/` holds more than a couple of
      files — `ls` of the vendored directory tells you the names, not the terms.
    - **`dist-info/sboms/auditwheel.cdx.json` splits the vendored set for free.** auditwheel
      (>= 6.8) writes a CycloneDX SBOM naming each bundled library's origin: `pkg:rpm/rocky/...`
      for the ones it pulled out of the build *image*, and the project's own purl for the rest.
      One `json.load` separates "our build environment's obligation" (the `gpl_sources` job of
      gotcha 66) from "upstream's vendored tree" (this one) instead of guessing — here exactly
      `libxcb`, `libXau`, `libdrm`, all MIT, and no gcc runtime at all.

162. **A sibling build repo pins every source by URL and SHA-256, which makes the GPL/LGPL
    source release mechanical (extends gotchas 53/66/98).** Gotcha 66's `gpl_sources` job only
    knows how to fetch source RPMs from the manylinux image; a bundle built by upstream's own
    `<pkg>-ffmpeg`-style repo has no RPMs, but it does have a pin table —
    pyav-ffmpeg's `scripts/pkg.py` is importable on its own (`dataclasses` + `platform` only),
    so `exec`ing it yields `name`, `source_url` and `sha256` for all 17 dependencies. A job on
    `ubuntu-latest` (gotcha 4 — sources are arch-independent) downloads each tarball, verifies
    the pin, and hands the result to `_publish-wheel.yml`' `gpl-sources-artifact` as
    `gpl-sources.tar`, which is the same mechanism `collect-gpl-sources` feeds.
    - **The build repo itself is part of the corresponding source.** It carries the configure
      arguments and, usually, patches against the dependencies (pyav-ffmpeg patches FFmpeg,
      GMP, LAME and libvpx) — pristine upstream tarballs alone are *not* the source the binary
      was built from. Add its release tarball to the same archive.
    - **The same tarballs are also where the licence texts come from**, so collect both in one
      pass: glob `COPYING*`/`LICEN[CS]E*`/`NOTICE*` at the top two levels of each archive
      (x265 keeps its sources under `source/`, gnutls its texts under `doc/`), concatenate per
      dependency into `LICENSE.<name>`, and stage those at the checkout root where the PEP 639
      default glob ships them (gotchas 44/123 — PyAV declares `license = "BSD-3-Clause"` and no
      `license-files`, so the default applies). Verify the glob in 60 seconds with a throwaway
      `pyproject.toml` + `LICENSE.x264` rather than by inspecting a three-hour wheel.
    - **Derive the dependency set from the build script's platform conditions, not from the
      whole pin table** — `use_libvpl`/`use_cuda`/`is_arm32` gate which packages a given arch
      builds, and shipping a licence for something the wheel does not contain is its own kind
      of wrong.

165. **Three ways gotcha 137's licence sweep silently under-collects, and one image fact that
    makes it matter far more on riscv64 (the memray case).** Gotcha 137's `ldd` + `rpm -qf`
    recipe is right, and pyproj proved it — but each of these fails *quietly*, producing a
    green build and a wheel that is short a notice.
    - **`ldd` does not list the libraries you pass it.** Running it over the project's direct
      link dependencies gets the transitive closure and misses the roots themselves, so exactly
      the libraries you were thinking about are the ones absent. Add `readlink -f` of each root
      to the list. In memray's case that silently dropped `lz4-libs` and
      `elfutils-debuginfod-client` — and the `-devel` symlink you ldd is owned by a different
      package than the runtime `.so.N` the wheel ships, so resolve before querying rpm.
    - **`%license` survives `tsflags=nodocs`; `%doc` does not.** Gotcha 137 says to
      `dnf reinstall --setopt=tsflags=`, but after doing so the file is still invisible to
      `rpm -q --licensefiles` — it was never marked `%license`. `lz4-libs` ships
      `/usr/share/doc/lz4-libs/LICENSE` this way. The third fallback tier is
      `rpm -qd "$pkg" | grep -iE '/(LICEN[CS]E|COPYING|NOTICE)'` after the reinstall.
    - **Exclude only what auditwheel's allowlist actually covers.** glibc, the gcc runtime,
      libstdc++ and **zlib** (`zlib-ng-compat` on Rocky 10) are on the manylinux policy
      allowlist and never vendored, so collecting licences for them is noise; everything else
      in the closure does land in the wheel. Cross-check the finished list against
      `unzip -l <whl> | grep '\.libs/'` — that is the only proof the sweep was complete.
    - **The riscv64 manylinux image ships full `libcurl`, not `libcurl-minimal`.** Anything
      linking libcurl — `libdebuginfod` is the common route, via elfutils — therefore drags in
      krb5, openldap, libssh, libfido2, libcbor, libsasl2, libidn2, libunistring, systemd's
      libudev, pcre2 and brotli. memray's riscv64 wheel vendors **33** shared libraries where
      upstream's `manylinux_2_28` wheels vendor 9, so a licence gap that is minor upstream is
      substantial for us, and the `gpl_sources` package list has to grow to match (keyutils,
      libcap, libidn2, libssh, libunistring, libxcrypt, libzstd, lz4, pcre2, systemd on top of
      gcc and elfutils). `dnf download --source` resolves all of them by binary package name
      and dedupes to one SRPM each; validate the names on the aarch64 image first, since source
      RPMs are arch-independent.
    - **scikit-build-core applies the same default glob setuptools does, even behind a legacy
      `license = {text = "..."}` table** — `wheel.py` runs `Path().glob("LICEN[CS]E*")` (plus
      `COPYING*`/`NOTICE*`/`AUTHORS*`) from the build cwd when neither `project.license-files`
      nor `tool.scikit-build.wheel.license-files` is set. So gotcha 44's drop-a-file-at-the-root
      trick works here with no patch: stage `LICENSE.<pkg>.<file>` into `{project}` from
      `before-all` and it lands in `dist-info/licenses/`. `{project}` is substituted in
      `before-all` (`platforms/linux.py` calls `prepare_command(..., project=..., package=...)`),
      so the collector can be a script checked out beside the workflow.
