#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 BayLibre, SAS
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""
Extract metadata from a just-built riscv64 wheel and record its release under
the matching version entry of docs/packages/<name>.yaml on `main`.

The version entry must already be declared (the porter or the nightly upgrade
adds a bare `- version:` line, which is what the build workflow builds); this
script fills every declared target slot under `files` and replaces the complete
release on a rebuild.

generate_packages_doc.py renders this YAML into the published
Markdown pages under docs/project/<name>/, so this script only needs to
maintain the YAML source of truth; it never touches a generated page directly.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from email.message import Message
from email.parser import Parser
from pathlib import Path

import yaml

from github_issues import REPO, normalize_name
CI_SCRIPTS_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = (CI_SCRIPTS_DIR / ".." / "docs" / "packages").resolve()
ARTIFACTS_PATH = os.environ.get("ARTIFACTS_PATH", "dist")
RELEASE_TAG = os.environ.get("RELEASE_TAG")
GPL_SOURCES_DESCRIPTION = os.environ.get("GPL_SOURCES_DESCRIPTION", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() == "true"
GH_TOKEN = os.environ.get("GH_TOKEN", "")
BUILD_MATRIX = json.loads(os.environ.get("BUILD_MATRIX", "[]"))


def find_wheel_files(path):
    return sorted(Path(path).glob("*.whl"))


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


def python_version_from_wheel(filename):
    """Return (target, platform) encoded by a Linux wheel filename."""
    parts = filename.removesuffix(".whl").split("-")
    if len(parts) < 5:
        raise SystemExit(f"cannot parse wheel tags from {filename}")
    python_tag, abi_tag, platform_tag = parts[-3:]
    platforms = {
        "manylinux" if tag.startswith("manylinux") else "musllinux"
        for tag in platform_tag.split(".")
        if tag.startswith(("manylinux", "musllinux"))
    }
    if len(platforms) != 1:
        raise SystemExit(f"{filename} does not identify one Linux platform family")
    platform = platforms.pop()
    if abi_tag == "abi3" and re.fullmatch(r"cp3\d+", python_tag):
        target = f"3.{python_tag[3:]}-abi3"
    elif re.fullmatch(r"cp3\d+", python_tag) and abi_tag in (python_tag, python_tag + "t"):
        target = f"3.{abi_tag[3:]}"
    elif python_tag in ("py3", "py2.py3") and abi_tag == "none":
        target = None
    else:
        raise SystemExit(f"cannot map {filename} to a python target")
    return (f"{target}:{platform}" if target else None), platform


def extract_metadata_from_whl(whl_path):
    """
    Extract metadata according to https://packaging.python.org/en/latest/specifications/core-metadata/
    """
    with zipfile.ZipFile(whl_path, "r") as z:
        metadata_file = next(f for f in z.namelist() if f.endswith("METADATA"))
        content = z.read(metadata_file).decode()
        message: Message = Parser().parsestr(content)
        python_version, platform = python_version_from_wheel(whl_path.name)
        return {
            "name": message.get("Name"),
            "version": message.get("Version"),
            "license": extract_license(message),
            "python": python_version,
            "platform": platform,
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
        if metadata["python"]:
            file_data["python"] = metadata["python"]
        else:
            file_data["platform"] = metadata["platform"]
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


def version_blocks(lines):
    """Yield the [start, end) line ranges of each `versions:` list item."""
    start = None
    for i, line in enumerate(lines):
        if line.startswith("- "):
            if start is not None:
                yield start, i
            start = i
    if start is not None:
        yield start, len(lines)


def merge_publication_files(declared_files, published_files, effective_targets):
    """Fill target slots and require completeness for this run's effective matrix."""
    if not effective_targets:
        raise SystemExit("effective target list is empty or was not provided")
    published_by_target = {
        item["python"]: item
        for item in published_files
        if item.get("python")
    }
    pure_by_platform = {
        item["platform"]: item for item in published_files if item.get("platform")
    }
    merged = []
    for slot in declared_files:
        target = slot["python"]
        platform = target.rsplit(":", 1)[1]
        published = published_by_target.get(target) or pure_by_platform.get(platform)
        merged.append({"python": target, **(published or {})})
    unknown = set(published_by_target) - {item["python"] for item in declared_files}
    if unknown:
        raise SystemExit(
            "built wheels have undeclared python targets: " + ", ".join(sorted(unknown))
        )
    declared_targets = {item["python"] for item in declared_files}
    unknown_effective = effective_targets - declared_targets
    if unknown_effective:
        raise SystemExit(
            "effective matrix has undeclared python targets: "
            + ", ".join(sorted(unknown_effective))
        )
    missing = [
        item["python"]
        for item in merged
        if item["python"] in effective_targets and "filename" not in item
    ]
    if missing:
        raise SystemExit(
            "release is incomplete; no wheel was built for: " + ", ".join(missing)
        )
    return merged


def append_version(
    content, package_data, version, license, patch_dir, publication, comment=None
):
    """
    Fill in the publication metadata of the declared `versions:` entry for
    this version, preserving the rest of the file byte-for-byte.

    A pending entry has one or more target slots without `filename`; publishing
    requires and fills every slot. An already-released entry has its publication
    metadata replaced by the latest tag: older immutable GitHub Releases remain
    available for tracking, but only the latest release is exposed through the
    package YAML and Simple API.
    """
    existing_version = next(
        (
            item
            for item in (package_data.get("versions") or [])
            if str(item.get("version")) == str(version)
        ),
        None,
    )
    if existing_version is None:
        raise SystemExit(
            f"version {version} is not declared in the package YAML; add a "
            f"`- version: {version}` entry under `versions:` and rebuild"
        )

    declared_files = existing_version.get("files") or []
    if not declared_files:
        raise SystemExit(f"version {version} has no declared target files")
    effective_targets = {
        item["target"]
        for item in BUILD_MATRIX
        if str(item.get("version")) == str(version) and item.get("target")
    }
    publication["files"] = merge_publication_files(
        declared_files, publication["files"], effective_targets
    )

    publication_keys = ("tag", "files", "gpl-sources")
    if any(key in existing_version for key in publication_keys):
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

    lines = content.splitlines()
    block = next(
        (
            (start, end)
            for start, end in version_blocks(lines)
            if str(yaml.safe_load("\n".join(lines[start:end]))[0].get("version"))
            == str(version)
        ),
        None,
    )
    if block is None:
        raise SystemExit(f"could not locate the `- version: {version}` entry")
    start, end = block
    while end > start and not lines[end - 1].strip():
        end -= 1

    top_level_license = package_data.get("license")
    new_lines = []
    if patch_dir is not None and "patched" not in existing_version:
        new_lines.append("  patched: true")
    if (
        license
        and license != top_level_license
        and license not in VAGUE_LICENSES
        and "license" not in existing_version
    ):
        new_lines.append(f"  {yaml_line('license', license)}")
    if comment and "comment" not in existing_version:
        new_lines.append(f"  {yaml_line('comment', comment)}")
    publication_yaml = yaml.safe_dump(
        publication, sort_keys=False, allow_unicode=True
    ).rstrip("\n")
    new_lines.extend(f"  {line}" for line in publication_yaml.splitlines())

    lines[end:end] = new_lines
    return "\n".join(lines) + "\n"


def git_run(*args, check=True):
    return subprocess.run(["git", *args], check=check)


def checkout_main():
    """Check out the latest `origin/main`, starting from a depth-one checkout."""
    git_run("fetch", "--depth=1", "origin", "+refs/heads/main:refs/remotes/origin/main")
    git_run("switch", "--force-create", "main", "origin/main")


def push_main():
    """Push HEAD to main, rebasing and retrying when another push wins a race."""
    remote = (
        f"https://x-access-token:{GH_TOKEN}@github.com/{REPO}" if GH_TOKEN else "origin"
    )
    for attempt in range(1, 6):
        result = git_run("push", remote, "HEAD:main", check=False)
        if result.returncode == 0:
            return
        if attempt == 5:
            break
        print(f"push rejected; rebasing onto the latest main ({attempt}/5)")
        git_run(
            "fetch", "--depth=100", "origin", "+refs/heads/main:refs/remotes/origin/main"
        )
        if git_run("rebase", "origin/main", check=False).returncode != 0:
            git_run("rebase", "--abort", check=False)
            raise SystemExit("could not rebase the publication commit onto main")
    raise SystemExit("could not push the publication commit to main after 5 attempts")


def configure_git_identity():
    subprocess.run([CI_SCRIPTS_DIR / "git-identity.sh"], check=True)


def main(validate_only=False):
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
    publication = publication_metadata(
        RELEASE_TAG, wheel_metadata, GPL_SOURCES_DESCRIPTION
    )

    slug = normalize_name(display_name)
    patch_dir = find_patch_dir(slug, version)
    comment = None
    yaml_path = DOCS_DIR / f"{slug}.yaml"

    def compute_content():
        """Read the current YAML and return (old_content, new_content)."""
        if not yaml_path.exists():
            raise SystemExit(
                f"{yaml_path} does not exist; a package's first PR must add it "
                "(see docs/development.md)"
            )
        old_content = yaml_path.read_text()
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
        return old_content, new_content

    if validate_only:
        old_content, new_content = compute_content()
        if new_content is None:
            print(f"{slug} {version} is already documented; nothing to validate")
        else:
            print(f"Validated complete wheel set for {slug} {version}")
        return

    if DRY_RUN:
        old_content, new_content = compute_content()
        if new_content is None:
            print(f"{slug} {version} is already documented; nothing to do")
            return
        print("[dry-run] Not on main branch; no commit will be pushed.")
        print(f"[dry-run] Would write {yaml_path}:")
        diff = difflib.unified_diff(
            (old_content or "").splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=str(yaml_path) if old_content is not None else "/dev/null",
            tofile=str(yaml_path),
        )
        sys.stdout.writelines(diff)
        print("[dry-run] Would commit this change and push it directly to main")
        return

    configure_git_identity()
    checkout_main()

    # Compute the change against the latest main so concurrent changes are retained.
    _old_content, new_content = compute_content()
    if new_content is None:
        print(f"{slug} {version} is already documented; nothing to do")
        return

    yaml_path.write_text(new_content)
    git_run("add", str(yaml_path))

    git_run("commit", "-s", "-m", f"docs: update {slug}\n\nAdd version {version}")

    push_main()
    print(f"[+] Pushed publication metadata for {slug} {version} to main")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    main(parser.parse_args().validate_only)
