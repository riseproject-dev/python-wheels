# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Only an exact verified Result becomes an idempotent issue comment."""
import unittest
from unittest.mock import patch

from upstreaming import dossier_comment
from upstreaming.tests.test_dossier_gate import dossier, proposal, task


class TestDossierComment(unittest.TestCase):
    def result(self):
        return {"work_id": "w" * 64, "claim_id": "c" * 64, "artifact_id": 42,
                "digest": "sha256:" + "0" * 64}

    def task(self):
        value = task()
        value["tracking_issue"] = 12
        return value

    def test_render_is_readable_bounded_and_exact_result_marked(self):
        body = dossier_comment.render(dossier(), self.task(), self.result())
        self.assertIn("## Upstreaming investigation result", body)
        self.assertIn("### Research coverage", body)
        self.assertIn("Verified native Result", body)
        self.assertIn(dossier_comment.marker(self.task(), self.result()), body)
        self.assertLess(len(body.encode()), 60_000)

    def test_missing_result_identity_is_rejected(self):
        result = self.result(); del result["claim_id"]
        with self.assertRaises(dossier_comment.CommentError):
            dossier_comment.publish(dossier(), proposal(), self.task(), result, "token", "9")

    def test_existing_exact_result_comment_is_reused(self):
        result = self.result()
        body = dossier_comment.render(dossier(), self.task(), result)
        comment = {"id": 44, "body": body,
                   "html_url": "https://github.com/riseproject-dev/python-wheels/issues/12#issuecomment-44"}
        calls = []
        def fake(method, path, token, payload=None):
            calls.append((method, path))
            return [comment] if path.endswith("?per_page=100") else comment
        with patch("upstreaming.dossier_comment.request", side_effect=fake):
            receipt = dossier_comment.publish(dossier(), proposal(), self.task(), result, "token", "99")
        self.assertEqual(receipt["comment_id"], 44)
        self.assertFalse(any(method == "POST" for method, _ in calls))
