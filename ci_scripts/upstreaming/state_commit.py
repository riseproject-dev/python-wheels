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
