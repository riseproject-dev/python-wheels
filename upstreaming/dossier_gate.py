# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Trusted research-completeness gate, before durable investigation Completion.

Reads bounded JSON from the exact Claim staging directory, never executes
agent files. The native queue still authenticates the Claim and verifies upload.
This gate checks documented research coverage, not the truth of every assertion.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import schemas
from .common import sha256_text

RESEARCH_CATEGORIES = (
    "tracking_issue", "upstream_issues", "upstream_pull_requests", "ci_history",
    "documentation", "website", "mailing_lists", "blogs", "maintainer_reviews", "release_repositories", "ecosystem_report",
)
OPTIONALLY_ABSENT = {"website", "mailing_lists", "blogs", "release_repositories", "ecosystem_report"}


class DossierError(ValueError):
    pass


def validate(dossier: dict, proposal: dict, task: dict) -> None:
    schemas.validate("dossier", dossier)
    schemas.validate("proposal", proposal)
    for obj in (dossier, proposal):
        if obj["contribution_id"] != task["contribution_id"] or obj["expected_revision"] != task["revision"]:
            raise DossierError("dossier/proposal does not answer this immutable task")
    if proposal["outcome"] != "investigation" or proposal["operation"] != "none":
        raise DossierError("investigator must deliver an investigation, not a patch")
    if proposal.get("expected_head") != task.get("expected_head"):
        raise DossierError("proposal head does not match task")
    issue = (task.get("context") or {}).get("tracking_issue") or {}
    if not issue.get("url") or not isinstance(issue.get("description"), str):
        raise DossierError("task has no frozen tracking-issue description and URL")
    digest = sha256_text(issue["description"])
    if digest != issue.get("description_digest") or dossier["tracking_issue_description_digest"] != digest:
        raise DossierError("tracking issue description digest does not match immutable task")
    for category in RESEARCH_CATEGORIES:
        entry = dossier["research"][category]
        if entry["status"] == "not_applicable" and category not in OPTIONALLY_ABSENT:
            raise DossierError(f"{category}: research cannot be skipped")
    report = dossier["ecosystem_report"]
    research = dossier["research"]["ecosystem_report"]
    if report["status"] == "available":
        if research["status"] != "searched" or report["url"] not in {s["url"] for s in research["sources"]}:
            raise DossierError("available ecosystem report must be researched and cited")
    elif research["status"] != "not_applicable":
        raise DossierError("absent ecosystem report needs documented discovery and justification")
    if issue["url"] not in {s["url"] for s in dossier["research"]["tracking_issue"]["sources"]}:
        raise DossierError("tracking-issue research must cite the original issue URL")


def _read(root: Path, relative: Path, limit: int = 256 * 1024) -> str:
    if root.is_symlink() or relative.is_absolute() or ".." in relative.parts:
        raise DossierError("invalid or symlinked staging path")
    path = root
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise DossierError("symlink in investigation staging")
    if not path.is_file() or path.stat().st_size > limit:
        raise DossierError(f"missing or oversized research input: {relative}")
    data = path.read_bytes()
    if len(data) > limit:
        raise DossierError("research input grew beyond its bound")
    return data.decode("utf-8")


def check_stage(assignment: dict, staging: Path, finish_root: Path) -> str:
    claims = assignment.get("claims") or []
    if assignment.get("version") != 3 or len(claims) != 1:
        raise DossierError("expected a singleton version-3 investigator assignment")
    member = claims[0]
    task = member["work"]
    if task.get("task") != "investigation":
        raise DossierError("research gate only accepts investigator tasks")
    # A cancellation needs no dossier, but cannot smuggle a completed intent.
    # Native processing downstream still authenticates and applies these intents.
    intents = [json.loads(line) for line in _read(finish_root, Path("work-queue.finish.jsonl"), 1024 * 1024).splitlines()
               if line.strip()]
    if intents and all(i.get("version") == 3 and i.get("kind") == "finish"
                       and i.get("claim_handle", member["handle"]) == member["handle"]
                       and (i.get("parameters") or {}).get("outcome") == "cancelled" for i in intents):
        return "cancelled: no completed investigation admitted"
    identity = {"dispatch_id": assignment["dispatch_id"], "claim_id": member["claim_id"],
                "work_id": member["work_id"], "claim_handle": member["handle"]}
    # gh-aw's native codec is compact, recursively key-sorted JSON. The broader
    # pipeline canonical_json format is intentionally pretty-printed and is not
    # the Claim artifact namespace codec.
    native = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    namespace = hashlib.sha256(native.encode()).hexdigest()
    base = Path("claims") / namespace / "upstreaming-out"
    dossier = json.loads(_read(staging, base / "dossier.json"))
    proposal = json.loads(_read(staging, base / "proposal.json"))
    validate(dossier, proposal, task)
    return "research complete: eligible for native Completion and verified artifact delivery"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--finish-root", type=Path)
    parser.add_argument("--dossier", type=Path)
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--task", type=Path)
    parser.add_argument("--assignment-env", default="ASSIGNMENT")
    args = parser.parse_args()
    files = (args.dossier, args.proposal, args.task)
    if any(files):
        if not all(files) or args.staging or args.finish_root:
            parser.error("--dossier, --proposal and --task must be supplied together")
        validate(*(json.loads(path.read_text()) for path in files))
        print("dossier, proposal and task satisfy the research contract")
    else:
        if not args.staging or not args.finish_root:
            parser.error("--staging and --finish-root are required for trusted staging validation")
        raw = os.environ[args.assignment_env]
        if len(raw.encode()) > 49152:
            raise DossierError("assignment exceeds native bound")
        print(check_stage(json.loads(raw), args.staging, args.finish_root))
