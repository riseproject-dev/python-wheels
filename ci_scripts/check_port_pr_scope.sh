#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

# Enforce the hard rule that a package-port branch/PR only ever touches:
#   .github/workflows/build-<pkg>.yml
#   docs/packages/<pkg>.yaml
#   patches/<pkg>/<version>/**
#
# This has been violated repeatedly by agents that legitimately discover a
# new gotcha or write a small helper script while porting a package, and
# then let that ride along in the same commit as the port itself - which a
# port PR must never contain (skills/, ci_scripts/, .queue.yml bookkeeping
# all belong on `main` directly, per environment-and-auth.md). Four PRs in
# one session (#2104, #2105, #2106 and one caught before push) needed a
# post-hoc fix for exactly this. This script exists to catch it before the
# commit/push happens instead.
#
# On branch `main` this check does not apply at all - direct bookkeeping
# commits (queue updates, new gotchas, ci_scripts/ fixes) are the normal,
# correct thing there.
#
# Usage:
#   ci_scripts/check_port_pr_scope.sh            # checks staged files (pre-commit hook use)
#   ci_scripts/check_port_pr_scope.sh --branch    # checks the whole branch's diff against
#                                                  # origin/main (run this once before your
#                                                  # final push, in addition to the hook)
#
# Install as a local pre-commit hook (one-time, per clone/worktree - hooks are not
# versioned by git itself):
#   ln -sf ../../ci_scripts/check_port_pr_scope.sh .git/hooks/pre-commit
# or, to share one hooks dir across every worktree of this repo:
#   git config core.hooksPath ci_scripts/git-hooks
#   ln -sf ../check_port_pr_scope.sh ci_scripts/git-hooks/pre-commit

set -eu

cd "$(git rev-parse --show-toplevel)"

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" = "main" ]; then
    exit 0
fi

mode="${1:-staged}"
if [ "$mode" = "--branch" ]; then
    git fetch origin main --quiet 2>/dev/null || true
    base=$(git merge-base origin/main HEAD 2>/dev/null || echo "")
    if [ -z "$base" ]; then
        echo "check_port_pr_scope: could not find a merge-base with origin/main, skipping" >&2
        exit 0
    fi
    files=$(git diff --name-only "$base" HEAD)
else
    files=$(git diff --cached --name-only)
fi

[ -z "$files" ] && exit 0

bad=""
while IFS= read -r f; do
    [ -z "$f" ] && continue
    case "$f" in
        .github/workflows/*|docs/packages/*|patches/*) ;;
        *) bad="$bad$f
" ;;
    esac
done <<EOF
$files
EOF

if [ -n "$bad" ]; then
    echo "check_port_pr_scope: this branch ('$branch') is not main, so it must only touch" >&2
    echo "  .github/workflows/, docs/packages/ and patches/ - but it also touches:" >&2
    echo "$bad" | sed 's/^/    /' >&2
    echo "" >&2
    echo "Move these changes into a separate commit pushed directly to origin/main instead" >&2
    echo "(see ci_scripts/safe_push_main.sh), then unstage/remove them from this branch." >&2
    exit 1
fi

exit 0
