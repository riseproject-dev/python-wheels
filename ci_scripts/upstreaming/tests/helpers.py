# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Fixtures shared by the upstreaming tests."""

from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path

from ci_scripts.upstreaming import lifecycle
from ci_scripts.upstreaming.common import load_policy

NOW = "2026-11-18T12:00:00+00:00"
OWNER = {"id": 1001, "login": "owner"}
BACKUP = {"id": 1002, "login": "backup"}
STRANGER = {"id": 9999, "login": "stranger"}
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def policy(**over):
    p = load_policy()
    p = copy.deepcopy(p)
    p["command_authority"]["actor_ids"] = [OWNER["id"], BACKUP["id"]]
    p.update(over)
    return p


def contribution(phase="development", **over):
    rec = lifecycle.new_contribution(
        contribution_id="example--proj/12", project_id="example--proj",
        issue={"id": 5000, "number": 12}, upstream="example/proj", distributions=["proj"],
        base_ref="main", policy_id="test", now=NOW)
    rec.update({
        "phase": phase,
        "owners": {"primary": OWNER, "backup": BACKUP, "submitter": None, "handoff_reviewer": None},
        "admission_class": "configuration_integration",
        "upstream": {"repository_id": 1, "full_name": "example/proj", "base_ref": "main",
                     "base_sha": SHA_C},
        "fork": {"repository_id": 2, "name": "riseproject-upstreaming/proj", "head_ref": "riscv64",
                 "head_sha": SHA_A, "pr_number": 1},
    })
    rec.update(over)
    return rec


def comment(body, actor=OWNER, cid=1):
    return {"id": cid, "body": body, "user": dict(actor)}


def git(repo: Path, *args: str, env_extra=None) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@example.com",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    env.update(env_extra or {})
    return subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                          check=True, capture_output=True, text=True, env=env).stdout.strip()


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    return path


def commit_files(repo: Path, files: dict[str, str | None], msg="c", mode=None) -> str:
    for rel, content in files.items():
        p = repo / rel
        if content is None:
            git(repo, "rm", "-q", rel)
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        if mode:
            p.chmod(mode)
        git(repo, "add", rel)
    git(repo, "commit", "-q", "--allow-empty", "-m", msg)
    return git(repo, "rev-parse", "HEAD")
