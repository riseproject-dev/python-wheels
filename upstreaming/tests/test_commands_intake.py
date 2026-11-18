# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Section 21: requests and commands."""

import unittest

from upstreaming import commands, intake
from upstreaming.tests.helpers import NOW, OWNER, STRANGER, comment, policy

FORM = """### Upstream repository

https://github.com/example/proj

### PyPI distributions

Proj_Core
proj-core
proj.extra

### Upstream target branch

_No response_

### Additional notes

_No response_
"""


def issue(body=FORM, actor=STRANGER, iid=77, number=12, labels=("upstreaming-request",)):
    return {"id": iid, "number": number, "body": body, "user": dict(actor),
            "labels": [{"name": n} for n in labels]}


class TestCommandGrammar(unittest.TestCase):
    def test_valid(self):
        c = commands.parse('/upstreaming park contribution=x/1 revision=3 reason="no \\"V\\" hw"\n\nthanks')
        self.assertEqual(c.verb, "park")
        self.assertEqual(c.args["reason"], 'no "V" hw')
        self.assertEqual(c.revision, 3)

    def test_rejections(self):
        bad = [
            "> /upstreaming pause contribution=x/1 revision=1 reason=r",
            "```\n/upstreaming pause contribution=x/1 revision=1 reason=r\n```",
            "    /upstreaming pause contribution=x/1 revision=1 reason=r",
            "please /upstreaming pause contribution=x/1 revision=1 reason=r",
            "/upstreaming pause contribution=x/1 revision=1 reason=r\n/upstreaming resume contribution=x/1 revision=1 reason=r",
            "/upstreaming pause contribution=x/1 revision=1",
            "/upstreaming pause contribution=x/1 revision=1 reason=r extra=1",
            "/upstreaming pause contribution=x/1 revision=1 reason=r version=2",
            "/upstreaming explode contribution=x/1",
            "/upstreaming approve-handoff contribution=x/1 revision=1 head=abc",
            "/upstreaming register-upstream-pr contribution=x/1 revision=1 url=https://evil.example/pull/1",
            "/upstreaming pause contribution=../../etc revision=1 reason=r",
            "/upstreaming pause contribution=x/1 revision=1 revision=2 reason=r",
        ]
        for body in bad:
            with self.subTest(body=body), self.assertRaises(commands.CommandError):
                commands.parse(body)


class TestCommandAcceptance(unittest.TestCase):
    def setUp(self):
        self.p = policy()
        self.body = "/upstreaming pause contribution=x/1 revision=1 reason=r"

    def test_accept_once_and_replay(self):
        consumed = {}
        d = intake.accept_command(comment=comment(self.body), issue_number=1, event_body=self.body,
                                  policy=self.p, consumed=consumed, now=NOW)
        self.assertTrue(d.accepted)
        consumed[1] = d.receipt
        again = intake.accept_command(comment=comment(self.body), issue_number=1, event_body=None,
                                      policy=self.p, consumed=consumed, now=NOW)
        self.assertFalse(again.accepted)
        self.assertEqual(again.reason, "already consumed")

    def test_edit_after_consumption_is_reported_not_reinterpreted(self):
        consumed = {}
        d = intake.accept_command(comment=comment(self.body), issue_number=1, event_body=self.body,
                                  policy=self.p, consumed=consumed, now=NOW)
        consumed[1] = d.receipt
        edited = "/upstreaming resume contribution=x/1 revision=1 reason=r"
        e = intake.accept_command(comment=comment(edited), issue_number=1, event_body=edited,
                                  policy=self.p, consumed=consumed, now=NOW)
        self.assertFalse(e.accepted)
        self.assertIn("edited after consumption", e.reason)
        self.assertEqual(e.receipt["verb"], "pause")

    def test_event_fetch_mismatch_rejected(self):
        d = intake.accept_command(comment=comment(self.body), issue_number=1, event_body="other",
                                  policy=self.p, consumed={}, now=NOW)
        self.assertFalse(d.accepted)

    def test_unauthorized(self):
        d = intake.accept_command(comment=comment(self.body, actor=STRANGER), issue_number=1,
                                  event_body=None, policy=self.p, consumed={}, now=NOW)
        self.assertFalse(d.accepted)
        self.assertEqual(d.receipt["result"], "rejected")


class TestIntake(unittest.TestCase):
    def setUp(self):
        self.p = policy()

    def test_parse_and_normalize(self):
        r = intake.parse_request(issue(), self.p)
        self.assertEqual(r.upstream, "example/proj")
        self.assertEqual(r.distributions, ("proj-core", "proj-extra"))
        self.assertIsNone(r.target_branch)

    def test_bad_urls(self):
        for url in ["https://user:pw@github.com/a/b", "http://github.com/a/b",
                    "https://gitlab.com/a/b", "https://github.com/a/b/tree/main",
                    "https://github.com/a/b?x=1", "https://github.com/a/.."]:
            with self.subTest(url=url), self.assertRaises(intake.IntakeError):
                intake.canonical_repo(url)

    def test_oversized(self):
        with self.assertRaises(intake.IntakeError):
            intake.parse_request(issue(body=FORM + "x" * 20000), self.p)
        payload = {"repository": {"full_name": "riseproject-dev/python-wheels"}, "action": "opened",
                   "issue": issue(body="x" * 20000)}
        self.assertEqual(intake.filter_event("issues", payload, self.p), "request too large")

    def test_filter_events(self):
        repo = {"full_name": "riseproject-dev/python-wheels"}
        ok = {"repository": repo, "action": "opened", "issue": issue()}
        self.assertIsNone(intake.filter_event("issues", ok, self.p))
        self.assertIsNotNone(intake.filter_event("issues", dict(ok, action="edited"), self.p))
        self.assertIsNotNone(intake.filter_event("issues", dict(ok, issue=issue(labels=())), self.p))
        self.assertIsNotNone(intake.filter_event("issues", dict(ok, repository={"full_name": "x/y"}), self.p))
        c = {"repository": repo, "action": "created",
             "comment": {"body": "/upstreaming pause contribution=a/1 revision=0 reason=r",
                         "user": STRANGER}}
        self.assertEqual(intake.filter_event("issue_comment", c, self.p),
                         "actor is not an authorized command actor")
        c["comment"]["user"] = OWNER
        self.assertIsNone(intake.filter_event("issue_comment", c, self.p))

    def test_admission(self):
        r = intake.parse_request(issue(), self.p)
        kw = dict(policy=self.p, active_by_upstream={}, parked_upstreams=[], known_issue_ids=[],
                  requests_today_by_actor=0)
        self.assertEqual(intake.admission_decision(r, accepted_by=None, **kw)[0], "await_acceptance")
        self.assertEqual(intake.admission_decision(r, accepted_by=OWNER["id"], **kw)[0], "accept")
        self.assertEqual(intake.admission_decision(r, accepted_by=OWNER["id"],
                                                   **dict(kw, active_by_upstream={"Example/Proj": "c1"}))[0],
                         "duplicate")
        self.assertEqual(intake.admission_decision(r, accepted_by=OWNER["id"],
                                                   **dict(kw, parked_upstreams=["example/proj"]))[0],
                         "parked")
        self.assertEqual(intake.admission_decision(r, accepted_by=None,
                                                   **dict(kw, requests_today_by_actor=5))[0],
                         "rate_limited")
        self.assertEqual(intake.admission_decision(r, accepted_by=OWNER["id"],
                                                   **dict(kw, known_issue_ids=[77]))[0], "duplicate")


if __name__ == "__main__":
    unittest.main()
