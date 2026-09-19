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
- **A port PR/branch must touch only `.github/workflows/`, `docs/packages/<pkg>.yaml` and
  `patches/<pkg>/<version>/`** — never `skills/`, `ci_scripts/`, or `.queue.yml` (those are
  main-only, per the bullet above). This has been violated repeatedly: an agent researching
  a port legitimately finds a new gotcha or writes a helper script, and it rides along in the
  same commit as the port itself instead of going to `main` separately. Run
  `ci_scripts/check_port_pr_scope.sh --branch` before your final push on any non-`main`
  branch to catch it. Better: install it as a local pre-commit hook once per clone/worktree so
  it catches the mistake immediately instead of at push time —
  `git config core.hooksPath ci_scripts/git-hooks` (this setting lives in `.git/config`, not
  in the tracked tree, so run it again in any worktree that doesn't have it yet;
  `git config --get core.hooksPath` shows whether it's already set).

- **Pushing workflow files needs `workflow` scope** on the gh token, else the push is
  rejected ("refusing to allow an OAuth App to create or update workflow … without
  `workflow` scope"). Fix: `gh auth refresh -h github.com -s workflow` (interactive).
- `origin` (`riseproject-dev/python-wheels`) is canonical; there is no separate
  `upstream` remote. Branch from `origin/main`.
- Use `gh` extensively for anything requiring access to GitHub.

