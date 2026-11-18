# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Recoverable operation records and bounded uncertainty recovery
(plan sections 16.3 and 16.4).

There is no transaction spanning control Git, the native queue, fork pushes,
PR mutations, run launches or notifications. Each remote effect is an
operation: an intent persisted before the effect, then a receipt confirmed by
discovering the actual resource. A lost receipt is recovered by discovery,
never by repeating the effect. Elapsed time alone never confirms an effect,
declares nonlaunch, or frees capacity.
"""

from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timedelta
from typing import Any, Callable

from . import schemas
from .commands import Command

STATUSES = ("planned", "applying", "confirmed", "uncertain", "failed", "not_launched")
OPEN = frozenset({"planned", "applying", "uncertain"})
ALERT_AFTER = timedelta(hours=1)
OWNER_REVIEW_AFTER = timedelta(hours=24)


class RecoveryError(ValueError):
    pass


def operation_id(contribution_id: str, revision: int, kind: str, *reason_ids: str) -> str:
    """Deterministic: resubmitting the same intent yields the same ID, so a
    retried controller tick finds the existing operation instead of creating
    a second effect."""
    h = hashlib.sha256("\0".join([contribution_id, str(revision), kind, *reason_ids]).encode())
    return f"op-{h.hexdigest()[:24]}"


def plan(*, contribution_id: str, revision: int, kind: str, policy_version: str,
         reason_ids: list[str], target: dict, proposed: dict | None = None,
         capacity: dict | None = None, now: str) -> dict:
    op = {
        "schema_version": 1,
        "operation_id": operation_id(contribution_id, revision, kind, *reason_ids),
        "contribution_id": contribution_id,
        "revision": revision,
        "kind": kind,
        "policy_version": policy_version,
        "reason_ids": reason_ids,
        "target": target,
        "proposed": proposed or {},
        "capacity_reservation": capacity,
        "status": "planned",
        "external_ids": {},
        "discovery": [],
        "resolution": None,
        "created_at": now,
        "updated_at": now,
    }
    schemas.validate("operation", op)
    return op


def _set(op: dict, status: str, now: str, **extra: Any) -> dict:
    new = copy.deepcopy(op)
    new["status"] = status
    new["updated_at"] = now
    new.update(extra)
    schemas.validate("operation", new)
    return new


def mark_applying(op: dict, now: str) -> dict:
    if op["status"] != "planned":
        raise RecoveryError(f"cannot apply an operation in status {op['status']}")
    return _set(op, "applying", now)


def mark_result(op: dict, *, response_ok: bool | None, external_ids: dict | None, now: str) -> dict:
    """After the remote call. ``response_ok=None`` means the response was lost
    or ambiguous: the effect may or may not exist, so the operation becomes
    ``uncertain`` and must be discovered, not repeated."""
    if op["status"] != "applying":
        raise RecoveryError("result for an operation that was not applying")
    ids = dict(op["external_ids"], **(external_ids or {}))
    if response_ok is None:
        return _set(op, "uncertain", now, external_ids=ids)
    # Even an OK response is only provisional: discovery confirms the resource.
    return _set(op, "uncertain" if response_ok else "failed", now, external_ids=ids)


# Discovery predicates: given the operation and what the API shows now,
# return "confirmed", "absent", or "unrelated".


def discover_branch(op: dict, observed: dict | None) -> str:
    """observed = {"head": sha, "tree": sha, "parents": [...]} for the ref."""
    if observed is None:
        return "absent"
    prop = op.get("proposed") or {}
    if prop.get("commit") and observed.get("head") == prop["commit"]:
        return "confirmed"
    if prop.get("tree") and observed.get("tree") == prop["tree"] and \
            observed.get("parents") == prop.get("parents"):
        # Signed replay can change the commit SHA; tree + parents identify it.
        return "confirmed"
    if observed.get("head") == op["target"].get("expected_head"):
        return "absent"
    return "unrelated"


def discover_pr(op: dict, prs: list[dict]) -> str:
    """prs = open PRs in the fork, each with head_repo/head_ref/base_ref/body."""
    marker = (op.get("proposed") or {}).get("marker")
    for pr in prs:
        if pr.get("head_ref") == op["target"].get("ref") and \
                (marker is None or marker in (pr.get("body") or "")):
            return "confirmed"
    return "absent"


def discover_dispatch(op: dict, runs: list[dict], window: tuple[str, str]) -> str:
    """A dispatch is confirmed only by an associated run inside the launch
    window. Absence is *not* definitive nonlaunch."""
    lo, hi = window
    for r in runs:
        if r.get("head_sha") == op["target"].get("expected_head") and lo <= r["created_at"] <= hi \
                and r.get("event") in ("workflow_dispatch", "push", "pull_request"):
            return "confirmed"
    return "absent"


def discover_notification(op: dict, comments: list[dict]) -> str:
    marker = (op.get("proposed") or {}).get("marker")
    for c in comments:
        if marker and marker in (c.get("body") or ""):
            return "confirmed"
    return "absent"


DISCOVERERS: dict[str, Callable[..., str]] = {
    "branch_update": discover_branch,
    "branch_rewrite": discover_branch,
    "dev_pr_create": discover_pr,
    "dev_pr_update": discover_pr,
    "ci_dispatch": discover_dispatch,
    "ci_rerun": discover_dispatch,
    "notification": discover_notification,
}


def record_discovery(op: dict, result: str, detail: str, now: str) -> dict:
    """Fold one discovery attempt into the operation.

    * confirmed -> confirmed
    * unrelated -> stays uncertain; affected work holds for reconciliation
    * absent    -> stays uncertain (absence never proves nonlaunch)
    """
    if op["status"] not in OPEN:
        raise RecoveryError("discovery on a closed operation")
    disc = op["discovery"] + [{"at": now, "result": result, "detail": detail[:2000]}]
    status = "confirmed" if result == "confirmed" else "uncertain"
    return _set(op, status, now, discovery=disc)


def next_discovery_at(op: dict, policy: dict) -> datetime | None:
    if op["status"] not in OPEN:
        return None
    start = datetime.fromisoformat(op["created_at"])
    sched = policy["recovery_minutes"]
    n = len(op["discovery"])
    if n < len(sched):
        return start + timedelta(minutes=sched[n])
    # Reduced frequency thereafter; never declares success.
    return datetime.fromisoformat(op["discovery"][-1]["at"]) + timedelta(hours=6)


def alerts(op: dict, now: datetime) -> list[str]:
    if op["status"] not in OPEN or op["status"] == "planned":
        return []
    age = now - datetime.fromisoformat(op["created_at"])
    out = []
    if age >= ALERT_AFTER:
        out.append("uncertain_over_1h")
    if age >= OWNER_REVIEW_AFTER:
        out.append("owner_review_required")
    return out


def resolve(op: dict, cmd: Command, *, actor: dict, command_id: str, evidence: dict | None,
            now: str) -> dict:
    """Apply ``/upstreaming resolve-operation``. Requires positive evidence of
    the stated disposition; it never synthesizes a native queue Result."""
    if cmd.verb != "resolve-operation" or cmd.args["operation"] != op["operation_id"]:
        raise RecoveryError("command does not target this operation")
    if op["status"] not in OPEN:
        raise RecoveryError(f"operation already {op['status']}")
    if evidence is None or evidence.get("evidence_id") != cmd.args["evidence"]:
        raise RecoveryError("resolution evidence record not found")
    if evidence.get("kind") != "resolution":
        raise RecoveryError("evidence is not a resolution record")
    disposition = cmd.args["disposition"]
    status = {"confirmed": "confirmed", "not-launched": "not_launched", "failed": "failed"}[disposition]
    return _set(op, status, now, resolution={
        "actor": actor, "disposition": disposition,
        "evidence_id": evidence["evidence_id"], "command_id": command_id,
    })


def releases_capacity(op: dict) -> bool:
    """Capacity reservations are freed only on verified termination or
    definitive nonlaunch, never on elapsed time."""
    return op["status"] in ("not_launched", "failed") or (
        op["status"] == "confirmed" and op["kind"] not in ("ci_dispatch", "ci_rerun",
                                                           "branch_update", "branch_rewrite"))
