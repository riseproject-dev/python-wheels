# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Build and publish one state-only commit on control ``main`` (plan 6.3).

* Build: a commit whose parent is the expected ``main`` tip and whose tree
  is that tip's tree plus the staged state files, using a private index (the
  working tree is never touched, so unrelated files cannot ride along).
* Validate: ``state.validate_state_diff`` against the trusted parent.
* Publish: a plain fast-forward push of that exact commit. On rejection
  (an unrelated commit landed on ``main``), refetch, call ``recheck`` so the
  caller re-verifies the affected work preconditions on the new tip, rebuild
  and retry a bounded number of times. Never force, never merge conflicting
  machine state, never repeat a remote effect to obtain a receipt.

Publishing is refused unless the reviewed policy has ``read_only: false``.
The App-token / ruleset route that permits the push is an integration
deliverable (see ``INTEGRATION.md``), not assumed here.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from . import state
from .common import canonical_json

MAX_ATTEMPTS = 4


class PublishError(RuntimeError):
    pass


def _git(repo: Path, *args: str, env: dict | None = None, input: str | None = None,
         check: bool = True) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                          capture_output=True, text=True, env=e, input=input, check=check)


def build(repo: Path, parent: str, records: dict[str, dict], message: str) -> str:
    """Return the SHA of a new commit: ``parent`` + ``records`` (path -> record)."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _git(repo, "read-tree", parent, env=env)
        for path, rec in sorted(records.items()):
            if not path.startswith("upstreaming-state/"):
                raise PublishError(f"refusing to stage {path}")
            blob = _git(repo, "hash-object", "-w", "--stdin", input=canonical_json(rec)).stdout.strip()
            _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env)
        tree = _git(repo, "write-tree", env=env).stdout.strip()
    return _git(repo, "commit-tree", tree, "-p", parent, "-m", message).stdout.strip()


def publish(repo: Path, *, remote: str, branch: str, records_for: Callable[[str], dict[str, dict]],
            message: str, policy: dict, recheck: Callable[[str], bool] | None = None) -> str:
    """Publish state as a fast-forward of ``remote/branch``.

    ``records_for(tip)`` returns the records to write on top of ``tip``
    (reloading/recomputing from that tip is the caller's job). ``recheck(tip)``
    returns False if the affected work preconditions no longer hold on the new
    tip, in which case publication stops for a later tick.
    """
    if policy.get("read_only", True):
        raise PublishError("policy is read-only; state publication disabled")
    for _attempt in range(MAX_ATTEMPTS):
        _git(repo, "fetch", "--quiet", remote, f"+refs/heads/{branch}:refs/upstreaming/tip")
        tip = _git(repo, "rev-parse", "refs/upstreaming/tip").stdout.strip()
        if recheck is not None and not recheck(tip):
            raise PublishError("preconditions changed on the new main tip; deferring")
        commit = build(repo, tip, records_for(tip), message)
        rep = state.validate_state_diff(repo, tip, commit, policy)
        if not rep.ok:
            raise PublishError("state commit failed final-tree validation: " + "; ".join(rep.problems[:5]))
        p = _git(repo, "push", "--quiet", "--porcelain", remote, f"{commit}:refs/heads/{branch}", check=False)
        if p.returncode == 0:
            return commit
        if "rejected" not in (p.stdout + p.stderr) and "non-fast-forward" not in (p.stdout + p.stderr) \
                and "fetch first" not in (p.stdout + p.stderr):
            raise PublishError(f"push failed: {p.stderr.strip()[:300]}")
    raise PublishError("main kept moving; giving up after bounded retries")


def records_from_checkout(root: Path, base: str, repo: Path | None = None) -> dict[str, dict]:
    """State files changed in the working tree relative to ``base``
    (added or modified only), as path -> record. Used by the workflow after
    ``python -m upstreaming reconcile`` wrote records into the checkout."""
    import json
    repo = repo or root
    out = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "upstreaming-state").stdout
    records: dict[str, dict] = {}
    for entry in filter(None, out.split("\0")):
        code, path = entry[:2], entry[3:]
        if "D" in code or "R" in code:
            raise PublishError(f"{path}: deletions/renames are not state updates")
        if path.endswith(".json"):
            records[path] = json.loads((root / path).read_text(encoding="utf-8"))
    return records


def main(argv=None) -> int:
    """python -m upstreaming.state_commit [--remote origin] [--branch main] [--message M]

    Publishes the state files changed in this checkout as one validated
    fast-forward commit on main. On a race, the records are re-applied on
    the new tip (they are full records keyed by path), revalidated, and only
    pushed if each record's revision has not moved backwards on the tip.
    """
    import argparse
    import json
    from .common import load_policy
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", default="upstreaming: update state")
    a = ap.parse_args(argv)
    root = Path(_git(Path("."), "rev-parse", "--show-toplevel").stdout.strip())
    policy = load_policy()
    records = records_from_checkout(root, "HEAD")
    if not records:
        print("no state changes")
        return 0

    def recheck(tip: str) -> bool:
        # A record on the new tip with a higher revision than ours means
        # another writer advanced that contribution: defer to the next tick.
        for path, rec in records.items():
            p = _git(root, "show", f"{tip}:{path}", check=False)
            if p.returncode != 0:
                continue
            cur = json.loads(p.stdout)
            if isinstance(cur.get("revision"), int) and isinstance(rec.get("revision"), int) \
                    and cur["revision"] > rec["revision"]:
                return False
        return True

    try:
        sha = publish(root, remote=a.remote, branch=a.branch, records_for=lambda tip: records,
                      message=a.message, policy=policy, recheck=recheck)
    except PublishError as e:
        print(f"::error::{e}")
        return 1
    print(sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
