# Gotchas — PR, CI, triggers, publishing & maintainer signals

One thematic slice of the porting gotchas. Each entry keeps its permanent number (cited elsewhere as "gotcha N"); numbers are stable IDs, not sequential, and a few (33, 55, 56, 57) are reused across themes — see [gotchas-index.md](../gotchas-index.md).

To pull up one entry: `grep -n '^N\. ' references/gotchas/pr-ci-and-maintainer.md`.

## In this file

- **45** — A brand-new `build-<pkg>.yml` cannot be dispatched from a PR — GitHub only knows
- **54** — A `build-<pkg>.yml` that is not yet on the default branch cannot be
- **62** — A multi-hour job's log can be dropped by GitHub entirely — quiet the build tool
- **65** — Resuming another agent's in-flight port: re-check the branch against *today's*
- **68** — A pinned action SHA that does not exist kills the job in "Set up job", after the
- **80** — When a maintainer parks a port, stop pushing to the branch entirely — the
- **89** — No workflow runs at all after pushing a PR may be GitHub, not your triggers — check
- **158** — Editing a PR's *description* is free on a parked port; pushing a commit is not
- **163** — A maintainer hold that *names* a condition is an instruction to come back and
- **173** — `gh pr list --state open --head <pkg>` does not see a *merged* PR, so a finished

---

45. **A brand-new `build-<pkg>.yml` cannot be dispatched from a PR — GitHub only knows
    a workflow that has already run at least once.** The `Trigger: <pkg>:<ver>` line makes
    `pr-trigger.yml` run `gh workflow run build-<pkg>.yml --ref <branch>`, which resolves
    the file name through `POST /repos/.../actions/workflows/{file}/dispatches`. That
    lookup only sees workflows in the repository's *registry*, and a file that has never
    produced a run is not in it: the call dies with `HTTP 404: workflow build-<pkg>.yml
    not found on the default branch`, the trigger job goes red, and no build ever starts.
    Not a permissions or ref problem — the same call succeeds for every other open port
    PR, because those workflows were registered by a run under the `pull_request` trigger
    that `workflows: rework triggering behaviour` (#364) removed.
    - **Check registration rather than guessing:** `gh api
      "repos/riseproject-dev/python-wheels/actions/workflows?per_page=100" --paginate
      -q '.workflows[].path' | grep <pkg>`. Living on `main` is sufficient but not
      necessary — `build-scipy.yml`/`build-shapely.yml` are listed while existing only on
      their PR branches.
    - **Nothing inside the port fixes it**, so don't burn cycles rewording the `Trigger:`
      line or re-pushing: only a first run registers a workflow, and no trigger the file is
      allowed to declare can produce one. Validate everything locally, open the PR, and
      report the blocker — the workflow has to reach `main` (or `pr-trigger.yml` needs a
      path+ref dispatch that doesn't go through the workflow registry) before CI can be
      driven green.

54. **A `build-<pkg>.yml` that is not yet on the default branch cannot be
    `workflow_dispatch`-ed at all, so a brand-new package needs the `pull_request:
    paths` trigger to get its first CI run.** GitHub's dispatch API resolves a workflow
    by its file name *on the default branch*; for a file that only exists on your PR
    branch it answers `HTTP 404: workflow build-<pkg>.yml not found on the default
    branch`, and `gh api repos/<repo>/actions/workflows` does not list it (no id has
    been assigned). That is true of `gh workflow run --ref <branch>` **and** of
    `pr-trigger.yml`, which is just `gh workflow run` behind a `Trigger: <pkg>:<ver>`
    line in the PR body — so on a new-package PR the trigger job fails and no build ever
    starts. The `pull_request: paths` trigger is what registers the workflow: once one
    run exists the workflow gets an id, and `workflow_dispatch` on the branch starts
    working (that is why an in-flight package PR shows a `pull_request` run first and
    `workflow_dispatch` runs only after). Keep both triggers on a new workflow, as every
    workflow on `main` does — the `workflow_dispatch`-only rework (#364) was reverted by
    #391 for exactly this reason. `Trigger:` lines remain the way to build a *different
    version* of a workflow that already exists on `main`.

62. **A multi-hour job's log can be dropped by GitHub entirely — quiet the build tool
    and tee to an artifact *before* you spend the cycle (the ray/bazel case).** A build
    step that ran 3h43m and failed left **no** retrievable log: `gh run view --log-failed`
    said `log not found`, `gh api .../jobs/<id>/logs` answered `BlobNotFound`, and the
    run's log zip contained only the short jobs. The failure was undiagnosable and the
    same tree had to be rebuilt blind — a second multi-hour cycle bought nothing. The
    short jobs in the *same run* returned their logs fine, so this is volume, not a
    permissions or self-hosted-runner problem.
    - **The usual culprit is progress rendering, not real output.** bazel redraws a
      status block continuously and emits it even with no TTY (the escape codes show up
      in the stored log as `[1A[K`), so hours of it dwarf the compiler output you
      actually want. Most heavy build tools have the same knob under a different name.
    - **Prefer the project's own pass-through variable** over editing its build scripts.
      ray's `python/setup.py` reads `BAZEL_ARGS` (`bazel_flags.extend(shlex.split(BAZEL_ARGS))`),
      so `export BAZEL_ARGS="--curses=no --show_progress_rate_limit=60"` is upstream's
      documented knob rather than a divergence. It cut the log to ~3.6k lines / 34 KB.
    - **Tee to a file and upload it on failure as the belt-and-braces half** — one step,
      and it survives whatever GitHub decides about the job log:
      ```yaml
      - name: Build wheels
        run: |
          set -o pipefail
          docker run ... bash <<'SCRIPT' 2>&1 | tee build.log
          ...
          SCRIPT
      - name: Upload build log
        if: failure()
        uses: actions/upload-artifact@<sha>
        with: {name: <pkg>-<ver>-build-log, path: build.log}
      ```
      **`set -o pipefail` is load-bearing**: the default `run:` shell is `bash -e {0}`
      *without* pipefail, so `tee` would otherwise report success and the step would go
      green on a failed build. Verify the pattern in 5 seconds on any host — a heredoc
      that `exit 7`s through `| tee` must still give `rc=7`.

65. **Resuming another agent's in-flight port: re-check the branch against *today's*
    main, and treat a maintainer hold as binding even when a fix must be pushed (the
    sglang follow-up).** Two things bite when picking up an existing PR rather than
    starting one.
    - **A commit that followed a repo-wide convention can have been invalidated while
      the PR sat open.** sglang's branch head was "drop pull_request trigger, build via
      Trigger: directive", written to follow #364 — which #391 reverted. Diff the
      workflow's `on:`/header against a *recently merged* sibling (not against the
      workflow you copied from originally) before touching anything else; the branch,
      not main, is the thing that drifted.
    - **Under a hold (gotcha 48), a push that touches `build-<pkg>.yml` re-fires the
      `pull_request` trigger whether you want it or not** — `paths` matches the PR's
      diff against base, so *every* push to the branch starts the build again. That is
      not a licence to let it run: land the fix, then `gh run cancel` the run you
      caused, so the correction reaches the branch without taking the shared riscv64
      runners back. Say in the report that you cancelled it and why; a cancelled run
      you explain is cheaper than six runner-hours the maintainer already refused twice.

68. **A pinned action SHA that does not exist kills the job in "Set up job", after the
    queue wait — verify every `uses:` pin before pushing.** `actionlint` checks the
    *syntax* of `owner/repo@ref` and never asks GitHub whether the ref resolves, so a
    mistyped or hallucinated 40-hex SHA passes every local check and then fails the job
    with ``Unable to resolve action `actions/download-artifact@<sha>`, unable to find
    version `<sha>` `` — before checkout, before any `run:` step. On a workflow whose
    first jobs are cheap and whose expensive job is `needs:`-gated behind them, that is a
    full cycle burnt on nothing (here: a queue wait plus a 100-minute bazel bootstrap
    before the wheel job even started). One API call per pin settles it:
    ```bash
    grep -ohE 'uses: [^@]+@[a-f0-9]{40}' .github/workflows/build-<pkg>.yml | sort -u |
      while read -r _ a; do gh api "repos/${a%@*}/commits/${a#*@}" --jq .sha >/dev/null \
        || echo "BAD PIN: $a"; done
    ```
    Cheaper still, and the reason this is worth a rule rather than a habit: **copy the pin
    from a workflow already on `main`** rather than from memory or from another action's
    SHA — `grep -rhoE '<owner>/<action>@[a-f0-9]+ *# *v[0-9.]+' .github/workflows/ | sort |
    uniq -c` shows what the repo already uses and how many workflows agree on it. A pin
    that disagrees with every other workflow in the repo is a bug even when it resolves.

80. **When a maintainer parks a port, stop pushing to the branch entirely — the
    `pull_request: paths` trigger makes *every* push restart the riscv64 build (the sglang
    follow-up).** Gotcha 48 says a stripped `Trigger:` line or a human-cancelled run is a
    stop signal and not a flake, but it only warns against re-adding the `Trigger:` line.
    That is not enough: gotcha 54 requires a new workflow to keep `pull_request: paths`, so
    on a parked PR an *ordinary* commit — even one that only fixes the triggers, rebases
    onto `main`, or tidies a comment — dispatches the full matrix onto the shared
    `ubuntu-24.04-riscv` runners again. PR #357 was cancelled by `luhenry` three times, the
    last one **21 seconds** after a "restore the pull_request trigger" push, following an
    explicit PR comment ("Waiting for dependencies to be available before trying to enable
    it further"). Nothing in the workflow was wrong; the pushes themselves were the problem.
    - **Read the run's `actor`/`triggering_actor` before treating a cancellation as
      infra flake**: `gh api repos/<repo>/actions/runs/<id> -q
      '{c:.conclusion,a:.actor.login,t:.triggering_actor.login,d:.updated_at}'`. A human
      login plus a sub-minute delta between `created_at` and `updated_at` is a deliberate
      cancel — a runner/infra failure neither names a person nor lands that fast.
    - **A maintainer comment on the PR is part of the CI signal.** Check `gh pr view <n>
      --json comments` alongside `statusCheckRollup` before deciding to re-run anything;
      "waiting for X" there outranks a red rollup as the reason the matrix is not green.
    - **Verify the stated blocker instead of restating it**, so the report is evidence and
      not hearsay. Non-extra entries in `info.requires_dist` are the ones that gate
      installability: sglang hard-requires `cuda-python>=13.0` and `cuda-tile==1.6.0rc5`,
      neither of which has a riscv64 file on PyPI or on our registry (gotcha 30's `curl`),
      and CUDA is proprietary — so the wheel is buildable but not installable, permanently,
      which is exactly what the maintainer was waiting on. Land the workflow, say plainly
      that CI was never proven green and why, and leave the dispatch to them.

89. **No workflow runs at all after pushing a PR may be GitHub, not your triggers — check
    the status API before re-reading gotchas 45/54.** Those two explain the *registry*
    failure mode, where a `workflow_dispatch` of a never-run workflow 404s while
    `pull_request` still works. A total absence — `gh api
    "repos/<repo>/actions/runs?branch=<branch>"` empty, `gh pr checks` reporting none, and
    even the repo-wide `pull_request` checks (`pr-checks.yml`) missing — is a different
    thing, and other branches showing fresh `startup_failure` runs is the tell that it is
    not yours. One call settles it:
    ```bash
    curl -s https://www.githubstatus.com/api/v2/summary.json \
      | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["status"]["description"]);[print("!",c["name"],c["status"]) for c in d["components"] if c["status"]!="operational"]'
    ```
    `Actions major_outage` means wait, not debug — a workflow edited during the outage
    would be a change made for no reason.

158. **Editing a PR's *description* is free on a parked port; pushing a commit is not
    (the complement to gotcha 80).** Gotcha 80 says an ordinary push to a held PR restarts
    the whole riscv64 matrix, because `pull_request: paths` matches the PR's diff against
    base on every push. That makes it easy to assume the PR is untouchable and to leave a
    finished port carrying a description written against an older convention. It is not:
    GitHub's default `pull_request` activity types are `opened`, `synchronize` and
    `reopened`, and **`edited` is not among them**, so `gh pr edit --body-file` fires no
    build at all. Confirmed empirically here — three body edits on a parked PR produced
    only skipped `pr-trigger.yml` runs and left the green `Build ... (riscv64)` run from
    the previous day as the newest one on the branch.
    - **So when resuming an older port (gotcha 65), bring the description up to the
      current template even when you must not push.** Convention drifts in *both* files:
      check the branch's `on:`/header against a recently merged sibling **and** the PR body
      against the PR-description template (`references/pr-and-publishing.md`), which may have
      been added or rewritten after the PR was opened.
    - **Verify the branch is genuinely undrifted before concluding there is nothing to
      push.** Being tens of commits behind `main` is not by itself drift — a port that adds
      only new files (`build-<pkg>.yml`, `patches/<pkg>/**`) cannot conflict, so a rebase
      buys nothing and costs a full matrix re-run. Diff the conventions, not the commit
      count.
    - **A merged dependency PR is not a landed dependency.** The registry check
      (`curl --max-redirs 0 .../simple/<dep>/` → 302) stays authoritative long after the
      merge: publishing needs a separate `main` dispatch, and for a heavy package that run
      itself takes hours (pyarrow's is a 24h-timeout Arrow C++ build). Read the *publish
      run's* status, not the PR's `mergedAt`, before deciding a blocked port can be
      unblocked.

163. **A maintainer hold that *names* a condition is an instruction to come back and
    re-test it, not a permanent park (the positive case gotchas 48/80/158 leave out).**
    Those three all push one way — a cancelled run is a stop signal, an ordinary push
    restarts the matrix, edit the description but do not commit — which makes it easy to
    resume a held port, confirm it is still held, and hand it back untouched forever. Read
    what the hold actually says first. "Let's wait for `<dep>` to be available and we can
    enable that dependency" is a *conditional* hold with a checkable trigger and a named
    follow-up, and one `curl --max-redirs 0 https://pypi.riseproject.dev/simple/<dep>/`
    (gotcha 30) settles whether it still binds. When it has cleared, doing the thing the
    maintainer named is the work — including the push that re-fires `pull_request: paths`,
    because that build is the point rather than collateral damage. An *unconditional* hold
    ("waiting for dependencies to be available before trying to enable it further", with no
    dependency that can land) is gotcha 80 and stays binding.
    - **Check the condition per interpreter, not just per name.** The dep has to cover the
      tags your matrix builds; gotcha 84's per-tag registry read is the same command.
    - **`PIP_NO_DEPS=1` is the standing marker of such a hold.** Gotcha 122 introduces it
      for a runtime dependency with no riscv64 wheel *and* no sdist, and says in as many
      words that nothing about the port changes when the dependency lands — so when it does,
      the whole shape comes back out: the env var, the `before-test` that hand-staged what
      the wheel install could not resolve, and the `--ignore`/`--noconftest` that skipped
      the tests reaching it. Grep a resumed port for `PIP_NO_DEPS` before anything else.
    - **The payoff is usually much larger than the diff.** Deleting ten lines here took the
      suite from 2 tests to 12 and, more to the point, from "the extensions import" to
      actually running the model-loading path the package exists for. Quote the before/after
      counts in the PR: a reviewer cannot otherwise tell a re-enabled dependency from a
      cosmetic change.
    - **Settle it off-target first, exactly as if it were a new port.** Upstream's released
      wheel for *any* platform plus the checkout's tests reproduces the full suite on your
      own host in seconds (gotcha 52), so you learn which tests the dependency unlocks, and
      that they pass, before spending a queued riscv64 cycle.

173. **`gh pr list --state open --head <pkg>` does not see a *merged* PR, so a finished
    port reads as unstarted work — check `--state all` and the registry first (the
    pillow-heif case).** The standard resume check looks for an open PR on the package's
    branch. A port that has already landed answers `[]`, while everything else on the
    machine still looks mid-flight: the local branch exists, the worktree is still there at
    its pre-merge commit, and `git log` in it shows a normal-looking WIP commit. Starting
    over from that state duplicates a merged workflow and, if it gets as far as a second
    `main` dispatch, re-uploads files GitLab already has (`HTTPError: 400 Bad Request`,
    after a full multi-hour build). Three cheap calls settle it before any research:
    ```bash
    gh pr list --state all --search <pkg> --json number,state,headRefName,url
    curl -s -o /dev/null -w '%{http_code}\n' --max-redirs 0 https://pypi.riseproject.dev/simple/<pkg>/
    git log --oneline origin/main -- .github/workflows/build-<pkg>.yml
    ```
    A `200` from the registry plus a merged PR means the work is done including the publish
    dispatch; verify the post-merge bookkeeping (issue, `closingIssuesReferences`, project
    Status) rather than the port.
    - **An `origin/github-actions/add-doc-for-<pkg>` branch is the strongest single tell**,
      and it shows up in a plain `git branch -a | grep <pkg>` before you have asked GitHub
      anything: only `_publish-wheel.yml` creates it, and only on a run whose ref was `main`.
      Its existence proves the wheels reached the registry. The matching `docs: add <pkg>`
      PR is the maintainer's to merge, not yours.
    - **`docs/packages/<pkg>.yaml` missing from `main` is not evidence the port is
      incomplete** — it arrives through that separate docs PR, so it lags the wheels by
      however long the maintainer takes.
