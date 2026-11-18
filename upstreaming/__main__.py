# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Command-line entry points.

    python -m upstreaming validate-state [ROOT]
    python -m upstreaming check-state-diff BASE CANDIDATE
    python -m upstreaming audit-triggers [--paths P ...]
    python -m upstreaming parse-command FILE|-
    python -m upstreaming capacity [--file usage.json]
    python -m upstreaming observe [ROOT]     # read-only tick

All subcommands are local or read-only. None performs a remote write.
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
    issues = collect.intake_issues() if not args.offline else []
    res = controller.tick(contributions=contributions, operations=operations, consumed=consumed,
                          projects=projects, policy=dict(policy, read_only=True),
                          inputs=controller.Inputs(now=now, issues=issues, pressure=pressure))
    res.report["would_stage"] = [state.record_path(k, r) if k != "events" else f"events/{r['contribution_id']}"
                                 for k, r in res.staged]
    res.report["requested_effects"] = res.requested_effects
    print(json.dumps(res.report, indent=2, default=str))
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
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
