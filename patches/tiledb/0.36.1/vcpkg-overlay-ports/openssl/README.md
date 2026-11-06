# riscv64 overlay for vcpkg's `openssl` port

Vendored from `microsoft/vcpkg` at the commit TileDB 2.30.1 (the libtiledb core this
`tiledb` port builds) pins as its `builtin-baseline`
(`dd930e314f529c86d2703a60d5ea7dd6573d9e5a`, `ports/openssl` at `openssl@3.6.1#2`),
unmodified except for `unix/portfile.cmake` (the actual fix, below) and the `*.patch`
files vcpkg ships for this port, renamed to `*.diff` (content byte-for-byte identical;
`portfile.cmake`'s own `PATCHES` list renamed to match) purely so this repo's
`ci_scripts/check_patch.py` - which requires an `Upstream-Status:` tag on every
`*.patch` file a PR adds or changes - doesn't mistake vcpkg's own vendored patches
for ones we authored.

**Why this exists**: vcpkg's own `ports/openssl/unix/portfile.cmake` maps
`VCPKG_TARGET_ARCHITECTURE` to an OpenSSL `Configure` target for Linux
(`linux-aarch64`/`linux-armv4`/`linux-x86_64`/`linux-x86`), with no `riscv64` case, so it
falls into the `else()` branch and configures OpenSSL as `linux-generic32` - a *32-bit*
target. Meanwhile the *top-level* `ports/openssl/portfile.cmake` (one directory up)
already appends `enable-ec_nistp_64_gcc_128` to `CONFIGURE_OPTIONS` whenever
`VCPKG_TARGET_ARCHITECTURE MATCHES "^(x64|arm64|riscv64|ppc64le)$"` - riscv64 included.
That flag requires a 64-bit `bn_ops`, so handing it to a `linux-generic32` configure makes
OpenSSL's `Configure` die immediately (`CMake Error ... vcpkg_execute_required_process ...
error: building openssl:riscv64-linux-release failed with: BUILD_FAILED`, seen on PR #3183's
`Build libtiledb for tiledb 0.36.1` job). This looks like a plain inconsistency inside
vcpkg's own port - the two portfiles don't agree on whether riscv64 is a supported,
64-bit target - not something specific to this repo's build.

**The fix**: add a `riscv64` case to `unix/portfile.cmake`'s `OPENSSL_ARCH` selection,
mapping it to `linux-generic64` (OpenSSL's 64-bit, assembly-free generic target -
`bn_ops SIXTY_FOUR_BIT_LONG`). **Not** `linux64-riscv64`: that target builds, but its
`crypto/aes/asm/aes-riscv64.pl` calls the exported `AES_set_encrypt_key` with a plain
`jal`, which can't reach across the PLT of a sufficiently large shared object
(`R_RISCV_JAL` relocation truncated) - the same asm-reach failure mode CLAUDE.md gotcha
625 documents for Conan's `openssl` recipe, and libtiledb statically links OpenSSL into
one large `libtiledb.so`. `linux-generic64` is the same 64-bit/no-asm choice gotcha 625
lands on for that reason.

How this overlay reaches the build: `build-tiledb.yml`'s `build_libtiledb` job passes
`-DVCPKG_OVERLAY_PORTS=.../patches/tiledb/0.36.1/vcpkg-overlay-ports` to libtiledb's CMake
configure, which vcpkg's toolchain file (`scripts/buildsystems/vcpkg.cmake`) reads and
prefers over the registry's own `openssl` port.
