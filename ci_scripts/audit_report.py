#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""
Parse pip-audit JSON report, emit warning annotations, append a job summary,
and open/update GitHub issues (one per (package, vulnerability id)).

Expects environment:
  GH_TOKEN            authenticated gh token
  GITHUB_REPOSITORY   owner/repo (auto-set on GitHub Actions)
  GITHUB_SERVER_URL   e.g. https://github.com (auto-set)
  GITHUB_RUN_ID       current workflow run id (auto-set)
  GITHUB_STEP_SUMMARY path to write step summary (auto-set)

Usage: audit_report.py <path-to-audit-report.json>
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

ISSUE_LABELS = ["pip-audit", "security"]


def run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not repo or not run_id:
        return "<run URL unavailable outside GitHub Actions>"
    return f"{server}/{repo}/actions/runs/{run_id}"


def append_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a") as f:
        f.write(text)


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=check
    )


def find_existing_issue(title: str) -> Optional[int]:
    """Return open issue number matching exact title with the pip-audit label, else None."""
    try:
        result = gh(
            "issue", "list",
            "--label", "pip-audit",
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


def create_issue(title: str, body: str) -> Optional[int]:
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


def comment_issue(number: int, body: str) -> bool:
    try:
        gh("issue", "comment", str(number), "--body", body)
        return True
    except subprocess.CalledProcessError as e:
        print(f"    [!] gh issue comment failed: {e.stderr or e}", file=sys.stderr)
        return False


def format_body(pkg: str, version: str, vuln: Dict, url: str) -> str:
    fix_versions = vuln.get("fix_versions") or []
    aliases = vuln.get("aliases") or []
    description = (vuln.get("description") or "").strip()

    lines = [
        f"`pip-audit` detected a vulnerability in **{pkg}** {version}.",
        "",
        f"- Vulnerability ID: `{vuln.get('id', 'unknown')}`",
    ]
    if aliases:
        lines.append(f"- Aliases: {', '.join(f'`{a}`' for a in aliases)}")
    if fix_versions:
        lines.append(f"- Fix versions: {', '.join(f'`{v}`' for v in fix_versions)}")
    else:
        lines.append("- Fix versions: _none reported_")
    lines += [
        f"- First observed: {url}",
        "",
        "### Description",
        "",
        description or "_(no description provided)_",
    ]
    return "\n".join(lines)


def format_comment(pkg: str, version: str, url: str) -> str:
    return (
        f"Still detected in {url}\n"
        f"- Package: `{pkg}` {version}\n"
    )


def process_report(report_path: Path) -> int:
    if not report_path.exists():
        print(f"[!] Report not found at {report_path}; nothing to process.")
        return 0

    try:
        data = json.loads(report_path.read_text())
    except json.JSONDecodeError as e:
        print(f"[!] Failed to parse {report_path}: {e}")
        return 0

    deps = data.get("dependencies", [])
    url = run_url()
    vuln_count = 0
    summary_rows = []

    for dep in deps:
        pkg = dep.get("name")
        version = dep.get("version", "")
        vulns = dep.get("vulns") or []
        if not pkg or not vulns:
            continue

        for vuln in vulns:
            vuln_id = vuln.get("id", "unknown")
            title = f"pip-audit: {pkg} — {vuln_id}"
            fix_versions = vuln.get("fix_versions") or []
            fixes = ", ".join(fix_versions) if fix_versions else "none"

            # GHA warning annotation (yellow bubble on job)
            print(
                f"::warning file=ci_scripts/packages.txt::"
                f"{pkg} {version}: {vuln_id} (fix: {fixes})"
            )

            summary_rows.append(
                f"| `{pkg}` | {version} | `{vuln_id}` | {fixes} |"
            )

            existing = find_existing_issue(title)
            if existing is not None:
                if comment_issue(existing, format_comment(pkg, version, url)):
                    print(f"    [+] Updated existing issue #{existing} for {pkg} {vuln_id}")
                else:
                    print(f"    [!] Failed to comment on issue #{existing} for {pkg} {vuln_id}")
            else:
                number = create_issue(title, format_body(pkg, version, vuln, url))
                if number is not None:
                    print(f"    [+] Created issue #{number} for {pkg} {vuln_id}")
                else:
                    print(f"    [!] Failed to create issue for {pkg} {vuln_id}")

            vuln_count += 1

    if summary_rows:
        summary = (
            "## pip-audit report\n\n"
            f"Detected **{vuln_count}** vulnerability(ies). "
            f"Run: {url}\n\n"
            "| Package | Version | Vulnerability | Fix versions |\n"
            "|---------|---------|---------------|--------------|\n"
            + "\n".join(summary_rows)
            + "\n"
        )
    else:
        summary = f"## pip-audit report\n\nNo vulnerabilities detected. Run: {url}\n"

    append_summary(summary)
    print(f"[+] Processed {vuln_count} vulnerability(ies).")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: audit_report.py <path-to-audit-report.json>", file=sys.stderr)
        return 2
    return process_report(Path(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
