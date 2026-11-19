# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Fresh trusted publisher workspace validation (plan sections 10.4, 14.2, 15).

The credentialed publisher never runs project code, tests, wheel payloads or
agent scripts. It reconstructs a proposal in a fresh repository created by
this module, fetched from verified repository IDs and exact commits, with all
user/system Git configuration, hooks, filters and credential helpers
disabled. It then validates the proposed commits and final tree against the
trusted base independently of what the proposal claims it changed.

This module only validates. Pushing is done by the trusted fork handler with
an exact expected-head lease (``lease_refspec``), never an unconditional force.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEBUG_PREFIX, DEV_REF

MAX_FILES = 300
MAX_BLOB_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_COMMITS = 50

# Hard-coded, not inherited: a clean Git with nothing executable configured.
SAFE_GIT_CONFIG = [
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.fsmonitor=false",
    "-c", "core.symlinks=false",
    "-c", "credential.helper=",
    "-c", "protocol.allow=never",
    "-c", "protocol.https.allow=always",
    "-c", "protocol.file.allow=never",
    "-c", "protocol.ext.allow=never",
    "-c", "transfer.fsckObjects=true",
    "-c", "fetch.fsckObjects=true",
    "-c", "submodule.recurse=false",
    "-c", "uploadpack.allowFilter=false",
]

# Workflow content that a proposal may never introduce.
FORBIDDEN_WORKFLOW = [
    (re.compile(r"^\s*pull_request_target\s*:", re.M), "pull_request_target trigger"),
    (re.compile(r"\bpull_request_target\b"), "pull_request_target trigger"),
    (re.compile(r"permissions\s*:\s*write-all"), "permissions: write-all"),
    (re.compile(r"\$\{\{\s*secrets\.(?!GITHUB_TOKEN\b)"), "new secret reference"),
    (re.compile(r"\$\{\{\s*github\.event\.(issue|comment|review|pull_request)\.(title|body)"),
     "interpolation of untrusted event text"),
]


def safe_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "TMPDIR")}
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": "",
        "HOME": "/nonexistent",
    })
    return env


def git(repo: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(["git", *SAFE_GIT_CONFIG, "-C", str(repo), *args], check=check,
                          capture_output=True, text=True, env=safe_env()).stdout


def fresh_workspace(path: Path) -> Path:
    """Initialize an empty bare repository the publisher controls."""
    path.mkdir(parents=True, exist_ok=False)
    subprocess.run(["git", *SAFE_GIT_CONFIG, "init", "--bare", "-q", str(path)], check=True,
                   env=safe_env())
    # Alternates would let a hostile object store leak in.
    alt = path / "objects" / "info" / "alternates"
    if alt.exists():
        alt.unlink()
    return path


@dataclass
class Scope:
    """Approved patch surface for one contribution (from the dossier)."""
    allowed_globs: list[str]
    workflow_globs: list[str] = field(default_factory=lambda: [".github/workflows/*"])
    upstream_facing: bool = False   # True after handoff: no {debug} allowed
    history: str = "append"         # append | rewrite


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    touches_workflows: bool = False
    final_tree: str | None = None
    commits: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _bad_path(p: str) -> str | None:
    parts = p.split("/")
    if p.startswith("/") or any(x in ("", ".", "..") for x in parts):
        return "path traversal or empty component"
    if any(x.lower() == ".git" for x in parts):
        return ".git path component"
    if any(ord(c) < 32 for c in p) or "\\" in p:
        return "control character or backslash in path"
    return None


def validate_update(repo: Path, *, base: str, expected_head: str, candidate: str,
                    scope: Scope) -> Report:
    """Validate ``candidate`` as the new ``riscv64`` head.

    * ``append``: ``expected_head`` must be an ancestor (fast-forward).
    * ``rewrite``: allowed history rewrite; ``base`` must be an ancestor and
      the push uses an exact lease on ``expected_head``.
    Final-tree checks compare ``base`` (trusted upstream base) to
    ``candidate`` so the whole contribution is in scope, not just the delta.
    """
    rep = Report()

    def is_ancestor(a: str, b: str) -> bool:
        return subprocess.run(["git", *SAFE_GIT_CONFIG, "-C", str(repo), "merge-base",
                               "--is-ancestor", a, b], env=safe_env()).returncode == 0

    if scope.history == "append" and not is_ancestor(expected_head, candidate):
        rep.problems.append("append requested but candidate does not descend from the expected head")
    if not is_ancestor(base, candidate):
        rep.problems.append("candidate does not descend from the approved upstream base")
    if scope.history not in ("append", "rewrite"):
        rep.problems.append(f"unknown history mode {scope.history}")

    revs = git(repo, "rev-list", "--reverse", "--parents", f"{base}..{candidate}").split("\n")
    revs = [r.split() for r in revs if r]
    if len(revs) > MAX_COMMITS:
        rep.problems.append(f"{len(revs)} commits exceeds {MAX_COMMITS}")
    for r in revs:
        sha, parents = r[0], r[1:]
        if len(parents) != 1:
            rep.problems.append(f"{sha[:12]}: merge or root commits are not permitted")
        subject = git(repo, "log", "-1", "--format=%s", sha).strip()
        rep.commits.append({"sha": sha, "subject": subject})
        if subject.startswith(DEBUG_PREFIX) and scope.upstream_facing:
            rep.problems.append(f"{sha[:12]}: {DEBUG_PREFIX} commit on an upstream-facing branch")

    raw = git(repo, "diff-tree", "-r", "-z", "--no-renames", base, candidate)
    fields = raw.split("\0")
    total = 0
    seen: dict[str, str] = {}
    i = 0
    while i < len(fields) - 1:
        meta, path = fields[i], fields[i + 1]
        i += 2
        old_mode, new_mode, _o, new_sha, status = meta.lstrip(":").split()
        rep.changed.append(path)
        why = _bad_path(path)
        if why:
            rep.problems.append(f"{path}: {why}")
            continue
        if not any(fnmatch.fnmatchcase(path, g) for g in scope.allowed_globs):
            rep.problems.append(f"{path}: outside the approved patch surface")
        if any(fnmatch.fnmatchcase(path, g) for g in scope.workflow_globs):
            rep.touches_workflows = True
        if status == "D":
            continue
        if new_mode == "160000":
            rep.problems.append(f"{path}: submodule (gitlink) not permitted")
            continue
        if new_mode == "120000":
            rep.problems.append(f"{path}: symlink not permitted")
            continue
        if new_mode == "100755" and old_mode != "100755":
            rep.problems.append(f"{path}: new executable file mode needs explicit scope")
        size = int(git(repo, "cat-file", "-s", new_sha).strip())
        total += size
        if size > MAX_BLOB_BYTES:
            rep.problems.append(f"{path}: {size} bytes is too large")
        if any(fnmatch.fnmatchcase(path, g) for g in scope.workflow_globs) and size <= MAX_BLOB_BYTES:
            text = git(repo, "cat-file", "blob", new_sha)
            old = "" if status == "A" else git(repo, "cat-file", "blob", f"{base}:{path}")
            for pat, what in FORBIDDEN_WORKFLOW:
                if pat.search(text) and not pat.search(old):
                    rep.problems.append(f"{path}: introduces {what}")
    if len(rep.changed) > MAX_FILES:
        rep.problems.append(f"{len(rep.changed)} files exceeds {MAX_FILES}")
    if total > MAX_TOTAL_BYTES:
        rep.problems.append(f"{total} bytes of changed content exceeds the limit")
    for n in filter(None, git(repo, "ls-tree", "-r", "-z", "--name-only", candidate).split("\0")):
        k = n.casefold()
        if k in seen and seen[k] != n:
            rep.problems.append(f"{n}: case-insensitive collision with {seen[k]}")
        seen[k] = n
    if ".gitmodules" in rep.changed:
        rep.problems.append(".gitmodules change not permitted")
    rep.final_tree = git(repo, "rev-parse", f"{candidate}^{{tree}}").strip()
    return rep


def debug_commits(repo: Path, base: str, head: str) -> list[dict]:
    out = []
    for line in git(repo, "log", "--reverse", "--format=%H%x00%s", f"{base}..{head}").splitlines():
        sha, subject = line.split("\0", 1)
        if subject.startswith(DEBUG_PREFIX):
            out.append({"sha": sha, "subject": subject})
    return out


def lease_refspec(candidate: str, expected_head: str, ref: str = DEV_REF) -> list[str]:
    """Arguments for the exact-head leased push. Only ``riscv64``."""
    if ref != DEV_REF:
        raise ValueError(f"only {DEV_REF} may be published")
    if not re.fullmatch(r"[0-9a-f]{40}", candidate) or not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise ValueError("lease needs full SHAs")
    return [f"--force-with-lease=refs/heads/{ref}:{expected_head}",
            f"{candidate}:refs/heads/{ref}"]
