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
- **208** — A fresh `main` publish run finishing green does not mean
- **357** — A single combined-interpreter build job's artifact name needs to match the
- **380** — A project that splits every release into two independently-named PyPI
- **370** — `.queue.yml` lives on `main` in a checkout shared by every concurrently
- **413** — `git -C <dir> apply <glob>` hands git the *literal* glob — the shell expands
- **458** — A failed job with no log at all and its steps still `in_progress` is a dead

---

45. **A brand-new `build-<pkg>.yml` cannot be dispatched from a PR — GitHub only knows
    a workflow that has already run at least once.** `gh workflow run build-<pkg>.yml
    --ref <branch> -f version=<glob>` resolves the file name through
    `POST /repos/.../actions/workflows/{file}/dispatches`. That
    lookup only sees workflows in the repository's *registry*, and a file that has never
    produced a run is not in it: the call dies with `HTTP 404: workflow build-<pkg>.yml
    not found on the default branch`, and no build ever starts.
    Not a permissions or ref problem — the same call succeeds for every other open port
    PR, because those workflows were registered by a run under the `pull_request` trigger
    that `workflows: rework triggering behaviour` (#364) removed.
    - **Check registration rather than guessing:** `gh api
      "repos/riseproject-dev/python-wheels/actions/workflows?per_page=100" --paginate
      -q '.workflows[].path' | grep <pkg>`. Living on `main` is sufficient but not
      necessary — `build-scipy.yml`/`build-shapely.yml` are listed while existing only on
      their PR branches.
    - **Nothing inside the port fixes it**, so don't burn cycles re-dispatching or
      re-pushing: only a first run registers a workflow, and no trigger the file is
      allowed to declare can produce one except `pull_request: paths`. Validate everything
      locally, open the PR with both files, and let that first `pull_request` run register
      the workflow — it also builds every pending version, so a dispatch is rarely needed.

54. **A `build-<pkg>.yml` that is not yet on the default branch cannot be
    `workflow_dispatch`-ed at all, so a brand-new package needs the `pull_request:
    paths` trigger to get its first CI run.** GitHub's dispatch API resolves a workflow
    by its file name *on the default branch*; for a file that only exists on your PR
    branch it answers `HTTP 404: workflow build-<pkg>.yml not found on the default
    branch`, and `gh api repos/<repo>/actions/workflows` does not list it (no id has
    been assigned), so `gh workflow run --ref <branch>` fails and no build ever
    starts. The `pull_request: paths` trigger is what registers the workflow: once one
    run exists the workflow gets an id, and `workflow_dispatch` on the branch starts
    working (that is why an in-flight package PR shows a `pull_request` run first and
    `workflow_dispatch` runs only after). Keep all three triggers on a new workflow, as
    every workflow on `main` does — the `workflow_dispatch`-only rework (#364) was reverted
    by #391 for exactly this reason. To build a *different version*, declare it in
    `docs/packages/<pkg>.yaml`: the next `pull_request` run builds every pending entry.

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
    follow-up).** Gotcha 48 says a human-cancelled run is a stop signal and not a flake,
    but it only warns against re-dispatching.
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
    no run at all and left the green `Build ... (riscv64)` run from the previous day as
    the newest one on the branch.
    - **So when resuming an older port (gotcha 65), bring the description up to the
      current template even when you must not push.** Convention drifts in *both* files:
      check the branch's `on:`/header against a recently merged sibling **and** the PR body
      against the PR-description template (`references/pr-and-publishing.md`), which may have
      been added or rewritten after the PR was opened.
    - **Verify the branch is genuinely undrifted before concluding there is nothing to
      push.** Being tens of commits behind `main` is not by itself drift — a port that adds
      only new files (`build-<pkg>.yml`, `docs/packages/<pkg>.yaml`, `patches/<pkg>/**`) cannot conflict, so a rebase
      buys nothing and costs a full matrix re-run. Diff the conventions, not the commit
      count.
    - **A merged dependency PR is not a landed dependency.** The registry check
      (`curl --max-redirs 0 .../simple/<dep>/` → 302) stays authoritative long after the
      merge: publishing happens in the `push` run the merge triggers, and for a heavy
      package that run itself takes hours (pyarrow's is a 24h-timeout Arrow C++ build).
      Read the *publish run's* status, not the PR's `mergedAt`, before deciding a blocked
      port can be unblocked.

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
    `main` run, creates a second release for a version that already has one (after a full
    multi-hour build). Three cheap calls settle it before any research:
    ```bash
    gh pr list --state all --search <pkg> --json number,state,headRefName,url
    curl -s -o /dev/null -w '%{http_code}\n' --max-redirs 0 https://pypi.riseproject.dev/simple/<pkg>/
    git log --oneline origin/main -- .github/workflows/build-<pkg>.yml
    ```
    A `200` from the registry plus a merged PR means the work is done including the publish;
    verify the post-merge bookkeeping (issue, `closingIssuesReferences`, project Status)
    rather than the port.
    - **A `docs/packages/<pkg>.yaml` entry that still has no `tag:`/`files:` on `main` is
      not evidence the port is unpublished** — the release metadata arrives through the
      shared `github-actions/update-doc` docs PR, which only `_publish-wheel.yml` pushes
      to, and only on a run whose ref was `main`. Read the `push` run's conclusion and
      the docs PR; the YAML on `main` lags the wheels by however long the maintainer takes.
    - **The `.queue.yml` entry is the *other* direction of the same trap: its `status`/`notes`
      are a pre-port research snapshot, not live state, so a fully published package can still
      read `status: porting`, `pr: null` with a note asserting "no riscv64 on PyPI or
      pypi.riseproject.dev".** Nothing rewrites an entry when the PR merges or the publish
      lands — only an agent does, and one that stops early (or whose push got clobbered per
      gotcha 370) leaves the entry contradicting `main` indefinitely. Never take the queue note
      as the current state of a port: settle it against `main` and the registry with 173's three
      calls first. py-ed25519-zebra-bindings 1.3.0 was already merged (#1241), released and live
      on the registry for twelve days while its entry still said `porting`; the whole "port"
      reduced to verifying the four wheels and correcting the entry.

208. **A fresh `main` publish run finishing green does not mean
    `pypi.riseproject.dev/simple/<pkg>/` is live yet — it can 404 for a while first.**
    Gotcha 30's 200-vs-302 check assumes the package is already on the registry or never
    will be; it misses a third, transient state. Right after `_publish-wheel.yml` runs on
    `main` and reports success (draft release created, "Verify release is immutable"
    green, `docs/packages/<pkg>.yaml` written), the endpoint can still answer `404` —
    tree-sitter-yaml's did, immediately after its own publish, while a same-day publish
    from two hours earlier (pyyaml-ft) was already `200`, and two more from the prior
    30 minutes (pylsqpack, opencv-contrib-python) were still `404` too. The index that
    backs `/simple/` is rebuilt on its own schedule, decoupled from the GitHub Release.
    Don't read a post-publish `404` as a failed publish and don't re-dispatch to "fix"
    it — re-running `build-<pkg>.yml` on `main` after a successful run just creates a
    second release for the same version for no reason. Confirm the publish worked from
    the run's own conclusion and the release, not from the index; a `404` a few minutes
    old is not yet evidence of anything.

357. **A single combined-interpreter build job's artifact name needs to match the
    `publish` job's `artifact-pattern` exactly — the usual `-*-` wildcard assumes a
    per-interpreter matrix and silently never matches a one-job build.** Most ports
    matrix `cp312`/`cp313`/.../`cp314t` across separate jobs, each uploading its own
    artifact tagged with the interpreter (`<pkg>-<version>-cp312-manylinux_riscv64`,
    etc.), so `_publish-wheel.yml`'s `artifact-pattern: <pkg>-<version>-*-manylinux_riscv64`
    globs across all of them. A port whose build genuinely can't be split per-interpreter
    (skia-python's single Skia compile shared across all four Pythons in one job;
    praat-parselmouth's ~1M-line vendored-Praat compile, same shape) uploads exactly
    *one* artifact with no interpreter segment — `<pkg>-<version>-manylinux_riscv64` —
    and the wildcard pattern never matches it. The build job itself goes green (wheels
    built, tests passed); only the separate `publish` job fails, with
    `SystemExit: No wheels found in dist` from `_publish-wheel.yml`'s own glob. Fix by
    dropping the `-*-` from that port's `artifact-pattern` to match the single upload
    name exactly, not by adding a fake wildcard segment to the upload. Hit identically
    on skia-python and praat-parselmouth, both single-job multi-interpreter builds.
    - **`gh run rerun --failed` will not validate this fix.** It replays the workflow
      YAML as it existed at that run's original trigger, not the branch's current HEAD
      — confirmed by inspecting a rerun's job log, which still showed the pre-fix
      `artifact-pattern`. Dispatch a fresh run (`gh workflow run` or a new commit)
      instead; for a multi-hour single-job build this means eating a full rebuild to
      re-validate just the publish-job config, since the build and publish jobs are
      not independently re-runnable once the artifact-pattern itself was wrong.

370. **`.queue.yml` lives on `main` in a checkout shared by every concurrently
    running agent, so a plain `git add .queue.yml && git commit` can silently commit
    (and thus attribute to your message) another agent's unrelated in-flight edit sitting
    in the same working tree — or worse, a *stale* full-file write from another agent can
    revert your own just-pushed change back to its old value the moment that agent's
    commit lands (observed live: an xrootd `porting` update was clobbered back to `queued`
    three commits later by a sibling agent that had started from a checkout predating the
    push).** Editing the shared worktree in place is not safe for this file. Instead, edit
    it from an ephemeral, isolated worktree checked out fresh from `origin/main` for each
    state transition:
    ```bash
    git fetch origin main
    git worktree add --detach .git/pw-scratch/<pkg>/queue-edit origin/main
    # edit .git/pw-scratch/<pkg>/queue-edit/.queue.yml, validate parseability + count
    git -C .git/pw-scratch/<pkg>/queue-edit commit -am "queue: mark <pkg> as <state>, ..."
    git -C .git/pw-scratch/<pkg>/queue-edit push origin HEAD:main
    git worktree remove .git/pw-scratch/<pkg>/queue-edit --force
    ```
    This guarantees the commit's tree is exactly `origin/main` plus your one-entry diff,
    with nothing else riding along. It does not fully close the race — another agent can
    still push between your fetch and your push (retry with a fresh fetch on rejection),
    or land a stale-based commit of their own *after* yours that reverts it the same way
    yours could have reverted theirs. **Re-read the entry back from `origin/main` after
    every push in this same session** (not just trust the push exit code) so a collision
    like the one above is caught and re-applied immediately rather than surfacing only
    at the next periodic queue.yml audit.

380. **A project that splits every release into two independently-named PyPI
    packages from one build needs two `_publish-wheel.yml` calls, not two artifact
    patterns on one call (the mlx case; see `build-mlx.yml`).** Upstream's own
    `setup.py` builds the identical C++ tree twice with different env vars
    (`MLX_BUILD_FRONTEND_PACKAGE=1` / `MLX_BUILD_BACKEND_PACKAGE=1`) to produce a thin
    per-interpreter `mlx` wheel (the nanobind bindings) and a per-platform,
    python-agnostic `mlx-cpu` wheel (the compiled `libmlx.so`) that `mlx`'s own
    `install_requires` depends on at runtime — neither one imports anything on its own.
    `_publish-wheel.yml` asserts exactly one normalized package name and one version
    across whatever `artifact-pattern` matches (`len(normalized_names) != 1 or
    len(versions) != 1` raises), so publishing both needs two separate
    `uses: $/.github/workflows/_publish-wheel.yml` jobs with disjoint patterns
    (`mlx-<ver>-cp3*-manylinux_riscv64` vs. `mlx_cpu-<ver>-manylinux_riscv64` — anchor
    each pattern so neither's prefix matches the other's artifact names), each creating
    its own `docs/packages/<pkg>.yaml` on first publish with no extra registration step.
    - **A GPL-sources job attaches to whichever wheel actually vendors the GPL library,
      not both automatically.** Here only the backend (`mlx-cpu`) wheel's `auditwheel
      repair` vendors `libopenblas`/`libgfortran`; the frontend wheel's repair step
      excludes and only relabels the platform tag (see gotcha below on that), so only
      the backend's `publish` job needs `gpl-sources-artifact`/`-description` — wiring
      it into both is harmless but adds a needless second copy of the same tarball to a
      release that ships no GPL-linked binary.
    - **Test the split for real, not per-half** — install both wheels together in the
      same environment and run a real op (e.g. `import mlx.core as mx;
      mx.eval(mx.array([1.0]) * 2)`) before trusting either wheel in isolation, since a
      backend-only or frontend-only smoke test cannot catch a packaging mismatch (an
      `RPATH`/install-location assumption, a version skew between the two) between the
      halves that only surfaces when they are installed side by side.


413. **`git -C <dir> apply <glob>` hands git the literal glob, because the shell
    expands it in the step's own cwd and `-C` only moves git — use
    `working-directory:` instead.** Symptom: a patch step that dies about 30 seconds
    into the job with `error: can't open patch
    '../python-wheels/patches/<pkg>/<ver>/00*.patch': No such file or directory` and
    exit 128, on a branch where that patch file is demonstrably committed (`git
    ls-tree -r origin/<branch> -- patches/<pkg>/` lists it).
    - **The message names a path that is correct, for a file that never existed.** A
      `run:` step starts in `$GITHUB_WORKSPACE`, and bash expands the glob there,
      before git runs at all. With no `nullglob`/`failglob`, a glob that matches
      nothing is passed through verbatim, so git receives the six characters `00*.patch`
      as a filename and only *then* resolves it relative to `-C`'s directory. The
      error therefore quotes a directory that does exist and a file name that cannot.
    - **This repo makes the mismatch invisible rather than loud.** The runner
      workspace is `/home/runner/work/python-wheels/python-wheels`, so the repo name
      doubles: `../python-wheels` evaluated from the workspace root resolves back onto
      the workspace *itself*, which exists. The glob fails quietly instead of erroring
      on a missing directory, and the relative path reads correctly in review because
      it *is* the right path — from the package subdirectory.
    - **Fix: give the shell and git one base.** For an upstream checkout under `path:
      <pkg>`, use the shape the rest of the repo already uses —
      ```yaml
      - name: Patch <pkg> source
        working-directory: <pkg>
        run: git apply ../python-wheels/patches/<pkg>/${{ env.<PKG>_VERSION }}/00*.patch
      ```
      (`build-ray.yml`, `build-tink.yml`, `build-torch.yml`, `build-labmaze.yml`,
      `build-minorminer.yml`, `build-pyicu-binary.yml`). When upstream is checked out
      at the workspace root with no `path:`, the plain `git apply
      python-wheels/patches/...` form is already correct — there is no `..` to get
      wrong. Never reach for `git -C` here.
    - **An x86_64 or local rehearsal cannot catch this class of bug at all.** The
      defect lives in the workflow's directory wiring, not in the build: a rehearsal
      that clones upstream and runs cmake by hand in a differently-shaped tree
      exercises none of it, so "built and tested on x86_64 as a rehearsal" is not
      evidence the patch step works. Anything that depends on the *runner's* layout
      (`$GITHUB_WORKSPACE`, `path:`-relative paths, `working-directory`) is only
      proven by a real CI run — budget the first riscv64 run as the test of the YAML,
      not of the code.
    - **While you are in the triggers, list `patches/<pkg>/**` alongside the workflow
      and `docs/packages/<pkg>.yaml`** in both `pull_request: paths` and `push: paths`
      (136 of this repo's 188 patched packages already do). Without it a follow-up
      commit that only edits a patch produces no run at all, which looks exactly like
      gotcha 89 and wastes a cycle on the wrong hypothesis.

458. **A failed job with *no* log at all and its steps still `in_progress` is a dead
    runner, not a failed build — and the check-run *annotations* endpoint still holds the
    dying process's message (the mini-racer V8 case).** The shape is unmistakable once you
    know it: `conclusion: failure`, every step from the one that was executing onwards left
    at `status: in_progress`/`pending`, and `GET /repos/<repo>/actions/jobs/<id>/logs`
    answering `404 BlobNotFound`. Logs are only uploaded when a job *terminates*, so their
    absence is itself the evidence — and it is not gotcha 62's volume drop, which leaves the
    steps properly `completed`. Two API calls separate them: a **sibling job in the same
    run** returns `200` for its log (so retention and permissions are fine), and the failed
    job's steps are unfinished (so it never got to upload).
    - **The one surviving artefact is the annotation, and the job id *is* the check-run
      id**: `GET /repos/<repo>/check-runs/<job id>/annotations`. It survives when the log
      does. Here it carried `Fatal glibc error: pthread_mutex_lock.c:130
      (___pthread_mutex_lock): assertion failed: mutex->__data.__owner == 0` — with
      `path: .github` and `start_line: 0`, i.e. a *job-level* annotation written as the
      runner died, not a compiler diagnostic from a step.
    - **Correlate across packages before blaming your build.** Sweep every failed job in the
      last week or two for the same shape and read its annotations — jobs with unfinished
      steps are a tiny set, so this is cheap:
      ```python
      cand = [j for j in jobs if j["conclusion"] == "failure"
              and any(s["status"] in ("in_progress", "pending", "queued") for s in j["steps"])]
      ```
      Three of 749 failed jobs over eight days had it, on three different runners and three
      unrelated packages: mini-racer (3h20m into a V8 compile), tensor-grep (11 minutes) and
      litellm — dead **7 seconds** after the job started. A 7-second death cannot be memory,
      disk or anything a build did, which retires the "the expensive build exhausted the
      runner" hypothesis (gotcha 421) in one comparison rather than one 27-hour rebuild.
    - **Then re-run, do not debug.** `POST /repos/<repo>/actions/runs/<id>/rerun-failed-jobs`
      replays only the dead job against the same merge ref, as a second attempt on the same
      run. That matters most on exactly the ports where this hurts: no push means no
      `pull_request: paths` restart (gotcha 80), no new commit on a PR whose other checks
      are already green, and the existing `timeout-minutes` ceiling is preserved.
    - **This is the missing half of gotcha 447's "read the log before concluding it is a
      wall".** When there is no log to read, the annotation plus the unfinished steps are
      the substitute — and reaching for a source fix, a parallelism cap or a parked entry
      without checking them costs a full build cycle to disprove.
