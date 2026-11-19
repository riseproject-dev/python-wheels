# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Native work-queue plans for upstreaming tasks (plan sections 5.1, 15.1).

``controller.tick`` produces ``submit_work`` requests. This module turns
them into the immutable gh-aw Work payload and a staged plan for the
dispatcher (``{"version": 1, "nodes": [...], "dispatch": {...}}``, the
format accepted by gh-aw's ``stagePlanIntents``).

Effect contracts. gh-aw v1.2.2 verifies only a fixed set of output types
inside a queue Claim; a branch push to another repository is not one of
them (``push_to_pull_request_branch`` has no Claim verifier). So the
agent's only resource output is ``upload_artifact`` (verified by the
Actions artifact API), carrying the proposal and patch series. The trusted
``publish`` job of the worker workflow reads that artifact after the Claim
is verified and performs the fork push itself, recorded as a pipeline
operation. Investigations are no-write.
"""

from __future__ import annotations

import hashlib
import json

from .common import CONTROL_REPO, DEV_REF, canonical_json

POOL = "upstreaming"
# Two worker profiles in one pool: investigations (read and report, cheaper
# model, no publish job) and patch work (stronger model, trusted publish job).
WORKER_PROFILE = "upstreaming-worker"
INVESTIGATOR_PROFILE = "upstreaming-investigator"
PROFILE_WORKFLOWS = {WORKER_PROFILE: ".github/workflows/upstreaming-worker.lock.yml",
                     INVESTIGATOR_PROFILE: ".github/workflows/upstreaming-investigator.lock.yml"}
PROPOSAL_ARTIFACT = "upstreaming-out"

WRITE_TASKS = {"development_patch", "development_repair", "upstream_revision"}
ALLOWED_OPERATIONS = {
    "development_patch": ["append", "rewrite"],
    "development_repair": ["append", "rewrite"],
    "upstream_revision": ["append"],   # history policy may widen this per project
    "investigation": [],
}

# Diagnostic no-write outputs are always allowed alongside.
_DIAG = [{"type": t, "min": 0, "max": 1} for t in ("noop", "report_incomplete", "report_missing_tool",
                                                   "report_missing_data")]


def effect_contract(task: str) -> dict:
    if task == "investigation":
        # The dossier comes back as an artifact too, but investigations must
        # not need a write-capable Claim: they report via artifact only.
        return {"version": 1, "outputs": _DIAG + [{"type": "upload_artifact", "min": 1, "max": 1}]}
    if task in WRITE_TASKS:
        return {"version": 1, "outputs": _DIAG + [{"type": "upload_artifact", "min": 1, "max": 1}]}
    raise ValueError(f"unknown task {task}")


def payload(request: dict, record: dict, *, control_repo_id: str, allowed_paths: list[str],
            context: dict | None = None) -> dict:
    """Immutable Work payload for one controller request. Everything the
    agent and the trusted publish job need is in here; nothing is looked up
    from mutable state at execution time except re-checks."""
    task = request["task"]
    context = dict(context or {})
    issue = (record.get("active_work") or {}).get("tracking_issue")
    if issue is not None:
        context["tracking_issue"] = issue
    fork = record.get("fork") or {}
    up = record["upstream"]
    p = {
        "task": task,
        "plan": _PLANS[task],
        "contribution_id": record["contribution_id"],
        "revision": record["revision"],
        "tracking_issue": record["tracking_issue"]["number"],
        "upstream": up["full_name"],
        "upstream_repository_id": up.get("repository_id"),
        "base_ref": up.get("base_ref"),
        "base_sha": up.get("base_sha"),
        "fork": fork.get("name"),
        "fork_name": (fork.get("name") or "/").split("/", 1)[1] or None,
        "fork_repository_id": fork.get("repository_id"),
        "ref": DEV_REF,
        "expected_head": fork.get("head_sha"),
        "upstream_facing": record.get("upstream_pr") is not None,
        "allowed_operations": ALLOWED_OPERATIONS[task],
        "allowed_paths": allowed_paths,
        "distributions": record.get("distributions") or [],
        "admission_class": record.get("admission_class"),
        "reason_ids": request.get("reason_ids") or [],
        "context": context or {},
        "resource_scope": {"version": 1, "resources": [
            {"host": "github.com", "repository": CONTROL_REPO, "repository_id": str(control_repo_id)}]},
        "effect_contract": effect_contract(task),
    }
    return p


def profile_for(task: str) -> str:
    if task == "investigation":
        return INVESTIGATOR_PROFILE
    if task in WRITE_TASKS:
        return WORKER_PROFILE
    raise ValueError(f"unknown task {task}")


def graph_id(dedupe_key: str) -> str:
    return "upstreaming:" + hashlib.sha256(dedupe_key.encode()).hexdigest()[:32]


def request_from_active(rec: dict) -> dict | None:
    """The controller's committed request (``active_work``) as a work request,
    or None if there is nothing to dispatch for this record."""
    aw = rec.get("active_work")
    if not aw or rec.get("paused") or aw.get("revision") != rec["revision"]:
        return None
    fork = rec.get("fork") or {}
    return {"type": "submit_work", "dedupe_key": aw["dedupe_key"], "contribution_id": rec["contribution_id"],
            "revision": rec["revision"], "expected_head": fork.get("head_sha"), "task": aw["task"]}


def node(request: dict, record: dict, **kw) -> dict:
    pl = payload(request, record, **kw)
    key = request["dedupe_key"]
    return {
        "graph_id": graph_id(key),
        "node_key": "task",
        "pool": POOL,
        "priority": 2 if request["task"] in ("upstream_revision", "development_repair") else 3,
        "fairness_key": "",
        "worker_profile": profile_for(request["task"]),
        "payload": pl,
        "depends_on": [],
    }


def plan(nodes: list[dict], *, max_dispatches: int = 1) -> dict:
    if not nodes:
        raise ValueError("empty plan")
    return {"version": 1, "nodes": nodes,
            "dispatch": {"pool": POOL, "max_claims": max_dispatches, "max_dispatches": max_dispatches}}


def task_digest(pl: dict) -> str:
    return hashlib.sha256(canonical_json(pl).encode()).hexdigest()


_PLANS = {
    "investigation": (
        "Investigate this upstream project and produce the dossier for a riscv64 wheel contribution. "
        "Read the full tracking issue description in context.tracking_issue and fetch its comments. "
        "Research upstream issues, open/closed PRs, CI/history, docs, websites, mailing lists, blogs, "
        "maintainers and their past reviews before recommending scope. Query project_graph_query for "
        "the dependency graph. Check sw-ecosystem/project-reports and extensively use any matching "
        "report, cross-checking it with current upstream sources. The dossier must satisfy "
        "upstreaming/schemas/dossier.schema.json, including complete research records with source URLs "
        "and findings for every category. Missing or unavailable required research is incomplete work: "
        "do not finish completed. Do not modify any repository. Return the dossier JSON as the proposal artifact."),
    "development_patch": (
        "Write the smallest patch to the fork's riscv64 branch that makes the upstream project build, "
        "test and publish Linux riscv64 wheels through its normal release process, following the "
        "nearest existing architecture pattern. The project's own CI must run on the fork: if a job is "
        "guarded to the upstream repository (for example `if: github.repository == 'owner/repo'`), "
        "lift the guard in a separate {debug} commit. CI must execute natively on `ubuntu-24.04-riscv` "
        "and upload the built riscv64 wheel as an artifact. If the project already has such a job, "
        "the fix may be only the {debug} commit. Return the proposal and patch series as the artifact."),
    "development_repair": (
        "Diagnose the failing fork CI identified by reason_ids on the expected head and propose a "
        "focused fix within scope. Return the proposal and patch series as the artifact."),
    "upstream_revision": (
        "Address the current maintainer feedback/CI failures identified by reason_ids on the "
        "upstream-facing riscv64 branch. No {debug} commits. Return the proposal and series."),
}


def dumps(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
