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

from . import capacity, collect, controller, lifecycle, observe_ci, recovery, schemas
from .common import safe_id


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

# A dispatcher launch that has not shown up as a run by then is launched again.
DISPATCH_LAUNCH_GRACE_MINUTES = 15
DISPATCHER_WORKFLOW = ".github/workflows/upstreaming-dispatcher.lock.yml"


def dispatch_recovery(contributions: dict[str, dict], *, runs: list[dict] | None,
                      queue_works: dict[str, str] | None, now: datetime, policy: dict) -> tuple[list[dict], list[tuple[str, dict]], list[dict]]:
    """Requested tasks whose dispatch never reached the queue (plan 15.3).

    ``runs`` are recent dispatcher workflow runs (GitHub API objects);
    ``queue_works`` maps a Work's ``graph_id`` to its queue state, from the
    pinned gh-aw CLI's validating replay ({} when the queue does not exist
    yet). Either being None means "unknown": nothing is decided this tick.

    For each ``active_work`` (oldest first) whose Work is absent from the
    queue, or admitted but still unclaimed:

    * a dispatcher run created after the request is still queued/running: wait;
    * no dispatcher run after the request, past a short grace: launch again
      (the launch itself was lost);
    * otherwise every such run finished without its Work being claimed. If
      fewer than ``1 + retries.infrastructure_per_head_failure`` runs did,
      launch the dispatcher again (it replays the same committed request, so
      the queue sees the identical Work); else give up and wait for a human.

    Returns (relaunch requests, staged records, report). No model is involved
    in deciding; a relaunch is an ordinary dispatcher run.
    """
    from datetime import timedelta
    from . import work
    relaunch: list[dict] = []
    staged: list[tuple[str, dict]] = []
    report: list[dict] = []
    if runs is None or queue_works is None:
        return relaunch, staged, report
    limit = 1 + ((policy.get("retries") or {}).get("infrastructure_per_head_failure", 2))
    iso = now.isoformat()
    pending = sorted(((k, c) for k, c in contributions.items() if c.get("active_work")),
                     key=lambda kc: kc[1]["active_work"]["requested_at"])
    for key, c in pending:
        aw = c["active_work"]
        if c["phase"] == "handoff":
            new = dict(c, active_work=None, updated_at=iso)
            contributions[key] = new
            schemas.validate("contribution", new)
            staged.append(("contributions", new))
            report.append({"contribution": c["contribution_id"], "task": aw["task"],
                           "decision": "cleared obsolete Work at handoff"})
            continue
        state = queue_works.get(work.graph_id(aw["dedupe_key"]))
        if state not in (None, "available", "completed", "cancelled"):
            continue      # a live Claim is resolved by the worker outcome or deadline
        requested = datetime.fromisoformat(aw["requested_at"])
        after = [r for r in runs if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= requested]
        entry = {"contribution": c["contribution_id"], "task": aw["task"], "queue_state": state,
                 "dispatcher_runs": [r["id"] for r in after]}
        if state in ("completed", "cancelled"):
            # Work graphs are immutable and terminal. Reusing the same graph
            # can only fail. Allocate a new revision for a bounded automatic
            # retry, or park the contribution so it cannot block the queue.
            attempt = aw.get("attempt", 1)
            if attempt < limit:
                revision = c["revision"] + 1
                fresh_aw = dict(aw, revision=revision, attempt=attempt + 1,
                                dedupe_key=f"{c['contribution_id']}@{revision}:{aw['task']}",
                                requested_at=iso,
                                deadline_at=(now + timedelta(hours=controller.WORK_DEADLINE_HOURS)).isoformat(),
                                dispatched_run_id=None)
                new = dict(c, revision=revision, activity="agent_running", active_work=fresh_aw,
                           pending_human_action=None, updated_at=iso)
                contributions[key] = new
                schemas.validate("contribution", new)
                staged.extend([("contributions", new),
                               ("events", lifecycle._event(c, new, "terminal_work_retry", "observation",
                                                           f"queue-{state}-{attempt + 1}", iso, True))])
                relaunch.append({"type": "relaunch_dispatcher", "contribution_id": new["contribution_id"]})
                report.append(entry | {"decision": f"new revision for terminal Work, attempt {attempt + 1} of {limit}"})
            else:
                new = dict(c, phase="parked", activity="idle", active_work=None, pending_human_action=None,
                           parked_reason=f"automatic worker retries exhausted after terminal queue state {state}",
                           updated_at=iso)
                contributions[key] = new
                schemas.validate("contribution", new)
                staged.extend([("contributions", new),
                               ("events", lifecycle._event(c, new, "worker_retries_exhausted", "observation",
                                                           f"queue-{state}", iso, True))])
                report.append(entry | {"decision": "parked: automatic worker retries exhausted"})
            continue
        if any(r.get("status") != "completed" for r in after):
            report.append(entry | {"decision": "dispatcher running"})
            continue
        latest = max(after, key=lambda r: r["created_at"], default=None)
        if latest is not None and str(latest["id"]) != str(aw.get("dispatched_run_id")):
            c = dict(c, active_work=dict(aw, dispatched_run_id=str(latest["id"])))
            contributions[key] = c
            staged.append(("contributions", c))
        if not after:
            if now - requested < timedelta(minutes=DISPATCH_LAUNCH_GRACE_MINUTES):
                report.append(entry | {"decision": "waiting for the dispatcher to start"})
                continue
            relaunch.append({"type": "relaunch_dispatcher", "contribution_id": c["contribution_id"]})
            report.append(entry | {"decision": "relaunch: no dispatcher run"})
            continue
        # Every finished dispatcher run since the request left the Work unclaimed.
        if len(after) < limit:
            relaunch.append({"type": "relaunch_dispatcher", "contribution_id": c["contribution_id"]})
            report.append(entry | {"decision": f"relaunch: dispatch attempt {len(after) + 1} of {limit}"})
            continue
        new = dict(c, active_work=None, activity="waiting_human", updated_at=iso,
                   pending_human_action={"kind": "dispatch_failed", "requested_at": iso,
                                         "reminded_at": None, "escalated_at": None})
        contributions[key] = new
        staged.append(("contributions", new))
        report.append(entry | {"decision": "dispatch failed; waiting for a human"})
    return relaunch[: max(1, policy["concurrency"]["coding_workers"])], staged, report


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
    new["active_work"] = None          # any outcome ends the requested task
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
    if outcome.get("status") != "investigation" and art \
            and all(k in art for k in ("work_id", "claim_id", "artifact_id", "name", "digest", "run_id")):
        new["proposal_artifact"] = {k: art[k] for k in ("work_id", "claim_id", "artifact_id", "name",
                                                        "digest", "run_id")} | {
            "result_commit": art.get("result_commit"), "outcome": outcome.get("status")}
    op = outcome.get("operation")
    if op:
        staged.append(("operations", op))
        new["publication_operation_id"] = op["operation_id"]
    status = outcome.get("status")
    if status in ("published", "uncertain") and op:
        changed_files = (op.get("proposed") or {}).get("changed_files") or []
        if changed_files:
            new["scope_paths"] = list(dict.fromkeys((new.get("scope_paths") or []) + changed_files))
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
        if fclass != "stale":
            # A failed immutable Work graph cannot be submitted again. A new
            # repair attempt gets a new revision and therefore a new graph ID.
            new["revision"] += 1
            new["clean_head_sha"] = None
    elif status == "investigation":
        # Investigation artifacts are evidence, never patch proposals. Keeping
        # one in proposal_artifact would make base-branch CI look like patch CI
        # and suppress the first development task.
        new["proposal_artifact"] = None
        # The dossier is recorded as evidence. Its validated decision either
        # enters automatic provisioning or parks without launching a writer.
        dossier = outcome.get("dossier")
        eid = None
        if isinstance(dossier, dict):
            eid = safe_id(f"dossier-{new['contribution_id'].replace('/', '--')}-r{new['revision']}")
            ev = {"schema_version": 1, "evidence_id": eid, "contribution_id": new["contribution_id"],
                  "kind": "dossier", "policy_version": (policy or {}).get("policy_version", "unknown"),
                  "collected_at": now,
                  "summary": str((outcome.get("proposal") or {}).get("diagnosis") or "investigation dossier")[:8000],
                  "limitations": [], "data": dossier,
                  "digests": {"artifact": (outcome.get("artifact") or {}).get("digest") or ""}}
            staged.append(("evidence", ev))
        new["dossier_evidence_id"] = eid
        refresh = new.get("refresh")
        decision = (dossier.get("proposal") or {}).get("decision") if isinstance(dossier, dict) else None
        if not eid:
            new["activity"] = "waiting_human"
            new["pending_human_action"] = {"kind": "investigation_without_dossier", "requested_at": now,
                                           "reminded_at": None, "escalated_at": None}
        elif decision not in ("develop", "park"):
            new["phase"] = "investigation"
            new["activity"] = "idle"
            new["pending_human_action"] = None
            new["revision"] += 1
            staged.append(("events", lifecycle._event(rec, new, "dossier_contract_stale", "observation",
                                                       str(worker_run_id or eid), now, True)))
        elif decision == "park":
            new["previous_phase"] = (refresh or {}).get("from_phase") or new["phase"]
            new["phase"] = "parked"
            new["activity"] = "idle"
            new["parked_reason"] = dossier["proposal"]["rationale"][:2000]
            new["pending_human_action"] = None
            new["refresh"] = None
            new["revision"] += 1
            staged.append(("events", lifecycle._event(rec, new, "dossier_parked", "observation",
                                                       str(worker_run_id or eid), now, True)))
        else:
            new["activity"] = "fix_needed" if refresh else "idle"
            new["phase"] = "development" if refresh else "provisioning"
            new["admission_class"] = dossier["proposal"]["admission_class"]
            new["scope_paths"] = list(dossier["proposal"]["allowed_paths"])
            new["scope_coverage_complete"] = True
            new["pending_human_action"] = None
            new["refresh"] = None
            new["revision"] += 1
            kind = "dossier_refreshed" if refresh else "dossier_develop"
            staged.append(("events", lifecycle._event(rec, new, kind, "observation",
                                                       str(worker_run_id or eid), now, True)))
    new["updated_at"] = now
    staged.append(("contributions", new))
    return new, staged


def tick(api: collect.Api, snap: Snapshot, *, policy: dict, now: datetime,
         publications: list[dict], pressure: capacity.Pressure,
         issues: list[dict] | None = None, comments: list[dict] | None = None,
         verified_prs: dict[str, dict] | None = None, acceptances: dict[int, int] | None = None,
         observe: bool = True, dispatcher_runs: list[dict] | None = None,
         queue_works: dict[str, str] | None = None, users: dict | None = None,
         provisioning: dict | None = None, tracking_issues: dict | None = None,
         upstream_snapshots: dict | None = None, provisions: list[dict] | None = None,
         development_prs: list[dict] | None = None) -> TickOutput:
    out = TickOutput()
    iso = now.isoformat()
    contributions = dict(snap.contributions)
    by_cid = {c["contribution_id"]: k for k, c in contributions.items()}

    # Trusted same-fork development PR receipts are independently read back.
    dev_pr_report = []
    for receipt in development_prs or []:
        cid = receipt.get("contribution_id")
        if cid not in by_cid:
            continue
        key = by_cid[cid]
        c = contributions[key]
        op = snap.operations.get(receipt.get("operation_id"))
        if not op or op["kind"] not in ("dev_pr_create", "dev_pr_update") or op["status"] not in recovery.OPEN \
                or c["phase"] != "development" or c.get("active_operation_id") != op["operation_id"] \
                or c["revision"] != receipt.get("revision") or receipt.get("status") != "published":
            continue
        if receipt.get("repository") != op["target"]["repository"] \
                or receipt.get("repository_id") != op["target"]["repository_id"] \
                or receipt.get("head_sha") != op["target"]["expected_head"]:
            dev_pr_report.append({"contribution": cid, "status": "receipt mismatch"})
            continue
        try:
            pr = api.get(f"/repos/{receipt['repository']}/pulls/{int(receipt['pr_number'])}")
        except (ValueError, KeyError, collect.CollectError):
            dev_pr_report.append({"contribution": cid, "status": "readback unavailable"})
            continue
        marker = op["proposed"].get("marker")
        body_ok = (marker in (pr.get("body") or "") if op["kind"] == "dev_pr_create"
                   else "<!-- upstreaming-development:" in (pr.get("body") or ""))
        if pr.get("id") != receipt.get("pr_id") or pr.get("state") != "open" \
                or not body_ok \
                or (pr.get("head") or {}).get("sha") != op["target"]["expected_head"] \
                or (pr.get("head") or {}).get("ref") != "riscv64" \
                or (pr.get("head") or {}).get("repo", {}).get("id") != op["target"]["repository_id"] \
                or (pr.get("base") or {}).get("ref") != c["upstream"]["base_ref"]:
            dev_pr_report.append({"contribution": cid, "status": "PR readback mismatch"})
            continue
        new_op = recovery.record_discovery(op, "confirmed", f"development PR {pr['number']} verified", iso)
        new_op["external_ids"].update({"pr_id": int(pr["id"]), "pr_number": int(pr["number"]),
                                       "development_pr_run_id": str(receipt["development_pr_run_id"])})
        fork = dict(c["fork"], pr_number=int(pr["number"]))
        new = dict(c, fork=fork, active_operation_id=None, activity="waiting_ci", updated_at=iso)
        schemas.validate("contribution", new)
        contributions[key] = new
        snap.operations[op["operation_id"]] = new_op
        out.staged.extend([("operations", new_op), ("contributions", new),
                           ("events", lifecycle._event(c, new, "development_pr_created", "observation",
                                                       op["operation_id"], iso, False))])
        dev_pr_report.append({"contribution": cid, "status": "confirmed", "pr_number": pr["number"]})
    out.report["development_prs"] = dev_pr_report

    # Verified administrative provisioning receipts are separate from model
    # artifact Results. Re-read the actual fork/ref before advancing state.
    provision_report = []
    for receipt in provisions or []:
        cid = receipt.get("contribution_id")
        if cid not in by_cid:
            continue
        key = by_cid[cid]
        c = contributions[key]
        op = snap.operations.get(receipt.get("operation_id"))
        if not op or op["kind"] != "fork_provision" or op["status"] not in recovery.OPEN \
                or c["phase"] != "provisioning" or c.get("active_operation_id") != op["operation_id"] \
                or c["revision"] != receipt.get("revision") or receipt.get("status") != "provisioned":
            continue
        if receipt.get("fork") != op["target"]["repository"] \
                or receipt.get("upstream_id") != c["upstream"]["repository_id"] \
                or receipt.get("base_sha") != c["upstream"]["base_sha"] \
                or receipt.get("actions_read_only") is not True:
            provision_report.append({"contribution": cid, "status": "receipt mismatch"})
            continue
        try:
            repo = collect.repository(api, receipt["fork"])
            head = collect.branch_head(api, receipt["fork"], "riscv64")
        except collect.CollectError:
            provision_report.append({"contribution": cid, "status": "readback unavailable"})
            continue
        expected = op["target"].get("expected_head") or op["target"]["base_sha"]
        if not head or head["head"] != receipt.get("head_sha") or head["head"] != expected \
                or repo["id"] != receipt.get("fork_id") or repo.get("parent_id") != c["upstream"]["repository_id"]:
            provision_report.append({"contribution": cid, "status": "fork identity/ref mismatch"})
            continue
        new_op = recovery.record_discovery(op, "confirmed", "fork/source identity, branch and trusted setup receipt verified", iso)
        if receipt.get("provision_run_id"):
            new_op["external_ids"]["provision_run_id"] = str(receipt["provision_run_id"])
        if receipt.get("provision_artifact_id"):
            new_op["external_ids"]["provision_artifact_id"] = int(receipt["provision_artifact_id"])
        new = dict(c, fork={"repository_id": repo["id"], "name": repo["full_name"], "head_ref": "riscv64",
                            "head_sha": head["head"], "pr_number": None}, phase="development", activity="idle",
                   active_operation_id=None, pending_human_action=None, revision=c["revision"] + 1, updated_at=iso)
        schemas.validate("contribution", new)
        contributions[key] = new
        snap.operations[op["operation_id"]] = new_op
        out.staged.extend([("operations", new_op), ("contributions", new),
                           ("events", lifecycle._event(c, new, "fork_provisioned", "observation", op["operation_id"], iso, True))])
        provision_report.append({"contribution": cid, "status": "provisioned"})
    out.report["provisions"] = provision_report

    # 1. Publication outcomes from finished workers. A development reset or an
    # infrastructure retry can leave multiple artifacts for the same immutable
    # contribution revision. Fold only the newest artifact; never let an older
    # outcome overwrite or crash a later verified Result.
    latest: dict[tuple[str, int], tuple[tuple[int, int], dict]] = {}
    superseded = []
    for pub in publications:
        task = pub.get("task") or {}
        cid, revision = task.get("contribution_id"), task.get("revision")
        if not isinstance(cid, str) or not isinstance(revision, int):
            continue
        def numeric(value):
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0
        rank = (numeric(pub.get("publication_artifact_id")), numeric(pub.get("worker_run_id")))
        key = (cid, revision)
        prior = latest.get(key)
        if prior is None or rank > prior[0]:
            if prior is not None:
                superseded.append(prior[1])
            latest[key] = (rank, pub)
        else:
            superseded.append(pub)
    publications = [item[1] for item in latest.values()]
    pubs_report = [{"contribution": (pub.get("task") or {}).get("contribution_id"),
                    "ignored": "superseded publication artifact"} for pub in superseded]
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
        task_revision = pub.get("task", {}).get("revision")
        if rec["phase"] in ("handoff", "upstream_review") and pub.get("status") != "published" \
                and isinstance(task_revision, int) and task_revision <= rec["revision"]:
            out.staged.append(("contributions", rec))
            pubs_report.append({"contribution": cid, "ignored": "superseded by exact-head handoff"})
            continue
        if task_revision != rec["revision"] and pub.get("status") != "published":
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

    # 1b. Requested tasks that never produced an outcome: give up, ask a human.
    timed_out = []
    for key, c in list(contributions.items()):
        aw = c.get("active_work")
        if aw and datetime.fromisoformat(aw["deadline_at"]) <= now:
            new = dict(c, active_work=None, activity="waiting_human", updated_at=iso,
                       pending_human_action={"kind": "task_without_outcome", "requested_at": iso,
                                             "reminded_at": None, "escalated_at": None})
            contributions[key] = new
            out.staged.append(("contributions", new))
            timed_out.append({"contribution": c["contribution_id"], "task": aw["task"],
                              "requested_at": aw["requested_at"]})
    out.report["timed_out_work"] = timed_out

    # 1c. Requested tasks whose dispatch never reached the queue: relaunch the
    # dispatcher (bounded), then wait for a human.
    relaunch, staged, rep = dispatch_recovery(contributions, runs=dispatcher_runs, queue_works=queue_works,
                                              now=now, policy=policy)
    out.staged.extend(staged)
    out.report["dispatch_recovery"] = rep
    out.report["dispatch_relaunch"] = relaunch

    # 1d. Carry durable review constraints across head changes. Older records
    # predate pending_feedback_evidence_ids, so recover their already-ingested
    # human relay evidence before selecting another repair.
    for key, c in list(contributions.items()):
        feedback_ids = sorted(
            e["evidence_id"] for e in snap.evidence.values()
            if e.get("kind") == "human_relay" and e.get("contribution_id") == c["contribution_id"])
        if feedback_ids and "pending_feedback_evidence_ids" not in c \
                and c["phase"] in {"development", "handoff", "upstream_review"}:
            c = dict(c, pending_feedback_evidence_ids=feedback_ids[-64:])
            contributions[key] = c
            out.staged.append(("contributions", c))

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
        # Recovery is evaluated before live CI. If CI accepts the current head
        # in this same tick, do not launch a dispatcher for the now-obsolete
        # retry request.
        out.report["dispatch_relaunch"] = [
            item for item in out.report["dispatch_relaunch"]
            if (contributions[by_cid[item["contribution_id"]]].get("active_work") is not None
                and contributions[by_cid[item["contribution_id"]]]["phase"] != "handoff")]

    # 3. Commands, intake and work selection (controller).
    res = controller.tick(contributions=contributions, operations=snap.operations, consumed=snap.consumed,
                          projects=snap.projects, policy=policy,
                          inputs=controller.Inputs(now=now, issues=issues or [], comments=comments or [],
                                                   pressure=pressure, verified_prs=verified_prs or {},
                                                   users=users or {}, provisioning=provisioning or {},
                                                   tracking_issues=tracking_issues or {},
                                                   upstream_snapshots=upstream_snapshots or {},
                                                   acceptances=acceptances or {}))
    out.staged.extend(res.staged)
    out.report["controller"] = res.report
    out.report["requested_effects"] = res.requested_effects
    out.report["provision_requests"] = res.report["provision_requests"]
    out.report["dev_pr_requests"] = res.report["dev_pr_requests"]
    # 4. Publish-only retries due now (infrastructure failures; no model call).
    retries = []
    for c in contributions.values():
        pp = c.get("pending_publication")
        if pp and not pp.get("exhausted") and not c.get("paused") \
                and c["phase"] in lifecycle.WRITE_PHASES | {"investigation"} \
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
