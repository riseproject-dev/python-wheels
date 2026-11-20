# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Rejected commands receive actionable App-authored tracking replies."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from upstreaming import command_feedback


class FakeApi:
    def __init__(self):
        self.created = None

    def request(self, method, path, body=None):
        if path.endswith("?per_page=100"):
            return []
        if path.endswith("/issues/comments/42"):
            return {"id": 42, "body": "/upstreaming force-develop revision=1",
                    "user": {"login": "luhenry", "id": 660779}}
        if method == "POST":
            self.created = {"id": 99, "body": body["body"], "user": {"login": "riseproject-dev[bot]"}}
            return self.created
        return self.created


class TestCommandFeedback(unittest.TestCase):
    def test_rejected_restart_has_actionable_template(self):
        receipt = {"comment_id": 42, "actor": {"login": "luhenry"}, "verb": "restart",
                   "reason": "stale revision 7, current is 8"}
        original = {"body": "/upstreaming restart revision=7 reason=r",
                    "user": {"login": "luhenry"}}
        body = command_feedback.render(receipt, original)
        self.assertIn('/upstreaming restart revision=7 reason="..."', body)

    def test_rejected_command_is_quoted_pings_author_and_shows_expected_form(self):
        receipt = {"schema_version": 1, "command_id": "comment-42", "command_version": 1,
                   "comment_id": 42, "issue_number": 1138, "actor": {"id": 660779, "login": "luhenry"},
                   "received_at": "2026-11-20T00:00:00+00:00", "content_digest": "0" * 64,
                   "verb": "", "args": {}, "contribution_id": None, "revision": None,
                   "result": "rejected", "reason": "missing fields: class, paths, reason"}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); directory = root / "upstreaming-state/commands"; directory.mkdir(parents=True)
            (directory / "comment-42.json").write_text(json.dumps(receipt))
            api = FakeApi()
            with patch("upstreaming.command_feedback.Api", return_value=api):
                out = command_feedback.publish(root, "token")
        self.assertEqual(out[0]["status"], "created")
        self.assertIn("@luhenry, this command was rejected", api.created["body"])
        self.assertIn("> /upstreaming force-develop revision=1", api.created["body"])
        self.assertIn("missing fields: class, paths, reason", api.created["body"])
        self.assertIn("force-develop revision=1 class=configuration_integration", api.created["body"])
        self.assertIn("<!-- upstreaming-command-feedback:42 -->", api.created["body"])
