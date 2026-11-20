# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Command-line entry points.

    python -m upstreaming validate-state [ROOT]
    python -m upstreaming check-state-diff BASE CANDIDATE
    python -m upstreaming audit-triggers [--paths P ...]
    python -m upstreaming parse-command FILE|-
    python -m upstreaming capacity [--file usage.json]
    python -m upstreaming observe [ROOT] [--offline]   # read-only tick, prints report
    python -m upstreaming plan --out PLAN.json --control-repo-id ID
    python -m upstreaming reconcile --publications DIR [--out-records DIR] [--report R.json]

All subcommands are local or read-only. None performs a remote write:
``reconcile`` writes state files locally; ``state_commit`` publishes them.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import capacity, collect, commands, controller, state, triggers
from .common import STATE_ROOT, load_policy


def _root() -> Path:
    import subprocess
    return Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                               text=True, check=True).stdout.strip())


def cmd_validate_state(args) -> int:
    policy = load_policy()
    store = state.StateStore(Path(args.root or _root()), policy)
    bad = 0
    for kind in ("projects", "contributions", "operations", "commands", "events", "evidence"):
        try:
            n = len(store.load_all(kind))
            print(f"{kind}: {n} valid")
        except state.StateError as e:
            print(f"{kind}: INVALID: {e}", file=sys.stderr)
            bad += 1
    total = store.total_bytes()
    if total > policy["storage"]["warn_total_bytes"]:
        print(f"warning: {total} bytes of live state; pause expansion and review storage policy",
              file=sys.stderr)
    return 1 if bad else 0


def cmd_check_state_diff(args) -> int:
    rep = state.validate_state_diff(Path(args.repo or _root()), args.base, args.candidate, load_policy())
    for p in rep.problems:
        print(f"::error::{p}")
    print(json.dumps({"ok": rep.ok, "changed": len(rep.changed), "bytes": rep.total_bytes}))
    return 0 if rep.ok else 1


def cmd_audit_triggers(args) -> int:
    root = Path(args.root or _root())
    paths = args.paths or [f"{STATE_ROOT}/contributions/example.json"]
    findings = triggers.audit(root / ".github" / "workflows", paths)
    hit = [f for f in findings if f.triggered]
    consumers = triggers.workflow_run_consumers(root / ".github" / "workflows")
    print(json.dumps({
        "changed_paths": paths,
        "workflows_scanned": len(findings),
        "triggered": [{"workflow": f.workflow, "why": f.why} for f in hit],
        "workflow_run_consumers": consumers,
        "classification": triggers.classify_commit(paths),
    }, indent=2))
    return 1 if (hit and args.expect_none) else 0


def cmd_parse_command(args) -> int:
    body = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    try:
        c = commands.parse(body)
    except commands.CommandError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1
    print(json.dumps({"ok": True, "verb": c.verb, "args": c.args}))
    return 0


def cmd_capacity(args) -> int:
    policy = load_policy()
    if args.file:
        raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
        snap = raw.get("response", raw)
        fetched = datetime.fromisoformat(raw["fetched_at"]) if "fetched_at" in raw else datetime.now(timezone.utc)
        now = fetched
    else:
        snap, fetched = collect.usage(policy["capacity"]["usage_url"])
        now = datetime.now(timezone.utc)
    p = capacity.observe(snap, fetched_at=fetched, now=now,
                         max_age_seconds=policy["capacity"]["max_age_seconds"])
    ok, why = capacity.admit_expensive(p, reserved=0, estimated_jobs=1, policy=policy)
    print(json.dumps({"observation_ok": p.ok, "reason": p.reason, "running": p.running,
                      "pending": p.pending, "oldest_pending_seconds": p.oldest_pending_seconds,
                      "per_entity": p.per_entity, "admit_expensive": ok, "why": why,
                      "note": "pressure observation, not free capacity"}, indent=2))
    return 0


def cmd_observe(args) -> int:
    """Read-only Stage B tick: reads GitHub/PyPI/usage, prints the decision
    report. Never writes state or remote resources."""
    policy = load_policy()
    root = Path(args.root or _root())
    store = state.StateStore(root, policy)
    contributions = {k: v for k, v in store.load_all("contributions").items()}
    operations = {v["operation_id"]: v for v in store.load_all("operations").values()}
    consumed = {v["comment_id"]: v for v in store.load_all("commands").values()}
    projects = {v["project_id"]: v for v in store.load_all("projects").values()}
    now = datetime.now(timezone.utc)
    try:
        snap, fetched = collect.usage(policy["capacity"]["usage_url"])
        pressure = capacity.observe(snap, fetched_at=fetched, now=now,
                                    max_age_seconds=policy["capacity"]["max_age_seconds"])
    except Exception as e:  # unavailable data is "no expensive admission", not zero load
        pressure = capacity.Pressure(ok=False, reason=f"usage unavailable: {e}")
    api = collect.Api()
    issues = collect.intake_issues(api) if not args.offline else []
    # Commands on tracked issues and on intake issues (a command can be posted
    # on a request before its contribution is first persisted).
    numbers = sorted({c["tracking_issue"]["number"] for c in contributions.values()}
                     | {i["number"] for i in issues})
    comments = collect.command_comments(api, numbers, None) if not args.offline else []
    res = controller.tick(contributions=contributions, operations=operations, consumed=consumed,
                          projects=projects, policy=dict(policy, read_only=True),
                          inputs=controller.Inputs(now=now, issues=issues, comments=comments, pressure=pressure,
                                                   upstream_snapshots={} if args.offline else collect.upstream_snapshots(
                                                       api, contributions.values(), issues, policy),
                                                   tracking_issues={} if args.offline else collect.tracking_issues(
                                                       api, contributions.values(), issues),
                                                   **dict(zip(("users", "provisioning"),
                                                              _command_lookups(api, reconcile_snapshot(root, policy), comments)
                                                              if not args.offline else ({}, {})))))
    res.report["would_stage"] = [state.record_path(k, r) if k != "events" else f"events/{r['contribution_id']}"
                                 for k, r in res.staged]
    res.report["requested_effects"] = res.requested_effects
    print(json.dumps(res.report, indent=2, default=str))
    return 0


def reconcile_snapshot(root: Path, policy: dict):
    return _load(root, policy)[1]


def _load(root: Path, policy: dict):
    from . import reconcile
    store = state.StateStore(root, policy)
    return store, reconcile.Snapshot(
        contributions=dict(store.load_all("contributions")),
        operations={v["operation_id"]: v for v in store.load_all("operations").values()},
        consumed={v["comment_id"]: v for v in store.load_all("commands").values()},
        projects={v["project_id"]: v for v in store.load_all("projects").values()},
        evidence={v["evidence_id"]: v for v in store.load_all("evidence").values()})


def _pressure(policy: dict) -> capacity.Pressure:
    now = datetime.now(timezone.utc)
    try:
        snap, fetched = collect.usage(policy["capacity"]["usage_url"])
        return capacity.observe(snap, fetched_at=fetched, now=now,
                                max_age_seconds=policy["capacity"]["max_age_seconds"])
    except Exception as e:  # unavailable data is "no expensive admission", not zero load
        return capacity.Pressure(ok=False, reason=f"usage unavailable: {e}")


def cmd_plan(args) -> int:
    """Dispatcher preparation: turn the tasks the controller already requested
    (``active_work`` in committed state) into a gh-aw staged plan. Selection
    happened in the controller tick that committed ``active_work``; the plan
    only replays that decision, so a rerun or a second dispatcher run stages
    the identical Work (the queue admits an identical node once). No plan file
    means nothing to dispatch."""
    from . import work
    policy = load_policy()
    _store, snap = _load(Path(args.root or _root()), policy)
    contracts = {e["evidence_id"]: e for e in snap.evidence.values() if e.get("kind") == "target_contract"}
    nodes, selected = [], []
    for rec in sorted(snap.contributions.values(), key=lambda c: (c["active_work"] or {}).get("requested_at", "")
                      if c.get("active_work") else ""):
        req = work.request_from_active(rec)
        if req is None:
            continue
        if len(nodes) >= policy["concurrency"]["coding_workers"]:
            break
        if not rec["upstream"].get("repository_id") or not rec["upstream"].get("base_sha"):
            raise ValueError("requested task lacks verified upstream identity/base; request a fresh verified revision")
        if not (rec["active_work"].get("tracking_issue") or {}).get("url"):
            raise ValueError("requested task lacks a frozen tracking-issue description; request a fresh revision")
        ctr = (contracts.get(rec.get("target_contract_id") or "") or {}).get("data") or {}
        reason_evidence = []
        for evidence_id in req.get("reason_ids") or []:
            evidence = snap.evidence.get(evidence_id)
            if evidence:
                item = {key: evidence.get(key) for key in
                        ("evidence_id", "kind", "summary", "limitations")}
                if evidence.get("kind") == "human_relay":
                    item["data"] = evidence.get("data")
                reason_evidence.append(item)
        nodes.append(work.node(req, rec, control_repo_id=args.control_repo_id,
                               allowed_paths=rec.get("scope_paths") or ctr.get("allowed_paths")
                               or [".github/workflows/*"],
                               context={"requested_at": rec["active_work"]["requested_at"],
                                        "reason_evidence": reason_evidence}))
        selected.append({"contribution": rec["contribution_id"], "task": req["task"],
                         "worker_profile": nodes[-1]["worker_profile"]})
    print(json.dumps({"selected": selected}, indent=2))
    if not nodes:
        return 0
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(work.plan(nodes), indent=2))
    return 0


def _command_lookups(api, snap, comments) -> tuple[dict, dict]:
    """Read-only facts some commands need, fetched before the tick: the
    backup owner named by approve-scope, and the fork checks for provision."""
    users: dict = {}
    provisioning: dict = {}
    for item in comments:
        try:
            cmd = commands.parse(item["comment"]["body"])
        except commands.CommandError:
            continue
        if cmd.verb == "approve-scope" and cmd.args["backup"] not in users:
            users[cmd.args["backup"]] = collect.user(api, cmd.args["backup"])
        if cmd.verb == "provision":
            from . import intake
            rec = intake.contribution_for_issue(snap.contributions.values(), item["issue_number"])
            if rec is not None and rec["contribution_id"] not in provisioning:
                provisioning[rec["contribution_id"]] = collect.verify_provisioning(api, rec)
    return users, provisioning


def cmd_reconcile(args) -> int:
    """State-publisher tick: fold publication outcomes, observe live CI,
    apply commands and intake. Writes changed records into the checkout;
    the workflow then publishes them with state_commit."""
    from . import reconcile
    policy = load_policy()
    root = Path(args.root or _root())
    store, snap = _load(root, policy)
    api = collect.Api()
    pubs = []
    # publications/<run-id>/ holds one unzipped upstreaming-publication artifact
    # (from a worker run or a publish-retry run) plus artifact-id.
    for p in sorted(Path(args.publications).glob("*/outcome.json")) if args.publications else []:
        o = json.loads(p.read_text())
        t = p.parent / "task.json"
        o["task"] = json.loads(t.read_text()) if t.exists() else {}
        w = p.parent / "worker-run-id"
        o["worker_run_id"] = w.read_text().strip() if w.exists() else p.parent.name
        aid = p.parent / "artifact-id"
        o["publication_artifact_id"] = int(aid.read_text().strip()) if aid.exists() else None
        for name, key in (("dossier.json", "dossier"), ("proposal.json", "proposal"), ("result.json", "artifact")):
            f = p.parent / name
            if f.exists() and key not in o:
                try:
                    o[key] = json.loads(f.read_text())
                except json.JSONDecodeError:
                    pass
        pubs.append(o)
    development_prs = []
    for p in sorted(Path(args.development_prs).glob("*/outcome.json")) if args.development_prs else []:
        receipt = json.loads(p.read_text())
        aid = p.parent / "artifact-id"
        receipt["development_pr_artifact_id"] = int(aid.read_text()) if aid.exists() else None
        development_prs.append(receipt)
    provisions = []
    for p in sorted(Path(args.provisions).glob("*/outcome.json")) if args.provisions else []:
        receipt = json.loads(p.read_text())
        receipt["provision_run_id"] = p.parent.name
        aid = p.parent / "artifact-id"
        receipt["provision_artifact_id"] = int(aid.read_text()) if aid.exists() else None
        provisions.append(receipt)
    issues = [] if args.offline else collect.intake_issues(api)
    tracking = sorted({c["tracking_issue"]["number"] for c in snap.contributions.values()}
                      | {i["number"] for i in issues})
    comments = [] if args.offline else collect.command_comments(api, tracking, args.since)
    source_snapshots = {} if args.offline else collect.upstream_snapshots(api, snap.contributions.values(), issues, policy)
    issue_snapshots = {} if args.offline else collect.tracking_issues(api, snap.contributions.values(), issues)
    users, provisioning = _command_lookups(api, snap, comments) if not args.offline else ({}, {})
    from .common import INTAKE_LABEL
    acceptances = {} if args.offline else collect.label_acceptances(
        api, issues, INTAKE_LABEL, policy["command_authority"]["actor_ids"])
    runs = queue = None
    if not args.offline and args.gh_aw:
        from . import queue_result
        try:
            runs = collect.dispatcher_runs(api)
            queue = queue_result.queue_work_states(args.gh_aw, collect.CONTROL_REPO)
        except (collect.CollectError, OSError, ValueError) as e:
            print(f"dispatch recovery skipped this tick: {e}", file=sys.stderr)
            runs = queue = None
    out = reconcile.tick(api, snap, policy=policy, now=datetime.now(timezone.utc), publications=pubs,
                         pressure=_pressure(policy), issues=issues, comments=comments, observe=not args.offline,
                         dispatcher_runs=runs, queue_works=queue, users=users, provisioning=provisioning,
                         acceptances=acceptances, tracking_issues=issue_snapshots, upstream_snapshots=source_snapshots,
                         provisions=provisions, development_prs=development_prs)
    for kind, rec in out.staged:
        store.stage(kind, rec)
    written = store.write_staged()
    out.report["written"] = written
    text = json.dumps(out.report, indent=2, default=str)
    (Path(args.report).write_text(text) if args.report else print(text))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m upstreaming")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("validate-state"); p.add_argument("root", nargs="?")
    p.set_defaults(fn=cmd_validate_state)
    p = sub.add_parser("check-state-diff"); p.add_argument("base"); p.add_argument("candidate")
    p.add_argument("--repo"); p.set_defaults(fn=cmd_check_state_diff)
    p = sub.add_parser("audit-triggers"); p.add_argument("--root"); p.add_argument("--paths", nargs="*")
    p.add_argument("--expect-none", action="store_true"); p.set_defaults(fn=cmd_audit_triggers)
    p = sub.add_parser("parse-command"); p.add_argument("file"); p.set_defaults(fn=cmd_parse_command)
    p = sub.add_parser("capacity"); p.add_argument("--file"); p.set_defaults(fn=cmd_capacity)
    p = sub.add_parser("observe"); p.add_argument("root", nargs="?")
    p.add_argument("--offline", action="store_true"); p.set_defaults(fn=cmd_observe)
    p = sub.add_parser("plan"); p.add_argument("--root"); p.add_argument("--out", required=True)
    p.add_argument("--control-repo-id", required=True); p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("reconcile"); p.add_argument("--root"); p.add_argument("--publications")
    p.add_argument("--provisions"); p.add_argument("--development-prs")
    p.add_argument("--report"); p.add_argument("--since"); p.add_argument("--offline", action="store_true")
    p.add_argument("--gh-aw", help="pinned gh-aw v1.2.2 binary, to read the queue for dispatch recovery")
    p.set_defaults(fn=cmd_reconcile)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
