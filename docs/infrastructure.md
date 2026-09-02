---
title: Infrastructure
layout: default
nav_order: 7
---

# Infrastructure

The [python-wheels](https://github.com/riseproject-dev/python-wheels) project
makes use of some supplemental infrastructure available both on GitHub, and
externally. The following sections outline these services and how to
configure/maintain them.

## RISE RISC-V Runners

For RISE-hosted builds of Python wheels and upstream submissions, the
`python-wheels` repository uses the [RISC-V
Runners](https://riscv-runners.riseproject.dev/) project. It is already enabled
for the repository; to reconfigure, see the [installation
guide](https://riscv-runners.riseproject.dev/docs/getting-started/install).

## GitHub Releases

Built wheels are stored as assets on GitHub Releases. Each successful publish
from `main` creates a new release with a normalized package-and-version title
and a unique UTC timestamp in its tag. Releases are created as drafts, populated
with all wheel and GPL-source assets, and then published.

Immutable releases must remain enabled under the repository's release settings.
Once published, a release's tag and assets cannot be changed or deleted. The
`_publish-wheel.yml` reusable workflow checks this setting before publishing and
verifies that the resulting release is immutable.

The workflow uses the repository-provided `GITHUB_TOKEN`; callers grant the
publish job `contents: write` and `pull-requests: write`. No external package
registry credentials are required.

## GitHub Pages Configuration

The `.github/workflows/website.yml` workflow handles building and deploying
documentation, including providing previews of the docs on a per-PR basis. For
this to work correctly, the following settings need to be configured under
`Settings -> Pages -> Build and deployment` in the repository:

1. `Source` should be set to `Deploy from a branch`
2. `Branch` should be set to `gh-pages` `/(root)`

When this is configured, any changes touching the `docs` folder will trigger a
docs build, where upon completion the `rossjrw/pr-preview-action` will
automatically comment on the PR with a link looking like:

```
https://riseproject-dev.github.io/python-wheels/pr-preview/pr-171/
```

Note that the `gh-pages` branch should be automatically created by the
workflows, but if not it must be created manually with an empty `.nojekyll` file
in the project root to avoid long rebuild times.
