#!/bin/bash
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# Mirrors the build environment of upstream's docker/wheel.Dockerfile: a
# statically linked OpenSSL for reqwest's native-tls backend, plus the pinned
# Rust toolchain.
set -euxo pipefail

OPENSSL_VERSION=3.5.7
RUST_VERSION=1.96.0

# libstdc++-static is added to upstream's list: build.rs links the C++ memalloc
# profiler statically and Rocky 10 keeps libstdc++.a out of the default install.
yum -y install gcc perl-core glibc-devel make libstdc++-static

curl -fsSL "https://github.com/openssl/openssl/releases/download/openssl-${OPENSSL_VERSION}/openssl-${OPENSSL_VERSION}.tar.gz" -o /tmp/openssl.tar.gz
tar xzf /tmp/openssl.tar.gz -C /tmp
cd "/tmp/openssl-${OPENSSL_VERSION}"
./config no-shared no-tests --prefix=/usr/local/openssl --openssldir=/etc/ssl
make -j"$(nproc)"
make install_sw
ln -sf /usr/local/openssl/lib64 /usr/local/openssl/lib || true
cd /
rm -rf /tmp/openssl*

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs |
    sh -s -- -y --profile minimal --default-toolchain "${RUST_VERSION}"
