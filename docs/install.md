---
title: Installing the Packages
layout: default
nav_order: 3
---

# Installing the Packages

The built wheels are stored as immutable assets in this project's [GitHub
Releases](https://github.com/riseproject-dev/python-wheels/releases) and exposed
through a static Python Simple Repository API. To install them, first upgrade
pip to the latest version, e.g.,

```bash
python -m pip install --upgrade pip
```

and then pass the `--index-url` option to the install command to tell pip to
pull packages from the RISE package index, e.g.,

```bash
python -m pip install scipy --index-url https://pypi.riseproject.dev/simple/
```

{: .note }
> Some riscv64 packages are now built and published upstream on PyPI. We will
> no longer build, upgrade and publish them as part of the `python-wheels`
> project.
>
> To make sure to always install the latest version available, use
>
> ```bash
> python -m pip install scipy --prefer-binary --extra-index-url https://pypi.riseproject.dev/simple/
> ```
>
> This will:
>
> - search both PyPI and the RISE package index.
> - pick the highest available version.
> - prefer binary wheels over source distributions.
>
> This ensures we get wheels from PyPI when available, while falling back to
> our package index for packages without riscv64 wheels, avoiding unnecessary
> source builds.

{: .warning }
> In general, `--extra-index-url` should be used very carefully (see
> <https://peps.python.org/pep-0708/#motivation>).
>
> The RISE package index only contains wheels for packages that have
> pre-existing counterparts in PyPI, so it is safe to use it in that context.
