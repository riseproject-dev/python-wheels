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

With --base-file, versions that the given (base branch) copy of the package
YAML already declares are left out, so a pull request only builds the versions
it adds.  An empty or missing base file means every version is new.

With --python-matrix, print instead a matrix `include:` list of
{"version", "python", "python-version"} entries, where each version gets the interpreters of its
`python-versions` (the ones upstream builds for, recorded by
check_versions.py) that riscv64 can build, minus --python-exclude. An entry
like `3.8-abi3` records the wheel's ABI floor; its matrix leg uses the oldest
available, non-free-threaded build interpreter at or above that floor.
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
        if "python-versions" not in entry:
            raise SystemExit(
                f"{path}: version {version} has no python-versions; run "
                f"`check_versions.py --python-versions {package}` or add it by hand"
            )
        pythons = entry["python-versions"]
        if not isinstance(pythons, list) or not pythons or not all(
            isinstance(v, str) and re.fullmatch(r"3\.\d+(?:t|-abi3)?", v)
            for v in pythons
        ):
            raise SystemExit(
                f"{path}: version {version} python-versions must be a non-empty "
                "list of quoted strings like '3.10', '3.14t', or '3.8-abi3', "
                f"got {pythons!r}"
            )
        if len(pythons) != len(set(pythons)):
            raise SystemExit(
                f"{path}: version {version} python-versions contains duplicates: {pythons!r}"
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


def base_versions(path):
    """Versions declared in the base branch's copy of the package YAML."""
    text = Path(path).read_text() if Path(path).exists() else ""
    data = yaml.safe_load(text) or {}
    return {str(v["version"]).strip() for v in data.get("versions") or []}


def cp_tag(python_version):
    """'3.14t' -> 'cp314t', the cibuildwheel identifier prefix."""
    return "cp" + python_version.replace(".", "")


def python_version(tag):
    """'cp314t' -> '3.14t'."""
    digits = tag.removeprefix("cp").removesuffix("t")
    return digits[0] + "." + digits[1:] + ("t" if tag.endswith("t") else "")


def version_key(value):
    """Numeric (major, minor), ignoring a free-threaded or abi3 suffix."""
    base = value.removesuffix("t").removesuffix("-abi3")
    return tuple(map(int, base.split(".")))


def adjust(tags, exclude=()):
    """Drop the tags matching an exclude glob."""
    return [t for t in tags if not any(fnmatch.fnmatchcase(t, g) for g in exclude)]


def python_matrix(package, entries, selected, exclude=()):
    """
    Return the matrix entries of the selected versions, and a warning for each
    version whose interpreters cannot produce a riscv64 build.
    """
    matrix, warnings = [], []
    for entry in entries:
        version = str(entry["version"])
        if version not in selected:
            continue
        values = entry["python-versions"]
        regular = {cp_tag(v) for v in values if not v.endswith("-abi3")}
        tags = adjust([t for t in RISCV64_PYTHONS if t in regular], exclude)
        for tag in tags:
            matrix.append({
                "version": version,
                "python": tag,
                "python-version": python_version(tag),
                "wheel-tag": tag,
            })

        for value in (v for v in values if v.endswith("-abi3")):
            floor = value.removesuffix("-abi3")
            candidates = adjust([
                tag for tag in RISCV64_PYTHONS
                if not tag.endswith("t") and version_key(python_version(tag)) >= version_key(floor)
            ], exclude)
            if not candidates:
                warnings.append(
                    f"{package} {version} has no usable riscv64 build interpreter "
                    f"at or above its {value} floor after exclusions"
                )
                continue
            tag = candidates[0]
            matrix.append({
                "version": version,
                "python": tag,
                "python-version": python_version(tag),
                "wheel-tag": cp_tag(floor) + "-abi3",
                "abi3-floor": floor,
            })

        if not any(item["version"] == version for item in matrix):
            warnings.append(
                f"{package} {version} is not in the matrix: none of {values} can be "
                "built for riscv64, or all are excluded"
            )
    return matrix, warnings


def _self_test():
    entries = [
        {"version": "1.0", "python-versions": ["3.8-abi3", "3.14t"]},
        {"version": "2.0", "python-versions": ["3.13"]},
    ]
    # Upstream's list in RISCV64_PYTHONS order, minus what riscv64 can't build.
    assert python_matrix("pkg", entries, ["1.0"], ["cp39", "cp310", "cp311", "cp314t"]) == ([
        {
            "version": "1.0", "python": "cp312", "python-version": "3.12",
            "wheel-tag": "cp38-abi3", "abi3-floor": "3.8",
        },
    ], [])
    assert python_matrix("pkg", entries, ["2.0"]) == ([
        {
            "version": "2.0", "python": "cp313", "python-version": "3.13",
            "wheel-tag": "cp313",
        }
    ], [])
    matrix, warnings = python_matrix("pkg", entries, ["2.0"], ["cp31?"])
    assert matrix == [] and len(warnings) == 1, warnings
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
        "--base-file",
        help="base branch copy of the package YAML; skip versions it declares",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="only validate the YAML; print nothing",
    )
    parser.add_argument(
        "--python-matrix",
        action="store_true",
        help="print {version, python, python-version} matrix entries instead of versions",
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

    if args.base_file and not args.glob:
        already_on_base = base_versions(args.base_file)
        versions = [v for v in versions if str(v["version"]) not in already_on_base]

    selected = select_versions(versions, args.glob)
    if args.glob and not selected:
        raise SystemExit(
            f"no version of {args.package} matches {args.glob!r}; declared: "
            + ", ".join(str(v["version"]) for v in versions)
        )
    if args.python_matrix:
        selected, warnings = python_matrix(
            args.package, versions, selected, args.python_exclude.split()
        )
        for warning in warnings:
            print(warning, file=sys.stderr)
    json.dump(selected, sys.stdout, separators=(",", ":"))
    print()


if __name__ == "__main__":
    main()
