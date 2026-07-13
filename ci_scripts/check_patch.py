# SPDX-FileCopyrightText: 2025 BayLibre, SAS
# SPDX-FileCopyrightText: 2026 The RISE Project

# SPDX-License-Identifier: Apache-2.0
"""
This script is based on the one located at:

https://gitlab.com/riseproject/python/wheel_builder/-/blob/main/ci_scripts/check_patch.py

Its purpose is to check the contents of patches (commits) submitted to the
project for aan "Upstream-Status" tag, which is inspired by the same tag used
in the Yocto Project:

https://docs.yoctoproject.org/dev/contributor-guide/recipe-style-guide.html#patch-upstream-status

See the valid_statuses dictionary below for types of Upstream-Status tags
accepted.
"""

import sys
import subprocess
import re

valid_statuses = {
    "Issue": {
        "value": r"^\[https?://\S+\]$",  # Mandatory url in brackets
        "hint": "[url]",
        "mandatory": True,
        "description": "Brackets enclosed url of the issue opened on upstream project",
    },
    "Submitted": {
        "value": r"^\[https?://\S+\]$",  # Mandatory url in brackets
        "hint": "[url]",
        "mandatory": True,
        "description": "Brackets enclosed url of the merge request opened on upstream project",
    },
    "To upstream": {
        "value": r"^(\[.*\])?$",  # Optional comment in brackets
        "hint": "[comment]",
        "mandatory": False,
        "description": "Optional brackets enclosed comment to add any useful information for future upstream submission",
    },
    "Inappropriate": {
        "value": r"^\[.+\]$",  # Any comment in brackets
        "hint": "[comment]",
        "mandatory": True,
        "description": "Brackets enclosed reason why the patch is inappropriate for upstream",
    },
    "Backport": {
        "value": r"^\[https?://\S+\]$",  # Mandatory url in brackets
        "hint": "[url]",
        "mandatory": True,
        "description": "Brackets enclosed url of the backported patch",
    },
}


def get_commits_between(start_ref, end_ref):
    """Get commit hashes between two branches or commits."""
    cmd = ["git", "rev-list", f"{start_ref}..{end_ref}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def get_commit_files(commit):
    """Get a list of patch files added or modified in a commit."""
    cmd = ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", commit]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    files = []
    for line in result.stdout.splitlines():
        status, filename = line.split("\t", 1)
        if status in ("A", "M") and filename.endswith(".patch"):
            files.append(filename)
    return files


def extract_patch_from_commit(commit, patch_file):
    """Extract a patch file from a given commit."""
    cmd = ["git", "show", f"{commit}:{patch_file}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WARNING: Could not extract {patch_file} from commit {commit}")
        return None
    return result.stdout


def check_upstream_status(patch_content, patch):
    """Check if the Upstream-Status tag is correctly formatted in a patch file."""

    status_key = "|".join(valid_statuses.keys())
    match = re.search(r"^Upstream-Status: *(.*)$", patch_content, re.MULTILINE)

    if not match:
        print(f"❌Missing Upstream-Status tag in {patch}")
        return False

    value = match.groups()

    match = re.search(rf"^({status_key}|\w+) *(.*)$", value[0], re.MULTILINE)

    status, extra = match.groups()

    if status not in valid_statuses.keys():
        print(f"❌Invalid Upstream-Status '{status}' in {patch}")
        return False

    if not re.match(valid_statuses[status]["value"], extra):
        print(f"❌Incorrect format for Upstream-Status '{status}' in {patch}")
        return False

    return True


def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <start_branch_or_commit> <end_branch_or_commit>")
        sys.exit(1)

    start_ref, end_ref = sys.argv[1], sys.argv[2]
    commits = get_commits_between(start_ref, end_ref)

    error_found = False

    for commit in commits:
        patch_files = get_commit_files(commit)
        for patch in patch_files:
            patch_content = extract_patch_from_commit(commit, patch)
            if patch_content:
                if not check_upstream_status(patch_content, patch):
                    error_found = True
                else:
                    print(f"✅{patch}")

    if error_found:
        print("Valid formats:")
        for key, value in valid_statuses.items():
            print(f"  - Upstream-Status: {key} {value["hint"]}")
            print(
                f"    {value["hint"]}: {value["description"]} {'(mandatory)' if value["mandatory"] else ''}"
            )
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
