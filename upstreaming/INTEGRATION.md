# Integration report and Stage A checklist

This file separates what was **verified locally** from what is **reported**
by the user and from what is **still unverified**. Each item marked
unverified needs explicit authorization before anyone tests it remotely.

## Verified locally (2026-11-18)

- `python3 -m unittest discover -s upstreaming/tests -t .`
  passes. These are the plan section 21 rows that can be exercised without
  remote access. See the table below.
- **Trigger audit (6.4).** A static reading of every `on.push` filter in
  `.github/workflows` (1,633 workflows at the time of writing). A push to
  `main` that only touches `upstreaming-state/**` starts no workflow. None of
  the workflows consumes `workflow_run`. Only `website.yml` has an
  unfiltered-by-package push trigger (`docs/**`, `ci_scripts/dashboard/**`),
  and `build-*.yml` push triggers are limited to each package's own
  workflow/YAML. `upstreaming-validate.yml` runs on
  `upstreaming/**` and its own workflow files. The audit runs in
  CI on every PR, so a new workflow with a broad `push` trigger fails it.
  This is static evidence only: confirming GitHub's real behavior for
  App-token pushes is still a Stage A item.
- **Probe on real wheels.** `markupsafe 3.0.4` (manylinux riscv64, PyPI)
  passes: rv64gc arch attributes, only policy libraries. `numpy 2.5.3`
  (RISE index) is flagged because three objects, including the bundled
  OpenBLAS, carry `v1p0`/`zve*` in `.riscv.attributes`. That attribute is the
  link-time union, so it can come from properly dispatched code. The probe
  therefore requires an explicit reviewer allowance (`--rvv-allowed`) plus a
  no-V fallback run. The flag itself is not a verdict.
- **Runner image digest.** Resolved by a read-only `imagetools inspect`:
  `ghcr.io/riseproject-dev/riscv-runner/runner/ubuntu-24.04:prod` is index
  `sha256:48874e63b5f9007cf0424488182ce2845d303a92a211c92fd459c29a0a0620ef`
  (linux/riscv64 manifest `sha256:9f35ce18...`). The entrypoint is
  `docker-init -- riscv-runner-entrypoint.sh` and the user is `runner`. The
  repro Dockerfiles pin this index. They have not been built.
- `actionlint` and `shellcheck` pass on the hand-written workflows and
  scripts. (actionlint reports a few items in the gh-aw-generated locks,
  such as `concurrency.queue`, that newer Actions features use; the locks
  are not edited by hand.)
- **gh-aw v1.2.2 (plan 22, item 1).** Downloaded release binary
  `linux-arm64`, SHA-256 matches the release `checksums.txt`
  (`a1dd217c...d11fe3`), kept in `.git/pw-scratch/upstreaming/gh-aw`.
  `upstreaming/check_gh_aw.sh <binary>` passes:
  - `upstreaming-worker.md` and `upstreaming-dispatcher.md` compile under
    strict mode and the committed locks are byte-identical to the
    compiler's output.
  - In the worker lock: the agent job has read-only permissions; the only
    agent resource output is `upload_artifact` (max one, `allowed-paths:
    upstreaming-out/*`, 4 MiB); the App private key appears only in the
    `publish` job; `publish` needs `safe_outputs` and `detection` and runs
    only when `needs.safe_outputs.outputs.work_queue_outcome == 'completed'`
    (the v1.2.2 handler emits `completed` only when every Claim settled with
    a `result`, see `safe_output_handler_manager.cjs`).
  - Rejected-route fixtures (`upstreaming/tests/gh-aw-fixtures/`): a
    credentialed custom safe-output job is still refused ("requires a
    trusted per-Claim delivery adapter"); the cross-repository
    `push-to-pull-request-branch` worker still compiles, but has no Claim
    delivery verifier in v1.2.2 source.
- **Result gate.** The publish job runs the pinned gh-aw v1.2.2 CLI
  (`upstreaming/install_gh_aw.sh`, SHA-256 pinned for linux-amd64 and
  linux-arm64) and reads `work-queue replay --json`. The fields used
  (`works[id].claim_id/barrier/result/result_commit_id`,
  `claims[id].state/work_id/dispatch_id`, `dispatches[id].run`) are the JSON
  tags of `Projection` in v1.2.2 `pkg/workqueue/types.go`; gh-aw sets
  `barrier: "verified"` and `result` only in `settleVerifiedDelivery`, which
  requires delivery evidence from `verified_receipts` for the dispatch's
  bound run, attempt 1.
- **Engine.** Worker and dispatcher use `engine: pi` with
  `model: anthropic/opus-5.5`; both compile, the lock validates
  `ANTHROPIC_API_KEY`, and threat detection also runs on Anthropic.
- **Local end to end.** `tests/test_pipeline.py` runs controller selection,
  Work construction, a simulated agent series, Result resolution, artifact
  extraction, preflight, rebuild, leased push to a local bare fork, and the
  next reconciliation tick (publication receipt, head change, CI evidence).

## Reported by the user, not independently inspected

- The `riseproject-upstreaming` organization exists.
- The `riseproject-dev` writer App and the `rise-risc-v-runners` runner App
  are installed there.

## Unverified: Stage A deliverables (plan 20, 22)

Each item needs explicit authorization before it is tested remotely.

1. **gh-aw remote run.** Compilation is verified (above). Still to run on
   GitHub: one dispatcher -> worker -> verified `upload_artifact` Result ->
   publish job, and confirm (a) `gh aw work-queue replay --json` reports the
   Claim with `barrier: "verified"` and a `result` descriptor whose
   `upload_artifact` resource has the fields `queue_result.py` reads (taken
   from v1.2.2 source, `pkg/workqueue/types.go` and `upload_artifact.cjs`,
   not yet observed), (b) the `publish` job gate fires only on that Result,
   (c) the replay in `publish` already sees the Result written by the same
   run's `safe_outputs` job, (d) the `pre-agent-steps` checkout of `./fork`
   works inside the gh-aw sandbox, (e) Pi with `anthropic/opus-5.5` resolves
   (the compiler cannot check model availability offline). Needs: the
   `work-queue` branch bootstrapped by the first trusted submission, and the
   environments in [`SETUP.md`](SETUP.md). If any of (a)-(d) fails, report it as a
   blocker; do not switch routes.
2. **Destination token.** Discover the installation with
   `GET /orgs/riseproject-upstreaming/installation`. Mint a token with
   `repositories: <one fork>` and `contents`, `pull_requests` and
   `workflows` write. Confirm that it cannot write
   `riseproject-dev/python-wheels`, and that build jobs can obtain neither
   token nor the App key.
3. **Control token and `main` write route.** `main` currently has no
   branch protection or ruleset (read-only check, 2026-11-18), so an App
   token with `contents: write` can push. The `reconcile` job mints one
   with `owner: riseproject-dev`, `repositories: python-wheels`,
   `contents`/`actions` write. Choose the identity and signing route for
   `state_commit.publish`. Document its real
   blast radius: the token is repository-wide. Confirm that an App-token
   state-only push triggers nothing, and that a mixed commit is rejected by
   `check-state-diff`.
4. **Fork provisioning/migration.** Prefer a human-provisioned fork for the
   MVP. Inventory the existing contribution forks under `riseproject-dev`.
   They are not migrated.
5. **Native runner.** Run one real `ubuntu-24.04-riscv` job in a selected
   fork. Check runner-group/selected-repository settings and confirm that
   the fork's default `GITHUB_TOKEN` is read-only, with no OIDC and no
   inherited secrets.
6. **Owners and policy.** `command_authority.actor_ids` currently holds only
   `660779` (`@luhenry`), as an interim setting. Name the primary/backup
   owner, submitter and reviewer; a backup owner is required before write
   admission. Approve the proposed numeric defaults, or change them.
7. **Pilot contract.** Choose the pilot project (an existing `@luhenry`
   project), its frozen target rows, the dependency contract, the required
   job patterns, and either a safe rehearsal or an explicit release
   limitation.
8. **Capacity thresholds.** Agree `max_pending_jobs_rise` and
   `max_pending_age_seconds` with the runner operators. The historical
   snapshot (113 pending for RISE) already exceeds the proposed 100, so the
   observer would defer expensive work.
9. **Isolation.** Provision the disposable VM for `image/run.sh`. Run the
   hostile-Docker/host-network test from plan 13.2, and test the
   CPU/memory/disk/network limits enforced outside the guest. GHCR
   publication of the repro image needs separate authorization.
10. **Label.** Create the `upstreaming-request` label.

## Section 21 coverage

| Fixture row | Local test | Remaining |
|---|---|---|
| Valid/duplicate/unauthorized/oversized request, missed event, edited target | `test_commands_intake.TestIntake`, `TestTick.test_intake_creates_queued_contribution` | Catch-up cursor against live API |
| Quoted/multiple/replayed/edited/deleted/stale commands | `TestCommandGrammar`, `TestCommandAcceptance`, `TestPauseParkResume` | - |
| Status update vs changed head/scope | `TestRevision` | Real publisher rejection |
| Pause before/after publication check | `TestPublicationCheck`, `TestTick.test_pause_processed_before_work...` | In-flight race on real push |
| Parked project, dependency change, duplicate | `test_park_only_explicit_resume`, `TestIntake.test_admission` | Native Work cancellation |
| Destination vs control token, fork OIDC | static: `publisher.FORBIDDEN_WORKFLOW` | Stage A item 2, 5 |
| Native fork job | - | Stage A item 5 |
| Workflow-write denial, salted branch, leased rewrite | `TestPublisherValidation.test_lease`, schema `head_ref` const | Compiled gh-aw outputs |
| Hostile Git config/paths/modes/symlinks/submodules | `TestPublisherValidation`, `publisher.SAFE_GIT_CONFIG` | Hostile bundle transport |
| State-only push, mixed, concurrent downstream, rename/delete | `TestStateDiff`, `TestStateCommit`, `TestTriggers` | App-token push on GitHub |
| Lost receipt / uncertain dispatch / resolution | `TestRecovery` | Native Claim/Result recovery |
| Test-merge SHA, reruns, skipped/neutral/approval | `TestCiEvidence` | Live check-run pagination |
| Debug head, clean rewrite, upstream-facing | `test_debug_commits_and_upstream_facing`, `TestHandoff` | Pilot |
| Wheel payload/linkage/RVV leak, hidden index | `test_probe`, `probe.install_and_import` | Clean target sandbox run |
| Runtime floor, compressed/abi3/free-threaded tags | `TestRelease` | Floor install test |
| QEMU nested build, hostile Docker | `image/run.sh` guards | Stage A item 9 |
| hwprobe/RVV dispatch, benchmarks | static RVV leak check only | Stage E |
| Merge stops development, release polling, yanks | `TestMergeAndRelease`, `TestRelease` | Cleanup route |
| Budgets do not reset, no-progress review | `TestCapacityBudgets` | Billing ceilings |
| No-write mode, corrupt/oversized state, secrets | `test_read_only_refuses`, `test_store_roundtrip...`, `test_rejects_symlink_mode_and_secret` | Migration tooling |
