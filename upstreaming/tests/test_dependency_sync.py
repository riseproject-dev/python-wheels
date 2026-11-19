# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Dependabot proposals cannot leave actual workflow pins unchanged."""
import json
from pathlib import Path
import runpy
import tempfile
import unittest

ROOT = Path(__file__).parents[2]
SYNC = runpy.run_path(str(ROOT / "upstreaming/dependencies/sync.py"))["synchronize"]


class TestDependencySynchronization(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("upstreaming/dependencies/package.json", "upstreaming/dependencies/go.mod",
                     "upstreaming/install_gh_aw.sh", "upstreaming/queue_result.py",
                     ".github/workflows/upstreaming-investigator.md", ".github/workflows/upstreaming-worker.md",
                     ".github/workflows/upstreaming-dispatcher.md"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())

    def tearDown(self):
        self.tmp.cleanup()

    def update(self, package, version):
        path = self.root / "upstreaming/dependencies/package.json"
        manifest = json.loads(path.read_text())
        manifest["dependencies"][package] = version
        path.write_text(json.dumps(manifest))

    def test_pins_match(self):
        self.assertEqual(SYNC(self.root), [])

    def test_runtime_proposal_needs_source_sync(self):
        self.update("@earendil-works/pi-coding-agent", "1.6.0")
        self.update("pi-web-access", "0.49.0")
        self.assertEqual(len(SYNC(self.root)), 3)
        self.assertEqual(SYNC(self.root, write=True), [])
        self.assertEqual(SYNC(self.root), [])
        source = (self.root / ".github/workflows/upstreaming-investigator.md").read_text()
        self.assertIn('version: "1.6.0"', source)
        self.assertIn("npm:pi-web-access@0.49.0", source)

    def test_prerelease_and_compiler_upgrade_do_not_silently_merge(self):
        self.update("pi-web-access", "0.49.0-beta.1")
        with self.assertRaises(ValueError):
            SYNC(self.root)
        self.update("pi-web-access", "0.49.0")
        module = self.root / "upstreaming/dependencies/go.mod"
        module.write_text(module.read_text().replace("v1.2.2", "v1.3.0"))
        errors = SYNC(self.root, write=True)
        self.assertTrue(any("reviewed installer hashes" in e for e in errors))
