---
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
name: Upstreaming worker
description: Bounded riscv64 upstreaming task (patch, repair or revise one contribution)
on:
  workflow_dispatch:
permissions:
  contents: read
  issues: read
  pull-requests: read
  actions: read
engine:
  id: pi
model: anthropic/claude-opus-5-5
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
  - name: Check out the contribution fork at the expected head (read-only)
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
  safe_outputs:
    pre-steps:
      - name: Check out trusted native artifact compatibility patch
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          ref: ${{ github.sha }}
          persist-credentials: false
          path: native-artifact-compat
          sparse-checkout: upstreaming
      - name: Apply hash-pinned gh-aw v1.2.2 native artifact fix
        run: python3 native-artifact-compat/upstreaming/gh_aw_compat.py "$RUNNER_TEMP/gh-aw/actions"
  publish:
    # Ordinary trusted job, not a safe output. Gated on the compiled
    # safe_outputs outcome, then on the exact Claim's verified Result as
    # reported by the pinned gh-aw v1.2.2 CLI's validating ledger replay
    # (upstreaming/queue_result.py).
    needs: [safe_outputs]
    if: needs.safe_outputs.outputs.work_queue_outcome == 'completed'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    environment: upstreaming-publish
    permissions:
      contents: read
      actions: read
    concurrency:
      group: upstreaming-fork-writer
      cancel-in-progress: false
    outputs:
      status: ${{ steps.publish.outputs.status }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          persist-credentials: false
          path: control
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d  # v10.0.1
        with:
          enable-cache: false
      - name: Resolve this Claim's verified Result and download exactly its artifact
        id: result
        working-directory: control
        env:
          GH_TOKEN: ${{ github.token }}
          ASSIGNMENT: ${{ inputs.work_queue_assignment }}
          WORKFLOW_PATH: .github/workflows/upstreaming-worker.lock.yml
        run: |
          set -euo pipefail
          mkdir -p ../in
          printf '%s' "$ASSIGNMENT" > ../in/assignment.json
          printf '%s' "$ASSIGNMENT" | jq '.claims[0].work' > ../in/task.json
          [ "$(jq -r .task ../in/task.json)" != investigation ] || { echo "investigations run in upstreaming-investigator"; exit 1; }
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
          if [ "$rc" != 0 ]; then
            echo "publish=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          uv run --no-project --with-requirements upstreaming/requirements.txt \
            python -m upstreaming.artifact extract ../in/proposal.zip ../in
          uv run --no-project --with-requirements upstreaming/requirements.txt \
            python -m upstreaming.fork_publish preflight --record ../in/record.json --task ../in/task.json \
              --proposal ../in/proposal.json --out ../in/preflight.json
          jq -r '"fork_name=" + .fork_name, "publish=" + (.publish|tostring)' ../in/preflight.json >> "$GITHUB_OUTPUT"
          if [ "$(jq -r .publish ../in/preflight.json)" != true ]; then
            jq '{status:"rejected", failure_class:(.failure_class // "validation"), reason, stage:"preflight"}' \
              ../in/preflight.json > ../in/outcome.json
          fi
      - name: Mint a token for exactly this fork
        id: fork-token
        if: steps.result.outputs.publish == 'true'
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510  # v3.3.0
        with:
          client-id: ${{ vars.RISEPROJECT_APP_CLIENT_ID }}
          private-key: ${{ secrets.RISEPROJECT_APP_PRIVATE_KEY }}
          owner: riseproject-upstreaming
          repositories: ${{ steps.result.outputs.fork_name }}
          permission-contents: write
          permission-workflows: write
          permission-pull-requests: write
      - name: Rebuild, validate and push to riscv64 (exact-head lease)
        id: publish
        if: steps.result.outputs.publish == 'true'
        working-directory: control
        env:
          UPSTREAMING_FORK_TOKEN: ${{ steps.fork-token.outputs.token }}
        run: |
          set -euo pipefail
          rc=0
          uv run --no-project --with-requirements upstreaming/requirements.txt \
            python -m upstreaming.fork_publish publish --record ../in/record.json --task ../in/task.json \
              --proposal ../in/proposal.json --mbox ../in/patches.mbox --result ../in/result.json \
              --out ../in/outcome.json || rc=$?
          jq -r '"status=" + .status' ../in/outcome.json >> "$GITHUB_OUTPUT"
          jq . ../in/outcome.json >> "$GITHUB_STEP_SUMMARY"
          # 1 rejected / 3 infrastructure are recorded outcomes, not job failures;
          # 2 (uncertain) fails the job so it is visible, and discovery resolves it.
          exit $(( rc == 1 || rc == 3 ? 0 : rc ))
      # Everything the controller needs to record the outcome and, for an
      # infrastructure failure, to retry this exact publication without a new
      # agent run: the task, the verified artifact identity and the outcome.
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1
        if: always()
        with:
          name: upstreaming-publication
          path: |
            in/assignment.json
            in/task.json
            in/result.json
            in/preflight.json
            in/outcome.json
            in/proposal.json
            in/dossier.json
          if-no-files-found: ignore
          retention-days: 30
timeout-minutes: 120
max-turns: 400
strict: true
---

# riscv64 upstreaming worker

You handle exactly one task for the RISE riscv64 Python-wheels upstreaming
pipeline. The trusted pre-agent step wrote the immutable task to
`/tmp/gh-aw/agent/task.json` and checked out the contribution's `riscv64`
branch in `./fork`. The task's
`plan` field says what to do; `reason_ids` and `context` say why.

Only process the compiler-supplied `work_queue_assignment`. It has exactly
one Claim; use its `handle` as `claim_handle` on every safe output and on
`work_queue_claim_finish`.

## What to produce

Write these files into `upstreaming-out/` at the top of the workspace (next
to `fork/`, not inside it) and upload them with a single `upload_artifact`
call: `{"path": "upstreaming-out"}` (the native handler names the artifact
`claim-<hash>-upstreaming-out`):

- `proposal.json`: a JSON object matching
  `upstreaming/schemas/proposal.schema.json` in the control repository.
  `contribution_id`, `expected_revision` and `expected_head` must copy the
  task's `contribution_id`, `revision` and `expected_head`. `operation` is
  `append` (new commits on top of `expected_head`), `rewrite` (a series on
  top of `base_sha`, only if `allowed_operations` contains it) or `none`.
  `changed_files` lists every path your series changes relative to
  `expected_head` (for `rewrite`, relative to it as well).
  `patch_digest` is the sha256 of `patches.mbox`, or null.
- `patches.mbox`: for `append`, `git -C fork format-patch --stdout <expected_head>`;
  for `rewrite`, `git -C fork format-patch --stdout <base_sha>`. Omit it
  when `operation` is `none`.

Then call `work_queue_claim_finish` with `outcome: "completed"`. If you
cannot produce a useful result, stage `report_incomplete` explaining why and
finish with `outcome: "cancelled"`.

You cannot push, open PRs, comment or change any repository. A trusted job
re-applies your series in a fresh repository, validates it against the
approved scope and pushes it to `riscv64` itself. Anything outside
`allowed_paths`, any `{debug}` commit when `upstream_facing` is true, any
`pull_request_target`, `id-token: write`, new secret, interpolation of untrusted event text
into scripts or package publication step is rejected.

## Rules

1. Change only files matching `allowed_paths`. Make the smallest change that
   follows the nearest existing architecture pattern in the project (for
   example an existing aarch64 or s390x wheel row). No unrelated refactors,
   formatting or dependency changes.
2. Native riscv64 jobs use exactly `runs-on: ubuntu-24.04-riscv`. QEMU jobs
   follow the project's own x86_64/aarch64 host precedent. Manylinux image
   `manylinux_2_39_riscv64`, musllinux `musllinux_1_2_riscv64`.
3. Temporary fork-only changes that let CI run on the fork (for example
   removing `if: github.repository == 'owner/repo'`) go in a separate commit
   whose subject starts with `{debug}`. Never when `upstream_facing` is true.
   Debug commits enable validation only, never publication or secrets. The
   fork's CI must run the riscv64 wheel job on push to `riscv64`: if that
   workflow does not trigger on pushes to `riscv64`, add the trigger in the
   same `{debug}` commit. If the project already builds riscv64 wheels
   upstream, the `{debug}` commit alone can be the whole series.
4. Baseline code is `rv64gc`. Optional RVV only behind Linux `riscv_hwprobe`
   (`RISCV_HWPROBE_KEY_IMA_EXT_0` / `RISCV_HWPROBE_IMA_V`) with an `rv64gc`
   fallback. No global `-march=...v...` or `-march=native`.
5. Never remove, skip or weaken tests to get green CI. If the failure is
   infrastructure, permissions/approval, a missing prerequisite or unrelated,
   say so in `diagnosis` and `blockers`, use `operation: "none"`, and stop.
6. You may build and run tests locally in `./fork` to validate. Record what
   you ran in `validation_performed` and what you could not run in
   `validation_not_performed`. Your own assessment is not CI evidence.
7. Do not ask questions upstream. If scope or maintainer intent is unclear,
   use `outcome: "needs_clarification"` with the options and your
   recommendation in `diagnosis`.
8. Commit messages follow the upstream project's conventions. Never mention
   AI tools or add AI attribution trailers.
