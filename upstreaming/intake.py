# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Issue intake and command acceptance (plan sections 7.1 to 7.3).

Cheap, deterministic filters that run before the serialized controller or any
model invocation. Public issues and labels grant no write or CI-spending
authority: an intake request only becomes a ``queued`` contribution, and a
command only applies if its immutable actor ID is in the reviewed authority
list at acceptance time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from . import commands
from .common import CONTROL_REPO, INTAKE_LABEL, normalize_distribution, sha256_text

INTAKE_ACTIONS = frozenset({"opened", "labeled", "reopened"})
COMMENT_ACTIONS = frozenset({"created", "edited"})

_REPO_URL = re.compile(r"^https://github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9_.-]{1,100}?)(?:\.git)?/?$")
_DIST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")

# Headings produced by .github/ISSUE_TEMPLATE/upstreaming-request.yml.
FIELDS = {
    "Upstream repository": "upstream",
    "PyPI distributions": "distributions",
    "Upstream target branch": "target_branch",
    "Additional notes": "notes",
}


class IntakeError(ValueError):
    pass


@dataclass(frozen=True)
class Request:
    issue_id: int
    issue_number: int
    actor_id: int
    upstream: str            # owner/name
    distributions: tuple[str, ...]
    target_branch: str | None
    notes: str
    digest: str


def parse_issue_form(body: str) -> dict[str, str]:
    """Split a GitHub issue-form body (``### Heading`` sections)."""
    out: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m and m.group(1) in FIELDS:
            if current:
                out[current] = "\n".join(buf).strip()
            current, buf = FIELDS[m.group(1)], []
        elif current:
            buf.append(line)
    if current:
        out[current] = "\n".join(buf).strip()
    return {k: ("" if v == "_No response_" else v) for k, v in out.items()}


def canonical_repo(url: str) -> str:
    """Accept canonical GitHub repository URLs only. No credentials, other
    hosts, query strings, fragments or extra path components."""
    url = url.strip()
    m = _REPO_URL.match(url)
    if not m or "@" in url:
        raise IntakeError("upstream repository must be https://github.com/<owner>/<repo>")
    owner, name = m.group(1), m.group(2)
    if name in (".", "..") or name.endswith("."):
        raise IntakeError("invalid repository name")
    return f"{owner}/{name}"


def filter_event(event_name: str, payload: dict[str, Any], policy: dict) -> str | None:
    """Return None if the event deserves controller attention, else why not.
    Cheap enough to run on every public event."""
    repo = (payload.get("repository") or {}).get("full_name")
    if repo != CONTROL_REPO:
        return "event is not for the control repository"
    if event_name == "issues":
        if payload.get("action") not in INTAKE_ACTIONS:
            return "unsupported issue action"
        labels = {lbl.get("name") for lbl in (payload.get("issue") or {}).get("labels", [])}
        if INTAKE_LABEL not in labels:
            return "missing intake label"
        body = (payload.get("issue") or {}).get("body") or ""
        if len(body.encode("utf-8")) > policy["intake"]["max_request_bytes"]:
            return "request too large"
        return None
    if event_name == "issue_comment":
        if payload.get("action") not in COMMENT_ACTIONS:
            return "unsupported comment action"
        body = (payload.get("comment") or {}).get("body") or ""
        if not commands.looks_like_command(body):
            return "not a command"
        actor = ((payload.get("comment") or {}).get("user") or {}).get("id")
        if actor not in policy["command_authority"]["actor_ids"]:
            return "actor is not an authorized command actor"
        return None
    if event_name in ("schedule", "workflow_dispatch"):
        return None
    return f"unsupported event {event_name}"


def parse_request(issue: dict, policy: dict) -> Request:
    body = issue.get("body") or ""
    if len(body.encode("utf-8")) > policy["intake"]["max_request_bytes"]:
        raise IntakeError("request too large")
    form = parse_issue_form(body)
    upstream = canonical_repo(form.get("upstream", ""))
    dists: list[str] = []
    for line in form.get("distributions", "").splitlines():
        token = line.strip().lstrip("-* ").split()[0] if line.strip() else ""
        if not token:
            continue
        if not _DIST.match(token):
            raise IntakeError(f"invalid distribution name {token!r}")
        n = normalize_distribution(token)
        if n not in dists:
            dists.append(n)
    if not dists:
        raise IntakeError("at least one PyPI distribution is required")
    if len(dists) > policy["intake"]["max_distributions"]:
        raise IntakeError("too many distributions")
    branch = form.get("target_branch", "").strip() or None
    if branch is not None and (not _BRANCH.match(branch) or ".." in branch):
        raise IntakeError("invalid target branch")
    return Request(
        issue_id=issue["id"], issue_number=issue["number"], actor_id=issue["user"]["id"],
        upstream=upstream, distributions=tuple(dists), target_branch=branch,
        notes=form.get("notes", ""), digest=sha256_text(body),
    )


def admission_decision(req: Request, *, accepted_by: int | None, policy: dict,
                       active_by_upstream: dict[str, str], parked_upstreams: Iterable[str],
                       known_issue_ids: Iterable[int], requests_today_by_actor: int) -> tuple[str, str | None]:
    """Decide what to do with a parsed request.

    Returns (decision, detail): ``accept`` (create a queued contribution),
    ``duplicate`` (link to the canonical contribution in detail), ``parked``
    (link, never resume), ``await_acceptance``, or ``rate_limited``.
    """
    if req.issue_id in set(known_issue_ids):
        return "duplicate", "issue already processed"
    key = req.upstream.lower()
    if key in {u.lower() for u in parked_upstreams}:
        return "parked", "project is parked; a duplicate request cannot resume it"
    active = {k.lower(): v for k, v in active_by_upstream.items()}
    if key in active:
        return "duplicate", active[key]
    authority = set(policy["command_authority"]["actor_ids"])
    if req.actor_id not in authority and accepted_by not in authority:
        if requests_today_by_actor >= policy["intake"]["max_requests_per_actor_per_day"]:
            return "rate_limited", None
        return "await_acceptance", "an authorized RISE contributor must accept this request"
    return "accept", None


# --------------------------------------------------------------------------
# Commands


@dataclass(frozen=True)
class CommandDecision:
    accepted: bool
    reason: str | None
    command: commands.Command | None
    receipt: dict


def accept_command(*, comment: dict, issue_number: int, event_body: str | None,
                   policy: dict, consumed: dict[int, dict], now: str) -> CommandDecision:
    """Authenticate and record a command comment exactly once.

    ``comment`` is the comment as freshly fetched from the API. ``event_body``
    is the body carried by the triggering event, when there was one: if the two
    differ the event is rejected and a fresh command is required. A consumed
    comment is never reinterpreted, even after an edit.
    """
    cid = comment["id"]
    body = comment.get("body") or ""
    digest = sha256_text(body)
    actor = {"id": comment["user"]["id"], "login": comment["user"]["login"]}

    def receipt(result: str, reason: str | None, cmd: commands.Command | None) -> dict:
        return {
            "schema_version": 1,
            "command_id": f"comment-{cid}",
            "comment_id": cid,
            "issue_number": issue_number,
            "content_digest": digest,
            "command_version": commands.COMMAND_VERSION,
            "verb": cmd.verb if cmd else "",
            "args": dict(cmd.args) if cmd else {},
            "actor": actor,
            "contribution_id": cmd.contribution if cmd else None,
            "revision": cmd.revision if cmd else None,
            "result": result,
            "reason": reason,
            "received_at": now,
        }

    if cid in consumed:
        prior = consumed[cid]
        why = ("already consumed" if prior["content_digest"] == digest
               else "edited after consumption; the recorded decision stands, post a new command")
        return CommandDecision(False, why, None, prior)
    if event_body is not None and event_body != body:
        return CommandDecision(False, "fetched content differs from the event; post a fresh command",
                               None, receipt("rejected", "content changed before acceptance", None))
    if actor["id"] not in policy["command_authority"]["actor_ids"]:
        r = receipt("rejected", "unauthorized actor", None)
        return CommandDecision(False, "unauthorized actor", None, r)
    try:
        cmd = commands.parse(body)
    except commands.CommandError as e:
        return CommandDecision(False, str(e), None, receipt("rejected", str(e), None))
    return CommandDecision(True, None, cmd, receipt("accepted", None, cmd))


def contribution_for_issue(contributions, issue_number: int):
    """The contribution a tracking issue's commands apply to: the newest
    non-terminal one tracked by that issue, else the newest one."""
    from .lifecycle import TERMINAL
    tracked = [c for c in contributions if c["tracking_issue"]["number"] == issue_number]
    live = [c for c in tracked if c["phase"] not in TERMINAL]
    return max(live or tracked, key=lambda c: c["created_at"]) if tracked else None


# --------------------------------------------------------------------------
# Fairness


def starving(items: Iterable[dict], *, now: datetime, business_days: int = 2) -> list[dict]:
    """Accepted eligible work older than the selection/escalation target."""
    limit = _business_days_before(now, business_days)
    return [i for i in items if datetime.fromisoformat(i["eligible_since"]) <= limit]


def _business_days_before(now: datetime, days: int) -> datetime:
    t = now
    while days > 0:
        t -= timedelta(days=1)
        if t.weekday() < 5:
            days -= 1
    return t
