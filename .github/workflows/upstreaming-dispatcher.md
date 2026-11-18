---
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
name: Upstreaming dispatcher
description: Admit at most one controller-selected upstreaming task and request one worker
on:
  workflow_dispatch:
imports:
  - shared/work-queue-staged-plan.md
permissions:
  contents: read
  actions: read
  issues: read
engine:
  id: pi
model: anthropic/claude-haiku-5-5
network:
  allowed: []
tools:
  work-queue: true
  bash:
    - cat /tmp/gh-aw/agent/upstreaming-plan.json
safe-outputs:
  threat-detection: false
  dispatch-workflow:
    workflows: [upstreaming-worker, upstreaming-investigator]
    target-ref: ${{ github.event.repository.default_branch }}
    max: 1
steps:
  - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d  # v10.0.1
    with:
      enable-cache: false
  - name: Replay the controller-requested task from committed state (deterministic, no model)
    id: select
    env:
      GH_TOKEN: ${{ github.token }}
      CONTROL_REPO_ID: ${{ github.event.repository.id }}
    run: |
      set -euo pipefail
      uv run --no-project --with-requirements upstreaming/requirements.txt \
        python -m upstreaming plan --out /tmp/gh-aw/agent/upstreaming-plan.json \
          --control-repo-id "$CONTROL_REPO_ID"
  # No `if: hashFiles(...)` here: hashFiles only sees the workspace, so a
  # plan under /tmp always looked absent and the step was skipped. The
  # script checks for the file itself.
  - name: Stage the plan as trusted queue intents
    uses: actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3  # v9.0.0
    with:
      script: |
        const fs = require("node:fs");
        const path = require("node:path");
        const file = "/tmp/gh-aw/agent/upstreaming-plan.json";
        if (!fs.existsSync(file)) { core.info("No actionable upstreaming work"); return; }
        const plan = JSON.parse(fs.readFileSync(file, "utf8"));
        const { stagePlanIntents } = require(path.join(process.env.RUNNER_TEMP, "gh-aw/actions/work_queue_intents.cjs"));
        stagePlanIntents(path.join(process.env.RUNNER_TEMP, "gh-aw/safeoutputs/work-queue/work-queue.intents.jsonl"), plan);
        core.info(`Staged ${plan.nodes.length} upstreaming task(s)`);
timeout-minutes: 10
strict: true
---

# Upstreaming dispatcher

Read `/tmp/gh-aw/agent/upstreaming-plan.json`, then call `work_queue_read`
with `{"pool":"upstreaming","limit":8}`. An absent queue is empty; the
trusted submission installs Policy and Work together. An existing
policyless ledger or a tool error is a failure, not an empty backlog.

The trusted preparation step read the task the upstreaming controller
requested in the committed `upstreaming-state/` and staged at most one task
(for the `upstreaming-investigator` or `upstreaming-worker` profile) followed by
`{"pool":"upstreaming","max_claims":1,"max_dispatches":1}`. Explain the
staged plan in one short paragraph: the contribution, the task kind and the
reason it was selected. Do not submit again, choose a winner, dispatch
directly, or emit `noop`. A staged request is not a launch.
