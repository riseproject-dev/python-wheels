# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

"""Build the RISC-V Wheels dashboard into the Jekyll source tree.

Wraps the vendored generator (see README.md) with the sanity checks the website
build needs: the upstream package list has served HTTP 200 with zero rows, and
publishing that would replace a working dashboard with a blank one.

Nothing is written to --output-dir unless a complete result was produced, so a
failed run leaves the previously published dashboard serving untouched.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

VENDOR_DIR = Path(__file__).resolve().parent

UPSTREAM_LIST_URL = "https://hugovk.dev/top-pypi-packages/top-pypi-packages.min.json"
# The upstream endpoint is a live query and has returned HTTP 200 carrying an
# empty `rows` plus a ClickHouse row-limit `exception`. This pinned copy of the
# same file is committed upstream and regenerated monthly, so falling back to it
# costs at most one month of ranking drift.
FALLBACK_LIST_URL = (
    "https://raw.githubusercontent.com/hugovk/top-pypi-packages/"
    "6becf8c3b/top-pypi-packages.min.json"
)

# Loose floors: enough to catch an empty or truncated upstream response without
# tripping on normal drift (the list is ~15000 rows, of which ~1900 survive the
# extension filter).
MIN_INPUT_ROWS = 5000
MIN_OUTPUT_PACKAGES = 500
MIN_WHEEL_SVG_BYTES = 10 * 1024

# Copied from the vendored directory as-is.
STATIC_FILES = ("index.html", "wheel.css", "favicon.ico")
# Produced by generate.py in the build directory.
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


def get_package_list(candidates):
    """Fetch the package list from the first usable candidate. Exits on failure."""
    failures = []
    for label, url in candidates:
        print(f"Fetching the {label} package list: {url}")
        payload = fetch(url)
        if payload is not None:
            rows, reason = validate_package_list(payload)
            if rows is not None:
                print(f"  accepted: {len(rows)} rows")
                if label == "pinned":
                    print(
                        "::warning::The upstream package list was unusable; "
                        "using the pinned copy, so the download rankings may be "
                        "up to a month old."
                    )
                return payload
            print(f"  rejected: {reason}")
            failures.append(f"{label}: {reason}")
        else:
            failures.append(f"{label}: could not be fetched")

    sys.exit(
        "Could not obtain a usable package list, refusing to publish:\n  "
        + "\n  ".join(failures)
    )


def validate_output(build_dir):
    """Exit unless the generator produced a complete, sane result."""
    results = build_dir / "results.json"
    try:
        with open(results, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"{results} is unusable: {e}")

    packages = data.get("data")
    if not isinstance(packages, list):
        sys.exit(f"{results} has no `data` list")
    if len(packages) < MIN_OUTPUT_PACKAGES:
        sys.exit(
            f"{results} has only {len(packages)} packages, expected at least "
            f"{MIN_OUTPUT_PACKAGES}"
        )
    if not isinstance(data.get("last_update"), str) or not data["last_update"]:
        sys.exit(f"{results} has no `last_update`")

    wheel = build_dir / "wheel.svg"
    if not wheel.is_file():
        sys.exit(f"{wheel} was not generated")
    size = wheel.stat().st_size
    if size < MIN_WHEEL_SVG_BYTES:
        # One <path> per package, so a near-empty wheel is a few hundred bytes.
        sys.exit(f"{wheel} is only {size} bytes, expected at least "
                 f"{MIN_WHEEL_SVG_BYTES}")

    return len(packages)


def check_no_front_matter():
    """Exit if index.html gained YAML front matter.

    The page's AngularJS bindings (``{{ package.name }}``) are also valid Liquid.
    Jekyll only leaves them alone because a file without front matter is a static
    file, copied byte-for-byte. Add front matter and the package list renders
    empty in production with no build error.
    """
    index = VENDOR_DIR / "index.html"
    with open(index, encoding="utf-8") as f:
        if f.read(3) == "---":
            sys.exit(
                f"{index} starts with YAML front matter. Jekyll would then run "
                "Liquid over it and eat the AngularJS bindings, silently "
                "emptying the package list. Remove the front matter."
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-dir",
        required=True,
        type=Path,
        help="scratch directory for the generator; must be outside docs/, as it "
        "collects a multi-GB requests-cache.sqlite",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="where to stage the dashboard, e.g. docs/dashboard",
    )
    parser.add_argument(
        "--list-url",
        help="override the upstream package list URL (for testing the input gate)",
    )
    args = parser.parse_args()

    if args.list_url:
        candidates = [("override", args.list_url)]
    else:
        candidates = [("upstream", UPSTREAM_LIST_URL), ("pinned", FALLBACK_LIST_URL)]

    check_no_front_matter()

    build_dir = args.build_dir.resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    payload = get_package_list(candidates)
    (build_dir / "top-pypi-packages.json").write_bytes(payload)

    # A subprocess, not an import: utils.py builds its CachedSession at module
    # import time, so the sqlite path binds to the cwd of whoever imports it
    # first. Running with cwd=build_dir keeps every cwd-relative read and write
    # out of the Jekyll source tree.
    print("Running the vendored generator...")
    subprocess.run(
        [sys.executable, str(VENDOR_DIR / "generate.py")],
        cwd=build_dir,
        check=True,
    )

    count = validate_output(build_dir)

    os.makedirs(args.output_dir, exist_ok=True)
    for name in STATIC_FILES:
        shutil.copy2(VENDOR_DIR / name, args.output_dir / name)
    for name in GENERATED_FILES:
        shutil.copy2(build_dir / name, args.output_dir / name)

    print(f"Staged the dashboard for {count} packages in {args.output_dir}")


if __name__ == "__main__":
    main()
