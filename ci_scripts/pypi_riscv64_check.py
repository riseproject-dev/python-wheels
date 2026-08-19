#!/usr/bin/env python3
"""
pypi_riscv64_check.py

Fetches the top N PyPI packages by download count, filters down to those
shipping platform-specific (binary) wheels, and flags which ones already
provide riscv64 wheels in their latest release on PyPI.

Data source: hugovk/top-pypi-packages (updated monthly, via GitHub raw)
Wheel info:  PyPI JSON API  https://pypi.org/pypi/{package}/json

Usage:
    python pypi_riscv64_check.py              # default: top 50
    python pypi_riscv64_check.py --top 30     # top 30 binary-wheel packages
    python pypi_riscv64_check.py --exclude-riscv64   # hide packages that already have it
    python pypi_riscv64_check.py --create-issues     # file GitHub issues for gaps (needs GH_TOKEN)
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

TOP_PACKAGES_URL = (
    "https://raw.githubusercontent.com/hugovk/top-pypi-packages/"
    "main/top-pypi-packages.min.json"
)
PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"
REGISTRY_SIMPLE_URL = "https://pypi.riseproject.dev/simple/{package}/"
REQUEST_DELAY = 0.5   # seconds between PyPI API calls (be polite)
ISSUE_LABELS = ["riscv64-check", "wheel"]


def gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True)


def find_existing_issue(title: str) -> int | None:
    """Return open issue number matching exact title with the riscv64-check label, else None."""
    try:
        result = gh(
            "issue", "list",
            "--label", ISSUE_LABELS[0],
            "--state", "open",
            "--search", f'"{title}" in:title',
            "--json", "number,title",
            "--limit", "50",
        )
    except subprocess.CalledProcessError as e:
        print(f"    [!] gh issue list failed: {e.stderr or e}", file=sys.stderr)
        return None

    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    for issue in issues:
        if issue.get("title") == title:
            return issue.get("number")
    return None


def create_issue(title: str, body: str) -> int | None:
    args = ["issue", "create", "--title", title, "--body", body]
    for label in ISSUE_LABELS:
        args += ["--label", label]
    try:
        result = gh(*args)
    except subprocess.CalledProcessError as e:
        print(f"    [!] gh issue create failed: {e.stderr or e}", file=sys.stderr)
        return None

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("http") and "/issues/" in line:
            try:
                return int(line.rsplit("/", 1)[-1])
            except ValueError:
                pass
    return None


def open_issues_for_missing(packages: list[str]) -> dict[str, int]:
    """Open an issue for each package not already tracked by an open riscv64-check
    issue. Returns {package: issue_number} for every package that ends up with
    one open, whether just created or pre-existing."""
    issues = {}
    for name in packages:
        title = f"{name} riscv64 support"
        existing = find_existing_issue(title)
        if existing is not None:
            issues[name] = existing
            continue
        body = (
            f"`{name}` ships binary wheels but no riscv64 wheels on PyPI, "
            "and is not present in the RISE riscv64 registry.\n\n"
            "Detected by the monthly `pypi-riscv64-check` workflow."
        )
        number = create_issue(title, body)
        if number is not None:
            print(f"    [+] Created issue #{number} for {name}")
            issues[name] = number
        else:
            print(f"    [!] Failed to create issue for {name}")
    return issues


def open_summary_issue(report: str, issue_map: dict[str, int]) -> None:
    """Open (or skip, if one already exists) a monthly summary issue linking
    to each per-package issue and notifying the maintainers."""
    title = f"PyPI riscv64 check - {time.strftime('%Y-%m')}"
    if find_existing_issue(title) is not None:
        print(f"    [=] Summary issue for {title!r} already open, skipping")
        return

    lines = ["@threexc @justeph monthly PyPI riscv64 wheel report:", "", "```", report, "```"]
    if issue_map:
        lines += ["", "Per-package issues:"]
        lines += [f"- #{number} — {name}" for name, number in issue_map.items()]
    body = "\n".join(lines)

    number = create_issue(title, body)
    if number is not None:
        print(f"    [+] Created summary issue #{number}")
    else:
        print("    [!] Failed to create summary issue")


def normalise(name: str) -> str:
    """PEP 503 normalisation for simple-index package names."""
    return re.sub(r"[-_.]+", "-", name).lower()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Packages missing from the registry get 30x-redirected to pypi.org
    instead of 404ing, so redirects must be treated as "not present"
    rather than followed."""

    def redirect_request(self, *args, **kwargs):
        return None


_REGISTRY_OPENER = urllib.request.build_opener(_NoRedirect)


def in_rise_registry(name: str) -> bool:
    """Whether the package has any wheels in the RISE riscv64 registry."""
    req = urllib.request.Request(
        REGISTRY_SIMPLE_URL.format(package=normalise(name)),
        headers={"User-Agent": "pypi-riscv64-checker/1.0"},
    )
    try:
        _REGISTRY_OPENER.open(req, timeout=15)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code in (302, 303, 404):
            return False
        print(f"  [WARN] Could not check registry for {name}: {exc}")
        return False
    except Exception as exc:
        print(f"  [WARN] Could not check registry for {name}: {exc}")
        return False


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(
        url, headers={"User-Agent": "pypi-riscv64-checker/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def analyse_package(name: str, download_count: int) -> dict | None:
    """
    Returns a result dict if the package ships at least one binary wheel,
    otherwise None (pure-Python or fetch error).
 
    A binary wheel is any .whl file whose filename does NOT end with
    'none-any.whl' (the platform-independent tag).
    """
    try:
        info = fetch_json(PYPI_JSON_URL.format(package=name))
    except Exception as exc:
        print(f"  [WARN] Could not fetch {name}: {exc}")
        return None
 
    wheel_files = [
        u["filename"]
        for u in info.get("urls", [])
        if u["packagetype"] == "bdist_wheel"
    ]

    binary_wheels = [f for f in wheel_files if not f.endswith("none-any.whl")]
    if not binary_wheels:
        return None   # pure-Python or no wheels at all

    riscv64_wheels = [f for f in wheel_files if "riscv64" in f.lower()]
    has_riscv64 = len(riscv64_wheels) > 0

    return {
        "project": name,
        "download_count": download_count,
        "has_riscv64": has_riscv64,
        "in_rise_registry": None if has_riscv64 else in_rise_registry(name),
    }


def fmt_count(n: int) -> str:
    """Format large numbers with M/B suffixes."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    return str(n)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--top", type=int, default=50,
        help="Number of binary-wheel packages to collect (default: 50)"
    )
    parser.add_argument(
        "--exclude-riscv64", action="store_true",
        help="Exclude packages that already have riscv64 wheels"
    )
    parser.add_argument(
        "--create-issues", action="store_true",
        help="Open a GitHub issue for each package missing riscv64 wheels "
             "upstream and in the RISE registry, unless one is already open"
    )
    args = parser.parse_args()

    print("Fetching top-packages dataset …")
    dataset = fetch_json(TOP_PACKAGES_URL)
    all_packages = dataset["rows"]
    last_update = dataset.get("last_update", "unknown")
    print(f"  Dataset last updated: {last_update}")
    print(f"  Scanning for top {args.top} binary-wheel packages …\n")

    results = []
    scanned = 0

    for pkg in all_packages:
        if len(results) >= args.top:
            break

        name = pkg["project"]
        dl = pkg["download_count"]
        result = analyse_package(name, dl)
        scanned += 1

        if result is None:
            continue

        if args.exclude_riscv64 and result["has_riscv64"]:
            print(f"  SKIP (riscv64 exists): {name}")
            continue

        results.append(result)
        time.sleep(REQUEST_DELAY)

    # --- Build table ---
    report_lines = [
        f"{'Rank':<5} {'Package':<35} {'Downloads':>12} {'riscv64':>10} {'RISE registry':>14}",
        "-" * 82,
    ]
    for i, r in enumerate(results, 1):
        riscv_col = "✓" if r["has_riscv64"] else "✗"
        if r["has_riscv64"]:
            registry_col = "N/A"
        else:
            registry_col = "✓" if r["in_rise_registry"] else "✗"
        report_lines.append(
            f"{i:<5} {r['project']:<35} "
            f"{fmt_count(r['download_count']):>12} "
            f"{riscv_col:>10} "
            f"{registry_col:>14}"
        )

    no_riscv = [r for r in results if not r["has_riscv64"]]
    missing = [r["project"] for r in no_riscv if not r["in_rise_registry"]]
    covered = [r["project"] for r in no_riscv if r["in_rise_registry"]]

    report_lines += [
        "",
        f"Packages WITHOUT riscv64 wheels upstream and NOT in RISE registry ({len(missing)}/{len(results)}):",
        *(f"  - {name}" for name in missing),
        "",
        f"Packages WITHOUT riscv64 wheels upstream ALREADY in RISE registry ({len(covered)}/{len(results)}):",
        *(f"  - {name}" for name in covered),
        "",
        f"Scanned {scanned} packages total.",
    ]

    report = "\n".join(report_lines)
    print()
    print(report)

    if args.create_issues:
        print()
        issue_map = open_issues_for_missing(missing)
        open_summary_issue(report, issue_map)


if __name__ == "__main__":
    main()
