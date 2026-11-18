---
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
name: Upstreaming investigator
description: Investigate one upstream project for a riscv64 wheel contribution (read and report only)
on:
  workflow_dispatch:
permissions:
  contents: read
  issues: read
  pull-requests: read
  actions: read
engine:
  id: pi
model: anthropic/claude-sonnet-5-5
concurrency:
  job-discriminator: ${{ github.run_id }}
network:
  allowed:
    - defaults
    - python
    - github
tools:
  work-queue:
    require-assignment: true
    worker: true
  github:
    toolsets: [repos, pull_requests, actions]
  bash:
    - "*"
  edit:
safe-outputs:
  upload-artifact:
    max-uploads: 1
    retention-days: 30
    max-size-bytes: 4194304
    allowed-paths:
      - upstreaming-out/*
  noop:
    report-as-issue: false
pre-agent-steps:
  - name: Check out the upstream project (read-only)
    env:
      GH_AW_ACTIONS_DIR: ${{ runner.temp }}/gh-aw/actions
    run: |
      set -euo pipefail
      node <<'JS'
      const fs = require("node:fs");
      const path = require("node:path");
      const { normalizeAssignment } = require(path.join(process.env.GH_AW_ACTIONS_DIR, "work_queue_claim_scope.cjs"));
      const event = JSON.parse(fs.readFileSync(process.env.GITHUB_EVENT_PATH, "utf8"));
      const a = normalizeAssignment(JSON.parse(event.inputs.work_queue_assignment));
      if (a.claims.length !== 1) throw new Error("upstreaming worker takes exactly one Claim");
      const w = a.claims[0].work;
      fs.mkdirSync("/tmp/gh-aw/agent", { recursive: true });
      fs.writeFileSync("/tmp/gh-aw/agent/task.json", JSON.stringify(w, null, 2));
      JS
      task=/tmp/gh-aw/agent/task.json
      fork=$(jq -r '.fork // empty' "$task")
      upstream=$(jq -r '.upstream' "$task")
      head=$(jq -r '.expected_head // empty' "$task")
      base=$(jq -r '.base_sha // empty' "$task")
      [[ "$upstream" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "bad upstream"; exit 1; }
      mkdir -p "$GITHUB_WORKSPACE/fork"
      cd "$GITHUB_WORKSPACE/fork"
      git init -q
      git remote add upstream "https://github.com/$upstream.git"
      if [ -n "$fork" ]; then
        [[ "$fork" =~ ^riseproject-upstreaming/[A-Za-z0-9_.-]+$ ]] || { echo "bad fork"; exit 1; }
        git remote add origin "https://github.com/$fork.git"
      fi
      if [ -n "$base" ]; then git fetch -q --no-tags --depth=200 upstream "$base"; fi
      if [ -n "$head" ]; then
        git fetch -q --no-tags --depth=200 origin "$head"
        git checkout -q -B riscv64 "$head"
      elif [ -n "$base" ]; then
        git checkout -q -B riscv64 "$base"
      else
        git fetch -q --no-tags --depth=200 upstream HEAD
        git checkout -q -B riscv64 FETCH_HEAD
      fi
      git config user.name "riseproject-upstreaming"
      git config user.email "noreply@riseproject.dev"
      echo "checked out $(git rev-parse HEAD) into ./fork"
jobs:
  record:
    # Ordinary trusted job, not a safe output. An investigation never pushes,
    # so there is no fork token and no environment: this job only checks the
    # exact Claim's verified Result (gh-aw v1.2.2 ledger replay, same gate as
    # the worker's publish job), downloads exactly that artifact and hands the
    # dossier to the controller as an upstreaming-publication artifact.
    needs: [safe_outputs]
    if: needs.safe_outputs.outputs.work_queue_outcome == 'completed'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
      actions: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          persist-credentials: false
          path: control
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d  # v10.0.1
        with:
          enable-cache: false
      - name: Resolve this Claim's verified Result and download exactly its artifact
        working-directory: control
        env:
          GH_TOKEN: ${{ github.token }}
          ASSIGNMENT: ${{ inputs.work_queue_assignment }}
          WORKFLOW_PATH: .github/workflows/upstreaming-investigator.lock.yml
        run: |
          set -euo pipefail
          mkdir -p ../in
          printf '%s' "$ASSIGNMENT" > ../in/assignment.json
          printf '%s' "$ASSIGNMENT" | jq '.claims[0].work' > ../in/task.json
          [ "$(jq -r .task ../in/task.json)" = investigation ] || { echo "investigator only takes investigations"; exit 1; }
          rc=0
          gh_aw=$(upstreaming/install_gh_aw.sh "$RUNNER_TEMP/gh-aw-cli") || rc=3
          if [ "$rc" = 0 ]; then
            uv run --no-project --with-requirements upstreaming/requirements.txt \
              python -m upstreaming.queue_result --gh-aw "$gh_aw" \
                --assignment ../in/assignment.json --run-id "$GITHUB_RUN_ID" \
                --workflow "$WORKFLOW_PATH" --repo "$GITHUB_REPOSITORY" --out ../in || rc=$?
          else
            jq -n '{status:"infra_error", failure_class:"infrastructure", reason:"gh-aw install failed", stage:"result"}' > ../in/outcome.json
          fi
          if [ "$rc" = 0 ]; then
            uv run --no-project --with-requirements upstreaming/requirements.txt \
              python -m upstreaming.artifact extract ../in/proposal.zip ../in
            jq -n '{status:"investigation", failure_class:null, reason:null, stage:"result"}' > ../in/outcome.json
          fi
          jq . ../in/outcome.json >> "$GITHUB_STEP_SUMMARY"
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1
        if: always()
        with:
          name: upstreaming-publication
          path: |
            in/assignment.json
            in/task.json
            in/result.json
            in/outcome.json
            in/proposal.json
            in/dossier.json
          if-no-files-found: ignore
          retention-days: 30
timeout-minutes: 90
max-turns: 300
strict: true
---

# riscv64 upstreaming investigator

You investigate one upstream project for the RISE riscv64 Python-wheels
upstreaming pipeline. The trusted pre-agent step wrote the immutable task to
`/tmp/gh-aw/agent/task.json` and checked out the upstream project in
`./fork` (read-only: nothing you change there is used). The task's `plan`
field says what to do; `reason_ids` and `context` say why.

Only process the compiler-supplied `work_queue_assignment`. It has exactly
one Claim; use its `handle` as `claim_handle` on every safe output and on
`work_queue_claim_finish`.

## What to produce

Write these files into `upstreaming-out/` at the top of the workspace (next
to `fork/`, not inside it) and upload them with a single `upload_artifact`
call: `{"path": "upstreaming-out", "name": "upstreaming-proposal"}`:

- `dossier.json`: the facts a human needs to approve the contribution's
  scope, each with exact file paths or URLs as evidence:
  - release coverage: which platforms and architectures the latest release
    ships wheels for on PyPI, and whether riscv64 is already there;
  - build backend and native dependencies;
  - release graph: the workflows and jobs that build, test and publish
    wheels, and how they are triggered;
  - existing architecture precedent: the nearest aarch64/s390x/ppc64le
    wheel rows a riscv64 row should follow;
  - fork guards: conditions such as `if: github.repository == 'owner/repo'`
    that stop CI from running on a fork;
  - contribution rules: CONTRIBUTING, commit conventions, CLA/DCO;
  - any existing riscv64 work upstream (issues, PRs, CI);
  - proposed admission class, allowed paths, target matrix, and risks.
- `proposal.json`: a JSON object matching
  `upstreaming/schemas/proposal.schema.json` in the control repository,
  with `outcome: "investigation"`, `operation: "none"`, and
  `contribution_id`, `expected_revision` and `expected_head` copied from the
  task's `contribution_id`, `revision` and `expected_head`. Put a short
  summary of your findings in `diagnosis`.

Then call `work_queue_claim_finish` with `outcome: "completed"`. If you
cannot produce a useful result, stage `report_incomplete` explaining why and
finish with `outcome: "cancelled"`.

## Rules

1. Read and report only. You cannot push, open PRs, comment or change any
   repository, and you write no patches.
2. Do not ask questions upstream. If scope or maintainer intent is unclear,
   say so in the dossier with the options and your recommendation.
3. Distinguish what you verified (with a path or URL) from what you infer.
4. Never mention AI tools in anything you write.
