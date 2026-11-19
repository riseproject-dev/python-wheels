# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Prevent accidental loss of the investigator and CI runtime boundaries."""
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).parents[2]
WF = ROOT / ".github/workflows"


def source(name):
    return yaml.safe_load((WF / f"{name}.md").read_text().split("---", 2)[1])


def run_scripts(value):
    if isinstance(value, dict):
        if isinstance(value.get("run"), str):
            yield value["run"]
        for child in value.values():
            yield from run_scripts(child)
    elif isinstance(value, list):
        for child in value:
            yield from run_scripts(child)


class TestWorkflowContracts(unittest.TestCase):
    def test_only_investigator_unsandboxed(self):
        investigator = source("upstreaming-investigator")
        self.assertFalse(investigator["strict"])
        self.assertFalse(investigator["sandbox"]["agent"])
        self.assertFalse(investigator["safe-outputs"]["threat-detection"])
        self.assertEqual(investigator["permissions"]["contents"], "read")
        self.assertNotIn("publish", investigator["jobs"])
        self.assertEqual(investigator["engine"]["extensions"],
                         ["npm:pi-web-access@0.48.0", "npm:pi-subagents@0.89.0"])
        self.assertIn("issues", investigator["tools"]["github"]["toolsets"])
        graph = investigator["mcp-servers"]["project-graph"]
        self.assertTrue(graph["required"])
        self.assertEqual(graph["container"], "ghcr.io/riseproject-dev/sw-ecosystem/project-graph-mcp:latest")
        self.assertEqual(graph["allowed"], ["project_graph_query"])
        for name in ("upstreaming-worker", "upstreaming-dispatcher"):
            config = source(name)
            self.assertTrue(config["strict"])
            self.assertNotEqual(config.get("sandbox", {}).get("agent"), False)
            self.assertFalse(config.get("features", {}).get("dangerously-disable-sandbox-agent", False))

    def test_completeness_gate_precedes_durable_completion(self):
        lock = yaml.safe_load((WF / "upstreaming-investigator.lock.yml").read_text())
        steps = lock["jobs"]["safe_outputs"]["steps"]
        names = [s.get("name") for s in steps]
        self.assertLess(names.index("Require complete research before native queue Completion"),
                        names.index("Reconcile work queue claim"))
        self.assertLess(names.index("Require complete research before native queue Completion"),
                        names.index("Process Safe Outputs"))
        self.assertNotIn("detection", lock["jobs"])

    def test_authored_python_ci_invocations_use_uv(self):
        for path in sorted(WF.glob("upstreaming-*")):
            if path.name.endswith(".lock.yml") or path.suffix not in (".md", ".yml"):
                continue  # Compiler-owned internal runtime setup is not authored here.
            text = path.read_text()
            config = yaml.safe_load(text.split("---", 2)[1] if path.suffix == ".md" else text)
            for script in run_scripts(config):
                joined = script.replace("\\\n", " ")
                self.assertIsNone(re.search(r"(?:^|[\n;&|])\s*python(?:3)?(?:\s|$)", joined),
                                  f"{path.name}: direct Python CI invocation without uv")
        sync_step = next(s for s in yaml.safe_load((WF / "upstreaming-validate.yml").read_text())["jobs"]["validate"]["steps"]
                         if s.get("name") == "Runtime dependency inventory matches authored workflow pins")
        self.assertIn("uv run --no-project python upstreaming/dependencies/sync.py", sync_step["run"])
