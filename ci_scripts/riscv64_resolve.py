#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["pip"]
# ///
"""
Resolve a dependency set for riscv64, per interpreter, without a riscv64 host.

This is the pre-flight every port needs before it spends a CI cycle: will pip
find a riscv64 wheel for each of `CIBW_TEST_REQUIRES`/`install_requires`, on
each interpreter of the matrix, from PyPI plus pypi.riseproject.dev? It answers
the sharper form of gotcha 30 -- not "do we host this name?" but "what will pip
actually pick, and can it backtrack to a resolvable set?" -- and the answer is
what a PR quotes.

It wraps `pip install --dry-run --report` with the flags that are easy to get
wrong:

  * every `manylinux_2_NN_riscv64` platform our registry uses, because our
    wheels are not all built against the same glibc floor;
  * `--abi abi3 --abi none` alongside the interpreter's own tag, without which
    pip silently rejects every `cpNN-abi3` and `py3-none-any` wheel and a
    resolvable set looks impossible (gotcha 101);
  * `--python-version 314` for both cp314 and cp314t, which differ only in the
    ABI tag.

Run it on Linux: `--platform` does not override marker evaluation, so a macOS
host makes every `platform_system == "Darwin"` requirement real (gotcha 178).

Usage:
    uv run ci_scripts/riscv64_resolve.py pytest 'twisted[tls]' numpy gevent
    uv run ci_scripts/riscv64_resolve.py --abi cp314t -- 'cryptography>=42.0'
    uv run ci_scripts/riscv64_resolve.py --show-all -r test-requirements.txt
"""

import argparse
import json
import platform
import subprocess
import sys
import tempfile

REGISTRY = "https://pypi.riseproject.dev/simple/"

# Every glibc floor our own riscv64 wheels have been tagged with, newest first.
PLATFORMS = [
    "manylinux_2_39_riscv64",
    "manylinux_2_38_riscv64",
    "manylinux_2_34_riscv64",
    "manylinux_2_31_riscv64",
    "manylinux_2_17_riscv64",
]

ABIS = ["cp312", "cp313", "cp314", "cp314t"]


def python_version(abi):
    """cp314t is cp314's ABI, not its own Python version."""
    digits = abi.removeprefix("cp").removesuffix("t")
    return digits


def resolve(abi, requirements, files, extra_index_url):
    argv = [
        sys.executable, "-m", "pip", "install",
        "--dry-run", "--quiet", "--disable-pip-version-check",
        "--only-binary", ":all:",
        "--python-version", python_version(abi),
        "--implementation", "cp",
        "--abi", abi, "--abi", "abi3", "--abi", "none",
        "--extra-index-url", extra_index_url,
    ]
    for tag in PLATFORMS:
        argv += ["--platform", tag]
    for path in files:
        argv += ["--requirement", path]
    argv += list(requirements)

    with tempfile.NamedTemporaryFile("r", suffix=".json") as report:
        proc = subprocess.run(
            argv + ["--report", report.name],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return None, (proc.stderr or proc.stdout).strip()
        return json.load(open(report.name)), None


def wheel_name(item):
    url = item.get("download_info", {}).get("url", "")
    return url.rsplit("/", 1)[-1] or "?"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("requirements", nargs="*", help="requirement specifiers")
    parser.add_argument(
        "-r", "--requirement", action="append", default=[],
        help="a requirements file, repeatable",
    )
    parser.add_argument(
        "--abi", action="append", choices=ABIS,
        help=f"interpreter to resolve for, repeatable (default: {' '.join(ABIS)})",
    )
    parser.add_argument(
        "--extra-index-url", default=REGISTRY,
        help=f"index to add to PyPI (default: {REGISTRY})",
    )
    parser.add_argument(
        "--show-all", action="store_true",
        help="list every resolved wheel, not just the compiled ones",
    )
    args = parser.parse_args()

    if not args.requirements and not args.requirement:
        parser.error("give at least one requirement or -r file")
    if platform.system() != "Linux":
        print(
            f"warning: running on {platform.system()}; environment markers are "
            "evaluated for the host, so run this on Linux (gotcha 178)",
            file=sys.stderr,
        )

    failed = False
    for abi in args.abi or ABIS:
        report, error = resolve(
            abi, args.requirements, args.requirement, args.extra_index_url
        )
        if error:
            failed = True
            print(f"{abi}: UNRESOLVABLE")
            for line in error.splitlines():
                print(f"    {line}")
            continue
        names = sorted(wheel_name(item) for item in report["install"])
        shown = names if args.show_all else [n for n in names if "-none-any" not in n]
        print(f"{abi}: {len(names)} wheels, {len(shown)} shown")
        for name in shown:
            print(f"    {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
