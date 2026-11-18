# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Fail-closed installation of the approved native artifact compatibility fix."""
import base64
import hashlib
from pathlib import Path
import tempfile
import unittest

from upstreaming import gh_aw_compat

# Base64 preserves exact upstream bytes, including non-ASCII comments, for
# the pinned input hash without adding those comments to project prose.
FIXTURE = Path(__file__).parents[1] / "gh-aw-compat/tests/upload_artifact.v1.2.2.cjs.b64"


class TestNativeArtifactPatch(unittest.TestCase):
    def test_exact_source_and_output_and_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            actions = Path(tmp)
            handler = actions / "upload_artifact.cjs"
            handler.write_bytes(base64.decodebytes(FIXTURE.read_bytes()))
            self.assertEqual(gh_aw_compat.apply(actions), "patched")
            self.assertEqual(hashlib.sha256(handler.read_bytes()).hexdigest(), gh_aw_compat.PATCHED_SHA256)
            self.assertEqual(gh_aw_compat.apply(actions), "already patched")

    def test_unknown_source_and_symlink_rejected_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            actions = Path(tmp)
            handler = actions / "upload_artifact.cjs"
            handler.write_text("unexpected")
            with self.assertRaises(ValueError):
                gh_aw_compat.apply(actions)
            self.assertEqual(handler.read_text(), "unexpected")
            handler.unlink()
            handler.symlink_to(FIXTURE)
            with self.assertRaises(ValueError):
                gh_aw_compat.apply(actions)
