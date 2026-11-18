# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""One trusted reconciliation tick (plan section 9), producing state only.

Inputs, all read-only:
* committed ``upstreaming-state/``;
* GitHub: intake issues, command comments, verified PRs, fork branch heads,
  live CI on the exact head;
* worker publication outcomes (``upstreaming-publication`` artifacts of
  finished worker runs), which carry the native Result's artifact identity
  and the independent branch operation receipt;
* runner pressure.

Output: the set of state records to commit (by ``state_commit.publish``)
and a report. Remote effects are never performed here: dispatching work is
the dispatcher's job, pushing is the worker publish job's job.

A queue Result alone never advances the fork head or enters ``waiting_ci``;
only the publication receipt plus an observed branch head does.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import capacity, collect, controller, lifecycle, observe_ci, recovery


@dataclass
class Snapshot:
    contributions: dict[str, dict]
    operations: dict[str, dict]
    consumed: dict[int, dict]
    projects: dict[str, dict]
    evidence: dict[str, dict]


@dataclass
class TickOutput:
    staged: list[tuple[str, dict]] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)


RETRY_BACKOFF_MINUTES = (15, 60, 240)


def apply_publication(rec: dict, outcome: dict, *, now: str, policy: dict | None = None,
                      worker_run_id: str | None = None) -> tuple[dict, list[tuple[str, dict]]]:
    """Fold one publication outcome (from fork_publish / queue_result) into the record.

    * published / uncertain -> waiting_ci (observation confirms the head)
    * no_change             -> idle
    * rejected, validation  -> fix_needed (a new agent task)
    * rejected, stale       -> idle (the world moved; the next tick re-plans)
    * infra_error           -> keep the proposal, schedule a publish-only retry
                               of the same worker run with backoff; after
                               ``retries.infrastructure_per_head_failure``
                               attempts, wait for a human (no model call ever)
    """
    from datetime import datetime as _dt, timedelta
    staged: list[tuple[str, dict]] = []
    new = copy.deepcopy(rec)
    status = outcome.get("status")
    fclass = outcome.get("failure_class")
    pending = new.get("pending_publication")
    if status == "infra_error":
        attempts = (pending or {}).get("attempts", 0) + 1 if (pending or {}).get("worker_run_id") == worker_run_id \
            else max(outcome.get("attempt", 1), 1)
        limit = ((policy or {}).get("retries") or {}).get("infrastructure_per_head_failure", 2)
        exhausted = attempts > limit
        delay = RETRY_BACKOFF_MINUTES[min(attempts - 1, len(RETRY_BACKOFF_MINUTES) - 1)]
        new["pending_publication"] = {
            "worker_run_id": str(worker_run_id or (pending or {}).get("worker_run_id") or "0"),
            "attempts": attempts, "last_reason": (outcome.get("reason") or "")[:2000],
            "next_attempt_at": (_dt.fromisoformat(now) + timedelta(minutes=delay)).isoformat(),
            "exhausted": exhausted}
        new["activity"] = "waiting_human" if exhausted else "waiting_capacity"
        if exhausted:
            new["pending_human_action"] = {"kind": "publication_infrastructure_failure", "requested_at": now,
                                           "reminded_at": None, "escalated_at": None}
        op = outcome.get("operation")
        if op:
            staged.append(("operations", op))
            new["publication_operation_id"] = op["operation_id"]
        new["updated_at"] = now
        staged.append(("contributions", new))
        return new, staged
    new["pending_publication"] = None
    art = outcome.get("artifact")
    if art:
        new["proposal_artifact"] = {k: art[k] for k in ("work_id", "claim_id", "artifact_id", "name",
                                                        "digest", "run_id")} | {
            "result_commit": art.get("result_commit"), "outcome": outcome.get("status")}
    op = outcome.get("operation")
    if op:
        staged.append(("operations", op))
        new["publication_operation_id"] = op["operation_id"]
    status = outcome.get("status")
    if status == "published":
        # The branch head itself is recorded by the next observation (head
        # change bumps revision); here we only leave agent_running.
        new["activity"] = "waiting_ci"
    elif status == "uncertain":
        new["activity"] = "waiting_ci"   # discovery happens in observe_ci
    elif status == "no_change":
        new["activity"] = "idle"
    elif status == "rejected":
        new["activity"] = "idle" if fclass == "stale" else "fix_needed"
    new["updated_at"] = now
    staged.append(("contributions", new))
    return new, staged


def tick(api: collect.Api, snap: Snapshot, *, policy: dict, now: datetime,
         publications: list[dict], pressure: capacity.Pressure,
         issues: list[dict] | None = None, comments: list[dict] | None = None,
         verified_prs: dict[str, dict] | None = None, acceptances: dict[int, int] | None = None,
         observe: bool = True) -> TickOutput:
    out = TickOutput()
    iso = now.isoformat()
    contributions = dict(snap.contributions)
    by_cid = {c["contribution_id"]: k for k, c in contributions.items()}

    # 1. Publication outcomes from finished workers.
    pubs_report = []
    for pub in publications:
        cid = (pub.get("task") or {}).get("contribution_id")
        if cid not in by_cid:
            pubs_report.append({"ignored": "unknown contribution"})
            continue
        key = by_cid[cid]
        rec = contributions[key]
        pid = pub.get("publication_artifact_id")
        if pid and pid in (rec.get("processed_publications") or []):
            continue          # already folded in by an earlier tick
        if pid:
            rec = dict(rec, processed_publications=((rec.get("processed_publications") or []) + [pid])[-64:])
            contributions[key] = rec
        if pub.get("task", {}).get("revision") != rec["revision"] and pub.get("status") != "published":
            out.staged.append(("contributions", rec))
            pubs_report.append({"contribution": cid, "ignored": "stale revision"})
            continue
        rec, staged = apply_publication(rec, pub, now=iso, policy=policy, worker_run_id=pub.get("worker_run_id"))
        contributions[key] = rec
        out.staged.extend(staged)
        for kind, r in staged:
            if kind == "operations":
                snap.operations[r["operation_id"]] = r
        pubs_report.append({"contribution": cid, "status": pub.get("status"), "reason": pub.get("reason")})
    out.report["publications"] = pubs_report

    # 2. Live branch and CI observation.
    if observe:
        contracts = {e["evidence_id"]: e for e in snap.evidence.values() if e.get("kind") == "target_contract"}
        obs = observe_ci.observe(api, contributions=contributions, operations=snap.operations,
                                 contracts=contracts, policy=policy, now=iso)
        for kind, r in obs.staged:
            if kind == "contributions":
                contributions[by_cid[r["contribution_id"]]] = r
        out.staged.extend(obs.staged)
        out.report["observation"] = obs.report

    # 3. Commands, intake and work selection (controller).
    res = controller.tick(contributions=contributions, operations=snap.operations, consumed=snap.consumed,
                          projects=snap.projects, policy=policy,
                          inputs=controller.Inputs(now=now, issues=issues or [], comments=comments or [],
                                                   pressure=pressure, verified_prs=verified_prs or {},
                                                   acceptances=acceptances or {}))
    out.staged.extend(res.staged)
    out.report["controller"] = res.report
    out.report["requested_effects"] = res.requested_effects
    # 4. Publish-only retries due now (infrastructure failures; no model call).
    retries = []
    for c in contributions.values():
        pp = c.get("pending_publication")
        if pp and not pp.get("exhausted") and not c.get("paused") and c["phase"] in lifecycle.WRITE_PHASES \
                and datetime.fromisoformat(pp["next_attempt_at"]) <= now:
            retries.append({"type": "retry_publication", "contribution_id": c["contribution_id"],
                            "worker_run_id": pp["worker_run_id"], "attempt": pp["attempts"] + 1})
    out.report["publication_retries"] = retries
    out.staged = observe_ci.dedupe(out.staged)
    return out


def mark_dispatched(rec: dict, *, now: str) -> dict:
    """The dispatcher staged Work for this contribution: an agent is running."""
    out = lifecycle.observe_status(rec, activity="agent_running", now=now)
    return out.record
