# One-time repository setup for the upstreaming pipeline

These are the settings in `riseproject-dev/python-wheels` that the
workflows expect. Nothing here is created by the pipeline itself.

## Why two environments

Only two jobs in the pipeline can obtain write credentials, and each runs in
its own GitHub Actions environment:

| Environment | Job(s) | What it can do once it runs |
|---|---|---|
| `upstreaming-publish` | `publish` in `upstreaming-worker.lock.yml`; `publish` in `upstreaming-publish-retry.yml` | Mint a GitHub App token for **one** `riseproject-upstreaming/<fork>` (contents, workflows, pull-requests write) and push that fork's `riscv64` branch |
| `upstreaming-state` | `reconcile` in `upstreaming-controller.yml` | Mint a GitHub App token for `riseproject-dev/python-wheels` (contents, actions write), push one validated state-only commit to `main`, launch the dispatcher and publish-only retries |

The agent job, the dispatcher and the read-only `observe` job use neither
environment.

An environment gives three controls on top of the code checks:

1. **Branch restriction.** Only workflow runs from `main` can enter it, so a
   PR or a pushed branch cannot run a modified publish job with the App key.
2. **Secret scoping.** The App private key is exposed only to jobs that
   declare the environment, not to every job that can read repository or org
   secrets.
3. **An emergency stop, and optional approval.** Restricting the environment
   to a branch that does not exist stops every writer immediately, without a
   code change. Required reviewers give you a manual gate during the pilot.

## `upstreaming-publish`

GitHub: **Settings → Environments → New environment** in
`riseproject-dev/python-wheels`.

1. **Name:** `upstreaming-publish` (exactly; the workflows reference it).
2. **Deployment protection rules**
   - **Required reviewers:** during Stage A/C, tick it and add `luhenry`. Every
     fork push then waits for your approval in the Actions run. Leave
     **Prevent self-review** unticked, since you are the only reviewer. Once
     you trust the pipeline, untick it; automatic publish-only retries
     (`upstreaming-publish-retry.yml`) also wait for approval while it is on.
   - **Wait timer:** leave unset.
   - **Allow administrators to bypass configured protection rules:** untick it,
     so that the rules also apply to you.
3. **Deployment branches and tags:** choose **Selected branches and tags**,
   **Add deployment branch or tag rule**, type `main`, ref type **Branch**.
   Do not add any other rule.
4. **Environment secrets:** **Add environment secret**
   - Name `RISEPROJECT_APP_PRIVATE_KEY`, value: the same private key (PEM,
     including the `-----BEGIN` and `-----END` lines) as the
     `RISEPROJECT_APP_PRIVATE_KEY` org secret.
   An environment secret takes precedence over the org secret of the same
   name for jobs in this environment. This keeps the pipeline working if the
   org secret's repository access is later narrowed (step 6).
5. **Environment variables:** none. `RISEPROJECT_APP_CLIENT_ID` is already an
   org variable visible to this repository (`Iv23libkhGSOLc70e3vl`).
6. **Not now:** once both environments hold the key, remove
   `python-wheels` from the org secret `RISEPROJECT_APP_PRIVATE_KEY`'s
   selected repositories (**Org settings → Secrets and variables → Actions →
   RISEPROJECT_APP_PRIVATE_KEY → Repository access**), **if** no other
   workflow in `python-wheels` uses it. Today 1,623 `build-*.yml` workflows
   plus `gc-releases.yml`, `mark-pr-ready.yml`, `nightly.yml` and
   `website.yml` do, so leave the org secret as it is. The consequence: any
   workflow running on `main` in this repository can read the same key, so
   the environments add branch and reviewer controls for the upstreaming
   jobs, not exclusive access to the key.

The App must be installed on `riseproject-upstreaming` with access to each
fork it will push to, and must have **Contents**, **Workflows** and **Pull
requests** read/write permissions there (reported done; checked in Stage A
item 2). The token minted in the job is restricted to the single fork named
by the task.

## `upstreaming-state`

1. **Name:** `upstreaming-state`.
2. **Deployment protection rules**
   - **Required reviewers:** leave unticked. This job runs every tick (every
     15 minutes once the schedule is enabled) and only writes validated
     `upstreaming-state/**` JSON. A reviewer gate here would stall the loop.
     Writes are gated by `upstreaming/policy.json` `read_only` instead.
   - **Allow administrators to bypass:** untick.
3. **Deployment branches and tags:** **Selected branches and tags**, one rule:
   `main`, type **Branch**.
4. **Environment secrets:** `RISEPROJECT_APP_PRIVATE_KEY`, same value as
   above.
5. **Environment variables:** none.

The App's installation on `riseproject-dev` needs **Contents: write** and
**Actions: write** on `python-wheels` (it already pushes to `main` and
dispatches workflows for the existing downstream jobs).

## Emergency stop

- **Stop all writes now:** in each environment, change the deployment branch
  rule from `main` to a branch that does not exist (for example
  `disabled`). Jobs that need the environment then fail before they start.
  Read-only observation keeps working.
- **Stop durably:** set `"read_only": true` in `upstreaming/policy.json` on
  `main`. That is the default today.

## Other one-time items (not environments)

- **Secret `ANTHROPIC_API_KEY`:** already an org secret selected for this
  repository. The worker (Pi, `anthropic/opus-5.5`), its threat detection and
  the dispatcher use it. It is not placed in either environment because the
  agent jobs do not use environments.
- **Label `upstreaming-request`:** create it (you said you will).
- **First queue submission:** creates the `work-queue` branch (you said you
  will). The dispatcher's first staged plan does this too.
- **Actions settings:** **Settings → Actions → General → Workflow
  permissions** stays **Read repository contents and packages permissions**.
  Every upstreaming job requests exactly what it needs.

## How to check it

From a checkout, with `gh` authenticated as a repository admin:

```sh
gh api repos/riseproject-dev/python-wheels/environments --jq '.environments[] | {name, protection_rules, deployment_branch_policy}'
gh api repos/riseproject-dev/python-wheels/environments/upstreaming-publish/deployment-branch-policies --jq '.branch_policies[] | {name, type}'
gh api repos/riseproject-dev/python-wheels/environments/upstreaming-state/deployment-branch-policies --jq '.branch_policies[] | {name, type}'
gh api repos/riseproject-dev/python-wheels/environments/upstreaming-publish/secrets --jq '.secrets[].name'
gh api repos/riseproject-dev/python-wheels/environments/upstreaming-state/secrets --jq '.secrets[].name'
```

Expected: both environments exist; each has exactly one branch policy
`main` of type `branch`; each lists the secret `RISEPROJECT_APP_PRIVATE_KEY`;
`upstreaming-publish` has a `required_reviewers` rule while the pilot is
gated.
