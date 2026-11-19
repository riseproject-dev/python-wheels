# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Apply the approved, hash-pinned gh-aw v1.2.2 native artifact fix.

Run only in trusted safe_outputs job preparation, before any handler loads.
Never reads agent artifacts. Both the source and resulting handler are pinned;
unknown source, symlinks, failed application or unexpected output abort the job.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile

SOURCE_SHA256 = "5713a810aacb0c748eebb787876e21c64400fc675d966c234c44e318c5f7a52b"
PATCHED_SHA256 = "d0cb0128220bb95633b0acbbb20ccb6e26c53a7b4a3d07d4e33347f7657a15a0"
PATCH = Path(__file__).with_name("gh-aw-compat") / "native-artifact.patch"


def apply(actions: Path) -> str:
    actions = actions.resolve(strict=True)
    handler = actions / "upload_artifact.cjs"
    if handler.is_symlink() or not handler.is_file():
        raise ValueError("native artifact handler must be a regular file")
    digest = hashlib.sha256(handler.read_bytes()).hexdigest()
    if digest == PATCHED_SHA256:
        return "already patched"
    if digest != SOURCE_SHA256:
        raise ValueError(f"unexpected gh-aw artifact handler SHA-256: {digest}")
    # Apply outside any source checkout: git apply otherwise interprets paths
    # relative to its repository root. Never replace the runtime until the
    # complete candidate has passed the output hash check.
    with tempfile.TemporaryDirectory(prefix="native-artifact-compat-") as tmp:
        candidate = Path(tmp) / handler.name
        candidate.write_bytes(handler.read_bytes())
        for check in (True, False):
            subprocess.run(["git", "apply", "--unidiff-zero", "-p4", *(["--check"] if check else []), str(PATCH)],
                           cwd=tmp, check=True, capture_output=True)
        data = candidate.read_bytes()
        if hashlib.sha256(data).hexdigest() != PATCHED_SHA256:
            raise ValueError("patched artifact handler SHA-256 does not match")
        handler.write_bytes(data)
    return "patched"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("actions", type=Path)
    args = parser.parse_args()
    print(apply(args.actions))
