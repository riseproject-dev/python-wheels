# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Section 21: lifecycle, pause/park, handoff and revision rules."""

import unittest

from upstreaming import commands, lifecycle, schemas
from upstreaming.tests.helpers import (BACKUP, NOW, OWNER, SHA_A, SHA_B, SHA_C,
                                                  contribution)


def cmd(text):
    return commands.parse(text)


def apply(rec, text, **kw):
    return lifecycle.apply_command(rec, cmd(text), command_id="comment-1", actor=OWNER, now=NOW, **kw)


CID = "example--proj/12"


class TestRevision(unittest.TestCase):
    def test_status_observation_does_not_bump(self):
        rec = contribution()
        out = lifecycle.observe_status(rec, activity="waiting_ci", next_poll_at=NOW, now=NOW)
        self.assertEqual(out.record["revision"], rec["revision"])
        out2 = lifecycle.observe_status(out.record, next_poll_at="2026-11-18T13:00:00+00:00", now=NOW)
        self.assertIsNone(out2.event)

    def test_head_change_bumps_and_invalidates(self):
        rec = contribution(last_ci_evidence_id="ev-1")
        out = lifecycle.observe_head(rec, SHA_B, now=NOW)
        self.assertEqual(out.record["revision"], rec["revision"] + 1)
        self.assertIsNone(out.record["last_ci_evidence_id"])
        self.assertIsNone(lifecycle.observe_head(out.record, SHA_B, now=NOW).event)

    def test_status_change_does_not_stale_proposal_but_head_does(self):
        rec = contribution()
        polled = lifecycle.observe_status(rec, activity="waiting_ci", now=NOW).record
        polled["activity"] = "idle"
        self.assertIsNone(lifecycle.publication_check(polled, expected_revision=rec["revision"],
                                                      expected_head=SHA_A, observed_head=SHA_A,
                                                      ref="riscv64", repository="riseproject-upstreaming/proj"))
        moved = lifecycle.observe_head(rec, SHA_B, now=NOW).record
        self.assertEqual(lifecycle.publication_check(moved, expected_revision=rec["revision"],
                                                     expected_head=SHA_A, observed_head=SHA_B,
                                                     ref="riscv64", repository="riseproject-upstreaming/proj"),
                         "work revision changed")


class TestPublicationCheck(unittest.TestCase):
    def args(self, **kw):
        a = dict(expected_revision=0, expected_head=SHA_A, observed_head=SHA_A, ref="riscv64",
                 repository="riseproject-upstreaming/proj")
        a.update(kw)
        return a

    def test_ok(self):
        self.assertIsNone(lifecycle.publication_check(contribution(), **self.args()))

    def test_rejects(self):
        cases = {
            "paused": (contribution(paused=True), {}),
            "ref": (contribution(), {"ref": "riscv64-2"}),
            "repo": (contribution(), {"repository": "riseproject-dev/proj"}),
            "head": (contribution(), {"observed_head": SHA_B}),
            "phase": (contribution(phase="release_wait"), {}),
            "parked": (contribution(phase="parked"), {}),
            "active op": (contribution(active_operation_id="op-1"), {}),
        }
        for name, (rec, kw) in cases.items():
            with self.subTest(name):
                self.assertIsNotNone(lifecycle.publication_check(rec, **self.args(**kw)))


class TestPauseParkResume(unittest.TestCase):
    def test_pause_then_stale_resume_rejected(self):
        rec = contribution()
        p = apply(rec, f"/upstreaming pause contribution={CID} revision=0 reason=r")
        self.assertTrue(p.accepted)
        self.assertTrue(p.record["paused"])
        bumped = lifecycle.observe_head(p.record, SHA_B, now=NOW).record
        stale = apply(bumped, f"/upstreaming resume contribution={CID} revision=0 reason=r")
        self.assertFalse(stale.accepted)
        ok = apply(bumped, f"/upstreaming resume contribution={CID} revision=1 reason=r")
        self.assertTrue(ok.accepted)
        self.assertFalse(ok.record["paused"])
        self.assertEqual(ok.record["revision"], 2)

    def test_stale_pause_still_honoured(self):
        rec = lifecycle.observe_head(contribution(), SHA_B, now=NOW).record
        self.assertTrue(apply(rec, f"/upstreaming pause contribution={CID} revision=0 reason=r").accepted)

    def test_park_only_explicit_resume(self):
        rec = apply(contribution(), f"/upstreaming park contribution={CID} revision=0 reason=evidence").record
        self.assertEqual(rec["phase"], "parked")
        with self.assertRaises(lifecycle.TransitionError):
            lifecycle.transition(rec, "development", cause_type="observation", cause_id=None, now=NOW)
        out = apply(rec, f"/upstreaming resume contribution={CID} revision=0 reason=\"new evidence\"")
        self.assertEqual(out.record["phase"], "investigation")  # dossier revalidation
        self.assertEqual(out.record["revision"], 1)

    def test_paused_blocks_ordinary_work_not_merge(self):
        rec = contribution(phase="upstream_review", paused=True)
        out = lifecycle.transition(rec, "release_wait", cause_type="observation", cause_id="m", now=NOW)
        self.assertEqual(out.record["phase"], "release_wait")
        with self.assertRaises(lifecycle.TransitionError):
            lifecycle.transition(contribution(phase="queued", paused=True), "investigation",
                                 cause_type="observation", cause_id=None, now=NOW)

    def test_terminal_rejects(self):
        rec = contribution(phase="abandoned")
        self.assertFalse(apply(rec, f"/upstreaming resume contribution={CID} revision=0 reason=r").accepted)


class TestRestartGeneration(unittest.TestCase):
    def test_abandoned_contribution_restarts_on_same_identity(self):
        rec = contribution(
            phase="abandoned", generation=2, revision=8, terminal_reason="old attempt",
            scope_paths=[".github/workflows/wheels.yml"], dossier_evidence_id="dossier-old",
            scope_coverage_complete=True, processed_publications=[11, 12],
            processed_review_ids=[21], processed_review_comment_ids=[22],
            processed_pr_conversation_comment_ids=[23],
            pending_feedback_evidence_ids=["review-old"],
            proposal_artifact={"artifact_id": 1}, last_ci_evidence_id="ci-old",
            budget={"policy_id": "test", "attempts_used": 3, "no_progress_streak": 2,
                    "clusters": {"x": 2}, "spent_estimate_usd_cents": 99})
        out = apply(rec, f'/upstreaming restart contribution={CID} revision=8 reason="clean start"')
        self.assertTrue(out.accepted)
        restarted = out.record
        self.assertEqual(restarted["contribution_id"], CID)
        self.assertEqual(restarted["tracking_issue"], rec["tracking_issue"])
        self.assertEqual((restarted["generation"], restarted["revision"]), (3, 9))
        self.assertEqual((restarted["phase"], restarted["activity"]), ("queued", "idle"))
        self.assertIsNone(restarted["fork"])
        self.assertIsNone(restarted["dossier_evidence_id"])
        self.assertIsNone(restarted["scope_paths"])
        self.assertIsNone(restarted["proposal_artifact"])
        self.assertEqual(restarted["processed_publications"], [11, 12])
        self.assertEqual(restarted["processed_review_comment_ids"], [])
        self.assertEqual(restarted["pending_feedback_evidence_ids"], [])
        self.assertEqual(restarted["budget"]["attempts_used"], 0)
        self.assertEqual(out.event["kind"], "command:restart")
        self.assertTrue(out.event["revision_bumped"])
        schemas.validate("contribution", restarted)

    def test_restart_is_abandoned_only_and_stale_proof(self):
        self.assertFalse(apply(contribution(),
                               f"/upstreaming restart contribution={CID} revision=0 reason=r").accepted)
        abandoned = contribution(phase="abandoned", revision=2)
        self.assertFalse(apply(abandoned,
                               f"/upstreaming restart contribution={CID} revision=1 reason=r").accepted)

    def test_restart_waits_for_writer_quiescence(self):
        for rec in (contribution(phase="abandoned", active_work={"x": 1}),
                    contribution(phase="abandoned", active_operation_id="op-1"),
                    contribution(phase="abandoned", pending_publication={"x": 1})):
            with self.subTest(record=rec):
                self.assertFalse(apply(rec,
                    f"/upstreaming restart contribution={CID} revision=0 reason=r").accepted)


class TestHandoff(unittest.TestCase):
    def test_request_needs_evidence_and_head(self):
        rec = contribution()
        self.assertFalse(apply(rec, f"/upstreaming request-handoff contribution={CID} revision=0 head={SHA_A}").accepted)
        rec["last_ci_evidence_id"] = "ev-1"
        self.assertFalse(apply(rec, f"/upstreaming request-handoff contribution={CID} revision=0 head={SHA_B}").accepted)
        out = apply(rec, f"/upstreaming request-handoff contribution={CID} revision=0 head={SHA_A}")
        self.assertTrue(out.accepted)
        self.assertEqual(out.record["phase"], "handoff")

    def _handoff(self):
        rec = contribution(phase="handoff", last_ci_evidence_id="ev-1",
                           debug_commits=[{"sha": SHA_A, "subject": "{debug} enable wheels on fork", "reason": "guard"}])
        rec["clean_head_sha"] = SHA_B
        rec["fork"]["head_sha"] = SHA_B
        return rec

    def test_approve_binds_clean_head(self):
        rec = self._handoff()
        self.assertFalse(apply(rec, f"/upstreaming approve-handoff contribution={CID} revision=0 head={SHA_A}").accepted)
        out = apply(rec, f"/upstreaming approve-handoff contribution={CID} revision=0 head={SHA_B}")
        self.assertTrue(out.accepted)
        self.assertEqual(out.record["handoff_approval"]["head"], SHA_B)

    def test_new_change_invalidates_approval(self):
        rec = apply(self._handoff(), f"/upstreaming approve-handoff contribution={CID} revision=0 head={SHA_B}").record
        moved = lifecycle.observe_head(rec, SHA_C, now=NOW).record
        self.assertIsNone(moved["handoff_approval"])

    def test_register_requires_verified_pr(self):
        rec = apply(self._handoff(), f"/upstreaming approve-handoff contribution={CID} revision=0 head={SHA_B}").record
        url = "https://github.com/example/proj/pull/9"
        text = f"/upstreaming register-upstream-pr contribution={CID} revision=0 url={url}"
        self.assertFalse(apply(rec, text).accepted)
        pr = {"id": 99, "number": 9, "html_url": url, "state": "open", "base_repository": "example/proj",
              "base_ref": "main", "head_repository": "riseproject-upstreaming/proj",
              "head_repository_id": 2, "head_ref": "riscv64", "head_sha": SHA_B}
        self.assertFalse(apply(rec, text, verified_pr=dict(pr, head_sha=SHA_C)).accepted)
        self.assertFalse(apply(rec, text, verified_pr=dict(pr, base_repository="other/proj")).accepted)
        out = apply(rec, text, verified_pr=pr)
        self.assertTrue(out.accepted)
        self.assertEqual(out.record["phase"], "upstream_review")
        self.assertIsNone(out.record["blocked_reason"])
        other = apply(rec, text, verified_pr=dict(pr, head_repository="someone/proj", head_ref="feature"))
        self.assertIn("automated revisions disabled", other.record["blocked_reason"])
        # Upstream-facing: approval survives a routine revision push.
        pushed = lifecycle.observe_head(out.record, SHA_C, now=NOW).record
        self.assertIsNotNone(pushed["handoff_approval"])


class TestMergeAndRelease(unittest.TestCase):
    def test_merge_stops_development(self):
        rec = contribution(phase="upstream_review", active_operation_id="op-1")
        out = lifecycle.transition(rec, "release_wait", cause_type="observation", cause_id="merge", now=NOW)
        self.assertIsNone(out.record["active_operation_id"])
        self.assertIsNotNone(lifecycle.publication_check(
            out.record, expected_revision=0, expected_head=SHA_A, observed_head=SHA_A,
            ref="riscv64", repository="riseproject-upstreaming/proj"))

    def test_no_shortcut_to_released(self):
        with self.assertRaises(lifecycle.TransitionError):
            lifecycle.transition(contribution(phase="upstream_review"), "released",
                                 cause_type="observation", cause_id=None, now=NOW)

    def test_write_admission_is_automatic_after_dossier_and_fork(self):
        rec = contribution()
        rec["owners"] = {"primary": None, "backup": None, "submitter": None, "handoff_reviewer": None}
        self.assertIsNone(lifecycle.write_admission(rec))
        rec["admission_class"] = None
        self.assertIn("admission class", lifecycle.write_admission(rec))

    def test_schema_rejects_wrong_ref_and_unknown_version(self):
        rec = contribution()
        rec["fork"]["head_ref"] = "riscv64-salt"
        self.assertTrue(schemas.errors("contribution", rec))
        rec = contribution(schema_version=2)
        self.assertTrue(schemas.errors("contribution", rec))


if __name__ == "__main__":
    unittest.main()


class TestStopEndsRequestedWork(unittest.TestCase):
    def test_stop_commands_clear_active_work(self):
        from upstreaming import commands as C
        from upstreaming.tests.helpers import NOW, OWNER, contribution
        rec = contribution(phase="investigation", activity="agent_running", revision=1)
        rec["active_work"] = {"dedupe_key": "k", "task": "investigation", "revision": 1,
                              "requested_at": NOW, "deadline_at": NOW, "dispatched_run_id": None}
        for body in ("/upstreaming pause", "/upstreaming abandon reason=x", "/upstreaming park reason=x",
                     "/upstreaming block reason=x"):
            out = lifecycle.apply_command(rec, C.parse(body), command_id="c", actor=dict(OWNER), now=NOW)
            self.assertTrue(out.accepted, body)
            self.assertIsNone(out.record["active_work"], body)
            self.assertNotEqual(out.record["activity"], "agent_running", body)


class TestCapacityOwnBacklog(unittest.TestCase):
    def test_other_tenants_old_pending_jobs_do_not_block(self):
        from datetime import datetime, timezone
        from upstreaming import capacity
        now = datetime(2026, 11, 18, 22, tzinfo=timezone.utc)
        job = lambda ent, created: {"job_labels": ["ubuntu-24.04-riscv"], "status": "pending",
                                     "entity_name": ent, "job_created_at": created}
        pol = {"capacity": {"max_pending_jobs_rise": 100, "max_pending_age_seconds": 7200}}
        p = capacity.observe({"jobs": [job("someone-else", "2026-11-17T00:00:00Z")]}, fetched_at=now, now=now,
                             max_age_seconds=900)
        self.assertTrue(capacity.admit_expensive(p, reserved=0, estimated_jobs=1, policy=pol)[0])
        p = capacity.observe({"jobs": [job("riseproject-upstreaming", "2026-11-17T00:00:00Z")]}, fetched_at=now,
                             now=now, max_age_seconds=900)
        self.assertFalse(capacity.admit_expensive(p, reserved=0, estimated_jobs=1, policy=pol)[0])


class TestScopeAndProvision(unittest.TestCase):
    def setUp(self):
        from upstreaming.tests.helpers import contribution
        self.rec = contribution(phase="investigation", activity="waiting_human", revision=1,
                                dossier_evidence_id="dossier-x", fork=None,
                                owners={"primary": None, "backup": None, "submitter": None,
                                        "handoff_reviewer": None}, admission_class=None)
        self.rec["upstream"]["base_sha"] = None

    def apply(self, rec, body, **kw):
        return lifecycle.apply_command(rec, commands.parse(body), command_id="c", actor=dict(OWNER), now=NOW, **kw)

    def test_approve_scope_then_provision(self):
        bk = dict(BACKUP)
        out = self.apply(self.rec, f"/upstreaming approve-scope revision=1 class=configuration_integration "
                                   f"backup={bk['login']}", backup_user=bk)
        self.assertTrue(out.accepted, out.reason)
        r = out.record
        self.assertEqual((r["phase"], r["revision"], r["owners"]["primary"]["id"], r["owners"]["backup"]["id"]),
                         ("provisioning", 2, OWNER["id"], bk["id"]))
        self.assertEqual(r["pending_human_action"]["kind"], "provision_fork")
        self.assertIsNotNone(lifecycle.write_admission(r))          # no fork yet
        bad = self.apply(r, "/upstreaming provision revision=2", provisioning={"error": "no riscv64 branch"})
        self.assertFalse(bad.accepted)
        self.assertIn("riscv64", bad.reason)
        prov = {"workflow_verified": True, "fork": "riseproject-upstreaming/proj", "fork_id": 9, "head_sha": SHA_A, "upstream_id": 1,
                "base_ref": "main", "base_sha": SHA_A}
        out = self.apply(r, "/upstreaming provision revision=2", provisioning=prov)
        self.assertTrue(out.accepted, out.reason)
        d = out.record
        self.assertEqual((d["phase"], d["activity"], d["fork"]["repository_id"], d["upstream"]["base_sha"]),
                         ("development", "idle", 9, SHA_A))
        self.assertIsNone(lifecycle.write_admission(d))
        from upstreaming import controller
        self.assertEqual(controller._actionable(d), "development_patch")

    def test_human_can_force_parked_dossier_into_automatic_development(self):
        parked = dict(self.rec, phase="parked", activity="idle", parked_reason="No current patch")
        out = self.apply(parked, '/upstreaming force-develop revision=1 class=configuration_integration '
                                 'paths=".github/workflows/*,pyproject.toml" reason="Proceed with a concrete reviewed scope."')
        self.assertTrue(out.accepted, out.reason)
        self.assertEqual((out.record["phase"], out.record["revision"], out.record["activity"]),
                         ("provisioning", 2, "idle"))
        self.assertEqual(out.record["scope_paths"], [".github/workflows/*", "pyproject.toml"])
        self.assertIsNone(out.record["parked_reason"])
        self.assertFalse(self.apply(self.rec, '/upstreaming force-develop revision=1 class=configuration_integration '
                                             'paths=".github/workflows/*" reason="Not parked."').accepted)
        self.assertFalse(self.apply(parked, '/upstreaming force-develop revision=1 class=configuration_integration '
                                             'paths="*" reason="Scope is too broad."').accepted)

    def test_approve_scope_needs_dossier_and_other_backup(self):
        bk = dict(BACKUP)
        no_dossier = dict(self.rec, dossier_evidence_id=None)
        self.assertFalse(self.apply(no_dossier, "/upstreaming approve-scope revision=1 class=configuration_integration "
                                                f"backup={bk['login']}", backup_user=bk).accepted)
        self.assertFalse(self.apply(self.rec, "/upstreaming approve-scope revision=1 class=configuration_integration "
                                              f"backup={OWNER['login']}", backup_user=dict(OWNER)).accepted)
        self.assertFalse(self.apply(self.rec, "/upstreaming approve-scope revision=1 class=configuration_integration "
                                              "backup=nobody", backup_user=None).accepted)
        with self.assertRaises(commands.CommandError):
            commands.parse("/upstreaming approve-scope revision=1 class=whatever backup=x")
        c = commands.parse('/upstreaming approve-scope revision=1 class=configuration_integration backup=x '
                           'paths=".github/workflows/*,pyproject.toml"')
        self.assertEqual(c.args["paths"], ".github/workflows/*,pyproject.toml")
