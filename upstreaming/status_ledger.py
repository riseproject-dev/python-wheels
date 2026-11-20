# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Append concise App-authored lifecycle entries to tracking issues."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from . import schemas
from .common import CONTROL_REPO


class LedgerError(ValueError):
    pass


MESSAGES = {
    "intake:accepted": "Accepted the labeled request.",
    "intake:label_removed": "Cancelled intake because the request label was removed before Work admission.",
    "dossier_develop": "Verified the investigation dossier and admitted automatic development.",
    "dossier_parked": "Verified the investigation dossier and parked the contribution because no bounded patch is actionable.",
    "fork_provisioned": "Provisioned and verified the contribution fork and exact `riscv64` base.",
    "development_pr_created": "Created and verified the same-fork development PR.",
    "development_review_feedback": "Recorded authorized development-PR change feedback and requested repair.",
    "development_review_inquiry": "Recorded an authorized explanation-only development-PR comment. No repair was requested; lifecycle state is unchanged.",
    "handoff_ready": "Accepted clean-head development CI and reached human upstream handoff.",
}


def _command_lines(record: dict) -> list[str]:
    revision = record["revision"]
    lines = []
    phase = record["phase"]
    if phase not in ("released", "abandoned", "superseded", "no_work", "already_released"):
        lines += [f'/upstreaming pause revision={revision} reason="..."',
                  f'/upstreaming park revision={revision} reason="..."',
                  f'/upstreaming abandon revision={revision} reason="..."']
    if record.get("paused") or record.get("blocked_reason"):
        lines.append(f'/upstreaming resume revision={revision} reason="..."')
    if phase in ("development", "handoff") and (record.get("fork") or {}).get("pr_number"):
        lines.append(f'/upstreaming refresh revision={revision} reason="..."')
    if phase == "abandoned":
        lines.append(f'/upstreaming restart revision={revision} reason="..."')
    if phase == "parked":
        paths = ",".join(record.get("scope_paths") or [".github/workflows/*"])
        admission = record.get("admission_class") or "configuration_integration"
        lines.append(f'/upstreaming force-develop revision={revision} class={admission} paths="{paths}" reason="..."')
    if phase == "handoff" and record.get("clean_head_sha"):
        lines.append(f'/upstreaming approve-handoff revision={revision} head={record["clean_head_sha"]}')
    return lines


def render(event: dict, record: dict, run_url: str) -> str:
    schemas.validate("event", event); schemas.validate("contribution", record)
    revision = event.get("to", {}).get("revision", record["revision"])
    phase = event.get("to", {}).get("phase", record["phase"])
    activity = event.get("to", {}).get("activity", record["activity"])
    kind = event["kind"]
    message = MESSAGES.get(kind, kind.replace("_", " ").replace(":", ": ").capitalize() + ".")
    visible = f"**Upstreaming r{revision} · {phase}/{activity}** — {message} [Workflow run]({run_url})"
    commands = _command_lines(record)
    details = ""
    if commands:
        details = "\n\n<details>\n<summary>Possible next commands</summary>\n\n```text\n" + "\n".join(commands) + "\n```\n</details>"
    marker = f"<!-- upstreaming-ledger:{record['contribution_id']}:{event['sequence']} -->"
    return visible + details + "\n\n" + marker


class Api:
    def __init__(self, token: str):
        if not token:
            raise LedgerError("App issue token required")
        self.token = token

    def request(self, method: str, path: str, body: dict | None = None):
        if method not in ("GET", "POST") or not path.startswith(f"/repos/{CONTROL_REPO}/issues/") or ".." in path:
            raise LedgerError("invalid ledger API request")
        req = urllib.request.Request("https://api.github.com" + path,
            data=None if body is None else json.dumps(body).encode(), method=method,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            raise LedgerError(f"ledger API HTTP {exc.code}") from None
        if len(raw) > 2 * 1024 * 1024:
            raise LedgerError("oversized ledger response")
        return json.loads(raw) if raw else None


def publish(root: Path, report: dict, token: str, run_url: str) -> list[dict]:
    api = Api(token)
    paths = [Path(path) for path in report.get("written", [])
             if re.fullmatch(r"upstreaming-state/events/[A-Za-z0-9_.-]+/[0-9]{8}\.json", path)]
    receipts = []
    comment_cache: dict[int, list[dict]] = {}
    for path in sorted(paths):
        event = json.loads((root / path).read_text())
        cid_file = path.parent.name
        record = json.loads((root / "upstreaming-state/contributions" / f"{cid_file}.json").read_text())
        number = record["tracking_issue"]["number"]
        marker = f"<!-- upstreaming-ledger:{record['contribution_id']}:{event['sequence']} -->"
        comments = comment_cache.setdefault(number, api.request("GET", f"/repos/{CONTROL_REPO}/issues/{number}/comments?per_page=100"))
        existing = next((comment for comment in comments if marker in (comment.get("body") or "")), None)
        if existing:
            receipts.append({"event": str(path), "comment_id": existing["id"], "status": "existing"})
            continue
        body = render(event, record, run_url)
        comment = api.request("POST", f"/repos/{CONTROL_REPO}/issues/{number}/comments", {"body": body})
        observed = api.request("GET", f"/repos/{CONTROL_REPO}/issues/comments/{comment['id']}")
        if observed.get("body") != body or (observed.get("user") or {}).get("login") != "riseproject-dev[bot]":
            raise LedgerError("ledger comment readback or App author mismatch")
        comments.append(observed)
        receipts.append({"event": str(path), "comment_id": observed["id"], "status": "created"})
    return receipts


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = publish(args.root, json.loads(args.report.read_text()), os.environ.get("GH_TOKEN", ""), args.run_url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
