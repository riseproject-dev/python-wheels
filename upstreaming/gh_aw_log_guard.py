# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Hash-pinned guard against GitHub workflow commands in agent output.

The canonical agent stream remains unchanged in its artifact. Only the child
process bytes forwarded to the Actions console are made command-safe.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = "28c69eb1c56469eac2e1182fea6cde195ee95c698b8412b5ed85c821e331b8f6"
PATCHED_SHA256 = "74bb397cd5e0502d4a83c6c9e9a9d838d52d588b4402807f1f24b97178f21326"

IMPORT_NEEDLE = '''const { StringDecoder } = require("string_decoder");
'''
IMPORT_REPLACEMENT = '''const { StringDecoder } = require("string_decoder");

// Agent and tool output is untrusted. GitHub Actions interprets any line that
// begins with two colons as a runner command. Insert a space after every colon
// byte only in the console copy. Operating on bytes keeps this safe across
// output chunks and preserves the canonical stream collected for artifacts.
function workflowCommandSafe(data) {
  let colonCount = 0;
  for (const byte of data) if (byte === 0x3a) colonCount += 1;
  if (colonCount === 0) return data;
  const safe = Buffer.allocUnsafe(data.length + colonCount);
  let target = 0;
  for (const byte of data) {
    safe[target++] = byte;
    if (byte === 0x3a) safe[target++] = 0x20;
  }
  return safe;
}
'''
WRITE_REPLACEMENTS = {
    "process.stdout.write(data)": "process.stdout.write(workflowCommandSafe(data))",
    "process.stderr.write(data)": "process.stderr.write(workflowCommandSafe(data))",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_bytes(source: bytes, *, verify_source: bool = True) -> bytes:
    if verify_source and digest(source) != SOURCE_SHA256:
        raise RuntimeError("gh-aw process_runner.cjs does not match pinned v1.2.2 input")
    text = source.decode()
    if text.count(IMPORT_NEEDLE) != 1:
        raise RuntimeError("gh-aw process_runner import anchor is missing or ambiguous")
    text = text.replace(IMPORT_NEEDLE, IMPORT_REPLACEMENT)
    for old, new in WRITE_REPLACEMENTS.items():
        if text.count(old) != 1:
            raise RuntimeError(f"gh-aw process_runner write anchor is missing or ambiguous: {old}")
        text = text.replace(old, new)
    return text.encode()


def apply(actions_dir: Path) -> None:
    path = actions_dir / "process_runner.cjs"
    source = path.read_bytes()
    if PATCHED_SHA256 != "TO_BE_FILLED" and digest(source) == PATCHED_SHA256:
        return
    patched = patch_bytes(source)
    if PATCHED_SHA256 == "TO_BE_FILLED" or digest(patched) != PATCHED_SHA256:
        raise RuntimeError("gh-aw process_runner.cjs patched output hash mismatch")
    path.write_bytes(patched)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("actions_dir", type=Path)
    args = parser.parse_args(argv)
    apply(args.actions_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
