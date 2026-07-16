---
title: Development Guide
layout: default
nav_order: 6
---

# Development Guide

Structurally, the [python-wheels](https://github.com/riseproject-dev/python-wheels) repository has four goals:

1. Provide a simple interface for users to install Python wheels from.
2. Create GitHub Actions workflows for building binary Python wheels that
   closely match upstream projects' existing CI/CD, but which build and test
   only for riscv64.
3. Add supplemental workflows and tooling to track upstream releases, automate
   version upgrades, and simplify deprecation once upstream projects incorporate
   riscv64 builds, allowing developers to focus on broader package support.
4. Serve as a reference to upstream maintainers, indicating that their projects
   can easily add support for riscv64.

## Workflow Creation Process

`python-wheels` workflows should closely match those for the upstream project to
ensure that our build process for riscv64 wheels is consistent and can be
submitted to the upstream maintainers as evidence of feasibility. Unless
otherwise noted, this guide will reference the existing `build-numpy.yml`
workflow for example code.

The general process:

1. Review the upstream project's build and test workflows (they may be called
   `python.yml`, `wheel.yml`, `build.yml`, `release.yml`, or something else
   entirely), identifying the section(s) which build for Linux with glibc and
   musl.
2. Create a copy of the upstream build workflow in the `python-wheels` repo at
   `.github/workflows/build-<package>.yml`, where `<package>` matches the
   project name (e.g. `build-numpy.yml` for NumPy`).
3. Remove any workflow logic not related to the Linux glibc and musl (if
   present) build processes, support for other architectures and operating
   systems (e.g. Windows, Mac OS). This includes the sdist build (unless it is
   consumed by a build or test step).
4. Repeat steps #2 and #3 for the corresponding test workflow, if it is separate
   from the upstream build file.

From this point, some customizations are required to enable builds targeting
riscv64.

## Workflow Customizations for riscv64

### riscv64 Runners

We make use of the official [RISE RISC-V
Runners](https://riscv-runners.riseproject.dev/) for any jobs which should run
on a riscv64 platform, particularly build and test jobs. The `python-wheels`
repository is already configured to access them. The `runs-on` directives in any
new workflows should be changed like so:

```
jobs:
  build:
    runs-on: ubuntu-24.04-riscv
```

### Target Python Versions

Previously RISE has used a Python version matrix covering the four latest
releases (`major.minor`, e.g. `3.14`), plus any freethreaded variants available
(e.g. `3.14t`). As of July 14th, 2026, this includes Pythons 3.11, 3.12, 3.13,
and 3.14 (along with 3.14t, the freethreaded equivalent). However, the NumPy
project (as of version 2.5.0) supports Python 3.12 as the minimum. Since this
package is fundamental to many others which we are supporting, we will follow
its precedent when defining our version matrix. Some wheels have previously been
built for 3.13t, but since this was an experimental version with limited support
we avoid it now.

With these factors, our default version matrix becomes:

`['3.12', '3.13', '3.14', '3.14t']`

Exceptions may be necessary for some packages, which should be carefully
considered to balance achieving similarity to upstream with feasibility of
maintenance.

### uv

The official `actions/setup-python` Action does not yet support riscv64 builds,
so workflows using it will fall back to using the host version (if one
is present matching the `major.minor` numbering used by the workflow, e.g.
`3.12`). A simple alternative is to replace any usage of `actions/setup-python`
in the upstream workflow with `astral-sh/setup-uv` like so:

```
- uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39  # v8.2.0
  name: Install Python
  with:
    python-version: '3.12'
    activate-environment: true
    enable-cache: false
```

Note the `python-version` 'activate-environment', and 'enable-cache' options.
The first two allow us to select the environment Python and have it pre-enabled
(matching `actions/setup-python` behaviour for our purposes). The `enable-cache`
option is disabled for now, as it has caused failures in previous build
attempts.

### Upstream Project Checkouts

We use the `actions/checkout` action to checkout the upstream repository at the
desired tag:

```
- name: Checkout numpy v${{ env.NUMPY_VERSION }}
  uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0  # v7.0.0
  with:
    repository: numpy/numpy
    ref: v${{ env.NUMPY_VERSION }}
    submodules: true
    persist-credentials: false
```

This effectively overwrites the default project layout for the workflow, which
would otherwise be a copy of `python-wheels`. It allows our workflows to operate
as if they are part of the upstream project without having to include them in a
fork. More importantly, it is critical for uncomplicated usage of tools like
cibuildwheel, which assumes that the root directory is the project to be built
when invoked.

### Using the python-wheels Repository in Workflows

The `python-wheels` repository contains some custom Actions we require, and
patch files to apply for certain projects. The one every `build-<package>.yml`
workflow needs is `publish-wheels`, which performs the following steps:

1. Downloads the built wheel(s) from the previous job
2. Uploads them to the GitLab PyPI registry (via the lower-level
   `publish-to-gitlab` Action)
3. Opens a PR against `docs/packages/<name>.yaml` documenting the new version
   (via `ci_scripts/update_doc.py`), which `docs/packages/generate_packages_doc.py`
   later renders into the published Markdown page. With it in place, the
   `build-numpy.yml` script's `publish` job looks like this:

```
publish:
  name: Publish numpy ${{ inputs.version || '2.5.0' }} to GitLab
  needs: build_wheels
  # Only publish when the workflow was triggered from main with a specific
  # version. Manual trigger is the only entry point, so checking the ref is
  # enough to gate uploads.
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  permissions:
    contents: write
    pull-requests: write

  steps:
    - name: Publish wheels and open docs PR
      uses: riseproject-dev/python-wheels/actions/publish-wheels@main
      with:
        artifact-pattern: numpy-${{ env.NUMPY_VERSION }}-*-manylinux_riscv64
        gitlab-username: ${{ vars.GITLAB_DEPLOY_USER }}
        gitlab-token: ${{ secrets.GITLAB_DEPLOY_TOKEN }}
        gitlab-project-id: ${{ vars.GITLAB_PROJECT_ID }}
        gh-token: ${{ secrets.GITHUB_TOKEN }}
```

`permissions` needs `contents: write` and `pull-requests: write` here (not just
`contents: read`) since the docs step pushes a branch and opens a PR with the
default `GITHUB_TOKEN`.

Other workflows need to follow the same process, modifying `artifact-pattern` to
match their own artifact naming scheme and otherwise reusing `publish-wheels`
like the example. The `publish-to-gitlab` Action should only be used directly if
a workflow needs the upload step without the docs PR side effect.

## Testing a New Workflow

Open a new draft PR with the workflow(s) included, and include a `Trigger:` line
in the PR description with a version for each package version you want to build,
like so:

`Trigger: numpy:v2.5.0`
`Trigger: numpy:v2.5.1`

The repository's automation logic will pick up on and trigger the appropriate
build workflows for each version. Achieving a passing (green) build may require
several attempts including rework and possible patches, depending on the nature
of the failure.

### Skipping musl Builds

While building for both glibc and musl (in cibuildwheel terms, `manylinux` and
`musllinux`) is desirable, some of the projects we target do not build for
musllinux (or they do, but run into various issues on riscv64 specifically), and
so dependent packages cannot rely on musl versions of the packages either. If
the musl builds fail without an obvious solution, strip those jobs from the
workflow and retry, while opening an issue to track the musl incompatibility.

### Patching a Project

Some workflows may fail consistently when building or testing a module, despite
following the guidelines above. When this occurs, consider whether the failure
meets one of the following criteria:

1. The failure exercises a narrow part of the module's functionality, or relies
   on external resources (e.g. large downloads over the network)
2. The failure is due to reliance on some other software unavailable on riscv64
3. The failure is a consequence of an artificial test limitation, e.g. a maximum
   timeout
4. The project's build scripts use host tooling which isn't available on the
   runners or in the riscv64 manylinux images (e.g. `apt` vs `dnf`)

Additionally, some packages may not fully incorporate all of the LICENSE files
found in their repositories or as required by their dependencies. See the
[Licensing](#licensing) section for more info on this topic. In these cases, it
may be justified to add one or more patch files to remove these cases from the
workflow. In this scenario, follow these steps:

1. Any such patches should be placed in a `patches/<package_name>/<version_tag>`
   path inside `python-wheels`.
2. Each patch should include an `Upstream-Status` tag. See the [Upstream Status
   Tags](#upstream-status-tags) section for details on valid types.
3. An extra step should be added to the build/test workflows before execution to
   use `git apply` to make necessary modifications to the project source.
4. The change should be documented for the package, so that users are aware of
   modifications made.

**Note: Patching should be performed and reviewed on a case-by-case basis - as
much functionality as possible should be tested by our system to ensure a smooth
user experience when consuming wheels from RISE's package registry.**

## Releasing a Wheel

The `publish-to-gitlab` action does not run unless the workflow is triggered
from main. This is intentional, and is meant to ensure that only those workflows
which have been fully tested, reviewed, and merged are used to build and push
packages. Following the merge of a PR, the workflow(s) must be re-triggered from
the `main` branch in order to release the wheels to the package registry.

## Other Workflow Tips and Tricks

### Licensing

The wheels built by the `python-wheels` project use a variety of open-source
licenses. Since RISE is the distributor of riscv64 wheels in the corresponding
package registry, we must ensure that the wheels adhere to each project's
licensing requirements. More specifically, check:

1. The built wheel contains one or more `LICENSE` files corresponding to those
   contained in the upstream project source.
2. If the wheel ships any statically- or dynamically-linked libraries from other
   projects, the licensing requirements for those projects are also correctly
   addressed.

If either point is not met, we should follow the [Patching a
Project](#patching-a-project) process for patching our build, and submit an
issue and/or PR upstream to help them comply with license requirements as well.

### Adding Builds for Rust Packages

Modules which are cross-compiled from Rust to Python typically use
[maturin](https://www.maturin.rs/). This greatly simplifies building binary
wheels for riscv64, but there is a pitfall here to watch out for - many projects
use a matrix definition looking like:

```
matrix:
  platform:
    - runner: ubuntu-22.04
      target: x86_64
    - runner: ubuntu-22.04
      target: x86
    - runner: ubuntu-22.04
      target: aarch64
    - runner: ubuntu-22.04
      target: armv7
    - runner: ubuntu-22.04
      target: ppc64le
```

For riscv64 and some other architectures, the `rustc` toolchain target name does
not follow this simple pattern (i.e. the `arch` part of the triple is not exact):

```
tgamblin@alchemist ~/workspace/baylibre/rise/python-wheels (tgamblin/dev-guide)$ rustup target list | grep riscv64
riscv64a23-unknown-linux-gnu
riscv64gc-unknown-linux-gnu
riscv64gc-unknown-linux-musl
riscv64gc-unknown-none-elf
riscv64imac-unknown-none-elf
```

Simply adding a new line with `target: riscv64` will lead to build failures. The
recommended approach here is to make the matrix more explicit, then add riscv64,
so that each entry looks like:

```
- runner: ubuntu-24.04-riscv
  target: riscv64gc-unknown-linux-gnu
  arch: riscv64
```

Note that doing so typically requires a tweak to an `Upload wheels` step or
similar, so that it uses the `arch` field:

```
- name: Upload wheels
  uses: actions/upload-artifact@v4
  with:
    name: wheels-linux-${{ matrix.platform.arch }}
    path: dist
```

### GCC Version Mismatches

Some packages may require GCC 14 or later to compile for riscv64. If your build
requires GCC 14, ensure that you are either using a cibuildwheel container
approach, or (if the project doesn't use cibuildwheel) have an appropriate
workaround in place, since the RISC-V runners currently ship GCC 13 by default.

### Upstream Status Tags

We use a pattern established by the [Yocto
Project](https://docs.yoctoproject.org/dev/contributor-guide/recipe-style-guide.html#patch-upstream-status)
for indicating the purpose and status of custom patches which we carry for
various projects. Each tag should be specified in the patch file's commit
message like so:

```
Upstream-Status: <type> [reason and/or link]
```

There are five valid `Upstream-Status` types for the `python-wheels` repository:

1. `Issue`: An issue has been opened on the upstream project to indicate a bug
   was found during build/test. The issue link should be included.
2. `Submitted`: A change was submitted to fix an issue upstream, but we are
   carrying the patch ourselves until it's merged and released in a future
   version. Include a link to the upstream PR and/or merged commit.
3. `To upstream`: The patch needs to be submitted upstream, but submission is
   blocked. Include an explanation of why it can't be submitted upstream yet.
4. `Inappropriate`: The patch includes changes which are necessary for riscv64
   builds and/or our infrastructure, but are not relevant upstream. Include a
   short description of why.
5. `Backport`: The patch includes a fix which is already merged in an upstream
   release version, but not in the version we're trying to build. Include a link
   and short description of the problem.

Including an `Upstream-Status` tag is a baseline requirement for custom patches,
and it is automatically searched for by the `ci_scripts/check_patch.py` script
when submitting a PR. However, any additional detail which can be provided in
each patch's commit message is helpful for maintenance.
