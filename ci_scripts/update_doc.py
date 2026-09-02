#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 BayLibre, SAS
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""
Extract metadata from a just-built riscv64 wheel, add or update the
corresponding docs/packages/<name>.yaml entry with the new version, and open
a pull request with the change.

generate_packages_doc.py renders this YAML into the published
Markdown pages, so this script only needs to maintain the YAML source of
truth; it never touches docs/packages/*.md or index.md directly.
"""

import difflib
import hashlib
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
CI_SCRIPTS_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = (CI_SCRIPTS_DIR / ".." / "docs" / "packages").resolve()
PACKAGES_FILE = CI_SCRIPTS_DIR / "packages.txt"
ARTIFACTS_PATH = os.environ.get("ARTIFACTS_PATH", "dist")
RELEASE_TAG = os.environ.get("RELEASE_TAG")
GPL_SOURCES_DESCRIPTION = os.environ.get("GPL_SOURCES_DESCRIPTION", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() == "true"


def find_wheel_files(path):
    return sorted(Path(path).glob("*.whl"))


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
            "filename": whl_path.name,
            "sha256": hashlib.sha256(whl_path.read_bytes()).hexdigest(),
            "requires-python": message.get("Requires-Python"),
        }


def publication_metadata(release_tag, wheel_metadata, gpl_sources_description=""):
    files = []
    for metadata in wheel_metadata:
        file_data = {
            "filename": metadata["filename"],
            "sha256": metadata["sha256"],
        }
        if metadata["requires-python"]:
            file_data["requires-python"] = metadata["requires-python"]
        files.append(file_data)
    publication = {"tag": release_tag, "files": files}
    if gpl_sources_description:
        publication["gpl-sources"] = {
            "filename": "gpl-sources.tar",
            "description": gpl_sources_description,
        }
    return publication


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


def render_new_yaml(
    slug, source_code, license, version, patch_dir, publication, comment=None
):
    """Render a brand-new docs/packages/<slug>.yaml for a package's first version."""
    lines = [yaml_line("package-name", slug)]
    if source_code:
        lines.append(yaml_line("source-code", source_code))
    lines.append(yaml_line("license", license))
    lines.append("versions:")
    lines.append(f"  - {yaml_line('version', version)}")
    if patch_dir is not None:
        lines.append("    patched: true")
    if comment:
        lines.append(f"    {yaml_line('comment', comment)}")
    publication_yaml = yaml.safe_dump(
        publication, sort_keys=False, allow_unicode=True
    ).rstrip("\n")
    lines.extend(f"    {line}" for line in publication_yaml.splitlines())
    return "\n".join(lines) + "\n"


def append_version(
    content, package_data, version, license, patch_dir, publication, comment=None
):
    """
    Append a new version entry to the end of an existing package YAML file's
    `versions:` list, preserving the rest of the file byte-for-byte.

    An existing version's publication metadata is replaced by the latest tag.
    Older immutable GitHub Releases remain available for tracking, but only the
    latest release is exposed through the package YAML and Simple API.
    """
    existing_version = next(
        (
            item
            for item in (package_data.get("versions") or [])
            if str(item.get("version")) == str(version)
        ),
        None,
    )
    if existing_version is not None:
        publication_keys = ("tag", "files", "gpl-sources")
        current = {
            key: existing_version[key]
            for key in publication_keys
            if key in existing_version
        }
        if current == publication:
            return None
        for key in publication_keys:
            existing_version.pop(key, None)
        existing_version.update(publication)
        return yaml.safe_dump(package_data, sort_keys=False, allow_unicode=True)

    top_level_license = package_data.get("license")
    lines = [f"  - {yaml_line('version', version)}"]
    if patch_dir is not None:
        lines.append("    patched: true")
    if license and license != top_level_license and license not in VAGUE_LICENSES:
        lines.append(f"    {yaml_line('license', license)}")
    if comment:
        lines.append(f"    {yaml_line('comment', comment)}")
    publication_yaml = yaml.safe_dump(
        publication, sort_keys=False, allow_unicode=True
    ).rstrip("\n")
    lines.extend(f"    {line}" for line in publication_yaml.splitlines())

    return content.rstrip("\n") + "\n" + "\n".join(lines) + "\n"


def add_to_packages_file(slug):
    lines = PACKAGES_FILE.read_text().splitlines()
    header_end = next(
        i for i, line in enumerate(lines) if line and not line.startswith("#")
    )
    header, entries = lines[:header_end], [line for line in lines[header_end:] if line]
    entries = sorted(set(entries) | {slug}, key=str.casefold)
    PACKAGES_FILE.write_text("\n".join(header + entries) + "\n")


def git_run(*args, check=True):
    return subprocess.run(["git", *args], check=check)


def checkout_shared_branch(branch):
    """
    Check out the shared docs branch as a local worktree HEAD, based on
    origin/<branch> if it already exists, otherwise on origin/main.

    All docs updates are pushed to this single branch, so a run needs to build
    on whatever is already there rather than starting from main each time.
    """
    git_run("fetch", "origin")
    remote_ref = f"origin/{branch}"
    exists = (
        git_run("rev-parse", "--verify", "--quiet", remote_ref, check=False).returncode
        == 0
    )
    base = remote_ref if exists else "origin/main"
    git_run("switch", "--force-create", branch, base)


def pr_exists(branch):
    """Return True if an open PR already targets this branch as its head."""
    out = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            REPO,
            "--head",
            branch,
            "--state",
            "open",
            "--json",
            "number",
            "--jq",
            "length",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return out.isdigit() and int(out) > 0


def configure_git_identity():
    git_run("config", "user.name", "github-actions[bot]")
    git_run(
        "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"
    )


def extract_pr_url(stdout):
    for line in stdout.split("\n"):
        line = line.strip()
        if "github.com" in line and "/pull/" in line:
            return line
    return None


def main():
    wheel_files = find_wheel_files(ARTIFACTS_PATH)
    if not wheel_files:
        print(f"No .whl file found in {ARTIFACTS_PATH}")
        sys.exit(1)
    if not RELEASE_TAG:
        print("RELEASE_TAG must be set")
        sys.exit(1)

    wheel_metadata = [extract_metadata_from_whl(path) for path in wheel_files]
    names = {normalize_name(item["name"]) for item in wheel_metadata if item["name"]}
    versions = {item["version"] for item in wheel_metadata if item["version"]}
    if len(names) != 1 or len(versions) != 1:
        print("Wheels contain mixed or missing package names or versions")
        sys.exit(1)

    metadata = wheel_metadata[0]
    display_name = metadata["name"]
    version = metadata["version"]
    license = metadata["license"]
    source_code = metadata["source_code"]
    publication = publication_metadata(
        RELEASE_TAG, wheel_metadata, GPL_SOURCES_DESCRIPTION
    )

    slug = normalize_name(display_name)
    patch_dir = find_patch_dir(slug, version)
    comment = None
    yaml_path = DOCS_DIR / f"{slug}.yaml"

    branch = "github-actions/update-doc"
    pr_title = "docs: Update projects"

    def compute_content():
        """Read the current YAML (if any) and return (is_new, old_content, new_content)."""
        is_new = not yaml_path.exists()
        old_content = None if is_new else yaml_path.read_text()
        if is_new:
            new_content = render_new_yaml(
                slug, source_code, license, version, patch_dir, publication, comment
            )
        else:
            package_data = yaml.safe_load(old_content) or {}
            new_content = append_version(
                old_content,
                package_data,
                version,
                license,
                patch_dir,
                publication,
                comment,
            )
        return is_new, old_content, new_content

    if DRY_RUN:
        is_new, old_content, new_content = compute_content()
        if new_content is None:
            print(f"{slug} {version} is already documented; nothing to do")
            return
        print(
            "[dry-run] Not on main branch — no branch, commit, or PR will be created."
        )
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
        print(
            f"[dry-run] Would open PR '{pr_title}' from branch '{branch}' against main"
        )
        return

    configure_git_identity()
    checkout_shared_branch(branch)

    # Compute the change against the shared branch's contents, so a package
    # already documented there by an earlier run in this batch is seen.
    is_new, _old_content, new_content = compute_content()
    if new_content is None:
        print(f"{slug} {version} is already documented; nothing to do")
        return

    yaml_path.write_text(new_content)
    git_run("add", str(yaml_path))

    if is_new:
        add_to_packages_file(slug)
        git_run("add", str(PACKAGES_FILE))
        git_run("commit", "-s", "-m", f"docs: add {slug}\n\nAdd version {version}")
    else:
        git_run("commit", "-s", "-m", f"docs: update {slug}\n\nAdd version {version}")

    git_run("push", "origin", f"HEAD:{branch}")

    if pr_exists(branch):
        print(f"[+] PR already open for branch '{branch}'; pushed update")
        return

    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            REPO,
            "--base",
            "main",
            "--head",
            branch,
            "--reviewer",
            "threexc,justeph,luhenry",
            "--title",
            pr_title,
            "--body",
            "Automatically generated PR to document newly published wheels. "
            "Please review it carefully before merging.\n\n"
            "If necessary, force-push this branch.",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    pr_url = extract_pr_url(result.stdout)
    print(f"[+] Opened PR: {pr_url or '(URL not found in output)'}")


if __name__ == "__main__":
    main()
