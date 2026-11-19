# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Missing research cannot become a completed investigator task."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from upstreaming import capacity, collect, controller, dossier_gate, schemas, work
from upstreaming.common import sha256_text
from upstreaming.tests.helpers import NOW, contribution, policy
from datetime import datetime

ISSUE_URL = "https://github.com/riseproject-dev/python-wheels/issues/12"
REPORT_URL = "https://github.com/riseproject-dev/sw-ecosystem/blob/main/project-reports/proj.md"


def task():
    return {"task": "investigation", "contribution_id": "example--proj/12", "revision": 1, "expected_head": None,
            "context": {"tracking_issue": {"id": 5000, "number": 12, "url": ISSUE_URL,
                                           "description": "Full original issue body, including user links.",
                                           "description_digest": sha256_text("Full original issue body, including user links.")}}}


def proposal():
    return {"schema_version": 1, "contribution_id": "example--proj/12", "expected_revision": 1,
            "expected_head": None, "ref": "riscv64", "operation": "none", "outcome": "investigation",
            "progress": "new_causal_evidence", "reconstruction_base": None, "diagnosis": "Completed upstream research."}


def dossier():
    entry = {"status": "searched", "queries": ["riscv64 all states"],
             "coverage": {"complete": True, "scope": "All matching open and closed discussions reviewed, including all result pages."},
             "sources": [{"url": ISSUE_URL, "finding": "Read the description and all discussion comments."}],
             "findings": "The linked discussions establish architecture requirements and prior reviewer decisions."}
    d = {"schema_version": 1, "contribution_id": "example--proj/12", "expected_revision": 1,
         "tracking_issue_description_digest": task()["context"]["tracking_issue"]["description_digest"],
         "summary": "Research covers project history, dependencies, documentation and maintainer review decisions.",
         "research": {category: copy.deepcopy(entry) for category in dossier_gate.RESEARCH_CATEGORIES},
         "history": [], "maintainers": [{"name": "reviewer", "role": "Release maintainer and architecture reviewer", "sources": [ISSUE_URL]}],
         "dependency_graph": {"tool": "project_graph_query", "success": True, "canonical_project": "proj",
                              "query": {"cypher": "MATCH (p) RETURN p"},
                              "result": {"projects": ["proj"]},
                              "assessment": "Compared the canonical graph project with build and runtime dependencies."},
         "ecosystem_report": {"status": "available", "url": REPORT_URL, "revision": "abc123",
                              "riscv64_status": "The report documents native support gaps and the current upstream CI status.",
                              "used_findings": {
                                  "support_status": "Used and verified the report's riscv64 support-status findings.",
                                  "dependencies": "Used the report's graph findings and checked them against the build configuration.",
                                  "prior_work_and_blockers": "Followed and reviewed the report's linked prior contributions and architecture blockers."},
                              "corroboration_and_conflicts": [ISSUE_URL]},
         "proposal": {"decision": "develop", "rationale": "Add bounded wheel CI configuration following the verified architecture precedent.",
                      "admission_class": "configuration_integration", "allowed_paths": [".github/workflows/*"]}}
    d["research"]["ecosystem_report"]["sources"][0]["url"] = REPORT_URL
    return d


class TestDossierCompleteness(unittest.TestCase):
    def test_complete_dossier_accepted(self):
        dossier_gate.validate(dossier(), proposal(), task())

    def test_agent_preflight_cli_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, value in (("dossier", dossier()), ("proposal", proposal()), ("task", task())):
                (root / f"{name}.json").write_text(json.dumps(value))
            command = [sys.executable, "-m", "upstreaming.dossier_gate",
                       "--dossier", str(root / "dossier.json"), "--proposal", str(root / "proposal.json"),
                       "--task", str(root / "task.json")]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            invalid = dossier(); invalid["history"] = [[ISSUE_URL, "open"]]
            (root / "dossier.json").write_text(json.dumps(invalid))
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_development_decision_requires_bounded_scope_and_park_is_empty(self):
        for path in ("*", "**", "../setup.py", "/tmp/setup.py", ".git/config", "src/**"):
            d = dossier(); d["proposal"]["allowed_paths"] = [path]
            with self.assertRaises((dossier_gate.DossierError, schemas.SchemaError), msg=path):
                dossier_gate.validate(d, proposal(), task())
        d = dossier()
        d["proposal"].update(decision="park", admission_class=None, allowed_paths=[],
                             rationale="No concrete patch is actionable until a documented external prerequisite is resolved.")
        dossier_gate.validate(d, proposal(), task())
        d["proposal"]["allowed_paths"] = ["pyproject.toml"]
        with self.assertRaises(schemas.SchemaError):
            dossier_gate.validate(d, proposal(), task())

    def test_every_category_is_required(self):
        for category in dossier_gate.RESEARCH_CATEGORIES:
            d = dossier()
            del d["research"][category]
            with self.assertRaises(schemas.SchemaError, msg=category):
                dossier_gate.validate(d, proposal(), task())

    def test_inaccessible_partial_or_unsupported_research_rejected(self):
        for update in ({"status": "unavailable"}, {"sources": []}, {"queries": []},
                       {"coverage": {"complete": False, "scope": "Only the first search page was read."}}):
            d = dossier()
            d["research"]["upstream_pull_requests"].update(update)
            with self.assertRaises(schemas.SchemaError):
                dossier_gate.validate(d, proposal(), task())
        d = dossier()
        d["research"]["upstream_issues"].update(status="not_applicable", justification="Did not attempt an upstream issue search for this project.")
        with self.assertRaises(dossier_gate.DossierError):
            dossier_gate.validate(d, proposal(), task())

    def test_missing_graph_or_unused_report_rejected(self):
        d = dossier()
        del d["dependency_graph"]
        with self.assertRaises(schemas.SchemaError):
            dossier_gate.validate(d, proposal(), task())
        d = dossier()
        d["research"]["ecosystem_report"]["sources"][0]["url"] = ISSUE_URL
        with self.assertRaises(dossier_gate.DossierError):
            dossier_gate.validate(d, proposal(), task())
        d = dossier()
        d["ecosystem_report"] = {"status": "absent"}
        with self.assertRaises(dossier_gate.DossierError):
            dossier_gate.validate(d, proposal(), task())
        d["research"]["ecosystem_report"].update(status="not_applicable", justification="Searched report index, canonical name, repository and synonyms; no report exists.")
        dossier_gate.validate(d, proposal(), task())

    def test_stale_issue_and_task_identity_rejected(self):
        for field, value in (("expected_revision", 0), ("contribution_id", "other/12"),
                             ("tracking_issue_description_digest", "0" * 64)):
            d = dossier()
            d[field] = value
            with self.assertRaises(dossier_gate.DossierError):
                dossier_gate.validate(d, proposal(), task())
        d = dossier()
        d["research"]["tracking_issue"]["sources"][0]["url"] = REPORT_URL
        with self.assertRaises(dossier_gate.DossierError):
            dossier_gate.validate(d, proposal(), task())

    def test_exact_claim_staging_and_cancellation(self):
        assignment = {"version": 3, "dispatch_id": "d1", "claims": [{"claim_id": "c1", "work_id": "w1", "handle": "h1", "work": task()}]}
        identity = {"dispatch_id": "d1", "claim_id": "c1", "work_id": "w1", "claim_handle": "h1"}
        ns = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(ns, "7a521a54e115fee86af74f06e7e1636613643950ecc9f57a6e82039311a49d94")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = root / "claims" / ns / "upstreaming-out"
            stage.mkdir(parents=True)
            (stage / "dossier.json").write_text(json.dumps(dossier()))
            (stage / "proposal.json").write_text(json.dumps(proposal()))
            finish = root / "work-queue.finish.jsonl"
            finish.write_text(json.dumps({"version": 3, "kind": "finish", "claim_handle": "h1", "parameters": {"outcome": "completed"}}))
            self.assertIn("eligible", dossier_gate.check_stage(assignment, root, root))
            (stage / "dossier.json").unlink()
            with self.assertRaises(dossier_gate.DossierError):
                dossier_gate.check_stage(assignment, root, root)
            finish.write_text(json.dumps({"version": 3, "kind": "finish", "claim_handle": "h1", "parameters": {"outcome": "cancelled"}}))
            self.assertIn("cancelled", dossier_gate.check_stage(assignment, root, root))
            finish.write_text(finish.read_text() + "\n" + json.dumps({"version": 3, "kind": "finish", "claim_handle": "h1", "parameters": {"outcome": "completed"}}))
            with self.assertRaises(dossier_gate.DossierError):
                dossier_gate.check_stage(assignment, root, root)

    def test_symlinked_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "link").symlink_to(root, target_is_directory=True)
            with self.assertRaises(dossier_gate.DossierError):
                dossier_gate._read(root, Path("link/anything.json"))


class TestImmutableTrackingIssue(unittest.TestCase):
    def test_full_description_url_and_links_frozen_into_work(self):
        body = "### Additional context\n\nhttps://github.com/example/proj/pull/31488\n" + "user context\n" * 500
        rec = contribution(phase="investigation", activity="idle")
        issue = {"id": 5000, "number": 12, "body": body}
        result = controller.tick(contributions={"c": rec}, operations={}, consumed={}, projects={}, policy=policy(read_only=False),
                                 inputs=controller.Inputs(now=datetime.fromisoformat(NOW), pressure=capacity.Pressure(ok=True),
                                                          tracking_issues={12: issue}))
        claimed = [r for k, r in result.staged if k == "contributions"][-1]
        node = work.node(result.requested_effects[0], claimed, control_repo_id="7", allowed_paths=[".github/workflows/*"])
        frozen = node["payload"]["context"]["tracking_issue"]
        self.assertEqual(frozen["description"], body)
        self.assertEqual(frozen["url"], ISSUE_URL)
        issue["body"] = "subsequent edit"
        self.assertEqual(node["payload"]["context"]["tracking_issue"]["description"], body)

    def test_issue_identity_and_oversized_description_rejected_not_truncated(self):
        expected = {"id": 5000, "number": 12}
        with self.assertRaises(collect.CollectError):
            collect.tracking_issue_context({"id": 5001, "number": 12, "body": "x"}, expected)
        with self.assertRaises(collect.CollectError):
            collect.tracking_issue_context({"id": 5000, "number": 12, "body": "x" * 16385}, expected)
