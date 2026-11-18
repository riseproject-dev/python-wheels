# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Safe extraction of the agent's proposal artifact (untrusted input).

The artifact is a zip produced by Actions from ``/tmp/gh-aw/agent/out/``.
Accept only regular files with fixed names at the top level, bounded
sizes, no links or path components. Also writes ``record.json`` from the
trusted control checkout (the agent never supplies the contribution record).

    python -m upstreaming.artifact extract proposal.zip OUTDIR
"""

from __future__ import annotations

import json
import stat
import sys
import zipfile
from pathlib import Path

ALLOWED = {"proposal.json": 256 * 1024, "patches.mbox": 4 * 1024 * 1024, "dossier.json": 256 * 1024,
           "notes.md": 64 * 1024}
MAX_TOTAL = 5 * 1024 * 1024


class ArtifactError(ValueError):
    pass


def extract(zip_path: Path, out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    got: list[str] = []
    total = 0
    with zipfile.ZipFile(zip_path) as z:
        infos = z.infolist()
        if len(infos) > len(ALLOWED) + 4:
            raise ArtifactError("too many entries")
        for i in infos:
            name = i.filename
            # The native upload keeps the staging-relative directory.
            if name.startswith("upstreaming-out/"):
                name = name[len("upstreaming-out/"):]
            if i.is_dir() or not name:
                continue
            if "/" in name or "\\" in name or name not in ALLOWED:
                raise ArtifactError(f"unexpected entry {i.filename!r}")
            mode = (i.external_attr >> 16) & 0o170000
            if mode and mode != stat.S_IFREG:
                raise ArtifactError(f"{name}: not a regular file")
            if i.file_size > ALLOWED[name]:
                raise ArtifactError(f"{name}: too large")
            total += i.file_size
            if total > MAX_TOTAL:
                raise ArtifactError("artifact too large")
            data = z.read(i)
            if len(data) != i.file_size:
                raise ArtifactError(f"{name}: size mismatch")
            (out / name).write_bytes(data)
            got.append(name)
    if "proposal.json" not in got:
        raise ArtifactError("proposal.json missing")
    json.loads((out / "proposal.json").read_text(encoding="utf-8"))
    return sorted(got)


def write_record(control_root: Path, task_path: Path, out: Path) -> None:
    """Copy the trusted contribution record named by the task from control state."""
    from .common import contribution_file_id
    task = json.loads(task_path.read_text())
    rec = control_root / "upstreaming-state" / "contributions" / f"{contribution_file_id(task['contribution_id'])}.json"
    if not rec.is_file() or rec.is_symlink():
        raise ArtifactError("contribution record not found in control state")
    (out / "record.json").write_bytes(rec.read_bytes())


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] != "extract":
        print(__doc__, file=sys.stderr)
        return 2
    out = Path(argv[3])
    got = extract(Path(argv[2]), out)
    write_record(Path(__file__).resolve().parents[1], out / "task.json", out)
    print(json.dumps({"extracted": got}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
