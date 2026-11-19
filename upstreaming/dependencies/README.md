# Upstreaming dependency updates

Dependabot checks weekly:

- GitHub Actions across all `upstreaming-*.yml`, through the existing root
  `github-actions` configuration. Unrelated dependency groups are preserved.
- Pi and investigator extensions through `package.json` / `package-lock.json`.
- Stable gh-aw releases through the `github.com/github/gh-aw` requirement in
  `go.mod`. This is a release-monitoring inventory, not a Go application.
- Control Python requirements in `upstreaming/requirements.txt` (their current
  lower-bound ranges already permit latest compatible versions).

Current runtime pins are stable releases. Dependabot's normal stable-release
selection applies; the synchronization checker rejects prerelease/range runtime
pins. The mutable project-graph `:latest` tag is used as explicitly requested;
its contents are not a versioned Dependabot update.

## Handling update PRs

Dependabot does not understand gh-aw Markdown engine/extension declarations or
arbitrary release-download shell scripts. A manifest-only PR is an update
proposal, not a ready runtime upgrade. CI checks that the authored source matches
our inventory, so it cannot silently merge while the runtime stays old.

For reviewed Pi/extension upgrades:

```sh
uv run --no-project python upstreaming/dependencies/sync.py --write
/path/to/reviewed-gh-aw compile upstreaming-worker upstreaming-investigator upstreaming-dispatcher --no-check-update --approve
uv run --no-project --with-requirements upstreaming/requirements.txt python -m unittest discover -s upstreaming/tests -t .
```

The script updates only the three upstreaming Markdown engine versions and the
investigator's two extension versions. Commit `.github/workflows` changes
separately from inventory/code changes. Do not hand-edit generated locks.

For gh-aw upgrades, also review:

1. Stable release version and independently pinned binary SHA-256 values in
   `upstreaming/install_gh_aw.sh`.
2. `upstreaming/check_gh_aw.sh` and the Result reader's CLI version/behavior.
3. Whether `gh-aw-compat/native-artifact.patch` is still needed. Verify the new
   runtime's original/patched hashes and native artifact authorization and Result
   tests; remove the compatibility patch only after equivalent coverage passes.
4. Detector engine behavior and supported research sandbox configuration.
5. Regenerated locks and native worker contracts. Installed contract changes
   require supported queue policy migration, not a reset of delivery history.

Dependabot must not bump `github/gh-aw-actions/*` independently of the compiler.
That action family is ignored in the generic Actions updater; the stable gh-aw
module inventory tracks its coordinated release upgrade instead.

No updater auto-merges runtime/compiler proposals or bypasses compatibility tests.
