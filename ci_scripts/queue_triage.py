#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
First-pass feasibility triage of a queued package, from PyPI metadata alone.

Answers the two questions that open every port, before any wheel is
downloaded or any YAML is written:

1. **Is the version in `.queue.yml` still the latest, and does the latest
   release still have the wheel shape the queue note describes?** A queue
   entry is a research snapshot (gotcha 388): upstream can delete its
   arch-specific payload in a later release, turning a
   `py3-none-<platform>` wheel set into a single `py3-none-any` wheel and
   erasing the riscv64 gap entirely. The per-version table prints each
   release's wheel tags with sizes, flags whether an sdist exists, and marks
   which releases already have a riscv64-installable file, so a vanished gap
   is visible in one read.

2. **With --deps, are the hard runtime dependencies reachable on riscv64?**
   (gotcha 40's check) For each entry in `requires_dist`, with extras
   dropped, reports whether PyPI publishes a riscv64-compatible file and
   whether pypi.riseproject.dev serves the project at all. Note that a
   `py3-none-any` facade wheel can resolve here while its real payload
   dependency does not -- follow a `py3-none-any` hit one level down before
   calling a dependency available.

This complements rather than overlaps the existing helpers:
`check_versions.py` compares the registry against PyPI for packages we
*already* build (`ci_scripts/packages.txt`), and `wheel_contents.py`
inspects the bytes *inside* one chosen wheel. This one chooses which
version and which wheel are worth looking at in the first place.

Usage:
    uv run ci_scripts/queue_triage.py tokenspeed-mla
    uv run ci_scripts/queue_triage.py tokenspeed-mla --deps
    uv run ci_scripts/queue_triage.py numba --releases 5 --deps
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = REPO_ROOT / ".queue.yml"
RISE_INDEX = "https://pypi.riseproject.dev/simple"

# A wheel file installs on riscv64 if its platform tag is `any` or names
# riscv64. Everything else (manylinux x86_64/aarch64, musllinux, macos, win)
# is a gap for us -- or, when there is no riscv64-compatible file at all and
# no sdist, a version riscv64 pip cannot even see.
RISCV_MARKERS = ("riscv64",)


def fetch_json(url):
    try:
        with urllib.request.urlopen(url) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"{url}: HTTP {error.code}") from error


def queue_entry(package):
    data = yaml.safe_load(QUEUE_PATH.read_text()) or {}
    for entry in data.get("packages") or []:
        if entry.get("pkg") == package:
            return entry
    return None


def platform_tags(filename):
    """Return the platform tags of a wheel filename."""
    stem = filename.rsplit(".whl", 1)[0]
    return stem.rsplit("-", 1)[-1].split(".")


def abi_tag(filename):
    stem = filename.rsplit(".whl", 1)[0]
    parts = stem.split("-")
    return parts[-2] if len(parts) >= 4 else "?"


def classify(files):
    """Summarise one release's files: tags, sizes, sdist and riscv64 reach."""
    wheels, sdists = [], []
    for item in files:
        if item.get("packagetype") == "sdist":
            sdists.append(item)
        elif item["filename"].endswith(".whl"):
            wheels.append(item)
    riscv = False
    for wheel in wheels:
        for tag in platform_tags(wheel["filename"]):
            if tag == "any" or any(marker in tag for marker in RISCV_MARKERS):
                riscv = True
    return wheels, sdists, riscv


def report_versions(package, data, entry, limit):
    releases = data["releases"]
    from packaging.version import InvalidVersion, Version

    def version_key(v):
        # A single unparseable release (a non-PEP440 string some projects
        # still publish) used to make the whole list fall back to lexicographic
        # order, silently misreporting "latest" for every release. Sort
        # unparseable versions after parseable ones instead of poisoning the
        # whole sort.
        try:
            return (1, Version(v))
        except InvalidVersion:
            return (0, v)

    order = sorted(releases, key=version_key)

    latest = data["info"]["version"]
    queued = (entry or {}).get("version")
    print(f"package        : {package}")
    print(f"latest on PyPI : {latest}")
    if entry is None:
        print("queue entry    : (none)")
    else:
        flag = "" if queued == latest else "  <-- STALE, triage the latest"
        print(f"queue entry    : {queued} (status {entry.get('status')}){flag}")
    print(f"requires_python: {data['info'].get('requires_python')}")
    print()

    print(f"last {limit} release(s), newest first:")
    for version in reversed(order[-limit:]):
        wheels, sdists, riscv = classify(releases[version])
        if not wheels and not sdists:
            print(f"  {version:<24} (no files -- yanked or empty release)")
            continue
        mark = "riscv64-OK" if riscv else "no riscv64 file"
        note = "+sdist" if sdists else "NO sdist"
        star = " *" if version == latest else ""
        print(f"  {version:<24} {mark:<16} {note:<9} {len(wheels)} wheel(s){star}")
        seen = {}
        for wheel in wheels:
            key = (abi_tag(wheel["filename"]), ".".join(platform_tags(wheel["filename"])))
            seen.setdefault(key, []).append(wheel["size"])
        for (abi, plat), sizes in sorted(seen.items()):
            span = f"{min(sizes) / 1e6:.1f} MB"
            if max(sizes) != min(sizes):
                span = f"{min(sizes) / 1e6:.1f}-{max(sizes) / 1e6:.1f} MB"
            print(f"      {abi:<12} {plat:<52} {span}")
    print()


def rise_serves(project):
    request = urllib.request.Request(f"{RISE_INDEX}/{project}/", method="HEAD")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status == 200
    except urllib.error.HTTPError:
        return False
    except OSError:
        return False


def report_deps(data):
    requires = data["info"].get("requires_dist") or []
    hard = [spec for spec in requires if "extra ==" not in spec]
    print(f"hard runtime dependencies ({len(hard)} of {len(requires)} requirements):")
    if not hard:
        print("  (none)")
        return
    for spec in hard:
        name = spec.split(";")[0].strip()
        for separator in ("[", "(", "=", "<", ">", "!", "~", " "):
            name = name.split(separator)[0]
        name = name.strip()
        dep = fetch_json(f"https://pypi.org/pypi/{name}/json")
        _, sdists, riscv = classify(dep["urls"])
        bits = []
        bits.append("riscv64/any wheel" if riscv else "NO riscv64 wheel")
        bits.append("sdist" if sdists else "no sdist")
        bits.append("on RISE" if rise_serves(name) else "not on RISE")
        print(f"  {name:<34} {' | '.join(bits)}")
        print(f"      spec: {spec}")
    print()
    print("A `py3-none-any` hit can be a facade: re-run this on any dependency")
    print("whose own requires_dist names a separate payload distribution.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", help="distribution name as it appears on PyPI")
    parser.add_argument(
        "--releases", type=int, default=8, help="how many recent releases to table (default 8)"
    )
    parser.add_argument(
        "--deps", action="store_true", help="also check hard dependencies for riscv64 reach"
    )
    args = parser.parse_args()

    data = fetch_json(f"https://pypi.org/pypi/{args.package}/json")
    report_versions(args.package, data, queue_entry(args.package), args.releases)
    if args.deps:
        report_deps(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
