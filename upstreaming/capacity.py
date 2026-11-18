# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Runner pressure observations, reservations and budgets (plan section 16).

The usage endpoint reports jobs and workers. That is pressure, not proof of
free hardware. Stale, malformed or unavailable data means "no new expensive
admissions", never "zero load". Commands, recovery and cheap observation
continue regardless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from .common import NATIVE_RUNNER_LABEL

RISE_ENTITY = "riseproject-dev"
FORK_ENTITY = "riseproject-upstreaming"


@dataclass
class Pressure:
    ok: bool
    reason: str | None = None
    running: int = 0
    pending: int = 0
    oldest_pending_seconds: int = 0          # over every entity (pressure on the shared pool)
    oldest_pending_rise_seconds: int = 0     # RISE entities only (our own backlog)
    per_entity: dict[str, dict[str, int]] = field(default_factory=dict)


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def observe(snapshot: Any, *, fetched_at: datetime, now: datetime, label: str = NATIVE_RUNNER_LABEL,
            max_age_seconds: int) -> Pressure:
    """Summarize a usage.json response for one runner label."""
    if (now - fetched_at).total_seconds() > max_age_seconds:
        return Pressure(ok=False, reason="stale usage data")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("jobs"), list):
        return Pressure(ok=False, reason="malformed usage data")
    p = Pressure(ok=True)
    for j in snapshot["jobs"]:
        if not isinstance(j, dict) or label not in (j.get("job_labels") or []):
            continue
        ent = p.per_entity.setdefault(str(j.get("entity_name")), {"running": 0, "pending": 0})
        if j.get("status") == "running":
            p.running += 1
            ent["running"] += 1
        elif j.get("status") in ("pending", "queued"):
            p.pending += 1
            ent["pending"] += 1
            try:
                age = (now - _parse_ts(j["job_created_at"])).total_seconds()
                p.oldest_pending_seconds = max(p.oldest_pending_seconds, int(age))
                if str(j.get("entity_name")) in (RISE_ENTITY, FORK_ENTITY):
                    p.oldest_pending_rise_seconds = max(p.oldest_pending_rise_seconds, int(age))
            except (KeyError, ValueError, TypeError):
                pass
    return p


def reserved_jobs(operations: Iterable[dict]) -> int:
    """Estimated jobs held by pipeline operations not yet visible or not yet
    finished. Observed run IDs replace the estimate (no double counting) in
    the caller once the runs' jobs appear in usage data."""
    total = 0
    for op in operations:
        r = op.get("capacity_reservation")
        if not r or op["status"] in ("failed", "not_launched"):
            continue
        if r.get("observed_run_ids"):
            continue
        total += r.get("estimated_jobs", 0)
    return total


def admit_expensive(p: Pressure, *, reserved: int, estimated_jobs: int, policy: dict) -> tuple[bool, str]:
    cap = policy["capacity"]
    if not p.ok:
        return False, f"no expensive admission: {p.reason}"
    pending = p.per_entity.get(RISE_ENTITY, {}).get("pending", 0) + \
        p.per_entity.get(FORK_ENTITY, {}).get("pending", 0)
    if pending + reserved + estimated_jobs > cap["max_pending_jobs_rise"]:
        return False, f"pending {pending} + reserved {reserved} + new {estimated_jobs} over threshold"
    # Another tenant's long queue does not mean our jobs wait: the backlog age
    # that gates admission is RISE's own (control repo and contribution forks).
    if p.oldest_pending_rise_seconds > cap["max_pending_age_seconds"]:
        return False, f"oldest pending RISE job waited {p.oldest_pending_rise_seconds}s"
    return True, "within thresholds"


# --------------------------------------------------------------------------
# Budgets (plan section 16.2)


def charge_attempt(budget: dict, *, cluster: str | None, progress: str, policy: dict) -> tuple[dict, list[str]]:
    """Charge one attempt (model call, queue retry, killed build, local repro
    or new Work all count). Returns the new budget and any stop reasons.
    Changed error text does not reset a cluster; new fingerprints do not
    reset totals."""
    r = policy["retries"]
    b = {**budget, "clusters": dict(budget.get("clusters", {}))}
    b["attempts_used"] = b.get("attempts_used", 0) + 1
    if cluster:
        b["clusters"][cluster] = b["clusters"].get(cluster, 0) + 1
    b["no_progress_streak"] = 0 if progress != "none" else b.get("no_progress_streak", 0) + 1
    stops = []
    if cluster and b["clusters"][cluster] >= r["patch_attempts_per_cluster"]:
        stops.append(f"patch attempts for cluster {cluster} exhausted")
    if b["attempts_used"] >= r["max_attempts_per_contribution"]:
        stops.append("contribution attempt ceiling reached")
    if b["no_progress_streak"] >= r["no_progress_review_after"]:
        stops.append("no progress in successive attempts: owner review")
    return b, stops


def classify_failure(text: str) -> str:
    """Coarse failure class from a sanitized log excerpt. Unknown stays
    unknown and goes to bounded evidence collection or a human."""
    t = text.lower()
    if any(s in t for s in ("waiting for a runner", "no runner", "runner lost communication",
                            "the operation was canceled", "econnreset", "503 service")):
        return "infrastructure"
    if any(s in t for s in ("resource not accessible by integration", "requires approval",
                            "403 forbidden", "permission denied (publickey)")):
        return "permission"
    if any(s in t for s in ("no matching distribution found", "could not find a version that satisfies")):
        return "dependency"
    if any(s in t for s in ("error:", "failed", "traceback", "assertionerror")):
        return "code"
    return "unknown"
