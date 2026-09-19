#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

# Enforce the hard rule that a package port (a workflow/docs/patches commit)
# and repo bookkeeping (.queue.yml, skills/, ci_scripts/, everything else)
# never land in the same commit. The two go to different places - the port
# to its own PR branch, bookkeeping straight to origin/main
# (ci_scripts/safe_push_main.sh) - and mixing them in one commit means
# whichever tool moves that commit moves the wrong half too.
#
# This has been violated repeatedly by agents that legitimately discover a
# new gotcha or write a small helper script while porting a package, and
# let it ride along in the same commit as the port itself. Four PRs in one
# session (#2104, #2105, #2106 and one caught before push) needed a
# post-hoc fix for exactly this.
#
# Earlier version of this script keyed off "are you on branch main", which
# is wrong: a worktree-isolated agent can never literally check out `main`
# (the primary checkout holds it) even when its commit is pure bookkeeping
# bound for origin/main via safe_push_main.sh. The check is per-commit
# content, not per-branch, and it only cares about one thing: don't mix
# port-scoped paths with anything else in the same commit.
#
# Usage:
#   ci_scripts/check_port_pr_scope.sh            # checks staged files (pre-commit hook use)
#   ci_scripts/check_port_pr_scope.sh --branch    # checks the whole branch's diff against
#                                                  # origin/main, commit by commit (run this
#                                                  # once before your final push, in addition
#                                                  # to the hook)
#
# Install as a local pre-commit hook (one-time; hooks are not versioned by git
# itself, but core.hooksPath lives in the shared .git/config, so this needs
# doing only once per clone even though every worktree uses it from then on):
#   git config core.hooksPath ci_scripts/git-hooks

set -eu

cd "$(git rev-parse --show-toplevel)"

is_port_path() {
    case "$1" in
        .github/workflows/*|docs/packages/*|patches/*) return 0 ;;
        *) return 1 ;;
    esac
}

# Prints nothing and exits 0 if $1 (a newline-separated file list) is entirely
# port-scoped or entirely non-port-scoped; otherwise prints the offending
# breakdown and exits 1.
check_file_list() {
    files="$1"
    label="$2"
    [ -z "$files" ] && return 0

    port=""
    other=""
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        if is_port_path "$f"; then
            port="$port$f
"
        else
            other="$other$f
"
        fi
    done <<EOF
$files
EOF

    if [ -n "$port" ] && [ -n "$other" ]; then
        echo "check_port_pr_scope: $label mixes a package port with repo bookkeeping." >&2
        echo "  These must be two separate commits: the port goes to its own PR branch," >&2
        echo "  bookkeeping goes straight to origin/main (ci_scripts/safe_push_main.sh)." >&2
        echo "" >&2
        echo "  Port-scoped (.github/workflows, docs/packages, patches):" >&2
        echo "$port" | sed 's/^/    /' >&2
        echo "  Everything else:" >&2
        echo "$other" | sed 's/^/    /' >&2
        return 1
    fi
    return 0
}

mode="${1:-staged}"
if [ "$mode" = "--branch" ]; then
    git fetch origin main --quiet 2>/dev/null || true
    base=$(git merge-base origin/main HEAD 2>/dev/null || echo "")
    if [ -z "$base" ]; then
        echo "check_port_pr_scope: could not find a merge-base with origin/main, skipping" >&2
        exit 0
    fi
    status=0
    for commit in $(git rev-list "$base"..HEAD); do
        files=$(git diff-tree --no-commit-id --name-only -r "$commit")
        check_file_list "$files" "commit $(git rev-parse --short "$commit")" || status=1
    done
    exit $status
else
    files=$(git diff --cached --name-only)
    check_file_list "$files" "this commit"
fi
