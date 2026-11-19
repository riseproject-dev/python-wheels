# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Same-fork development PR creation is exact and idempotent."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime

from upstreaming import capacity, controller, dev_pr, reconcile, recovery
from upstreaming.tests.helpers import NOW, SHA_A, SHA_B, SHA_C, contribution, policy

FORK = "riseproject-upstreaming/proj"


def records(root: Path):
    rec = contribution(phase="development", activity="waiting_capacity", revision=2,
                       dossier_evidence_id="dossier-1", scope_paths=[".github/workflows/build.yml"])
    rec["fork"] = {"repository_id": 9, "name": FORK, "head_ref": "riscv64", "head_sha": SHA_B, "pr_number": None}
    op = recovery.plan(contribution_id=rec["contribution_id"], revision=2, kind="dev_pr_create",
                       policy_version="test", reason_ids=["dossier-1", "result-1"],
                       target={"repository": FORK, "repository_id": 9, "ref": "riscv64",
                               "expected_head": SHA_B, "base_sha": SHA_C},
                       proposed={"marker": "<!-- development-marker -->", "content_digest": "sha256:x"}, now=NOW)
    rec["active_operation_id"] = op["operation_id"]
    for kind, name, value in (("operations", op["operation_id"], op),
                              ("contributions", "example--proj--12", rec)):
        path = root / "upstreaming-state" / kind / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value))
    return rec, op


class FakeApi:
    def __init__(self, rec, op, existing=False):
        self.rec, self.op, self.existing = rec, op, existing
        self.writes = []
        self.workflow_active = existing
        self.pr = {"id": 77, "number": 4, "html_url": "https://github.com/riseproject-upstreaming/proj/pull/4",
                   "state": "open", "body": dev_pr.body(rec, op),
                   "head": {"sha": SHA_B, "ref": "riscv64", "repo": {"id": 9}},
                   "base": {"ref": "main"}}

    def get(self, path):
        if path == f"/repos/{FORK}":
            return {"id": 9, "full_name": FORK, "default_branch": "main", "archived": False,
                    "fork": True, "parent": {"id": 1, "full_name": "example/proj"}}
        if path == f"/repos/{FORK}/branches/riscv64":
            return {"commit": {"sha": SHA_B, "commit": {"tree": {"sha": "d" * 40}}, "parents": []}}
        if path == f"/repos/{FORK}/contents/.github/workflows?ref=main":
            return [{"type": "file", "name": "build.yml", "path": ".github/workflows/build.yml"}]
        if path == f"/repos/{FORK}/contents/.github/workflows/build.yml?ref=main":
            import base64
            text = "name: CI\npermissions: {contents: read}\njobs: {}\n"
            return {"type": "file", "encoding": "base64", "content": base64.b64encode(text.encode()).decode()}
        if path == f"/repos/{FORK}/actions/workflows?per_page=100":
            return {"total_count": int(self.workflow_active),
                    "workflows": ([{"path": ".github/workflows/build.yml", "state": "active"}] if self.workflow_active else [])}
        if path.startswith(f"/repos/{FORK}/pulls?"):
            return [self.pr] if self.existing else []
        if path == f"/repos/{FORK}/pulls/4":
            return self.pr
        raise AssertionError(path)

    def write(self, method, path, value):
        self.writes.append((method, path, value))
        if path.endswith("/enable"):
            self.workflow_active = True
        return {}

    def mutate(self, method, path, value):
        self.writes.append((method, path, value))
        if method == "PATCH":
            self.pr["state"] = value["state"]
        return self.pr


class TestDevelopmentPR(unittest.TestCase):
    def test_controller_records_pr_intent_before_launch(self):
        rec = contribution(phase="development", activity="waiting_ci", revision=2,
                           dossier_evidence_id="dossier-1", scope_paths=[".github/workflows/build.yml"])
        rec["fork"] = {"repository_id": 9, "name": FORK, "head_ref": "riscv64", "head_sha": SHA_B, "pr_number": None}
        rec["proposal_artifact"] = {"outcome": "published", "result_commit": "q_result", "digest": "sha256:x"}
        branch = recovery.plan(contribution_id=rec["contribution_id"], revision=2, kind="branch_update",
                               policy_version="test", reason_ids=["result"],
                               target={"repository": FORK, "repository_id": 9, "ref": "riscv64",
                                       "expected_head": SHA_A, "base_sha": SHA_A}, now=NOW)
        branch = recovery.record_discovery(branch, "confirmed", "head verified", NOW)
        rec["publication_operation_id"] = branch["operation_id"]
        tick = controller.tick(contributions={"c": rec}, operations={branch["operation_id"]: branch},
                               consumed={}, projects={}, policy={"policy_version": "test", "read_only": False,
                               "concurrency": {"coding_workers": 1}, "retries": {}, "capacity": {}},
                               inputs=controller.Inputs(now=datetime.fromisoformat(NOW), pressure=capacity.Pressure(ok=True)))
        self.assertEqual(len(tick.report["dev_pr_requests"]), 1)
        op = next(value for kind, value in tick.staged if kind == "operations")
        self.assertEqual(op["kind"], "dev_pr_create")
        current = [value for kind, value in tick.staged if kind == "contributions"][-1]
        self.assertEqual(current["active_operation_id"], op["operation_id"])

    def test_verified_receipt_records_pr_and_confirms_operation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); rec, op = records(root); api = FakeApi(rec, op, existing=True)
            snap = reconcile.Snapshot({"c": rec}, {op["operation_id"]: op}, {}, {}, {})
            receipt = {"status": "published", "operation_id": op["operation_id"],
                       "contribution_id": rec["contribution_id"], "revision": 2,
                       "repository": FORK, "repository_id": 9, "pr_id": 77, "pr_number": 4,
                       "head_sha": SHA_B, "base_ref": "main", "development_pr_run_id": 100}
            result = reconcile.tick(api, snap, policy=policy(read_only=False),
                                    now=datetime.fromisoformat(NOW), publications=[],
                                    pressure=capacity.Pressure(ok=True), observe=False,
                                    development_prs=[receipt])
            current = [value for kind, value in result.staged if kind == "contributions"][-1]
            self.assertEqual(current["fork"]["pr_number"], 4)
            self.assertIsNone(current["active_operation_id"])
            self.assertTrue(any(kind == "operations" and value["status"] == "confirmed"
                                for kind, value in result.staged))

    def test_create_and_read_back_exact_same_fork_pr(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); rec, op = records(root); api = FakeApi(rec, op)
            with patch("upstreaming.dev_pr.Api", return_value=api), \
                 patch("upstreaming.dev_pr.provisioning.WriteApi", return_value=api):
                receipt = dev_pr.publish(root, op["operation_id"], "token", "99")
            self.assertEqual((receipt["pr_number"], receipt["head_sha"]), (4, SHA_B))
            pr_write = next(call for call in api.writes if call[0] == "POST")
            self.assertEqual(pr_write[2]["head"], "riscv64")
            self.assertEqual(pr_write[2]["base"], "main")

    def test_existing_marked_pr_is_reused_without_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); rec, op = records(root); api = FakeApi(rec, op, existing=True)
            with patch("upstreaming.dev_pr.Api", return_value=api), \
                 patch("upstreaming.dev_pr.provisioning.WriteApi", return_value=api):
                receipt = dev_pr.publish(root, op["operation_id"], "token", "100")
            self.assertEqual(receipt["pr_number"], 4)
            self.assertEqual(api.writes, [])
