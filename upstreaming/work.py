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
WORKER_PROFILE = "upstreaming-worker"
PROPOSAL_ARTIFACT = "upstreaming-proposal"

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


def node(request: dict, record: dict, **kw) -> dict:
    pl = payload(request, record, **kw)
    key = request["dedupe_key"]
    return {
        "graph_id": "upstreaming:" + hashlib.sha256(key.encode()).hexdigest()[:32],
        "node_key": "task",
        "pool": POOL,
        "priority": 2 if request["task"] in ("upstream_revision", "development_repair") else 3,
        "fairness_key": "",
        "worker_profile": WORKER_PROFILE,
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
        "Do not modify any repository. Return the dossier JSON as the proposal artifact."),
    "development_patch": (
        "Write the smallest patch to the fork's riscv64 branch that makes the upstream project build, "
        "test and publish Linux riscv64 wheels through its normal release process, following the "
        "nearest existing architecture pattern. Return the proposal and patch series as the artifact."),
    "development_repair": (
        "Diagnose the failing fork CI identified by reason_ids on the expected head and propose a "
        "focused fix within scope. Return the proposal and patch series as the artifact."),
    "upstream_revision": (
        "Address the current maintainer feedback/CI failures identified by reason_ids on the "
        "upstream-facing riscv64 branch. No {debug} commits. Return the proposal and series."),
}


def dumps(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
