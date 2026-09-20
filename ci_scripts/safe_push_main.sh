#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

# Push the current HEAD to origin/main safely under heavy concurrent-agent
# load, retrying on races and refusing to push a branch that isn't actually
# based on the latest origin/main.
#
# This repo has many agents committing directly to main concurrently (queue
# bookkeeping, new gotchas, small tooling fixes). Two failure modes have
# already happened in practice:
#   1. A plain `git push origin main` pushes the wrong thing when the local
#      branch isn't named "main" (pushes the local main ref, which may be
#      stale, instead of HEAD).
#   2. A worktree that ends up on a stale base (e.g. after a `git reset` or
#      a rebase that didn't actually pick up the latest fetch) can produce a
#      commit that, once pushed, *deletes* content other agents already
#      landed - a silent revert, not a merge conflict, so git alone won't
#      stop it. This nearly happened once already (~70 lines of other
#      agents' work would have been reverted) and was only caught by an
#      ad hoc `git diff | grep` before push.
#
# This script closes both: it always pushes HEAD (never a possibly-stale
# local branch), verifies immediately before pushing that origin/main is
# actually an ancestor of HEAD (i.e. you rebased onto the real latest, not
# some earlier snapshot), and retries fetch+rebase+push a bounded number of
# times on a race with another agent's concurrent push.
#
# Usage:
#     ci_scripts/safe_push_main.sh
#
# Run it as the very last step, once your commit(s) are ready. It does not
# commit anything for you and does not touch files other than doing the
# rebase itself; if the rebase hits a real conflict (two agents edited the
# same lines) it stops and leaves you to resolve it by hand - that case
# needs a human/agent decision, not automation.

set -eu

cd "$(git rev-parse --show-toplevel)"

max_attempts=5
attempt=1

while [ "$attempt" -le "$max_attempts" ]; do
    git fetch origin main --quiet

    if ! git merge-base --is-ancestor origin/main HEAD; then
        echo "HEAD is not based on the latest origin/main - rebasing (attempt $attempt/$max_attempts)" >&2
        if ! git rebase origin/main; then
            echo "rebase hit a real conflict - resolve it by hand, then re-run this script" >&2
            exit 1
        fi
    fi

    # Belt-and-braces: after rebasing, HEAD must contain every line
    # origin/main has for the files most commonly touched by concurrent
    # agents. A shrinking package count or gotcha count is a strong signal
    # something upstream got silently dropped rather than merged.
    old_pkgs=$(git show origin/main:.queue.yml 2>/dev/null | grep -c '^- pkg: ' || true)
    new_pkgs=$(grep -c '^- pkg: ' .queue.yml || true)
    if [ "$new_pkgs" -lt "$old_pkgs" ]; then
        echo "REFUSING TO PUSH: .queue.yml would drop from $old_pkgs to $new_pkgs packages." >&2
        echo "This looks like a stale-base revert, not an intentional edit. Fix your branch first." >&2
        exit 1
    fi

    if git push origin HEAD:main; then
        exit 0
    fi

    echo "push rejected (race with a concurrent push) - retrying" >&2
    attempt=$((attempt + 1))
done

echo "gave up after $max_attempts attempts - check for a persistent problem" >&2
exit 1
