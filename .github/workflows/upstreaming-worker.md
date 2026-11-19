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
  version: "1.5.0"
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
  bash:
    - "*"
  edit:
mcp-servers:
  github-authenticated:
    # Read-only, job-token authenticated history research without the pinned
    # gateway's incompatible cross-server source-integrity labels.
    container: "ghcr.io/github/github-mcp-server:v2.1.0"
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${{ github.token }}"
      GITHUB_READ_ONLY: "1"
      GITHUB_TOOLSETS: "context,repos,issues,pull_requests,actions"
      GITHUB_FEATURES: "fields_param"
    allowed:
      - get_commit
      - get_file_contents
      - get_pull_request
      - get_pull_request_comments
      - get_pull_request_diff
      - get_pull_request_files
      - get_pull_request_review_comments
      - get_pull_request_reviews
      - get_pull_request_status
      - issue_read
      - list_commits
      - list_issues
      - list_pull_requests
      - pull_request_read
      - search_code
      - search_issues
      - search_pull_requests
      - actions_list
    required: true
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
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d  # v10.0.1
        with:
          enable-cache: false
      - name: Apply hash-pinned gh-aw v1.2.2 native artifact fix
        run: uv run --no-project python native-artifact-compat/upstreaming/gh_aw_compat.py "$RUNNER_TEMP/gh-aw/actions"
  publish:
    # Ordinary trusted job, not a safe output. Gated on the compiled
    # safe_outputs outcome, then on the exact Claim's verified Result as
    # reported by the pinned gh-aw v1.2.2 CLI's validating ledger replay
    # (upstreaming/queue_result.py).
    needs: [safe_outputs]
    if: needs.safe_outputs.outputs.work_queue_outcome == 'completed'
    runs-on: ubuntu-latest
    timeout-minutes: 15
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
  continuation:
    needs: [safe_outputs, publish]
    if: always()
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510  # v3.3.0
        id: control-token
        with:
          client-id: ${{ vars.RISEPROJECT_APP_CLIENT_ID }}
          private-key: ${{ secrets.RISEPROJECT_APP_PRIVATE_KEY }}
          owner: riseproject-dev
          repositories: python-wheels
          permission-contents: read
          permission-actions: write
      - name: Continue reconciliation after the worker is terminal
        env:
          GH_TOKEN: ${{ steps.control-token.outputs.token }}
        run: gh workflow run upstreaming-controller.yml --repo "$GITHUB_REPOSITORY" --ref main
timeout-minutes: 120
max-turns: 400
strict: true
---

# riscv64 upstreaming worker

You handle exactly one task for the RISE riscv64 Python-wheels upstreaming
pipeline. The trusted pre-agent step wrote the immutable task to
`/tmp/gh-aw/agent/task.json` and checked out the contribution's `riscv64`
branch in `./fork`. The task's
`plan` field says what to do; `reason_ids` and `context` say why. For repair and
revision tasks, read every entry in `context.reason_evidence` before researching
or editing. Treat its concrete review feedback and rejected-change descriptions
as required repair constraints, then verify them against repository history.

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
`pull_request_target`, new secret, or interpolation of untrusted event text into
scripts is rejected.

## Mandatory change-history research

Before modifying any file, extensively research whether that kind of change is
accepted by this project. Use `github-authenticated` for all GitHub issue, PR,
review, Actions and code queries; do not use anonymous GitHub fetching.

- run `git log --follow -- <path>` and inspect the relevant commits and diffs;
- use blame where needed to identify the decision and maintainers behind the
  current form;
- search and read relevant open and closed upstream issues and pull requests,
  including reviews and rejected/superseded approaches;
- read contribution, release and changelog policies plus recent analogous PRs;
- cross-check the investigation dossier against current repository history.

For release notes, changelogs, news fragments, generated metadata and similar
policy-sensitive files, include a change only when commit/PR history or explicit
project documentation shows that contributor PRs should update that exact file.
For example, `CHANGELOG.md` being in `allowed_paths` is permission, not evidence
that it should be edited. If convention is unclear or conflicting, omit that file
and explain the evidence in `diagnosis` and `validation_not_performed`.

Do not begin editing until this history review is complete. If required issue,
PR, review or commit history is inaccessible, use `operation: "none"`, report the
blocker and stop rather than guessing. Record the key URLs, commits, decisions
and analogous changes in the proposal diagnosis.

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
   Debug commits enable validation only, never publication or secrets.
   Development CI runs on the automatically opened same-fork PR from
   `riscv64` to the frozen base. If the existing workflow already has a
   `pull_request` trigger covering that base, do not add `push: riscv64` or any
   other fork-only trigger. Never change unrelated event-dependent behavior,
   upload conditions, artifact retention or release behavior solely to make fork
   validation produce extra evidence. In particular, do not broaden conditions
   such as `inputs.upload`, add `github.event_name == 'push'`, or otherwise alter
   non-riscv64 behavior. If PR CI builds a wheel but intentionally does not upload
   it, leave that policy unchanged and record the acceptance limitation for a
   separate trusted probe. `riseproject-upstreaming` is a credentialless,
   configuration-free shell organization used only to hold contribution forks.
   It has no package secrets, publishing environments, repository variables or
   configured external OIDC trust, and none will be added. Do not change or
   disable `id-token: write`, Twine, or package-publisher actions merely because
   they exist: publication should fail out of the box for the fork identity. A
   successful external publication would demonstrate that the upstream relying
   party already trusts an equivalently broad identity and must be reported, not
   hidden with a source patch. Repository-mutating GitHub permissions and
   `pull_request_target` remain forbidden because they can mutate the fork itself.
   Add a separate `{debug}` trigger/guard adjustment only when no PR-compatible
   CI trigger exists, and explain the repository history that justifies it. If
   the project already builds riscv64 wheels upstream, a necessary `{debug}`
   guard adjustment alone can be the whole series.
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
8. Commit structure and history updates follow the upstream project's documented
   and observed conventions. Never mention
   AI tools or add AI attribution trailers. When the patch adds or relies on the
   `ubuntu-24.04-riscv` native runner, the commit body must mention
   `RISC-V GitHub Runners [1]` and end with this reference line exactly:

   ```text
   [1]: https://ci.riseproject.dev/
   ```
