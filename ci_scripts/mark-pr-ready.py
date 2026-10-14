#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyGithub>=2.7"]
# ///
"""Keep open pull requests' draft state in sync with their latest workflows.

For each PR, this script examines only GitHub Actions workflow runs whose
``head_sha`` is the PR's latest commit.  Within that commit, only the newest
run of each workflow that actually created jobs is considered, so rerun or
overlapping workflow attempts do not leave stale failures behind.

A PR is marked ready if and only if every latest workflow run completed with a
``success`` or ``skipped`` conclusion.  It is converted to draft for every
other state, including queued/running workflows, failures, and no workflows.

With ``--merge``, passing PRs are marked ready and squash-merged.  GitHub still
enforces branch protection, required reviews, and mergeability.

The token needs pull-request write and actions read access; merging also needs
contents write access.  Example:

    GH_TOKEN=... uv run ci_scripts/mark-pr-ready.py

In GitHub Actions, GITHUB_TOKEN is used by default.
"""

import argparse
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass

from github import Auth, Github
from github.PullRequest import PullRequest
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun

REPOSITORY = "riseproject-dev/python-wheels"
PASSING_CONCLUSIONS = {"success", "skipped"}


@dataclass(frozen=True)
class WorkflowState:
    state: str
    runs: tuple[WorkflowRun, ...]


def latest_workflow_runs(runs: Iterable[WorkflowRun]) -> tuple[WorkflowRun, ...]:
    """Return the newest run for each workflow ID.

    Run IDs increase over time.  A rerun of one run is exposed by GitHub as the
    same workflow run with its latest attempt's status and conclusion.
    """
    latest = {}
    for run in runs:
        previous = latest.get(run.workflow_id)
        if previous is None or run.id > previous.id:
            latest[run.workflow_id] = run
    return tuple(latest.values())


def workflow_state(runs: Iterable[WorkflowRun]) -> WorkflowState:
    latest = latest_workflow_runs(runs)
    # GitHub can create an immediately-failed workflow-run record with no jobs
    # when a workflow does not apply to the PR.  It is absent from the PR's
    # check rollup and must not count as a workflow that ran.  PR #2996's
    # "Build and deploy website" run is one such record.
    latest = tuple(run for run in latest if run.jobs().totalCount > 0)
    if not latest:
        return WorkflowState("none", latest)

    # Evaluate only the newest run of each workflow.  In particular, do not
    # let a failed job in an older overlapping run override a newer queued or
    # running workflow, as happened on PR #3220.
    if any(run.status != "completed" for run in latest):
        return WorkflowState("pending", latest)
    if any(run.conclusion not in PASSING_CONCLUSIONS for run in latest):
        return WorkflowState("failing", latest)
    return WorkflowState("passing", latest)


def sync_pull_request(
    repo: Repository, pr: PullRequest, dry_run: bool, merge: bool
) -> str:
    head_sha = pr.head.sha
    # Restrict evaluation to workflows for the PR's latest commit.  Pass the
    # SHA to GitHub and also check every returned run locally so workflows for
    # an older PR commit can never affect the result.
    runs = (
        run for run in repo.get_workflow_runs(head_sha=head_sha)
        if run.head_sha == head_sha
    )
    state = workflow_state(runs)
    actions = []

    if state.state == "passing":
        if pr.draft:
            actions.append("mark ready")
            if not dry_run:
                pr.mark_ready_for_review()
        if merge:
            actions.append("squash merge")
            if not dry_run:
                result = pr.merge(merge_method="squash", sha=pr.head.sha)
                if not result.merged:
                    actions[-1] = f"merge rejected: {result.message}"
    elif not pr.draft:
        actions.append("convert to draft")
        if not dry_run:
            pr.convert_to_draft()

    action = "; ".join(actions) if actions else "unchanged"
    details = ", ".join(
        f"{run.name or run.workflow_id}={run.status}/{run.conclusion or '-'}"
        for run in sorted(state.runs, key=lambda item: item.workflow_id)
    )
    if not details:
        details = "no workflows"
    print(f"PR #{pr.number}: {state.state}; {action} ({details})")
    return action


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token",
        default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
        help="GitHub token (default: $GH_TOKEN, then $GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--pr",
        type=int,
        action="append",
        dest="prs",
        metavar="NUMBER",
        help="process only this PR (repeatable; default: every open PR)",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="squash-merge PRs whose latest workflows all passed or skipped",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report changes without applying them"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.token:
        raise SystemExit("--token, GH_TOKEN, or GITHUB_TOKEN is required")

    github = Github(auth=Auth.Token(args.token))
    try:
        repo = github.get_repo(REPOSITORY)
        if args.prs:
            pull_requests = (repo.get_pull(number) for number in args.prs)
        else:
            # PyGithub paginates this collection lazily, so this processes
            # every open PR rather than only the API's first page.
            pull_requests = repo.get_pulls(
                state="open", sort="created", direction="desc"
            )

        for pr in pull_requests:
            if pr.state != "open":
                print(f"PR #{pr.number}: closed; unchanged")
                continue
            sync_pull_request(repo, pr, args.dry_run, args.merge)
    finally:
        github.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
