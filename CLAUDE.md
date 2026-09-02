# CLAUDE.md — python-wheels

## Porting a package to riscv64

To add a package's riscv64 wheel build to this repo (published to `pypi.riseproject.dev`),
use the **`python-project-porting` skill**. It holds the full playbook: the working loop, the
hard rules, the anatomy of a `build-<pkg>.yml`, ~186 gotchas, and the patching/licensing/PR
steps.

- Entry point: [`skills/python-project-porting/SKILL.md`](skills/python-project-porting/SKILL.md)
  (also at `.claude/skills/python-project-porting/` for auto-discovery). Read it first — it is
  the navigator and points to everything else.
- Depth lives in `skills/python-project-porting/references/`:
  - `gotchas-index.md` + the `gotchas/` directory — the numbered gotchas, split by theme.
    Skim the index before starting a port; it routes by topic and by number.
  - `workflow-anatomy.md` — anatomy of a `build-<pkg>.yml`.
  - `patching-and-licensing.md` — patch mechanics, `Upstream-Status:` types, GPL sources.
  - `pr-and-publishing.md` — post-merge publish/issue/project steps, PR template, PR/CI conventions.
  - `environment-and-auth.md` — where files may go, commit identity, token scopes.

Gotchas are cited across the repo — including in `build-<pkg>.yml` comments — as **"gotcha N"**
(sometimes "CLAUDE.md gotcha N"). Resolve any such N through the number→file table in
`skills/python-project-porting/references/gotchas-index.md`, then
`grep -n '^N\. ' skills/python-project-porting/references/gotchas/<file>` (or grep the whole
`gotchas/` directory).
