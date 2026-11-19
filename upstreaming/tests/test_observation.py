# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Section 21: CI evidence, capacity, budgets, recovery, release, triggers, tick."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from upstreaming import (capacity, ci_evidence, commands, controller, recovery,
                                    release, triggers)
from upstreaming.tests.helpers import (NOW, OWNER, SHA_A, SHA_B, comment, contribution,
                                                  policy)

T = datetime.fromisoformat(NOW)


def run(i, sha=SHA_A, attempt=1, conclusion="success", wf=10, event="pull_request"):
    return {"id": i, "head_sha": sha, "run_attempt": attempt, "conclusion": conclusion,
            "workflow_id": wf, "event": event, "path": ".github/workflows/wheels.yml"}


def job(i, name, conclusion="success", status="completed", labels=("ubuntu-24.04-riscv",)):
    return {"id": i, "name": name, "status": status, "conclusion": conclusion,
            "started_at": NOW if conclusion not in ("skipped",) else None, "labels": list(labels)}


class TestCiEvidence(unittest.TestCase):
    def ev(self, runs, jobs, expected=("p-1-cp312-cp312-manylinux_2_39_riscv64.whl",), produced=None):
        return ci_evidence.evaluate(runs=runs, jobs_by_run=jobs, head_sha=SHA_A,
                                    required_job_patterns=["riscv64"], expected_wheels=list(expected),
                                    produced_wheels=list(expected if produced is None else produced))

    def test_passed(self):
        self.assertEqual(self.ev([run(1)], {1: [job(1, "wheels riscv64")]}).state, "passed")

    def test_skipped_neutral_cancelled_not_success(self):
        for c in ("skipped", "neutral", "cancelled"):
            with self.subTest(c):
                v = self.ev([run(1)], {1: [job(1, "wheels riscv64", conclusion=c)]})
                self.assertEqual(v.state, "not_executed")

    def test_missing_job_and_wheel(self):
        self.assertEqual(self.ev([run(1)], {1: [job(1, "lint")]}).state, "not_executed")
        self.assertEqual(self.ev([run(1)], {1: [job(1, "wheels riscv64")]}, produced=[]).state, "failed")

    def test_other_head_and_approval(self):
        self.assertEqual(self.ev([run(1, sha=SHA_B)], {}).state, "missing")
        self.assertEqual(self.ev([run(1, conclusion="action_required")], {}).state, "access_wait")

    def test_rerun_uses_latest_attempt(self):
        runs = [run(1, attempt=1), run(1, attempt=2)]
        v = self.ev(runs, {1: [job(1, "wheels riscv64")]})
        self.assertEqual(v.state, "passed")
        self.assertEqual(len(ci_evidence.latest_attempts(runs)), 1)
        self.assertEqual(ci_evidence.latest_attempts(runs)[0]["run_attempt"], 2)

    def test_pending_and_label(self):
        self.assertEqual(self.ev([run(1)], {1: [job(1, "wheels riscv64", status="in_progress",
                                                     conclusion=None)]}).state, "pending")
        v = self.ev([run(1)], {1: [job(1, "wheels riscv64", labels=("riscv-custom",))]})
        self.assertEqual(v.state, "failed")


USAGE = Path.home() / "notes/ecosystem-wg/python/python-wheels-upstreaming/research/2026-11-17-reassessment/runner-usage.json"


class TestCapacityBudgets(unittest.TestCase):
    def test_stale_and_malformed(self):
        p = policy()
        self.assertFalse(capacity.observe({}, fetched_at=T, now=T, max_age_seconds=900).ok)
        old = capacity.observe({"jobs": []}, fetched_at=T - timedelta(hours=1), now=T, max_age_seconds=900)
        self.assertFalse(old.ok)
        ok, why = capacity.admit_expensive(old, reserved=0, estimated_jobs=1, policy=p)
        self.assertFalse(ok)
        self.assertIn("stale", why)

    def test_thresholds_and_reservations(self):
        p = policy()
        snap = {"jobs": [{"job_labels": ["ubuntu-24.04-riscv"], "status": "pending",
                          "entity_name": "riseproject-dev", "job_created_at": NOW}] * 90}
        pr = capacity.observe(snap, fetched_at=T, now=T, max_age_seconds=900)
        self.assertTrue(capacity.admit_expensive(pr, reserved=0, estimated_jobs=5, policy=p)[0])
        ops = [{"status": "applying", "capacity_reservation": {"estimated_jobs": 8, "observed_run_ids": []}},
               {"status": "confirmed", "capacity_reservation": {"estimated_jobs": 50, "observed_run_ids": [1]}},
               {"status": "not_launched", "capacity_reservation": {"estimated_jobs": 50}}]
        self.assertEqual(capacity.reserved_jobs(ops), 8)
        self.assertFalse(capacity.admit_expensive(pr, reserved=8, estimated_jobs=5, policy=p)[0])

    @unittest.skipUnless(USAGE.exists(), "historical usage snapshot not available")
    def test_historical_snapshot(self):
        raw = json.loads(USAGE.read_text())
        t = datetime.fromisoformat(raw["fetched_at"])
        pr = capacity.observe(raw["response"], fetched_at=t, now=t, max_age_seconds=900)
        self.assertEqual(pr.per_entity["riseproject-dev"], {"running": 22, "pending": 113})
        self.assertFalse(capacity.admit_expensive(pr, reserved=0, estimated_jobs=1, policy=policy())[0])

    def test_budget_does_not_reset(self):
        p = policy()
        b = {"policy_id": "x", "attempts_used": 0}
        stops = []
        for _ in range(3):
            b, stops = capacity.charge_attempt(b, cluster="link-error", progress="new_causal_evidence", policy=p)
        self.assertTrue(any("cluster" in s for s in stops))
        b2, stops2 = capacity.charge_attempt({"policy_id": "x", "attempts_used": 0}, cluster="a",
                                             progress="none", policy=p)
        b2, stops2 = capacity.charge_attempt(b2, cluster="b", progress="none", policy=p)
        self.assertTrue(any("no progress" in s for s in stops2))
        self.assertEqual(b2["attempts_used"], 2)


class TestRecovery(unittest.TestCase):
    def op(self, kind="branch_update"):
        return recovery.plan(contribution_id="c/1", revision=3, kind=kind, policy_version="p",
                             reason_ids=["fail-1"], target={"repository": "riseproject-upstreaming/proj",
                                                            "ref": "riscv64", "expected_head": SHA_A},
                             proposed={"commit": SHA_B, "tree": "1" * 40, "parents": [SHA_A]}, now=NOW)

    def test_deterministic_id(self):
        self.assertEqual(self.op()["operation_id"], self.op()["operation_id"])

    def test_lost_receipt_discovered_not_repeated(self):
        op = recovery.mark_applying(self.op(), NOW)
        op = recovery.mark_result(op, response_ok=None, external_ids=None, now=NOW)
        self.assertEqual(op["status"], "uncertain")
        with self.assertRaises(recovery.RecoveryError):
            recovery.mark_applying(op, NOW)  # no second effect
        r = recovery.discover_branch(op, {"head": SHA_B})
        self.assertEqual(r, "confirmed")
        r2 = recovery.discover_branch(op, {"head": "9" * 40, "tree": "1" * 40, "parents": [SHA_A]})
        self.assertEqual(r2, "confirmed")  # signed replay changed the SHA
        self.assertEqual(recovery.discover_branch(op, {"head": "8" * 40, "tree": "7" * 40}), "unrelated")
        op = recovery.record_discovery(op, r, "found", NOW)
        self.assertEqual(op["status"], "confirmed")

    def test_absence_is_not_nonlaunch(self):
        op = recovery.mark_result(recovery.mark_applying(self.op("ci_dispatch"), NOW),
                                  response_ok=None, external_ids=None, now=NOW)
        for _ in range(6):
            op = recovery.record_discovery(op, "absent", "none", NOW)
        self.assertEqual(op["status"], "uncertain")
        self.assertFalse(recovery.releases_capacity(op))
        later = T + timedelta(hours=25)
        self.assertIn("owner_review_required", recovery.alerts(op, later))

    def test_schedule(self):
        op = recovery.mark_result(recovery.mark_applying(self.op(), NOW), response_ok=None,
                                  external_ids=None, now=NOW)
        p = policy()
        self.assertEqual(recovery.next_discovery_at(op, p), T + timedelta(minutes=1))
        op = recovery.record_discovery(op, "absent", "", NOW)
        self.assertEqual(recovery.next_discovery_at(op, p), T + timedelta(minutes=5))

    def test_resolve_requires_evidence(self):
        op = recovery.mark_result(recovery.mark_applying(self.op("ci_dispatch"), NOW),
                                  response_ok=None, external_ids=None, now=NOW)
        c = commands.parse(f"/upstreaming resolve-operation operation={op['operation_id']} "
                           "disposition=not-launched evidence=ev-9")
        with self.assertRaises(recovery.RecoveryError):
            recovery.resolve(op, c, actor=OWNER, command_id="x", evidence=None, now=NOW)
        ev = {"evidence_id": "ev-9", "kind": "resolution"}
        done = recovery.resolve(op, c, actor=OWNER, command_id="x", evidence=ev, now=NOW)
        self.assertEqual(done["status"], "not_launched")
        self.assertTrue(recovery.releases_capacity(done))


def pyfile(name, yanked=False):
    return {"filename": name, "yanked": yanked, "digests": {"sha256": "0" * 64}}


class TestRelease(unittest.TestCase):
    rows = [release.Row("cp312", "cp312", "manylinux", (2, 39)),
            release.Row("cp313", "cp313", "manylinux", (2, 39)),
            release.Row("cp313", "cp313t", "manylinux", (2, 39)),
            release.Row("cp312", "cp312", "musllinux", (1, 2))]

    def test_abi3_compressed_and_free_threaded(self):
        files = [pyfile("p-1.0-cp312-abi3-manylinux_2_39_riscv64.whl"),
                 pyfile("p-1.0-cp313-cp313t-manylinux_2_39_riscv64.whl"),
                 pyfile("p-1.0-cp312-cp312-musllinux_1_2_riscv64.musllinux_1_2_x86_64.whl")]
        cov = release.coverage(files, "1.0", self.rows)
        self.assertEqual(cov.missing, [])
        self.assertTrue(cov.complete)

    def test_floor_yank_and_universal(self):
        files = [pyfile("p-1.0-cp312-cp312-manylinux_2_41_riscv64.whl"),
                 pyfile("p-1.0-cp313-cp313-manylinux_2_39_riscv64.whl", yanked=True),
                 pyfile("p-1.0-py3-none-any.whl")]
        cov = release.coverage(files, "1.0", self.rows)
        self.assertIn("cp312-cp312-manylinux_2_39", cov.missing)   # newer floor does not satisfy
        self.assertIn("cp313-cp313-manylinux_2_39", cov.missing)   # yanked
        self.assertFalse(cov.complete)
        uni = release.coverage(files, "1.0", self.rows, allow_universal=True)
        self.assertEqual(uni.missing, [])

    def test_select_release(self):
        rel = {"0.9": [pyfile("a")], "1.0rc1": [pyfile("b")], "1.0": [pyfile("c", yanked=True)],
               "1.1": [pyfile("d")]}
        self.assertEqual(release.select_release(rel, minimum="0.9"), ["0.9", "1.1"])


class TestTriggers(unittest.TestCase):
    def test_semantics(self):
        doc = {"on": {"push": {"branches": ["main"], "paths": ["docs/**", "!docs/x/**"]}}}
        self.assertTrue(triggers.push_triggers(doc, ["docs/a.md"])[0])
        self.assertFalse(triggers.push_triggers(doc, ["docs/x/a.md"])[0])
        self.assertFalse(triggers.push_triggers(doc, ["upstreaming-state/a.json"])[0])
        self.assertTrue(triggers.push_triggers({True: "push"}, ["a"])[0])
        self.assertFalse(triggers.push_triggers({True: {"push": {"tags": ["v*"]}}}, ["a"])[0])
        self.assertEqual(triggers.classify_commit(["upstreaming-state/a", "ci_scripts/b"]), "mixed")

    def test_repository_state_only_push_triggers_nothing(self):
        root = Path(__file__).resolve().parents[2]
        findings = triggers.audit(root / ".github/workflows", ["upstreaming-state/contributions/x.json"])
        self.assertEqual([f.workflow for f in findings if f.triggered], [])
        self.assertEqual(triggers.workflow_run_consumers(root / ".github/workflows"),
                         ["upstreaming-controller.yml"])


class TestTick(unittest.TestCase):
    def test_idle_tick_selects_nothing(self):
        rec = contribution(activity="waiting_ci")
        res = controller.tick(contributions={"a": rec}, operations={}, consumed={}, projects={},
                              policy=policy(), inputs=controller.Inputs(now=T))
        self.assertEqual(res.requested_effects, [])
        self.assertEqual(res.staged, [])

    def test_pause_processed_before_work_and_unauthorized_ignored(self):
        rec = contribution(activity="fix_needed")
        cid = rec["contribution_id"]
        pressure = capacity.Pressure(ok=True)
        inputs = controller.Inputs(now=T, pressure=pressure, comments=[
            {"issue_number": 12, "comment": comment(
                f"/upstreaming pause contribution={cid} revision=0 reason=r", cid=5)},
        ])
        res = controller.tick(contributions={"a": rec}, operations={}, consumed={}, projects={},
                              policy=policy(), inputs=inputs)
        self.assertEqual(res.requested_effects, [])
        self.assertTrue(any(k == "contributions" and r["paused"] for k, r in res.staged))

    def test_repair_selected_with_capacity_only(self):
        rec = contribution(activity="fix_needed")
        none = controller.tick(contributions={"a": rec}, operations={}, consumed={}, projects={},
                               policy=policy(), inputs=controller.Inputs(now=T))
        self.assertEqual(none.requested_effects, [])
        self.assertIn("no expensive admission", none.report["deferred"][0]["why"])
        res = controller.tick(contributions={"a": rec}, operations={}, consumed={}, projects={},
                              policy=policy(), inputs=controller.Inputs(now=T, pressure=capacity.Pressure(ok=True)))
        self.assertEqual(len(res.requested_effects), 1)
        eff = res.requested_effects[0]
        self.assertEqual(eff["effect_contract"]["ref"], "riscv64")
        self.assertEqual(eff["expected_head"], SHA_A)

    def test_uncertain_operation_holds_work(self):
        rec = contribution(activity="fix_needed")
        op = recovery.plan(contribution_id=rec["contribution_id"], revision=0, kind="branch_update",
                           policy_version="p", reason_ids=[], target={"repository": "r"}, now=NOW)
        op["status"] = "uncertain"
        res = controller.tick(contributions={"a": rec}, operations={op["operation_id"]: op}, consumed={},
                              projects={}, policy=policy(),
                              inputs=controller.Inputs(now=T, pressure=capacity.Pressure(ok=True)))
        self.assertEqual(res.requested_effects, [])

    def test_dispatch_once_per_task_then_timeout(self):
        from datetime import timedelta
        from upstreaming import reconcile
        rec = contribution(phase="queued", activity="idle")
        contribs = {"c": rec}
        dispatched = []
        for i in range(4):
            snap = reconcile.Snapshot(contributions=contribs, operations={}, consumed={}, projects={}, evidence={})
            out = reconcile.tick(None, snap, policy=policy(read_only=False), now=T + timedelta(minutes=15 * i),
                                 publications=[], pressure=capacity.Pressure(ok=True), observe=False)
            dispatched += [e["task"] for e in out.report["requested_effects"]]
            for k, r in out.staged:
                if k == "contributions":
                    contribs = {"c": r}
        self.assertEqual(dispatched, ["investigation"])
        self.assertEqual(contribs["c"]["phase"], "investigation")
        self.assertEqual(contribs["c"]["activity"], "agent_running")
        # No outcome for longer than the deadline: wait for a human, never re-dispatch.
        snap = reconcile.Snapshot(contributions=contribs, operations={}, consumed={}, projects={}, evidence={})
        out = reconcile.tick(None, snap, policy=policy(read_only=False), now=T + timedelta(hours=7),
                             publications=[], pressure=capacity.Pressure(ok=True), observe=False)
        self.assertEqual(out.report["requested_effects"], [])
        self.assertEqual(len(out.report["timed_out_work"]), 1)
        final = [r for k, r in out.staged if k == "contributions"][-1]
        self.assertEqual((final["activity"], final["active_work"]), ("waiting_human", None))

    def test_investigation_outcome_auto_admits_development(self):
        from upstreaming import reconcile
        from upstreaming.tests.test_dossier_gate import dossier
        rec = contribution(phase="investigation", activity="agent_running")
        rec["active_work"] = {"dedupe_key": "k", "task": "investigation", "revision": 0,
                              "requested_at": NOW, "deadline_at": NOW}
        pub = {"status": "investigation", "task": {"contribution_id": rec["contribution_id"], "revision": 0},
               "worker_run_id": "7", "publication_artifact_id": 3,
               "dossier": dossier(), "proposal": {"diagnosis": "Bounded wheel integration work is actionable."},
               "artifact": {"digest": "sha256:" + "0" * 64}}
        legacy = dict(pub, publication_artifact_id=2, worker_run_id="6", dossier={"legacy": "missing decision"})
        snap = reconcile.Snapshot(contributions={"c": rec}, operations={}, consumed={}, projects={}, evidence={})
        out = reconcile.tick(None, snap, policy=policy(read_only=False), now=T, publications=[legacy, pub],
                             pressure=capacity.Pressure(ok=True), observe=False)
        ev = [r for k, r in out.staged if k == "evidence"]
        self.assertEqual(ev[0]["kind"], "dossier")
        self.assertEqual(ev[0]["data"], dossier())
        final = [r for k, r in out.staged if k == "contributions"][-1]
        self.assertEqual(final["dossier_evidence_id"], ev[0]["evidence_id"])
        self.assertEqual((final["phase"], final["activity"], final["revision"]), ("provisioning", "waiting_capacity", 1))
        self.assertEqual(final["admission_class"], "configuration_integration")
        self.assertEqual(final["scope_paths"], [".github/workflows/*"])
        self.assertIsNone(final["pending_human_action"])
        self.assertIsNone(final["proposal_artifact"])
        self.assertEqual(len(out.report["provision_requests"]), 1)
        self.assertTrue(any(item.get("ignored") == "superseded publication artifact"
                            for item in out.report["publications"]))
        self.assertEqual(out.report["requested_effects"], [])

    def test_investigation_can_park_without_human_gate(self):
        from upstreaming import reconcile
        from upstreaming.tests.test_dossier_gate import dossier
        rec = contribution(phase="investigation", activity="agent_running")
        rec["active_work"] = {"dedupe_key": "k", "task": "investigation", "revision": 0,
                              "requested_at": NOW, "deadline_at": NOW}
        research = dossier()
        research["proposal"].update(decision="park", admission_class=None, allowed_paths=[],
                                    rationale="No concrete upstream patch is currently actionable; retain verified evidence and wait for a new prerequisite.")
        pub = {"status": "investigation", "task": {"contribution_id": rec["contribution_id"], "revision": 0},
               "worker_run_id": "8", "publication_artifact_id": 4, "dossier": research,
               "proposal": {"diagnosis": "No actionable patch."}, "artifact": {"digest": "sha256:" + "1" * 64}}
        snap = reconcile.Snapshot(contributions={"c": rec}, operations={}, consumed={}, projects={}, evidence={})
        out = reconcile.tick(None, snap, policy=policy(read_only=False), now=T, publications=[pub],
                             pressure=capacity.Pressure(ok=True), observe=False)
        final = [r for k, r in out.staged if k == "contributions"][-1]
        self.assertEqual((final["phase"], final["activity"], final["active_work"], final["revision"]),
                         ("parked", "idle", None, 1))
        self.assertIn("No concrete upstream patch", final["parked_reason"])
        self.assertEqual(out.report["provision_requests"], [])

    def test_command_resolves_contribution_from_issue(self):
        rec = contribution(activity="waiting_ci")
        res = controller.tick(contributions={"a": rec}, operations={}, consumed={}, projects={}, policy=policy(),
                              inputs=controller.Inputs(now=T, comments=[
                                  {"issue_number": 12, "comment": comment('/upstreaming pause reason="test"', cid=7)},
                                  {"issue_number": 999, "comment": comment("/upstreaming pause", cid=8)},
                                  {"issue_number": 12, "comment": comment(
                                      "/upstreaming pause contribution=other--x/1", cid=9)}]))
        by = {c["comment"]: c for c in res.report["commands"]}
        self.assertEqual(by[7]["result"], "accepted")
        self.assertEqual(by[8]["result"], "rejected")
        self.assertIn("tracks no contribution", by[8]["reason"])
        self.assertIn("this issue tracks", by[9]["reason"])
        receipt = [r for k, r in res.staged if k == "commands" and r["comment_id"] == 7][0]
        self.assertEqual((receipt["contribution_id"], receipt["revision"]), (rec["contribution_id"], 0))
        self.assertTrue([r for k, r in res.staged if k == "contributions"][-1]["paused"])

    def test_intake_creates_queued_contribution(self):
        from upstreaming.tests.test_commands_intake import issue
        res = controller.tick(contributions={}, operations={}, consumed={}, projects={},
                              policy=policy(), inputs=controller.Inputs(
                                  now=T, issues=[issue()], acceptances={77: OWNER["id"]}))
        kinds = [k for k, _ in res.staged]
        self.assertIn("contributions", kinds)
        self.assertIn("projects", kinds)
        # Investigation is selected; it needs no write admission.
        self.assertEqual(res.requested_effects[0]["effect_contract"], {"kind": "none"})


if __name__ == "__main__":
    unittest.main()


class TestPauseOnFreshRequest(unittest.TestCase):
    def test_pause_posted_with_the_request_stops_the_first_dispatch(self):
        from upstreaming.tests.test_commands_intake import issue
        iss = issue(actor={"id": 1001, "login": "owner"}, number=4935)
        res = controller.tick(contributions={}, operations={}, consumed={}, projects={}, policy=policy(),
                              inputs=controller.Inputs(now=T, issues=[iss], pressure=capacity.Pressure(ok=True),
                                                       comments=[{"issue_number": 4935, "comment": comment(
                                                           '/upstreaming pause reason="test"', cid=5)}]))
        self.assertEqual(res.report["commands"][0]["result"], "accepted")
        self.assertEqual(res.requested_effects, [])
        self.assertTrue([r for k, r in res.staged if k == "contributions"][-1]["paused"])
