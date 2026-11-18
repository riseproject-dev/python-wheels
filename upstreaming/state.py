# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Durable lifecycle state under ``main:upstreaming-state/`` (plan section 6).

Two parts:

* ``StateStore``: load/validate/stage records in a working tree. It writes
  files locally only; publication is the state publisher's job.
* ``validate_state_diff``: the independent final-tree check the state
  publisher runs before pushing. It compares the candidate commit's tree with
  the trusted base and rejects anything other than regular, schema-valid,
  size-bounded JSON files under ``upstreaming-state/``, including deletions,
  renames out of the directory, mode changes, symlinks, submodules and
  case-folding path collisions.

GitHub tokens are repository-scoped, not path-scoped. This validator plus the
reviewed publisher code are what keep the state writer inside
``upstreaming-state/``; the token itself could write anywhere.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import schemas
from .common import STATE_KINDS, STATE_ROOT, canonical_json, contribution_file_id, safe_id

SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]

_ID_KEY = {
    "projects": "project_id",
    "contributions": "contribution_id",
    "operations": "operation_id",
    "commands": "command_id",
    "evidence": "evidence_id",
}


class StateError(ValueError):
    pass


def find_secrets(text: str) -> list[str]:
    return [p.pattern for p in SECRET_PATTERNS if p.search(text)]


def record_path(kind: str, record: dict) -> str:
    """Relative path of a record. Events live in a per-contribution folder."""
    if kind == "events":
        return (f"{STATE_ROOT}/events/{contribution_file_id(record['contribution_id'])}/"
                f"{record['sequence']:08d}.json")
    rid = record[_ID_KEY[kind]]
    name = contribution_file_id(rid) if "/" in rid else safe_id(rid)
    return f"{STATE_ROOT}/{kind}/{name}.json"


def _limit(kind: str, policy: dict) -> int:
    s = policy["storage"]
    return s["max_event_bytes"] if kind in ("events", "commands") else s["max_record_bytes"]


def check_blob(path: str, data: bytes, policy: dict) -> list[str]:
    """Validate one file's content as committed state."""
    problems: list[str] = []
    parts = path.split("/")
    if len(parts) < 3 or parts[0] != STATE_ROOT or parts[1] not in STATE_KINDS:
        return [f"{path}: not under an allowed {STATE_ROOT}/<kind>/ directory"]
    kind = parts[1]
    expected_depth = 4 if kind == "events" else 3
    if len(parts) != expected_depth or not parts[-1].endswith(".json"):
        problems.append(f"{path}: unexpected path shape")
    if len(data) > _limit(kind, policy):
        problems.append(f"{path}: {len(data)} bytes exceeds the {kind} limit")
    try:
        text = data.decode("utf-8")
        record = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return problems + [f"{path}: not UTF-8 JSON ({e})"]
    if find_secrets(text):
        problems.append(f"{path}: content matches a credential pattern")
    for e in schemas.errors(STATE_KINDS[kind], record):
        problems.append(f"{path}: {e}")
    if not problems:
        try:
            if record_path(kind, record) != path:
                problems.append(f"{path}: record identity does not match its path")
        except (KeyError, ValueError) as e:
            problems.append(f"{path}: {e}")
    return problems


# --------------------------------------------------------------------------
# Final-tree validation against the trusted base (git plumbing only).


def _git(repo: Path, *args: str, input: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, input=input).stdout


@dataclass
class DiffReport:
    problems: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    total_bytes: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems


def validate_state_diff(repo: Path, base: str, candidate: str, policy: dict) -> DiffReport:
    """Check that ``candidate`` differs from ``base`` only by valid state.

    Uses ``git diff-tree --no-renames`` so a rename is seen as a delete plus
    an add, and both sides are checked. Deletions are rejected: lifecycle
    history is append/update only, retention is a reviewed migration.
    """
    rep = DiffReport()
    parents = _git(repo, "rev-list", "--parents", "-n1", candidate).decode().split()[1:]
    base_sha = _git(repo, "rev-parse", base).decode().strip()
    if parents != [base_sha]:
        rep.problems.append("candidate must be a single commit on top of the trusted base")
    raw = _git(repo, "diff-tree", "-r", "-z", "--no-renames", "--no-commit-id",
               base, candidate)
    fields = raw.split(b"\0")
    i = 0
    while i < len(fields) - 1:
        meta = fields[i].decode()
        path = fields[i + 1].decode("utf-8", "surrogateescape")
        i += 2
        old_mode, new_mode, _old, new_sha, status = meta.lstrip(":").split()
        rep.changed.append(path)
        if not path.startswith(STATE_ROOT + "/"):
            rep.problems.append(f"{path}: outside {STATE_ROOT}/")
            continue
        if status == "D":
            rep.problems.append(f"{path}: deletion is not permitted")
            continue
        if new_mode != "100644":
            rep.problems.append(f"{path}: mode {new_mode} is not a regular non-executable file")
            continue
        if status == "M" and old_mode != new_mode:
            rep.problems.append(f"{path}: mode change")
        data = _git(repo, "cat-file", "blob", new_sha)
        rep.total_bytes += len(data)
        rep.problems.extend(check_blob(path, data, policy))
    if rep.total_bytes > policy["storage"]["max_commit_bytes"]:
        rep.problems.append(f"state commit is {rep.total_bytes} bytes, over the limit")
    # Case-insensitive collisions anywhere in the resulting state tree.
    names = _git(repo, "ls-tree", "-r", "-z", "--name-only", candidate, "--", STATE_ROOT)
    seen: dict[str, str] = {}
    for n in filter(None, names.decode("utf-8", "surrogateescape").split("\0")):
        k = n.casefold()
        if k in seen and seen[k] != n:
            rep.problems.append(f"{n}: collides with {seen[k]} on case-insensitive filesystems")
        seen[k] = n
    return rep


# --------------------------------------------------------------------------
# Working-tree store


class StateStore:
    """Load and stage lifecycle records in a checkout of the control repo."""

    def __init__(self, root: Path, policy: dict):
        self.root = Path(root)
        self.policy = policy
        self._staged: dict[str, dict] = {}

    def _dir(self, kind: str) -> Path:
        if kind not in STATE_KINDS:
            raise StateError(f"unknown kind {kind}")
        return self.root / STATE_ROOT / kind

    def load_all(self, kind: str) -> dict[str, dict]:
        """Load every record of a kind, validating each. Invalid state blocks
        writes: callers must stop affected work, never guess."""
        out: dict[str, dict] = {}
        d = self._dir(kind)
        if not d.exists():
            return out
        for p in sorted(d.rglob("*.json")):
            if p.is_symlink() or not p.is_file():
                raise StateError(f"{p}: not a regular file")
            rel = p.relative_to(self.root).as_posix()
            problems = check_blob(rel, p.read_bytes(), self.policy)
            if problems:
                raise StateError("; ".join(problems))
            rec = json.loads(p.read_text(encoding="utf-8"))
            out[rel] = rec
        return out

    def contributions(self) -> list[dict]:
        return list(self.load_all("contributions").values())

    def next_event_sequence(self, contribution_id: str) -> int:
        d = self._dir("events") / contribution_file_id(contribution_id)
        existing = [int(p.stem) for p in d.glob("*.json")] if d.exists() else []
        staged = [r["sequence"] for k, r in self._staged.items()
                  if k.startswith(f"{STATE_ROOT}/events/{contribution_file_id(contribution_id)}/")]
        return max(existing + staged, default=-1) + 1

    def stage(self, kind: str, record: dict) -> str:
        if kind == "events":
            record = dict(record, sequence=self.next_event_sequence(record["contribution_id"]))
        schemas.validate(STATE_KINDS[kind], record)
        path = record_path(kind, record)
        data = canonical_json(record).encode("utf-8")
        problems = check_blob(path, data, self.policy)
        if problems:
            raise StateError("; ".join(problems))
        self._staged[path] = record
        return path

    def write_staged(self) -> list[str]:
        written = []
        for rel, rec in sorted(self._staged.items()):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(canonical_json(rec), encoding="utf-8")
            written.append(rel)
        self._staged.clear()
        return written

    def total_bytes(self) -> int:
        base = self.root / STATE_ROOT
        return sum(p.stat().st_size for p in base.rglob("*") if p.is_file()) if base.exists() else 0
