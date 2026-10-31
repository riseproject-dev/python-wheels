#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyGithub>=2.7", "pyyaml"]
# ///
"""Delete the GitHub Releases that no package YAML links to.

Every publication creates a new release named `<package>-v<version>-<UTC
timestamp>` and records its tag in `docs/packages/<package>.yaml`; a rebuild of
the same version creates another release and the YAML moves on to its tag, so
the older ones pile up.  This script deletes every release whose tag is not
the `tag` of a version entry of a package YAML, unless that tag is still
needed:

- the YAML read is the checkout's `docs/packages/` (run it on `main`);
- a tag recorded by the YAML of an open pull request from a `package/<pkg>`
  branch (the publication PR waiting to be merged) is kept, since merging that
  PR makes the release reachable;
- only releases that look like ours (`<name>-v<version>-<14 digits>`) are ever
  touched, so a hand-made release is left alone.

Draft releases left behind by a publication that failed halfway are collected
the same way.  Deleting a release does not delete its git tag: an immutable
release's tag cannot be removed anyway.

It refuses to run when no tag is found in the YAML or when it would delete more
than `--max-delete-fraction` of the releases, either of which means the YAML
could not be read as expected.

The token needs contents write access and pull-request read access (the
workflow uses the riseproject-dev App's).  Run it
in the `publish-wheel` concurrency group so no publication is in flight.
Example:

    GH_TOKEN=... uv run ci_scripts/gc-releases.py --dry-run

In GitHub Actions, GITHUB_TOKEN is used by default.
"""

import argparse
import os
import re
import sys
from pathlib import Path

import yaml
from github import Auth, Github, GithubException
from github.Repository import Repository

REPOSITORY = "riseproject-dev/python-wheels"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "packages"
# <normalized-package>-v<version>-<UTC timestamp>, see _publish-wheel.yml.
PACKAGE_BRANCH_PREFIX = "package/"
RELEASE_TAG_RE = re.compile(r"^.+-v.+-\d{14}$")


def tags_in_yaml(text: str, source: str) -> set[str]:
    """The release tags recorded by the version entries of one package YAML."""
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"{source}: invalid YAML: {exc}")
    return {
        str(entry["tag"])
        for entry in data.get("versions") or []
        if isinstance(entry, dict) and entry.get("tag")
    }


def tags_on_disk(docs_dir: Path) -> set[str]:
    tags = set()
    for path in sorted(docs_dir.glob("*.yaml")):
        tags |= tags_in_yaml(path.read_text(), str(path))
    return tags


def tags_in_open_prs(repo: Repository) -> set[str]:
    """Tags recorded by the package YAMLs an open `package/*` branch PR changes."""
    tags = set()
    for pr in repo.get_pulls(state="open"):
        if not pr.head.ref.startswith(PACKAGE_BRANCH_PREFIX):
            continue
        if pr.head.repo is None or pr.head.repo.full_name != repo.full_name:
            continue
        for changed in pr.get_files():
            if not re.fullmatch(r"docs/packages/[^/]+\.yaml", changed.filename):
                continue
            if changed.status == "removed":
                continue
            content = repo.get_contents(changed.filename, ref=pr.head.sha)
            tags |= tags_in_yaml(
                content.decoded_content.decode(), f"PR #{pr.number} {changed.filename}"
            )
    return tags


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token",
        default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
        help="GitHub token (default: $GH_TOKEN, then $GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report deletions without applying them"
    )
    parser.add_argument(
        "--max-delete-fraction",
        type=float,
        default=0.5,
        metavar="FRACTION",
        help="refuse to delete more than this fraction of our releases "
        "(default: %(default)s)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.token:
        raise SystemExit("--token, GH_TOKEN, or GITHUB_TOKEN is required")

    referenced = tags_on_disk(DOCS_DIR)
    if not referenced:
        raise SystemExit(f"no release tag found under {DOCS_DIR}; refusing to delete")
    print(f"{len(referenced)} release tags are linked from {DOCS_DIR.name}/")

    github = Github(auth=Auth.Token(args.token))
    failures = 0
    try:
        repo = github.get_repo(REPOSITORY)
        pending = tags_in_open_prs(repo) - referenced
        print(f"{len(pending)} more are recorded by open pull requests")
        keep = referenced | pending

        ours = [
            release
            for release in repo.get_releases()
            if RELEASE_TAG_RE.match(release.tag_name)
        ]
        garbage = [release for release in ours if release.tag_name not in keep]
        print(f"{len(garbage)} of {len(ours)} releases are not linked")

        if len(garbage) > args.max_delete_fraction * len(ours):
            raise SystemExit(
                f"would delete {len(garbage)} of {len(ours)} releases, more than "
                f"--max-delete-fraction={args.max_delete_fraction}; refusing"
            )

        for release in garbage:
            state = "draft" if release.draft else "published"
            if args.dry_run:
                print(f"would delete {release.tag_name} ({state})")
                continue
            try:
                release.delete_release()
            except GithubException as exc:
                print(f"{release.tag_name}: could not delete: {exc}")
                failures += 1
            else:
                print(f"deleted {release.tag_name} ({state})")
    finally:
        github.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
