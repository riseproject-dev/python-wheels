## Environment / auth notes

- **Never write outside the repository.** Worktrees go in `.claude/worktrees/<pkg>`, scratch
  files in `.git/pw-scratch/<pkg>`, local lock state in `.git/pw-locks/`. No files in `$HOME`,
  `~/.local/bin`, `/tmp`, or sibling directories, and **no installing software** on the host
  (brew/apt/dnf/npm/pip). If you think you need either, ask first.
- **A port adds files only under `.github/workflows/` and `patches/<pkg>/<version>/`.**
  Never create a `ci/` directory, and never add a helper script, Dockerfile, or test file
  anywhere else in the repo — not for a build step, not for a smoke test, not "just this
  once" because the content is long. Anything a job needs that is not a patch is **written
  by the workflow at run time** from a `run:` heredoc (gotcha 7): into `$RUNNER_TEMP` for a
  docker build context, or into the upstream checkout for something cibuildwheel must carry
  into the container (`{project}/<name>` then names it). This has been asked for three times
  — `ci/memray`, `ci/pyogrio`, `ci/pyroscope-io` were each removed after the fact — so treat
  a new top-level path as a hard stop, not a judgement call. If a file genuinely cannot be
  inlined, ask before writing it.
  - Reproduce the file byte for byte when inlining: quote the heredoc marker (`<<'EOF'`) so
    nothing expands, and diff the extracted block against the original before pushing.
  - `cat >` drops the executable bit, so a script invoked by path needs `chmod +x`; one
    invoked as `bash <script>` does not. Getting this wrong costs a full image build.
- **Commit identity is `Ludovic Henry <git@ludovic.dev>`** and is already configured. Never
  pass `-c user.email`/`-c user.name` or set `GIT_AUTHOR_*`/`GIT_COMMITTER_*` — in particular
  do not use the user's address from your own session context, which is a *different*
  address. A `pre-commit` hook rejects any other identity (and any workflow adding
  `BUILD_VERBOSITY`); if it fires, fix the command, don't bypass the hook.
  - **`ci_scripts/git-identity.sh` is for CI, not for you — never run it.** It sets
    `user.name`/`user.email` to `github-actions[bot]` (or the App bot when `APP_SLUG` is set)
    so *workflow* commits are attributed to the bot. Run locally it silently rewrites
    `.git/config`, and because `git config` in a worktree writes the **common** config, it
    clobbers the identity for the shared checkout and every other worktree/agent too — the
    next commit anywhere lands as `github-actions[bot]`. Read it if you need to know what CI
    does; restore with `git config user.name "Ludovic Henry"` and
    `git config user.email "git@ludovic.dev"`, and check `git log -1 --format='%an <%ae>'`
    before pushing. The `pre-commit` hook is not always installed locally, so nothing else
    catches it.
- **Bookkeeping commits (`.queue.yml`, a new gotcha, a `ci_scripts/` fix) go straight to
  `origin/main`, never a feature branch** — but many agents do this concurrently, so use
  `ci_scripts/safe_push_main.sh` instead of a bare `git push`. It always pushes `HEAD` (a bare
  `git push origin main` pushes your local `main` branch, which may be stale, if you aren't
  literally on a branch named `main`), fetches and rebases onto the latest `origin/main` first,
  retries on a race with another agent's concurrent push, and refuses to push if `.queue.yml`'s
  package count would shrink (a signal you rebased onto a stale snapshot and are about to
  silently revert someone else's already-landed commit — this has nearly happened more than
  once). If it reports a real rebase conflict, resolve it by hand before re-running it.
  Before writing a new gotcha number, run `ci_scripts/next_gotcha.sh` (and again right before
  the final push) — concurrent agents have repeatedly collided on the same next number.
- **A single commit must never mix a package port (`.github/workflows/`,
  `docs/packages/<pkg>.yaml`, `patches/<pkg>/<version>/`) with bookkeeping (`skills/`,
  `ci_scripts/`, `.queue.yml`, anything else)** — they go to different places (the port to
  its own PR branch, bookkeeping straight to `main` per the bullet above), so a commit that
  mixes them puts the wrong half wherever it lands. This has been violated repeatedly: an
  agent researching a port legitimately finds a new gotcha or writes a helper script, and it
  rides along in the same commit as the port itself. Run `ci_scripts/check_port_pr_scope.sh
  --branch` before your final push to catch it across a whole branch's commits. Better:
  install it as a local pre-commit hook once per clone so every future commit is checked as
  you make it — `git config core.hooksPath ci_scripts/git-hooks` (this setting lives in
  `.git/config`, not the tracked tree, so it does need setting again in a clone that doesn't
  have it yet; `git config --get core.hooksPath` shows whether it's already set — but it *is*
  shared across all worktrees of one clone once set, main checkout included). The check is
  about what a commit's diff contains, not what branch you're on — a bookkeeping-only commit
  passes from any branch, including a worktree that can never literally check out `main`
  itself. One important limitation: a worktree's hook runs whatever `ci_scripts/check_port_pr_scope.sh`
  is actually committed *in that worktree's own checkout* — if the script itself has a fix on
  `main` that this worktree hasn't picked up yet (it was created before the fix, or hasn't
  merged since), the hook still runs the old logic until that worktree syncs with `main`.
- **No commit message may mention Claude or Anthropic, in any form** (`Co-Authored-By:
  Claude ...`, `Claude-Session:`, `Generated by Claude Code`, etc.) — this has leaked through
  twice from a tool's own auto-appended trailer, once all the way into a merged PR (#2151),
  because the only thing checked was the PR body/comment footer, not the commit message
  itself. The same `core.hooksPath` install above also wires up a `commit-msg` hook
  (rejects it before the commit is even made) and a `pre-push` hook (rescans every commit
  about to be pushed, in case one was made before the hook was installed or with
  `--no-verify`) — both call `ci_scripts/check_no_ai_attribution.sh`. `pr-checks.yml` runs
  the same script over every commit in a PR as a second, clone-independent net, **and
  separately over the PR's own title and body** — a `create_pull_request` tool call can
  append its own "Generated by ..." footer to the *description* without touching any commit
  message at all (a real leak caught this way on the chalkpy-rs port, after the commit-message
  checks above were already all green), so the commit-scanning checks alone don't cover it.
  None of this touches file/diff content, only commit messages and the PR title/body: a patch
  can legitimately carry a real person named Claude as an upstream byline, and there is no way
  to tell that apart from an AI attribution trailer from content alone.

- **The docker daemon is shared with every other agent on this host.** Never stop or kill
  containers by an image filter — `docker ps -q --filter ancestor=quay.io/pypa/manylinux_2_39_riscv64
  | xargs docker kill` matches *every* concurrent port's local rehearsal, because they all run in
  the same handful of manylinux/musllinux images. One such sweep killed a sibling agent's
  `cibuildwheel-*` container mid-rehearsal, and there is no way to restart someone else's job.
  Start your own with an explicit `--name <pkg>-<what>`, stop only that name, and read
  `docker ps --format '{{.Names}}'` before any cleanup. The same applies to `docker system prune`
  and to pulling: an image another agent is mid-pull on is shared state too.

- **Pushing workflow files needs `workflow` scope** on the gh token, else the push is
  rejected ("refusing to allow an OAuth App to create or update workflow … without
  `workflow` scope"). Fix: `gh auth refresh -h github.com -s workflow` (interactive).
- `origin` (`riseproject-dev/python-wheels`) is canonical; there is no separate
  `upstream` remote. Branch from `origin/main`.
- Use `gh` extensively for anything requiring access to GitHub.

