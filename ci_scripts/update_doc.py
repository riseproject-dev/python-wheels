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

import difflib
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
GPL_SOURCES_URL = os.environ.get("GPL_SOURCES_URL")
GPL_SOURCES_DESCRIPTION = os.environ.get("GPL_SOURCES_DESCRIPTION", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() == "true"


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


# "License :: OSI Approved :: BSD License" -> "BSD"
TROVE_LICENSE_PREFIX = "License :: "


def license_from_classifiers(message):
    for classifier in message.get_all("Classifier", []):
        if not classifier.startswith(TROVE_LICENSE_PREFIX):
            continue
        name = classifier.rsplit(" :: ", 1)[-1].strip()
        if name and name != "OSI Approved":
            return name
    return None


def extract_license(message):
    """
    Core metadata < 2.4 allows the whole licence text in `License`, and projects
    such as scipy ship exactly that. Only take that field when it is a short
    identifier; otherwise fall back to the trove classifier, which stays short.
    """
    license = message.get("License-Expression")
    if license:
        return license

    license = message.get("License")
    if license and "\n" not in license.strip() and len(license.strip()) <= 64:
        return license.strip()

    return license_from_classifiers(message) or "Unknown"


# Trove names that say a family rather than a licence. They are good enough for a
# brand-new package's top-level entry but cannot establish that a version's licence
# changed, so a per-version key is not worth emitting for them.
VAGUE_LICENSES = frozenset(
    {
        "BSD License",
        "Apache Software License",
        "MIT License",
        "GNU General Public License (GPL)",
        "GNU Lesser General Public License v2 or later (LGPLv2+)",
        "Python Software Foundation License",
    }
)


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


def render_gpl_sources_comment():
    """
    Render a doc comment linking to a permanently-hosted GPL sources
    artifact (e.g. a manylinux toolchain's src.rpm), if the calling workflow
    published one for this build.
    """
    if not GPL_SOURCES_URL:
        return None
    suffix = f" ({GPL_SOURCES_DESCRIPTION})" if GPL_SOURCES_DESCRIPTION else ""
    return f"`Link <{GPL_SOURCES_URL}>`__ to sources of bundled GPL libraries{suffix}"


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


def render_new_yaml(slug, source_code, license, version, patch_dir, comment=None):
    """Render a brand-new docs/packages/<slug>.yaml for a package's first version."""
    lines = [yaml_line("package-name", slug)]
    if source_code:
        lines.append(yaml_line("source-code", source_code))
    lines.append(yaml_line("license", license))
    lines.append("versions:")
    lines.append(f"  - {yaml_line('version', version)}")
    if patch_dir is not None:
        lines.append("    patched:")
    if comment:
        lines.append(f"    {yaml_line('comment', comment)}")
    return "\n".join(lines) + "\n"


def append_version(content, package_data, version, license, patch_dir, comment=None):
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
    if license and license != top_level_license and license not in VAGUE_LICENSES:
        lines.append(f"    {yaml_line('license', license)}")
    if comment:
        lines.append(f"    {yaml_line('comment', comment)}")

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
    comment = render_gpl_sources_comment()
    yaml_path = DOCS_DIR / f"{slug}.yaml"
    is_new = not yaml_path.exists()
    old_content = None if is_new else yaml_path.read_text()

    if is_new:
        new_content = render_new_yaml(slug, source_code, license, version, patch_dir, comment)
    else:
        package_data = yaml.safe_load(old_content) or {}
        new_content = append_version(
            old_content, package_data, version, license, patch_dir, comment
        )
        if new_content is None:
            print(f"{slug} {version} is already documented; nothing to do")
            return

    branch = f"github-actions/{'add' if is_new else 'update'}-doc-for-{slug}"
    pr_title = f"docs: {'add' if is_new else 'update'} {slug}"

    if DRY_RUN:
        print("[dry-run] Not on main branch — no branch, commit, or PR will be created.")
        print(f"[dry-run] Would write {yaml_path}:")
        diff = difflib.unified_diff(
            (old_content or "").splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=str(yaml_path) if old_content is not None else "/dev/null",
            tofile=str(yaml_path),
        )
        sys.stdout.writelines(diff)
        if is_new:
            print(f"[dry-run] Would add '{slug}' to {PACKAGES_FILE}")
        print(f"[dry-run] Would open PR '{pr_title}' from branch '{branch}' against main")
        return

    yaml_path.write_text(new_content)
    configure_git_identity()

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
            "--title", pr_title,
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
