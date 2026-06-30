---
title: Manylinux_2_35 and Manylinux_2_39
layout: default
nav_order: 4
---

# Manylinux_2_35 and Manylinux_2_39

The packages distributed in this registry are a mix of manylinux_2_35 and
manylinux_2_39 wheels. Support for manylinux wheels for riscv64 was added to
pip in version 24.1 so you must have pip 24.1 or greater installed locally in
order to install the packages. This is why we recommend upgrading pip above
before installing anything. Prior to the release of pip 24.1, some wheels with
the linux tag were created for a select set of packages and uploaded to this
package registry. If your version of pip is older than 24.1 pip will install
these older wheels instead of the manylinux wheels, if they are available.
This is probably not what you want so do upgrade pip.

These older packages in this registry with the 'linux' platform tag, e.g.,
`numpy-1.26.4-cp39-cp39-linux_riscv64.whl`, actually behave like manylinux_2_35
wheels. These wheels were generated because we didn't want to wait for the
release of pip 24.1 to begin distributing riscv64 wheels, so while we were
waiting, we used a modified auditwheel that generates wheels with the linux
platform tag that mostly behave like manylinux_2_35 wheels. This means that
the wheels will work on any Linux distribution with glibc 2.35 or greater. The
wheels also vendor all of their dependencies that are not on the
manylinux_2_35 whitelist, e.g., OpenBLAS and libgfortran. One downside of
misusing the platform tag in this way is that pip will not warn you when you
install the wheels on distributions that use a glibc older than 2.35. In this
case the wheels will install but will be unlikely to work. As most riscv64
users are expected to use recent distributions to benefit from the latest
riscv64 support from the kernel and toolchains, this hopefully won't be too
much of an issue.

The manylinux_2_39 wheels are built with the upstream manylinux_2_39_riscv64
image. There are a few exceptions that were built with a custom
manylinux_2_39_riscv64 based on RockyLinux 10 which we used for a short period
of time before the official manylinux_2_39_riscv64 images were published.

All earlier wheels are built using a custom manylinux_2_35 based on Ubuntu
22.04. See the local
[riseproject/python/manylinux](https://gitlab.com/riseproject/python/manylinux)
fork for more details.
