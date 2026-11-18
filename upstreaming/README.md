# riscv64 upstreaming pipeline: trusted control code

This package implements the local, trusted parts of the upstreaming pipeline
planned in `python-wheels-upstreaming-pipeline-final-plan.md`: a small
deterministic controller and publisher around bounded model tasks. It helps
upstream projects publish Linux `riscv64` wheels themselves. The RISE index
and this repository's recipes are inputs to that work, not where the result
ends up.

Status: **Stage A implementation, not yet run remotely**. The whole write
path exists and is tested locally: the gh-aw worker (compiled with v1.2.2),
the dispatcher, the trusted fork publisher, live CI observation and the
state commit on `main`. Every writer is off while `policy.json` has
`read_only: true`, and none has run against GitHub. The remaining Stage A
checks are in [`INTEGRATION.md`](INTEGRATION.md); each needs explicit
authorization.

## How a task flows (plan 5.1, 15.3)

```text
controller workflow (reconcile job, every tick, no model)
  fold publication outcomes, observe fork head + CI, apply commands/intake
  -> commit changed state to main (state_commit, validated, fast-forward)
  -> if work was selected: launch the dispatcher
dispatcher (gh-aw, trusted preparation step runs `python -m upstreaming plan`)
  -> stages one Work + dispatch_next; native scheduler grants a Claim
worker (gh-aw, assignment-only, no remote-write credential)
  agent patches ./fork locally, uploads ONE native artifact
  (upstreaming-out/proposal.json + patches.mbox), finishes its Claim
  -> gh-aw verifies the artifact and records Result (= proposal delivered)
worker publish job (ordinary trusted job, gated on work_queue_outcome)
  install the pinned gh-aw v1.2.2 CLI, `work-queue replay --json`, require
  this Claim's Result (barrier verified, bound to this run, attempt 1),
  download exactly that artifact by ID and digest, preflight against state,
  mint a token for the one task fork, rebuild + validate in a fresh repo,
  leased push to riscv64, read back the ref, upload the publication outcome
next controller tick: records the publication receipt and the new head,
  then watches CI on that exact head
on an infrastructure failure (network, token, API): the controller schedules
  upstreaming-publish-retry.yml for the same worker run with backoff
  (15, 60, 240 minutes; `retries.infrastructure_per_head_failure` attempts),
  never a new agent task; after that it waits for a human
```

Outcome classes: `validation` (the proposal is unacceptable; the next tick
asks the agent for a repair), `stale` (the branch, revision or pause changed;
re-plan, no retry), `infrastructure` (retry the publish only). A retry
whose push already landed confirms it from the branch instead of pushing
again.

A queue Result proves the proposal artifact was delivered, nothing more.
The fork push is a separate pipeline operation with its own receipt.

## Layout

| Path | Purpose | Plan |
|---|---|---|
| `schemas/*.schema.json` | Contribution, project, operation, command, event, evidence, agent proposal and policy schemas (v1) | 6.2 |
| `policy.json` | Reviewed policy: proposed numeric defaults, command authority (`660779` = `@luhenry`; immutable user IDs, since logins can be renamed), `read_only: true` | 7, 16, 19 |
| `commands.py` | Strict `/upstreaming` command grammar | 7.3 |
| `intake.py` | Issue-form parsing, cheap event filter, admission, command acceptance/replay rules | 7.1-7.3 |
| `lifecycle.py` | Phases, ordinary transitions, command effects, revision rule, publication check, write admission | 8 |
| `state.py` | State store and the independent final-tree validator for state commits | 6.1, 6.3, 6.5 |
| `state_commit.py` | Builds a state-only commit with a private index and publishes it as a fast-forward with bounded rebuild-on-race | 6.3 |
| `recovery.py` | Operation intents/receipts, discovery predicates, backoff, alerts, evidence-backed resolution | 16.3, 16.4 |
| `ci_evidence.py` | Run/attempt/job evaluation. Only executed matching jobs count. | 6.2, 14.3 |
| `capacity.py` | Runner pressure from `usage.json`, reservations, admission, budgets, failure classes | 16.1, 16.2 |
| `publisher.py` | Fresh trusted workspace and final-tree validation of fork updates, `{debug}` handling, exact-head lease | 10.4, 14.2, 15.3 |
| `release.py` | Official release coverage against a frozen matrix (abi3, free-threaded, compressed tags, floors, yanks) | 11.2, 18.2 |
| `probe.py` | External wheel probe: RECORD, ELF machine/ABI, `DT_NEEDED`, RVV leakage in baseline objects, binary-only install | 11.4, 12.1 |
| `triggers.py` | Trigger-compatibility audit of `.github/workflows` | 6.4 |
| `controller.py` | One deterministic tick. Effects are requested, not executed. | 9 |
| `collect.py` | Read-only GitHub client (GET only, pagination): issues, comments, PRs, branch heads, workflow runs/jobs/check runs/statuses/artifacts, PyPI, usage, sw-ecosystem reports | 9, 14.3 |
| `observe_ci.py` | Live fork/upstream CI on the exact head into evidence records and activity changes; branch-operation discovery | 9, 14.3 |
| `work.py` | Immutable gh-aw Work payloads, artifact-only effect contracts, staged plans | 5.1, 15.1 |
| `queue_result.py` | Publication gate: the exact Claim's verified Result and its artifact identity, from the pinned gh-aw CLI's `work-queue replay --json` | 15.3 |
| `install_gh_aw.sh` | Installs gh-aw v1.2.2 with a pinned SHA-256 (worker publish job, retry, validation CI) | 15.3, 22 |
| `SETUP.md` | Exact one-time repository settings: the `upstreaming-publish` and `upstreaming-state` environments, emergency stop | 10.2, 6.3 |
| `artifact.py` | Safe extraction of the untrusted proposal artifact | 15.3 |
| `fork_publish.py` | Trusted fork publisher: preflight, fresh rebuild of the patch series, validation, leased push, readback | 10.4, 15.3, 16.3 |
| `reconcile.py` | One reconciliation tick: publications, live observation, controller | 9 |
| `check_gh_aw.sh` | Locks match the pinned gh-aw v1.2.2 compiler; rejected-route fixtures still rejected | 22 |
| `image/` | Runner-free `linux/riscv64` reproduction image (latest runner `:prod`, host Docker daemon, rebuilt weekly by `upstreaming-image.yml`) and guarded launcher | 13 |
| `tests/` | Executable acceptance tests mapped to plan section 21 | 21 |

The repository also gets:

- `.github/ISSUE_TEMPLATE/upstreaming-request.yml`, the intake form (7.1). It
  needs an `upstreaming-request` label, which an authorized person has to
  create.
- `.github/workflows/upstreaming-validate.yml`, which runs the tests, state
  validation and the state-only trigger audit on PRs and pushes.
- `.github/workflows/upstreaming-controller.yml`: `observe` (read-only
  report) and `reconcile` (state writer, active only when `read_only` is
  false). `workflow_dispatch` only; the schedule and issue triggers are
  commented out until the rollout stage is approved.
- `.github/workflows/upstreaming-image.yml`: rebuilds and publishes the
  reproduction image weekly, on changes to `upstreaming/image/`, and on demand.
- `.github/workflows/upstreaming-publish-retry.yml`: publish-only retry of
  one finished worker run (no agent), launched by `reconcile`.
- `.github/workflows/upstreaming-worker.md` / `.lock.yml` and
  `upstreaming-dispatcher.md` / `.lock.yml`: the gh-aw workflows, compiled
  with gh-aw v1.2.2 (`upstreaming/check_gh_aw.sh` verifies the locks).
  `.github/workflows/aw.json` (queue settings: one `upstreaming` pool,
  concurrency 1), `.github/workflows/shared/work-queue-staged-plan.md`
  (gh-aw v1.2.2's shared dispatcher contract, copied verbatim),
  `.github/aw/actions-lock.json` and `.gitattributes` are compiler outputs.
- `upstreaming-state/`, the state root (6.1). It is empty for now.

The pipeline is deliberately separate from the downstream build machinery
in this repository: nothing here is imported by, or calls into,
`ci_scripts/`, `_setup.yml`, `_publish-wheel.yml` or the `build-*.yml`
workflows, and they do not use it. Upstreaming docs stay out of `docs/`,
because a push touching `docs/**` deploys the website.

## Usage

```sh
# Tests (stdlib unittest; needs jsonschema, packaging, pyyaml)
python3 -m unittest discover -s upstreaming/tests -t .

python3 -m upstreaming validate-state
python3 -m upstreaming audit-triggers --expect-none --paths upstreaming-state/x.json
python3 -m upstreaming check-state-diff <trusted-base> <candidate>
python3 -m upstreaming parse-command comment.txt
python3 -m upstreaming capacity [--file usage.json]
python3 -m upstreaming observe [--offline]     # read-only tick
python3 -m upstreaming.probe some.whl [--install --import mod]
```

None of these perform remote writes.

## Design decisions encoded here

- **Correctness** comes from the model's judgment, executed CI and human
  review. The validators enforce identities, paths, credentials and
  operations. They are not semantic proofs.
- **Revision** increments only when the requested work changes: the head or
  base, the approved scope, or a human decision that affects work. Polls and
  status observations never bump it, so a useful proposal survives a status
  change and is rejected after a head change.
- **Pause** is best effort. A pause is honored at the publication check, and
  a stale pause is still honored. An effect that already passed the check
  may finish and is then reconciled as usual.
- **Park** can be lifted only by an explicit, current-revision `resume`,
  which sends the contribution back to `investigation` so the dossier is
  revalidated. Duplicates, timers and prerequisite changes never resume a
  parked contribution.
- **Handoff**: `request-handoff` needs executed CI evidence for the exact
  head. `approve-handoff` binds to the clean head after `{debug}` removal.
  Any new change made before submission clears the approval.
  `register-upstream-pr` checks the actual PR resource: base repository,
  base ref, head SHA and state. If the PR's head is not
  `riseproject-upstreaming/<p>:riscv64`, automated revisions are disabled
  and patches go to the submitter instead of being pushed to some other
  branch.
- **Operations** have deterministic IDs. A lost response leaves the
  operation `uncertain`. Discovery may confirm the effect, but the effect is
  never repeated. Absence of evidence is not proof of nonlaunch, and capacity
  is only freed on verified termination or definitive nonlaunch.
- **CI evidence** counts only executed, matching jobs on the exact head.
  Skipped, neutral, cancelled, approval-required, missing and other-SHA runs
  never count as success. Reruns resolve to the latest attempt.
- **State commits** must be a single commit directly on the trusted tip.
  They may only add or modify regular `100644`, schema-valid, size-bounded,
  secret-free JSON whose identity matches its path under
  `upstreaming-state/`. No deletions, escapes, symlinks or case collisions
  are allowed. The token is repository-scoped, so this check is what keeps
  the writer inside `upstreaming-state/`.
- **Fork updates** are reconstructed in a fresh Git with no
  user/system config, hooks or credential helpers. They are checked
  against the trusted base for the approved paths, symlinks, submodules,
  new executables, size limits, case collisions, history shape, and
  forbidden workflow content (`pull_request_target`, OIDC, new secrets,
  untrusted interpolation, PyPI publication). `{debug}` commits are
  rejected once the branch is upstream-facing. Pushes use
  `--force-with-lease=refs/heads/riscv64:<expected>` only.
