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
`read_only: true`. `read_only` is now `false`: the controller persists state on `main` and dispatches tasks. The remaining Stage A
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
| `policy.json` | Reviewed policy: proposed numeric defaults, command authority (`660779` = `@luhenry`; immutable user IDs, since logins can be renamed), `read_only` | 7, 16, 19 |
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
| `SETUP.md` | Exact one-time repository settings: state environment, automatic development writers, upstream handoff and emergency stop | 10.2, 6.3 |
| `artifact.py` | Safe extraction of the untrusted proposal artifact | 15.3 |
| `fork_publish.py` | Trusted fork publisher: preflight, fresh rebuild of the patch series, validation, leased push, readback | 10.4, 15.3, 16.3 |
| `reconcile.py` | One reconciliation tick: publications, live observation, controller | 9 |
| `check_gh_aw.sh` | Locks match the pinned gh-aw v1.2.2 compiler; rejected-route fixtures still rejected | 22 |
| `image/` | Runner-free `linux/riscv64` reproduction image (latest runner `:prod`, host Docker daemon, rebuilt weekly by `upstreaming-image.yml`) and guarded launcher | 13 |
| `tests/` | Executable acceptance tests mapped to plan section 21 | 21 |

The repository also gets:

- Intake (7.1) uses the existing **Package build request** issues
  (`.github/ISSUE_TEMPLATE/package-request.yml`), which already track each
  package's riscv64 work. Add the `upstreaming-request` label to such an
  issue to start upstreaming it. The controller reads its *Source
  repository* and *Package name (on PyPI)* fields; *Why is this needed?* and
  *Additional context* become notes for the investigation.
- `.github/workflows/upstreaming-validate.yml`, which runs the tests, state
  validation and the state-only trigger audit on PRs and pushes.
- `.github/workflows/upstreaming-controller.yml`: `observe` (read-only
  report) and `reconcile` (state writer, active only when `read_only` is
  false). Label and command events trigger immediate ticks. Completion of an
  investigator, worker, provisioning or publish-retry workflow triggers the
  next tick, and a 5-minute schedule is the recovery fallback. State-only
  commits do not match any trigger, preventing recursion.
- `.github/workflows/upstreaming-image.yml`: rebuilds and publishes the
  reproduction image weekly, on changes to `upstreaming/image/`, and on demand.
- `.github/workflows/upstreaming-publish-retry.yml`: publish-only retry of
  one finished worker or investigator run (no agent), launched by `reconcile`.
- The gh-aw workflows, compiled with gh-aw v1.2.2
  (`upstreaming/check_gh_aw.sh` verifies the locks). Two worker profiles
  share the `upstreaming` pool; `work.profile_for` routes each task:
  - `upstreaming-investigator.md` / `.lock.yml`: investigations
    (`anthropic/claude-sonnet-5-5`). Read and report only. Its trusted
    `record` job independently resolves the exact native Result and validates
    the dossier. A dependent `notify` job then publishes or discovers the
    deterministic human-readable tracking-issue comment and uploads its
    read-back receipt. No fork token or publishing environment.
  - `upstreaming-dev-pr.yml`: trusted idempotent creation and readback of the
    same-fork `riscv64` development PR after a published patch head.
  - `upstreaming-worker.md` / `.lock.yml`: development patch, repair and
    upstream revision (`anthropic/claude-opus-5-5`), with the trusted
    `publish` job.
  - `upstreaming-dispatcher.md` / `.lock.yml`
    (`anthropic/claude-haiku-5-5`): stages the task the controller already
    committed in `active_work` (`python -m upstreaming plan`) and launches
    one worker. The model only explains the plan.

  A dispatch that never reaches the queue (the dispatcher failed, was
  skipped, or never started) is detected by `reconcile`: it reads the
  dispatcher's runs and the queue (gh-aw `work-queue replay --json`) and,
  while the task's Work is absent or unclaimed, launches the dispatcher
  again, up to `1 + retries.infrastructure_per_head_failure` dispatcher
  runs. Then the contribution waits for a human (`dispatch_failed`). Each
  relaunch replays the same committed request, so the queue sees identical
  Work. If the runs or the queue cannot be read, nothing is decided that
  tick.
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

## Onboarding a project (the whole loop)

Every project goes through the same steps. Project-specific evidence and
pilot details are kept in lifecycle state and diagnostic artifacts, not here.

1. **Request.** Add the `upstreaming-request` label to the project's
   *Package build request* issue. The next controller tick creates the
   contribution in `queued` and, unless paused, requests an investigation.
   Removing the label before any Work is requested durably abandons that intake;
   removing it after Work starts does not silently stop the contribution.
2. **Investigation.** The dispatcher launches `upstreaming-investigator`.
   A custom read-only GitHub MCP server uses the job's scoped token for issues,
   PRs, reviews, Actions and code without anonymous rate limits. Read-only web
   tools cover non-GitHub historical sources; the required graph MCP covers
   dependency evidence. After native delivery,
   the trusted `record` job validates the exact Result and the dependent
   `notify` job posts a bounded readable summary to the tracking issue. The
   controller records the dossier as evidence. A machine-readable, trusted-gated
   dossier decision either moves directly to `provisioning` with a bounded
   admission class and path set, or moves to `parked` when no concrete patch is
   actionable. Neither route waits for scope approval. An authorized human may
   override a parked decision with:

   ```text
   /upstreaming force-develop revision=N class=configuration_integration paths=".github/workflows/*" reason="Concrete scope to pursue."
   ```

3. **Provision the fork through trusted upstreaming workflows only.** Direct
   writes or direct CI dispatches in `riseproject-upstreaming/*` are forbidden.
   The controller records a `fork_provision` intent and dispatches the trusted
   workflow. It creates or verifies the fork, initializes read-only CI, disables
   parses the default-branch workflow files as a bounded data inventory,
   explicitly enables safe CI, disables privileged/publication workflows, and
   creates the exact `riscv64` base only if absent. Existing work is never reset. Creation uses a token that
   cannot write existing repositories; branch/settings operations use a separate
   single-fork token. Permission failures hold for review, without local fallback.
   After receipt verification and fresh fork/ref readback, the controller moves
   to `development`. Bare existing-fork verification cannot bypass this workflow.
   Fork creation, one-fork Administration/settings, inherited-workflow disabling
   and exact base branch initialization are live-verified.
4. **Development.** The next tick requests a `development_patch`. Before any
   edit, the worker must use its token-authenticated read-only GitHub research
   server to inspect per-file commit history, analogous accepted and rejected
   PRs, relevant issues/reviews and repository contribution/release policy. Policy-sensitive files such as changelogs are changed only when that
   evidence establishes the convention. When build CI shares a workflow with an
   OIDC/package publication job, a separate `{debug}` commit disables only that
   publication job with literal `if: false`; trusted setup verifies it is
   unreachable before enabling build/test CI, and cleanup removes the debug
   commit before handoff. Repair tasks also receive bounded durable evidence summaries for the exact review or CI feedback that caused them. The
   `upstreaming-worker` then proposes
   a series, and its trusted `publish` job
   automatically rebuilds, revalidates and pushes it to `riscv64` under the
   exact operation, token and expected-head gates. The controller records a
   `dev_pr_create` operation; the trusted workflow opens or discovers `riscv64`
   against the frozen base and verifies readback. The pull-request event starts
   fork CI on `ubuntu-24.04-riscv`; the controller records CI evidence for the
   exact head and asks for repairs
   while it fails. Passing means every required riscv64 job executed
   natively and a riscv64 wheel artifact was uploaded.
5. **Upstream handoff.** When the exact development head passes its frozen CI
   contract and has no debug commits, observation automatically records it as the
   clean head and enters `handoff`. Human involvement begins there: a human
   approves that exact head and opens or registers the upstream-facing PR.

Investigator inputs, mandatory history/dependency/report research and the trusted
pre-Completion gate: [`INVESTIGATION.md`](INVESTIGATION.md). Weekly runtime,
compiler and action updates: [`dependencies/README.md`](dependencies/README.md).

## Commands on a tracking issue

Post a command as its own comment on the request issue. The issue says which
contribution it applies to, so `contribution=` is optional (if given, it must
match). Stop commands need no revision:

```text
/upstreaming pause
/upstreaming pause reason="waiting for runner quota"
/upstreaming park reason="needs RVV hardware we do not have"
/upstreaming block reason="..."
/upstreaming abandon reason="..."
```

Commands that change or approve work name the revision you reviewed, shown
in the issue's status and in the controller report, so they cannot apply to
work that moved meanwhile:

```text
/upstreaming resume revision=1 reason="quota back"
/upstreaming force-develop revision=2 class=configuration_integration paths=".github/workflows/*" reason="Concrete override scope."
/upstreaming approve-handoff revision=3 head=<clean head sha>
```

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
- **Park** is an automatic no-action outcome when the dossier identifies no
  concrete patch. `resume` sends it through a new investigation. An authorized,
  current-revision `force-develop` instead records a bounded override scope and
  proceeds directly to automatic provisioning. Duplicates, timers and
  prerequisite changes never resume a parked contribution.
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
