---
title: Workflows Reference
layout: default
nav_order: 8
---

# Workflows

## python-wheels Contribution Guidelines

For general contributions, use a coding assistant such as Claude to accelerate
creation of new package workflows (the repository already contains a CLAUDE.md
with useful lessons from previous efforts). LLM-generated code should **not** be
considered sufficient without user review. For best practices, reference
[docs/development.md](development). Briefly:

1. Workflows should be designed to mirror the upstream equivalents' linux +
   glibc build/test processes, deviating only where necessary and with
   documentation as to why.
2. **A brand-new package is two files: `build-<package>.yml` and
   `docs/packages/<package>.yaml`.** The YAML declares the versions to build
   (see [Declaring Versions](development#declaring-versions)); the workflow
   must keep all three triggers, `workflow_dispatch`, `pull_request: paths`
   and `push: paths`, each pointing at both files. GitHub only lets you
   dispatch a workflow that has already produced at least one run on the
   repository; a file that exists solely on a PR branch is not yet registered,
   so a `workflow_dispatch` fails with `HTTP 404`. The `pull_request: paths`
   run from opening the PR is what registers it, and builds the pending
   versions. Never drop this trigger to "avoid a duplicate CI run" it's the
   only way a new package's build ever starts.
3. The `_publish-wheel.yml` reusable workflow must be used in place of any
   upstream deployment procedure. It performs a dry run on pull requests and
   publishes immutable GitHub Releases when run from `main`. In
   particular, the contributor **must** check that the correct number of wheels
   are generated and selected for upload.
4. Built wheels need to be inspected for license compliance, both to ensure that
   the package ships its own licensing information and that any third-party
   libraries which are statically linked are also properly handled (which is
   sometimes not the case for upstream projects). If GPL-licensed sources (e.g.
   the build environment's `gcc`) end up linked into a wheel, the
   `collect-gpl-sources` action must be used to publish those sources
   permanently alongside the release.
5. Merging the contribution pushes the pending version to `main`, which runs
   the workflow again through its `push` trigger. That run creates a new
   immutable GitHub Release and opens or updates the shared documentation PR.
   The release becomes visible through the RISE Simple API only after that
   documentation PR is reviewed, merged, and deployed. The maintainer also
   opens (or reuses) a tracking issue for the package and links it to the PR.

## Reviewing a Documentation PR

Documentation updates are generated as part of the `_publish-wheel.yml`
workflow, which runs `ci_scripts/update_doc.py` against every newly built wheel.
It fills in the version's declared entry with the immutable release tag and,
for every wheel, the filename, SHA-256 hash, and optional `Requires-Python`
value. These YAML files are the source of truth for both the package
documentation and the static Simple API. This is separate from `.github/workflows/website.yml`, which builds
and deploys the site, including documentation previews. The generated
pull requests need to be checked against the following criteria:

1. The `license` field indicating the current project license should only ever
   be placed near the top of the file, not under each new package version. The
   exception to this is if the licensing terms vary across different versions,
   in which case they should be carefully checked, with the new license
   specified in the top-level `license` field, and with previous versions having
   their own `license` field declaring their respective licenses.
2. The `license` field needs to contain a valid license string (e.g. `MIT`).  In
   some upstream packages this is pointed at a `LICENSE` file or similar in
   pyproject.toml, and this can result in the draft PRs including the entire
   license text in the documentation file. This should be replaced with the
   actual license type. For valid license strings, review the [SPDX
   list](https://spdx.org/licenses/).
3. Each released version entry must contain the latest release tag and list
   every expected wheel with the correct filename, SHA-256 hash, and
   `Requires-Python` value. An entry with neither `tag` nor `files` is still
   pending and will be built again by the next push touching the package. If
   the package linked against one or more GPL-licensed projects, the same
   version entry must also record its `gpl-sources.tar` asset.
4. `patched: true` should be added if one or more patches are applied to the
   source for each version. If omitted, it defaults to `false`. This will
   produce a link to the appropriate patches
   located under `patches/<package>/<version>`.
5. If the package workflow deviates significantly from the upstream
   equivalent but does so **without** using a patch file (such as disabling
   certain tests with `pytest -k`, or using a different set of dependencies) a
   separate `warning:` field should be added indicating the details.
6. Documentation PRs trigger builds for preview versions of the documentation.
   **Before** merging this should be checked to ensure that the generated
   changes are as expected.

## Developer Automation

To assist with contributions, the `python-wheels` repository contains the
following workflows beyond those used for specific package builds:

1. `website.yml`: Builds and deploys documentation changes to GitHub Pages
2. `nightly.yml`: Performs a nightly comparison of supported package versions in
   the RISE package index against those available upstream. It also creates
   'deprecation' PRs for packages which support riscv64 upstream (meaning that
   RISE no longer needs to support them separately), and runs a basic
   `pip_audit` run against our package list.
3. `pr-checks.yml`: Checks commits in each PR to ensure no 'revertme' or 'DO NOT
   MERGE' tags are included in the subject lines, since commits of this type may
   be used for testing but should never be valid for merge. It also ensures that
   a valid `Upstream-Status` tag is included in every custom patch we include
   when deviating from upstream packages' workflow/source checkouts, and that
   every changed `docs/packages/*.yaml` is well-formed and every changed
   build workflow has one.
4. `_setup.yml`: Called first by every `build-<package>.yml`; reads
   `docs/packages/<package>.yaml` and outputs the versions to build (the
   pending ones, or those matching the `version` glob of a
   `workflow_dispatch`).

## The RISC-V Wheels Dashboard

RISE makes use of the [RISC-V
Wheels](https://stanfromireland.github.io/riscv-wheels/) dashboard, which tracks
the status of riscv64 compatibility for 360 binary Python wheels. This provides
a detailed look at ecosystem-wide support, including wheels which are available
in the RISE package index but not yet upstream. It should be the first reference when
determining which packages to contribute support for and at what level (i.e.
upstream versus `python-wheels`).
