---
title: Workflows Reference
layout: default
nav_order: 8
---

# Workflows

This page describes the complete lifecycle of a package in `python-wheels`: the
first contribution, automated upgrades, publication, documentation, and eventual
deprecation. For build implementation details, see the [development
guide](development).

## Lifecycle at a glance

A package normally moves through these states:

1. A contributor opens a PR containing `.github/workflows/build-<pkg>.yml` and
   `docs/packages/<pkg>.yaml`. The YAML contains a **pending** version.
2. The PR builds and tests that version. Its `publish` job calls
   `_publish-wheel.yml` in dry-run mode; no release or automated PR is created.
3. Merging the PR triggers the package workflow on `main`. The wheels are built
   again and published in a new immutable GitHub Release.
4. The publish job pushes the release metadata to `package/<pkg>` and opens or
   updates a PR titled `<pkg>: update packages`.
5. Merging that package PR makes the release visible in the generated Simple API
   and triggers deployment of the website.
6. Each night, `check_versions` compares tracked packages with PyPI. An upgrade,
   yanked release, or deprecation is proposed on the same `package/<pkg>` branch
   and in a PR with the same `<pkg>: update packages` title.
7. Merging an upgrade PR returns to step 3. A deprecation PR instead retires the
   package when PyPI provides an upstream riscv64 or universal wheel.

The central design rule is that **all automated changes for one package share
`package/<pkg>`, while different packages use different branches**. Publication
and nightly version checks are also serialized by the `publish-wheel`
concurrency group. This prevents the two automation sources from overwriting one
another without forcing unrelated package changes into one branch or PR.

## 1. Adding a package

### Files in the first PR

A new package contribution contains at least:

- `.github/workflows/build-<pkg>.yml`;
- `docs/packages/<pkg>.yaml`.

It may also contain versioned patches under `patches/<pkg>/<version>/`. A patch
must contain a valid `Upstream-Status:` header. Do not add the package manually
to `ci_scripts/packages.txt`; `ci_scripts/update_doc.py` does that after the
first successful publication.

The package YAML is the source of truth for versions:

```yaml
package-name: <pkg>
source-code: <upstream repository URL>
license: <SPDX identifier>
versions:
- version: <wheel version>
```

The version is the value that will appear in the wheel's `METADATA`, which is
not necessarily identical to the upstream git tag. An entry with neither `tag`
nor `files` is **pending**. A released entry has both keys. A partial entry with
only one of them is invalid.

### Required package-workflow triggers

Every `build-<pkg>.yml` must have all three triggers, with both the workflow and
package YAML in the `pull_request` and `push` path filters:

```yaml
on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version glob to (re)build; empty builds every version of docs/packages/<pkg>.yaml not released yet'
        required: false
        default: ''
  pull_request:
    branches: [main]
    paths:
      - '.github/workflows/build-<pkg>.yml'
      - 'docs/packages/<pkg>.yaml'
  push:
    branches: [main]
    paths:
      - '.github/workflows/build-<pkg>.yml'
      - 'docs/packages/<pkg>.yaml'
```

They have distinct purposes:

- `pull_request` registers a brand-new workflow with GitHub and validates the
  pending versions before merge;
- `push` performs the post-merge build and publication from `main`;
- `workflow_dispatch` is for an intentional rebuild, selected with a version
  glob. It is not the normal post-merge mechanism.

A new workflow cannot be usefully dispatched before GitHub has registered it.
The first PR run provides that registration. Do not remove the PR trigger to
avoid a duplicate build: the PR run validates, while the `main` run publishes.

### Setup and version selection

The first job calls `/.github/workflows/_setup.yml`:

```yaml
setup:
  uses: $/.github/workflows/_setup.yml
  with:
    package: <pkg>
    version: ${{ inputs.version }}
```

`_setup.yml` runs `ci_scripts/pending_versions.py` and returns a JSON version
list:

- without a dispatch glob, every pending version is returned, except that on a
  pull request from a `package/<pkg>` branch only the versions the PR adds to
  `docs/packages/<pkg>.yaml` on top of the base branch are returned, so linking
  a release does not rebuild versions already merged but not yet released;
- with a dispatch glob, every matching declared version is returned, including
  versions already released;
- if nothing is pending, it returns `[]`.

Every matrix job must guard against the empty list with
`if: needs.setup.outputs.versions != '[]'`. Build and test jobs consume the
selected versions as `matrix.version`, create wheel artifacts, and should mirror
upstream's Linux build and tests as closely as possible. The standard target
matrix and implementation patterns are documented in [Development
guidelines](development).

### The publish caller

Every package workflow ends with a matrix job that calls the reusable publish
workflow:

```yaml
publish:
  name: Publish <pkg> ${{ matrix.version }}
  needs: [setup, build_wheels]
  if: needs.setup.outputs.versions != '[]'
  strategy:
    fail-fast: false
    matrix:
      version: ${{ fromJSON(needs.setup.outputs.versions) }}
  permissions:
    contents: write
    pull-requests: write
  uses: $/.github/workflows/_publish-wheel.yml
  with:
    artifact-pattern: <pkg>-${{ matrix.version }}-*-manylinux_riscv64
  secrets:
    app-private-key: ${{ secrets.RISEPROJECT_APP_PRIVATE_KEY }}
```

The artifact pattern must select wheels for exactly one normalized package and
one version. If GPL source correspondence is required, the caller also supplies
`gpl-sources-artifact` and `gpl-sources-description`; the source tarball is then
published beside the wheels and recorded in the package YAML.

### What happens on the first PR

The PR's package workflow builds and tests every pending version. The publish
job downloads and inspects the selected wheels, verifies that their normalized
project names and versions agree, computes the prospective release tag, and
prints a dry-run summary. `ci_scripts/update_doc.py` also prints the YAML diff
and branch/PR it would create.

Because the ref is not `main`, a PR run does **not** create a GitHub Release,
push `package/<pkg>`, or open a package PR. Reviewers should verify:

- the workflow follows upstream's build and test process;
- all expected Python/platform wheels exist and no unrelated artifact matched;
- wheel metadata contains the declared package name and version;
- tests exercised the installed wheel rather than the source checkout;
- package and third-party licenses are present;
- corresponding GPL sources are configured when required;
- the publish dry run shows the expected release and files;
- `pr-checks.yml` accepts the package YAML, workflow association, commits, and
  any patch headers.

## 2. Publishing after merge

Merging the first contribution or an upgrade PR places a pending version on
`main`. The package workflow's `push` trigger builds and tests it again. This
second build is intentional: only reviewed code from `main` may publish.

For each selected version, `_publish-wheel.yml`:

1. downloads the matching artifacts and rejects an empty or mixed package/version
   set;
2. creates a draft GitHub Release targeting the triggering commit;
3. uses release title `<normalized-package>-v<version>` and tag
   `<normalized-package>-v<version>-<UTC timestamp>`;
4. uploads all wheels and, when configured, `gpl-sources.tar`;
5. publishes the release and verifies that repository immutable releases froze
   it;
6. runs `ci_scripts/update_doc.py` to record the publication.

Every successful `main` publication creates a new immutable release. A manual
rebuild therefore creates a new timestamped release rather than editing an old
one. Publication fails if no wheels match, wheels contain mixed names or
versions, the wheel version is undeclared, GPL sources are missing, or the
resulting release is not immutable.

### The package branch and PR

`update_doc.py` normalizes the wheel's project name and uses:

- branch: `package/<normalized-pkg>`;
- PR title: `<normalized-pkg>: update packages`;
- base: `main`.

If the branch already exists, it is fetched and rebased onto `main` before the
new commit is made. The push uses `--force-with-lease`, so an unexpected branch
update is rejected rather than overwritten. If an open PR already uses the
branch, publication pushes to it instead of opening another PR.

The publication commit fills the declared version entry with:

- the immutable release `tag`;
- every wheel's `filename` and SHA-256 digest;
- `requires-python` when present in wheel metadata;
- GPL source asset metadata when configured;
- `patched: true` when a matching patch directory exists;
- a per-version license only when wheel metadata identifies a meaningful change
  from the package's top-level license.

On a package's first publication, the same commit adds it to
`ci_scripts/packages.txt`, which makes it eligible for nightly checks.

### Serialization

The `publish` job in `_publish-wheel.yml` and the `check_versions` job in
`nightly.yml` use the same repository-wide concurrency group:

```yaml
concurrency:
  group: publish-wheel
  cancel-in-progress: false
  queue: max
```

Only one of these jobs mutates package branches at a time. `queue: max` retains
waiting jobs instead of replacing an older pending job, and
`cancel-in-progress: false` lets the active publication or nightly check finish.
This is deliberately job-level concurrency: package builds may proceed in
parallel, but branch/PR mutation is serialized.

## 3. Reviewing and completing publication

The automated package PR may contain a nightly declaration, publication
metadata, or both. Review the complete diff rather than assuming it came from
only one source.

For publication metadata, verify:

1. top-level `license` is a short valid identifier (preferably SPDX), not a file
   path or full license text;
2. every expected wheel is listed exactly once with the correct filename,
   SHA-256 digest, and `requires-python` value;
3. the tag names the expected immutable GitHub Release and its assets match the
   YAML;
4. `gpl-sources` is present when the wheel requires corresponding GPL sources;
5. `patched: true` and any `comment:` or `warning:` accurately describe carried
   changes;
6. no unrelated package files were changed.

Merging `<pkg>: update packages` places `tag` and `files` on `main`, so the
version is no longer pending. That push has two effects:

- the package build workflow may be triggered by its YAML path, but `_setup.yml`
  returns `[]`, so all guarded build/publish jobs skip;
- `website.yml` regenerates package pages and the static PEP 503/691 Simple API,
  builds the Jekyll site, and deploys it to `pypi.riseproject.dev`.

The GitHub Release exists before this merge, but pip cannot discover it through
the RISE index until the YAML reaches `main` and the website deployment
completes. Publication is therefore not complete until the package PR is merged
and the site deploy succeeds.

## 4. Nightly upgrades and maintenance

`nightly.yml` runs on a schedule (Mondays and Thursdays at 02:00 UTC), by manual dispatch, and for PRs that modify
its version-checking logic. Its `check_versions` job reads the tracked package
set from `ci_scripts/packages.txt` and compares package YAML/release state with
PyPI.

The detection phase leaves the checkout clean and writes reports. For each
package it can detect:

- stable PyPI releases not yet declared in the package YAML;
- released versions that PyPI has yanked;
- a point where upstream starts shipping a riscv64 wheel;
- a point where upstream switches to a universal pure-Python wheel, making a
  separate RISE binary build unnecessary;
- malformed/missing metadata or network/API errors.

A release already supplied upstream as riscv64 or pure Python is not added as a
new RISE build. Deprecation waits until all already-declared versions have been
published, so a pending build is not silently abandoned.

### One branch and PR per package

For every actionable result, the workflow re-runs
`check_versions.py --declare <package>` in isolation. It uses the same
`package/<normalized-pkg>` branch as publication:

1. fetch the existing package branch when present, otherwise start at `main`;
2. rebase existing package work onto the current `main` and push that rebase
   even if the requested declaration is already present;
3. declare new pending versions, mark yanked versions, or apply deprecation;
4. commit only `docs/packages/<pkg>.yaml` and, for deprecation, the relevant
   package/deprecated lists;
5. push with a lease when updating an existing branch;
6. open or update a draft PR titled `<normalized-pkg>: update packages`.

The PR body explains the detected upgrade/deprecation/yank. For an upgrade, the
new bare `- version:` entries trigger that package's `build-<pkg>.yml` PR run.
The build and publish dry run must pass before merge. Merging the nightly PR
then invokes the same `main` publication path described above.

Using the existing package branch is important when nightly and publication
cross paths. For example, if publication metadata is awaiting review and a new
upstream version appears, nightly rebases and appends the declaration instead
of replacing the metadata. Conversely, publication can fill a version already
declared by nightly on that branch. Shared concurrency prevents both jobs from
performing those operations simultaneously.

### Deprecation and yanks

When upstream supplies riscv64 wheels (including a compatible `abi3` wheel) or
only universal pure-Python wheels, nightly can propose deprecation. The package
YAML is marked deprecated, the package is removed from
`ci_scripts/packages.txt`, and it is added to `ci_scripts/deprecated.txt`.
`check_deprecated_packages` continues checking that deprecated upstream support
has not disappeared.

Versions yanked on PyPI are marked `yanked: true` in the package YAML. The
Simple API renders this using the corresponding package-index yank metadata.
A package PR can contain a yank together with an upgrade or deprecation.

The other nightly jobs are independent of package-branch mutation:

- `check_deprecated_packages` verifies that deprecated packages still provide a
  riscv64 or universal wheel upstream;
- `check_installation` performs a basic install of the tracked package set on a
  riscv64 runner;
- `pip_audit` scans the installed packages and reports vulnerabilities.

## 5. Manual rebuilds and failure recovery

Use `workflow_dispatch` only when intentionally rebuilding a declared version:

```sh
gh workflow run build-<pkg>.yml --ref main -f version='<glob>'
```

A glob can select released versions as well as pending ones. On `main`, each
match creates a new immutable release and updates its YAML entry to the newest
release. On a non-`main` ref, publication remains a dry run.

Important failure boundaries:

- If build or tests fail, no release is created.
- If release creation/upload succeeds but documentation update fails, the
  immutable release may already exist; rerunning creates another release.
- A force-with-lease failure means the package branch changed unexpectedly.
  Re-run after inspecting the branch; do not replace it with an unconditional
  force-push.
- If the package PR is not merged, the release remains undiscoverable in the
  RISE Simple API and the YAML version remains pending on `main`.
- Do not dispatch a rebuild merely because the normal post-merge `push` run is
  still queued or running.

## 6. Automation credentials

GitHub restricts recursive workflow triggering from the repository's default
`GITHUB_TOKEN`; depending on the event, runs are suppressed or require manual
approval. `nightly.yml` and `_publish-wheel.yml` therefore prefer an installation
token for the `riseproject-dev` GitHub App so package PR checks start normally.
They fall back to `GITHUB_TOKEN` when App credentials are unavailable, including
untrusted pull-request contexts.

Required repository configuration:

- variable `RISEPROJECT_APP_CLIENT_ID`;
- secret `RISEPROJECT_APP_PRIVATE_KEY`;
- App installation access to the repository, with write access to contents and
  pull requests and read access to issues.

Because `_publish-wheel.yml` is reusable, each package workflow must explicitly
pass the private key as `app-private-key`. Token permissions can only be
maintained or reduced across a reusable-workflow call, so the caller's publish
job must grant `contents: write` and `pull-requests: write`.

## 7. Related workflows

- `_setup.yml` selects pending or explicitly requested package versions.
- `_publish-wheel.yml` inspects artifacts, creates immutable releases, and
  updates package branches.
- `nightly.yml` detects upgrades, yanks, deprecations, installation failures,
  and known vulnerabilities.
- `pr-checks.yml` checks commit/PR policy, validates package YAML/workflow
  pairing, and validates patch `Upstream-Status` headers.
- `website.yml` turns `docs/packages/*.yaml` into package documentation and the
  Simple API, then deploys GitHub Pages.

## The RISC-V Wheels Dashboard

RISE maintains the [RISC-V Wheels]({{ '/dashboard/' | relative_url }}) dashboard,
which tracks riscv64 compatibility across the most-downloaded binary Python
wheels, including wheels available in the RISE index but not upstream. Consult
it before deciding whether a package still needs a `python-wheels` build.

The dashboard is regenerated during website deployment. Its generator is
vendored in `ci_scripts/dashboard/` from
[riseproject-dev/python-wheels-dashboard](https://github.com/riseproject-dev/python-wheels-dashboard),
which remains its upstream source of truth.
