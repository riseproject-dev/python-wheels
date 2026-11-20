#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Generate the public upstreaming status page from durable contribution state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

PHASE_LABELS = {
    "intake": "Requested",
    "investigation": "Investigating",
    "parked": "Parked",
    "abandoned": "Closed",
    "provisioning": "Preparing fork",
    "development": "Development",
    "handoff": "Ready for upstream",
    "upstream_review": "Upstream review",
    "completed": "Completed",
}
ACTIVITY_LABELS = {
    "idle": "",
    "agent_running": "agent running",
    "waiting_ci": "waiting for CI",
    "waiting_human": "waiting for human",
}


def status_label(state: dict) -> str:
    phase = PHASE_LABELS.get(state["phase"], state["phase"].replace("_", " ").title())
    activity = ACTIVITY_LABELS.get(
        state["activity"], state["activity"].replace("_", " ")
    )
    return f"{phase} ({activity})" if activity else phase


def markdown_link(label: str, url: str | None) -> str:
    return f"[{label}]({url})" if url else "-"


def render(states: list[dict]) -> str:
    states = sorted(states, key=lambda state: state["upstream"]["full_name"].casefold())
    lines = [
        "---",
        "title: Upstreaming",
        "layout: default",
        "nav_order: 9",
        "permalink: /upstreaming/",
        "---",
        "",
        "# Upstreaming status",
        "",
        "This table tracks work to contribute RISC-V support back to upstream projects. "
        "It is generated from the pipeline's durable state whenever the website is built.",
        "",
        "| Project | Tracking issue | Status | Development PR | Upstream PR | Updated (UTC) |",
        "|:--------|:---------------|:-------|:---------------|:------------|:--------------|",
    ]
    for state in states:
        full_name = state["upstream"]["full_name"]
        issue = state["tracking_issue"]["number"]
        fork = state.get("fork") or {}
        internal_url = None
        if fork.get("name") and fork.get("pr_number"):
            internal_url = f"https://github.com/{fork['name']}/pull/{fork['pr_number']}"
        upstream_pr = state.get("upstream_pr") or {}
        updated = datetime.fromisoformat(state["updated_at"]).strftime("%Y-%m-%d %H:%M")
        cells = [
            markdown_link(full_name, f"https://github.com/{full_name}"),
            markdown_link(f"#{issue}", f"https://github.com/riseproject-dev/python-wheels/issues/{issue}"),
            status_label(state),
            markdown_link(f"#{fork['pr_number']}", internal_url) if internal_url else "-",
            markdown_link(f"#{upstream_pr['number']}", upstream_pr.get("url")) if upstream_pr else "-",
            updated,
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "Status changes are recorded by the automated upstreaming pipeline. "
            "Use the tracking issue for the detailed history and available actions.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, default=Path("upstreaming-state/contributions"))
    parser.add_argument("--output", type=Path, default=Path("docs/upstreaming.md"))
    args = parser.parse_args()
    states = [json.loads(path.read_text()) for path in args.state_dir.glob("*.json")]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(states))


if __name__ == "__main__":
    main()
