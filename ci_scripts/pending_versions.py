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

With --python-matrix, print instead a matrix `include:` list of
{"version", "python"} pairs, where each version gets the interpreters of its
`python-versions` (the ones upstream builds for, recorded by
check_versions.py) that riscv64 can build, minus --python-exclude.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

import yaml

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "packages"

# Interpreters cibuildwheel can build for riscv64 (the *-manylinux_riscv64
# identifiers of its build-platforms.toml; there is no cp313t), oldest first.
# Not a policy list: only a technical limit on what upstream's tags can map to.
# Update it when bumping cibuildwheel.
RISCV64_PYTHONS = [
    "cp39", "cp310", "cp311", "cp312", "cp313",
    "cp314", "cp314t", "cp315", "cp315t",
]


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
        pythons = entry.get("python-versions", [])
        if not isinstance(pythons, list) or not all(
            isinstance(v, str) and re.fullmatch(r"3\.\d+t?", v) for v in pythons
        ):
            raise SystemExit(
                f"{path}: version {version} python-versions must be a list of "
                f"quoted strings like '3.10' or '3.14t', got {pythons!r}"
            )
    return versions


def is_pending(entry):
    return "tag" not in entry and "files" not in entry


def select_versions(versions, glob=None):
    if glob:
        return [
            str(v["version"])
            for v in versions
            if fnmatch.fnmatchcase(str(v["version"]), glob)
        ]
    return [str(v["version"]) for v in versions if is_pending(v)]


def cp_tag(python_version):
    """'3.14t' -> 'cp314t', the cibuildwheel identifier prefix."""
    return "cp" + python_version.replace(".", "")


def adjust(tags, exclude=()):
    """Drop the tags matching an exclude glob."""
    return [t for t in tags if not any(fnmatch.fnmatchcase(t, g) for g in exclude)]


def python_matrix(package, entries, selected, exclude=()):
    matrix = []
    for entry in entries:
        version = str(entry["version"])
        if version not in selected:
            continue
        if "python-versions" not in entry:
            raise SystemExit(
                f"{package} {version} has no python-versions in docs/packages/{package}.yaml; "
                f"run `check_versions.py --python-versions {package}` or write it by hand"
            )
        tags = {cp_tag(v) for v in entry["python-versions"]}
        tags = adjust([t for t in RISCV64_PYTHONS if t in tags], exclude)
        if not tags:
            raise SystemExit(
                f"{package} {version}: no Python version to build (none of "
                f"{entry['python-versions']} can be built for riscv64, or all excluded)"
            )
        matrix += [{"version": version, "python": tag} for tag in tags]
    return matrix


def _self_test():
    entries = [
        {"version": "1.0", "python-versions": ["3.8", "3.12", "3.13t", "3.14", "3.14t"]},
        {"version": "2.0", "python-versions": ["3.13"]},
        {"version": "3.0"},
    ]
    # Upstream's list in RISCV64_PYTHONS order, minus what riscv64 can't build.
    assert python_matrix("pkg", entries, ["1.0"], ["cp314t"]) == [
        {"version": "1.0", "python": "cp312"},
        {"version": "1.0", "python": "cp314"},
    ]
    assert python_matrix("pkg", entries, ["2.0"]) == [{"version": "2.0", "python": "cp313"}]
    for selected, exclude in ((["3.0"], []), (["2.0"], ["cp31?"])):
        try:
            python_matrix("pkg", entries, selected, exclude)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"{selected} {exclude} should fail")
    print("[+] self-test passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", help="docs/packages/<package>.yaml to read")
    parser.add_argument(
        "--glob",
        default="",
        help="version glob to build, released or not (default: pending versions only)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="only validate the YAML; print nothing",
    )
    parser.add_argument(
        "--python-matrix",
        action="store_true",
        help="print {version, python} matrix entries instead of versions",
    )
    parser.add_argument(
        "--python-exclude",
        default="",
        help="space-separated interpreter tag globs (e.g. 'cp39 cp315*') to drop",
    )
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    if "--self-test" in sys.argv:
        _self_test()
        return
    args = parser.parse_args()

    versions = load_versions(args.package)
    if args.check:
        return

    selected = select_versions(versions, args.glob)
    if args.glob and not selected:
        raise SystemExit(
            f"no version of {args.package} matches {args.glob!r}; declared: "
            + ", ".join(str(v["version"]) for v in versions)
        )
    if args.python_matrix:
        selected = python_matrix(
            args.package, versions, selected, args.python_exclude.split()
        )
    json.dump(selected, sys.stdout, separators=(",", ":"))
    print()


if __name__ == "__main__":
    main()
