#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Mark every package we publish as "Available in RISE PyPI" in the project.

For each package in ci_scripts/packages.txt, take its oldest open
"<pkg> riscv64 support" issue and, unless its Status already says it is
available (in RISE PyPI, or upstream after a deprecation), add it to the
"Python Wheels" project and set Status to "Available in RISE PyPI".

The website workflow runs this after each deploy, so a package only flips once
its docs PR is merged and /simple/ lists it. It compares state rather than
reacting to one push, so a skipped or failed run is caught up by the next one.

Needs a token with the ``project`` scope (the GitHub App: organization
"Projects: read and write"):

    gh auth refresh -h github.com -s project
    ci_scripts/sync_project_status.py --dry-run
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from github_issues import (
    STATUS_RISE,
    STATUS_UPSTREAM,
    fetch_issues,
    oldest_open_issue,
    project_status,
    set_issue_status,
)

PACKAGES_FILE = Path(__file__).resolve().parent / "packages.txt"

# Each update is two mutations. Usually only a package or two change per run,
# but a backlog would otherwise trip GitHub's secondary rate limit.
PAUSE_SECONDS = 1.5


def read_packages():
    return [line.strip() for line in PACKAGES_FILE.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the issues that would change, change nothing")
    args = parser.parse_args()

    try:
        issues = fetch_issues(strict=True)
    except RuntimeError as e:
        sys.exit(str(e))

    no_issue, failed, changed = [], [], 0
    for package in read_packages():
        issue = oldest_open_issue(issues, package)
        if issue is None:
            no_issue.append(package)
            continue
        status = project_status(issue)
        if status in (STATUS_RISE, STATUS_UPSTREAM):
            continue
        prefix = "[dry-run] would set" if args.dry_run else "[+] set"
        print(f"{prefix} {package} #{issue['number']}: {status} -> {STATUS_RISE}")
        if args.dry_run:
            changed += 1
            continue
        try:
            set_issue_status(issue["url"], STATUS_RISE)
            changed += 1
            time.sleep(PAUSE_SECONDS)
        except subprocess.CalledProcessError as e:
            print(f"::warning::{package} #{issue['number']}: {e.stderr.strip()}")
            failed.append(package)

    print(f"{changed} issue(s) {'to update' if args.dry_run else 'updated'}, "
          f"{len(failed)} failed, {len(no_issue)} package(s) without an open issue")
    if no_issue:
        print("::group::Packages without an open '<pkg> riscv64 support' issue")
        print("\n".join(no_issue))
        print("::endgroup::")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
