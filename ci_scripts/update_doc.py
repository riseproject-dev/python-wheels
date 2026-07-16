#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 BayLibre, SAS
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""
Extract metadata from a just-built riscv64 wheel, add or update the
corresponding docs/packages/<name>.yaml entry with the new version, and open
a pull request with the change.

docs/packages/generate_packages_doc.py renders this YAML into the published
Markdown pages, so this script only needs to maintain the YAML source of
truth; it never touches docs/packages/*.md or index.md directly.
"""

import os
import re
import string
import subprocess
import sys
import zipfile
from email.message import Message
from email.parser import Parser
from pathlib import Path

import yaml

REPO = "riseproject-dev/python-wheels"
DOCS_DIR = Path("docs/packages")
PACKAGES_FILE = Path("ci_scripts/packages.txt")
ARTIFACTS_PATH = os.environ.get("ARTIFACTS_PATH", "dist")


def find_wheel_file(path):
    for file in Path(path).glob("*.whl"):
        return file
    return None


def normalize_name(name):
    """
    https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def normalize_label(label):
    """
    https://packaging.python.org/en/latest/specifications/well-known-project-urls/#label-normalization
    """
    chars_to_remove = string.punctuation + string.whitespace
    removal_map = str.maketrans("", "", chars_to_remove)
    return label.translate(removal_map).lower()


def extract_license(message):
    license = message.get("License-Expression")
    if not license:
        license = message.get("License", "Unknown")
    return license


def extract_source_code_url(message):
    # Collect all "Project-URL" lines
    project_urls = message.get_all("Project-URL", [])
    well_known_labels = ["source", "repository", "sourcecode", "github"]

    for entry in project_urls:
        try:
            label, url = map(str.strip, entry.split(",", 1))
            if normalize_label(label) in well_known_labels:
                return url
        except ValueError:
            continue  # skip malformed lines

    # A lot of projects use homepage as source code url. Done in a second
    # loop so a homepage entry appearing before a well-known source label
    # doesn't win by accident.
    for entry in project_urls:
        try:
            label, url = map(str.strip, entry.split(",", 1))
            if normalize_label(label) == "homepage":
                return url
        except ValueError:
            continue

    return message.get("Home-page")  # deprecated fallback, may be None


def extract_metadata_from_whl(whl_path):
    """
    Extract metadata according to https://packaging.python.org/en/latest/specifications/core-metadata/
    """
    with zipfile.ZipFile(whl_path, "r") as z:
        metadata_file = next(f for f in z.namelist() if f.endswith("METADATA"))
        content = z.read(metadata_file).decode()
        message: Message = Parser().parsestr(content)
        return {
            "name": message.get("Name"),
            "version": message.get("Version"),
            "license": extract_license(message),
            "source_code": extract_source_code_url(message),
        }


def find_patch_dir(slug, version):
    """
    Look for a `patches/<slug>/<version_tag>` directory as described in
    docs/development.md, trying both a `v`-prefixed and bare version tag.
    """
    for tag in (f"v{version}", version):
        candidate = Path("patches") / slug / tag
        if candidate.exists():
            return candidate
    return None


def yaml_line(key, value):
    """Render a single `key: value` YAML mapping line, quoted as needed."""
    return yaml.safe_dump(
        {key: value}, default_flow_style=False, allow_unicode=True
    ).rstrip("\n")


def render_new_yaml(slug, source_code, license, version, patch_dir):
    """Render a brand-new docs/packages/<slug>.yaml for a package's first version."""
    lines = [yaml_line("package-name", slug)]
    if source_code:
        lines.append(yaml_line("source-code", source_code))
    lines.append(yaml_line("license", license))
    lines.append("versions:")
    lines.append(f"  - {yaml_line('version', version)}")
    if patch_dir is not None:
        lines.append("    patched:")
    return "\n".join(lines) + "\n"


def append_version(content, package_data, version, license, patch_dir):
    """
    Append a new version entry to the end of an existing package YAML file's
    `versions:` list, preserving the rest of the file byte-for-byte.

    Returns None if this exact version is already documented.
    """
    existing_versions = {
        str(v.get("version")) for v in (package_data.get("versions") or [])
    }
    if str(version) in existing_versions:
        return None

    top_level_license = package_data.get("license")
    lines = [f"  - {yaml_line('version', version)}"]
    if patch_dir is not None:
        lines.append("    patched:")
    if license and license != top_level_license:
        lines.append(f"    {yaml_line('license', license)}")

    return content.rstrip("\n") + "\n" + "\n".join(lines) + "\n"


def add_to_packages_file(slug):
    lines = PACKAGES_FILE.read_text().splitlines()
    header_end = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
    header, entries = lines[:header_end], [line for line in lines[header_end:] if line]
    entries = sorted(set(entries) | {slug}, key=str.casefold)
    PACKAGES_FILE.write_text("\n".join(header + entries) + "\n")


def git_run(*args):
    subprocess.run(["git", *args], check=True)


def configure_git_identity():
    git_run("config", "user.name", "github-actions[bot]")
    git_run("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")


def extract_pr_url(stdout):
    for line in stdout.split("\n"):
        line = line.strip()
        if "github.com" in line and "/pull/" in line:
            return line
    return None


def main():
    whl_file = find_wheel_file(ARTIFACTS_PATH)
    if not whl_file:
        print(f"No .whl file found in {ARTIFACTS_PATH}")
        sys.exit(1)

    metadata = extract_metadata_from_whl(whl_file)
    display_name = metadata["name"]
    version = metadata["version"]
    license = metadata["license"]
    source_code = metadata["source_code"]

    if not display_name or not version:
        print("Name or version could not be extracted")
        sys.exit(1)

    slug = normalize_name(display_name)
    patch_dir = find_patch_dir(slug, version)
    yaml_path = DOCS_DIR / f"{slug}.yaml"
    is_new = not yaml_path.exists()

    if is_new:
        yaml_path.write_text(
            render_new_yaml(slug, source_code, license, version, patch_dir)
        )
    else:
        content = yaml_path.read_text()
        package_data = yaml.safe_load(content) or {}
        updated = append_version(content, package_data, version, license, patch_dir)
        if updated is None:
            print(f"{slug} {version} is already documented; nothing to do")
            return
        yaml_path.write_text(updated)

    configure_git_identity()

    branch = f"github-actions/{'add' if is_new else 'update'}-doc-for-{slug}"
    git_run("switch", "-c", branch)
    git_run("add", str(yaml_path))

    if is_new:
        add_to_packages_file(slug)
        git_run("add", str(PACKAGES_FILE))
        git_run("commit", "-s", "-m", f"docs: add {slug}\n\nAdd version {version}")
    else:
        git_run("commit", "-s", "-m", f"docs: update {slug}\n\nAdd version {version}")

    git_run("push", "origin", branch)

    result = subprocess.run(
        [
            "gh", "pr", "create", "--draft",
            "--repo", REPO,
            "--base", "main",
            "--head", branch,
            "--reviewer", "threexc,justeph",
            "--title", f"docs: {'add' if is_new else 'update'} {slug}",
            "--body",
            "Automatically generated PR to document a newly published wheel. "
            "Please review it carefully before merging.\n\n"
            "If necessary, force-push this branch.",
        ],
        capture_output=True, text=True, check=True,
    )
    pr_url = extract_pr_url(result.stdout)
    print(f"[+] Opened PR: {pr_url or '(URL not found in output)'}")


if __name__ == "__main__":
    main()
