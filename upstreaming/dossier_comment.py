# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Publish an exact verified investigation Result as a readable issue comment."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from .common import CONTROL_REPO, canonical_json
from .dossier_gate import validate


class CommentError(ValueError):
    pass


def _text(value, limit=8000):
    return str(value).replace("\x00", "").replace("<!--", "&lt;!--").strip()[:limit]


def marker(task: dict, result: dict) -> str:
    identity = {"contribution_id": task["contribution_id"], "revision": task["revision"],
                "work_id": result["work_id"], "claim_id": result["claim_id"],
                "artifact_id": result["artifact_id"], "digest": result["digest"]}
    return "<!-- upstreaming-investigation-result:" + hashlib.sha256(canonical_json(identity).encode()).hexdigest() + " -->"


def render(dossier: dict, task: dict, result: dict) -> str:
    lines = ["## Upstreaming investigation result", "", _text(dossier["summary"]), ""]
    proposal = dossier.get("proposal") or {}
    if proposal:
        lines += ["### Proposed direction", ""]
        for key, value in list(proposal.items())[:20]:
            label = _text(str(key).replace("_", " ").capitalize(), 100)
            if isinstance(value, (str, int, float, bool)) or value is None:
                lines.append(f"- **{label}:** {_text(value, 2000)}")
            elif isinstance(value, list):
                lines.append(f"- **{label}:** " + "; ".join(_text(v, 500) for v in value[:20]))
        lines.append("")
    lines += ["### Dependency and ecosystem evidence", "", _text(dossier["dependency_graph"]["assessment"]), ""]
    report = dossier["ecosystem_report"]
    if report["status"] == "available":
        lines += [f"Ecosystem report: {report['url']} (`{_text(report['revision'], 100)}`)", "",
                  _text(report["riscv64_status"]), ""]
    else:
        lines += ["No matching ecosystem report was available; the dossier records the search evidence.", ""]
    lines += ["### Research coverage", ""]
    for category, record in dossier["research"].items():
        lines.append(f"- **{category.replace('_', ' ').title()}**: {_text(record['findings'], 1000)}")
        links = [source["url"] for source in record["sources"][:5]]
        if links:
            lines.append("  Sources: " + ", ".join(links))
    if dossier.get("history"):
        lines += ["", "### Relevant prior work", ""]
        for item in dossier["history"][:30]:
            lines.append(f"- [{item['outcome']}]({item['url']}): {_text(item['decision'], 1000)}")
    lines += ["", f"Verified native Result: work `{result['work_id']}`, claim `{result['claim_id']}`, artifact `{result['artifact_id']}`.",
              "This is investigation evidence, not an upstream approval or publication decision.", "", marker(task, result)]
    body = "\n".join(lines)
    if len(body.encode()) > 60_000:
        raise CommentError("rendered dossier comment exceeds bounded size")
    return body


def request(method: str, path: str, token: str, body: dict | None = None):
    prefix = f"/repos/{CONTROL_REPO}/issues/"
    if method not in ("GET", "POST") or not token or not path.startswith(prefix) or ".." in path:
        raise CommentError("invalid comment API request")
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request("https://api.github.com" + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise CommentError(f"comment API HTTP {exc.code}") from None
    if len(raw) > 2 * 1024 * 1024:
        raise CommentError("oversized comment API response")
    return json.loads(raw) if raw else None


def trusted_runtime(env: dict[str, str]) -> bool:
    return env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == CONTROL_REPO \
        and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" \
        and env.get("GITHUB_WORKFLOW") in ("Upstreaming investigator", "Upstreaming publish retry")


def publish(dossier: dict, proposal: dict, task: dict, result: dict, token: str, run_id: str,
            expected_author: str | None = None) -> dict:
    validate(dossier, proposal, task)
    for key in ("work_id", "claim_id", "artifact_id", "digest"):
        if not result.get(key):
            raise CommentError(f"verified Result missing {key}")
    number = int(task["tracking_issue"])
    body = render(dossier, task, result)
    identity = marker(task, result)
    comments = request("GET", f"/repos/{CONTROL_REPO}/issues/{number}/comments?per_page=100", token)
    matches = [comment for comment in comments if identity in (comment.get("body") or "")]
    if len(matches) > 1:
        raise CommentError("multiple comments have the exact Result marker")
    created = not matches
    comment = matches[0] if matches else request("POST", f"/repos/{CONTROL_REPO}/issues/{number}/comments", token, {"body": body})
    observed = request("GET", f"/repos/{CONTROL_REPO}/issues/comments/{comment['id']}", token)
    if observed.get("body") != body or created and expected_author and (observed.get("user") or {}).get("login") != expected_author:
        raise CommentError("comment readback does not match verified Result and App author")
    return {"schema_version": 1, "status": "published", "contribution_id": task["contribution_id"],
            "revision": task["revision"], "work_id": result["work_id"], "claim_id": result["claim_id"],
            "artifact_id": result["artifact_id"], "comment_id": observed["id"],
            "comment_url": observed["html_url"], "content_digest": hashlib.sha256(body.encode()).hexdigest(),
            "notification_run_id": int(run_id)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dossier", "proposal", "task", "result"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not trusted_runtime(os.environ):
        raise CommentError("dossier comments require a trusted upstreaming Result workflow")
    values = [json.loads(getattr(args, name).read_text()) for name in ("dossier", "proposal", "task", "result")]
    receipt = publish(*values, os.environ.get("GH_TOKEN", ""), os.environ["GITHUB_RUN_ID"],
                      os.environ.get("UPSTREAMING_COMMENT_AUTHOR") or None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2))
