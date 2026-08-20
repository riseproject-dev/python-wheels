Port a new package to this repo (riscv64 wheel → pypi.riseproject.dev). Follow
the porting playbook, working process, and gotchas in CLAUDE.md — that's the
source of truth; everything below is just this package's coordinates.

Create the branch and the worktree first then proceed with research. Always work out of the worktree!

Package to port:
- Name (PyPI distribution):  <pkg>   pyarrow
- Version/tag to build:      <ver>   25.0.1
- PyPI page:                 <pypi>  https://pypi.org/project/pyarrow/
- Source repository:         <repo>  https://github.com/apache/arrow
- Project homepage/docs:     <home>  https://arrow.apache.org/docs/python/

Do the full loop end to end: branch + worktree, add build-<pkg>.yml, validate
locally, push, open the PR, then watch CI and iterate until every matrix job is
green and publish dry-runs cleanly. Wire up real testing the way upstream tests
its own wheels. When it's working, fold any new project-agnostic learnings back
into CLAUDE.md.
