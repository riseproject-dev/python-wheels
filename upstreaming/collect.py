# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Read-only collectors.

Every network call here is a GET. Nothing writes. Results are normalized
for ``controller.tick`` and ``ci_evidence``.

``Api`` wraps the GitHub REST API with the token in ``GH_TOKEN``/
``GITHUB_TOKEN`` (urllib, no third-party client), handles pagination and
refuses anything but a GET.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from . import ci_evidence
from .common import CONTROL_REPO, INTAKE_LABEL

API = "https://api.github.com"
_PATH_RE = re.compile(r"^/[A-Za-z0-9_./%?&=,:+-]*$")


class CollectError(RuntimeError):
    pass


class Api:
    def __init__(self, token: str | None = None, base: str = API, opener=None):
        self.token = token if token is not None else (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
        self.base = base
        self._open = opener or urllib.request.urlopen

    def _request(self, url: str) -> tuple[Any, dict]:
        req = urllib.request.Request(url, method="GET", headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "riseproject-upstreaming-collector",
            **({"Authorization": f"Bearer {self.token}"} if self.token else {}),
        })
        try:
            with self._open(req, timeout=30) as r:
                body = r.read()
                return (json.loads(body) if body else None), dict(r.headers)
        except urllib.error.HTTPError as e:
            raise CollectError(f"GET {url}: HTTP {e.code}") from None

    def get(self, path: str) -> Any:
        if not _PATH_RE.match(path) or ".." in path:
            raise CollectError(f"refusing unexpected API path {path!r}")
        return self._request(self.base + path)[0]

    def get_bytes(self, path: str, *, max_bytes: int = 8 * 1024 * 1024) -> bytes:
        """GET a binary resource (e.g. an artifact zip). The API redirects to
        blob storage; urllib follows it and drops Authorization cross-host."""
        if not _PATH_RE.match(path) or ".." in path:
            raise CollectError(f"refusing unexpected API path {path!r}")
        req = urllib.request.Request(self.base + path, method="GET", headers={
            "Accept": "application/vnd.github+json", "User-Agent": "riseproject-upstreaming-collector",
            **({"Authorization": f"Bearer {self.token}"} if self.token else {})})
        try:
            with self._open(req, timeout=60) as r:
                data = r.read(max_bytes + 1)
        except urllib.error.HTTPError as e:
            raise CollectError(f"GET {path}: HTTP {e.code}") from None
        if len(data) > max_bytes:
            raise CollectError("download exceeds size limit")
        return data

    def paginate(self, path: str, *, key: str | None = None, max_pages: int = 10) -> list:
        """Follow Link: rel=next up to ``max_pages``. ``key`` selects the list
        inside an object response (e.g. ``check_runs``)."""
        if not _PATH_RE.match(path) or ".." in path:
            raise CollectError(f"refusing unexpected API path {path!r}")
        url = self.base + path
        out: list = []
        for _ in range(max_pages):
            data, headers = self._request(url)
            out.extend(data[key] if key else data)
            nxt = _next_link(headers.get("Link") or headers.get("link") or "")
            if not nxt:
                break
            if not nxt.startswith(self.base + "/"):
                raise CollectError("pagination left the API host")
            url = nxt
        return out


def _next_link(link: str) -> str | None:
    for part in link.split(","):
        m = re.match(r'\s*<([^>]+)>;\s*rel="next"', part)
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------
# Control-repository inputs


def intake_issues(api: Api, max_pages: int = 3) -> list[dict]:
    items = api.paginate(f"/repos/{CONTROL_REPO}/issues?labels={INTAKE_LABEL}&state=open&per_page=50",
                         max_pages=max_pages)
    return [i for i in items if "pull_request" not in i]


def tracking_issue_context(issue: dict, expected: dict) -> dict:
    """Freeze the whole issue description into a task; never truncate it.
    The URL is constructed from the verified control-repository issue identity.
    Comments remain available for the agent to read through that URL/API."""
    from .common import sha256_text
    if issue.get("id") != expected["id"] or issue.get("number") != expected["number"]:
        raise CollectError("tracking issue identity changed")
    body = issue.get("body") or ""
    if not isinstance(body, str) or len(body.encode("utf-8")) > 16384:
        raise CollectError("tracking issue description exceeds the intake limit; not truncated")
    return {"id": issue["id"], "number": issue["number"],
            "url": f"https://github.com/{CONTROL_REPO}/issues/{issue['number']}",
            "description": body, "description_digest": sha256_text(body)}


def tracking_issues(api: Api, contributions: Iterable[dict], intake_issues: list[dict]) -> dict[int, dict]:
    """Fresh descriptions for every live tracked issue (not just labeled intake)."""
    from .lifecycle import TERMINAL
    issues = {i["number"]: i for i in intake_issues}
    for rec in contributions:
        n = rec["tracking_issue"]["number"]
        if rec["phase"] not in TERMINAL and n not in issues:
            issues[n] = api.get(f"/repos/{CONTROL_REPO}/issues/{n}")
    return issues


def label_acceptances(api: Api, issues: Iterable[dict], label: str, authority: Iterable[int]) -> dict[int, int]:
    """issue id -> the authorized actor who added ``label`` (from the issue's
    events). Adding the intake label is how a RISE owner accepts a request
    filed by someone else; anyone else adding it accepts nothing."""
    auth = set(authority)
    out: dict[int, int] = {}
    for i in issues:
        if i["user"]["id"] in auth:
            continue
        for ev in api.paginate(f"/repos/{CONTROL_REPO}/issues/{int(i['number'])}/events?per_page=100", max_pages=3):
            if ev.get("event") == "labeled" and (ev.get("label") or {}).get("name") == label \
                    and (ev.get("actor") or {}).get("id") in auth:
                out[i["id"]] = ev["actor"]["id"]
    return out


def dispatcher_runs(api: Api, workflow_file: str = "upstreaming-dispatcher.lock.yml") -> list[dict]:
    """Recent runs of the dispatcher workflow (newest first)."""
    return api.paginate(f"/repos/{CONTROL_REPO}/actions/workflows/{workflow_file}/runs?per_page=30",
                        key="workflow_runs", max_pages=1)


def command_comments(api: Api, issue_numbers: Iterable[int], since: str | None) -> list[dict]:
    """Comments on tracking issues that look like commands, for controller.Inputs.comments."""
    from .commands import looks_like_command
    out = []
    for n in issue_numbers:
        q = f"?per_page=100&since={urllib.parse.quote(since)}" if since else "?per_page=100"
        for c in api.paginate(f"/repos/{CONTROL_REPO}/issues/{int(n)}/comments{q}", max_pages=3):
            if looks_like_command(c.get("body") or ""):
                out.append({"issue_number": int(n), "comment": {"id": c["id"], "body": c["body"],
                                                                  "user": {"id": c["user"]["id"], "login": c["user"]["login"]}}})
    return out


def pull_request(api: Api, url: str) -> dict:
    """Verified PR resource for ``register-upstream-pr``."""
    parts = url.rstrip("/").split("/")
    if len(parts) != 7 or parts[:3] != ["https:", "", "github.com"] or parts[5] != "pull":
        raise CollectError("not a PR URL")
    pr = api.get(f"/repos/{parts[3]}/{parts[4]}/pulls/{int(parts[6])}")
    return {
        "id": pr["id"], "number": pr["number"], "html_url": pr["html_url"], "state": pr["state"],
        "base_repository": pr["base"]["repo"]["full_name"], "base_ref": pr["base"]["ref"],
        "head_repository": (pr["head"].get("repo") or {}).get("full_name"),
        "head_repository_id": (pr["head"].get("repo") or {}).get("id") or 0,
        "head_ref": pr["head"]["ref"], "head_sha": pr["head"]["sha"],
        "merged": pr.get("merged", False), "merge_commit_sha": pr.get("merge_commit_sha"),
    }


def user(api: Api, login: str) -> dict | None:
    """{"id", "login"} for a GitHub user, or None if there is no such user."""
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", login):
        return None
    try:
        u = api.get(f"/users/{login}")
    except CollectError as e:
        if "HTTP 404" in str(e):
            return None
        raise
    return {"id": u["id"], "login": u["login"]} if u.get("type") == "User" else None


FORK_ORG = "riseproject-upstreaming"


def verify_provisioning(api: Api, record: dict) -> dict:
    """Read-only check that a human-provisioned fork is ready (plan 10.1).

    The fork is ``riseproject-upstreaming/<upstream repo name>``. It must be a
    fork of the recorded upstream (same repository ID), not archived, and have
    a ``riscv64`` branch. The upstream base is the upstream default branch's
    current head unless the record names a base ref. Returns the facts the
    ``provision`` command records, or {"error": why}.
    """
    up_name = record["upstream"]["full_name"]
    fork = f"{FORK_ORG}/{up_name.split('/', 1)[1]}"
    try:
        upstream = api.get(f"/repos/{up_name}")
        f = api.get(f"/repos/{fork}")
    except CollectError as e:
        return {"error": f"cannot read {fork} or {up_name}: {e}"}
    if record["upstream"].get("repository_id") not in (None, upstream["id"]):
        return {"error": "upstream repository ID changed"}
    parent = f.get("parent") or {}
    if not f.get("fork") or parent.get("id") != upstream["id"]:
        return {"error": f"{fork} is not a fork of {up_name}"}
    if f.get("archived"):
        return {"error": f"{fork} is archived"}
    head = branch_head(api, fork, "riscv64")
    if head is None:
        return {"error": f"{fork} has no riscv64 branch"}
    base_ref = record["upstream"].get("base_ref") or upstream["default_branch"]
    base = branch_head(api, up_name, base_ref)
    if base is None:
        return {"error": f"{up_name} has no branch {base_ref}"}
    return {"fork": fork, "fork_id": f["id"], "head_sha": head["head"], "upstream_id": upstream["id"],
            "base_ref": base_ref, "base_sha": base["head"]}


# --------------------------------------------------------------------------
# Fork / branch state


def repository(api: Api, full_name: str) -> dict:
    r = api.get(f"/repos/{full_name}")
    return {"id": r["id"], "full_name": r["full_name"], "default_branch": r["default_branch"],
            "fork": r.get("fork", False), "archived": r.get("archived", False),
            "parent": (r.get("parent") or {}).get("full_name")}


def branch_head(api: Api, full_name: str, ref: str) -> dict | None:
    """{"head", "tree", "parents"} for a branch, or None if it does not exist."""
    try:
        b = api.get(f"/repos/{full_name}/branches/{urllib.parse.quote(ref, safe='')}")
    except CollectError as e:
        if "HTTP 404" in str(e):
            return None
        raise
    c = b["commit"]
    return {"head": c["sha"], "tree": c["commit"]["tree"]["sha"], "parents": [p["sha"] for p in c["parents"]]}


def dev_pull_request(api: Api, fork: str, ref: str = "riscv64") -> dict | None:
    owner = fork.split("/")[0]
    prs = api.get(f"/repos/{fork}/pulls?state=open&head={owner}:{ref}&per_page=10")
    return prs[0] if prs else None


# --------------------------------------------------------------------------
# Live CI


@dataclass
class CiSnapshot:
    repository: dict
    head_sha: str
    runs: list[dict] = field(default_factory=list)
    jobs_by_run: dict[int, list[dict]] = field(default_factory=dict)
    check_runs: list[dict] = field(default_factory=list)
    statuses: list[dict] = field(default_factory=list)
    artifacts_by_run: dict[int, list[dict]] = field(default_factory=dict)


def _norm_run(r: dict) -> dict:
    return {"id": r["id"], "head_sha": r["head_sha"], "run_attempt": r.get("run_attempt", 1),
            "status": r["status"], "conclusion": r.get("conclusion"), "workflow_id": r["workflow_id"],
            "event": r["event"], "path": r.get("path", ""), "name": r.get("name", ""),
            "created_at": r.get("created_at"), "head_branch": r.get("head_branch"),
            "pull_requests": [p["number"] for p in r.get("pull_requests") or []],
            "workflow_sha": None}


def _norm_job(j: dict) -> dict:
    return {"id": j["id"], "run_id": j["run_id"], "run_attempt": j.get("run_attempt", 1),
            "name": j["name"], "status": j["status"], "conclusion": j.get("conclusion"),
            "started_at": j.get("started_at"), "completed_at": j.get("completed_at"),
            "labels": j.get("labels") or [], "runner_name": j.get("runner_name"),
            "head_sha": j.get("head_sha")}


def ci_snapshot(api: Api, full_name: str, head_sha: str, *, max_runs: int = 30) -> CiSnapshot:
    """Everything CI says about one exact head SHA: workflow runs (all
    attempts resolve to the latest by run_attempt), their jobs for that
    attempt, check runs and commit statuses, and artifacts."""
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise CollectError("head_sha must be a full SHA")
    repo = repository(api, full_name)
    snap = CiSnapshot(repository=repo, head_sha=head_sha)
    runs = api.paginate(f"/repos/{full_name}/actions/runs?head_sha={head_sha}&per_page=50",
                        key="workflow_runs", max_pages=2)
    snap.runs = [_norm_run(r) for r in runs][:max_runs]
    for r in ci_evidence.latest_attempts(snap.runs):
        jobs = api.paginate(f"/repos/{full_name}/actions/runs/{r['id']}/attempts/{r['run_attempt']}/jobs?per_page=100",
                            key="jobs", max_pages=5)
        snap.jobs_by_run[r["id"]] = [_norm_job(j) for j in jobs]
        if r["status"] == "completed":
            arts = api.paginate(f"/repos/{full_name}/actions/runs/{r['id']}/artifacts?per_page=100",
                                key="artifacts", max_pages=2)
            snap.artifacts_by_run[r["id"]] = [{"id": a["id"], "name": a["name"], "size": a["size_in_bytes"],
                                               "digest": a.get("digest"), "expired": a.get("expired", False)}
                                              for a in arts]
    snap.check_runs = [{"id": c["id"], "name": c["name"], "status": c["status"], "conclusion": c.get("conclusion"),
                        "app": (c.get("app") or {}).get("slug")}
                       for c in api.paginate(f"/repos/{full_name}/commits/{head_sha}/check-runs?per_page=100",
                                             key="check_runs", max_pages=5)]
    snap.statuses = [{"context": s["context"], "state": s["state"]}
                     for s in api.paginate(f"/repos/{full_name}/commits/{head_sha}/statuses?per_page=100", max_pages=2)]
    return snap


def wheel_names_from_artifacts(snap: CiSnapshot) -> list[str]:
    """Upload-artifact names are not file names; wheel jobs in this ecosystem
    conventionally name artifacts after the wheel or ``wheels-<tag>``, or
    ``<python>-<platform>-...``. This returns names ending in .whl and the
    names of artifacts that mention riscv64; callers that need exact files
    download the artifact in a sandbox (never in a credentialed job)."""
    return sorted({a["name"] for arts in snap.artifacts_by_run.values() for a in arts
                   if not a["expired"] and (a["name"].endswith(".whl") or "riscv64" in a["name"])
                   and a.get("size", 1) > 0})


def evaluate_snapshot(snap: CiSnapshot, *, required_job_patterns: list[str], expected_wheels: list[str],
                      produced_wheels: list[str] | None = None) -> ci_evidence.CiVerdict:
    produced = produced_wheels if produced_wheels is not None else wheel_names_from_artifacts(snap)
    return ci_evidence.evaluate(runs=snap.runs, jobs_by_run=snap.jobs_by_run, head_sha=snap.head_sha,
                                required_job_patterns=required_job_patterns,
                                expected_wheels=expected_wheels, produced_wheels=produced)


# --------------------------------------------------------------------------
# Other sources


def pypi_release(distribution: str, opener=None) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", distribution):
        raise CollectError("invalid distribution name")
    with (opener or urllib.request.urlopen)(f"https://pypi.org/pypi/{distribution}/json", timeout=30) as r:
        return json.load(r)


def usage(url: str, opener=None) -> tuple[Any, datetime]:
    with (opener or urllib.request.urlopen)(url, timeout=30) as r:
        return json.load(r), datetime.now(timezone.utc)


def ecosystem_report(api: Api, project: str) -> str | None:
    """The sw-ecosystem project report for ``project``, if one exists (plan step 2)."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", project):
        raise CollectError("invalid project name")
    try:
        data = api.get(f"/repos/riseproject-dev/sw-ecosystem/contents/project-reports/{project}.md")
    except CollectError as e:
        if "HTTP 404" in str(e):
            return None
        raise
    import base64
    return base64.b64decode(data["content"]).decode("utf-8", "replace")
