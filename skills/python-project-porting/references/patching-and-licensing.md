## Patching a project

Patching is decided case by case and reviewed as such — test as much real functionality as
possible rather than patching failures away. A patch is justified when the failure is:

- in a narrow part of the module, or dependent on external resources (large downloads);
- caused by software unavailable on riscv64;
- an artificial test limitation (a fixed timeout, say) rather than a real defect;
- from build scripts calling host tooling absent on the runners or in the riscv64 manylinux
  image (`apt` vs `dnf`);
- a missing LICENSE the project or a dependency requires (see Licensing below).

Mechanics: put the patch under `patches/<pkg>/<version_tag>/`, add a `git apply` step before
the build/test step, document the change on the package's docs entry, and give every patch an
`Upstream-Status:` tag — `ci_scripts/check_patch.py` enforces its presence on PRs. Extra
detail in the commit message beyond the tag pays for itself at maintenance time. The five
valid types:

| Type | Use when | Must include |
|---|---|---|
| `Issue` | build/test found a bug, reported upstream | link to the issue |
| `Submitted` | fix sent upstream, carried until merged + released | link to the PR/commit |
| `To upstream` | needs upstreaming, but submission is blocked | why it's blocked |
| `Inappropriate` | needed for riscv64/our infra, irrelevant upstream | short reason |
| `Backport` | already fixed in a later upstream release | link + description |

## Licensing and GPL sources

RISE distributes these wheels, so licence compliance is ours. Check two things per port:

- the built wheel carries the LICENSE file(s) from the upstream source;
- if it ships statically or dynamically linked libraries from other projects, their licence
  requirements are met too.

If either fails, patch the build (above) and send the fix upstream as well.

When a build links GPL components that come from **our build environment** rather than the
project — most often the `gcc` baked into the manylinux_riscv64 image — we must make those
sources available permanently, not just for CI's artifact retention window. Add a
`gpl_sources` job beside `build_wheels` using the `collect-gpl-sources` action, give it the
**same pinned `MANYLINUX_RISCV64_IMAGE`** the build used (otherwise the sources don't
correspond to the toolchain that produced the wheels), add it to the publish job's `needs:`,
and pass the artifact through:

```yaml
gpl-sources-artifact: <pkg>-<version>-gpl-sources
gpl-sources-release-tag: <pkg>-v<version>
gpl-sources-description: gcc
```

`publish-wheels` attaches the tar to a GitHub Release (creating it if needed) and hands the
download URL to `update_doc.py`, which renders it as that version's `comment:` — no manual
docs edit. `build-numpy.yml` is the complete example.

