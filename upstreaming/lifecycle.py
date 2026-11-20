# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Contribution lifecycle: phases, ordinary transitions and command handling
(plan sections 6.2, 7.3 and 8).

Everything here is pure: functions take a record and return a new record plus
the semantic event to persist. They never perform remote effects. The trusted
state publisher persists the outcome; remote writers call ``publication_check``
immediately before an effect.

Revision rule: ``revision`` increments only when requested work changes (head
or base, approved scope/contract, or a human decision affecting work). Polls,
heartbeats and routine CI observations never increment it.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from . import schemas
from .commands import Command, URGENT
from .common import DEV_REF, validate_scope_paths

PHASES = (
    "queued", "investigation", "provisioning", "development", "handoff",
    "upstream_review", "release_wait", "released", "parked",
    "no_work", "deferred", "abandoned", "already_released",
)
TERMINAL = frozenset({"released", "no_work", "deferred", "abandoned", "already_released"})
ACTIVITIES = ("idle", "agent_running", "waiting_ci", "fix_needed",
              "waiting_capacity", "waiting_human")

# Ordinary (non-command) phase exits. "parked" and "abandoned" are reachable
# from every non-terminal phase through commands only.
ORDINARY = {
    "queued": {"investigation", "deferred"},
    "investigation": {"provisioning", "no_work", "deferred", "already_released"},
    "provisioning": {"development", "deferred"},
    "development": {"handoff"},
    "handoff": {"upstream_review", "development"},
    "upstream_review": {"release_wait"},
    "release_wait": {"released"},
    "released": set(),
    "parked": set(),
}

# Phases in which automated contribution writes to the fork may happen.
WRITE_PHASES = frozenset({"provisioning", "development", "handoff", "upstream_review"})


class TransitionError(ValueError):
    pass


@dataclass
class Outcome:
    record: dict[str, Any]
    accepted: bool
    reason: str | None
    event: dict[str, Any] | None


def _event(before: dict, after: dict, kind: str, cause_type: str, cause_id: str | None,
           now: str, bumped: bool) -> dict:
    keys = ("phase", "activity", "paused", "revision", "generation",
            "blocked_reason", "parked_reason")
    return {
        "schema_version": 1,
        "contribution_id": after["contribution_id"],
        "sequence": 0,  # assigned by the state store
        "at": now,
        "kind": kind,
        "from": {k: before.get(k) for k in keys if before.get(k) != after.get(k)},
        "to": {k: after.get(k) for k in keys if before.get(k) != after.get(k)},
        "cause": {"type": cause_type, "id": cause_id},
        "revision_bumped": bumped,
    }


def _bump(rec: dict) -> None:
    rec["revision"] += 1


def transition(record: dict, to_phase: str, *, cause_type: str, cause_id: str | None,
               now: str, reason: str | None = None) -> Outcome:
    """Apply an ordinary (observation/result-driven) phase transition."""
    if to_phase not in PHASES:
        raise TransitionError(f"unknown phase {to_phase!r}")
    frm = record["phase"]
    if to_phase not in ORDINARY.get(frm, set()):
        raise TransitionError(f"{frm} -> {to_phase} is not an ordinary transition")
    if record.get("paused") and to_phase not in ("release_wait", "released"):
        # Pause stops new work. Merge/release are observations, not work.
        raise TransitionError("contribution is paused")
    rec = copy.deepcopy(record)
    rec["phase"] = to_phase
    rec["activity"] = "idle"
    rec["updated_at"] = now
    bumped = False
    if to_phase in TERMINAL:
        rec["terminal_reason"] = reason
    if to_phase == "release_wait":
        # Merge ends fork development immediately.
        rec["active_operation_id"] = None
    if frm == "handoff" and to_phase == "development":
        # New contribution changes before submission invalidate approval.
        rec["handoff_approval"] = None
        rec["handoff_request"] = None
        bumped = True
        _bump(rec)
    schemas.validate("contribution", rec)
    return Outcome(rec, True, None, _event(record, rec, f"phase:{to_phase}", cause_type,
                                           cause_id, now, bumped))


def observe_head(record: dict, new_head: str, *, now: str, cause_id: str | None = None) -> Outcome:
    """Record an observed fork head. A changed head is changed requested work:
    bump the revision and invalidate head-bound readiness and approval."""
    fork = record.get("fork") or {}
    if fork.get("head_sha") == new_head:
        return Outcome(record, True, "unchanged", None)
    rec = copy.deepcopy(record)
    rec["fork"]["head_sha"] = new_head
    rec["last_ci_evidence_id"] = None
    if rec.get("upstream_pr") is None:
        rec["handoff_approval"] = None
    rec["updated_at"] = now
    _bump(rec)
    schemas.validate("contribution", rec)
    return Outcome(rec, True, None, _event(record, rec, "head_changed", "observation",
                                           cause_id, now, True))


def observe_status(record: dict, *, activity: str | None = None, next_poll_at: str | None = None,
                   now: str) -> Outcome:
    """Routine observation; never bumps revision, never invalidates work."""
    rec = copy.deepcopy(record)
    if activity is not None:
        if activity not in ACTIVITIES:
            raise TransitionError(f"unknown activity {activity!r}")
        rec["activity"] = activity
    if next_poll_at is not None:
        rec["next_poll_at"] = next_poll_at
    semantic = rec.get("activity") != record.get("activity")
    if semantic:
        rec["updated_at"] = now
    schemas.validate("contribution", rec)
    ev = _event(record, rec, "activity", "observation", None, now, False) if semantic else None
    return Outcome(rec, True, None, ev)


# --------------------------------------------------------------------------
# Commands


def _reject(record: dict, reason: str) -> Outcome:
    return Outcome(record, False, reason, None)


def _restart_generation(record: dict, now: str) -> dict:
    """Reset mutable lifecycle state while retaining identity and replay fences."""
    rec = copy.deepcopy(record)
    rec.update({
        "generation": int(record.get("generation", 0)) + 1, "refresh": None,
        "phase": "queued", "activity": "idle", "paused": False,
        "blocked_reason": None, "parked_reason": None, "terminal_reason": None,
        "previous_phase": None,
        "owners": {"primary": None, "backup": None, "submitter": None,
                   "handoff_reviewer": None},
        "admission_class": None,
        "upstream": {"repository_id": None, "full_name": record["upstream"]["full_name"],
                     "base_ref": None, "base_sha": None},
        "fork": None, "upstream_pr": None, "target_contract_id": None,
        "prerequisite_ids": [], "active_operation_id": None,
        "queue_work_id": None, "queue_claim_handle": None, "queue_result_id": None,
        "proposal_artifact": None, "publication_operation_id": None,
        "pending_publication": None,
        # Keep processed_publications as a replay fence against old run artifacts.
        "processed_review_ids": [], "processed_review_comment_ids": [],
        "processed_pr_conversation_comment_ids": [],
        "pending_feedback_evidence_ids": [], "active_work": None,
        "dossier_evidence_id": None, "scope_coverage_complete": False,
        "scope_paths": None, "debug_commits": [], "clean_head_sha": None,
        "handoff_request": None, "handoff_approval": None,
        "last_ci_evidence_id": None, "merge": None, "retirement": None,
        "release_acceptance": None, "pending_human_action": None,
        "next_poll_at": None, "updated_at": now,
    })
    budget = record["budget"]
    rec["budget"] = {"policy_id": budget["policy_id"], "attempts_used": 0,
                     "no_progress_streak": 0, "clusters": {},
                     "spent_estimate_usd_cents": 0}
    _bump(rec)
    return rec


def apply_command(record: dict, cmd: Command, *, command_id: str, actor: dict, now: str,
                  verified_pr: dict | None = None, provisioning: dict | None = None,
                  backup_user: dict | None = None) -> Outcome:
    """Apply an already authenticated, not-yet-consumed command.

    Actor authority, replay and digest checks happen in ``intake.accept_command``
    before this is called. ``verified_pr`` is the upstream PR resource as read
    from the GitHub API for ``register-upstream-pr``; the URL alone is never
    sufficient.
    """
    if cmd.verb == "resolve-operation":
        raise TransitionError("resolve-operation applies to operations, see recovery.py")
    if cmd.contribution is not None and cmd.contribution != record["contribution_id"]:
        return _reject(record, "command names another contribution than this issue's")
    rev = cmd.revision
    cur = record["revision"]
    phase = record["phase"]
    if rev is None:
        # Only stop commands may omit it (enforced by the grammar).
        rev = cur
    if rev > cur:
        return _reject(record, "revision is not a known revision")
    # Stopping is always safe, so a stale pause/park/block/abandon is honoured.
    # Everything that (re)activates or approves work must name the current revision.
    if cmd.verb not in ("pause", "block", "park", "abandon") and rev != cur:
        return _reject(record, f"stale revision {rev}, current is {cur}")
    if phase in TERMINAL and cmd.verb not in ("authorize-followup", "restart"):
        return _reject(record, f"contribution is terminal ({phase})")

    rec = copy.deepcopy(record)
    rec["updated_at"] = now
    bumped = False
    v = cmd.verb
    a = cmd.args

    if v == "pause":
        if rec["paused"]:
            return _reject(record, "already paused")
        rec["paused"] = True
    elif v == "block":
        rec["blocked_reason"] = a.get("reason") or "blocked"
        rec["activity"] = "waiting_human"
    elif v == "resume":
        if phase == "parked":
            # Explicit resumption only; revalidate the dossier.
            rec["phase"] = "investigation"
            rec["parked_reason"] = None
            rec["activity"] = "idle"
        elif rec["paused"] or rec.get("blocked_reason"):
            rec["paused"] = False
            rec["blocked_reason"] = None
            if rec["activity"] == "waiting_human" and rec.get("pending_human_action") is None:
                rec["activity"] = "idle"
        else:
            return _reject(record, "nothing to resume")
        _bump(rec)
        bumped = True
    elif v == "park":
        if phase == "parked":
            return _reject(record, "already parked")
        rec["previous_phase"] = phase
        rec["phase"] = "parked"
        rec["parked_reason"] = a["reason"]
        rec["activity"] = "idle"
    elif v == "abandon":
        rec["phase"] = "abandoned"
        rec["terminal_reason"] = a["reason"]
        rec["activity"] = "idle"
    elif v == "restart":
        if phase != "abandoned":
            return _reject(record, f"restart needs phase abandoned, not {phase}")
        if record.get("active_work"):
            return _reject(record, "cannot restart while Work is active")
        if record.get("active_operation_id") or record.get("pending_publication"):
            return _reject(record, "cannot restart while a writer operation is active")
        rec = _restart_generation(record, now)
        bumped = True
    elif v == "refresh":
        if phase not in ("development", "handoff"):
            return _reject(record, f"refresh needs an existing development PR, not phase {phase}")
        fork = record.get("fork") or {}
        if not fork.get("pr_number") or not fork.get("head_sha"):
            return _reject(record, "refresh needs a verified development PR and head")
        if record.get("active_work"):
            return _reject(record, "cannot refresh while Work is active")
        if record.get("active_operation_id") or record.get("pending_publication"):
            return _reject(record, "cannot refresh while a writer operation is active")
        rec["refresh"] = {"command_id": command_id, "reason": a["reason"],
                          "from_phase": phase, "head_sha": fork["head_sha"],
                          "pr_number": fork["pr_number"]}
        rec["phase"] = "queued"
        rec["activity"] = "idle"
        rec["dossier_evidence_id"] = None
        rec["scope_coverage_complete"] = False
        rec["scope_paths"] = None
        rec["proposal_artifact"] = None
        rec["last_ci_evidence_id"] = None
        rec["clean_head_sha"] = None
        rec["handoff_request"] = None
        rec["handoff_approval"] = None
        rec["pending_human_action"] = None
        rec["publication_operation_id"] = None
        _bump(rec)
        bumped = True
    elif v == "request-handoff":
        if phase != "development":
            return _reject(record, f"request-handoff needs phase development, not {phase}")
        if rec["paused"]:
            return _reject(record, "contribution is paused")
        if (rec.get("fork") or {}).get("head_sha") != a["head"]:
            return _reject(record, "head does not match the current fork head")
        if not rec.get("last_ci_evidence_id"):
            return _reject(record, "no executed development CI evidence for this head")
        rec["phase"] = "handoff"
        rec["activity"] = "idle"
        rec["handoff_request"] = {"command_id": command_id, "head": a["head"], "revision": cur}
    elif v == "approve-handoff":
        if phase != "handoff":
            return _reject(record, f"approve-handoff needs phase handoff, not {phase}")
        clean = rec.get("clean_head_sha")
        if not clean:
            return _reject(record, "debug cleanup has not produced a clean head yet")
        if a["head"] != clean or (rec.get("fork") or {}).get("head_sha") != clean:
            return _reject(record, "approval head is not the current clean head")
        if rec.get("debug_commits") and any(d["sha"] == clean for d in rec["debug_commits"]):
            return _reject(record, "clean head is a debug commit")
        rec["handoff_approval"] = {
            "command_id": command_id, "actor": actor, "head": clean, "revision": cur,
            "evidence_ids": [x for x in [rec.get("last_ci_evidence_id")] if x],
        }
        rec["activity"] = "waiting_human"
        rec["pending_human_action"] = {"kind": "open_upstream_pr", "requested_at": now,
                                       "reminded_at": None, "escalated_at": None}
    elif v == "register-upstream-pr":
        if phase != "handoff":
            return _reject(record, f"register-upstream-pr needs phase handoff, not {phase}")
        appr = rec.get("handoff_approval")
        if not appr:
            return _reject(record, "handoff has not been approved")
        if verified_pr is None:
            return _reject(record, "upstream PR resource not verified")
        if verified_pr.get("html_url") != a["url"]:
            return _reject(record, "verified PR does not match the URL")
        if verified_pr.get("base_repository") != rec["upstream"]["full_name"]:
            return _reject(record, "PR is not against the upstream repository")
        if rec["upstream"].get("base_ref") and verified_pr.get("base_ref") != rec["upstream"]["base_ref"]:
            return _reject(record, "PR base ref differs from the approved base")
        if verified_pr.get("head_sha") != appr["head"]:
            return _reject(record, "PR head is not the approved clean head")
        if verified_pr.get("state") != "open":
            return _reject(record, "PR is not open")
        head_repo = verified_pr.get("head_repository")
        rec["upstream_pr"] = {
            "id": verified_pr["id"], "number": verified_pr["number"], "url": a["url"],
            "head_repository_id": verified_pr["head_repository_id"],
            "head_ref": verified_pr["head_ref"], "head_sha": verified_pr["head_sha"],
            "base_ref": verified_pr["base_ref"], "registered_by": actor,
        }
        writable = (rec.get("fork") and head_repo == rec["fork"]["name"]
                    and verified_pr["head_ref"] == DEV_REF)
        if not writable:
            # The human used another branch: prepare patches for them, never
            # silently create another automated branch.
            rec["blocked_reason"] = ("upstream PR head is not "
                                     f"{(rec.get('fork') or {}).get('name')}:{DEV_REF}; "
                                     "automated revisions disabled, patches go to the submitter")
        rec["phase"] = "upstream_review"
        rec["activity"] = "waiting_ci"
        rec["pending_human_action"] = None
    elif v == "clarify":
        if rec["activity"] != "waiting_human" and not rec.get("blocked_reason"):
            return _reject(record, "no pending question")
        rec["activity"] = "idle"
        rec["pending_human_action"] = None
        _bump(rec)
        bumped = True
    elif v == "revise-scope":
        if rec.get("upstream_pr") is None:
            rec["handoff_approval"] = None
        rec["target_contract_id"] = a["proposal"]
        rec["activity"] = "idle"
        _bump(rec)
        bumped = True
    elif v == "force-develop":
        if phase != "parked":
            return _reject(record, f"force-develop needs phase parked, not {phase}")
        paths = [g for g in a["paths"].split(",") if g]
        try:
            validate_scope_paths(paths)
        except ValueError as exc:
            return _reject(record, str(exc))
        rec["phase"] = "provisioning"
        rec["activity"] = "idle"
        rec["parked_reason"] = None
        rec["admission_class"] = a["class"]
        rec["scope_paths"] = paths
        rec["pending_human_action"] = None
        _bump(rec)
        bumped = True
    elif v == "approve-scope":
        if phase != "investigation":
            return _reject(record, f"approve-scope needs phase investigation, not {phase}")
        if rec.get("active_work"):
            return _reject(record, "the investigation is still running")
        if not rec.get("dossier_evidence_id"):
            return _reject(record, "no investigation dossier recorded yet")
        if backup_user is None:
            return _reject(record, f"backup owner {a['backup']!r} is not a known GitHub user")
        if backup_user["id"] == actor["id"]:
            return _reject(record, "the backup owner must be someone else")
        rec["owners"] = dict(rec["owners"], primary=dict(actor), backup=dict(backup_user))
        rec["admission_class"] = a["class"]
        rec["scope_paths"] = [g for g in (a.get("paths") or "").split(",") if g] or None
        rec["phase"] = "provisioning"
        rec["activity"] = "waiting_human"
        rec["pending_human_action"] = {"kind": "provision_fork", "requested_at": now,
                                       "reminded_at": None, "escalated_at": None}
        _bump(rec)
        bumped = True
    elif v == "provision":
        if phase != "provisioning":
            return _reject(record, f"provision needs phase provisioning, not {phase}")
        if not provisioning or provisioning.get("error"):
            return _reject(record, (provisioning or {}).get("error") or "fork not verified")
        if provisioning.get("workflow_verified") is not True:
            return _reject(record, "fork provisioning must complete through the trusted upstreaming workflow; a bare existing fork is not sufficient")
        rec["fork"] = {"repository_id": provisioning["fork_id"], "name": provisioning["fork"],
                       "head_ref": DEV_REF, "head_sha": provisioning["head_sha"], "pr_number": None}
        rec["upstream"] = dict(rec["upstream"], repository_id=provisioning["upstream_id"],
                               base_ref=provisioning["base_ref"], base_sha=provisioning["base_sha"])
        rec["phase"] = "development"
        rec["activity"] = "idle"
        rec["pending_human_action"] = None
        rec["last_ci_evidence_id"] = None
        _bump(rec)
        bumped = True
    elif v == "authorize-followup":
        if phase not in ("release_wait", "released"):
            return _reject(record, "follow-ups need a merged contribution")
        # The completed record is left intact; intake.new_followup creates
        # the new identity. Here we only record the event.
    else:  # pragma: no cover - grammar and this table must agree
        raise TransitionError(f"unhandled verb {v}")

    # Stopping a contribution or moving it to a new revision ends any
    # requested task: a late worker outcome is then ignored as stale, and
    # dispatch recovery must not launch it again.
    if rec.get("active_work") and (rec["paused"] or rec["phase"] in TERMINAL | {"parked"}
                                   or rec["revision"] != record["revision"] or rec.get("blocked_reason")):
        rec["active_work"] = None
        if rec["activity"] == "agent_running":
            rec["activity"] = "idle"

    if rec != record or v == "authorize-followup":
        schemas.validate("contribution", rec)
    kind = f"command:{v}"
    return Outcome(rec, True, None, _event(record, rec, kind, "command", command_id, now, bumped))


def command_priority(cmd: Command) -> int:
    """Urgent stop commands sort first, then other controls."""
    return 0 if cmd.verb in URGENT else 1


# --------------------------------------------------------------------------
# Publication guard


def publication_check(record: dict, *, expected_revision: int, expected_head: str | None,
                      observed_head: str | None, ref: str, repository: str) -> str | None:
    """Re-read immediately before a fork write. Returns None when the write
    may proceed, otherwise the reason it must not. An effect that already
    passed this check may still finish after a later pause (best-effort
    pause, plan section 2); it is reconciled as a normal effect."""
    if record["phase"] not in WRITE_PHASES:
        return f"phase {record['phase']} does not permit fork writes"
    if record.get("paused"):
        return "paused"
    if record.get("blocked_reason"):
        return "blocked"
    if ref != DEV_REF:
        return f"ref {ref!r} is not {DEV_REF!r}"
    fork = record.get("fork") or {}
    if repository != fork.get("name"):
        return "repository is not the recorded contribution fork"
    if record["revision"] != expected_revision:
        return "work revision changed"
    if observed_head != expected_head:
        return "fork head changed since the proposal was made"
    if record.get("active_operation_id"):
        return "another writer operation is active on this fork"
    return None


def new_contribution(*, contribution_id: str, project_id: str, issue: dict, upstream: str,
                     distributions: list[str], base_ref: str | None, policy_id: str,
                     now: str, follows: str | None = None) -> dict:
    rec = {
        "schema_version": 1,
        "contribution_id": contribution_id,
        "project_id": project_id,
        "revision": 0,
        "generation": 0,
        "refresh": None,
        "phase": "queued",
        "activity": "idle",
        "paused": False,
        "blocked_reason": None,
        "parked_reason": None,
        "terminal_reason": None,
        "previous_phase": None,
        "tracking_issue": {"id": issue["id"], "number": issue["number"]},
        "owners": {"primary": None, "backup": None, "submitter": None, "handoff_reviewer": None},
        "admission_class": None,
        "distributions": distributions,
        "upstream": {"repository_id": None, "full_name": upstream, "base_ref": base_ref,
                     "base_sha": None},
        "fork": None,
        "upstream_pr": None,
        "target_contract_id": None,
        "prerequisite_ids": [],
        "active_operation_id": None,
        "queue_work_id": None,
        "queue_claim_handle": None,
        "queue_result_id": None,
        "proposal_artifact": None,
        "publication_operation_id": None,
        "pending_publication": None,
        "processed_publications": [],
        "processed_review_ids": [],
        "processed_review_comment_ids": [],
        "processed_pr_conversation_comment_ids": [],
        "active_work": None,
        "dossier_evidence_id": None,
        "debug_commits": [],
        "clean_head_sha": None,
        "handoff_request": None,
        "handoff_approval": None,
        "last_ci_evidence_id": None,
        "merge": None,
        "retirement": None,
        "release_acceptance": None,
        "budget": {"policy_id": policy_id, "attempts_used": 0, "no_progress_streak": 0,
                   "clusters": {}, "spent_estimate_usd_cents": 0},
        "pending_human_action": None,
        "follows": follows,
        "next_poll_at": None,
        "created_at": now,
        "updated_at": now,
    }
    schemas.validate("contribution", rec)
    return rec


def write_admission(record: dict) -> str | None:
    """Gate before any write-capable work is submitted for a contribution."""
    if not record.get("admission_class"):
        return "admission class not approved"
    if not record.get("fork") or not record["fork"].get("repository_id"):
        return "fork not provisioned/verified"
    if record["upstream"].get("base_sha") is None:
        return "no immutable upstream base SHA in the dossier"
    return None
