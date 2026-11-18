# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Resolve an exact Claim's verified Result and proposal artifact (plan 15.3).

The publish job must not trust a generic successful job, Completion, or an
artifact chosen by name. It runs the pinned gh-aw v1.2.2 CLI:

    gh aw work-queue --repo OWNER/REPO replay --json

which validates the whole ledger and prints the replayed ``Projection``
(``pkg/workqueue/types.go``). From it we require, for the assignment's
exact Work and Claim:

* ``works[work_id].claim_id == claim_id`` and ``barrier == "verified"``;
  gh-aw sets ``barrier``/``result``/``result_commit_id`` together only when
  the Result's evidence is ``delivery``/``verified_receipts`` for the
  dispatch's bound run, attempt 1 (``settleVerifiedDelivery``);
* ``claims[claim_id].state == "completed"`` and the claim belongs to that
  work;
* ``dispatches[dispatch_id].run`` is this workflow run, attempt 1, this
  workflow file;
* ``result`` (the canonical descriptor) holds exactly one
  ``upload_artifact`` output whose resource is an artifact of this run.

That output's artifact ID, name and digest are the only artifact the
publisher may download, and its bytes must match the digest.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass

# Native safe-output tool accepts path, not a name override. Uploading the
# upstreaming-out directory yields claim-<hash>-upstreaming-out.
PROPOSAL_ARTIFACT_SUFFIX = "upstreaming-out"
GH_AW_VERSION = "v1.2.2"


class ResultError(ValueError):
    """No usable verified Result: the publisher must not push."""


@dataclass(frozen=True)
class ProposalArtifact:
    work_id: str
    claim_id: str
    artifact_id: int
    name: str
    digest: str            # "sha256:<hex>" as reported by the artifact API
    run_id: str
    run_attempt: int
    result_commit: str | None


def resolve(projection: dict, *, work_id: str, claim_id: str, dispatch_id: str, run_id: str,
            workflow: str) -> ProposalArtifact:
    """Check the replayed projection and return the Result's artifact."""
    work = (projection.get("works") or {}).get(work_id)
    if not work:
        raise ResultError("Work not found in the replayed queue")
    if work.get("claim_id") != claim_id:
        raise ResultError("Work is owned by another Claim")
    if work.get("barrier") != "verified" or not work.get("result_commit_id"):
        raise ResultError(f"no verified Result (barrier={work.get('barrier')!r})")
    claim = (projection.get("claims") or {}).get(claim_id) or {}
    if claim.get("work_id") != work_id or claim.get("dispatch_id") != dispatch_id:
        raise ResultError("Claim does not belong to this Work/dispatch")
    if claim.get("state") != "completed":
        raise ResultError(f"Claim is {claim.get('state')!r}, not completed")
    dispatch = (projection.get("dispatches") or {}).get(dispatch_id) or {}
    run = dispatch.get("run") or {}
    if str(run.get("run_id")) != str(run_id) or run.get("run_attempt") != 1:
        raise ResultError("dispatch is bound to another run or attempt")
    if run.get("workflow") != workflow:
        raise ResultError("dispatch is bound to another workflow")
    descriptor = work.get("result")
    if isinstance(descriptor, str):
        descriptor = json.loads(descriptor)
    outputs = (descriptor or {}).get("outputs") or []
    arts = [o for o in outputs if o.get("type") == "upload_artifact"]
    if len(arts) != 1:
        raise ResultError(f"expected exactly one verified artifact output, found {len(arts)}")
    res = arts[0].get("resource") or {}
    if res.get("kind") != "artifact" or str(res.get("target_run_id")) != str(run_id):
        raise ResultError("artifact resource is not from this run")
    name = res.get("name") or ""
    if not name.endswith(PROPOSAL_ARTIFACT_SUFFIX):
        raise ResultError(f"unexpected artifact name {name!r}")
    digest = res.get("digest") or ""
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise ResultError("artifact digest missing")
    try:
        aid = int(res["id"])
    except (KeyError, ValueError):
        raise ResultError("artifact ID missing") from None
    return ProposalArtifact(work_id=work_id, claim_id=claim_id, artifact_id=aid, name=name, digest=digest,
                            run_id=str(run_id), run_attempt=1, result_commit=work.get("result_commit_id"))


def check_artifact_metadata(meta: dict, art: ProposalArtifact) -> None:
    """``meta`` is GET /repos/{repo}/actions/artifacts/{id}."""
    if meta.get("id") != art.artifact_id or meta.get("name") != art.name:
        raise ResultError("artifact identity changed")
    if meta.get("expired"):
        raise ResultError("artifact expired")
    if str((meta.get("workflow_run") or {}).get("id")) != art.run_id:
        raise ResultError("artifact belongs to another run")
    if meta.get("digest") != art.digest:
        raise ResultError("artifact digest changed")


def check_bytes(data: bytes, art: ProposalArtifact) -> None:
    if "sha256:" + hashlib.sha256(data).hexdigest() != art.digest:
        raise ResultError("downloaded artifact does not match the verified digest")


def replay(gh_aw: str, repo: str, timeout: int = 600) -> dict:
    """Run the pinned gh-aw CLI's validating replay of the live ledger."""
    v = subprocess.run([gh_aw, "version"], capture_output=True, text=True, timeout=60)
    if GH_AW_VERSION not in v.stdout:
        raise ResultError(f"expected gh-aw {GH_AW_VERSION}, got {v.stdout.strip()!r}")
    p = subprocess.run([gh_aw, "work-queue", "--repo", repo, "replay", "--json"],
                       capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        # Network/auth failures and ledger validation failures look alike here;
        # either way nothing may be published now, and retrying is safe.
        raise OSError(f"gh aw work-queue replay failed: {p.stderr.strip()[-300:]}")
    return replay_output(p)


def replay_output(result: subprocess.CompletedProcess) -> dict:
    """The v1.2.2 CLI emits replay JSON on stderr; accept stdout on versions
    that use it, but only a complete JSON object, never mixed diagnostics."""
    value = json.loads(result.stdout if result.stdout.strip() else result.stderr)
    if not isinstance(value, dict) or not isinstance(value.get("works"), dict):
        raise ValueError("replay output is not a queue projection")
    return value


def queue_work_states(gh_aw: str, repo: str, timeout: int = 600) -> dict[str, str]:
    """``graph_id -> state`` for every Work in the live queue, from the same
    validating replay. A queue that does not exist yet is empty. Any other
    failure raises OSError: the caller must treat the queue as unknown."""
    p = subprocess.run([gh_aw, "work-queue", "--repo", repo, "replay", "--json"],
                       capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        if "queue_missing" in p.stderr:
            return {}
        raise OSError(f"gh aw work-queue replay failed: {p.stderr.strip()[-300:]}")
    works = (replay_output(p).get("works") or {}).values()
    return {w["graph_id"]: w.get("state") or "unknown" for w in works if w.get("graph_id")}


def _write_status(out, status: str, failure_class: str, reason: str) -> None:
    from pathlib import Path
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / "outcome.json").write_text(json.dumps(
        {"status": status, "failure_class": failure_class, "reason": reason[:2000], "stage": "result"}, indent=2))


def main(argv=None) -> int:
    """python -m upstreaming.queue_result --gh-aw BIN --assignment A.json --run-id N
    --workflow PATH --repo OWNER/REPO --out DIR [--projection FILE]

    Resolves the Result, checks artifact metadata via the API, downloads the
    archive by ID and verifies its digest. Exit 1 (no publish) otherwise.
    ``--projection`` reads a saved ``replay --json`` output instead of
    running the CLI (used by the retry path, which must re-run the replay
    anyway when it has no saved projection)."""
    import argparse
    import sys
    from pathlib import Path
    from .collect import Api, CollectError
    ap = argparse.ArgumentParser()
    ap.add_argument("--gh-aw")
    ap.add_argument("--projection", type=Path)
    ap.add_argument("--assignment", required=True, type=Path)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    assignment = json.loads(a.assignment.read_text())
    claims = assignment.get("claims") or []
    if assignment.get("version") != 3 or len(claims) != 1:
        print("no publish: expected a version-3 singleton assignment", file=sys.stderr)
        return 1
    m = claims[0]
    try:
        if a.projection:
            projection = json.loads(a.projection.read_text())
        elif a.gh_aw:
            projection = replay(a.gh_aw, a.repo)
        else:
            raise ResultError("need --gh-aw or --projection")
        art = resolve(projection, work_id=m["work_id"], claim_id=m["claim_id"],
                      dispatch_id=assignment["dispatch_id"], run_id=a.run_id, workflow=a.workflow)
        api = Api()
        check_artifact_metadata(api.get(f"/repos/{a.repo}/actions/artifacts/{art.artifact_id}"), art)
        data = api.get_bytes(f"/repos/{a.repo}/actions/artifacts/{art.artifact_id}/zip")
        check_bytes(data, art)
    except ResultError as e:
        print(f"no publish: {e}", file=sys.stderr)
        _write_status(a.out, "rejected", "validation", str(e))
        return 1
    except (CollectError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        # Could not reach GitHub or the CLI failed: retry later, same artifact.
        print(f"no publish (infrastructure): {e}", file=sys.stderr)
        _write_status(a.out, "infra_error", "infrastructure", str(e))
        return 3
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "proposal.zip").write_bytes(data)
    (a.out / "result.json").write_text(json.dumps(art.__dict__, indent=2))
    (a.out / "task.json").write_text(json.dumps(m["work"], indent=2))
    print(json.dumps(art.__dict__))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
