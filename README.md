# RISE Python Wheels

RISE Python Wheels is a public project enabling the RISC-V support for the
Python ecosystem. It makes use of the RISE [RISC-V
Runners](https://riscv-runners.riseproject.dev/) project to build wheels on
native riscv64 hardware, with the goal of maintaining a riscv64-specific package
repository for projects where upstream are not yet ready or able to perform
builds themselves.

This work is a continuation of the earlier
[wheel_builder](https://gitlab.com/riseproject/python/wheel_builder) project,
which hosts binary wheels for a variety of Python modules.

For more informatiion about RISE, visit the [project
website](https://riseproject.dev/).

## Motivation

Python is commonly used in the fields of scientific computing, data analysis and
machine learning. However, the Python packages used in these disciplines aren’t
wholly written in Python - they also contain a lot of code written in C/C++ or
other languages which needs to be built as part of the module. Such projects
typically create binary wheels for each of their releases and upload these
wheels to pypi, the Python Package Index. This allows users to easily and
quickly install tested, prebuilt versions of their favourite projects using the
pip (or [uv](https://docs.astral.sh/uv/)) tool.

Until recently, Python packaging infrastructure like
[auditwheel](https://github.com/pypa/auditwheel),
[cibuildwheel](https://github.com/pypa/cibuildwheel), and
[manylinux](https://github.com/pypa/manylinux) did not support riscv64, and no
native runners for GitHub Actions were available. This made supporting the
architecture difficult for open-source projects without complicated build
processes and emulated systems. However, the aforementioned infrastructure now
supports riscv64, and with the RISE [RISC-V
Runners](https://riscv-runners.riseproject.dev/) project, maintainers have the
option of building binary wheels on native riscv64 platforms. The RISE Python
Wheels project's goal is to accelerate this adoption and ensure that the riscv64
architecture is fully-supported for data science and machine learning
applications.

## Installing the Packages

Under Construction

## Contributing

Under Construction
