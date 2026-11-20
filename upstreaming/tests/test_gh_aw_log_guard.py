# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

import subprocess
import unittest

from upstreaming import gh_aw_log_guard


SYNTHETIC = b'''const { StringDecoder } = require("string_decoder");
function forwardOut(data) { return process.stdout.write(data); }
function forwardErr(data) { return process.stderr.write(data); }
'''


class TestGhAwLogGuard(unittest.TestCase):
    def test_patch_rejects_unpinned_runtime(self):
        with self.assertRaisesRegex(RuntimeError, "does not match pinned"):
            gh_aw_log_guard.patch_bytes(SYNTHETIC)

    def test_console_copy_cannot_form_workflow_command_across_chunks(self):
        patched = gh_aw_log_guard.patch_bytes(SYNTHETIC, verify_source=False).decode()
        script = patched + '''
process.stdout.write(workflowCommandSafe(Buffer.from(":")));
process.stdout.write(workflowCommandSafe(Buffer.from(":add-matcher::bad")));
process.stdout.write("\\n");
process.stdout.write(workflowCommandSafe(Buffer.from("::error::bad")));
'''
        result = subprocess.run(["node", "-e", script], check=True, capture_output=True)
        output = result.stdout.decode()
        self.assertNotIn("::", output)
        self.assertIn(": : add-matcher: : bad", output)
        self.assertIn(": : error: : bad", output)

    def test_patch_changes_only_forwarded_console_bytes(self):
        patched = gh_aw_log_guard.patch_bytes(SYNTHETIC, verify_source=False).decode()
        self.assertIn("process.stdout.write(workflowCommandSafe(data))", patched)
        self.assertIn("process.stderr.write(workflowCommandSafe(data))", patched)
        self.assertNotIn("stdout = collect(stdout, workflowCommandSafe", patched)
        self.assertNotIn("stderr = collect(stderr, workflowCommandSafe", patched)


if __name__ == "__main__":
    unittest.main()
