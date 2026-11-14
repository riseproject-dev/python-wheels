# riscv64 CI porting tools

Two scripts that automate (most of) the mechanical work of proposing riscv64
CI support to upstream maturin/cibuildwheel projects, as evidence for RISE's
goal of getting riscv64 wheels built by upstream instead of by `python-wheels`.

Both scripts:

- Clone upstream repos as **siblings of the `python-wheels` checkout**, not
  into this `tools/` directory.
- Only ever use `git clone --depth 1 <https-url>`, and verify the clone has
  exactly one remote (`origin`) before touching anything.
- **Never commit, never push, never add a remote, never create a branch.**
  Any change they make is left as an uncommitted working-tree diff for you to
  review, turn into a PR, or discard.
- When a repo doesn't need action (already has riscv64, or needs more
  judgment than the script applies), the clone is deleted again — you won't
  find a pile of untouched/irrelevant clones lying around afterwards.

Run them from anywhere; paths are resolved relative to this script's location,
not your current directory. They share the clone/log/riscv-detection logic
above via `riscv64_common.py` (not meant to be run on its own) — keep it next
to both scripts.

## `riscv64_autoport.py` — patch repos from `maturin_packages.txt`

Source of packages: `python-wheels/maturin_packages.txt`, filtered against
`python-wheels/ci_scripts/deprecated.txt`.

`maturin_packages.txt` is a **derived list, not an official python-wheels
file** — every `build-<pkg>.yml` whose contents mention `maturin`. It goes
stale as packages are added, ported, or deprecated, so regenerate it before a
run:

```sh
python3 riscv64_autoport.py --regenerate-packages-list
```

This rescans `.github/workflows/build-*.yml` and rewrites
`maturin_packages.txt`. It has no dependencies beyond the standard library.

Then run the actual porting pass (requires `pip install ruamel.yaml`, which
preserves comments/formatting on write):

```sh
python3 riscv64_autoport.py --dry-run        # see what it would do first
python3 riscv64_autoport.py                  # clone + patch for real
python3 riscv64_autoport.py --only fastnanoid,djade   # just these packages
python3 riscv64_autoport.py --workers 24     # clone concurrency (default 16)
```

What it does per package:

1. Clone the upstream repo.
2. If its CI already mentions `riscv`, delete the clone and report
   `done-upstream`.
3. Try one narrow, safe edit: if a job's `runs-on` is matrix-driven and the
   matrix has a list of per-platform maps that **already carry their own
   os/runner field and their own `manylinux` field**, append one new riscv64
   entry cloned from an existing aarch64-ish entry.
4. Anything else — a fixed job-wide `runs-on`, a single job-wide `manylinux:`
   value instead of per-entry, a cross-product matrix, a dynamically
   generated matrix, not actually a maturin project, etc. — is reported
   `NEEDS-REVIEW` and the clone is deleted. These need a human (or an LLM)
   look; the script deliberately doesn't guess.

Output:

- `riscv64_autoport.log` — full run log (same as stdout).
- `riscv64_autoport_report.json` — structured summary: `changed`,
  `done_upstream`, `needs_review` (with per-package reasons).

Override either with `--log` / `--report`.

## `riscv64_discover.py` — find new candidates from the PyPI dashboard

Source of packages: the RISE
[python-wheels-dashboard](https://riseproject-dev.github.io/python-wheels-dashboard/)'s
own `results.json` — the top-downloaded PyPI packages with compiled
extensions, already cross-referenced against riscv64-wheel and RISE-registry
status. No separate "top PyPI packages" list is needed; this dashboard
already is that, pre-filtered to the packages worth looking at (`css_class ==
"warning"`: has compiled wheels, no riscv64 wheel on PyPI, not yet in the RISE
registry either).

```sh
python3 riscv64_discover.py                  # top 150 candidates (default)
python3 riscv64_discover.py --limit 50
python3 riscv64_discover.py --dry-run        # classify only, clone nothing
python3 riscv64_discover.py --report report.json
```

What it does per candidate package, highest-downloaded first:

1. Resolve a GitHub repo from PyPI's JSON API (`home_page` / `project_urls`).
   No repo found → skip.
2. List `.github/workflows` via the GitHub API and grep the raw file contents
   (free — doesn't count against the API rate limit) for `maturin` or
   `cibuildwheel`. Neither found → skip, out of scope.
3. Grep the same files for `riscv` — the dashboard updates daily and can be
   stale; this catches riscv64 CI added since the last refresh.
4. Search GitHub for any PR (open, merged, or closed) mentioning `riscv` in
   that repo. If one exists, skip and report its URL/state instead of
   cloning — **don't duplicate work already in flight upstream.**
5. Otherwise, shallow-clone it for you to start a port.

Needs `gh` (GitHub CLI) **authenticated** (`gh auth status`) for usable API
and search rate limits (5000/hr core, 30/min search). Without it, the script
falls back to unauthenticated calls (60/hr core, 10/min search) — use a small
`--limit` in that case, or it will get rate-limited partway through.

Output:

- `riscv64_discover.log` — full run log (same as stdout).
- `riscv64_discover_report.json` — every cloned/skipped package and why.

Override either with `--log` / `--report`.

## Typical workflow

```sh
cd python-wheels/tools
python3 riscv64_autoport.py --regenerate-packages-list
python3 riscv64_autoport.py --dry-run
python3 riscv64_autoport.py
python3 riscv64_discover.py --dry-run --limit 50
python3 riscv64_discover.py --limit 50
```

Review every uncommitted diff before committing or opening a PR — both
scripts are deliberately conservative, but "conservative" isn't the same as
"always correct."
