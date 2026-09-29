# RISE Python Wheels

[RISE Python Wheels](https://pypi.riseproject.dev) is a public project enabling the RISC-V support for the
Python ecosystem. It makes use of the [RISE RISC-V Runners](https://riscv-runners.riseproject.dev/)
project to build wheels on native riscv64 hardware, with the goal of maintaining a riscv64-specific package
repository for projects where upstream are not yet ready or able to perform builds themselves.

## About RISE

[RISE](https://riseproject.dev) is a collaborative, industry-led initiative under the Linux Foundation that accelerates open-source software development for the RISC-V architecture.

## Usage

Installing Python wheels from the RISE registry is as easy as:

```bash
python -m pip install --upgrade pip
```

and then pass the `--index-url` option to the install command to tell pip to
pull packages from the RISE package index, e.g.,

```bash
python -m pip install scipy --index-url https://pypi.riseproject.dev/simple/
```

Find complete documentation on [the python-wheels website](https://pypi.riseproject.dev/)

## Background

This work is a continuation of the earlier [wheel_builder](https://gitlab.com/riseproject/python/wheel_builder) project.
