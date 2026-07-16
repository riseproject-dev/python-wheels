#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project

# SPDX-License-Identifier: MIT
"""
Script to check if packages in the riscv64 registry are up to date with PyPI.

This script compares versions between the riscv64 registry and PyPI to determine
if packages should be upgraded or can be deprecated.

It is inspired by the check_versions.py script at:

https://gitlab.com/riseproject/python/wheel_builder/-/blob/main/ci_scripts/check_versions.py
"""

import re
import subprocess
import sys
import os
from typing import Dict, List, Optional
from packaging import version
from pathlib import Path
import requests


REGISTRY_URL = "https://pypi.riseproject.dev/simple/"
PACKAGES_FILE = "ci_scripts/packages.txt"
REPO = "riseproject-dev/python-wheels"

# Cap on how many new versions get dispatched per upgrade PR. When the registry
# drifts far behind PyPI, an unbounded loop could kick off dozens of workflow
# runs per package. Three keeps the retry cost bounded while still covering the
# common "we missed one or two point releases" case.
MAX_NEW_VERSIONS_PER_PR = 3


def read_packages() -> List[str]:
    """Read the list of packages from packages.txt."""
    packages = []
    try:
        with open(PACKAGES_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    packages.append(line)
    except FileNotFoundError:
        print(f"Error: {PACKAGES_FILE} not found")
        sys.exit(1)
    return packages


def get_registry_latest_version(package: str) -> Optional[str]:
    """Get the latest version available in the riscv64 registry."""
    try:
        result = subprocess.run([
            "pip", "index", "versions", package,
            "--index-url", REGISTRY_URL,
            "--platform", "manylinux_2_34_riscv64",
            "--platform", "manylinux_2_35_riscv64",
            "--platform", "manylinux_2_39_riscv64",
            "--python-version", "3.12"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return None

        for line in result.stdout.split('\n'):
            if "Available versions:" in line:
                versions_part = line.split("Available versions:")[1].strip()
                if versions_part:
                    versions = [v.strip() for v in versions_part.split(',')]
                    return versions[0] if versions else None
        return None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None


def get_pypi_package_info(package: str) -> Optional[Dict]:
    """Get package information from PyPI API."""
    try:
        response = requests.get(f"https://pypi.org/pypi/{package}/json", timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def get_pypi_latest_version(package_info: Dict) -> str:
    return package_info["info"]["version"]


def get_pypi_package_url(package_info: Dict) -> str:
    return package_info["info"]["package_url"]


def has_riscv64_wheel(package_info: Dict, target_version: str) -> bool:
    """Check if a specific version has riscv64 wheels available."""
    releases = package_info.get("releases", {})
    for release in releases.get(target_version, []):
        if "riscv64" in release.get("filename", "").lower():
            return True
    return False


def is_pure_python_wheel(package_info: Dict, target_version: str) -> bool:
    """Check if a version only has pure Python wheels."""
    releases = package_info.get("releases", {})
    has_wheels = False
    for release in releases.get(target_version, []):
        filename = release.get("filename", "")
        if filename.endswith(".whl"):
            has_wheels = True
            if "py3-none-any" not in filename.lower():
                return False
    return has_wheels


def git_run(*args, subdir: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=subdir, check=True, capture_output=True, text=True)


def find_upstream_issue(package: str) -> Optional[str]:
    """
    Find issue for a package in the wheel_builder's Upstream milestone.

    All issues in the upstream milestone follow the same title format:

        {package} riscv64 support
    """
    try:
        issue_title = f"{package} riscv64 support"
        result = subprocess.run([
            "gh", "issue", "list",
            "--milestone", "Upstream",
            "--search", issue_title,
            "--json", "number",
            "--jq", ".[0].number",
            "--repo", REPO,
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return None

        return result.stdout.strip() or None

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception):
        return None


def configure_git_identity():
    git_run("config", "user.name", "github-actions[bot]")
    git_run("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")


def extract_pr_url(stdout: str) -> Optional[str]:
    for line in stdout.split('\n'):
        line = line.strip()
        if "github.com" in line and "/pull/" in line:
            return line
    return None


def create_deprecation_pr(package: str, reason: str) -> Optional[str]:
    """Create a pull request to deprecate a package."""
    try:
        git_run("fetch", "origin")
        git_run("switch", "main")

        yaml_file = Path(f"docs/packages/{package}.yaml")
        if not yaml_file.exists():
            print(f"    [!] YAML file for {package} does not exist")
            return None

        content = yaml_file.read_text()

        if content.startswith("deprecated:"):
            print(f"    [!] {package} is already deprecated")
            return None

        new_content = f"deprecated:\n{content}"

        upstream_issue = find_upstream_issue(package)
        if upstream_issue:
            print(f"    [+] Found upstream issue #{upstream_issue} for {package}")
        else:
            print(f"    [!] No upstream issue found for {package}")

        branch = f"github-actions/deprecate-{package}"

        configure_git_identity()
        git_run("switch", "-c", branch)

        yaml_file.write_text(new_content)

        packages_file = Path("ci_scripts/packages.txt")
        if packages_file.exists():
            lines = packages_file.read_text().splitlines()
            updated_lines = []
            for line in lines:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#') and stripped_line == package:
                    continue
                updated_lines.append(line)
            packages_file.write_text('\n'.join(updated_lines) + '\n')

        deprecated_file = Path("ci_scripts/deprecated.txt")
        lines = deprecated_file.read_text().splitlines()

        comments = lines[:7]
        deprecated_packages = lines[7:]

        if package not in deprecated_packages:
            deprecated_packages.append(package)
            deprecated_packages.sort(key=lambda s: s.lower())
            updated_lines = comments + deprecated_packages
            deprecated_file.write_text('\n'.join(updated_lines) + '\n')

        commit_title = f"{package}: deprecate our wheel"
        fix_tag = f"Fixes: #{upstream_issue}\n\n" if upstream_issue else ""

        git_run("add", str(yaml_file))
        git_run("add", str(packages_file))
        git_run("add", str(deprecated_file))
        git_run("commit", "-s", "-m", f"{commit_title}\n\n{reason}\n\n{fix_tag}")

        git_run("push", "origin", branch)

        result = subprocess.run([
            "gh", "pr", "create", "--draft",
            "--repo", REPO,
            "--base", "main",
            "--head", branch,
            "--reviewer", "threexc,justeph",
            "--title", f"{package}: deprecate our wheel",
            "--body", f"Automatically generated PR to deprecate {package}.\n\n{reason}\n\n{fix_tag}",
        ], capture_output=True, text=True, check=True)

        return extract_pr_url(result.stdout) or f"PR created for {package} (URL not found in output)"

    except subprocess.CalledProcessError as e:
        print(f"    [X] Error creating PR for {package}: {e.stderr or e}")
        return None
    except Exception as e:
        print(f"    [X] Unexpected error creating PR for {package}: {e}")
        return None


def dispatch_workflow(workflow: str, ref: str, version_input: str) -> bool:
    """
    Dispatch a workflow_dispatch workflow with a version input.

    Strips any leading `v`/`V` from version_input; build workflows already
    prepend `v` when constructing git refs (e.g. `ref: v${{ env.VERSION }}`),
    so passing `v2.5.1` would produce `vv2.5.1`.
    """
    version_input = version_input.lstrip("vV")
    try:
        subprocess.run([
            "gh", "workflow", "run", workflow,
            "--repo", REPO,
            "--ref", ref,
            "-f", f"version={version_input}",
        ], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"    [!] Failed to dispatch {workflow}: {e.stderr or e}")
        return False


def get_new_versions(package_info: Dict, registry_version: str) -> List[str]:
    """
    Return sorted list of stable PyPI versions strictly greater than
    registry_version. Skips prereleases, dev releases, and fully yanked
    versions.

    Result is truncated to the newest MAX_NEW_VERSIONS_PER_PR entries so a
    stale registry does not spawn dozens of workflow dispatches per package.
    Older skipped versions can still be triggered manually by editing the PR
    body to add more `Trigger:` directives.
    """
    try:
        reg_ver = version.parse(registry_version)
    except version.InvalidVersion:
        return []

    result = []
    for raw, files in (package_info.get("releases") or {}).items():
        try:
            v = version.parse(raw)
        except version.InvalidVersion:
            continue
        if v.is_prerelease or v.is_devrelease:
            continue
        if v <= reg_ver:
            continue
        if files and all(f.get("yanked") for f in files):
            continue
        result.append(raw)

    result.sort(key=version.parse)
    return result[-MAX_NEW_VERSIONS_PER_PR:]


def find_workflow_default_version(content: str) -> Optional[str]:
    """
    Return the value of `default:` under `workflow_dispatch.inputs.version`.

    Uses a simple heuristic: the first `default:` after `workflow_dispatch:`.
    This holds for the current build-<pkg>.yml template.
    """
    marker = re.search(r"workflow_dispatch:", content)
    if not marker:
        return None
    m = re.search(
        r"^\s*default:\s*(['\"]?)([^'\"\n\r]+?)\1\s*$",
        content[marker.end():],
        re.MULTILINE,
    )
    return m.group(2).strip() if m else None


def bump_workflow_version(path: Path, new_version: str) -> bool:
    """
    Update the workflow_dispatch default version in a workflow file, and
    replace every quoted literal of the old version elsewhere in the file
    (concurrency group, env defaults, job names).

    Returns True if the file was modified.
    """
    content = path.read_text()
    current = find_workflow_default_version(content)
    if current is None or current == new_version:
        return False
    updated = re.sub(
        r"(['\"])" + re.escape(current) + r"\1",
        lambda m: f"{m.group(1)}{new_version}{m.group(1)}",
        content,
    )
    if updated == content:
        return False
    path.write_text(updated)
    return True


def create_upgrade_pr(package: str, package_info: Dict, new_versions: List[str]) -> Optional[str]:
    """
    Create a PR to trigger builds for each new package version.

    - Bumps the `default:` version in build-<pkg>.yml (and test-<pkg>.yml if
      present) to the latest new version.
    - PR body includes a `Trigger: <package>:<version>` line for every new
      version so the pr-trigger workflow (or a human editing the body) can
      re-dispatch builds.
    - Script also directly dispatches build-<pkg>.yml (and test-<pkg>.yml if
      present) once per new version, because PRs authored by GITHUB_TOKEN do
      not fire pull_request workflows.
    - If build workflow is missing, PR body contains boilerplate asking the
      reviewer to create it.
    """
    if not new_versions:
        return None

    latest_version = new_versions[-1]

    try:
        configure_git_identity()

        git_run("fetch", "origin")
        git_run("switch", "main")

        branch = f"github-actions/upgrade-{package}-{latest_version}"
        git_run("switch", "-c", branch)

        pypi_package_url = get_pypi_package_url(package_info)
        build_workflow = Path(f".github/workflows/build-{package}.yml")
        test_workflow = Path(f".github/workflows/test-{package}.yml")

        bumped: List[Path] = []
        if build_workflow.exists() and bump_workflow_version(build_workflow, latest_version):
            git_run("add", str(build_workflow))
            bumped.append(build_workflow)
        if test_workflow.exists() and bump_workflow_version(test_workflow, latest_version):
            git_run("add", str(test_workflow))
            bumped.append(test_workflow)

        if bumped:
            commit_message = f"{package}: upgrade to v{latest_version}"
            git_run("commit", "-m", commit_message)
        else:
            # This block should only run if either:
            #
            # 1. No workflows exist for the package
            # 2. The workflows don't need a bump for the detected version
            #
            # In the latter case, we want an empty PR to indicate that a new
            # build should be triggered to add the latest version to the
            # registry. Trigger directives are added for the empty PR so we can
            # run a test build and ensure no tweaks need to be made before
            # running the workflow from main.
            commit_message = f"DO NOT MERGE: {package}: trigger builds for v{latest_version}"
            git_run("commit", "--allow-empty", "-m", commit_message)

        git_run("push", "origin", branch)

        versions_list = ", ".join(f"v{v}" for v in new_versions)
        body_lines = [
            f"Automatically generated PR to upgrade {package} — new versions detected: {versions_list}.",
            "",
            f"Link to [PyPI]({pypi_package_url}).",
            "",
        ]

        if bumped:
            bumped_list = ", ".join(f"`{p}`" for p in bumped)
            body_lines += [
                f"Bumped default `version` input to v{latest_version} in {bumped_list}.",
                "",
            ]

        if build_workflow.exists():
            body_lines += [
                "Build (and test, if present) workflows dispatched automatically for each version listed below.",
                "",
                "Trigger directives (re-dispatch by editing the PR body):",
                "",
            ]
            body_lines += [f"Trigger: {package}:{v}" for v in new_versions]
            body_lines += [
                "",
                "If all builds succeed without modification, merge this PR and re-trigger the workflow(s) from `main` to publish.",
                "If changes are needed, force-push this branch and re-dispatch.",
            ]
        else:
            body_lines += [
                f"No build workflow found at `.github/workflows/build-{package}.yml`.",
                "Please create one (and optionally a matching `test-*.yml`) before merging.",
                "",
                "Once the workflow exists, edit this PR body to re-fire the `Trigger:` directives:",
                "",
            ]
            body_lines += [f"Trigger: {package}:{v}" for v in new_versions]

        body = "\n".join(body_lines) + "\n"

        result = subprocess.run([
            "gh", "pr", "create", "--draft",
            "--repo", REPO,
            "--base", "main",
            "--head", branch,
            "--reviewer", "threexc,justeph",
            "--title", f"Upgrade {package} to v{latest_version}",
            "--body", body,
        ], capture_output=True, text=True, check=True)

        pr_url = extract_pr_url(result.stdout) or f"PR created for {package} (URL not found in output)"

        if build_workflow.exists():
            for v in new_versions:
                print(f"    [+] Dispatching build-{package}.yml on {branch} for v{v}")
                dispatch_workflow(f"build-{package}.yml", branch, v)
                if test_workflow.exists():
                    print(f"    [+] Dispatching test-{package}.yml on {branch} for v{v}")
                    dispatch_workflow(f"test-{package}.yml", branch, v)
        else:
            print(f"    [!] No build workflow for {package}; skipping dispatch")

        return pr_url

    except subprocess.CalledProcessError as e:
        print(f"    [X] Error creating upgrade PR for {package}: {e.stderr or e}")
        return None
    except Exception as e:
        print(f"    [X] Unexpected error creating upgrade PR for {package}: {e}")
        return None


def compare_versions(registry_version: str, pypi_version: str) -> int:
    """Compare two version strings. Returns 0 if version matches, -1 otherwise."""
    reg_ver = version.parse(registry_version)
    pypi_ver = version.parse(pypi_version)
    if reg_ver < pypi_ver:
        return -1
    return 0


def check_package(package: str, create_prs: bool = False) -> Dict[str, any]:
    """Check a single package version and optionally create PRs."""

    registry_version = get_registry_latest_version(package)
    if registry_version is None:
        print(f"[X] Could not get registry version for {package}")
        return {"status": "error", "package": package, "error": "Could not get registry version"}

    pypi_info = get_pypi_package_info(package)
    if pypi_info is None:
        print(f"[X] Could not get PyPI info for {package}")
        return {"status": "error", "package": package, "error": "Could not get PyPI info"}

    pypi_version = get_pypi_latest_version(pypi_info)
    pypi_package_url = get_pypi_package_url(pypi_info)

    if compare_versions(registry_version, pypi_version) == 0:
        print(f"[+] {package} v{pypi_version} is up to date")
        return {
            "status": "up_to_date",
            "package": package,
            "registry_version": registry_version,
            "pypi_version": pypi_version
        }

    if has_riscv64_wheel(pypi_info, pypi_version):
        print(f"[-] {package} v{pypi_version} has riscv64 wheels on PyPI. Can be deprecated.")
        reason = f"{package} v{pypi_version} has riscv64 wheels on PyPI: {pypi_package_url}"
        pr_url = create_deprecation_pr(package, reason) if create_prs else None
        return {
            "status": "can_deprecate",
            "package": package,
            "registry_version": registry_version,
            "pypi_version": pypi_version,
            "reason": reason,
            "pr_url": pr_url,
        }

    if is_pure_python_wheel(pypi_info, pypi_version):
        print(f"[-] {package} v{pypi_version} switched to pure Python wheels only. Can be deprecated.")
        reason = f"{package} v{pypi_version} switched to pure Python wheels only: {pypi_package_url}"
        pr_url = create_deprecation_pr(package, reason) if create_prs else None
        return {
            "status": "can_deprecate",
            "package": package,
            "registry_version": registry_version,
            "pypi_version": pypi_version,
            "reason": reason,
            "pr_url": pr_url,
        }

    new_versions = get_new_versions(pypi_info, registry_version) or [pypi_version]
    print(f"[^] {package} can be upgraded: v{registry_version} -> {', '.join(f'v{v}' for v in new_versions)}")
    pr_url = create_upgrade_pr(package, pypi_info, new_versions) if create_prs else None
    return {
        "status": "need_upgrade",
        "package": package,
        "registry_version": registry_version,
        "pypi_version": pypi_version,
        "new_versions": new_versions,
        "pr_url": pr_url,
    }


def print_summary(results: List[Dict[str, any]]):
    """Print a formatted summary of all results."""
    up_to_date, can_deprecate, need_upgrade, errors = [], [], [], []

    for result in results:
        {
            "up_to_date": up_to_date,
            "can_deprecate": can_deprecate,
            "need_upgrade": need_upgrade,
            "error": errors,
        }.get(result["status"], []).append(result)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\n[+] UP TO DATE ({len(up_to_date)} packages):")
    if up_to_date:
        max_name_len = max(len(r["package"]) for r in up_to_date)
        for result in sorted(up_to_date, key=lambda x: x["package"]):
            print(f"    {result['package']:<{max_name_len}} v{result['pypi_version']}")
    else:
        print("    (none)")

    print(f"\n[-] CAN BE DEPRECATED ({len(can_deprecate)} packages):")
    if can_deprecate:
        max_name_len = max(len(r["package"]) for r in can_deprecate)
        max_reg_version_len = max(len(f"v{r['registry_version']}") for r in can_deprecate)
        for result in sorted(can_deprecate, key=lambda x: x["package"]):
            reg_version = f"v{result['registry_version']}"
            pypi_version = f"v{result['pypi_version']}"
            print(f"    {result['package']:<{max_name_len}} {reg_version:>{max_reg_version_len}} -> {pypi_version} ({result['reason']})")
            if result.get('pr_url'):
                print(f"    {'':<{max_name_len}} {'':<{max_reg_version_len}}    PR: {result['pr_url']}")
    else:
        print("    (none)")

    print(f"\n[^] NEED UPGRADE ({len(need_upgrade)} packages):")
    if need_upgrade:
        max_name_len = max(len(r["package"]) for r in need_upgrade)
        max_reg_version_len = max(len(f"v{r['registry_version']}") for r in need_upgrade)
        for result in sorted(need_upgrade, key=lambda x: x["package"]):
            reg_version = f"v{result['registry_version']}"
            pypi_version = f"v{result['pypi_version']}"
            print(f"    {result['package']:<{max_name_len}} {reg_version:>{max_reg_version_len}} -> {pypi_version}")
            if result.get('pr_url'):
                print(f"    PR: {result['pr_url']}")
    else:
        print("    (none)")

    if errors:
        print(f"\n[X] ERRORS ({len(errors)} packages):")
        max_name_len = max(len(r["package"]) for r in errors)
        for result in sorted(errors, key=lambda x: x["package"]):
            print(f"    {result['package']:<{max_name_len}} {result['error']}")

    print("\n" + "=" * 80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Check package versions between riscv64 registry and PyPI")
    parser.add_argument("packages", nargs="*", help="Specific packages to check (default: all packages from packages.txt)")
    parser.add_argument("--create-prs", action="store_true", help="Create pull requests for packages that can be deprecated or upgraded")
    parser.add_argument("--summary", action="store_true", help="Show detailed summary at the end")

    args = parser.parse_args()

    if args.packages:
        packages = args.packages
        print(f"Checking {len(packages)} specified package(s)...")
    else:
        packages = read_packages()
        print("Checking package versions between riscv64 registry and PyPI...")
        print(f"Found {len(packages)} packages to check")

    if args.create_prs and not os.environ.get("GH_TOKEN"):
        print("[!] Warning: --create-prs specified but GH_TOKEN not set")
        args.create_prs = False

    results = []
    for package in packages:
        try:
            results.append(check_package(package, create_prs=args.create_prs))
        except KeyboardInterrupt:
            print("\n[!] Interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"[X] Error checking {package}: {e}")
            results.append({"status": "error", "package": package, "error": str(e)})

    if args.summary or len(packages) > 5:
        print_summary(results)

    if any(r["status"] == "error" for r in results):
        sys.exit(1)

    if args.create_prs:
        pr_failures = [
            r for r in results
            if r["status"] in ("need_upgrade", "can_deprecate") and r.get("pr_url") is None
        ]
        if pr_failures:
            print(f"\n[X] PR creation failed for {len(pr_failures)} package(s): "
                  + ", ".join(r["package"] for r in pr_failures))
            sys.exit(1)


if __name__ == "__main__":
    main()
