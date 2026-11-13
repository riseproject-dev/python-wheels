#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""List packages with pending versions and optionally dispatch a batch.

A version is pending when it has no release tag or when any expected file has
no filename, matching ci_scripts/pending_versions.py and _setup.yml.

Without --batch, this command only prints package names. With --batch N, it
also dispatches up to N corresponding build workflows on main. Packages whose
build-<package>.yml workflow is absent are listed but cannot be dispatched.

Examples:

    uv run ci_scripts/queue-pending-versions.py
    uv run ci_scripts/queue-pending-versions.py --batch 10
    uv run ci_scripts/queue-pending-versions.py --batch 10 --cancel-in-progress
    uv run ci_scripts/queue-pending-versions.py --batch 10 --dry-run
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from pending_versions import is_pending, load_versions

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "packages"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
DEFAULT_REPOSITORY = "riseproject-dev/python-wheels"


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def pending_packages() -> list[str]:
    packages = []
    for path in sorted(DOCS_DIR.glob("*.yaml")):
        package = path.stem
        if any(is_pending(entry) for entry in load_versions(package)):
            packages.append(package)
    return packages


def workflow_path(package: str) -> Path:
    return WORKFLOWS_DIR / f"build-{package}.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch",
        type=positive_int,
        metavar="N",
        help="dispatch up to N pending package workflows; omit to only list packages",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY),
        help="GitHub repository to dispatch in (default: %(default)s)",
    )
    parser.add_argument(
        "--ref", default="main", help="git ref to dispatch (default: %(default)s)"
    )
    parser.add_argument(
        "--cancel-in-progress",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="allow dispatched workflows to cancel an in-progress run in the same "
        "concurrency group (default: false)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show which workflows would be dispatched without dispatching them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packages = pending_packages()
    for package in packages:
        print(package)

    if args.batch is None:
        return 0

    dispatchable = [package for package in packages if workflow_path(package).is_file()]
    missing = [package for package in packages if not workflow_path(package).is_file()]
    for package in missing:
        print(
            f"warning: {package}: {workflow_path(package).relative_to(REPO_ROOT)} is missing; "
            "cannot dispatch",
            file=sys.stderr,
        )

    selected = dispatchable[: args.batch]
    failures = 0
    for package in selected:
        workflow = workflow_path(package).name
        command = [
            "gh",
            "workflow",
            "run",
            workflow,
            "--repo",
            args.repo,
            "--ref",
            args.ref,
            "--field",
            f"cancel-in-progress={str(args.cancel_in_progress).lower()}",
        ]
        if args.dry_run:
            print(
                f"would dispatch {workflow} on {args.repo}@{args.ref} "
                f"with cancel-in-progress={str(args.cancel_in_progress).lower()}",
                file=sys.stderr,
            )
            continue
        result = subprocess.run(command, cwd=REPO_ROOT, check=False)
        if result.returncode:
            failures += 1
            print(f"error: could not dispatch {workflow}", file=sys.stderr)
        else:
            print(f"dispatched {workflow}", file=sys.stderr)

    action = "would dispatch" if args.dry_run else "dispatched"
    print(
        f"{action} {len(selected) - failures} of {len(packages)} pending package workflows",
        file=sys.stderr,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
