# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Create or discover one controller-authorized same-fork development PR."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from . import collect, schemas
from .common import CONTROL_REPO, DEV_REF, contribution_file_id


class DevPRError(ValueError):
    pass


def body(record: dict, operation: dict) -> str:
    return "\n".join([
        "## riscv64 wheel development",
        "",
        "This same-fork pull request is the automated development and CI workspace for a bounded riscv64 wheel contribution.",
        "",
        f"Tracking issue: https://github.com/{CONTROL_REPO}/issues/{record['tracking_issue']['number']}",
        f"Verified dossier: `{record['dossier_evidence_id']}`",
        f"Allowed paths: {', '.join(record['scope_paths'] or [])}",
        "",
        "This is not an upstream submission. Human approval is required before upstream handoff.",
        "",
        operation["proposed"]["marker"],
    ])


def load_request(root: Path, operation_id: str) -> tuple[dict, dict]:
    if not re.fullmatch(r"op-[0-9a-f]{24}", operation_id):
        raise DevPRError("invalid operation ID")
    op = json.loads((root / "upstreaming-state/operations" / f"{operation_id}.json").read_text())
    schemas.validate("operation", op)
    cid = contribution_file_id(op["contribution_id"])
    record = json.loads((root / "upstreaming-state/contributions" / f"{cid}.json").read_text())
    schemas.validate("contribution", record)
    fork = record.get("fork") or {}
    if op["kind"] != "dev_pr_create" or op["status"] != "planned" \
            or record["phase"] != "development" or record.get("active_operation_id") != operation_id \
            or record["revision"] != op["revision"] or record.get("paused") or record.get("blocked_reason"):
        raise DevPRError("operation is not the current authorized development PR intent")
    if op["target"].get("repository") != fork.get("name") or op["target"].get("repository_id") != fork.get("repository_id") \
            or op["target"].get("ref") != DEV_REF or op["target"].get("expected_head") != fork.get("head_sha") \
            or op["target"].get("base_sha") != record["upstream"].get("base_sha"):
        raise DevPRError("development PR target does not match current fork/base")
    return record, op


class Api(collect.Api):
    def write(self, path: str, value: dict) -> dict:
        if not path.startswith("/repos/") or not path.endswith("/pulls") or ".." in path:
            raise DevPRError("unsupported development PR API operation")
        req = urllib.request.Request(self.base + path, data=json.dumps(value).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {self.token}",
                                              "Accept": "application/vnd.github+json",
                                              "Content-Type": "application/json",
                                              "X-GitHub-Api-Version": "2022-11-28"})
        try:
            with self._open(req, timeout=30) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            raise DevPRError(f"development PR API HTTP {exc.code}") from None
        if len(raw) > 2 * 1024 * 1024:
            raise DevPRError("oversized development PR response")
        return json.loads(raw)


def publish(root: Path, operation_id: str, token: str, run_id: str) -> dict:
    record, op = load_request(root, operation_id)
    api = Api(token=token)
    repo = collect.repository(api, op["target"]["repository"])
    if repo["id"] != op["target"]["repository_id"] or repo.get("parent_id") != record["upstream"]["repository_id"]:
        raise DevPRError("fork identity changed")
    head = collect.branch_head(api, repo["full_name"], DEV_REF)
    if not head or head["head"] != op["target"]["expected_head"]:
        raise DevPRError("development branch head changed")
    base_ref = record["upstream"]["base_ref"]
    owner = repo["full_name"].split("/", 1)[0]
    query = urllib.parse.urlencode({"state": "open", "head": f"{owner}:{DEV_REF}", "base": base_ref, "per_page": 100})
    pulls = api.get(f"/repos/{repo['full_name']}/pulls?{query}")
    marker = op["proposed"]["marker"]
    matching = [pr for pr in pulls if marker in (pr.get("body") or "")]
    unrelated = [pr for pr in pulls if marker not in (pr.get("body") or "")]
    if len(matching) > 1 or unrelated:
        raise DevPRError("existing development-head PR is ambiguous or unrelated")
    expected_body = body(record, op)
    pr = matching[0] if matching else api.write(f"/repos/{repo['full_name']}/pulls", {
        "title": "CI: develop riscv64 wheel support",
        "head": DEV_REF,
        "base": base_ref,
        "body": expected_body,
        "draft": False,
        "maintainer_can_modify": False,
    })
    observed = api.get(f"/repos/{repo['full_name']}/pulls/{pr['number']}")
    if observed.get("state") != "open" or observed.get("body") != expected_body \
            or (observed.get("head") or {}).get("sha") != op["target"]["expected_head"] \
            or (observed.get("head") or {}).get("ref") != DEV_REF \
            or (observed.get("base") or {}).get("ref") != base_ref:
        raise DevPRError("development PR readback mismatch")
    return {"schema_version": 1, "status": "published", "operation_id": operation_id,
            "contribution_id": record["contribution_id"], "revision": record["revision"],
            "repository": repo["full_name"], "repository_id": repo["id"],
            "pr_id": observed["id"], "pr_number": observed["number"], "pr_url": observed["html_url"],
            "head_sha": op["target"]["expected_head"], "base_ref": base_ref,
            "development_pr_run_id": int(run_id)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REPOSITORY") != CONTROL_REPO \
            or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise DevPRError("development PRs require the trusted control workflow on main")
    result = publish(Path.cwd(), args.operation_id, os.environ.get("UPSTREAMING_FORK_TOKEN", ""), os.environ["GITHUB_RUN_ID"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
