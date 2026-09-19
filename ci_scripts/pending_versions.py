#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Print, as a JSON list, the versions of a package that a build workflow should
build, read from docs/packages/<package>.yaml.

A version entry without `tag`/`files` has not been released yet and is
pending; with no --glob, those are the versions returned. With --glob, every
version matching the glob is returned, released or not, so a workflow_dispatch
can force a rebuild.

The YAML lags: a version is published hours before the shared documentation PR
records it here. --released takes the release tags that already exist and drops
their versions from the pending set, so a push to main landing inside that
window does not rebuild and republish what is already out.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

import yaml

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "packages"


def normalized_name(package):
    """
    The project name as _publish-wheel.yml builds its release tags from: the
    wheel's own name, PEP 503 normalized.
    """
    path = DOCS_DIR / f"{package}.yaml"
    data = yaml.safe_load(path.read_text()) or {}
    name = data.get("package-name") or package
    return re.sub(r"[-_.]+", "-", name).lower()


def released_versions(package, released_tags):
    """
    The versions among `released_tags` that are already out: publishing version
    V of package P tags the release `P-vV-<timestamp>`.
    """
    prefix = normalized_name(package)
    pattern = re.compile(rf"^{re.escape(prefix)}-v(.+)-\d{{14}}$")
    return {m.group(1) for m in map(pattern.match, released_tags) if m}


def load_versions(package):
    path = DOCS_DIR / f"{package}.yaml"
    if not path.exists():
        raise SystemExit(
            f"{path} does not exist: every build-<pkg>.yml needs a "
            "docs/packages/<pkg>.yaml declaring the versions to build "
            "(see docs/development.md)"
        )
    data = yaml.safe_load(path.read_text()) or {}
    versions = data.get("versions") or []
    seen = set()
    for entry in versions:
        version = str(entry.get("version", "")).strip()
        if not version:
            raise SystemExit(f"{path}: a versions entry has no version")
        if version in seen:
            raise SystemExit(f"{path}: version {version} is listed twice")
        seen.add(version)
        if ("tag" in entry) != ("files" in entry):
            raise SystemExit(
                f"{path}: version {version} has one of tag/files but not both"
            )
    return versions


def is_pending(entry):
    return "tag" not in entry and "files" not in entry


def select_versions(versions, glob=None, already_released=frozenset()):
    if glob:
        # An explicit glob is a rebuild request, so it ignores what is already
        # released.
        return [
            str(v["version"])
            for v in versions
            if fnmatch.fnmatchcase(str(v["version"]), glob)
        ]
    return [
        str(v["version"])
        for v in versions
        if is_pending(v) and str(v["version"]) not in already_released
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", help="docs/packages/<package>.yaml to read")
    parser.add_argument(
        "--glob",
        default="",
        help="version glob to build, released or not (default: pending versions only)",
    )
    parser.add_argument(
        "--released",
        type=Path,
        help="file of existing release tags, one per line; their versions are "
        "not pending even when this YAML does not record them yet",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="only validate the YAML; print nothing",
    )
    args = parser.parse_args()

    versions = load_versions(args.package)
    if args.check:
        return

    already_released = frozenset()
    if args.released:
        already_released = released_versions(
            args.package, args.released.read_text().split()
        )

    selected = select_versions(versions, args.glob, already_released)
    if args.glob and not selected:
        raise SystemExit(
            f"no version of {args.package} matches {args.glob!r}; declared: "
            + ", ".join(str(v["version"]) for v in versions)
        )
    json.dump(selected, sys.stdout, separators=(",", ":"))
    print()


if __name__ == "__main__":
    main()
