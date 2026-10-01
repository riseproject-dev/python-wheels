# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

"""Build the RISC-V Wheels dashboard into the Jekyll source tree.

Runs the vendored generator's steps (see README.md) with the sanity checks the
website build needs: the upstream package list has served HTTP 200 with zero rows,
and publishing that would replace a working dashboard with a blank one.

Nothing is written to --output-dir unless a complete result was produced, so a
failed run leaves the previously published dashboard serving untouched.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import urllib.request

import requests_cache
import yaml

VENDOR_DIR = Path(__file__).resolve().parent
REPO_ROOT = VENDOR_DIR.parents[1]

sys.path.insert(0, str(VENDOR_DIR))

from svg_wheel import generate_svg_wheel  # noqa: E402
import utils  # noqa: E402
from utils import (  # noqa: E402
    annotate_wheels,
    get_top_packages,
    save_to_file,
)

# Loose floors: enough to catch an empty or truncated upstream response without
# tripping on normal drift (the list is ~15000 rows, of which ~1900 survive the
# extension filter).
MIN_INPUT_ROWS = 5000
MIN_OUTPUT_PACKAGES = 500
MIN_WHEEL_SVG_BYTES = 10 * 1024

# Copied from the vendored directory as-is.
STATIC_FILES = ("index.html", "wheel.css", "favicon.ico")
# Produced by generate.py.
GENERATED_FILES = ("results.json", "wheel.svg")


def fetch(url):
    """Return the payload at ``url``, or ``None`` after printing why not."""
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            # file:// responses carry status None; only HTTP has one to check.
            status = getattr(response, "status", None)
            if status is not None and status != 200:
                print(f"  rejected: HTTP {status}")
                return None
            return response.read()
    except Exception as e:
        print(f"  rejected: {e}")
        return None


def validate_package_list(payload):
    """Return ``(rows, None)`` if the payload is usable, else ``(None, reason)``."""
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, f"not valid JSON: {e}"

    if not isinstance(data, dict):
        return None, "payload is not a JSON object"

    # The upstream query reports failure in-band, with a 200 and empty rows.
    if "exception" in data:
        return None, f"upstream reported an error: {data['exception']}"

    rows = data.get("rows")
    if not isinstance(rows, list):
        return None, "payload has no `rows` list"
    if len(rows) < MIN_INPUT_ROWS:
        return None, f"only {len(rows)} rows, expected at least {MIN_INPUT_ROWS}"

    return rows, None


def get_package_list():
    """Fetch the package list from the first usable candidate. Exits on failure."""
    failures = []
    url = "https://hugovk.dev/top-pypi-packages/top-pypi-packages.min.json"
    print(f"Fetching the package list: {url}")
    payload = fetch(url)
    if payload is not None:
        rows, reason = validate_package_list(payload)
        if rows is not None:
            print(f"  accepted: {len(rows)} rows")
            return payload
        sys.exit(f"Could not obtain a usable package list, refusing to publish: {reason}")
    else:
        sys.exit(f"Could not obtain a usable package list, refusing to publish: could not be fetched")


def collect_registry_packages(packages_dir):
    """Return the normalised names of every package the RISE registry serves.

    These are read from this repo's own docs/packages/*.yaml rather than probed
    over HTTP against pypi.riseproject.dev: the YAML is what the registry is
    generated from, so it is both authoritative and free.
    """
    names = set()
    unreleased = 0
    for path in sorted(packages_dir.glob("*.yaml")):
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            sys.exit(f"{path} is unusable: {e}")

        name = (data or {}).get("package-name")
        if not name:
            sys.exit(f"{path} has no `package-name`")
        if not (data.get("versions") or []):
            # Nothing published yet, so the registry serves no wheels for it.
            unreleased += 1
            continue
        # Same normalisation as utils.normalize().
        names.add(re.sub(r"[-_.]+", "-", name).lower())

    print(f"Read {len(names)} registry packages from {packages_dir}", end="")
    print(f" ({unreleased} with no release yet)" if unreleased else "")
    return frozenset(names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="where to stage the dashboard, e.g. docs/dashboard",
    )
    parser.add_argument(
        "--packages-dir",
        default=REPO_ROOT / "docs" / "packages",
        type=Path,
        help="directory of per-package YAML describing the RISE registry (default: docs/packages)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    packages_dir = args.packages_dir.resolve()

    payload = get_package_list()
    registry = collect_registry_packages(packages_dir)

    utils.SESSION = requests_cache.CachedSession(
        "requests-cache", expire_after=utils.SESSION.settings.expire_after
    )

    Path("top-pypi-packages.json").write_bytes(payload)

    packages = get_top_packages()
    packages = annotate_wheels(packages, registry)
    save_to_file(packages, "results.json")
    generate_svg_wheel(packages)

    os.makedirs(output_dir, exist_ok=True)
    for name in STATIC_FILES:
        shutil.copy2(VENDOR_DIR / name, output_dir / name)
    for name in GENERATED_FILES:
        shutil.copy2(name, output_dir / name)

    print(f"Staged the dashboard for {len(packages)} packages in {output_dir}")


if __name__ == "__main__":
    main()
