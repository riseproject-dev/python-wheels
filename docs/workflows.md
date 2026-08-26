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
2. **A brand-new `build-<package>.yml` must keep both the `workflow_dispatch`
   and `pull_request: paths` triggers.** GitHub only lets you dispatch a
   workflow that has already produced at least one run on the repository; a
   file that exists solely on a PR branch is not yet registered, so
   `workflow_dispatch` and a `Trigger:` line (see below) both fail with
   `HTTP 404`. The `pull_request: paths` run from opening the PR is what
   registers it. Never drop this trigger to "avoid a duplicate CI run" it's
   the only way a new package's build ever starts.
3. The `publish-wheels` action must be used in place of any upstream deployment
   procedure. It provides a dry-run mechanism for in-flight PRs, and consistent
   deployment of wheels to the RISE registry on merge to `main`. In particular,
   the contributor **must** check that the correct number of wheels are
   generated and selected for upload.
4. Built wheels need to be inspected for license compliance, both to ensure that
   the package ships its own licensing information and that any third-party
   libraries which are statically linked are also properly handled (which is
   sometimes not the case for upstream projects). If GPL-licensed sources (e.g.
   the build environment's `gcc`) end up linked into a wheel, the
   `collect-gpl-sources` action must be used to publish those sources
   permanently alongside the release.
5. After the contribution is merged, the workflow needs to be re-triggered from
   the `main` branch by a maintainer for the packages to be deployed to the RISE
   registry, and a new documentation PR to be auto-generated for the new
   version. The maintainer also opens (or reuses) a tracking issue for the
   package and links it to the PR.

## Reviewing a Documentation PR

Documentation updates are generated as part of the `publish-wheels` workflow,
which runs the `ci_scripts/update_doc.py` script against the newly-built wheels'
metadata. This is not to be confused with `.github/workflows/docs.yml`, which
generates updates to the GitHub Pages documentation (including previews in docs
PRs) based on these updates. The corresponding draft PRs need to be checked
against the following criteria:

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
3. If the package linked against one or more GPL-licensed projects as part of
   the build, the documentation needs to provide a `comment:` field with links
   to the GPL source archives generated as part of the workflows.
4. A `patched:` field should be added if one or more patches are applied to the
   source for each version. This will produce a link to the appropriate patches
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

1. `docs.yml`: Builds and deploys documentation changes to GitHub Pages
2. `nightly.yml`: Performs a nightly comparison of supported package versions in
   the RISE registry against those available upstream. It also creates
   'deprecation' PRs for packages which support riscv64 upstream (meaning that
   RISE no longer needs to support them separately), and runs a basic
   `pip_audit` run against our package list.
3. `pr-checks.yml`: Checks commits in each PR to ensure no 'revertme' or 'DO NOT
   MERGE' tags are included in the subject lines, since commits of this type may
   be used for testing but should never be valid for merge. It also ensures that
   a valid `Upstream-Status` tag is included in every custom patch we include
   when deviating from upstream packages' workflow/source checkouts.
4. `pr-trigger.yml`: Provides a supplemental trigger mechanism for contributors,
   allowing additional workflow runs for one or more packages to be triggered
   with a PR by specifying the `Trigger: <package>:<version>` directive in the
   PR description. This is only necessary if the default version in a workflow
   is not the only one to be built, or if other maintenance-style changes are
   being made where the contributors would like to validate behaviour. Note
   this only works for workflows already registered on GitHub (i.e. already
   merged to `main`, or having produced at least one `pull_request` run — see
   above).

## The RISC-V Wheels Dashboard

RISE makes use of the [RISC-V
Wheels](https://stanfromireland.github.io/riscv-wheels/) dashboard, which tracks
the status of riscv64 compatibility for 360 binary Python wheels. This provides
a detailed look at ecosystem-wide support, including wheels which are available
in the RISE registry but not yet upstream. It should be the first reference when
determining which packages to contribute support for and at what level (i.e.
upstream versus `python-wheels`).
