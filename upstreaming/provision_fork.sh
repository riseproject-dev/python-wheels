#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# Human fork provisioning (plan 10.1): run by a RISE owner with their own
# gh login, never by a workflow. The pipeline's App cannot fork most
# upstreams (GitHub requires the App on the source account too).
#
#   upstreaming/provision_fork.sh OWNER/REPO [BASE_REF]
#
# 1. forks OWNER/REPO into riseproject-upstreaming/REPO (default branch only),
#    or reuses it if it is already a fork of OWNER/REPO;
# 2. waits for the fork's Git objects;
# 3. creates riscv64 at the upstream BASE_REF head (default branch if
#    omitted), or leaves an existing riscv64 untouched;
# 4. keeps Actions default token permissions read-only.
# Then post `/upstreaming provision revision=N` on the tracking issue.
set -eu
up=${1:?OWNER/REPO}
name=${up#*/}
fork=riseproject-upstreaming/$name
up_id=$(gh api "repos/$up" --jq .id)
base_ref=${2:-$(gh api "repos/$up" --jq .default_branch)}
if parent=$(gh api "repos/$fork" --jq '.parent.id // empty' 2>/dev/null); then
    [ "$parent" = "$up_id" ] || { echo "$fork exists and is not a fork of $up" >&2; exit 1; }
    echo "reusing $fork"
else
    gh api -X POST "repos/$up/forks" -f organization=riseproject-upstreaming -F default_branch_only=true >/dev/null
    echo "forked $up into $fork"
fi
i=0
until gh api "repos/$fork/commits/HEAD" --jq .sha >/dev/null 2>&1; do
    i=$((i + 1)); [ "$i" -lt 30 ] || { echo "fork objects not available after 5 minutes" >&2; exit 1; }
    sleep 10
done
base_sha=$(gh api "repos/$up/commits/$base_ref" --jq .sha)
if head=$(gh api "repos/$fork/branches/riscv64" --jq .commit.sha 2>/dev/null); then
    echo "riscv64 already exists at $head; left untouched"
else
    gh api -X POST "repos/$fork/git/refs" -f ref=refs/heads/riscv64 -f sha="$base_sha" >/dev/null
    echo "created riscv64 at $base_sha ($up $base_ref)"
fi
gh api -X PUT "repos/$fork/actions/permissions/workflow" -f default_workflow_permissions=read \
    -F can_approve_pull_request_reviews=false >/dev/null
echo "done: $fork (riscv64)"
