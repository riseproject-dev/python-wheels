#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyGithub>=2.7", "requests>=2.31"]
# ///
"""Run the four steps that remain once a package PR is merged.

Merging a package PR pushes its pending `- version:` entry to `main`, and
`build-<pkg>.yml`'s own `push` trigger builds and publishes it -- this script
never dispatches a build itself. What is left, and what this script does, for
`<pr>`/`<pkg>`:

1. **Check the publish**: confirm `build-<pkg>.yml` has a completed,
   successful run for the `push` event on `main`, then confirm
   `https://pypi.riseproject.dev/simple/<pkg>/` returns 200. A 302 means the
   request redirected to real PyPI, i.e. we do not host it yet -- redirects
   are never followed.
2. **Issue**: find an existing issue titled `<pkg> riscv64 support` (matching
   on a normalised name, case-insensitively, since a title does not always
   match the PyPI name exactly -- "SGLang", "LibCST", "PyNaCl"; the oldest
   wins when several match) or create one, labelled `wheel`, body shaped like
   `.github/ISSUE_TEMPLATE/package-request.yml`.
3. **Development link**: link the PR to the issue via the same
   `addCloseIssueReferences` mutation GitHub's own Development panel uses
   (works for an already-merged PR, unlike a closing keyword in the body),
   and confirm it with the PR's own `closingIssuesReferences`.
4. **Project**: add the issue to the *Python Wheels* project and set its
   Status field to *Available in RISE PyPI*.

Every step is idempotent: an existing issue is reused rather than duplicated,
an existing Development link or project item is left as is.

PyGithub (the REST API) does the first three steps; PyGithub has no GraphQL
client, so the Development link and the Project v2 item/field updates go
straight to https://api.github.com/graphql over `requests`, the same way
mark-pr-ready.py's convert_to_draft()/mark_ready_for_review() reach a REST
route PyGithub does not cover.

The token needs `repo` and `project` scopes -- `gh auth refresh -h github.com
-s project` adds the latter to a `gh`-managed token if missing. Example:

    GH_TOKEN=... uv run ci_scripts/package-postmerge.py 3318 pyarrow

PR #390 <-> issue #405 is a reference pair to diff a new one against.
"""

import argparse
import os
import re
import sys

import requests
from github import Auth, Github
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository

REPO = "riseproject-dev/python-wheels"
WHEEL_LABEL = "wheel"
PYPI_SIMPLE_URL = "https://pypi.riseproject.dev/simple/{pkg}/"
GRAPHQL_URL = "https://api.github.com/graphql"

# Projects > Python Wheels, its Status field, and the "Available in RISE
# PyPI" option -- see skills/python-project-porting/references/pr-and-publishing.md.
PROJECT_ID = "PVT_kwDOCRlTBM4BbcwJ"
STATUS_FIELD_ID = "PVTSSF_lADOCRlTBM4BbcwJzhWNMvs"
STATUS_AVAILABLE_IN_RISE_PYPI = "47fc9ee4"

LINK_PR_TO_ISSUE_MUTATION = """
mutation($issueId: ID!, $prIds: [ID!]!) {
  addCloseIssueReferences(input: {issueId: $issueId, pullRequestIds: $prIds}) {
    clientMutationId
  }
}
"""

CLOSING_ISSUES_QUERY = """
query($id: ID!) {
  node(id: $id) {
    ... on PullRequest {
      closingIssuesReferences(first: 50) {
        nodes { number }
      }
    }
  }
}
"""

ADD_TO_PROJECT_MUTATION = """
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
"""

SET_STATUS_MUTATION = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId, itemId: $itemId, fieldId: $fieldId,
    value: {singleSelectOptionId: $optionId}
  }) {
    projectV2Item { id }
  }
}
"""


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def graphql(token: str, query: str, **variables):
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]


def parse_pr_fields(body: str) -> dict[str, str]:
    """Extract the `* **Field**: value` lines of the PR description template."""
    fields = {}
    for line in body.splitlines():
        match = re.match(r"\*\s*\*\*([^*]+)\*\*:\s*`?([^`]+?)`?\s*$", line.strip())
        if match:
            fields[match.group(1).strip().lower()] = match.group(2).strip()
    return fields


def check_publish(repo: Repository, pkg: str) -> None:
    workflow = repo.get_workflow(f"build-{pkg}.yml")
    runs = workflow.get_runs(branch="main", event="push")
    if runs.totalCount == 0:
        raise SystemExit(f"no `push` run of build-{pkg}.yml on main yet")
    latest = runs[0]
    if latest.status != "completed":
        raise SystemExit(f"push run is still {latest.status}: {latest.html_url}")
    if latest.conclusion != "success":
        raise SystemExit(
            f"push run did not succeed ({latest.conclusion}): {latest.html_url}"
        )

    url = PYPI_SIMPLE_URL.format(pkg=pkg)
    response = requests.get(url, allow_redirects=False, timeout=15)
    if response.status_code != 200:
        raise SystemExit(
            f"{url} returned {response.status_code}, not 200 -- a 302 means the "
            "request redirected to real PyPI, i.e. we do not host it yet (gotcha 30)"
        )
    print(f"[1/4] build-{pkg}.yml's push run succeeded; {url} returns 200")


def find_existing_issue(github: Github, pkg: str) -> Issue | None:
    target = normalize_name(pkg)
    suffix_re = re.compile(r"\s*riscv64 support\s*$", re.IGNORECASE)
    matches = [
        issue
        for issue in github.search_issues(
            '"riscv64 support" in:title', repo=REPO, **{"is": "issue"}
        )
        if normalize_name(suffix_re.sub("", issue.title)) == target
    ]
    if not matches:
        return None
    # Several matches is already a known problem (bcrypt has four) -- link the
    # oldest, matching what this repo already does (#82, #84, #94).
    matches.sort(key=lambda issue: issue.number)
    return matches[0]


def create_issue(
    repo: Repository, pkg: str, pr_number: int, source_repo: str | None
) -> Issue:
    title = f"{pkg} riscv64 support"
    body = (
        "### Package name (on PyPI)\n\n"
        f"{pkg}\n\n"
        "### Source repository\n\n"
        f"{source_repo or '_No response_'}\n\n"
        "### Version(s) requested\n\n"
        "_No response_\n\n"
        "### Why is this needed?\n\n"
        f"riscv64 wheel build added in #{pr_number}\n\n"
        "### Additional context\n\n"
        "_No response_"
    )
    return repo.create_issue(title=title, body=body, labels=[WHEEL_LABEL])


def ensure_linked(token: str, pr: PullRequest, issue: Issue) -> None:
    pr_node_id, issue_node_id = pr.node_id, issue.node_id

    def linked_issue_numbers() -> set[int]:
        data = graphql(token, CLOSING_ISSUES_QUERY, id=pr_node_id)
        return {
            node["number"] for node in data["node"]["closingIssuesReferences"]["nodes"]
        }

    if issue.number in linked_issue_numbers():
        print(f"[3/4] PR #{pr.number} is already linked to issue #{issue.number}")
        return

    graphql(
        token,
        LINK_PR_TO_ISSUE_MUTATION,
        issueId=issue_node_id,
        prIds=[pr_node_id],
    )
    if issue.number not in linked_issue_numbers():
        raise SystemExit(
            f"addCloseIssueReferences did not take -- PR #{pr.number}'s "
            f"closingIssuesReferences still does not include #{issue.number}"
        )
    print(f"[3/4] linked PR #{pr.number} -> issue #{issue.number}")


def ensure_in_project(token: str, issue: Issue) -> None:
    added = graphql(
        token, ADD_TO_PROJECT_MUTATION, projectId=PROJECT_ID, contentId=issue.node_id
    )
    item_id = added["addProjectV2ItemById"]["item"]["id"]
    graphql(
        token,
        SET_STATUS_MUTATION,
        projectId=PROJECT_ID,
        itemId=item_id,
        fieldId=STATUS_FIELD_ID,
        optionId=STATUS_AVAILABLE_IN_RISE_PYPI,
    )
    print(
        f"[4/4] issue #{issue.number} is in Python Wheels, Status = Available in RISE PyPI"
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr", type=int, help="the merged package PR's number")
    parser.add_argument("pkg", help="the package slug (matches build-<pkg>.yml)")
    parser.add_argument(
        "--token",
        default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
        help="GitHub token (default: $GH_TOKEN, then $GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report planned actions without applying them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.token:
        raise SystemExit("--token, GH_TOKEN, or GITHUB_TOKEN is required")

    github = Github(auth=Auth.Token(args.token))
    try:
        repo = github.get_repo(REPO)
        check_publish(repo, args.pkg)

        pr = repo.get_pull(args.pr)
        pr_fields = parse_pr_fields(pr.body or "")
        source_repo = pr_fields.get("source")

        issue = find_existing_issue(github, args.pkg)
        if issue:
            print(f"[2/4] reusing existing issue #{issue.number}: {issue.title}")
        elif args.dry_run:
            print(f"[2/4] [dry-run] would create issue '{args.pkg} riscv64 support'")
            print("[dry-run] stopping here -- the remaining steps need the issue's id")
            return 0
        else:
            issue = create_issue(repo, args.pkg, args.pr, source_repo)
            print(f"[2/4] created issue #{issue.number}: {issue.html_url}")

        if args.dry_run:
            print(f"[dry-run] would link PR #{args.pr} -> issue #{issue.number}")
            print(
                f"[dry-run] would add issue #{issue.number} to Python Wheels, "
                "Status = Available in RISE PyPI"
            )
            return 0

        ensure_linked(args.token, pr, issue)
        ensure_in_project(args.token, issue)
    finally:
        github.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
