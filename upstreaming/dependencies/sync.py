#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Check or synchronize Dependabot inventory with authored workflow pins.

Manifest-only runtime updates must not merge while workflow source stays old.
Use --write to copy reviewed Pi/extension versions into the Markdown sources,
then recompile with the reviewed gh-aw compiler. Compiler upgrades require
independent checksum and compatibility review; this script cannot waive it.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ("upstreaming-investigator", "upstreaming-worker", "upstreaming-dispatcher")
EXTENSIONS = ("pi-web-access", "pi-subagents")


def synchronize(root: Path, write: bool = False) -> list[str]:
    inventory = root / "upstreaming/dependencies"
    deps = json.loads((inventory / "package.json").read_text())["dependencies"]
    versions = {name: deps[name] for name in ("@earendil-works/pi-coding-agent", *EXTENSIONS)}
    for name, version in versions.items():
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError(f"{name}: require an exact stable release, got {version!r}")
    compiler = re.search(r"^require github\.com/github/gh-aw (v\d+\.\d+\.\d+)$",
                         (inventory / "go.mod").read_text(), re.M)
    if compiler is None:
        raise ValueError("gh-aw inventory must specify one exact stable release")
    issues = []
    version = compiler.group(1)
    installer = (root / "upstreaming/install_gh_aw.sh").read_text()
    resolver = (root / "upstreaming/queue_result.py").read_text()
    if f"version={version}\n" not in installer or f'GH_AW_VERSION = "{version}"' not in resolver:
        issues.append("gh-aw update requires reviewed installer hashes, Result reader, compatibility patch and compiler/lock regeneration")
    for name in WORKFLOWS:
        path = root / f".github/workflows/{name}.md"
        source = path.read_text()
        target, count = re.subn(r'(engine:\n  id: pi\n  version: )["\']?[^\n"\']+["\']?',
                                lambda m: m[1] + json.dumps(versions["@earendil-works/pi-coding-agent"]), source)
        if count != 1:
            raise ValueError(f"{path}: expected exactly one explicit Pi version")
        if name == "upstreaming-investigator":
            for extension in EXTENSIONS:
                target, count = re.subn(r"npm:" + re.escape(extension) + r"@[^\s]+",
                                        "npm:" + extension + "@" + versions[extension], target)
                if count != 1:
                    raise ValueError(f"{path}: expected one {extension} pin")
        if target != source:
            if write:
                path.write_text(target)
            else:
                issues.append(f"{path.relative_to(root)} pins do not match Dependabot inventory; run sync.py --write and recompile")
    return issues


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    issues = synchronize(args.root, args.write)
    for issue in issues:
        print(issue)
    raise SystemExit(bool(issues))
