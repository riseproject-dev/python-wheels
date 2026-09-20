#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Pick the next packages to port from .queue.yml.

Prints, as a JSON list, up to --count entries with status "queued" whose
`notes` field does not read like it is blocked on something else (another
package that has to land first, a maintainer hold, "do not attempt until
...", etc). This is a heuristic over free-text notes, not a dependency
graph: it only screens obvious candidates for a next porting batch, it does
not prove a package is unblocked. Read the notes field of anything it
returns before starting work on it.

Entries already claimed (see --claim) are skipped so concurrent orchestration
rounds don't hand out the same package twice.

Usage:
    uv run ci_scripts/queue_next.py --count 5
    uv run ci_scripts/queue_next.py --count 5 --claim
    uv run ci_scripts/queue_next.py --pkg bitsandbytes  # look up one entry
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = REPO_ROOT / ".queue.yml"


def _git_common_dir():
    # REPO_ROOT/.git is a *file* (not a directory) inside a git worktree, so
    # the claims lock must live under the shared common dir instead.
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


CLAIMS_PATH = _git_common_dir() / "pw-locks" / "queue-claims.json"

BLOCK_PATTERNS = [
    r"\bdo not attempt\b",
    r"\bdo not (?:pick up|start|push)\b",
    r"\bblocked (?:on|by)\b",
    r"\bwait(?:ing)? (?:for|on|until)\b",
    r"\bdepends on\b.*(?:being (?:available|published|merged)|not (?:merged|published))",
    r"\bnot (?:yet )?(?:merged|published)\b.*\bfirst\b",
    r"\bmaintainer hold\b",
    r"\bunconditional\b",
    r"\bonce .* (?:is|are) (?:merged|published|scoped in)\b",
]
BLOCK_RE = re.compile("|".join(BLOCK_PATTERNS), re.IGNORECASE)


def load_queue():
    data = yaml.safe_load(QUEUE_PATH.read_text()) or {}
    return data.get("packages") or []


def looks_blocked(entry):
    notes = entry.get("notes") or ""
    return bool(BLOCK_RE.search(notes))


def load_claims():
    if not CLAIMS_PATH.exists():
        return set()
    return set(json.loads(CLAIMS_PATH.read_text()))


def save_claims(claims):
    CLAIMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLAIMS_PATH.write_text(json.dumps(sorted(claims)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count", type=int, default=5, help="max number of entries to return"
    )
    parser.add_argument(
        "--claim",
        action="store_true",
        help="record returned packages in .git/pw-locks/queue-claims.json "
        "so a later call skips them; clear entries once their PR is open "
        "or the attempt is abandoned",
    )
    parser.add_argument(
        "--unclaim",
        metavar="PKG",
        action="append",
        default=[],
        help="remove PKG from the claims file (repeatable)",
    )
    parser.add_argument(
        "--include-blocked",
        action="store_true",
        help="don't screen out notes that look like a blocker",
    )
    parser.add_argument(
        "--pkg", help="print the single named queue entry (any status) and exit"
    )
    args = parser.parse_args()

    packages = load_queue()

    if args.pkg:
        for entry in packages:
            if entry.get("pkg") == args.pkg:
                json.dump(entry, sys.stdout, indent=2)
                print()
                return
        raise SystemExit(f"{args.pkg!r} not found in .queue.yml")

    claims = load_claims()
    if args.unclaim:
        claims -= set(args.unclaim)
        save_claims(claims)

    candidates = [
        entry
        for entry in packages
        if entry.get("status") == "queued"
        and entry.get("pkg") not in claims
        and (args.include_blocked or not looks_blocked(entry))
    ]
    selected = candidates[: args.count]

    if args.claim and selected:
        claims |= {entry["pkg"] for entry in selected}
        save_claims(claims)

    json.dump(selected, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
