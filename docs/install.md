---
title: Installing the Packages
layout: default
nav_order: 3
---

# Installing the Packages

The built wheels are hosted in the [package
registry](https://gitlab.com/riseproject/python/wheel_builder/-/packages)
associated with the riseproject/python/wheel_builder project. To install them,
first upgrade pip to the latest version, e.g.,

```bash
python -m pip install --upgrade pip
```

and then pass the `--index-url` option to the install command to tell pip to
pull packages from the registry associated with this project, e.g.,

```bash
python -m pip install scipy --index-url https://gitlab.com/api/v4/projects/riseproject%2Fpython%2Fwheel_builder/packages/pypi/simple
```

{: .note }
> Some riscv64 packages are now built and published upstream on PyPI. We will
> no longer build, upgrade and publish them as part of the wheel_builder
> project.
>
> To make sure to always install the latest version available, use
>
> ```bash
> python -m pip install scipy --prefer-binary --extra-index-url https://gitlab.com/api/v4/projects/riseproject%2Fpython%2Fwheel_builder/packages/pypi/simple
> ```
>
> This will:
>
> - search both PyPI and the internal registry.
> - pick the highest available version.
> - prefer binary wheels over source distributions.
>
> This ensures we get wheels from PyPI when available, while falling back to
> our registry for packages without riscv64 wheels, avoiding unnecessary source
> builds.

{: .warning }
> In general, `--extra-index-url` should be used very carefully (see
> <https://peps.python.org/pep-0708/#motivation>).
>
> The wheel_builder registry only contains wheels for packages that have
> pre-existing counterparts in PyPI, so it is safe to use it in that context.
