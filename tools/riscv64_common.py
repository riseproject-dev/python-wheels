"""Shared helpers for riscv64_autoport.py and riscv64_discover.py.

Not a public interface -- just the bits that were duplicated near-verbatim
between the two scripts: the shallow-clone-and-verify-origin logic (safety
critical: this is what stops an ambient git config from silently adding a
fork remote), a simple riscv-mention check, and a stdout+file log tee.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def clone_shallow(owner: str, repo: str, dest: Path) -> str:
    """Plain `git clone --depth 1` over https, verified afterwards to have
    exactly one `origin` remote -- paranoia against any ambient git config
    that might auto-add a fork remote. Returns one of:
    "exists", "cloned", "clone-failed: <reason>", "unexpected-remotes:<list>".
    On anything other than "exists"/"cloned", the half-made clone is deleted.
    """
    if dest.exists():
        return "exists"
    url = f"https://github.com/{owner}/{repo}.git"
    r = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        capture_output=True, text=True, timeout=180,
    )
    if r.returncode != 0:
        return f"clone-failed: {r.stderr.strip().splitlines()[-1] if r.stderr else 'unknown'}"
    remotes = subprocess.run(
        ["git", "-C", str(dest), "remote"], capture_output=True, text=True
    ).stdout.split()
    if remotes != ["origin"]:
        shutil.rmtree(dest, ignore_errors=True)
        return f"unexpected-remotes:{remotes}"
    return "cloned"


def text_mentions(texts, pattern: str) -> bool:
    """True if any string in `texts` matches `pattern` (case-insensitive)."""
    return any(re.search(pattern, t, re.I) for t in texts)


class Logger:
    """print() that also tees to a log file once one is set."""

    def __init__(self):
        self._fh = None

    def set_file(self, fh) -> None:
        self._fh = fh

    def __call__(self, msg: str = "") -> None:
        print(msg)
        if self._fh:
            print(msg, file=self._fh)


log = Logger()
