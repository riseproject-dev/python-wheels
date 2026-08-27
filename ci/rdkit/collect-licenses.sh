#!/bin/bash
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# auditwheel bundles Boost and the image's cairo/freetype stack into the wheel and
# upstream ships no licence text for any of it. Stage those texts at the project
# root, where setuptools' default license_files glob picks them up.
set -euo pipefail

project="${1:?usage: collect-licenses.sh <project> <boost-version> <expat-version>}"
boost_version="${2:?missing boost version}"
expat_version="${3:?missing expat version}"

# Conan builds these during the build, so their source trees do not exist yet.
curl -fsSL "https://raw.githubusercontent.com/boostorg/boost/boost-${boost_version}/LICENSE_1_0.txt" \
    -o "$project/LICENSE.boost"
curl -fsSL "https://raw.githubusercontent.com/libexpat/libexpat/R_${expat_version//./_}/expat/COPYING" \
    -o "$project/LICENSE.expat"

# Everything RDKit links out of the image, plus its transitive closure.
roots=()
for soname in libcairo.so.2 libfreetype.so.6 libpng16.so.16 libpixman-1.so.0; do
    roots+=("$(ldconfig -p | awk -v n="$soname" '$1 == n { print $NF; exit }')")
done
mapfile -t libs < <(
    { for r in "${roots[@]}"; do readlink -f "$r"; ldd "$r"; done; } |
        tr ' ' '\n' | grep '^/' | sort -u
)
# glibc, libgcc, libstdc++ and zlib are on auditwheel's allowlist, never bundled.
mapfile -t pkgs < <(
    rpm -qf --qf '%{NAME}\n' "${libs[@]}" 2>/dev/null |
        grep -E '^[A-Za-z0-9._+-]+$' | sort -u |
        grep -vE '^(glibc|libgcc|libstdc\+\+|gcc|zlib-ng-compat)$'
)

# Rocky ships no licence file for these; take it from the release they packaged.
license_url() {
    case "$1" in
    libX11) echo "https://gitlab.freedesktop.org/xorg/lib/libx11/-/raw/libX11-$2/COPYING" ;;
    libxcb) echo "https://gitlab.freedesktop.org/xorg/lib/libxcb/-/raw/libxcb-$2/COPYING" ;;
    esac
}

for pkg in "${pkgs[@]}"; do
    files=$(rpm -q --licensefiles "$pkg" 2>/dev/null || true)
    if [ -z "$files" ]; then
        # tsflags=nodocs drops %doc-marked licences; a reinstall restores them.
        dnf -y reinstall --setopt=tsflags= "$pkg" >/dev/null 2>&1 || true
        files=$(rpm -q --licensefiles "$pkg" 2>/dev/null || true)
        [ -n "$files" ] || files=$(rpm -qd "$pkg" | grep -iE '/(LICEN[CS]E|COPYING|NOTICE)' || true)
    fi
    if [ -z "$files" ]; then
        # A subpackage can leave its licence to a sibling built from the same source.
        srpm=$(rpm -q --qf '%{SOURCERPM}' "$pkg")
        for sib in $(rpm -qa --qf '%{SOURCERPM} %{NAME}\n' | awk -v s="$srpm" '$1 == s { print $2 }'); do
            files=$(rpm -q --licensefiles "$sib" 2>/dev/null || true)
            [ -n "$files" ] && break
        done
    fi
    if [ -n "$files" ]; then
        for f in $files; do
            [ -f "$f" ] && cp "$f" "$project/LICENSE.$pkg.$(basename "$f")"
        done
        continue
    fi
    url=$(license_url "$pkg" "$(rpm -q --qf '%{VERSION}' "$pkg")")
    if [ -n "$url" ] && curl -fsSL "$url" -o "$project/LICENSE.$pkg.COPYING"; then
        continue
    fi
    echo "no licence text for $pkg ($(rpm -q --qf '%{LICENSE}' "$pkg"))" >&2
    exit 1
done

ls -1 "$project"/LICENSE.*
