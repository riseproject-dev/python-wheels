# Upstreaming integration status

This is the current development checkpoint. Consult it before choosing the next
step and update it after significant tests, deployments, failures and decisions.
The overall sequence is defined by the operator's final plan:
`~/notes/ecosystem-wg/python/python-wheels-upstreaming/python-wheels-upstreaming-pipeline-final-plan.md`.
Concrete project targets and external-action history belong in the operator's
local `session-log.md`, not this generic pipeline documentation.

## Current checkpoint (2026-11-19)

**Stage A is not complete.** Controller intake, state publication, dispatch
recovery and investigator execution work remotely. A native artifact upload has
succeeded, but its Claim has no verified Result. The trusted record/publish jobs
correctly stayed blocked. No end-to-end workflow-mediated fork patch, development
PR, native wheel acceptance or release rehearsal is claimed.

Stages B/C remain limited by Stage A. Local observer and simulated publication
coverage are not substitutes for verified live delivery and publication.

## Operating decisions

- Continue development on `upstreaming-pipeline`, resetting it from current
  `main` after each merged PR and automatic remote-branch deletion.
- Control-repository PR creation/merging is authorized after CI passes.
- All contribution-fork creation, branch writes, PR mutations and CI dispatches
  must be performed exclusively by upstreaming workflows in the control
  repository. No direct local fork operations or manual target CI workaround.
- No upstream PR creation or production package publication is authorized.
- Keep gh-aw v1.2.2 until a stable, coordinated upgrade is reviewed. No alternate
  scheduler, publication route, salted branch or unverified-artifact fallback.
- Only the investigator has approved unsandboxed internet access. It remains
  read-only and gets neither the controller App key nor a fork-write token.
  Its native detector is disabled with explicit operator approval because v1.2.2
  requires the agent sandbox. Trusted completeness and artifact gates remain.
- The dispatcher and patch worker stay sandboxed. The worker's native detector
  currently uses a provider-specific CLI; Pi-only detection is an unresolved
  compatibility limitation and is not silently worked around.

## Deployed and observed remotely

| Component | Evidence | Status |
|---|---|---|
| Intake and command receipts | Controller runs 44378630046, 44379705607 and later ticks | Accepted commands and state-only App commits observed |
| State-only trigger isolation | Actual state commits plus recurring static audit | No recursive agent or downstream build triggered |
| Dispatcher recovery | Controller 44414462720 launched dispatcher 44414548306 | Failed admission can be relaunched within budget |
| Native queue bootstrap/launch | Dispatcher 44414548306 and 44420780035 | Work/Claim admitted, authenticated investigator launched |
| Investigator execution | Runs 44415024119 and 44421278888 | Read-only checkout and model execution succeeded |
| Native artifact compatibility patch | PR #4940 merged as `101ad75`; subsequent run 44421278888 | Original upload authorization blocker fixed; native artifact uploaded |
| Verified native Result | `safe_outputs` failed in run 44421278888; record skipped | **Blocked**, not equivalent to uploaded bytes |
| Fork write / development PR | Trusted publisher has not run for a verified patch Result | **Unverified** |
| Native build/test/release acceptance | No workflow-mediated validated contribution yet | **Unverified** |

The earlier manually initiated pilot workaround was removed and the branch
restored. It is explicitly excluded from pipeline success evidence.

Both existing App installations and required workflow-write permission have
been independently inspected. Repository-creation write permission is also
visible on the App and destination installation. This permission
is a verified prerequisite, not proof that workflow-mediated fork creation works. The control state writer works with its separate
repository-scoped token. Actual single-fork write-token isolation and publisher
CI-trigger association still need integration evidence.

## Latest deployment and current local changes

PR #4941 passed all control checks and merged as `5b7277becea`. Its investigator,
dependency and finalization fixes are deployed as source, but native contract
adoption and a successful remote Result remain unverified. GitHub server-signed
control commits verified the requested author identity; local SSH signing no
longer prevents control-code publication.

Current local work has **148 passing pipeline tests** and passing hand-authored
workflow lint. It adds a trusted workflow-only fork provisioning job, recorded
`fork_provision` intents, scoped creation/per-fork tokens, source-ID/base binding,
receipt readback, and initial-patch admission without waiting for base CI. The
manual fork helper is removed and bare existing-fork verification cannot bypass
workflow provisioning. These provisioning changes are not yet deployed or tested
against real fork permissions.

The additive, versioned investigator-profile migration in the same native pool
was approved by the operator and is implemented locally as
`upstreaming-investigator-v2`. The native on-demand `PoolInstall` copies installed
profiles and pool limits before adding the default-revision worker. Existing
profiles, Work and pending delivery history are preserved; no new queue or ref
is introduced. Live registration remains unverified.

Previously merged implementation:

- The native artifact patch now separates artifact descriptors from private
  repository/run authorization receipts, covering the observed finalizer error.
- Full issue description, digest and canonical URL are frozen into the requested
  task and passed through immutable Work. The investigator follows comments and
  user-provided links. Older active tasks without this snapshot need a new
  revision; the dispatcher refuses to invent or silently truncate context.
- Mandatory upstream research covers the entire relevant issue/PR corpus,
  historical CI, reviews, documentation, websites, mailing lists, blogs,
  maintainers and release relationships, with recorded queries, pagination scope,
  source URLs and accepted/rejected decisions.
- GitHub Issues tools are enabled with public-author research permitted.
- Required project-graph MCP (`:latest`, as requested), with query/result and
  dependency assessment in the dossier. Runtime use is **not yet verified**.
- Mandatory discovery of a matching ecosystem report; available reports must be
  read fully, used across support/dependency/prior-work analysis and cross-checked
  against current upstream evidence.
- Investigator-only unsandboxed access with pinned `pi-web-access` and
  `pi-subagents` extensions. Native detector disabled only for that investigator.
- A trusted completeness gate reads bounded JSON from the exact Claim staging
  namespace **before native Completion**; missing/inaccessible/partial research
  cannot complete. Cancellation may proceed without a dossier. Verified output
  is checked again before dossier evidence is recorded. This checks documented
  completeness and identity, not the semantic truth of every model claim.
- Dependabot coverage for upstreaming runtime packages, stable compiler releases,
  GitHub Actions and control Python requirements. Inventory/source synchronization
  prevents manifest-only runtime upgrades from silently leaving old pins.
- Authored Python CI invocations use `uv run`, including synchronization and the
  native compatibility installer. Generated internal gh-aw runtime setup is not
  hand-edited.

Details: [`INVESTIGATION.md`](INVESTIGATION.md),
[`dependencies/README.md`](dependencies/README.md),
[`gh-aw-compat/README.md`](gh-aw-compat/README.md).

## Latest local verification

- **140 pipeline tests pass**, including issue-context propagation, every required
  research category, graph/report requirements, stale identity, exact Claim
  staging, cancellation, symlink rejection, dependency synchronization and CI
  boundary tests.
- **110 native artifact/resource-scope regression tests pass** against the exact
  v1.2.2 source with mocked uploads/APIs. Foreign Claim/run/repository targets,
  cancelled Claims, reused factories, closed channels and changed artifact
  metadata are rejected.
- All three workflows compile with gh-aw v1.2.2 and lock comparison passes.
  The investigator's unsandboxed warning is intentional and operator-approved.
- Committed state validates; state-only trigger audit finds no triggered workflow
  and no `workflow_run` consumer.
- Dependency pins match the inventory. Stable compiler/package pins are retained.
- Local end-to-end tests exercise artifact validation, fresh Git reconstruction,
  exact-head leased publication to local repositories and CI reconciliation.
  These are simulated integration tests, not remote publication evidence.

Reproduction commands:

```sh
uv run --no-project --with-requirements upstreaming/requirements.txt python -m unittest discover -s upstreaming/tests -t .
uv run --no-project python upstreaming/dependencies/sync.py
upstreaming/check_gh_aw.sh /path/to/pinned-gh-aw
sh upstreaming/gh-aw-compat/check.sh
uv run --no-project --with-requirements upstreaming/requirements.txt python -m upstreaming validate-state
uv run --no-project --with-requirements upstreaming/requirements.txt python -m upstreaming audit-triggers --expect-none --paths upstreaming-state/contributions/x.json
```

## Blockers and next steps, in order

**Control-code publication:** local SSH signing is unavailable. The operator
permits control-repository pushes/PRs, so the documented GitHub server-signed
`createCommitOnBranch` route may be used for this branch after verifying author
identity and signature. Keep code/config and workflow changes in separate commits.
This does not change the contribution-fork publication route or waive native
Result, token, expected-head or operation-receipt checks.

1. **Resolve native delivery, not merely upload.** The live finalizer error is
   `Unsupported Claim effect target field: name`: artifact descriptor metadata
   was used as an authorization selector. The branch compatibility patch now
   supplies a separately registered private native target proof; 110 native
   tests include full delivery inspection. This still needs remote validation.
   Inspect the failed original Claim's native receipt checks and use
   supported verification/recovery or an explicitly reviewed compatibility fix.
   Never synthesize a Result, select a generic artifact by name, rerun uncertain
   effects, reset the queue, or treat reservation release as delivery.
2. **Deploy the investigator changes safely.** Adding Issues/extensions/MCP tools
   changes its native worker contract. The installed queue cannot update that
   authority while existing completed Work has pending delivery barriers.
   The operator approved an additive versioned profile in the same pool instead
   of replacing installed authority. Deploy it through supported on-demand
   `PoolInstall`, verify old profiles/economics remain intact, and retain pending
   history. Do not reset the queue or claim those old deliveries succeeded.
3. **Run the complete investigator through the controller/dispatcher.** Verify
   issue/comments, graph MCP, ecosystem report and historical research; require
   the gate, native verified Result and recorded dossier evidence.
4. **Approve bounded scope and owners.** The primary/backup owner, target matrix,
   allowed paths, release contract and existing-upstream-work decision must come
   from reviewed evidence. Do not infer that wheel CI alone closes a release gap.
5. **Validate workflow-only fork provisioning.** The implementation is now local:
   the controller persists a `fork_provision` operation, dispatches the trusted
   provisioning workflow, then consumes its receipt only after fork/ref readback.
   Real creation/token/settings permissions are not tested yet. Existing pilot
   setup is not proof of automated creation. The writer App's source-installation prerequisites may
   require a separately approved provisioning identity. No manual fallback.
6. **Develop, publish and open the fork PR through workflows.** Resolve the exact
   Claim Result, mint a single-fork token, independently rebuild/validate the
   series, push only `riscv64` with an exact-head lease, verify readback and record
   receipts. Implement development-PR creation/discovery with an operation marker.
7. **Observe actual PR CI and repair within budget.** Verify native
   `ubuntu-24.04-riscv` execution, build plus tests, wheel identities and independent
   acceptance probes. No skipped-job success, weakened tests or manual CI substitute.
8. **Rehearse the release path safely.** Validate build/repair/test/aggregation and
   would-be upload selection using a safe artifact sink, no production credentials.
   A separate release repository needs its own authorized contribution; unsupported
   rehearsal is a documented maintainer-owned prerequisite, not invented green CI.

The immediate requested milestone is a workflow-provisioned contribution fork,
`riscv64` branch and development PR with adequate executed build/test/release-path
evidence. Upstream handoff and later steps remain outside the current task.

## Remaining acceptance areas

- Real single-fork token isolation, native publisher/PR receipt recovery, pause
  races, expected-head conflicts and trigger association.
- Safe CI activation, actual wheel payload/linkage/runtime-floor installation and
  optional-extension fallback evidence; filenames and agent claims are insufficient.
- Disposable reproduction-host isolation/resource tests. The image build workflow
  exists, but hostile Docker/host-network containment is not certified here.
- Reviewed owners/capacity/billing limits, artifact expiry/deleted-run recovery,
  queue contract migration and missing-credential behavior.
- Optimization, upstream handoff/revision, merge cleanup and official release
  verification follow later gated stages of the final plan, not this pilot result.
