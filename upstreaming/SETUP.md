# One-time repository setup for the upstreaming pipeline

These settings are expected in `riseproject-dev/python-wheels`. The pipeline
does not create them itself.

## State environment

Only the controller state-commit job uses a GitHub Actions environment:

| Environment | Job | Purpose |
|---|---|---|
| `upstreaming-state` | `reconcile` in `upstreaming-controller.yml` | Mint a control-repository App token, publish validated `upstreaming-state/**` changes on `main`, and dispatch already-selected work or trusted retries |

Configure `upstreaming-state` with:

1. No required reviewer. A reviewer would stall every reconciliation tick.
2. No administrator bypass.
3. Selected deployment branch `main`, type **Branch**, with no other rule.
4. No environment secret or variable. The existing organization App key and
   client-ID variable remain available to the repository.

The control App installation needs Contents and Actions write access on the
control repository.

## Automatic development writers

Fork provisioning, `riscv64` publication and infrastructure-only retries do
not use a reviewer-gated environment. This is intentional: after an exact
verified investigation Result, the pipeline must proceed through bounded fork
development without human intervention. Human approval starts at upstream
handoff, not at fork creation or every development push.

Automatic writes remain gated by trusted code:

- policy `read_only` must be false;
- the controller must persist the exact operation intent first;
- the source repository ID and immutable base SHA must match;
- fork creation uses a destination creation token that cannot write existing
  repositories;
- settings and branch writes use a separate token restricted to one verified
  fork;
- proposal publication independently resolves the exact native Claim Result,
  validates paths/history, checks the expected head lease and verifies readback;
- retries reuse the same worker Result and operation. They do not invoke a model;
- no job receives production package credentials.

The writer App must be installed on `riseproject-upstreaming` and have the
repository-creation permission plus Contents, Workflows, Actions and Pull
requests write permissions needed by the trusted setup and publisher jobs.
Each repository token is narrowed to the one verified fork.

The App private key is an organization secret used elsewhere in this repository,
so an environment would not provide exclusive secret isolation. The exact-token,
operation and expected-head gates are the relevant writer boundaries.

## Human gate at upstream handoff

After development CI is accepted and debug-only changes are removed, the
contribution enters `handoff`. An authorized human must approve the exact clean
head before an upstream-facing PR can be registered. Upstream PR creation and
production package publication remain outside the automated development route.

## Emergency stop

- Set `"read_only": true` in `upstreaming/policy.json` on `main` to stop new
  state-changing ticks and trusted writer launches.
- Pause or park an individual contribution from its tracking issue.
- For an immediate repository-level stop, disable the upstreaming workflows or
  revoke the App installation/token permission. Read-only inspection remains
  available.

## Other one-time items

- `ANTHROPIC_API_KEY` is an organization secret selected for this repository.
  The worker, investigator and dispatcher use the pinned Pi models documented in
  their workflow sources.
- The `upstreaming-request` label starts intake on a *Package build request*.
- The first queue submission creates `work-queue`.
- Repository Actions default workflow permissions remain read-only. Individual
  trusted jobs request only their declared permissions.

## Verification

```sh
gh api repos/riseproject-dev/python-wheels/environments/upstreaming-state \
  --jq '{name, protection_rules, deployment_branch_policy}'
gh api repos/riseproject-dev/python-wheels/environments/upstreaming-state/deployment-branch-policies \
  --jq '.branch_policies[] | {name, type}'
```

Expected: `upstreaming-state` exists, has no required reviewer, and allows only
`main` as a deployment branch.
