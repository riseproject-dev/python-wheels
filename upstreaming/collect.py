# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Read-only collectors (Stage B observer).

Every function here issues GET requests only, through ``gh api`` with
whatever token the caller provides. Nothing writes. Results are normalized
for ``controller.tick``.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .common import CONTROL_REPO, INTAKE_LABEL


class CollectError(RuntimeError):
    pass


def gh_get(path: str, *, paginate: bool = False) -> Any:
    if not path.startswith("/") or any(c in path for c in "\n\r "):
        raise CollectError(f"refusing unexpected API path {path!r}")
    cmd = ["gh", "api", "--method", "GET", path]
    if paginate:
        cmd.insert(2, "--paginate")
        cmd.insert(3, "--slurp")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise CollectError(p.stderr.strip()[:500])
    data = json.loads(p.stdout or "null")
    if paginate:
        flat: list = []
        for page in data:
            flat.extend(page if isinstance(page, list) else [page])
        return flat
    return data


def intake_issues(max_pages: int = 3) -> list[dict]:
    out = []
    for page in range(1, max_pages + 1):
        batch = gh_get(f"/repos/{CONTROL_REPO}/issues?labels={INTAKE_LABEL}&state=open"
                       f"&per_page=50&page={page}")
        out.extend(i for i in batch if "pull_request" not in i)
        if len(batch) < 50:
            break
    return out


def issue_comments(number: int, since: str | None = None) -> list[dict]:
    q = f"?per_page=100&since={since}" if since else "?per_page=100"
    return gh_get(f"/repos/{CONTROL_REPO}/issues/{int(number)}/comments{q}", paginate=True)


def pull_request(url: str) -> dict:
    """Verified PR resource for ``register-upstream-pr``."""
    parts = url.rstrip("/").split("/")
    if len(parts) != 7 or parts[:3] != ["https:", "", "github.com"] or parts[5] != "pull":
        raise CollectError("not a PR URL")
    pr = gh_get(f"/repos/{parts[3]}/{parts[4]}/pulls/{int(parts[6])}")
    return {
        "id": pr["id"], "number": pr["number"], "html_url": pr["html_url"], "state": pr["state"],
        "base_repository": pr["base"]["repo"]["full_name"], "base_ref": pr["base"]["ref"],
        "head_repository": (pr["head"].get("repo") or {}).get("full_name"),
        "head_repository_id": (pr["head"].get("repo") or {}).get("id") or 0,
        "head_ref": pr["head"]["ref"], "head_sha": pr["head"]["sha"],
        "merged": pr.get("merged", False), "merge_commit_sha": pr.get("merge_commit_sha"),
    }


def workflow_runs(repo: str, head_sha: str) -> list[dict]:
    data = gh_get(f"/repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
    return data.get("workflow_runs", [])


def run_jobs(repo: str, run_id: int, attempt: int) -> list[dict]:
    data = gh_get(f"/repos/{repo}/actions/runs/{int(run_id)}/attempts/{int(attempt)}/jobs?per_page=100")
    return data.get("jobs", [])


def pypi_release(distribution: str) -> dict:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{distribution}/json", timeout=30) as r:
        return json.load(r)


def usage(url: str) -> tuple[Any, datetime]:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r), datetime.now(timezone.utc)
