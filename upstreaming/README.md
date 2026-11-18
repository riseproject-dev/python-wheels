# riscv64 upstreaming pipeline: trusted control code

This package implements the local, trusted parts of the upstreaming pipeline
planned in `python-wheels-upstreaming-pipeline-final-plan.md`: a small
deterministic controller and publisher around bounded model tasks. It helps
upstream projects publish Linux `riscv64` wheels themselves. The RISE index
and this repository's recipes are inputs to that work, not where the result
ends up.

Status: **Stage A/B groundwork**. Schemas, transition rules, command
handling, recovery, validators and a read-only observer exist and are
tested locally. No remote writer is enabled. Fork publication, the gh-aw
worker and state publication on `main` are blocked on the integration
checks in [`INTEGRATION.md`](INTEGRATION.md), and each one needs explicit
authorization before it is turned on.

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
| `collect.py` | Read-only GitHub/PyPI/usage collectors | Stage B |
| `image/` | Runner-free `linux/riscv64` reproduction image definition and guarded launcher | 13 |
| `gh-aw/upstreaming-worker.md.draft` | Uncompiled design sketch of the bounded worker | 5.1, 15 |
| `tests/` | Executable acceptance tests mapped to plan section 21 | 21 |

The repository also gets:

- `.github/ISSUE_TEMPLATE/upstreaming-request.yml`, the intake form (7.1). It
  needs an `upstreaming-request` label, which an authorized person has to
  create.
- `.github/workflows/upstreaming-validate.yml`, which runs the tests, state
  validation and the state-only trigger audit on PRs and pushes.
- `.github/workflows/upstreaming-controller.yml`, the read-only Stage B
  observer. It is `workflow_dispatch` only. The schedule and issue triggers
  are commented out until Stage B is approved.
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
