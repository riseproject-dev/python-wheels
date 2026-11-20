# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Turn live CI and branch state into lifecycle changes (plan sections 9, 14.3).

Deterministic, no model. For each contribution in a phase that watches CI:

* read the fork's current ``riscv64`` head (a manual or pipeline push shows
  up as a head change, which bumps the revision);
* resolve uncertain branch operations by discovery;
* read the CI snapshot for the exact head and evaluate it against the
  dossier's required jobs and expected wheels;
* record an evidence record and move ``activity`` to ``waiting_ci``,
  ``fix_needed`` (failed), ``waiting_human`` (approval/access) or ``idle``
  with ``last_ci_evidence_id`` set (passed).

Returns staged records for the state publisher. Never writes remotely.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import ci_evidence, collect, lifecycle, recovery, schemas
from .common import DEV_REF, safe_id

WATCH_PHASES = {"development", "handoff", "upstream_review"}


@dataclass
class Observation:
    staged: list[tuple[str, dict]] = field(default_factory=list)
    report: list[dict] = field(default_factory=list)


def _evidence_id(repo_id: int, run: dict) -> str:
    return safe_id(f"ci-{repo_id}-{run['id']}-{run['run_attempt']}")


def contract_for(record: dict, contracts: dict[str, dict]) -> dict:
    """The dossier target contract: required job patterns + expected wheels."""
    c = contracts.get(record.get("target_contract_id") or "") or {}
    data = c.get("data") or {}
    return {"required_job_patterns": data.get("required_job_patterns") or ["riscv64"],
            "expected_wheels": data.get("expected_wheels") or [],
            "require_wheel_artifact": data.get("require_wheel_artifact", True),
            "required_runner_label": data.get("required_runner_label")}


def observe(api: collect.Api, *, contributions: dict[str, dict], operations: dict[str, dict],
            contracts: dict[str, dict], policy: dict, now: str) -> Observation:
    obs = Observation()
    for rec in contributions.values():
        if rec["phase"] not in WATCH_PHASES or not rec.get("fork"):
            continue
        cid = rec["contribution_id"]
        fork = rec["fork"]["name"]
        head = collect.branch_head(api, fork, DEV_REF)
        entry: dict[str, Any] = {"contribution": cid, "fork": fork,
                                 "observed_head": head and head["head"]}
        # Uncertain branch operations are resolved by discovery first.
        for op in operations.values():
            if op["contribution_id"] == cid and op["status"] in recovery.OPEN and \
                    op["kind"] in ("branch_update", "branch_rewrite"):
                result = recovery.discover_branch(op, head)
                new = recovery.record_discovery(op, result, f"{DEV_REF} at {head and head['head']}", now)
                obs.staged.append(("operations", new))
                operations[op["operation_id"]] = new
                entry["operation"] = {"id": op["operation_id"], "discovery": result}
        if head is None:
            entry["note"] = "riscv64 branch missing"
            obs.report.append(entry)
            continue
        cur = rec
        if head["head"] != (rec["fork"].get("head_sha")):
            out = lifecycle.observe_head(rec, head["head"], now=now, cause_id=f"branch:{head['head'][:12]}")
            cur = out.record
            obs.staged.append(("contributions", cur))
            if out.event:
                obs.staged.append(("events", out.event))
            entry["head_changed"] = True
        if cur["phase"] == "development" and cur["activity"] == "idle" \
                and not cur.get("proposal_artifact") and not cur.get("publication_operation_id") \
                and not cur.get("last_ci_evidence_id") and head["head"] == cur["upstream"].get("base_sha"):
            # The provisioned base is not a delivered contribution. Missing or
            # fork-guarded base CI must not suppress the initial patch task.
            entry["note"] = "awaiting initial development patch"
            obs.report.append(entry)
            continue
        if not cur.get("active_work") and cur["activity"] != "agent_running":
            feedback = collect.development_review_feedback(
                api, cur, policy["command_authority"]["actor_ids"])
            if feedback:
                ids = feedback["review_ids"] + feedback["comment_ids"]
                eid = safe_id(f"review-{cur['fork']['repository_id']}-{cur['fork']['pr_number']}-{max(ids)}")
                summaries = [item["body"] for item in feedback["reviews"] + feedback["comments"]]
                ev = {"schema_version": 1, "evidence_id": eid, "contribution_id": cid,
                      "kind": "human_relay", "policy_version": policy["policy_version"],
                      "collected_at": now, "summary": "\n\n".join(summaries)[:8000],
                      "limitations": [], "data": feedback, "digests": {"head": head["head"]}}
                schemas.validate("evidence", ev)
                before = cur
                cur = dict(cur, revision=cur["revision"] + 1, phase="development", activity="fix_needed",
                           active_work=None, active_operation_id=None, clean_head_sha=None,
                           handoff_request=None, handoff_approval=None, pending_human_action=None,
                           last_ci_evidence_id=eid,
                           processed_review_ids=((cur.get("processed_review_ids") or []) + feedback["review_ids"])[-256:],
                           processed_review_comment_ids=((cur.get("processed_review_comment_ids") or [])
                                                         + feedback["comment_ids"])[-512:], updated_at=now)
                schemas.validate("contribution", cur)
                obs.staged.extend([("evidence", ev), ("contributions", cur),
                                   ("events", lifecycle._event(before, cur, "development_review_feedback",
                                                               "observation", eid, now, True))])
                entry["review_feedback"] = eid
                obs.report.append(entry)
                continue
        upstream_facing = cur.get("upstream_pr") is not None
        repo_for_ci = cur["upstream"]["full_name"] if upstream_facing else fork
        snap = collect.ci_snapshot(api, repo_for_ci, head["head"])
        ctr = contract_for(cur, contracts)
        verdict = collect.evaluate_snapshot(snap, required_job_patterns=ctr["required_job_patterns"],
                                            expected_wheels=ctr["expected_wheels"],
                                            required_runner_label=ctr["required_runner_label"])
        if verdict.state == "passed" and ctr["require_wheel_artifact"] \
                and not collect.wheel_names_from_artifacts(snap):
            # Green jobs without a riscv64 wheel artifact are not wheel success.
            verdict.state = "failed"
            verdict.problems.append("no riscv64 wheel artifact was uploaded")
        entry["ci"] = {"repository": repo_for_ci, "state": verdict.state, "problems": verdict.problems[:10]}
        latest = ci_evidence.latest_attempts([r for r in snap.runs if r["head_sha"] == head["head"]])
        new_activity = {"passed": "idle", "failed": "fix_needed", "pending": "waiting_ci",
                        "missing": "waiting_ci", "not_executed": "waiting_human",
                        "access_wait": "waiting_human"}[verdict.state]
        if verdict.state == "passed" and cur["phase"] == "handoff":
            new_activity = "waiting_human"
        if verdict.state in ("passed", "failed", "not_executed") and latest:
            run = max(latest, key=lambda r: r["id"])
            eid = _evidence_id(snap.repository["id"], run)
            ev = ci_evidence.evidence_record(
                evidence_id=eid, contribution_id=cid, policy_version=policy["policy_version"],
                collected_at=now, repository=snap.repository, run=run,
                jobs=[j for r in latest for j in snap.jobs_by_run.get(r["id"], [])],
                base_sha=cur["upstream"].get("base_sha"), test_merge_sha=None,
                expected_wheels=ctr["expected_wheels"],
                artifacts=[], verdict=verdict,
                debug_present=bool(cur.get("debug_commits")) and not upstream_facing,
                limitations=[] if verdict.state == "passed" else ["see problems"])
            obs.staged.append(("evidence", ev))
            if verdict.state == "passed" and cur.get("last_ci_evidence_id") != eid:
                cur = dict(cur, last_ci_evidence_id=eid, updated_at=now)
                obs.staged.append(("contributions", cur))
            if verdict.state == "passed" and cur["phase"] == "development" and not cur.get("debug_commits"):
                before = cur
                cur = dict(cur, phase="handoff", activity="waiting_human", active_work=None,
                           clean_head_sha=head["head"],
                           handoff_request={"command_id": f"observation-{eid}", "head": head["head"],
                                            "revision": cur["revision"]},
                           pending_human_action={"kind": "approve_handoff", "requested_at": now,
                                                 "reminded_at": None, "escalated_at": None},
                           updated_at=now)
                schemas.validate("contribution", cur)
                obs.staged.append(("contributions", cur))
                obs.staged.append(("events", lifecycle._event(before, cur, "handoff_ready", "observation", eid, now, False)))
                new_activity = "waiting_human"
                entry["handoff_ready"] = True
            entry["evidence"] = eid
        if cur["activity"] != new_activity and cur["activity"] != "agent_running":
            out = lifecycle.observe_status(cur, activity=new_activity, now=now)
            obs.staged.append(("contributions", out.record))
            if out.event:
                obs.staged.append(("events", out.event))
            entry["activity"] = new_activity
        obs.report.append(entry)
    return obs


def dedupe(staged: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Keep the last version of each non-event record, all events in order."""
    from .state import record_path
    last: dict[str, tuple[str, dict]] = {}
    events: list[tuple[str, dict]] = []
    for kind, rec in staged:
        if kind == "events":
            events.append((kind, rec))
        else:
            last[record_path(kind, rec)] = (kind, rec)
    return list(last.values()) + events
