# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Accepted command completion reactions are durable and self-healing."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from upstreaming import command_reactions


class FakeApi:
    def __init__(self, existing=False):
        self.existing = existing
        self.posts = []

    def request(self, method, path, body=None):
        if method == "GET":
            return ([{"content": "+1", "user": {"login": "riseproject-dev[bot]"}}]
                    if self.existing else [])
        self.posts.append((path, body))
        return {"content": "+1", "user": {"login": "riseproject-dev[bot]"}}


class TestCommandReactions(unittest.TestCase):
    def root(self, td):
        root = Path(td)
        directory = root / "upstreaming-state/commands"
        directory.mkdir(parents=True)
        accepted = {"command_id": "comment-7", "comment_id": 7, "result": "accepted"}
        rejected = {"command_id": "comment-8", "comment_id": 8, "result": "rejected"}
        (directory / "comment-7.json").write_text(json.dumps(accepted))
        (directory / "comment-8.json").write_text(json.dumps(rejected))
        return root

    def test_backfills_accepted_receipts_and_ignores_rejections(self):
        with tempfile.TemporaryDirectory() as td:
            api = FakeApi()
            with patch("upstreaming.command_reactions.Api", return_value=api):
                result = command_reactions.publish(self.root(td), "token")
        self.assertEqual(result, [{"command_id": "comment-7", "comment_id": 7, "status": "created"}])
        self.assertEqual(api.posts[0][1], {"content": "+1"})
        self.assertIn("/issues/comments/7/reactions", api.posts[0][0])

    def test_existing_app_completion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            api = FakeApi(existing=True)
            with patch("upstreaming.command_reactions.Api", return_value=api):
                result = command_reactions.publish(self.root(td), "token")
        self.assertEqual(result[0]["status"], "existing")
        self.assertEqual(api.posts, [])


if __name__ == "__main__":
    unittest.main()
