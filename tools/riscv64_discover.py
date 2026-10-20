#!/usr/bin/env python3
"""
Find top PyPI packages with no riscv64 wheel and no RISE-registry build, narrow
to ones built with maturin or cibuildwheel, skip any that already have riscv64
support (or an open/merged/closed PR proposing it) upstream, and shallow-clone
the rest into a workspace for porting.

Data source: the RISE python-wheels-dashboard's own results.json (same data
backing https://riseproject-dev.github.io/python-wheels-dashboard/), which is
already the top-downloaded PyPI packages with compiled extensions, ranked and
cross-referenced against riscv64-wheel/RISE-registry status. No separate "top
PyPI packages" list is needed -- this dashboard already is that, pre-filtered.

Pipeline per candidate package:
  1. Dashboard says: has compiled wheels, no riscv64 wheel, not in RISE registry
     (css_class == "warning"). Sorted by downloads, highest first.
  2. Resolve a GitHub repo from PyPI's JSON API (home_page / project_urls).
  3. List `.github/workflows` via the GitHub API; grep raw file contents
     (doesn't count against the API rate limit) for "maturin" / "cibuildwheel".
     No match -> skip (not in scope).
  4. Grep those same files for "riscv" -- dashboard updates daily and can be
     stale; catches riscv64 CI added since the last dashboard refresh.
  5. Search GitHub (any state: open/merged/closed) for a PR mentioning riscv
     in that repo. If found, skip and report it -- don't duplicate in-flight
     work.
  6. Otherwise: shallow clone (plain `git clone --depth 1`, https only, single
     `origin` remote verified) into the workspace.

Requires `gh` (GitHub CLI) authenticated for reasonable API/search rate limits
(`gh auth status`). Without it, falls back to unauthenticated REST calls,
which will be slow and may get rate-limited well before finishing a large run
-- use a small --limit in that case.

Lives at python-wheels/tools/riscv64_discover.py. Repos get cloned as siblings
of python-wheels (i.e. into the directory that contains the python-wheels
checkout), not into tools/ itself.

Usage:
    python3 riscv64_discover.py                    # top 150 candidates (default)
    python3 riscv64_discover.py --limit 50
    python3 riscv64_discover.py --dry-run           # classify only, clone nothing
    python3 riscv64_discover.py --report report.json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import riscv64_common as common

ROOT = Path(__file__).resolve().parent.parent.parent  # clone siblings of python-wheels
DASHBOARD_JSON = "https://riseproject-dev.github.io/python-wheels-dashboard/results.json"
PYPI_JSON = "https://pypi.org/pypi/{name}/json"
GITHUB_URL_RE = re.compile(r"github\.com/([^/\s\"'()#]+)/([^/\s\"'()#.]+)")

def _gh_authenticated() -> bool:
    if not shutil.which("gh"):
        return False
    r = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=10)
    return r.returncode == 0


HAVE_GH = _gh_authenticated()


def http_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "riscv64-discover/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception as e:
        print(f"  [http-error] {url}: {e}", file=sys.stderr)
        return None


def http_text(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "riscv64-discover/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode(errors="ignore")
    except Exception:
        return None


def gh_api(path: str) -> dict | list | None:
    """GET api.github.com/<path> via `gh api` if available (uses the user's
    token -> 5000/hr core, 30/min search), else anonymous (60/hr, 10/min)."""
    if HAVE_GH:
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            if "404" in r.stderr:
                return None
            if "403" in r.stderr or "rate limit" in r.stderr.lower():
                print("  [rate-limited] sleeping 60s", file=sys.stderr)
                time.sleep(60)
                return gh_api(path)
            return None
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return None
    else:
        data = http_json(f"https://api.github.com/{path}")
        time.sleep(1.0)  # be polite without a token
        return data


def fetch_dashboard_candidates(limit: int) -> list[dict]:
    data = http_json(DASHBOARD_JSON)
    if not data:
        sys.exit("Could not fetch dashboard results.json")
    pkgs = [p for p in data["data"] if p.get("css_class") == "warning"]
    pkgs.sort(key=lambda p: p.get("downloads", 0), reverse=True)
    return pkgs[:limit]


def resolve_github_repo(pkg_name: str) -> tuple[str, str] | None:
    info = http_json(PYPI_JSON.format(name=pkg_name))
    if not info:
        return None
    candidates = [info["info"].get("home_page") or ""]
    candidates += list((info["info"].get("project_urls") or {}).values())
    for url in candidates:
        m = GITHUB_URL_RE.search(url or "")
        if m:
            owner, repo = m.group(1), m.group(2)
            if owner.lower() not in ("sponsors", "orgs", "about") :
                return owner, repo.removesuffix(".git")
    return None


def workflow_files(owner: str, repo: str) -> list[dict]:
    listing = gh_api(f"repos/{owner}/{repo}/contents/.github/workflows")
    if not isinstance(listing, list):
        return []
    return [f for f in listing if f.get("name", "").endswith((".yml", ".yaml"))]


def classify_backend_and_riscv(owner: str, repo: str) -> tuple[str | None, bool]:
    """Returns (backend or None, already_has_riscv)."""
    files = workflow_files(owner, repo)
    texts = [http_text(f.get("download_url") or "") or "" for f in files]
    backend = None
    for text in texts:
        low = text.lower()
        if "maturin" in low and backend is None:
            backend = "maturin"
        elif "cibuildwheel" in low and backend is None:
            backend = "cibuildwheel"
    return backend, common.text_mentions(texts, r"riscv")


def existing_riscv_prs(owner: str, repo: str) -> list[str]:
    q = f"repo:{owner}/{repo} is:pr riscv"
    result = gh_api(f"search/issues?q={urllib.parse.quote(q)}")
    if not result or not isinstance(result, dict):
        return []
    return [item["html_url"] + f" ({item['state']})" for item in result.get("items", [])]


def clone_one(owner: str, repo: str, dest: Path) -> str:
    return common.clone_shallow(owner, repo, dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150, help="how many top warning-category packages to examine")
    ap.add_argument("--dry-run", action="store_true", help="classify only, clone nothing")
    ap.add_argument("--report", default="riscv64_discover_report.json")
    ap.add_argument("--log", default="riscv64_discover.log", help="path to write a full run log to")
    args = ap.parse_args()

    if not HAVE_GH:
        print("WARNING: `gh` not found -- using unauthenticated GitHub API calls "
              "(60/hr core, 10/min search). Use a small --limit.", file=sys.stderr)

    log = common.log
    with open(args.log, "w") as log_fh:
        log.set_file(log_fh)

        candidates = fetch_dashboard_candidates(args.limit)
        log(f"{len(candidates)} candidates from dashboard (warning category, by downloads)\n")

        cloned, skipped = [], []
        for pkg in candidates:
            name = pkg["name"]
            repo_info = resolve_github_repo(name)
            if not repo_info:
                log(f"[skip] {name}: no-github-repo-found")
                skipped.append(dict(name=name, reason="no-github-repo-found"))
                continue
            owner, repo = repo_info

            backend, has_riscv = classify_backend_and_riscv(owner, repo)
            if backend is None:
                log(f"[skip] {name} ({owner}/{repo}): not-maturin-or-cibuildwheel")
                skipped.append(dict(name=name, repo=f"{owner}/{repo}", reason="not-maturin-or-cibuildwheel"))
                continue
            if has_riscv:
                log(f"[skip] {name} ({owner}/{repo}): already-has-riscv-in-ci (dashboard is stale)")
                skipped.append(dict(name=name, repo=f"{owner}/{repo}", reason="already-has-riscv-in-ci"))
                continue

            prs = existing_riscv_prs(owner, repo)
            if prs:
                log(f"[skip] {name} ({owner}/{repo}): existing riscv PR(s): {prs}")
                skipped.append(dict(name=name, repo=f"{owner}/{repo}", reason="existing-riscv-pr", prs=prs))
                continue

            dest = ROOT / repo
            if args.dry_run:
                log(f"[would-clone] {name} ({owner}/{repo}) backend={backend}")
                cloned.append(dict(name=name, repo=f"{owner}/{repo}", backend=backend, dir=str(dest), dry_run=True))
                continue
            status = clone_one(owner, repo, dest)
            log(f"[{status}] {name} ({owner}/{repo}) backend={backend} -> {dest}")
            if status in ("cloned", "exists"):
                cloned.append(dict(name=name, repo=f"{owner}/{repo}", backend=backend, dir=str(dest)))
            else:
                skipped.append(dict(name=name, repo=f"{owner}/{repo}", reason=status))

        log("\n=== SUMMARY ===")
        log(f"Cloned/ready ({len(cloned)}): {', '.join(c['name'] for c in cloned)}")
        log(f"Skipped ({len(skipped)}):")
        by_reason: dict[str, int] = {}
        for s in skipped:
            by_reason[s["reason"]] = by_reason.get(s["reason"], 0) + 1
        for reason, n in sorted(by_reason.items(), key=lambda kv: -kv[1]):
            log(f"  {reason}: {n}")
            for s in skipped:
                if s["reason"] == reason:
                    extra = f" -- {s['prs']}" if reason == "existing-riscv-pr" else ""
                    log(f"    - {s['name']}{extra}")

    Path(args.report).write_text(json.dumps(dict(cloned=cloned, skipped=skipped), indent=2))
    print(f"\nReport written to {args.report}, log written to {args.log}")


if __name__ == "__main__":
    main()
