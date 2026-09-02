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

- **Pushing workflow files needs `workflow` scope** on the gh token, else the push is
  rejected ("refusing to allow an OAuth App to create or update workflow … without
  `workflow` scope"). Fix: `gh auth refresh -h github.com -s workflow` (interactive).
- `origin` (`riseproject-dev/python-wheels`) is canonical; there is no separate
  `upstream` remote. Branch from `origin/main`.
- Use `gh` extensively for anything requiring access to GitHub.

