#!/bin/bash
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# Stage, at the project root, the licence of everything that ends up inside the
# wheel: the libunwind built by before-all, memray's vendored libbacktrace, and
# every shared library auditwheel vendors out of the build image.
# scikit-build-core's default LICEN[CS]E* glob copies them into the wheel.
set -euo pipefail

project="${1:?usage: collect-licenses.sh <project-dir> <libunwind-src-dir>}"
unwind_src="${2:?usage: collect-licenses.sh <project-dir> <libunwind-src-dir>}"

cp "$unwind_src/COPYING" "$project/LICENSE.libunwind"
cp "$project/src/vendor/libbacktrace/LICENSE" "$project/LICENSE.libbacktrace"

roots=(/usr/lib64/libunwind.so /usr/lib64/liblz4.so /usr/lib64/libdebuginfod.so)

# ldd is transitive, so memray's direct link dependencies cover the whole
# closure; ldd does not list the roots themselves, so resolve those too.
mapfile -t libs < <(
    {
        ldd "${roots[@]}" | tr ' ' '\n' | grep '^/'
        readlink -f "${roots[@]}"
    } | sort -u
)

# `rpm -qf` reports unowned files on stdout, so keep only bare package names.
# glibc, the gcc runtime and zlib are on auditwheel's manylinux allowlist and
# are never vendored into the wheel.
mapfile -t pkgs < <(
    rpm -qf --qf '%{NAME}\n' "${libs[@]}" 2>/dev/null |
        grep -E '^[A-Za-z0-9._+-]+$' | sort -u |
        grep -vE '^(glibc|libgcc|libstdc\+\+|gcc|zlib-ng-compat)$'
)

for pkg in "${pkgs[@]}"; do
    mapfile -t files < <(rpm -q --licensefiles "$pkg" 2>/dev/null || true)

    # Some subpackages leave the licence to a sibling of the same source RPM.
    if [ -z "${files[0]:-}" ]; then
        srpm=$(rpm -q --qf '%{SOURCERPM}\n' "$pkg")
        mapfile -t files < <(
            rpm -qa --qf '%{SOURCERPM} %{NAME}\n' |
                awk -v s="$srpm" '$1 == s { print $2 }' |
                xargs -r rpm -q --licensefiles 2>/dev/null | sort -u
        )
    fi

    # Others mark it %doc rather than %license, and the image installs no docs.
    if [ -z "${files[0]:-}" ]; then
        dnf -y --disablerepo=extras reinstall --setopt=tsflags= "$pkg" >/dev/null
        mapfile -t files < <(rpm -qd "$pkg" | grep -iE '/(LICEN[CS]E|COPYING|NOTICE)')
    fi

    for f in "${files[@]}"; do
        [ -f "$f" ] || continue
        cp "$f" "$project/LICENSE.${pkg}.$(basename "$f")"
    done
    compgen -G "$project/LICENSE.$pkg.*" >/dev/null ||
        { echo "no licence file found for $pkg" >&2; exit 1; }
done

ls -1 "$project"/LICENSE.* | sed "s|$project/||"
