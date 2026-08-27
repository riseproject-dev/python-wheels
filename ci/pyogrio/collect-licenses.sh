#!/bin/bash
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# auditwheel vendors libgdal's whole shared-library closure into the wheel, so
# collect the licence of every rpm that closure comes from; the wheel build
# stages the result at the project root, where setuptools' license_files glob
# picks it up.
set -euo pipefail

out=/opt/licenses
mkdir -p "${out}"

mapfile -t libs < <(ldd /usr/local/lib/libgdal.so | tr ' ' '\n' | grep '^/' | sort -u)
mapfile -t pkgs < <(rpm -qf --qf '%{NAME}\n' "${libs[@]}" 2>/dev/null \
    | grep -E '^[A-Za-z0-9._+-]+$' | sort -u \
    | grep -vE '^(glibc|libgcc|libstdc\+\+|gcc)$')

for pkg in "${pkgs[@]}"; do
    mapfile -t files < <(rpm -q --licensefiles "${pkg}")

    # A subpackage may carry no licence of its own (pcre2 leaves it to
    # pcre2-syntax), so fall back to its siblings from the same source rpm.
    if [ "${#files[@]}" -eq 0 ]; then
        srpm=$(rpm -q --qf '%{SOURCERPM}' "${pkg}")
        mapfile -t siblings < <(rpm -qa --qf '%{SOURCERPM} %{NAME}\n' \
            | awk -v srpm="${srpm}" '$1 == srpm { print $2 }')
        mapfile -t files < <(rpm -q --licensefiles "${siblings[@]}")
    fi

    # And the image installs rpms with tsflags=nodocs, which drops the licence
    # of a package that marks it %doc rather than %license.
    if [ "${#files[@]}" -eq 0 ]; then
        dnf -y reinstall --setopt=tsflags= "${pkg}"
        mapfile -t files < <(rpm -qd "${pkg}" \
            | grep -iE '/(LICEN[CS]E|COPYING|COPYRIGHT)[^/]*$' || true)
    fi

    for file in "${files[@]}"; do
        [ -f "${file}" ] || { echo "missing ${file} from rpm ${pkg}" >&2; exit 1; }
        cat "${file}" >> "${out}/LICENSE_${pkg}"
    done

    # Packages under a licence that needs no notice ship no file at all
    # (sqlite-libs is public domain); record what the rpm declares instead.
    if [ ! -s "${out}/LICENSE_${pkg}" ]; then
        rpm -q --qf '%{NAME} %{VERSION} is distributed under: %{LICENSE}\nIts package ships no licence file.\n' \
            "${pkg}" > "${out}/LICENSE_${pkg}"
    fi
done

ls -l "${out}"
