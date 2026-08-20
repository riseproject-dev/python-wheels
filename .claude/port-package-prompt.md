Port a new package to this repo (riscv64 wheel → pypi.riseproject.dev). Follow
the porting playbook, working process, and gotchas in CLAUDE.md — that's the
source of truth; everything below is just this package's coordinates.

Create the branch and the worktree first then proceed with research.

Package to port:
- Name (PyPI distribution):   <pkg>
- Version/tag to build:       <version>          # latest stable unless told otherwise
- Source repository:          <github url>
- PyPI page:                  https://pypi.org/project/<pkg>/
- Project homepage/docs:      <home url>
- Upstream build/release docs: <url to their "building wheels/sdist" docs, if any>

Notes specific to this package (optional — delete if none):
- <e.g. native deps it needs, unusual build system, tests not in sdist, etc.>

Do the full loop end to end: branch + worktree, add build-<pkg>.yml, validate
locally, push, open the PR, then watch CI and iterate until every matrix job is
green and publish dry-runs cleanly. Wire up real testing the way upstream tests
its own wheels. When it's working, fold any new project-agnostic learnings back
into CLAUDE.md.
