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

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from packaging import version
from pathlib import Path
import requests
import yaml

from update_doc import normalize_name, version_blocks


ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs" / "packages"
PACKAGES_FILE = "ci_scripts/packages.txt"
DEPRECATED_FILE = "ci_scripts/deprecated.txt"
REPO = "riseproject-dev/python-wheels"

# Python versions (interpreter tags) a package must have upstream riscv64
# wheels for before we deprecate our own build. "3.14t" is the free-threaded
# build — a distinct ABI from "3.14", so it needs its own wheel.
TARGET_PYTHON_VERSIONS = ["3.12", "3.13", "3.14", "3.14t"]


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


def package_yaml(package: str) -> Path:
    # packages.txt keeps PyPI's spelling (PyYAML), the YAMLs use the normalized name.
    return DOCS_DIR / f"{normalize_name(package)}.yaml"


def load_package_yaml(package: str) -> Optional[Dict]:
    yaml_file = package_yaml(package)
    if not yaml_file.exists():
        return None
    return yaml.safe_load(yaml_file.read_text()) or {}


def declared_versions(package_data: Dict) -> Set[str]:
    return {str(e.get("version", "")).strip() for e in package_data.get("versions") or []}


def get_registry_latest_version(package_data: Dict) -> Optional[str]:
    """
    Latest version published to the riscv64 registry, read from the package
    YAML. Entries without `files` are declared but not built yet.
    """
    released = []
    for entry in package_data.get("versions") or []:
        if "files" not in entry:
            continue
        raw = str(entry["version"])
        try:
            released.append((version.parse(raw), raw))
        except version.InvalidVersion:
            continue
    return max(released)[1] if released else None


def get_pypi_package_info(package: str, retries: int = 3) -> Optional[Dict]:
    """Get package information from PyPI API, retrying on transient failures."""
    for attempt in range(retries):
        try:
            response = requests.get(f"https://pypi.org/pypi/{package}/json", timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return None


def get_pypi_latest_version(package_info: Dict) -> str:
    return package_info["info"]["version"]


def get_pypi_package_url(package_info: Dict) -> str:
    return package_info["info"]["package_url"]


def _parse_wheel_tags(filename: str) -> Optional[tuple]:
    """Split a wheel filename into (python_tag, abi_tag, platform_tag)."""
    if not filename.endswith(".whl"):
        return None
    parts = filename[:-len(".whl")].split("-")
    if len(parts) < 5:
        return None
    return parts[-3], parts[-2], parts[-1]


def _wheel_matches_python(python_tag: str, abi_tag: str, target: str) -> bool:
    """Check if a wheel's (python_tag, abi_tag) satisfies a target like "3.12" or "3.14t"."""
    free_threaded = target.endswith("t")
    interp_tag = "cp" + target.rstrip("t").replace(".", "")

    if free_threaded:
        return python_tag == interp_tag and abi_tag == f"{interp_tag}t"

    if python_tag == interp_tag:
        return abi_tag == interp_tag

    if abi_tag == "abi3" and re.fullmatch(r"cp3\d+", python_tag):
        return int(python_tag[3:]) <= int(interp_tag[3:])

    return False


def matching_riscv64_wheels(
    package_info: Dict, target_version: str, python_versions: List[str] = TARGET_PYTHON_VERSIONS
) -> Dict[str, List[str]]:
    """Map each target python version to the riscv64 wheel filenames that satisfy it."""
    riscv64_wheels = []
    for release in package_info.get("releases", {}).get(target_version, []):
        filename = release.get("filename", "")
        tags = _parse_wheel_tags(filename)
        if tags and "riscv64" in tags[2].lower():
            riscv64_wheels.append((filename, tags))

    return {
        pv: [fn for fn, (python_tag, abi_tag, _) in riscv64_wheels if _wheel_matches_python(python_tag, abi_tag, pv)]
        for pv in python_versions
    }


def has_riscv64_wheel(
    package_info: Dict, target_version: str, python_versions: List[str] = TARGET_PYTHON_VERSIONS
) -> bool:
    """Check whether a version has upstream riscv64 wheels covering every python_versions entry."""
    return all(matching_riscv64_wheels(package_info, target_version, python_versions).values())


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


def deprecate_package(package: str) -> bool:
    """
    Deprecate our wheel in the working tree: prefix docs/packages/<pkg>.yaml
    with `deprecated:`, drop the package from packages.txt and add it to
    deprecated.txt. Returns False when it is already deprecated.
    """
    yaml_file = package_yaml(package)
    content = yaml_file.read_text()
    if content.startswith("deprecated:"):
        return False
    yaml_file.write_text(f"deprecated:\n{content}")

    packages_file = Path(PACKAGES_FILE)
    lines = [line for line in packages_file.read_text().splitlines() if line.strip() != package]
    packages_file.write_text("\n".join(lines) + "\n")

    deprecated_file = Path(DEPRECATED_FILE)
    lines = deprecated_file.read_text().splitlines()
    i = next(i for i, line in enumerate(lines) if line.strip() and not line.lstrip().startswith("#"))
    comments, deprecated_packages = lines[:i], lines[i:]
    if package not in deprecated_packages:
        deprecated_packages.append(package)
        deprecated_packages.sort(key=str.lower)
        deprecated_file.write_text("\n".join(comments + deprecated_packages) + "\n")
    return True


def get_new_versions(package_info: Dict, registry_version: str) -> List[str]:
    """
    Return sorted list of stable PyPI versions strictly greater than
    registry_version. Skips prereleases, dev releases, and fully yanked
    versions.
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
    return result


def parse_since(value: str) -> datetime:
    """Accept a YYYY-MM-DD date or a duration such as 12m / 90d, in UTC."""
    now = datetime.now(timezone.utc)
    m = re.fullmatch(r"(\d+)([dm])", value)
    if not m:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return now - timedelta(days=n)
    total = now.year * 12 + now.month - 1 - n
    year, month = divmod(total, 12)
    # Clamp the day so e.g. Mar 31 - 1 month lands on Feb 28/29.
    for day in range(now.day, 0, -1):
        try:
            return now.replace(year=year, month=month + 1, day=day)
        except ValueError:
            continue


def get_versions_since(package_info: Dict, declared: Set[str], since: datetime) -> List[str]:
    """
    Return sorted list of stable PyPI versions first uploaded at or after
    `since` that are not yet declared in the package YAML. Unlike
    get_new_versions this is not capped and not relative to the registry
    version: an old release line that saw a point release recently counts.
    """
    result = []
    for raw, files in (package_info.get("releases") or {}).items():
        if raw in declared or not files or all(f.get("yanked") for f in files):
            continue
        try:
            v = version.parse(raw)
        except version.InvalidVersion:
            continue
        if v.is_prerelease or v.is_devrelease:
            continue
        uploaded = min(
            datetime.fromisoformat(f["upload_time_iso_8601"].replace("Z", "+00:00"))
            for f in files if f.get("upload_time_iso_8601")
        )
        if uploaded >= since:
            result.append(raw)
    return sorted(result, key=version.parse)


def declare_versions(yaml_file: Path, new_versions: List[str]) -> List[str]:
    """
    Append a bare `- version:` entry for each version not yet listed in the
    package YAML, and return the versions that were added.

    An entry without `tag`/`files` is what the build workflow builds, so this
    is all an upgrade PR has to change.
    """
    content = yaml_file.read_text()
    declared = set(re.findall(r"^- version: ['\"]?([^'\"\n]+)", content, re.M))
    added = [v for v in new_versions if v not in declared]
    if not added:
        return []
    lines = [content.rstrip("\n")]
    for v in added:
        lines.append(yaml.safe_dump([{"version": v}], default_flow_style=False).rstrip("\n"))
    yaml_file.write_text("\n".join(lines) + "\n")
    return added


def get_yanked_versions(package_info: Dict, package_data: Dict) -> List[str]:
    """
    Released versions of the YAML whose PyPI release is fully yanked and that
    are not yet marked `yanked: true` locally.
    """
    releases = package_info.get("releases") or {}
    yanked = []
    for entry in package_data.get("versions") or []:
        if "files" not in entry:
            continue
        raw = str(entry["version"])
        files = releases.get(raw) or []
        if not files or not all(f.get("yanked") for f in files):
            continue
        if "yanked" in entry:
            continue
        yanked.append(raw)
    return yanked


def mark_yanked(yaml_file: Path, yanked: List[str]) -> List[str]:
    """
    Add `yanked: true` right after `tag:` of each given version, preserving
    the rest of the file byte-for-byte, and return the versions that were
    marked. The Simple API renders it as PEP 592's data-yanked.
    """
    lines = yaml_file.read_text().splitlines()
    marked = []
    # Bottom-up so earlier block ranges stay valid after inserts.
    for start, end in reversed(list(version_blocks(lines))):
        raw = str(yaml.safe_load("\n".join(lines[start:end]))[0].get("version"))
        if raw not in yanked:
            continue
        if any(line.startswith("  yanked:") for line in lines[start:end]):
            continue
        tag = next((i for i in range(start, end) if lines[i].startswith("  tag:")), None)
        if tag is None:
            continue
        lines.insert(tag + 1, "  yanked: true")
        marked.append(raw)
    if marked:
        yaml_file.write_text("\n".join(lines) + "\n")
    return marked[::-1]


def compare_versions(registry_version: str, pypi_version: str) -> int:
    """Compare two version strings. Returns 0 if version matches, -1 otherwise."""
    reg_ver = version.parse(registry_version)
    pypi_ver = version.parse(pypi_version)
    if reg_ver < pypi_ver:
        return -1
    return 0


def check_package(
    package: str,
    since: Optional[datetime] = None,
    declare: bool = False,
) -> Dict[str, any]:
    """
    Check a single package against PyPI and optionally apply the outcome to
    the working tree.

    With `since`, every stable release uploaded since that date and missing
    from the YAML counts as an upgrade, not just the ones newer than the
    registry. With `declare`, the upgrade, deprecation or yanked marking is
    written to docs/packages/<pkg>.yaml (and packages.txt/deprecated.txt) for
    the caller to commit. Versions yanked upstream are reported in the
    result's `yanked` alongside the upgrade/deprecation status.
    """

    package_data = load_package_yaml(package)
    if package_data is None:
        print(f"[X] No {package_yaml(package).relative_to(ROOT_DIR)}")
        return {"status": "error", "package": package, "error": "No docs/packages YAML"}

    registry_version = get_registry_latest_version(package_data)
    if registry_version is None:
        print(f"[X] No released version in {package_yaml(package).relative_to(ROOT_DIR)}")
        return {"status": "error", "package": package, "error": "No released version in YAML"}

    pypi_info = get_pypi_package_info(package)
    if pypi_info is None:
        print(f"[X] Could not get PyPI info for {package}")
        return {"status": "error", "package": package, "error": "Could not get PyPI info"}

    yanked = get_yanked_versions(pypi_info, package_data)
    if yanked:
        print(f"[!] {package} {', '.join(f'v{v}' for v in yanked)} yanked on PyPI")
        if declare:
            marked = mark_yanked(package_yaml(package), yanked)
            print(f"    [+] marked {', '.join(f'v{v}' for v in marked)} yanked in {package_yaml(package).relative_to(ROOT_DIR)}")

    result = check_upgrade(package, package_data, pypi_info, registry_version, since, declare)
    result["yanked"] = yanked
    return result


def check_upgrade(
    package: str,
    package_data: Dict,
    pypi_info: Dict,
    registry_version: str,
    since: Optional[datetime],
    declare: bool,
) -> Dict[str, any]:
    """Classify the package as up to date, deprecatable or upgradable, and act on it."""
    pypi_version = get_pypi_latest_version(pypi_info)
    pypi_package_url = get_pypi_package_url(pypi_info)

    up_to_date = {
        "status": "up_to_date",
        "package": package,
        "registry_version": registry_version,
        "pypi_version": pypi_version,
    }
    behind = compare_versions(registry_version, pypi_version) < 0

    if not behind and since is None:
        print(f"[+] {package} v{pypi_version} is up to date")
        return up_to_date

    declared = declared_versions(package_data)
    if since is not None:
        candidates = get_versions_since(pypi_info, declared, since)
    else:
        candidates = [v for v in get_new_versions(pypi_info, registry_version) or [pypi_version] if v not in declared]

    # We provide wheels up to the point where upstream does: a version that
    # already has riscv64 wheels for every target Python, or that went pure
    # Python, is never built here, but every gap before it is.
    upstream = [v for v in candidates if has_riscv64_wheel(pypi_info, v) or is_pure_python_wheel(pypi_info, v)]
    new_versions = [v for v in candidates if v not in upstream]
    if upstream:
        print(f"    [=] {package}: skipping {', '.join(f'v{v}' for v in upstream)}, "
              f"riscv64 or pure Python wheels on PyPI for Python {', '.join(TARGET_PYTHON_VERSIONS)}")

    if new_versions:
        print(f"[^] {package} can be upgraded: v{registry_version} -> {', '.join(f'v{v}' for v in new_versions)}")
        if declare:
            added = declare_versions(package_yaml(package), new_versions)
            print(f"    [+] declared {', '.join(f'v{v}' for v in added)} in {package_yaml(package).relative_to(ROOT_DIR)}")
        return {
            "status": "need_upgrade",
            "package": package,
            "registry_version": registry_version,
            "pypi_version": pypi_version,
            "new_versions": new_versions,
        }

    # Only retire the package once every declared version has been built, so
    # the registry really does reach up to upstream's first riscv64 release.
    pending = [str(e["version"]) for e in package_data.get("versions") or [] if "files" not in e]
    if pending:
        print(f"[+] {package}: {', '.join(f'v{v}' for v in pending)} already declared, waiting for the build")
        return up_to_date

    if behind and has_riscv64_wheel(pypi_info, pypi_version):
        py_list = ", ".join(TARGET_PYTHON_VERSIONS)
        wheels_by_version = matching_riscv64_wheels(pypi_info, pypi_version)
        print(f"[-] {package} v{pypi_version} has riscv64 wheels on PyPI for Python {py_list}. Can be deprecated.")
        wheel_lines = [f"- {pv}: {fn}" for pv, files in wheels_by_version.items() for fn in files]
        for line in wheel_lines:
            print(f"        {line}")
        reason = (
            f"{package} v{pypi_version} has riscv64 wheels on PyPI for Python {py_list}: "
            f"{pypi_package_url}\n\n" + "\n".join(wheel_lines)
        )
        return deprecation_result(package, registry_version, pypi_version, reason, declare)

    if behind and is_pure_python_wheel(pypi_info, pypi_version):
        print(f"[-] {package} v{pypi_version} switched to pure Python wheels only. Can be deprecated.")
        reason = f"{package} v{pypi_version} switched to pure Python wheels only: {pypi_package_url}"
        return deprecation_result(package, registry_version, pypi_version, reason, declare)

    if since is not None:
        print(f"[+] {package}: every release since {since:%Y-%m-%d} is declared or shipped upstream")
    else:
        print(f"[+] {package} v{pypi_version} is up to date")
    return up_to_date


def deprecation_result(package: str, registry_version: str, pypi_version: str, reason: str, declare: bool) -> Dict[str, any]:
    upstream_issue = find_upstream_issue(package)
    if declare and deprecate_package(package):
        print(f"    [+] deprecated {package} in {package_yaml(package).relative_to(ROOT_DIR)}, packages.txt and deprecated.txt")
    return {
        "status": "can_deprecate",
        "package": package,
        "registry_version": registry_version,
        "pypi_version": pypi_version,
        "reason": reason,
        "upstream_issue": upstream_issue,
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
    else:
        print("    (none)")

    yanked = [r for r in results if r.get("yanked")]
    if yanked:
        print(f"\n[!] YANKED UPSTREAM ({len(yanked)} packages):")
        max_name_len = max(len(r["package"]) for r in yanked)
        for result in sorted(yanked, key=lambda x: x["package"]):
            print(f"    {result['package']:<{max_name_len}} {', '.join(f'v{v}' for v in result['yanked'])}")

    if errors:
        print(f"\n[X] ERRORS ({len(errors)} packages):")
        max_name_len = max(len(r["package"]) for r in errors)
        for result in sorted(errors, key=lambda x: x["package"]):
            print(f"    {result['package']:<{max_name_len}} {result['error']}")

    print("\n" + "=" * 80)


def write_report(results: List[Dict[str, any]], path: Path):
    """Markdown summary of the whole run, used as the nightly job summary."""
    upgrades = sorted((r for r in results if r["status"] == "need_upgrade"), key=lambda r: r["package"])
    deprecations = sorted((r for r in results if r["status"] == "can_deprecate"), key=lambda r: r["package"])
    yanked = sorted((r for r in results if r.get("yanked")), key=lambda r: r["package"])
    errors = sorted((r for r in results if r["status"] == "error"), key=lambda r: r["package"])

    lines = [
        "Automatically generated by the nightly `check_versions.py` run. Each package below gets "
        "its own PR, whose `build-<pkg>.yml` run builds it; merging publishes the wheels.",
        "",
    ]
    if upgrades:
        lines += [f"## Upgrades ({len(upgrades)})", ""]
        lines += [f"- **{r['package']}** v{r['registry_version']} -> "
                  + ", ".join(f"v{v}" for v in r["new_versions"]) for r in upgrades]
        lines.append("")
    if deprecations:
        lines += [f"## Deprecations ({len(deprecations)})", "",
                  "Upstream now ships riscv64 wheels; our build is retired.", ""]
        for r in deprecations:
            lines += [f"### {r['package']}", "", r["reason"], ""]
            if r.get("upstream_issue"):
                lines += [f"Fixes #{r['upstream_issue']}", ""]
    if yanked:
        lines += [f"## Yanked upstream ({len(yanked)})", ""]
        lines += [f"- **{r['package']}** " + ", ".join(f"v{v}" for v in r["yanked"]) for r in yanked]
        lines.append("")
    if errors:
        lines += [f"## Errors ({len(errors)})", ""]
        lines += [f"- **{r['package']}**: {r['error']}" for r in errors]
        lines.append("")
    path.write_text("\n".join(lines))


def package_title(result: Dict[str, any]) -> str:
    """Commit subject and PR title for one package's nightly change."""
    package = result["package"]
    if result["status"] == "need_upgrade":
        versions = result["new_versions"]
        return f"{package}: Add version{'s' if len(versions) > 1 else ''} {', '.join(versions)}"
    if result["status"] == "can_deprecate":
        return f"{package}: deprecate our wheel"
    return f"{package}: mark {', '.join(f'v{v}' for v in result['yanked'])} yanked upstream"


def package_report(result: Dict[str, any]) -> str:
    """PR body for one package's nightly change."""
    package = result["package"]
    slug = normalize_name(package)
    lines = ["Automatically generated by the nightly `check_versions.py` run.", ""]

    if result["status"] == "need_upgrade":
        lines += [
            f"**{package}** v{result['registry_version']} -> "
            + ", ".join(f"v{v}" for v in result["new_versions"]),
            "",
            f"Every `- version:` entry added to `docs/packages/{slug}.yaml` is built by this PR's own "
            f"`build-{slug}.yml` run; merging publishes the wheels.",
            "",
        ]
    elif result["status"] == "can_deprecate":
        lines += ["Upstream now ships riscv64 wheels; our build is retired.", "", result["reason"], ""]
        if result.get("upstream_issue"):
            lines += [f"Fixes #{result['upstream_issue']}", ""]

    if result.get("yanked"):
        lines += [
            "## Yanked upstream",
            "",
            ", ".join(f"v{v}" for v in result["yanked"])
            + f" are yanked on PyPI and marked `yanked: true` in `docs/packages/{slug}.yaml`.",
            "",
        ]
    return "\n".join(lines)


def write_reports(results: List[Dict[str, any]], directory: Path) -> List[Dict[str, str]]:
    """
    One Markdown body per package the nightly changes, plus a `packages.json`
    manifest of them, so the workflow can open one PR per package instead of a
    single batch PR.
    """
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for result in sorted(results, key=lambda r: r["package"]):
        if result["status"] not in ("need_upgrade", "can_deprecate") and not result.get("yanked"):
            continue
        slug = normalize_name(result["package"])
        (directory / f"{slug}.md").write_text(package_report(result))
        manifest.append({
            "package": result["package"],
            "slug": slug,
            "status": result["status"],
            "title": package_title(result),
            "body": f"{slug}.md",
        })
    (directory / "packages.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _self_test():
    """Sanity-check has_riscv64_wheel's per-interpreter matching. Run with --self-test."""
    releases = {
        "1.0": [
            {"filename": "pkg-1.0-cp312-cp312-manylinux_2_34_riscv64.whl"},
            {"filename": "pkg-1.0-cp313-cp313-manylinux_2_34_riscv64.whl"},
            {"filename": "pkg-1.0-cp314-cp314-manylinux_2_34_riscv64.whl"},
            {"filename": "pkg-1.0-cp312-abi3-manylinux_2_34_x86_64.whl"},  # not riscv64
        ]
    }
    info = {"releases": releases}
    # Missing 3.14t -> not all target versions covered.
    assert has_riscv64_wheel(info, "1.0") is False
    assert has_riscv64_wheel(info, "1.0", ["3.12", "3.13"]) is True

    releases["1.0"].append({"filename": "pkg-1.0-cp314-cp314t-manylinux_2_34_riscv64.whl"})
    assert has_riscv64_wheel(info, "1.0") is True

    # abi3 wheel covers any cp3X >= its floor, but never a free-threaded target.
    abi3_info = {"releases": {"1.0": [
        {"filename": "pkg-1.0-cp39-abi3-manylinux_2_34_riscv64.whl"},
    ]}}
    assert has_riscv64_wheel(abi3_info, "1.0", ["3.12", "3.13", "3.14"]) is True
    assert has_riscv64_wheel(abi3_info, "1.0", ["3.14t"]) is False

    # Per-package PR titles, one PR per package.
    upgrade = {"status": "need_upgrade", "package": "PyYAML", "registry_version": "6.0",
               "new_versions": ["6.0.1", "6.0.2"], "yanked": []}
    assert package_title(upgrade) == "PyYAML: Add versions 6.0.1, 6.0.2"
    assert package_title({**upgrade, "new_versions": ["6.0.1"]}) == "PyYAML: Add version 6.0.1"
    assert package_title({"status": "can_deprecate", "package": "citiespy"}) == "citiespy: deprecate our wheel"
    assert package_title({"status": "up_to_date", "package": "arch", "yanked": ["1.0"]}) == \
        "arch: mark v1.0 yanked upstream"
    # The body names the package YAML by its normalized name, not PyPI's spelling.
    assert "docs/packages/pyyaml.yaml" in package_report(upgrade)

    print("[+] self-test passed")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Check package versions between riscv64 registry and PyPI")
    parser.add_argument("packages", nargs="*", help="Specific packages to check (default: all packages from packages.txt)")
    parser.add_argument("--since", type=parse_since, metavar="DATE|Nd|Nm",
                        help="Treat every stable release uploaded since this date (YYYY-MM-DD) or duration (e.g. 12m, 90d) "
                             "that docs/packages/<pkg>.yaml does not list as a version to add, uncapped")
    parser.add_argument("--declare", action="store_true",
                        help="Apply the outcome to the working tree: declare new versions and mark yanked ones in "
                             "docs/packages/<pkg>.yaml, deprecate packages in the YAML, packages.txt and deprecated.txt")
    parser.add_argument("--report", type=Path, metavar="FILE", help="Write a Markdown summary of the whole run")
    parser.add_argument("--report-dir", type=Path, metavar="DIR",
                        help="Write one Markdown PR body per changed package, plus a packages.json manifest, "
                             "so the caller can open one PR per package")
    parser.add_argument("--summary", action="store_true", help="Show detailed summary at the end")
    parser.add_argument("--self-test", action="store_true", help="Run internal sanity checks and exit")

    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return

    if args.packages:
        packages = args.packages
        print(f"Checking {len(packages)} specified package(s)...")
    else:
        packages = read_packages()
        print("Checking package versions between riscv64 registry and PyPI...")
        print(f"Found {len(packages)} packages to check")

    results = []
    for package in packages:
        try:
            results.append(check_package(package, since=args.since, declare=args.declare))
        except KeyboardInterrupt:
            print("\n[!] Interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"[X] Error checking {package}: {e}")
            results.append({"status": "error", "package": package, "error": str(e)})

    if args.summary or len(packages) > 5:
        print_summary(results)

    if args.report:
        write_report(results, args.report)

    if args.report_dir:
        manifest = write_reports(results, args.report_dir)
        print(f"\nWrote {len(manifest)} per-package report(s) to {args.report_dir}")

    if any(r["status"] == "error" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
