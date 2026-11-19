# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Administrative fork provisioning is workflow-only, scoped and recoverable."""
import base64
import copy
from datetime import datetime
import unittest

from upstreaming import capacity, collect, commands, controller, lifecycle, provisioning, reconcile, recovery
from upstreaming.tests.helpers import NOW, SHA_A, SHA_B, SHA_C, contribution, policy

FORK = "riseproject-upstreaming/proj"
UP = "example/proj"


def request():
    rec = contribution(phase="provisioning", activity="waiting_human", dossier_evidence_id="dossier-1",
                       scope_paths=[".github/workflows/*"], fork=None)
    op = recovery.plan(contribution_id=rec["contribution_id"], revision=rec["revision"], kind="fork_provision",
                       policy_version="test", reason_ids=["dossier-1"],
                       target={"repository": FORK, "repository_id": None, "ref": "riscv64", "base_sha": SHA_C, "expected_head": None},
                       proposed={"commit": SHA_C, "marker": "provision"}, now=NOW)
    rec["active_operation_id"] = op["operation_id"]
    return rec, op


class Api:
    def __init__(self, exists=True, head=None):
        self.exists, self.head = exists, head
        self.writes = []
        self.parent = 1
        self.defaults = {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False}
        self.actions = {"enabled": True, "allowed_actions": "all"}
        self.workflows_registered = False
        self.deny_settings = False

    def fork(self):
        return {"id": 2, "full_name": FORK, "fork": True, "archived": False, "default_branch": "main",
                "parent": {"id": self.parent, "full_name": UP}}

    def get(self, path):
        if path == f"/repos/{UP}":
            return {"id": 1, "full_name": UP, "default_branch": "main"}
        if path == f"/repos/{UP}/git/commits/{SHA_C}":
            return {"sha": SHA_C}
        if path == f"/repos/{FORK}":
            if not self.exists:
                raise collect.CollectError("HTTP 404")
            return self.fork()
        if path == f"/repos/{FORK}/branches/riscv64":
            if self.head is None:
                raise collect.CollectError("HTTP 404")
            return {"commit": {"sha": self.head, "commit": {"tree": {"sha": "d" * 40}}, "parents": []}}
        if path == f"/repos/{FORK}/actions/permissions/workflow":
            return self.defaults
        if path == f"/repos/{FORK}/actions/permissions":
            return self.actions
        if path == f"/repos/{FORK}/actions/workflows?per_page=100":
            workflows = ([{"path": ".github/workflows/wheels.yml", "state": "disabled_manually"},
                          {"path": ".github/workflows/publish.yml", "state": "active"}]
                         if self.workflows_registered else [])
            return {"total_count": len(workflows), "workflows": workflows}
        if path == f"/repos/{FORK}/contents/.github/workflows?ref=main":
            return [{"type": "file", "name": "wheels.yml", "path": ".github/workflows/wheels.yml"},
                    {"type": "file", "name": "publish.yml", "path": ".github/workflows/publish.yml"}]
        if path.startswith(f"/repos/{FORK}/contents/"):
            text = "name: Wheel tests\npermissions: {contents: read}\njobs: {}\n"
            if "publish.yml" in path:
                text = "permissions: {contents: write}\njobs: {}\n"
            return {"type": "file", "encoding": "base64", "content": base64.b64encode(text.encode()).decode()}
        raise AssertionError(path)

    def write(self, method, path, body):
        self.writes.append((method, path, copy.deepcopy(body)))
        if self.deny_settings and "/actions/permissions" in path:
            raise provisioning.ProvisionError("HTTP 403")
        if path == f"/repos/{UP}/forks":
            self.exists = True
            return self.fork()
        if path == f"/repos/{FORK}/git/refs":
            self.head = body["sha"]
        if path == f"/repos/{FORK}/actions/permissions/workflow":
            self.defaults = dict(body)
        if path == f"/repos/{FORK}/actions/permissions":
            was_enabled = self.actions.get("enabled")
            self.actions = dict(body)
            if was_enabled is False and body.get("enabled") is True:
                self.workflows_registered = True
        return {}


class TestProvisioning(unittest.TestCase):
    def test_literal_false_publication_job_is_safe_but_active_publisher_is_not(self):
        workflow = {"permissions": {"contents": "read"}, "jobs": {"build": {"steps": []},
                    "publish": {"if": False, "permissions": {"id-token": "write"},
                                "steps": [{"uses": "pypa/gh-action-pypi-publish@v1"}]}}}
        self.assertFalse(provisioning._workflow_unsafe(workflow, "jobs: {}"))
        workflow["jobs"]["publish"].pop("if")
        self.assertTrue(provisioning._workflow_unsafe(workflow, "jobs: {}"))

    def test_create_and_exact_base_without_project_execution(self):
        rec, op = request()
        api = Api(exists=False)
        plan = provisioning.preflight(api, rec, op, policy(read_only=False))
        self.assertTrue(plan["create"])
        plan = provisioning.create_or_reuse(api, api, plan)
        self.assertTrue(plan["created"])
        outcome = provisioning.initialize(api, plan)
        self.assertEqual((outcome["status"], outcome["head_sha"], outcome["actions_read_only"]), ("provisioned", SHA_C, True))
        self.assertIn(("POST", f"/repos/{UP}/forks", {"organization": "riseproject-upstreaming", "name": "proj", "default_branch_only": True}), api.writes)
        self.assertIn(("POST", f"/repos/{FORK}/git/refs", {"ref": "refs/heads/riscv64", "sha": SHA_C}), api.writes)
        self.assertIn(".github/workflows/publish.yml", outcome["disabled_workflows"])
        self.assertIn(".github/workflows/wheels.yml", outcome["enabled_workflows"])
        self.assertFalse(any(path == f"/repos/{FORK}/actions/permissions/workflow"
                             for _, path, _ in api.writes))
        toggles = [body["enabled"] for method, path, body in api.writes
                   if path == f"/repos/{FORK}/actions/permissions"]
        self.assertEqual(toggles, [False, True])

    def test_existing_fork_is_adopted_not_claimed_as_created(self):
        rec, op = request()
        api = Api(head=SHA_C)
        plan = provisioning.preflight(api, rec, op, policy(read_only=False))
        self.assertFalse(plan["create"])
        plan = provisioning.create_or_reuse(api, None, plan)
        self.assertFalse(plan["created"])
        provisioning.initialize(api, plan)
        self.assertFalse(any(p.endswith("/forks") or p.endswith("/git/refs") for _, p, _ in api.writes))

    def test_collision_and_unexpected_work_rejected_before_write(self):
        rec, op = request()
        api = Api(head=SHA_B)
        plan = provisioning.preflight(api, rec, op, policy(read_only=False))
        with self.assertRaises(provisioning.ProvisionError):
            provisioning.initialize(api, plan)
        self.assertEqual(api.writes, [])
        api.parent = 99
        with self.assertRaises(provisioning.ProvisionError):
            provisioning.preflight(api, rec, op, policy(read_only=False))

    def test_permissions_or_missing_scope_never_use_a_fallback(self):
        rec, op = request()
        api = Api()
        plan = provisioning.preflight(api, rec, op, policy(read_only=False))
        api.defaults["default_workflow_permissions"] = "write"
        api.deny_settings = True
        with self.assertRaises(provisioning.ProvisionError):
            provisioning.initialize(api, plan)
        self.assertIsNone(api.head)
        for changed in (dict(rec, paused=True), dict(rec, phase="investigation"), dict(rec, dossier_evidence_id=None)):
            with self.assertRaises(provisioning.ProvisionError):
                provisioning.preflight(api, changed, op, policy(read_only=False))
        with self.assertRaises(provisioning.ProvisionError):
            provisioning.preflight(api, rec, op, policy(read_only=True))

    def test_controller_records_intent_once_and_no_model_for_provisioning(self):
        rec, _ = request()
        rec["active_operation_id"] = None
        rec["owners"] = {"primary": None, "backup": None, "submitter": None, "handoff_reviewer": None}
        args = dict(operations={}, consumed={}, projects={}, policy=policy(read_only=False),
                    inputs=controller.Inputs(now=datetime.fromisoformat(NOW), pressure=capacity.Pressure(ok=True)))
        tick = controller.tick(contributions={"c": rec}, **args)
        self.assertEqual(tick.requested_effects, [])
        self.assertEqual(len(tick.report["provision_requests"]), 1)
        op = next(r for k, r in tick.staged if k == "operations")
        current = [r for k, r in tick.staged if k == "contributions"][-1]
        self.assertEqual(current["active_operation_id"], op["operation_id"])
        args["operations"] = {op["operation_id"]: op}
        again = controller.tick(contributions={"c": current}, **args)
        self.assertEqual(again.report["provision_requests"], [])

    def test_verified_setup_advances_and_admits_initial_patch_without_base_ci(self):
        rec, op = request()
        api = Api(exists=False)
        plan = provisioning.create_or_reuse(api, api, provisioning.preflight(api, rec, op, policy(read_only=False)))
        receipt = provisioning.initialize(api, plan)
        snap = reconcile.Snapshot({"c": rec}, {op["operation_id"]: op}, {}, {}, {})
        result = reconcile.tick(api, snap, policy=policy(read_only=False), now=datetime.fromisoformat(NOW), publications=[],
                                pressure=capacity.Pressure(ok=True), provisions=[receipt])
        self.assertEqual(result.report["provisions"][0]["status"], "provisioned")
        self.assertEqual(result.report["requested_effects"][0]["task"], "development_patch")
        self.assertTrue(any(k == "operations" and r["status"] == "confirmed" for k, r in result.staged))

    def test_bare_existing_fork_cannot_bypass_workflow_provisioning(self):
        rec, _ = request()
        facts = {"fork": FORK, "fork_id": 2, "head_sha": SHA_C, "upstream_id": 1, "base_ref": "main", "base_sha": SHA_C}
        outcome = lifecycle.apply_command(rec, commands.parse(f"/upstreaming provision revision={rec['revision']}"),
                                          command_id="c", actor=rec["owners"]["primary"], now=NOW, provisioning=facts)
        self.assertFalse(outcome.accepted)
        self.assertIn("trusted upstreaming workflow", outcome.reason)

    def test_source_snapshots_bind_only_unspecified_fields(self):
        rec = contribution(phase="investigation", activity="idle")
        rec["upstream"]["repository_id"] = None
        rec["upstream"]["base_ref"] = None
        rec["upstream"]["base_sha"] = None
        source = {"repository_id": 1, "base_ref": "main", "base_sha": SHA_C}
        args = dict(contributions={"c": rec}, operations={}, consumed={}, projects={}, policy=policy(read_only=False),
                    inputs=controller.Inputs(now=datetime.fromisoformat(NOW), pressure=capacity.Pressure(ok=True), upstream_snapshots={UP: source}))
        tick = controller.tick(**args)
        bound = [r for k, r in tick.staged if k == "contributions"][-1]
        self.assertEqual(bound["upstream"], {"full_name": UP, **source})
        source["base_sha"] = SHA_A
        args["contributions"] = {"c": dict(bound, active_work=None, activity="idle")}
        next_tick = controller.tick(**args)
        current = [r for k, r in next_tick.staged if k == "contributions"][-1]
        self.assertEqual(current["upstream"]["base_sha"], SHA_C)
