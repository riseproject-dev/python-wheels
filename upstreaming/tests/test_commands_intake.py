# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Section 21: requests and commands."""

import unittest

from upstreaming import commands, intake
from upstreaming.tests.helpers import NOW, OWNER, STRANGER, comment, policy

# A "Package build request" body (.github/ISSUE_TEMPLATE/package-request.yml).
FORM = """### Package name (on PyPI)

Proj_Core

### Source repository

https://github.com/example/proj

### Version(s) requested

1.2.3

### Why is this needed?

riscv64 wheel build added in #123

### Additional context

_No response_
"""


def issue(body=FORM, actor=STRANGER, iid=77, number=12, labels=("wheel", "upstreaming-request")):
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
            "/upstreaming resume reason=r",
            "/upstreaming approve-handoff head=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
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


class TestShortCommands(unittest.TestCase):
    def test_stop_commands_need_no_ids(self):
        for body in ("/upstreaming pause", "/upstreaming pause reason=\"test\"",
                     "/upstreaming park reason=x", "/upstreaming block reason=x", "/upstreaming abandon reason=x"):
            with self.subTest(body):
                c = commands.parse(body)
                self.assertIsNone(c.contribution)
                self.assertIsNone(c.revision)

    def test_work_changing_commands_still_need_revision(self):
        self.assertEqual(commands.parse("/upstreaming resume revision=3 reason=r").revision, 3)
        self.assertEqual(commands.parse("/upstreaming restart revision=8 reason=r").revision, 8)
        self.assertEqual(commands.parse("/upstreaming refresh revision=7 reason=r").revision, 7)
        with self.assertRaises(commands.CommandError):
            commands.parse("/upstreaming resume reason=r")
        with self.assertRaises(commands.CommandError):
            commands.parse("/upstreaming restart reason=r")
        with self.assertRaises(commands.CommandError):
            commands.parse("/upstreaming park")        # park still needs a reason


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
        self.assertEqual(r.distributions, ("proj-core",))
        self.assertIsNone(r.target_branch)
        self.assertIn("riscv64 wheel build added in #123", r.notes)

    def test_real_package_request_body(self):
        # Issue #2136 as GitHub renders it.
        body = ("### Package name (on PyPI)\n\nav\n\n### Source repository\n\nhttps://github.com/PyAV-Org/PyAV\n\n"
                "### Version(s) requested\n\n18.1.0\n\n### Why is this needed?\n\nriscv64 wheel build added in #461\n\n"
                "### Additional context\n\n_No response_")
        r = intake.parse_request(issue(body=body), self.p)
        self.assertEqual((r.upstream, r.distributions), ("PyAV-Org/PyAV", ("av",)))

    def test_wheel_issue_without_upstreaming_label_is_not_intake(self):
        repo = {"full_name": "riseproject-dev/python-wheels"}
        ev = {"repository": repo, "action": "labeled", "issue": issue(labels=("wheel",))}
        self.assertEqual(intake.filter_event("issues", ev, self.p), "missing intake label")

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


class TestFreeformAndAcceptance(unittest.TestCase):
    def setUp(self):
        self.p = policy()

    def test_freeform_package_request(self):
        body = ("Work has already begun:\n\nhttps://github.com/example/proj/pull/31488\n"
                "https://github.com/example/proj/pull/31522\n")
        i = dict(issue(body=body), title="proj-core riscv64 support")
        r = intake.parse_request(i, self.p)
        self.assertEqual((r.upstream, r.distributions), ("example/proj", ("proj-core",)))
        two = dict(issue(body="https://github.com/a/b and https://github.com/c/d"), title="x riscv64 support")
        with self.assertRaises(intake.IntakeError):
            intake.parse_request(two, self.p)
        with self.assertRaises(intake.IntakeError):
            intake.parse_request(dict(issue(body=body), title="something else"), self.p)

    def test_label_added_by_owner_accepts(self):
        from upstreaming import collect

        class Api:
            def paginate(self, path, max_pages=3):
                return [{"event": "labeled", "label": {"name": "upstreaming-request"}, "actor": {"id": 99}},
                        {"event": "labeled", "label": {"name": "upstreaming-request"}, "actor": dict(OWNER)}]
        acc = collect.label_acceptances(Api(), [issue()], "upstreaming-request", [OWNER["id"]])
        self.assertEqual(acc, {77: OWNER["id"]})
        self.assertEqual(collect.label_acceptances(Api(), [issue()], "upstreaming-request", [5]), {})
