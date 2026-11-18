# Integration report and Stage A checklist

This file separates what was **verified locally** from what is **reported**
by the user and from what is **still unverified**. Each item marked
unverified needs explicit authorization before anyone tests it remotely.

## Verified locally (2026-11-18)

- `python3 -m unittest discover -s ci_scripts/upstreaming/tests -t .`
  passes. These are the plan section 21 rows that can be exercised without
  remote access. See the table below.
- **Trigger audit (6.4).** A static reading of every `on.push` filter in
  `.github/workflows` (1,633 workflows at the time of writing). A push to
  `main` that only touches `upstreaming-state/**` starts no workflow. None of
  the workflows consumes `workflow_run`. Only `website.yml` has an
  unfiltered-by-package push trigger (`docs/**`, `ci_scripts/dashboard/**`),
  and `build-*.yml` push triggers are limited to each package's own
  workflow/YAML. `upstreaming-validate.yml` runs on
  `ci_scripts/upstreaming/**` and its own workflow files. The audit runs in
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
- `actionlint` and `shellcheck` pass on the new workflows and scripts.

## Reported by the user, not independently inspected

- The `riseproject-upstreaming` organization exists.
- The `riseproject-dev` writer App and the `rise-risc-v-runners` runner App
  are installed there.

## Unverified: Stage A deliverables (plan 20, 22)

Each item needs explicit authorization before it is tested remotely.

1. **gh-aw pin.** `gh aw` is not installed here. Pin a release, compile
   `gh-aw/upstreaming-worker.md.draft`, and check that the compiled
   safe-outputs keep exactly `riscv64`, with no salt, no fallback PR/issue,
   no `recreate-ref` and no automatic merge. Also check that the native
   queue can carry the Work payload/effect contract used by
   `controller.tick`, and that leased rewrites have a supported route. If one
   of these is missing, report it as a blocker. Do not switch routes.
2. **Destination token.** Discover the installation with
   `GET /orgs/riseproject-upstreaming/installation`. Mint a token with
   `repositories: <one fork>` and `contents`, `pull_requests` and
   `workflows` write. Confirm that it cannot write
   `riseproject-dev/python-wheels`, and that build jobs can obtain neither
   token nor the App key.
3. **Control token and `main` write route.** Choose the ruleset/bypass,
   identity and signing route for `state_commit.publish`. Document its real
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
6. **Owners and policy.** Fill `policy.json` `command_authority.actor_ids`
   with immutable GitHub user IDs. Name the primary/backup owner, submitter
   and reviewer. Approve the proposed numeric defaults, or change them.
7. **Pilot contract.** Choose the pilot project (an existing `@luhenry`
   project), its frozen target rows, the dependency contract, the required
   job patterns, and either a safe rehearsal or an explicit release
   limitation.
8. **Capacity thresholds.** Agree `max_pending_jobs_rise` and
   `max_pending_age_seconds` with the runner operators. The historical
   snapshot (113 pending for RISE) already exceeds the proposed 100, so the
   observer would defer expensive work.
9. **Isolation.** Provision the disposable VM for `repro/run.sh`. Run the
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
| QEMU nested build, hostile Docker | `repro/run.sh` guards | Stage A item 9 |
| hwprobe/RVV dispatch, benchmarks | static RVV leak check only | Stage E |
| Merge stops development, release polling, yanks | `TestMergeAndRelease`, `TestRelease` | Cleanup route |
| Budgets do not reset, no-progress review | `TestCapacityBudgets` | Billing ceilings |
| No-write mode, corrupt/oversized state, secrets | `test_read_only_refuses`, `test_store_roundtrip...`, `test_rejects_symlink_mode_and_secret` | Migration tooling |
