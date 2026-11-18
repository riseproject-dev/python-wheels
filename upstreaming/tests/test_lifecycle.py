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

    def test_write_admission_requires_owners(self):
        rec = contribution()
        self.assertIsNone(lifecycle.write_admission(rec))
        rec["owners"]["backup"] = None
        self.assertIn("backup", lifecycle.write_admission(rec))

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
