# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Answer addressed development-PR feedback and resolve inline threads.

This runs only in the trusted post-publication job with a one-fork App token.
The worker supplies bounded response text but never receives the token.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ResponseError(RuntimeError):
    pass


class Api:
    def __init__(self, token: str, base: str = "https://api.github.com"):
        self.token, self.base = token, base.rstrip("/")

    def call(self, method: str, path: str, data: dict | None = None) -> Any:
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, data=body, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
        last: Exception | None = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    raw = response.read()
                return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code not in (429, 500, 502, 503, 504):
                    raise ResponseError(
                        f"GitHub {method} {path}: HTTP {exc.code}: {exc.read()[-500:].decode(errors='replace')}") from exc
            except urllib.error.URLError as exc:
                last = exc
            if attempt < 4:
                time.sleep(2 ** attempt)
        raise ResponseError(f"GitHub {method} {path} failed after retries: {last}")

    def graphql(self, query: str, variables: dict) -> dict:
        result = self.call("POST", "/graphql", {"query": query, "variables": variables})
        if result.get("errors"):
            raise ResponseError(f"GraphQL failed: {result['errors']}")
        return result["data"]


@dataclass(frozen=True)
class Feedback:
    id: int
    kind: str
    reviewer: str | None


def feedback_items(task: dict) -> dict[int, Feedback]:
    found: dict[int, Feedback] = {}
    for evidence in (task.get("context") or {}).get("reason_evidence") or []:
        if evidence.get("kind") != "human_relay":
            continue
        data = evidence.get("data") or {}
        for key, kind in (("reviews", "review"), ("comments", "inline"),
                          ("conversation_comments", "conversation")):
            for item in data.get(key) or []:
                if item.get("id"):
                    found[int(item["id"])] = Feedback(int(item["id"]), kind, item.get("reviewer"))
    return found


def marker(comment_id: int, head: str) -> str:
    return f"<!-- upstreaming-feedback-response:{comment_id}:{head} -->"


def response_body(item: Feedback, summary: str, head: str) -> str:
    mention = f"@{item.reviewer} " if item.reviewer else ""
    return f"{mention}{summary.strip()}\n\n{marker(item.id, head)}"


def review_threads(api: Api, owner: str, name: str, number: int) -> list[dict]:
    query = """
      query($owner:String!,$name:String!,$number:Int!) {
        repository(owner:$owner,name:$name) {
          pullRequest(number:$number) {
            reviewThreads(first:100) {
              nodes { id isResolved comments(first:100) { nodes { databaseId body } } }
            }
          }
        }
      }
    """
    data = api.graphql(query, {"owner": owner, "name": name, "number": number})
    return data["repository"]["pullRequest"]["reviewThreads"]["nodes"]


def apply(api: Api, *, record: dict, task: dict, proposal: dict, outcome: dict) -> list[dict]:
    if outcome.get("status") != "published" or not outcome.get("candidate"):
        return []
    fork = record.get("fork") or {}
    repository = fork.get("name")
    number = fork.get("pr_number")
    if not repository or not number:
        raise ResponseError("development PR identity is missing")
    feedback = feedback_items(task)
    responses = {int(item["comment_id"]): item["summary"] for item in proposal.get("feedback_responses") or []}
    missing = set(feedback) - set(responses)
    if missing:
        raise ResponseError(f"missing feedback responses: {sorted(missing)}")
    owner, name = repository.split("/", 1)
    head = outcome["candidate"]
    inline_comments = api.call("GET", f"/repos/{repository}/pulls/{number}/comments?per_page=100")
    conversation = api.call("GET", f"/repos/{repository}/issues/{number}/comments?per_page=100")
    existing_bodies = [item.get("body") or "" for item in inline_comments + conversation]
    threads = review_threads(api, owner, name, int(number)) if any(x.kind == "inline" for x in feedback.values()) else []
    actions: list[dict] = []
    for comment_id in sorted(feedback):
        item = feedback[comment_id]
        tag = marker(comment_id, head)
        body = response_body(item, responses[comment_id], head)
        if not any(tag in existing for existing in existing_bodies):
            if item.kind == "inline":
                api.call("POST", f"/repos/{repository}/pulls/{number}/comments/{comment_id}/replies", {"body": body})
            else:
                api.call("POST", f"/repos/{repository}/issues/{number}/comments", {"body": body})
            existing_bodies.append(body)
            actions.append({"comment_id": comment_id, "action": "replied"})
        if item.kind == "inline":
            thread = next((thread for thread in threads if any(
                comment.get("databaseId") == comment_id for comment in thread["comments"]["nodes"])), None)
            if thread is None:
                raise ResponseError(f"review thread for comment {comment_id} was not found")
            if not thread["isResolved"]:
                mutation = "mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{id isResolved}}}"
                api.graphql(mutation, {"id": thread["id"]})
                actions.append({"comment_id": comment_id, "action": "resolved"})
    return actions


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    for name in ("record", "task", "proposal", "outcome"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    values = {name: json.loads(getattr(args, name).read_text()) for name in ("record", "task", "proposal", "outcome")}
    token = os.environ.get("UPSTREAMING_FORK_TOKEN")
    if not token:
        raise ResponseError("UPSTREAMING_FORK_TOKEN is missing")
    actions = apply(Api(token), **values)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"actions": actions}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
