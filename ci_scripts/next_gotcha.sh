#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

# Print the next free gotcha number for skills/python-project-porting.
#
# Gotcha numbers are permanent IDs cited across the repo ("gotcha N"), so two
# concurrent agents picking the same next number is a real, recurring race
# (it has already happened several times across concurrent porting sessions).
# This script does not eliminate the race by itself - only a lock could do
# that, and there is no shared lock across independent git clones/worktrees -
# but it standardizes the check and, used correctly, closes the window to
# roughly the time between running it and pushing.
#
# Usage: run this from the repo root or a worktree, IMMEDIATELY before you
# write the new gotcha's number into a references/gotchas/*.md file, and
# AGAIN right before your final `git push` (after fetching+rebasing onto the
# latest origin/main) to catch anyone who landed a gotcha in between:
#
#     git fetch origin main
#     n=$(ci_scripts/next_gotcha.sh)
#     # write gotcha $n
#     ... commit ...
#     git fetch origin main && git rebase origin/main
#     ci_scripts/next_gotcha.sh   # re-check: still expecting $n?
#     git push origin HEAD:main
#
# If the number moved, renumber your gotcha to the new value before pushing.

set -eu

cd "$(git rev-parse --show-toplevel)"

git fetch origin main --quiet 2>/dev/null || true

max=$(git ls-tree -r --name-only origin/main -- skills/python-project-porting/references/gotchas/ \
    | xargs -I{} git show origin/main:{} \
    | grep -oE '^[0-9]+\. ' \
    | tr -d '. ' \
    | sort -n \
    | tail -1)

if [ -z "${max:-}" ]; then
    echo "could not determine the current max gotcha number from origin/main" >&2
    exit 1
fi

echo $((max + 1))
