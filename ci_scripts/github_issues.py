# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Shared helpers for the "<pkg> riscv64 support" issues and their status in
the "Python Wheels" project.

Uses the ``gh`` CLI. Reading project fields needs the ``read:project`` scope,
changing them the ``project`` scope (for the GitHub App: the organization
"Projects: read and write" permission).
"""

import json
import re
import subprocess
import sys

OWNER = "riseproject-dev"
REPO_NAME = "python-wheels"
REPO = f"{OWNER}/{REPO_NAME}"

# Projects > "Python Wheels - riseproject-dev/python-wheels". Node IDs rather
# than names, so that the edit works with any gh version (item-edit only
# recently learned --field/--value) and a project rename changes nothing.
PROJECT_NUMBER = 4
PROJECT_ID = "PVT_kwDOCRlTBM4BbcwJ"
STATUS_FIELD_ID = "PVTSSF_lADOCRlTBM4BbcwJzhWNMvs"
STATUS_TODO = "Todo"
STATUS_RISE = "Available in RISE PyPI"
STATUS_UPSTREAM = "Available Upstream"
STATUS_OPTION_IDS = {
    STATUS_TODO: "f75ad846",
    STATUS_RISE: "47fc9ee4",
    STATUS_UPSTREAM: "98236657",
}

TITLE_RE = re.compile(r"^\s*(.+?)\s+riscv64\s+support\s*$", re.IGNORECASE)

QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url state
        %s
      }
    }
  }
}
"""

PROJECT_FIELDS = """
        projectItems(first: 10) {
          nodes {
            project { id }
            status: fieldValueByName(name: "Status") {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
          }
        }"""


def normalize_name(name):
    """
    https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def fetch_issues(owner=OWNER, repo=REPO_NAME, with_project=True, strict=False):
    """
    Return {normalised package name: [issue, ...]} for "<pkg> riscv64 support"
    issues, open and closed, oldest first.

    Without the read:project scope the project fields are dropped with a
    warning, unless `strict`, where that and any other GraphQL error raise
    RuntimeError instead.
    """
    query = QUERY % (PROJECT_FIELDS if with_project else "")
    by_name = {}
    cursor = None
    while True:
        cmd = ["gh", "api", "graphql", "-f", f"query={query}",
               "-F", f"owner={owner}", "-F", f"repo={repo}"]
        if cursor:
            cmd += ["-F", f"cursor={cursor}"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            data = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            data = {}
        if with_project and not strict and "read:project" in proc.stderr:
            print("warning: token lacks the read:project scope, project status unavailable"
                  " (gh auth refresh -h github.com -s read:project)", file=sys.stderr)
            return fetch_issues(owner, repo, with_project=False)
        if "data" not in data or data["data"] is None:
            raise RuntimeError(f"gh api graphql failed: {proc.stderr.strip() or data}")
        if data.get("errors"):
            msgs = "; ".join(sorted({e.get("message", "") for e in data["errors"]}))
            if strict:
                raise RuntimeError(f"gh api graphql failed: {msgs}")
            print(f"warning: {msgs}", file=sys.stderr)
        issues = data["data"]["repository"]["issues"]
        for issue in issues["nodes"]:
            m = TITLE_RE.match(issue["title"])
            if m:
                by_name.setdefault(normalize_name(m.group(1)), []).append(issue)
        if not issues["pageInfo"]["hasNextPage"]:
            return by_name
        cursor = issues["pageInfo"]["endCursor"]


def oldest_open_issue(issues, package):
    """The package's oldest open issue in fetch_issues() output, or None."""
    for issue in issues.get(normalize_name(package), []):
        if issue["state"] == "OPEN":
            return issue
    return None


def project_status(issue):
    if "projectItems" not in issue:
        return "(unknown)"
    for item in (issue.get("projectItems") or {}).get("nodes") or []:
        if item and item["project"]["id"] == PROJECT_ID:
            return (item.get("status") or {}).get("name") or "(no status)"
    return "(not in project)"


def set_issue_status(issue_url, status):
    """
    Add the issue to the project (a no-op when it is already there) and set its
    Status. Raises subprocess.CalledProcessError when gh fails.
    """
    item_id = subprocess.run(
        ["gh", "project", "item-add", str(PROJECT_NUMBER), "--owner", OWNER,
         "--url", issue_url, "--format", "json", "--jq", ".id"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run(
        ["gh", "project", "item-edit", "--id", item_id,
         "--project-id", PROJECT_ID, "--field-id", STATUS_FIELD_ID,
         "--single-select-option-id", STATUS_OPTION_IDS[status]],
        capture_output=True, text=True, check=True,
    )
