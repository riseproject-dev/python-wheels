#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# Install the pinned gh-aw v1.2.2 CLI binary into DIR and print its path.
# The SHA-256 is pinned here (from the release's checksums.txt) rather than
# read from the release at run time.
#   upstreaming/install_gh_aw.sh DIR      (needs GH_TOKEN for gh release download)
set -eu
dir=${1:?install directory}
version=v1.2.2
case "$(uname -m)" in
    x86_64) asset=linux-amd64; sha=c2378d85466d29cdbdfebd0e513557b5cbec18d34f44e7cc00c2fa323687a153 ;;
    aarch64) asset=linux-arm64; sha=a1dd217c4b42ca9cb1af53f9a48f36e581d76b0d31ee671f2062241ba0d11fe3 ;;
    *) echo "unsupported architecture $(uname -m)" >&2; exit 1 ;;
esac
mkdir -p "$dir"
gh release download "$version" -R github/gh-aw -p "$asset" -D "$dir" --clobber >&2
echo "$sha  $dir/$asset" | sha256sum -c - >&2
chmod +x "$dir/$asset"
mv "$dir/$asset" "$dir/gh-aw"
"$dir/gh-aw" version | grep -q "$version" || { echo "unexpected gh-aw version" >&2; exit 1; }
echo "$dir/gh-aw"
