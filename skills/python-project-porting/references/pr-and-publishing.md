## After a PR is merged (the maintainer merges, not you)

Merging pushes the pending `- version:` entry to `main`, and the workflow's `push` trigger
builds and publishes it — **do not dispatch anything**. Four steps remain, all scriptable —
`.git/pw-postmerge.py <pr> <pkg>` does them and is idempotent (`--no-trigger` is now the only
mode that makes sense):

1. **Check the publish**: `gh run list --workflow build-<pkg>.yml --branch main --limit 3`
   must show the `push` run; when it is green, the docs PR (`github-actions/update-doc`) holds
   the version's `tag:`/`files:`. A dispatch is only for a *re*build:
   `gh workflow run build-<pkg>.yml --ref main -f version=<glob>` re-releases every matching
   version, so never fire one while the `push` run is still going. Only a run whose ref is
   `main` publishes; every other ref dry-runs. Confirm afterwards with
   `curl -s -o /dev/null -w '%{http_code}' --max-redirs 0 https://pypi.riseproject.dev/simple/<pkg>/`:
   **200 means we host it, 302 means we do not** (gotcha 30). Do not follow the redirect and grep
   for `riscv64` — the redirect lands on PyPI, so any package whose upstream ships riscv64 wheels
   (hypothesis' abi3 ones, say) reads as already published when it is not.
2. **Issue**: one titled exactly `<pkg> riscv64 support`, label `wheel`, body in the
   `.github/ISSUE_TEMPLATE/package-request.yml` form shape. **Search before creating** —
   146 already exist, titles are not always the PyPI name (`SGLang`, `LibCST`, `PyNaCl`), and
   duplicates are already a problem (bcrypt has four). Match on a normalised name, case-insensitively,
   and when several match, link the **oldest** — that is what the repo already does (#82, #84, #94).
3. **Development link**: PR -> issue. A closing keyword in the PR body also works, but for an
   already-merged PR use the mutation the Development panel uses:
   `addCloseIssueReferences(input:{issueId:..., pullRequestIds:[...]})`. Read it back via the PR's
   `closingIssuesReferences`.
4. **Project**: add the issue to Projects > *Python Wheels* (`PVT_kwDOCRlTBM4BbcwJ`) and set
   **Status** (`PVTSSF_lADOCRlTBM4BbcwJzhWNMvs`) to *Available in RISE PyPI*
   (option `47fc9ee4`; the others are *Todo* `f75ad846` and *Available Upstream* `98236657`).

Needs `project` scope on the gh token (`gh auth refresh -h github.com -s project`) on top of
`repo`/`workflow`. PR #390 <-> issue #405 is the reference pair to diff a new one against.

## PR title

Exactly `<pkg>: Add version <ver>` — matches the existing merged-PR convention (e.g. "iminuit:
Add version 2.33.0", "statsmodels: Add version 0.15.0"). Use the wheel version string as it
appears in `docs/packages/<pkg>.yaml` (so `+cpu`/local-version suffixes are kept, e.g. "vllm:
Add version 0.29.0+cpu"). No other wording ("add riscv64 wheel build", "build N wheels for
riscv64", etc.) — set/fix the title at creation time, not just the body.

## PR description template

Use this verbatim. Median merged-PR description is 358 words; this should land at 100-200.
Short sentences. No process narration, no "what I tried", no hyperbole.

```markdown
* **Package**: `<pkg>`
* **Version**: `<version>`
* **Source**: <repo url>
* **Docs**: <home url>

<What it compiles, one sentence.> Upstream publishes no riscv64 wheel.

Mirrors [upstream's `<workflow>.yml`](<link>).

**Differs from upstream**
- <what> - <why>

**Matrix**: <only if not cp312/cp313/cp314/cp314t - say which and why>

**Testing**
- same as upstream

**License**: OK

**Patches**
- `0001-foo.patch` - Backport [<link>]. <What breaks without it.> <Reproduces on x86 / riscv64-only.>

Built on cp312; <N> passed, <M> skipped.
```

Rules:
- **Lead**: one sentence on what is compiled, one on the gap. The bullets carry name/version.
- **Differs from upstream**: the highest-value section. Overridden `[tool.cibuildwheel]` keys, dropped
  musllinux, added `dnf` packages, image override. Nothing else differs -> "Nothing beyond the riscv64 image."
- **Matrix**: omit the line entirely when it is the default four. Otherwise name the blocking dependency.
- **Testing**: "same as upstream", or bullets of the divergences only - deps added/removed/pinned,
  deselected tests, `test-sources` staging. One reason each. Never describe the method.
- **License**: a check mark when nothing third-party is vendored. Otherwise EXACTLY ONE sentence: what
  ships and under what licence. Mention GPL **only when it is GPL** - silence means it is not. Never
  describe how the licence reaches the wheel - not the `before-all` step, not the glob, not the
  assertion. "Wheel bundles libfoo (GPL-2.0) and libbar (MIT); upstream ships no licence text for them,
  so the build adds it." is the whole section.

Hard length limits: whole description 100-200 words; each **Differs from upstream** bullet one line
under 20 words; lead paragraph two sentences; **License** one sentence; **Patches** one line each.
Over 200 words means you are narrating.

Explain WHAT, never HOW - the diff shows how. Delete any sentence that names a cibuildwheel variable
to explain a mechanism, describes a post-build assertion, or opens with "Note that" / "Importantly" /
"Crucially".
- **Patches**: omit when there are none. One line each: filename, `Upstream-Status` + link/reason, what
  breaks without it, whether it reproduces off riscv64.
- **Last line**: counts only.

Never include: `actionlint`/YAML-parses lines, the publish dry-run, `gotcha N` references, the build
shape (it is in the diff), or any debugging history. Do not hard-wrap (see PR / CI conventions).

## PR / CI conventions

- **Never change a PR's draft status.** A draft is a deliberate hold — usually the port is
  finished and green but depends on a package that is not on the registry yet. Green checks
  are not a reason to mark it ready; the maintainer flips it when the dependency lands. Only
  do it when explicitly asked for that PR.

- **Never hard-wrap a PR description.** Write each paragraph and each bullet as one long
  line and let the GitHub UI wrap it; manual line breaks reflow badly at any other width.
  This applies to the PR body only — workflow YAML and patch commit messages still wrap.
- `pr-checks.yml` rejects commits starting with `revertme`/`revert me`/`DO NOT MERGE`,
  lints every changed `docs/packages/*.yaml` (a `build-<pkg>.yml` without one fails),
  and validates `Upstream-Status:` headers in added/modified patches under `patches/`.
- Sanity that the `publish` job **dry-ran** on your PR branch (grep its log for
  "Dry run (not on main branch …)"); it should list the wheels it *would* upload
  without uploading.
- **Merging is what publishes.** `_publish-wheel.yml` only does the real thing
  (immutable GitHub Release and docs PR) when the run's ref is `main`; on any other
  ref it prints a dry run — resolved artifacts, release details, and the branch/PR title
  `update_doc.py` would have used. That is deliberate: only reviewed, merged workflows push
  packages. The merge's push to `main` runs the workflow for every still-pending version;
  nothing needs to be re-triggered by hand.

