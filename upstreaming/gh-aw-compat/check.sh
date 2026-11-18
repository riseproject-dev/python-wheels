#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# Reproduce the native handler tests against the exact v1.2.2 source.
# No GitHub writes, artifact uploads, credentials or live API calls.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git clone --quiet --depth 1 --branch v1.2.2 --filter=blob:none --sparse \
    https://github.com/github/gh-aw.git "$tmp/source"
[ "$(git -C "$tmp/source" rev-parse HEAD)" = 399a445fe2d8926c616b54b1b82a16b5b2be4445 ]
git -C "$tmp/source" sparse-checkout set actions/setup/js specs/work-queue
python3 "$root/upstreaming/gh_aw_compat.py" "$tmp/source/actions/setup/js"
cp "$root/upstreaming/gh-aw-compat/tests/upload_artifact_work_queue.test.cjs" \
    "$tmp/source/actions/setup/js/upload_artifact_work_queue.test.cjs"
cd "$tmp/source/actions/setup/js"
npm ci --ignore-scripts --no-audit --no-fund
npx --no-install vitest run --no-file-parallelism \
    upload_artifact_work_queue.test.cjs work_queue_resource_scope.test.cjs
