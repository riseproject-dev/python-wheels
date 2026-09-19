#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["pip"]
# ///
"""
Resolve requirements for riscv64, per interpreter, against PyPI + our registry.

Answers "which interpreters can this port actually test on?" before a CI cycle:
a dependency we host for cp312/cp313 but not cp314 caps the build matrix, and
pip is the only honest oracle for it. Runs `pip download --only-binary=:all:`
once per interpreter tag with every manylinux_2_NN_riscv64 platform the
registry uses, and prints the wheel each requirement resolves to, or the
interpreter as unresolvable.

Nothing is installed and nothing is kept: each run downloads into a temporary
directory that is removed afterwards.

`--abi abi3 --abi none` is passed alongside the interpreter's own tag on
purpose: with the literal tag only, pip silently rejects every `cpNN-abi3` and
`py3-none-any` wheel and a perfectly resolvable set looks impossible. A
free-threaded tag (`314t`) gets no `abi3`, which that build does not support.

Usage:
    uv run ci_scripts/check_riscv64_deps.py pytest orjson
    uv run ci_scripts/check_riscv64_deps.py --python 312 313 314 314t -- pytest 'numpy<3'
    uv run ci_scripts/check_riscv64_deps.py --no-registry pytest  # PyPI only
"""

import argparse
import re
import subprocess
import sys
import tempfile

REGISTRY = "https://pypi.riseproject.dev/simple/"
# The glibc floors our wheels are built against; not all are the same.
PLATFORMS = [
    "manylinux_2_39_riscv64",
    "manylinux_2_38_riscv64",
    "manylinux_2_35_riscv64",
    "manylinux_2_34_riscv64",
    "manylinux_2_31_riscv64",
    "manylinux_2_17_riscv64",
]
DEFAULT_PYTHONS = ["312", "313", "314", "314t"]


def resolve(python, requirements, registry):
    """Return (ok, lines): the wheels pip picked, or its error output."""
    free_threaded = python.endswith("t")
    version = python[:-1] if free_threaded else python
    abis = [f"cp{python}", "none"]
    if not free_threaded:
        abis.insert(1, "abi3")

    cmd = [sys.executable, "-m", "pip", "download", "--only-binary=:all:"]
    for platform in PLATFORMS:
        cmd += ["--platform", platform]
    for abi in abis:
        cmd += ["--abi", abi]
    cmd += ["--python-version", version, "--implementation", "cp"]
    if registry:
        cmd += ["--extra-index-url", REGISTRY]

    with tempfile.TemporaryDirectory() as dest:
        proc = subprocess.run(
            cmd + ["-d", dest, *requirements],
            capture_output=True,
            text=True,
        )
    if proc.returncode != 0:
        errors = [ln for ln in proc.stderr.splitlines() if ln.startswith("ERROR")]
        return False, errors or proc.stderr.splitlines()[-3:]
    wheels = sorted(re.findall(r"^Saved .*?([^/\\]+\.whl)$", proc.stdout, re.M))
    return True, wheels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        nargs="+",
        default=DEFAULT_PYTHONS,
        metavar="TAG",
        help="interpreter tags without the 'cp' prefix (default: %(default)s)",
    )
    parser.add_argument(
        "--no-registry",
        action="store_true",
        help="resolve against PyPI alone, to show what the registry adds",
    )
    parser.add_argument("requirements", nargs="+", help="pip requirement specifiers")
    args = parser.parse_args()

    failed = []
    for python in args.python:
        ok, lines = resolve(python, args.requirements, not args.no_registry)
        print(f"cp{python}: {'ok' if ok else 'UNRESOLVABLE'}")
        for line in lines:
            print(f"  {line}")
        if not ok:
            failed.append(python)

    if failed:
        print(
            "\nDrop from the matrix (or port the missing dependency first): "
            + ", ".join(f"cp{p}" for p in failed)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
