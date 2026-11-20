# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""One controller tick (plan sections 5.3 and 9).

``tick`` is deterministic and side-effect free: it takes loaded state, the
policy and an ``Inputs`` snapshot collected read-only by ``collect.py``, and
returns staged state changes plus a list of *requested* effects (native Work
submissions, notifications). Nothing is executed here.

* In read-only mode (``policy.read_only``, the default) requested effects are
  reported only; trusted code, not a prompt, disables every publisher.
* No model call happens on an idle tick: work is selected only when there is
  an actionable investigation, failure, or feedback item.
* A tick never waits for workers or builds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import capacity, collect, intake, lifecycle, recovery, schemas
from .commands import Command, URGENT
from .common import INTAKE_LABEL, contribution_file_id


@dataclass
class Inputs:
    now: datetime
    issues: list[dict] = field(default_factory=list)          # intake issues, freshly fetched
    tracking_issues: dict[int, dict] = field(default_factory=dict)  # every live issue's fresh description
    upstream_snapshots: dict[str, dict] = field(default_factory=dict)  # verified source ID / initial base
    comments: list[dict] = field(default_factory=list)        # {"issue_number", "comment", "event_body"}
    pressure: capacity.Pressure | None = None
    verified_prs: dict[str, dict] = field(default_factory=dict)  # url -> verified PR resource
    users: dict[str, dict | None] = field(default_factory=dict)  # login -> {"id","login"} or None
    provisioning: dict[str, dict] = field(default_factory=dict)  # contribution -> verify_provisioning()
    resolution_evidence: dict[str, dict] = field(default_factory=dict)
    acceptances: dict[int, int] = field(default_factory=dict)     # issue id -> accepting actor id
    requests_today: dict[int, int] = field(default_factory=dict)  # actor id -> count


@dataclass
class TickResult:
    staged: list[tuple[str, dict]] = field(default_factory=list)   # (kind, record)
    requested_effects: list[dict] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)

    def stage(self, kind: str, record: dict) -> None:
        self.staged.append((kind, record))


def _iso(t: datetime) -> str:
    return t.isoformat()


def _actionable(c: dict) -> str | None:
    """What a coding agent could usefully do now, or None (no AI on idle)."""
    if c["paused"] or c.get("blocked_reason") or c["phase"] in lifecycle.TERMINAL | {"parked"}:
        return None
    if c.get("pending_publication"):
        return None   # a delivered proposal is still being published; never re-run the agent for it
    if c.get("active_work"):
        return None   # a task was already requested for this contribution; wait for its outcome
    if c.get("active_operation_id") or c["activity"] in ("agent_running", "waiting_human",
                                                          "waiting_ci", "waiting_capacity"):
        return None
    if c["phase"] == "upstream_review" and c["activity"] == "fix_needed":
        return "upstream_revision"
    if c["phase"] == "development" and c["activity"] == "fix_needed":
        return "development_repair"
    if c["phase"] in ("queued", "investigation") and c["activity"] == "idle":
        return "investigation"
    if c["phase"] == "development" and c["activity"] == "idle" and not c.get("last_ci_evidence_id"):
        return "development_patch"
    return None


# A requested task that produced no outcome by then is given up on: the
# contribution waits for a human instead of being retried blindly.
WORK_DEADLINE_HOURS = 6

PRIORITY = {"upstream_revision": 0, "development_repair": 1, "development_patch": 2,
            "investigation": 3}
WRITE_KINDS = {"upstream_revision", "development_repair", "development_patch"}


def tick(*, contributions: dict[str, dict], operations: dict[str, dict], consumed: dict[int, dict],
         projects: dict[str, dict], policy: dict, inputs: Inputs) -> TickResult:
    res = TickResult()
    now = _iso(inputs.now)
    by_id = {c["contribution_id"]: c for c in contributions.values()}
    rep = res.report
    rep.update({"at": now, "policy_version": policy["policy_version"],
                "read_only": policy["read_only"], "commands": [], "intake": [],
                "operations": [], "selected": [], "deferred": [], "alerts": []})

    # 1. Intake first, so a command posted on a brand-new request applies to it.
    parked = [p["upstream"]["full_name"] for p in projects.values() if p.get("parked")]
    active = {c["upstream"]["full_name"]: c["contribution_id"] for c in by_id.values()
              if c["phase"] not in lifecycle.TERMINAL}
    known = [c["tracking_issue"]["id"] for c in by_id.values()]
    for issue in inputs.issues:
        if issue.get("id") in known:
            continue      # already a contribution; the form is not re-read
        try:
            req = intake.parse_request(issue, policy)
        except intake.IntakeError as e:
            rep["intake"].append({"issue": issue["number"], "decision": "invalid", "detail": str(e)})
            continue
        decision, detail = intake.admission_decision(
            req, accepted_by=inputs.acceptances.get(req.issue_id), policy=policy,
            active_by_upstream=active, parked_upstreams=parked, known_issue_ids=known,
            requests_today_by_actor=inputs.requests_today.get(req.actor_id, 0))
        rep["intake"].append({"issue": req.issue_number, "decision": decision, "detail": detail})
        if decision != "accept":
            continue
        project_id = contribution_file_id(req.upstream.replace("/", "--").lower())
        cid = f"{project_id}/{req.issue_number}"
        rec = lifecycle.new_contribution(
            contribution_id=cid, project_id=project_id,
            issue={"id": req.issue_id, "number": req.issue_number}, upstream=req.upstream,
            distributions=list(req.distributions), base_ref=req.target_branch,
            policy_id=policy["policy_version"], now=now)
        by_id[cid] = rec
        active[req.upstream] = cid
        known.append(req.issue_id)
        res.stage("contributions", rec)
        res.stage("events", {"schema_version": 1, "contribution_id": cid, "sequence": 0, "at": now,
                             "kind": "intake:accepted", "from": {}, "to": {"phase": "queued"},
                             "cause": {"type": "observation", "id": f"issue-{req.issue_id}"},
                             "revision_bumped": False})
        proj = projects.get(project_id) or {
            "schema_version": 1, "project_id": project_id,
            "upstream": {"repository_id": None, "full_name": req.upstream},
            "distributions": list(req.distributions), "parked": False, "parked_reason": None,
            "contribution_ids": [], "active_contribution_id": None, "prerequisites": [],
            "dossier_evidence_id": None, "release_observation": None, "updated_at": now}
        proj = dict(proj, contribution_ids=proj["contribution_ids"] + [cid],
                    active_contribution_id=cid, updated_at=now)
        projects[project_id] = proj
        res.stage("projects", proj)

    # Removing the intake label cancels only an accepted request that has not
    # requested any Work yet. Once active_work exists, explicit lifecycle
    # commands are required so an unlabeled event cannot silently stop work.
    for cid, c in list(by_id.items()):
        issue = inputs.tracking_issues.get(c["tracking_issue"]["number"])
        labels = {label.get("name") if isinstance(label, dict) else label
                  for label in (issue or {}).get("labels", [])}
        unprocessed = c["phase"] == "queued" and c["activity"] == "idle" \
            and not c.get("active_work") and not c.get("dossier_evidence_id") and not c.get("fork")
        if issue is None or INTAKE_LABEL in labels or not unprocessed:
            continue
        changed = dict(c, phase="abandoned", activity="idle",
                       terminal_reason=f"{INTAKE_LABEL} label removed before Work admission", updated_at=now)
        schemas.validate("contribution", changed)
        by_id[cid] = changed
        active.pop(c["upstream"]["full_name"], None)
        res.stage("contributions", changed)
        res.stage("events", lifecycle._event(c, changed, "intake:label_removed", "observation",
                                              f"issue-{c['tracking_issue']['id']}", now, False))
        project = projects.get(c["project_id"])
        if project and project.get("active_contribution_id") == cid:
            project = dict(project, active_contribution_id=None, updated_at=now)
            projects[c["project_id"]] = project
            res.stage("projects", project)
        rep["intake"].append({"issue": c["tracking_issue"]["number"], "decision": "cancelled",
                              "detail": f"{INTAKE_LABEL} label removed before Work admission"})

    # Bind initially unspecified source identities/bases from trusted API data,
    # never from the model's dossier. Already-bound bases remain immutable.
    source_blocked = set()
    for cid, c in list(by_id.items()):
        snapshot = inputs.upstream_snapshots.get(c["upstream"]["full_name"])
        if snapshot is None:
            continue
        if snapshot.get("error"):
            source_blocked.add(cid)
            rep["deferred"].append({"contribution": cid, "why": "source verification unavailable"})
            continue
        current = c["upstream"].get("repository_id")
        if current is not None and current != snapshot["repository_id"]:
            source_blocked.add(cid)
            changed = dict(c, blocked_reason="upstream repository identity changed", activity="waiting_human", updated_at=now)
            by_id[cid] = changed
            res.stage("contributions", changed)
            continue
        updated = dict(c["upstream"])
        for key in ("repository_id", "base_ref", "base_sha"):
            if updated.get(key) is None:
                updated[key] = snapshot[key]
        if updated != c["upstream"]:
            changed = dict(c, upstream=updated, updated_at=now)
            by_id[cid] = changed
            res.stage("contributions", changed)

    # 2. Authorized commands, urgent stops first, all before any work is selected.
    decisions = []
    for item in inputs.comments:
        d = intake.accept_command(comment=item["comment"], issue_number=item["issue_number"],
                                  event_body=item.get("event_body"), policy=policy,
                                  consumed=consumed, now=now)
        decisions.append(d)
    decisions.sort(key=lambda d: 0 if d.command and d.command.verb in URGENT else 1)
    for d in decisions:
        if d.receipt["comment_id"] in consumed and not d.accepted:
            rep["commands"].append({"comment": d.receipt["comment_id"], "result": d.reason})
            continue
        receipt = dict(d.receipt)
        if d.accepted:
            receipt = _apply(d.command, receipt, by_id, operations, inputs, res, now)
        consumed[receipt["comment_id"]] = receipt
        res.stage("commands", receipt)
        rep["commands"].append({"comment": receipt["comment_id"], "result": receipt["result"],
                                "reason": receipt.get("reason")})

    # 3. Uncertain operations before any replacement.
    blocked_by_op: set[str] = set()
    for op in operations.values():
        if op["status"] in recovery.OPEN:
            blocked_by_op.add(op["contribution_id"])
            due = recovery.next_discovery_at(op, policy)
            rep["operations"].append({"id": op["operation_id"], "status": op["status"],
                                      "next_discovery": due.isoformat() if due else None})
            for a in recovery.alerts(op, inputs.now):
                rep["alerts"].append({"operation": op["operation_id"], "alert": a})

    # Provisioning is a trusted administrative workflow, not a model task.
    # Persist its normal operation intent before dispatch, with no second queue.
    res.report["provision_requests"] = []
    for cid, c in list(by_id.items()):
        if len(res.report["provision_requests"]) >= 1:
            break
        if c["phase"] != "provisioning" or c.get("paused") or c.get("blocked_reason") \
                or c.get("active_operation_id") or cid in source_blocked:
            continue
        if (c.get("pending_human_action") or {}).get("kind") not in (None, "provision_fork"):
            continue
        if not c.get("dossier_evidence_id") or not c.get("admission_class") \
                or not c.get("scope_paths") \
                or not c["upstream"].get("repository_id") or not c["upstream"].get("base_sha"):
            rep["deferred"].append({"contribution": cid, "why": "provisioning prerequisites missing"})
            continue
        ok, why = capacity.admit_expensive(inputs.pressure or capacity.Pressure(ok=False, reason="no usage data"),
                                           reserved=capacity.reserved_jobs(operations.values()), estimated_jobs=1, policy=policy)
        if not ok:
            rep["deferred"].append({"contribution": cid, "why": why})
            continue
        fork = c.get("fork") or {}
        op = recovery.plan(contribution_id=cid, revision=c["revision"], kind="fork_provision",
                           policy_version=policy["policy_version"], reason_ids=[c["dossier_evidence_id"]],
                           target={"repository": "riseproject-upstreaming/" + c["upstream"]["full_name"].split('/', 1)[1],
                                   "repository_id": fork.get("repository_id"), "ref": "riscv64",
                                   "expected_head": fork.get("head_sha"), "base_sha": c["upstream"]["base_sha"]},
                           proposed={"commit": c["upstream"]["base_sha"], "marker": f"provision:{cid}:{c['revision']}"},
                           capacity={"selector": "ubuntu-24.04-riscv", "estimated_jobs": 1,
                                     "estimated_minutes": 10, "observed_run_ids": []}, now=now)
        if op["operation_id"] in operations:
            rep["deferred"].append({"contribution": cid, "why": "existing provisioning operation requires reconciliation"})
            continue
        res.stage("operations", op)
        res.stage("contributions", dict(c, active_operation_id=op["operation_id"], activity="waiting_capacity", updated_at=now))
        by_id[cid] = dict(c, active_operation_id=op["operation_id"], activity="waiting_capacity", updated_at=now)
        res.report["provision_requests"].append({"operation_id": op["operation_id"], "contribution_id": cid})

    # A published development head gets a same-fork development PR before CI
    # observation. Persist intent first; the trusted workflow creates/discovers
    # exactly riscv64 -> the frozen upstream base ref and returns a receipt.
    res.report["dev_pr_requests"] = []
    for cid, c in list(by_id.items()):
        if len(res.report["dev_pr_requests"]) >= 1:
            break
        fork = c.get("fork") or {}
        artifact = c.get("proposal_artifact") or {}
        pubop = operations.get(c.get("publication_operation_id"))
        if c["phase"] != "development" or c.get("paused") or c.get("blocked_reason") \
                or c.get("active_operation_id") or fork.get("pr_number") is not None \
                or not fork.get("repository_id") or not fork.get("head_sha") \
                or fork.get("head_sha") == c["upstream"].get("base_sha") \
                or artifact.get("outcome") != "published" or not artifact.get("result_commit") \
                or not c.get("dossier_evidence_id") or not c.get("scope_paths") \
                or not pubop or pubop.get("status") != "confirmed":
            continue
        marker = f"<!-- upstreaming-development:{cid}:r{c['revision']}:{fork['head_sha']} -->"
        op = recovery.plan(contribution_id=cid, revision=c["revision"], kind="dev_pr_create",
                           policy_version=policy["policy_version"],
                           reason_ids=[c["dossier_evidence_id"], str(artifact["result_commit"])],
                           target={"repository": fork["name"], "repository_id": fork["repository_id"],
                                   "ref": "riscv64", "expected_head": fork["head_sha"],
                                   "base_sha": c["upstream"]["base_sha"]},
                           proposed={"marker": marker, "content_digest": artifact["digest"]}, now=now)
        if op["operation_id"] in operations:
            continue
        res.stage("operations", op)
        changed = dict(c, active_operation_id=op["operation_id"], activity="waiting_capacity", updated_at=now)
        by_id[cid] = changed
        res.stage("contributions", changed)
        res.report["dev_pr_requests"].append({"operation_id": op["operation_id"], "contribution_id": cid})

    # Bootstrap CI once for an already recorded PR. This separate operation is
    # needed when GitHub registered no inherited workflows at PR creation time.
    for cid, c in list(by_id.items()):
        if len(res.report["dev_pr_requests"]) >= 1:
            break
        fork = c.get("fork") or {}
        artifact = c.get("proposal_artifact") or {}
        if c["phase"] != "development" or c.get("paused") or c.get("blocked_reason") \
                or c.get("active_operation_id") or fork.get("pr_number") is None \
                or c.get("last_ci_evidence_id") or artifact.get("outcome") != "published":
            continue
        created_at_head = any(op["contribution_id"] == cid and op["kind"] == "dev_pr_create"
                              and op["status"] == "confirmed"
                              and op["target"].get("expected_head") == fork.get("head_sha")
                              for op in operations.values())
        if not created_at_head:
            continue  # later patch pushes already emit pull_request:synchronize
        reason = f"ci-bootstrap-event-v2:{fork['head_sha']}"
        prior = [op for op in operations.values() if op["contribution_id"] == cid \
                 and op["kind"] == "dev_pr_update" and reason in op["reason_ids"] \
                 and op["target"].get("expected_head") == fork.get("head_sha")]
        if any(op["status"] in recovery.OPEN | {"confirmed"} for op in prior):
            continue
        op = recovery.plan(contribution_id=cid, revision=c["revision"], kind="dev_pr_update",
                           policy_version=policy["policy_version"], reason_ids=[reason],
                           target={"repository": fork["name"], "repository_id": fork["repository_id"],
                                   "ref": "riscv64", "expected_head": fork["head_sha"],
                                   "base_sha": c["upstream"]["base_sha"]},
                           proposed={"marker": f"ci-bootstrap:{cid}:r{c['revision']}",
                                     "content_digest": artifact["digest"]}, now=now)
        res.stage("operations", op)
        changed = dict(c, active_operation_id=op["operation_id"], activity="waiting_capacity", updated_at=now)
        by_id[cid] = changed
        res.stage("contributions", changed)
        res.report["dev_pr_requests"].append({"operation_id": op["operation_id"], "contribution_id": cid})

    # 8-10. Select bounded work, honouring capacity and one worker.
    candidates = []
    for c in by_id.values():
        if c["contribution_id"] in source_blocked:
            continue
        kind = _actionable(c)
        if kind is None:
            continue
        if c["contribution_id"] in blocked_by_op:
            rep["deferred"].append({"contribution": c["contribution_id"], "why": "uncertain operation"})
            continue
        if kind in WRITE_KINDS:
            why = lifecycle.write_admission(c)
            if why:
                rep["deferred"].append({"contribution": c["contribution_id"], "why": why})
                continue
        candidates.append((PRIORITY[kind], c["updated_at"], kind, c))
    candidates.sort(key=lambda x: (x[0], x[1]))
    slots = policy["concurrency"]["coding_workers"] - sum(
        1 for c in by_id.values() if c["activity"] == "agent_running" or c.get("active_work"))
    pressure = inputs.pressure
    for _p, _t, kind, c in candidates:
        if slots <= 0:
            rep["deferred"].append({"contribution": c["contribution_id"], "why": "no worker slot"})
            continue
        if kind in WRITE_KINDS:
            ok, why = capacity.admit_expensive(
                pressure or capacity.Pressure(ok=False, reason="no usage data"),
                reserved=capacity.reserved_jobs(operations.values()), estimated_jobs=1, policy=policy)
            if not ok:
                rep["deferred"].append({"contribution": c["contribution_id"], "why": why})
                continue
        slots -= 1
        reason_ids = []
        if kind in ("development_repair", "upstream_revision"):
            reason_ids = list(dict.fromkeys(
                (c.get("pending_feedback_evidence_ids") or [])
                + ([c["last_ci_evidence_id"]] if c.get("last_ci_evidence_id") else [])
                + ([c["dossier_evidence_id"]] if c.get("dossier_evidence_id") else [])))
        if not reason_ids and c.get("dossier_evidence_id"):
            reason_ids = [c["dossier_evidence_id"]]
        work = {
            "type": "submit_work",
            "dedupe_key": f"{c['contribution_id']}@{c['revision']}:{kind}",
            "contribution_id": c["contribution_id"],
            "revision": c["revision"],
            "expected_head": (c.get("fork") or {}).get("head_sha"),
            "task": kind,
            "reason_ids": reason_ids,
            "effect_contract": ({"kind": "none"} if kind == "investigation"
                                else {"kind": "fork_branch", "repository": (c.get("fork") or {}).get("name"),
                                      "ref": "riscv64"}),
        }
        res.requested_effects.append(work)
        rep["selected"].append({"contribution": c["contribution_id"], "task": kind})
        # Record the request in the same state commit, so the next tick does
        # not request it again. Cleared by the task's outcome or by timeout.
        from datetime import timedelta
        claimed = dict(c, activity="agent_running", updated_at=now, active_work={
            "dedupe_key": work["dedupe_key"], "task": kind, "revision": c["revision"], "attempt": 1,
            "requested_at": now,
            "deadline_at": (inputs.now + timedelta(hours=WORK_DEADLINE_HOURS)).isoformat(),
            "dispatched_run_id": None, "reason_ids": reason_ids})
        issue = inputs.tracking_issues.get(c["tracking_issue"]["number"]) or next(
            (i for i in inputs.issues if i["number"] == c["tracking_issue"]["number"]), None)
        if issue is not None:
            claimed["active_work"]["tracking_issue"] = collect.tracking_issue_context(issue, c["tracking_issue"])
        if kind == "investigation" and claimed["phase"] == "queued":
            claimed["phase"] = "investigation"
        by_id[c["contribution_id"]] = claimed
        res.stage("contributions", claimed)

    if policy["read_only"]:
        rep["note"] = "read-only: requested effects are reported, not executed"
    return res


def _apply(cmd: Command, receipt: dict, by_id: dict, operations: dict, inputs: Inputs,
           res: TickResult, now: str) -> dict:
    actor = receipt["actor"]
    if cmd.verb == "resolve-operation":
        op = operations.get(cmd.args["operation"])
        if op is None:
            return dict(receipt, result="rejected", reason="unknown operation")
        try:
            new = recovery.resolve(op, cmd, actor=actor, command_id=receipt["command_id"],
                                   evidence=inputs.resolution_evidence.get(cmd.args["evidence"]), now=now)
        except recovery.RecoveryError as e:
            return dict(receipt, result="rejected", reason=str(e))
        operations[op["operation_id"]] = new
        res.stage("operations", new)
        return receipt
    # The contribution is the one tracked by the issue the comment was posted on.
    rec = intake.contribution_for_issue(by_id.values(), receipt["issue_number"])
    if rec is None:
        return dict(receipt, result="rejected", reason="this issue tracks no contribution")
    if cmd.contribution is not None and cmd.contribution != rec["contribution_id"]:
        return dict(receipt, result="rejected",
                    reason=f"command names {cmd.contribution}, but this issue tracks {rec['contribution_id']}")
    receipt = dict(receipt, contribution_id=rec["contribution_id"],
                   revision=cmd.revision if cmd.revision is not None else rec["revision"])
    verified = inputs.verified_prs.get(cmd.args.get("url", "")) if cmd.verb == "register-upstream-pr" else None
    try:
        out = lifecycle.apply_command(rec, cmd, command_id=receipt["command_id"], actor=actor,
                                      now=now, verified_pr=verified,
                                      provisioning=inputs.provisioning.get(rec["contribution_id"]),
                                      backup_user=inputs.users.get(cmd.args.get("backup", "")))
    except lifecycle.TransitionError as e:
        return dict(receipt, result="rejected", reason=str(e))
    if not out.accepted:
        return dict(receipt, result="rejected", reason=out.reason)
    by_id[rec["contribution_id"]] = out.record
    res.stage("contributions", out.record)
    if out.event:
        res.stage("events", out.event)
    return receipt
