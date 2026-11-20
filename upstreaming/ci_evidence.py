# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""CI observation and evidence normalization (plan sections 6.2, 11.4, 14.3).

Only executed, matching jobs count. Missing, skipped, neutral, cancelled,
approval-required (``action_required``) and stale jobs never count as wheel
success. Reruns are resolved to the latest attempt per job name and matrix
identity; duplicate check names are kept apart by job ID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

SUCCESS = "success"
NOT_EXECUTED = frozenset({"skipped", "neutral", "cancelled", "action_required", "stale", None})
# Disposable forks intentionally lack package publishing credentials and OIDC
# trust. Those jobs may fail naturally and do not invalidate build/test CI.
CREDENTIALLESS_JOB_MARKERS = ("publish", "upload_pypi", "upload to pypi", "validate-release-request")


@dataclass
class CiVerdict:
    state: str                     # passed | failed | pending | not_executed | access_wait | missing
    executed_jobs: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def job_executed(job: dict) -> bool:
    return job.get("status") == "completed" and job.get("conclusion") not in NOT_EXECUTED \
        and bool(job.get("started_at"))


def latest_attempts(runs: Iterable[dict]) -> list[dict]:
    """Newest attempt of each workflow run (by workflow ID and event)."""
    best: dict[tuple, dict] = {}
    for r in runs:
        k = (r["workflow_id"], r["event"])
        if k not in best or (r["run_attempt"], r["id"]) > (best[k]["run_attempt"], best[k]["id"]):
            best[k] = r
    return list(best.values())


def evaluate(*, runs: list[dict], jobs_by_run: dict[int, list[dict]], head_sha: str,
             required_job_patterns: list[str], expected_wheels: list[str],
             produced_wheels: list[str], required_runner_label: str | None = None) -> CiVerdict:
    """Decide what the observed CI establishes for ``head_sha``.

    ``required_job_patterns`` are substrings identifying the wheel jobs the
    target contract requires (from the dossier). A run for another SHA is
    ignored: evidence is bound to the exact head that ran.
    """
    v = CiVerdict(state="missing")
    relevant = [r for r in latest_attempts(runs) if r.get("head_sha") == head_sha]
    if not relevant:
        v.problems.append("no workflow run for this head")
        return v
    if any(r.get("conclusion") == "action_required" for r in relevant):
        v.state = "access_wait"
        v.problems.append("a run needs approval; wait for the responsible human")
        return v
    all_jobs = [j for r in relevant for j in jobs_by_run.get(r["id"], [])]
    pending = [j for j in all_jobs if j.get("status") != "completed"]
    blocking_failures = [
        j for j in all_jobs
        if job_executed(j) and j.get("conclusion") != SUCCESS
        and not any(marker in j.get("name", "").lower() for marker in CREDENTIALLESS_JOB_MARKERS)
    ]
    for j in blocking_failures:
        v.problems.append(f"job {j['name']!r} failed ({j.get('conclusion')})")
    # Wheel success means the wheel was built on the native runner label: a
    # job only matches when its name matches and it ran on that label.
    for pat in required_job_patterns:
        matching = [j for j in all_jobs if pat in j["name"]]
        if not matching:
            v.problems.append(f"required job {pat!r} absent")
            continue
        for j in matching:
            if j.get("status") != "completed":
                continue
            if not job_executed(j):
                v.problems.append(f"job {j['name']!r} did not execute ({j.get('conclusion')})")
            elif j["conclusion"] != SUCCESS:
                v.problems.append(f"job {j['name']!r} failed ({j['conclusion']})")
            else:
                v.executed_jobs.append(j)
            labels = j.get("labels") or []
            if required_runner_label and required_runner_label not in labels:
                # Runner topology is project-specific. Dedicated native rows
                # pin a label; shared QEMU/cross matrices deliberately do not.
                v.problems.append(
                    f"job {j['name']!r} failed runner-label check {required_runner_label!r}: labels {labels}")
    missing_wheels = sorted(set(expected_wheels) - set(produced_wheels))
    if missing_wheels:
        v.problems.append(f"expected wheels not produced: {', '.join(missing_wheels)}")
    if any("failed" in p for p in v.problems):
        v.state = "failed"
    elif pending:
        v.state = "pending"
    elif any("did not execute" in p or "absent" in p for p in v.problems):
        v.state = "not_executed"
    elif v.problems:
        v.state = "failed"
    else:
        v.state = "passed"
    return v


def evidence_record(*, evidence_id: str, contribution_id: str, policy_version: str,
                    collected_at: str, repository: dict, run: dict, jobs: list[dict],
                    base_sha: str | None, test_merge_sha: str | None,
                    expected_wheels: list[str], artifacts: list[dict], verdict: CiVerdict,
                    debug_present: bool, limitations: list[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "evidence_id": evidence_id,
        "contribution_id": contribution_id,
        "kind": "ci",
        "policy_version": policy_version,
        "collected_at": collected_at,
        "summary": f"{run['path']} run {run['id']} attempt {run['run_attempt']}: {verdict.state}",
        "limitations": limitations + verdict.problems,
        "debug_present": debug_present,
        "ci": {
            "repository_id": repository["id"],
            "repository": repository["full_name"],
            "head_sha": run["head_sha"],
            "base_sha": base_sha,
            "test_merge_sha": test_merge_sha,
            "workflow_id": run["workflow_id"],
            "workflow_path": run["path"],
            "workflow_sha": run.get("workflow_sha"),
            "event": run["event"],
            "run_id": run["id"],
            "run_attempt": run["run_attempt"],
            "jobs": [{"job_id": j["id"], "name": j["name"], "status": j["status"],
                      "conclusion": j.get("conclusion"), "executed": job_executed(j),
                      "runner_labels": j.get("labels") or []} for j in jobs],
            "expected_wheels": expected_wheels,
            "artifacts": artifacts,
        },
    }
