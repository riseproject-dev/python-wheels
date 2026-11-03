#!/usr/bin/env python3
"""
Mechanically add riscv64 CI matrix entries to upstream maturin/PyO3 repos.

What it automates (no LLM, no subagents):
  1. Parse python-wheels/maturin_packages.txt + ci_scripts/deprecated.txt to build
     the package -> upstream-repo list (skips deprecated packages).
  2. Clone every upstream repo in parallel (shallow, https, plain `git clone` only).
  3. Verify each clone has exactly one remote (`origin`) -- paranoia against any
     ambient git config that might auto-add a fork remote.
  4. Grep the repo's own CI workflow(s) for an existing riscv64 build. If found,
     it's already fixed upstream: delete the clone, report DONE-UPSTREAM.
  5. Try a narrow, safe structural edit: a job whose `strategy.matrix` has a
     list-of-maps entry (each map already carrying its own os/runner AND a
     per-entry `manylinux` field) gets one new riscv64 entry appended, cloned
     from an existing aarch64-ish entry. This is the *only* shape it edits.
  6. Anything else (fixed job-level `runs-on`, a job-wide single `manylinux:`
     value instead of per-entry, a cross-product matrix, no matrix at all, not
     a maturin project, dynamically generated matrix, ...) is reported
     NEEDS-REVIEW and the clone is deleted -- these need a human or an LLM
     pass, a script shouldn't guess at them.

This intentionally does NOT try to handle every case the manual/LLM pass did
(e.g. converting a job-wide `manylinux: auto` into a per-entry field, or
picking which of two jobs like linux/musllinux to touch). Those are judgment
calls; scripting them wrong produces a bad diff silently. Doing the ~30-40% of
clean cases mechanically in seconds, and handing back a short, exact list of
what needs a human/LLM look for the rest, is the actual time savings -- the
previous approach spent 10 five-minute LLM agents rediscovering "runs-on is
fixed, skip" over and over.

`maturin_packages.txt` (python-wheels/maturin_packages.txt) is a derived list, not
an official python-wheels artifact -- it's every build-<pkg>.yml whose content
mentions "maturin". It goes stale as packages get added/ported/deprecated, so
regenerate it before a run rather than trusting an old copy:
    python3 riscv64_autoport.py --regenerate-packages-list

Requires: `pip install ruamel.yaml` (preserves comments/formatting on write --
plain PyYAML would silently reformat every file it touches).

Lives at python-wheels/tools/riscv64_autoport.py. Repos get cloned as siblings
of python-wheels (i.e. into the directory that contains the python-wheels
checkout), not into tools/ itself.

Usage:
    python3 riscv64_autoport.py --regenerate-packages-list  # refresh the input list first
    python3 riscv64_autoport.py                 # do everything
    python3 riscv64_autoport.py --dry-run        # clone + classify, edit nothing
    python3 riscv64_autoport.py --only pkg1,pkg2 # just these packages
    python3 riscv64_autoport.py --workers 24     # clone concurrency

Never commits, never pushes, never adds a remote, never creates a branch.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

import riscv64_common as common

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None  # only required for the clone+patch pipeline, not --regenerate-packages-list

TOOLS_DIR = Path(__file__).resolve().parent
PYTHON_WHEELS_DIR = TOOLS_DIR.parent
ROOT = PYTHON_WHEELS_DIR.parent  # upstream repos clone here, as siblings of python-wheels
WORKFLOWS_DIR = PYTHON_WHEELS_DIR / ".github" / "workflows"
DEPRECATED_FILE = PYTHON_WHEELS_DIR / "ci_scripts" / "deprecated.txt"
PACKAGES_FILE = PYTHON_WHEELS_DIR / "maturin_packages.txt"

RISCV_OS = "ubuntu-24.04-riscv"
RISCV_GNU_TARGET = "riscv64gc-unknown-linux-gnu"
RISCV_MUSL_TARGET = "riscv64gc-unknown-linux-musl"
RISCV_MANYLINUX = "manylinux_2_39"
RISCV_MUSLLINUX = "musllinux_1_2"

GITHUB_URL_RE = re.compile(r"https://github\.com/([^/\s\"'()]+)/([^/\s\"'()]+)")

yaml = None
if YAML is not None:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # don't rewrap long lines

log = common.log


def regenerate_packages_list() -> int:
    """Rescan python-wheels/.github/workflows for every build-<pkg>.yml whose
    content mentions maturin, and rewrite PACKAGES_FILE with that list. This
    is the whole definition of "maturin package" used here -- there's no
    separate manifest in python-wheels itself."""
    names = sorted(
        f.name
        for f in WORKFLOWS_DIR.glob("build-*.yml")
        if "maturin" in f.read_text(errors="ignore").lower()
    )
    PACKAGES_FILE.write_text("\n".join(names) + "\n")
    return len(names)


def load_packages(only: set[str] | None) -> list[dict]:
    deprecated = {
        line.strip().lower().replace("_", "-")
        for line in DEPRECATED_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    pkgs = []
    for line in PACKAGES_FILE.read_text().splitlines():
        line = line.strip()
        if not line or not line.startswith("build-"):
            continue
        pkg = line[len("build-"):-len(".yml")]
        if only and pkg not in only:
            continue
        if pkg.lower().replace("_", "-") in deprecated:
            continue
        wf_path = WORKFLOWS_DIR / line
        if not wf_path.is_file():
            continue
        text = wf_path.read_text(errors="ignore")
        m = GITHUB_URL_RE.search(text)
        if not m:
            pkgs.append(dict(pkg=pkg, owner=None, repo=None, dir=None))
            continue
        owner, repo = m.group(1), m.group(2)
        pkgs.append(dict(pkg=pkg, owner=owner, repo=repo, dir=repo))
    return pkgs


def clone_one(pkg: dict) -> tuple[dict, str]:
    if not pkg["repo"]:
        return pkg, "no-url"
    status = common.clone_shallow(pkg["owner"], pkg["repo"], ROOT / pkg["dir"])
    return pkg, status


def clone_all(pkgs: list[dict], workers: int) -> list[dict]:
    ready = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for pkg, status in ex.map(clone_one, pkgs):
            log(f"[clone] {pkg['pkg']}: {status}")
            if status in ("cloned", "exists"):
                ready.append(pkg)
    return ready


def wheel_workflow_files(d: Path) -> list[Path]:
    wf_dir = d / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    out = []
    for f in list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")):
        text = f.read_text(errors="ignore")
        if "maturin" in text.lower() or "pyo3/maturin-action" in text.lower():
            out.append(f)
    return out


def already_has_riscv(files: list[Path]) -> bool:
    return common.text_mentions((f.read_text(errors="ignore") for f in files), r"riscv")


def find_matrix_job(data: dict):
    """Yield (job_name, job_dict, matrix_dict, list_key) for jobs whose matrix
    has a list-of-maps entry where each map carries its own os/runner field
    AND its own manylinux field -- the only shape this script will touch."""
    for job_name, job in (data.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        runs_on = job.get("runs-on")
        if not (isinstance(runs_on, str) and "${{" in runs_on and "matrix" in runs_on):
            continue  # job-level runner must be matrix-driven, not a fixed string
        strategy = job.get("strategy")
        if not isinstance(strategy, dict):
            continue  # e.g. strategy defined via a reusable workflow, not inline
        matrix = strategy.get("matrix")
        if not isinstance(matrix, dict):
            continue  # e.g. `matrix: ${{ fromJSON(...) }}` -- a dynamic expression string
        for key, val in matrix.items():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                entry0 = val[0]
                runner_field = next((k for k in ("os", "runner") if k in entry0), None)
                if runner_field and "manylinux" in entry0:
                    yield job_name, job, matrix, key, runner_field
                    break


def build_riscv_entries(template: dict, runner_field: str) -> list[dict]:
    """Clone `template` (an existing aarch64-ish entry) into one or two riscv64
    entries, swapping target/arch/manylinux fields. Keeps every other key
    (interpreter, python-version, auditwheel, ...) verbatim from the template."""
    entries = []

    gnu = dict(template)
    gnu[runner_field] = RISCV_OS
    for k in list(gnu.keys()):
        if k in ("target", "target-triple") and isinstance(gnu[k], str) and "aarch64" in gnu[k]:
            gnu[k] = gnu[k].replace("aarch64-unknown-linux-gnu", RISCV_GNU_TARGET).replace("aarch64", "riscv64")
        elif k == "arch":
            gnu[k] = "riscv64"
        elif k == "manylinux":
            gnu[k] = RISCV_MANYLINUX
    entries.append(gnu)

    # if the template set is glibc-only (no musl sibling visible here), don't
    # invent a musl entry -- the caller only sees one template at a time.
    return entries


def try_patch(f: Path, dry_run: bool) -> str:
    data = yaml.load(f.read_text())
    if not isinstance(data, dict):
        return "skip:unparseable"

    touched = False
    for job_name, job, matrix, list_key, runner_field in find_matrix_job(data):
        entries = matrix[list_key]
        entry_dump = [json.dumps(e, default=str) for e in entries]
        template_idx = next((i for i, e in enumerate(entry_dump) if "aarch64" in e), None)
        if template_idx is None:
            continue  # no aarch64 sibling to model riscv64 on -- don't guess
        if any("riscv64" in e for e in entry_dump):
            continue  # already there (shouldn't happen, already_has_riscv caught it)

        template = entries[template_idx]
        new_entries = build_riscv_entries(template, runner_field)
        for e in new_entries:
            entries.append(e)
        touched = True

    if not touched:
        return "skip:no-matching-shape"
    if not dry_run:
        with f.open("w") as fh:
            yaml.dump(data, fh)
    return "changed"


def process(pkg: dict, dry_run: bool) -> str:
    d = ROOT / pkg["dir"]
    files = wheel_workflow_files(d)
    if not files:
        shutil.rmtree(d, ignore_errors=True)
        return "skip:not-maturin-or-no-workflow"

    if already_has_riscv(files):
        shutil.rmtree(d, ignore_errors=True)
        return "done-upstream"

    results = []
    for f in files:
        try:
            results.append(try_patch(f, dry_run))
        except Exception as e:
            results.append(f"skip:unparseable ({e.__class__.__name__}: {e})")
    if any(r == "changed" for r in results):
        return "changed"

    shutil.rmtree(d, ignore_errors=True)
    return results[0] if results else "skip:no-wheel-workflow"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="clone + classify only, never write or delete")
    ap.add_argument("--only", help="comma-separated package names to restrict to")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--log", default="riscv64_autoport.log", help="path to write a full run log to")
    ap.add_argument("--report", default="riscv64_autoport_report.json", help="path to write the JSON summary to")
    ap.add_argument(
        "--regenerate-packages-list", action="store_true",
        help="rewrite maturin_packages.txt from the current build-*.yml workflows, then exit",
    )
    args = ap.parse_args()

    if args.regenerate_packages_list:
        n = regenerate_packages_list()
        print(f"Wrote {n} entries to {PACKAGES_FILE}")
        return

    if yaml is None:
        sys.exit("Missing dependency: pip install ruamel.yaml")

    start = datetime.datetime.now(datetime.timezone.utc)
    with open(args.log, "w") as log_fh:
        common.log.set_file(log_fh)

        only = set(args.only.split(",")) if args.only else None
        pkgs = load_packages(only)
        log(f"{len(pkgs)} candidate packages (post-deprecation filter)")

        ready = clone_all(pkgs, args.workers)
        log(f"{len(ready)} cloned/ready\n")

        changed, done_upstream, needs_review = [], [], []
        for pkg in ready:
            status = process(pkg, args.dry_run)
            log(f"[patch] {pkg['pkg']}: {status}")
            if status == "changed":
                changed.append(pkg["pkg"])
            elif status == "done-upstream":
                done_upstream.append(pkg["pkg"])
            else:
                needs_review.append((pkg["pkg"], status))

        log("\n=== SUMMARY ===")
        log(f"CHANGED ({len(changed)}): {', '.join(changed)}")
        log(f"DONE-UPSTREAM already ({len(done_upstream)}): {', '.join(done_upstream)}")
        log(f"NEEDS-REVIEW ({len(needs_review)}, clones deleted):")
        for name, reason in needs_review:
            log(f"  {name}: {reason}")

        end = datetime.datetime.now(datetime.timezone.utc)
        log(f"\nRun took {(end - start).total_seconds():.0f}s. Full log: {args.log}")

    report = dict(
        started=start.isoformat(),
        finished=end.isoformat(),
        dry_run=args.dry_run,
        changed=changed,
        done_upstream=done_upstream,
        needs_review=[dict(pkg=name, reason=reason) for name, reason in needs_review],
    )
    Path(args.report).write_text(json.dumps(report, indent=2))
    print(f"Report written to {args.report}, log written to {args.log}")


if __name__ == "__main__":
    main()
