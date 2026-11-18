# Native artifact compatibility patch for gh-aw v1.2.2

Approved by the operator after investigator run 44415024119 failed native
artifact delivery. Base source: github/gh-aw tag v1.2.2, commit
`399a445fe2d8926c616b54b1b82a16b5b2be4445`.

## Why

`upload_artifact.cjs` constructs a target containing the native repository
ID and worker run ID, then authorizes it as an ordinary resource effect.
Ordinary targets require matching run IDs in immutable Work selectors.
The dispatcher cannot know a future worker run ID when admitting Work.

The handler already resolves the native repository via the GitHub API.
The patch wraps the native upload in `withClaimResourceEffects`, gh-aw's
existing protected native-target frame. That frame authenticates the Claim,
checks immutable repository selectors and the exact original dispatch/run
binding, and authorizes the concrete target before calling the artifact client.
It does not change general resource-scope validation.

Unchanged: durable Completion requirement, original Claim and factory fences,
repository-ID checks, immutable Work scope, original native run binding,
closed effect channels, private in-process delivery receipt, independent
artifact ID/name/run/digest/size readback, and verified Result publication.
No credentials, scheduler changes, generic artifact fallback, or direct pushes.

## Installation

The worker and investigator use `jobs.safe_outputs.pre-steps`, a supported
compiler hook, immediately after runtime setup and before artifact downloads
or handler loading. They check out trusted code at `github.sha` with no persisted
credentials and run `upstreaming/gh_aw_compat.py` against the flat runtime modules.
The installer checks the original handler SHA-256, applies only
`native-artifact.patch`, and checks the exact resulting SHA-256. Unknown source,
symlink, failed application or unexpected output aborts the job. Reapplication
of the exact patched file is idempotent.

Compiler-generated lock files are never edited by hand. The gh-aw release,
setup action and CLI stay pinned to v1.2.2.

## Tests

```sh
python3 -m unittest upstreaming.tests.test_gh_aw_compat
sh upstreaming/gh-aw-compat/check.sh
```

The second command fetches the pinned source and locked test dependencies,
applies the exact runtime patch, and runs upstream's native upload and
resource-scope tests. All native upload tests now use an immutable repository
selector without a future run ID. Additional tests reject a mismatched
repository ID, explicit foreign run selector and changed runtime run ID before
upload. Existing tests reject foreign Claims, cancelled Claims, reused factories,
closed channels and every altered artifact metadata field. All APIs and uploads
are mocked. No remote state is changed.

Local result: 109 tests pass (30 artifact tests, 79 resource-scope tests).
Live end-to-end validation is still required; this result alone does not prove
that the pipeline publishes or that numpy CI runs.

Two companion integration corrections use the actual v1.2.2 behavior:

- The validating CLI replay emits JSON on stderr. The reader accepts one complete
  projection from stdout or stderr only after a successful exit.
- The native safe-output tool takes `path`, not a name override. The verified
  artifact suffix is `upstreaming-out`, matching the uploaded directory. The
  exact artifact ID, Claim/run binding and digest checks are unchanged.

The old failed Work has Completion but no Result and a pending delivery barrier.
This patch does not rewrite that history or authorize replay of its effects.
Recovery must use supported queue operations and independently verified state,
not fabricated receipts or a reset queue.

## Licensing

The patch, upstream handler fixture, and adapted upstream regression test are
based on GitHub's MIT-licensed source. Its copyright and license are retained
in `LICENSE`. No upstream issue or PR has been opened; that is a separate remote
action requiring authorization.
