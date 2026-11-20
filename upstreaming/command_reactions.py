# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Idempotently mark durably accepted commands complete with ``+1``."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

from .status_ledger import Api, LedgerError


def _retry(call, attempts: int = 4):
    delay = 1
    for attempt in range(attempts):
        try:
            return call()
        except (LedgerError, OSError):
            if attempt + 1 == attempts:
                raise
            time.sleep(delay)
            delay *= 2


def publish(root: Path, token: str) -> list[dict]:
    api = Api(token)
    results = []
    paths = sorted((root / "upstreaming-state/commands").glob("*.json"))[-512:]
    for path in paths:
        receipt = json.loads(path.read_text())
        if receipt.get("result") != "accepted":
            continue
        comment_id = int(receipt["comment_id"])
        endpoint = f"/repos/riseproject-dev/python-wheels/issues/comments/{comment_id}/reactions"
        reactions = _retry(lambda: api.request("GET", endpoint + "?per_page=100"))
        if any(item.get("content") == "+1" and (item.get("user") or {}).get("login") == "riseproject-dev[bot]"
               for item in reactions):
            results.append({"command_id": receipt["command_id"], "comment_id": comment_id, "status": "existing"})
            continue
        created = _retry(lambda: api.request("POST", endpoint, {"content": "+1"}))
        if created.get("content") != "+1" or (created.get("user") or {}).get("login") != "riseproject-dev[bot]":
            raise LedgerError("command completion reaction readback or App author mismatch")
        results.append({"command_id": receipt["command_id"], "comment_id": comment_id, "status": "created"})
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = publish(args.root, os.environ.get("GH_TOKEN", ""))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
