# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Trusted fork publisher (plan sections 10.2, 10.4, 15.3, 16.3).

Input: the agent's proposal (JSON, untrusted) and patch series (an mbox
produced by ``git format-patch``, untrusted), plus the trusted contribution
record and the task payload that was admitted to the queue.

Steps, all in a fresh bare repository this module creates:

1. Fetch the fork's ``riscv64`` and the approved upstream base by exact SHA
   over HTTPS. Never reuse the agent's checkout, remotes or Git config.
2. Re-check the publication preconditions (phase, pause, revision, fork,
   ref and *current* fork head against the expected head).
3. Rebuild the series with ``git am`` on top of the expected head (append)
   or the upstream base (rewrite), with hooks, filters and user config off.
   No project code runs: ``git am`` only writes objects.
4. Validate the candidate with ``publisher.validate_update`` against the
   trusted base, and check the proposal's claims (changed files, patch
   digest) against what was actually rebuilt.
5. Persist an operation intent, push with
   ``--force-with-lease=refs/heads/riscv64:<expected>``, then discover the
   branch to confirm the effect. A lost response stays ``uncertain``.

The token is passed in by the caller (minted for exactly one fork with
contents/workflows/pull-requests write) and is only placed in a transient
HTTP header for the push. It is never written to disk.
"""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import lifecycle, publisher, recovery, schemas
from .common import DEV_REF, FORK_ORG, validate_scope_paths

MAX_MBOX_BYTES = 4 * 1024 * 1024
_SHA = re.compile(r"^[0-9a-f]{40}$")
APP_COMMIT_NAME = "riseproject-upstreaming[bot]"
APP_COMMIT_EMAIL = "359135081+riseproject-upstreaming[bot]@users.noreply.github.com"


class PublishRejected(RuntimeError):
    """The proposal must not be published. Not retried."""


class PublishInfraError(RuntimeError):
    """Transient infrastructure failure (network, token, API, git transport).
    The same artifact may be published again later without a new agent run."""


# Failure classes recorded on every outcome:
#   validation     - the proposal itself is unacceptable; needs a new agent task
#   stale          - the world moved (head/revision/pause); reconcile, no retry
#   infrastructure - retry the publish only, same artifact, no model call
FAILURE_CLASSES = ("validation", "stale", "infrastructure")


@dataclass
class Outcome:
    status: str                      # published | rejected | no_change | uncertain | infra_error
    reason: str | None = None
    failure_class: str | None = None
    candidate: str | None = None
    tree: str | None = None
    operation: dict | None = None
    report: dict = field(default_factory=dict)


def _git(repo: Path, *args: str, check: bool = True, input: bytes | None = None,
         extra_config: list[str] | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    e = publisher.safe_env()
    e.update({"GIT_AUTHOR_NAME": APP_COMMIT_NAME, "GIT_AUTHOR_EMAIL": APP_COMMIT_EMAIL,
              "GIT_COMMITTER_NAME": APP_COMMIT_NAME, "GIT_COMMITTER_EMAIL": APP_COMMIT_EMAIL})
    e.update(env or {})
    return subprocess.run(["git", *publisher.SAFE_GIT_CONFIG, *TEST_EXTRA_CONFIG, *(extra_config or []),
                           "-C", str(repo), *args],
                          check=check, capture_output=True, input=input, env=e)


def _auth_config(token: str | None) -> list[str]:
    if not token:
        return []
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}"]


# Tests replace these two to use local file:// remotes; production is HTTPS only.
URL_TEMPLATE = "https://github.com/{}.git"
TEST_EXTRA_CONFIG: list[str] = []


def _url(full_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", full_name):
        raise PublishRejected(f"invalid repository name {full_name!r}")
    return URL_TEMPLATE.format(full_name)


def _rewrite_app_identity(repo: Path, start: str, head: str) -> str:
    """Recreate the linear proposal series with the App as author/committer."""
    commits = [sha for sha in _git(repo, "rev-list", "--reverse", f"{start}..{head}").stdout.decode().splitlines() if sha]
    parent = start
    for old in commits:
        tree = _git(repo, "rev-parse", f"{old}^{{tree}}").stdout.decode().strip()
        message = _git(repo, "show", "-s", "--format=%B", old).stdout
        dates = {"GIT_AUTHOR_DATE": _git(repo, "show", "-s", "--format=%aI", old).stdout.decode().strip(),
                 "GIT_COMMITTER_DATE": _git(repo, "show", "-s", "--format=%cI", old).stdout.decode().strip()}
        parent = _git(repo, "commit-tree", tree, "-p", parent, input=message, env=dates).stdout.decode().strip()
    return parent


def check_proposal(proposal: dict, record: dict, task: dict, *, allow_no_change: bool = False) -> None:
    """Static checks before any network access."""
    schemas.validate("proposal", proposal)
    if proposal["contribution_id"] != record["contribution_id"] or task["contribution_id"] != record["contribution_id"]:
        raise PublishRejected("proposal/task/record contribution mismatch")
    if proposal["expected_revision"] != task["revision"] or proposal["expected_head"] != task["expected_head"]:
        raise PublishRejected("proposal does not answer the admitted task (revision/head)")
    if task.get("task") in ("development_repair", "upstream_revision"):
        missing_reasons = set(task.get("reason_ids") or []) - set(proposal.get("reason_ids") or [])
        if missing_reasons:
            raise PublishRejected(f"repair proposal did not acknowledge required evidence: {sorted(missing_reasons)}")
    fork = (record.get("fork") or {}).get("name") or ""
    if not fork.startswith(FORK_ORG + "/") or task["fork"] != fork:
        raise PublishRejected("task fork is not the recorded contribution fork")
    if proposal["outcome"] == "no_change" and allow_no_change:
        return
    if proposal["outcome"] != "patch" or proposal["operation"] == "none":
        raise PublishRejected(f"nothing to publish (outcome {proposal['outcome']})")
    if proposal["operation"] not in task["allowed_operations"]:
        raise PublishRejected(f"operation {proposal['operation']} not allowed for this task")
    if task.get("fork_repository_id") != record["fork"].get("repository_id") or not record["fork"].get("repository_id"):
        raise PublishRejected("task fork repository ID is not the approved one")
    if proposal.get("fork_repository_id") not in (None, record["fork"]["repository_id"]):
        raise PublishRejected("proposal names another fork")
    expected_base = task["expected_head"] if proposal["operation"] == "append" else record["upstream"]["base_sha"]
    if proposal.get("reconstruction_base") != expected_base:
        raise PublishRejected("proposal reconstruction base is not the trusted one for this operation")


def rebuild(work: Path, *, fork: str, upstream: str, expected_head: str, base_sha: str, mbox: bytes,
            operation: str, read_token: str | None = None) -> str:
    """Fetch exact commits into a fresh repo and apply the series. Returns the candidate SHA."""
    if not (_SHA.match(expected_head) and _SHA.match(base_sha)):
        raise PublishRejected("expected head and base must be full SHAs")
    if len(mbox) > MAX_MBOX_BYTES:
        raise PublishRejected("patch series too large")
    if not mbox.strip() and operation != "rewrite":
        raise PublishRejected("an empty series is only valid for a rewrite (removal of all commits)")
    if b"\nGIT binary patch\n" in mbox:
        raise PublishRejected("binary patches are not accepted")
    publisher.fresh_workspace(work)
    auth = _auth_config(read_token)
    for url, sha in ((_url(fork), expected_head), (_url(upstream), base_sha)):
        p = _git(work, "fetch", "--quiet", "--no-tags", "--filter=blob:none", url, sha, check=False,
                 extra_config=auth)
        if p.returncode:
            err = p.stderr.decode()[-300:]
            # A SHA the remote does not have is a stale/invalid proposal; anything
            # else (auth, network, 5xx) is infrastructure.
            if "not our ref" in err or "unadvertised object" in err or "couldn't find remote ref" in err:
                raise PublishRejected(f"commit {sha[:12]} not on the remote: {err}")
            raise PublishInfraError(f"could not fetch {sha[:12]}: {err}")
    start = expected_head if operation == "append" else base_sha
    # git am needs a work tree; use a private one inside the workspace.
    wt = work / "wt"
    _git(work, "worktree", "add", "--quiet", "--detach", str(wt), start)
    if not mbox.strip():
        return _git(wt, "rev-parse", "HEAD").stdout.decode().strip()
    p = _git(wt, "am", "--quiet", "--keep-cr", "--no-3way", "--committer-date-is-author-date",
             input=mbox, check=False,
             extra_config=["-c", "am.threeWay=false", "-c", "apply.whitespace=nowarn"])
    if p.returncode:
        _git(wt, "am", "--abort", check=False)
        raise PublishRejected(f"series does not apply on {start[:12]}: {p.stderr.decode()[-400:]}")
    applied = _git(wt, "rev-parse", "HEAD").stdout.decode().strip()
    return _rewrite_app_identity(wt, start, applied)


def publish(*, record: dict, task: dict, proposal: dict, mbox: bytes, token: str | None,
            observe_head: Callable[[], str | None], scope: publisher.Scope, policy: dict, now: str,
            save_operation: Callable[[dict], None], workdir: Path | None = None,
            artifact: dict | None = None, previous_candidate: str | None = None,
            push: Callable[[Path, list[str], list[str]], subprocess.CompletedProcess] | None = None) -> Outcome:
    """Validate and publish one proposal. ``observe_head()`` reads the fork's
    current ``riscv64`` head via the API (fresh, right before the push)."""
    try:
        check_proposal(proposal, record, task)
    except (PublishRejected, schemas.SchemaError) as e:
        return Outcome("rejected", str(e), failure_class="validation")
    fork = task["fork"]
    expected = task["expected_head"]
    try:
        observed_before = observe_head()
    except Exception as e:  # API failure reading the branch
        return Outcome("infra_error", f"could not read the fork head: {e}", failure_class="infrastructure")
    why = lifecycle.publication_check(record, expected_revision=task["revision"], expected_head=expected,
                                      observed_head=observed_before, ref=DEV_REF, repository=fork)
    if why and observed_before != expected and previous_candidate and observed_before == previous_candidate:
        # A previous attempt of this same publication already landed (its
        # receipt was lost). Confirm it; never push again.
        return Outcome("published", "already published by a previous attempt", candidate=previous_candidate)
    if why:
        return Outcome("rejected", f"publication check: {why}", failure_class="stale")
    tmp = tempfile.TemporaryDirectory(prefix="upstreaming-publish-") if workdir is None else None
    work = Path(tmp.name) / "repo" if tmp else workdir
    try:
        try:
            cand = rebuild(work, fork=fork, upstream=record["upstream"]["full_name"], expected_head=expected,
                           base_sha=record["upstream"]["base_sha"], mbox=mbox, operation=proposal["operation"],
                           read_token=token)
        except PublishInfraError as e:
            return Outcome("infra_error", str(e), failure_class="infrastructure")
        except PublishRejected as e:
            return Outcome("rejected", str(e), failure_class="validation")
        if cand == expected and proposal["operation"] == "append":
            return Outcome("no_change", "series produced no commits", candidate=cand)
        if proposal.get("proposed_tree"):
            tree = _git(work, "rev-parse", f"{cand}^{{tree}}").stdout.decode().strip()
            if tree != proposal["proposed_tree"]:
                return Outcome("rejected", "rebuilt tree differs from the proposal's proposed_tree", candidate=cand,
                               failure_class="validation")
        claimed = set(proposal.get("changed_files") or [])
        effective_globs = list(scope.allowed_globs)
        outside_scope = sorted(path for path in claimed if not any(
            fnmatch.fnmatchcase(path, allowed) for allowed in scope.allowed_globs))
        if outside_scope:
            if not task.get("review_scope_extension"):
                return Outcome("rejected", f"proposal changes files outside admitted scope: {outside_scope}",
                               candidate=cand, failure_class="validation")
            if any(any(ch in path for ch in "*?[]") for path in outside_scope):
                return Outcome("rejected", "review scope extensions must be exact paths",
                               candidate=cand, failure_class="validation")
            try:
                validate_scope_paths(outside_scope)
                validate_scope_paths(list(dict.fromkeys(effective_globs + outside_scope)))
            except ValueError as exc:
                return Outcome("rejected", f"invalid review scope extension: {exc}",
                               candidate=cand, failure_class="validation")
            effective_globs.extend(outside_scope)
        sc = publisher.Scope(allowed_globs=effective_globs, workflow_globs=scope.workflow_globs,
                             upstream_facing=record.get("upstream_pr") is not None,
                             history="append" if proposal["operation"] == "append" else "rewrite")
        rep = publisher.validate_update(work, base=record["upstream"]["base_sha"], expected_head=expected,
                                        candidate=cand, scope=sc)
        delta = _git(work, "diff", "--name-only", "--no-renames", expected, cand).stdout.decode().split()
        if claimed and set(delta) != claimed:
            rep.problems.append(f"proposal claims files {sorted(claimed)} but series changes {sorted(delta)}")
        digest = hashlib.sha256(mbox).hexdigest()
        if proposal.get("patch_digest") and proposal["patch_digest"] != digest:
            rep.problems.append("patch digest does not match the delivered series")
        report = {"changed": rep.changed, "delta": delta, "commits": rep.commits,
                  "touches_workflows": rep.touches_workflows, "problems": rep.problems}
        if not rep.ok:
            return Outcome("rejected", "; ".join(rep.problems[:5]), candidate=cand, tree=rep.final_tree, report=report,
                           failure_class="validation")
        parents = _git(work, "rev-list", "--parents", "-n1", cand).stdout.decode().split()[1:]
        op = recovery.plan(contribution_id=record["contribution_id"], revision=task["revision"],
                           kind="branch_update" if proposal["operation"] == "append" else "branch_rewrite",
                           policy_version=policy["policy_version"], reason_ids=list(task.get("reason_ids") or []) +
                           ([f"artifact:{artifact['artifact_id']}"] if artifact else []),
                           target={"repository_id": record["fork"]["repository_id"], "repository": fork,
                                   "ref": DEV_REF, "expected_head": expected,
                                   "base_sha": record["upstream"]["base_sha"]},
                           proposed={"commit": cand, "tree": rep.final_tree, "parents": parents,
                                     "marker": f"artifact:{artifact['artifact_id']}" if artifact else None,
                                     "content_digest": hashlib.sha256(mbox).hexdigest(),
                                     "changed_files": delta}, now=now)
        save_operation(op)                     # intent persisted before the effect
        if policy.get("read_only", True):
            return Outcome("rejected", "policy is read-only; validated but not pushed", candidate=cand,
                           tree=rep.final_tree, operation=op, report=report, failure_class="stale")
        # Last re-read immediately before the effect.
        try:
            head_now = observe_head()
        except Exception as e:
            op = recovery._set(op, "failed", now)
            save_operation(op)
            return Outcome("infra_error", f"could not re-read the fork head: {e}", candidate=cand, operation=op,
                           report=report, failure_class="infrastructure")
        if head_now != expected:
            op = recovery._set(op, "failed", now)
            save_operation(op)
            return Outcome("rejected", "fork head moved before push", candidate=cand, operation=op, report=report,
                           failure_class="stale")
        op = recovery.mark_applying(op, now)
        save_operation(op)
        args = publisher.lease_refspec(cand, expected)
        runner = push or (lambda w, a, cfg: _git(w, "push", "--porcelain", _url(fork), *a, check=False,
                                                 extra_config=cfg))
        try:
            p = runner(work, args, _auth_config(token))
            ok = p.returncode == 0
        except Exception:
            ok = None
        op = recovery.mark_result(op, response_ok=True if ok else (None if ok is None else False),
                                  external_ids={}, now=now)
        if ok is False:
            # Nothing was written. A lease mismatch means the branch moved
            # (stale); anything else (403, 5xx, network) is infrastructure.
            save_operation(op)
            err = p.stderr.decode()[-300:]
            out = p.stdout.decode() if isinstance(p.stdout, bytes) else (p.stdout or "")
            stale = "stale info" in err or "stale info" in out or "fetch first" in err or "non-fast-forward" in err
            return Outcome("rejected" if stale else "infra_error", f"push rejected: {err}", candidate=cand,
                           operation=op, report=report, failure_class="stale" if stale else "infrastructure")
        # Discover rather than trust the response.
        try:
            observed = observe_head()
        except Exception:
            observed = None
        result = recovery.discover_branch(op, {"head": observed} if observed else None)
        op = recovery.record_discovery(op, result, f"riscv64 at {observed}", now)
        save_operation(op)
        return Outcome("published" if op["status"] == "confirmed" else "uncertain",
                       None if op["status"] == "confirmed" else "push outcome not yet observable",
                       candidate=cand, tree=rep.final_tree, operation=op, report=report)
    finally:
        if tmp:
            tmp.cleanup()


def preflight(*, record: dict, task: dict, proposal: dict, fork_lookup: Callable[[str], dict]) -> dict:
    """Run before any token exists. Decides whether a push is even possible and
    returns the single fork name to mint a token for, taken from the trusted
    task and confirmed against the fork's current repository ID and org."""
    try:
        check_proposal(proposal, record, task, allow_no_change=True)
    except (PublishRejected, schemas.SchemaError) as e:
        return {"publish": False, "status": "rejected", "reason": str(e), "fork_name": "",
                "failure_class": "validation"}
    if proposal["outcome"] == "no_change":
        return {"publish": False, "status": "no_change", "reason": proposal.get("diagnosis"),
                "fork_name": "", "failure_class": None}
    try:
        repo = fork_lookup(task["fork"])
    except Exception as e:
        return {"publish": False, "status": "infra_error", "reason": f"could not read the fork: {e}",
                "fork_name": "", "failure_class": "infrastructure"}
    if repo.get("id") != record["fork"]["repository_id"] or not repo.get("full_name", "").startswith(FORK_ORG + "/"):
        return {"publish": False, "status": "rejected", "reason": "fork repository identity changed",
                "fork_name": "", "failure_class": "stale"}
    if repo.get("archived"):
        return {"publish": False, "status": "rejected", "reason": "fork is archived", "fork_name": "",
                "failure_class": "stale"}
    return {"publish": True, "status": "publish", "reason": None,
            "fork_name": repo["full_name"].split("/", 1)[1], "failure_class": None}


def main(argv=None) -> int:
    """CLI used by the trusted publish job.

    python -m upstreaming.fork_publish preflight --record R --task T --proposal P --out O
    python -m upstreaming.fork_publish publish --record R --task T --proposal P --mbox M \
        --result RES [--out O]

    The fork token comes from UPSTREAMING_FORK_TOKEN (publish only).
    """
    import argparse
    from datetime import datetime, timezone
    from .collect import Api, branch_head, repository
    from .common import load_policy
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["preflight", "publish"])
    for a in ("--record", "--task", "--proposal"):
        ap.add_argument(a, required=True, type=Path)
    ap.add_argument("--mbox", type=Path)
    ap.add_argument("--result", type=Path)
    ap.add_argument("--previous-candidate", help="commit a previous attempt of this publication would push")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    record = json.loads(a.record.read_text())
    task = json.loads(a.task.read_text())
    proposal = json.loads(a.proposal.read_text())
    if a.cmd == "preflight":
        res = preflight(record=record, task=task, proposal=proposal,
                        fork_lookup=lambda name: repository(Api(), name))
        text = json.dumps(res, indent=2)
        (a.out.write_text(text) if a.out else print(text))
        return 0
    policy = load_policy()
    token = os.environ.pop("UPSTREAMING_FORK_TOKEN", None)
    api = Api(token=token)
    artifact = json.loads(a.result.read_text()) if a.result else None
    ops: list[dict] = []
    mbox = a.mbox.read_bytes() if a.mbox and a.mbox.exists() else b""
    out = publish(record=record, task=task, proposal=proposal, mbox=mbox, token=token,
                  observe_head=lambda: (branch_head(api, task["fork"], DEV_REF) or {}).get("head"),
                  scope=publisher.Scope(allowed_globs=task["allowed_paths"]), policy=policy,
                  now=datetime.now(timezone.utc).isoformat(), save_operation=ops.append, artifact=artifact,
                  previous_candidate=a.previous_candidate)
    result = {"status": out.status, "reason": out.reason, "failure_class": out.failure_class,
              "candidate": out.candidate, "tree": out.tree,
              "operation": ops[-1] if ops else None, "report": out.report, "artifact": artifact,
              "attempt": int(os.environ.get("UPSTREAMING_PUBLISH_ATTEMPT", "1"))}
    text = json.dumps(result, indent=2)
    (a.out.write_text(text) if a.out else print(text))
    # 0 published/no_change, 1 rejected, 2 uncertain, 3 infrastructure (retry publish only)
    return {"published": 0, "no_change": 0, "uncertain": 2, "infra_error": 3}.get(out.status, 1)


if __name__ == "__main__":
    raise SystemExit(main())
