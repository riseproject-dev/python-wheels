#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# Compile-level checks against the pinned gh-aw release (plan 22, item 1):
# 1. the committed locks are exactly what `gh aw compile` produces;
# 2. the rejected-route fixtures still behave as recorded.
# Usage: upstreaming/check_gh_aw.sh /path/to/gh-aw   (the v1.2.2 binary)
set -eu
aw=${1:?path to the gh-aw v1.2.2 binary}
"$aw" version | grep -q 'v1.2.2' || { echo "expected gh-aw v1.2.2" >&2; exit 1; }
root=$(git rev-parse --show-toplevel)
cd "$root"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for w in upstreaming-worker upstreaming-dispatcher; do
    cp ".github/workflows/$w.lock.yml" "$tmp/$w.lock.yml.committed"
done
"$aw" compile upstreaming-worker upstreaming-dispatcher --no-check-update >/dev/null
for w in upstreaming-worker upstreaming-dispatcher; do
    cmp -s "$tmp/$w.lock.yml.committed" ".github/workflows/$w.lock.yml" \
        || { echo "$w.lock.yml is stale; recompile with gh-aw v1.2.2" >&2; exit 1; }
done

fx="$tmp/fixtures"
mkdir -p "$fx/.github/workflows"
git -C "$fx" init -q
cp upstreaming/tests/gh-aw-fixtures/rejected-*.md "$fx/.github/workflows/"
cd "$fx"
if "$aw" compile rejected-custom-job --no-check-update --approve >out 2>&1; then
    echo "rejected-custom-job now compiles: revisit plan 15.3" >&2; exit 1
fi
grep -q 'requires a trusted per-Claim delivery adapter' out || { cat out; exit 1; }
"$aw" compile rejected-direct-push --no-check-update --approve >out 2>&1 || { cat out; exit 1; }
echo "gh-aw v1.2.2 checks passed"
