# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Trusted workflow-only fork provisioning. Never executes upstream code.

Creation uses a creation-only destination App token. Branch/settings operations
use a separately minted single-fork token. Existing branches are never reset.
The controller records fork_provision intent before dispatching this workflow.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
import urllib.parse

import yaml

from . import collect, schemas
from .common import CONTROL_REPO, FORK_ORG, contribution_file_id


class ProvisionError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProvisionError("provisioning API redirect refused")


class WriteApi(collect.Api):
    def __init__(self, token: str):
        if not token:
            raise ProvisionError("explicit scoped provisioning token required")
        super().__init__(token=token, opener=urllib.request.build_opener(NoRedirect).open)

    def write(self, method: str, path: str, body: dict) -> dict:
        if method not in ("POST", "PUT") or not path.startswith("/repos/") or ".." in path:
            raise ProvisionError("unsupported provisioning API operation")
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method=method,
                                     headers={"Accept": "application/vnd.github+json", "Content-Type": "application/json",
                                              "X-GitHub-Api-Version": "2022-11-28", "Authorization": f"Bearer {self.token}"})
        try:
            with self._open(req, timeout=30) as response:
                data = response.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024:
                    raise ProvisionError("oversized provisioning response")
                return json.loads(data) if data else {}
        except urllib.error.HTTPError as e:
            raise ProvisionError(f"provisioning API {method} {path}: HTTP {e.code}") from None


def validate_request(record: dict, operation: dict, policy: dict) -> None:
    schemas.validate("contribution", record)
    schemas.validate("operation", operation)
    if policy.get("read_only", True):
        raise ProvisionError("policy is read-only")
    if record["phase"] != "provisioning" or record.get("paused") or record.get("blocked_reason"):
        raise ProvisionError("contribution is not authorized for provisioning")
    if not record.get("dossier_evidence_id") or not record.get("admission_class"):
        raise ProvisionError("reviewed dossier and approved scope required")
    if not record["owners"].get("primary") or not record["owners"].get("backup"):
        raise ProvisionError("primary and backup owners required")
    if not record["upstream"].get("repository_id") or not record["upstream"].get("base_sha"):
        raise ProvisionError("upstream identity and immutable base must be verified first")
    if operation["kind"] != "fork_provision" or operation["status"] != "planned" \
            or operation["contribution_id"] != record["contribution_id"] or operation["revision"] != record["revision"] \
            or record.get("active_operation_id") != operation["operation_id"]:
        raise ProvisionError("operation is not the current authorized provisioning intent")
    expected = f"{FORK_ORG}/{record['upstream']['full_name'].split('/', 1)[1]}"
    if operation["target"]["repository"] != expected or operation["target"].get("ref") != "riscv64" \
            or operation["target"].get("base_sha") != record["upstream"]["base_sha"]:
        raise ProvisionError("operation target does not match approved source/base")


def check_fork(fork: dict, plan: dict) -> None:
    if (fork.get("full_name") or "").lower() != plan["fork"].lower() or not fork.get("fork") \
            or (fork.get("parent") or {}).get("id") != plan["upstream_id"] or fork.get("archived"):
        raise ProvisionError("fork identity/network is not the approved upstream")
    if plan.get("fork_id") not in (None, fork["id"]):
        raise ProvisionError("fork repository ID changed")


def preflight(api, record: dict, operation: dict, policy: dict) -> dict:
    validate_request(record, operation, policy)
    up = record["upstream"]
    source = api.get(f"/repos/{up['full_name']}")
    if source["id"] != up["repository_id"] or source["full_name"].lower() != up["full_name"].lower():
        raise ProvisionError("upstream repository identity changed")
    commit = api.get(f"/repos/{up['full_name']}/git/commits/{up['base_sha']}")
    if commit["sha"] != up["base_sha"]:
        raise ProvisionError("upstream base commit identity changed")
    plan = {"operation_id": operation["operation_id"], "contribution_id": record["contribution_id"],
            "revision": record["revision"], "upstream": up["full_name"], "upstream_id": up["repository_id"],
            "fork": operation["target"]["repository"], "fork_name": operation["target"]["repository"].split('/', 1)[1],
            "fork_id": operation["target"].get("repository_id"), "base_sha": up["base_sha"],
            "expected_head": operation["target"].get("expected_head"), "create": False}
    try:
        fork = api.get(f"/repos/{plan['fork']}")
    except collect.CollectError as e:
        if "HTTP 404" not in str(e):
            raise
        plan["create"] = True
        return plan
    check_fork(fork, plan)
    plan["fork_id"] = fork["id"]
    return plan


def create_or_reuse(reader, creator, plan: dict) -> dict:
    try:
        existing = reader.get(f"/repos/{plan['fork']}")
    except collect.CollectError as e:
        if "HTTP 404" not in str(e):
            raise
    else:
        check_fork(existing, plan)
        return dict(plan, fork_id=existing["id"], created=False)
    if not plan["create"] or creator is None:
        raise ProvisionError("fork disappeared; not authorized to recreate it")
    result = creator.write("POST", f"/repos/{plan['upstream']}/forks",
                           {"organization": FORK_ORG, "name": plan["fork_name"], "default_branch_only": True})
    check_fork(result, plan)
    return dict(plan, fork_id=result["id"], created=True)


def disable_unsafe_workflows(api, fork: str) -> list[str]:
    """Disable inherited privileged/publication workflows before opening a PR.
    Parse data only; never run workflow contents in the credentialed job."""
    workflows = api.get(f"/repos/{fork}/actions/workflows?per_page=100")
    if workflows.get("total_count", 0) > 100:
        raise ProvisionError("workflow inventory exceeds bounded setup scan")
    disabled = []
    for wf in workflows.get("workflows", []):
        path = wf["path"]
        if not path.startswith(".github/workflows/") or ".." in path.split("/"):
            raise ProvisionError("unexpected inherited workflow path")
        data = api.get(f"/repos/{fork}/contents/{urllib.parse.quote(path, safe='/')}")
        if data.get("type") != "file" or data.get("encoding") != "base64":
            raise ProvisionError("workflow must be a regular data file")
        raw = base64.b64decode(data["content"])
        if len(raw) > 1024 * 1024:
            raise ProvisionError("oversized inherited workflow")
        text = raw.decode()
        workflow = yaml.safe_load(text)
        if not isinstance(workflow, dict):
            raise ProvisionError("invalid inherited workflow")
        levels = [workflow.get("permissions", {})] + [j.get("permissions", {}) for j in (workflow.get("jobs") or {}).values()]
        unsafe = bool(re.search(r"pull_request_target|id-token\\s*:\\s*write|twine\\s+upload|pypa/gh-action-pypi-publish", text))
        for permissions in levels:
            if not isinstance(permissions, dict):
                unsafe = True
            elif any(permissions.get(k) == "write" for k in ("contents", "issues", "pull-requests", "administration", "workflows")):
                unsafe = True
        if unsafe:
            api.write("PUT", f"/repos/{fork}/actions/workflows/{wf['id']}/disable", {})
            disabled.append(path)
    return disabled


def initialize(api, plan: dict) -> dict:
    fork = api.get(f"/repos/{plan['fork']}")
    check_fork(fork, plan)
    head = collect.branch_head(api, plan["fork"], "riscv64")
    if head and head["head"] not in (plan["base_sha"], plan.get("expected_head")):
        raise ProvisionError("unexpected existing riscv64 work; never reset it")
    if not head and plan.get("expected_head"):
        raise ProvisionError("recorded branch disappeared; recreation is not authorized")
    # Fail closed on access denial; never substitute a local write or broader token.
    api.write("PUT", f"/repos/{plan['fork']}/actions/permissions/workflow",
              {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False})
    api.write("PUT", f"/repos/{plan['fork']}/actions/permissions", {"enabled": True, "allowed_actions": "all"})
    disabled = disable_unsafe_workflows(api, plan["fork"])
    if head is None:
        api.write("POST", f"/repos/{plan['fork']}/git/refs", {"ref": "refs/heads/riscv64", "sha": plan["base_sha"]})
    observed = collect.branch_head(api, plan["fork"], "riscv64")
    permissions = api.get(f"/repos/{plan['fork']}/actions/permissions/workflow")
    if not observed or observed["head"] != (head["head"] if head else plan["base_sha"]) \
            or permissions.get("default_workflow_permissions") != "read" \
            or permissions.get("can_approve_pull_request_reviews"):
        raise ProvisionError("fork provisioning readback failed")
    return dict(plan, status="provisioned", head_sha=observed["head"], actions_read_only=True, disabled_workflows=disabled)


def current_request(api, operation_id: str) -> tuple[dict, dict, dict]:
    if not re.fullmatch(r"op-[0-9a-f]{24}", operation_id):
        raise ProvisionError("invalid operation ID")
    def read(path):
        data = api.get(f"/repos/{CONTROL_REPO}/contents/{path}?ref=main")
        if data.get("encoding") != "base64" or data.get("type") != "file":
            raise ProvisionError("trusted state input is not a regular file")
        raw = base64.b64decode(data["content"])
        if len(raw) > 256 * 1024:
            raise ProvisionError("oversized state input")
        return json.loads(raw)
    op = read(f"upstreaming-state/operations/{operation_id}.json")
    cid = contribution_file_id(op["contribution_id"])
    record = read(f"upstreaming-state/contributions/{cid}.json")
    policy = read("upstreaming/policy.json")
    validate_request(record, op, policy)
    return record, op, policy


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "create", "initialize"))
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REPOSITORY") != CONTROL_REPO \
            or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ProvisionError("fork mutations are allowed only in trusted control-repository workflows on main")
    reader = collect.Api()
    record, operation, policy = current_request(reader, args.operation_id)
    plan = preflight(reader, record, operation, policy)
    if args.mode == "create":
        creator = WriteApi(token=os.environ.get("UPSTREAMING_CREATION_TOKEN")) if plan["create"] else None
        plan = create_or_reuse(reader, creator, plan)
    elif args.mode == "initialize":
        previous = json.loads(args.plan.read_text())
        if any(previous[k] != plan[k] for k in ("operation_id", "contribution_id", "revision", "upstream_id", "base_sha", "fork")):
            raise ProvisionError("provisioning preconditions changed")
        plan["fork_id"] = previous["fork_id"]
        plan["created"] = previous["created"]
        plan = initialize(WriteApi(token=os.environ["UPSTREAMING_FORK_TOKEN"]), plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, indent=2))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as f:
            f.write(f"create={str(plan['create']).lower()}\nfork_name={plan['fork_name']}\n")
