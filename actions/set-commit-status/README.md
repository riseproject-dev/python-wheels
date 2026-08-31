# set-commit-status

Attaches a commit status to the PR head for builds kicked off via
`workflow_dispatch` (e.g. `Trigger: <pkg>:<version>` directives dispatched by
`pr-trigger.yml`). Such runs aren't auto-linked to the PR the way a
`pull_request` check is, so this surfaces them in the PR checks list.

A native JS action with `pre`/`main`/`post` hooks: `pre` sets `pending`, `post`
derives the job outcome and sets `success` / `failure` / `error`. One `uses:`
line covers both ends. On any event other than `workflow_dispatch` it's a no-op.

## Usage

Add as the first step of the wheel-building job, and grant the job
`statuses: write` (to set the status) and `actions: read` (the post step reads
this run's job conclusions):

```yaml
permissions:
  contents: read
  statuses: write
  actions: read

# ...
    steps:
      - name: Report build status to the PR
        if: ${{ github.event_name == 'workflow_dispatch' }}
        uses: riseproject-dev/python-wheels/actions/set-commit-status@main
        with:
          context: ${{ github.workflow }} / ${{ strategy.job-index }}
```

`context` is **required** and must be unique per matrix leg: statuses on the same
commit that share a context overwrite each other. `strategy.job-index` works for
every matrix shape; a matrix var (e.g. `${{ matrix.python }}`) reads nicer where
one exists.

## Inputs

| Name | Required | Default | Notes |
|------|----------|---------|-------|
| `context` | yes | — | Status label; unique per matrix leg. |
| `token` | no | `github.token` | Needs `statuses: write` (+ `actions: read` for post). |
| `sha` | no | `GITHUB_SHA` | Tip of the dispatched ref = PR head. |
| `target-url` | no | this run's URL | Where the status links. |
| `description` | no | — | Short text next to the check. |

## Developing

Source is TypeScript under `src/`; the runtime loads the committed bundles under
`dist/`. After editing `src/`, rebuild and commit the bundles:

```sh
npm ci
npm run build   # ncc -> dist/{pre,main,post}/index.js
```
