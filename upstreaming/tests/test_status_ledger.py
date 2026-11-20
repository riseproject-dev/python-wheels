# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Lifecycle issue ledger entries are concise, append-only and App-authored."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from upstreaming import lifecycle, status_ledger
from upstreaming.tests.helpers import NOW, contribution


class FakeApi:
    def __init__(self):
        self.calls = []
        self.comment = None

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith("?per_page=100"):
            return []
        if method == "POST":
            self.comment = {"id": 7, "body": body["body"], "html_url": "https://github.com/x",
                            "user": {"login": "riseproject-dev[bot]"}}
        return self.comment


class TestStatusLedger(unittest.TestCase):
    def records(self, root: Path):
        old = contribution(phase="queued", activity="idle", revision=0)
        new = dict(old, phase="parked", activity="idle", revision=1, parked_reason="No patch", updated_at=NOW)
        event = lifecycle._event(old, new, "dossier_parked", "observation", "dossier-1", NOW, True)
        event["sequence"] = 3
        cpath = root / "upstreaming-state/contributions/example--proj--12.json"
        epath = root / "upstreaming-state/events/example--proj--12/00000003.json"
        cpath.parent.mkdir(parents=True); epath.parent.mkdir(parents=True)
        cpath.write_text(json.dumps(new)); epath.write_text(json.dumps(event))
        return new, event, str(epath.relative_to(root))

    def test_render_has_short_summary_and_folded_prefilled_commands(self):
        record = contribution(phase="parked", activity="idle", revision=4, parked_reason="No patch")
        event = lifecycle._event(record, record, "dossier_parked", "observation", "d", NOW, False)
        event["sequence"] = 2
        body = status_ledger.render(event, record, "https://github.com/run")
        self.assertTrue(body.startswith("**Upstreaming r4 · parked/idle**"))
        self.assertIn("<details>", body)
        self.assertIn("<summary>Possible next commands</summary>", body)
        self.assertIn("/upstreaming force-develop revision=4", body)
        self.assertIn("<!-- upstreaming-ledger:", body)

    def test_explanation_only_ledger_does_not_claim_repair(self):
        record = contribution(phase="development", activity="fix_needed", revision=8, paused=True)
        event = lifecycle._event(record, record, "development_review_inquiry", "observation",
                                 "inquiry-1", NOW, False)
        event["sequence"] = 14
        body = status_ledger.render(event, record, "https://github.com/run")
        self.assertIn("explanation-only", body)
        self.assertIn("No repair was requested", body)
        self.assertNotIn("requested repair", body)

    def test_development_pr_ledger_offers_dossier_refresh(self):
        record = contribution(phase="development", activity="fix_needed", revision=7)
        event = lifecycle._event(record, record, "activity", "observation", None, NOW, False)
        event["sequence"] = 8
        body = status_ledger.render(event, record, "https://github.com/run")
        self.assertIn('/upstreaming refresh revision=7 reason="..."', body)

    def test_abandoned_ledger_offers_same_issue_restart(self):
        record = contribution(phase="abandoned", activity="idle", revision=8,
                              terminal_reason="restart requested")
        event = lifecycle._event(record, record, "command:abandon", "command", "c", NOW, False)
        event["sequence"] = 9
        body = status_ledger.render(event, record, "https://github.com/run")
        self.assertIn('/upstreaming restart revision=8 reason="..."', body)
        self.assertNotIn("/upstreaming resume", body)

    def test_publish_appends_one_app_authored_comment_for_written_event(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); _record, _event, path = self.records(root); api = FakeApi()
            with patch("upstreaming.status_ledger.Api", return_value=api):
                receipts = status_ledger.publish(root, {"written": [path]}, "token", "https://github.com/run")
            self.assertEqual(receipts[0]["status"], "created")
            self.assertEqual([call[0] for call in api.calls], ["GET", "POST", "GET"])
            self.assertIn("Upstreaming r1", api.comment["body"])
