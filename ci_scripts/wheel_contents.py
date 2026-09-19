#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Inspect a remote wheel without downloading it, for feasibility triage.

Reads the wheel's zip central directory over HTTP range requests and prints
its entries largest-first, so "what is actually inside this wheel" can be
answered in a few hundred kilobytes instead of a multi-hundred-megabyte
download (the check gotchas 24/27/35/41 ask for: vendor `bin/` tools and
foreign `lib*.so` blobs sitting next to the project's own extension).

With --member, one file is extracted the same way, which is how the small
but decisive files get read: `dist-info/METADATA`, `entry_points.txt`, a
backend's `driver.py` and its `ctypes.CDLL(...)`/`dlopen` lines.

Usage:
    uv run ci_scripts/wheel_contents.py tokenspeed-triton
    uv run ci_scripts/wheel_contents.py tokenspeed-triton --version 3.8.10.post20260721 \
        --match cp312-abi3-manylinux_2_27_aarch64
    uv run ci_scripts/wheel_contents.py <wheel-url> --all
    uv run ci_scripts/wheel_contents.py <wheel-url> --member tokenspeed_triton/backends/nvidia/driver.py
"""

import argparse
import json
import struct
import sys
import urllib.request
import zlib

TAIL = 1 << 20  # files.pythonhosted.org rejects a whole-file range with 501


def http(url, start=None, end=None, method="GET"):
    headers = {}
    if start is not None:
        headers["Range"] = f"bytes={start}-{end}"
    request = urllib.request.Request(url, headers=headers, method=method)
    return urllib.request.urlopen(request)


def resolve_url(package, version, match):
    if package.startswith("http://") or package.startswith("https://"):
        return package
    with http(f"https://pypi.org/pypi/{package}/json") as response:
        data = json.load(response)
    version = version or data["info"]["version"]
    files = data["releases"].get(version)
    if not files:
        raise SystemExit(
            f"{package} has no release {version}; released: "
            + ", ".join(sorted(data["releases"]))
        )
    wheels = [f for f in files if f["filename"].endswith(".whl")]
    if match:
        wheels = [f for f in wheels if match in f["filename"]]
    if not wheels:
        raise SystemExit(
            f"{package} {version} has no wheel matching {match!r}; files: "
            + ", ".join(f["filename"] for f in files)
        )
    if len(wheels) > 1:
        raise SystemExit(
            f"{package} {version} has {len(wheels)} matching wheels, narrow it with "
            "--match: " + ", ".join(w["filename"] for w in wheels)
        )
    return wheels[0]["url"]


def read_central_directory(url):
    size = int(http(url, method="HEAD").headers["Content-Length"])
    with http(url, max(0, size - TAIL), size - 1) as response:
        tail = response.read()
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0:
        raise SystemExit(f"{url}: no end-of-central-directory record in the last {TAIL} bytes")
    cd_size, cd_offset = struct.unpack("<II", tail[offset + 12 : offset + 20])
    if 0xFFFFFFFF in (cd_size, cd_offset):
        raise SystemExit(f"{url}: zip64 central directory, not supported here")
    with http(url, cd_offset, cd_offset + cd_size - 1) as response:
        directory = response.read()
    entries = []
    position = 0
    while position < len(directory) and directory[position : position + 4] == b"PK\x01\x02":
        method, = struct.unpack("<H", directory[position + 10 : position + 12])
        compressed, uncompressed = struct.unpack("<II", directory[position + 20 : position + 28])
        name_len, extra_len, comment_len = struct.unpack(
            "<HHH", directory[position + 28 : position + 34]
        )
        local_offset, = struct.unpack("<I", directory[position + 42 : position + 46])
        name = directory[position + 46 : position + 46 + name_len].decode("utf-8", "replace")
        entries.append(
            {
                "name": name,
                "method": method,
                "compressed": compressed,
                "uncompressed": uncompressed,
                "local_offset": local_offset,
            }
        )
        position += 46 + name_len + extra_len + comment_len
    return size, entries


def read_member(url, entry):
    # The local header repeats the name and carries its own extra field, whose
    # length can differ from the central directory's, so read it rather than
    # assuming the two match.
    with http(url, entry["local_offset"], entry["local_offset"] + 29) as response:
        header = response.read()
    name_len, extra_len = struct.unpack("<HH", header[26:30])
    start = entry["local_offset"] + 30 + name_len + extra_len
    with http(url, start, start + entry["compressed"] - 1) as response:
        payload = response.read()
    if entry["method"] == 0:
        return payload
    if entry["method"] == 8:
        return zlib.decompress(payload, -zlib.MAX_WBITS)
    raise SystemExit(f"{entry['name']}: unsupported compression method {entry['method']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", help="PyPI package name, or a direct wheel URL")
    parser.add_argument("--version", help="release to inspect (default: the latest)")
    parser.add_argument("--match", help="substring selecting one wheel of the release")
    parser.add_argument(
        "--member", help="extract this path from the wheel instead of listing entries"
    )
    parser.add_argument("--output", help="write --member to this file instead of stdout")
    parser.add_argument("--top", type=int, default=40, help="entries to list (default: 40)")
    parser.add_argument("--all", action="store_true", help="list every entry")
    args = parser.parse_args()

    url = resolve_url(args.package, args.version, args.match)
    size, entries = read_central_directory(url)

    if args.member:
        matched = [e for e in entries if e["name"] == args.member]
        if not matched:
            raise SystemExit(f"{args.member} is not in {url}")
        payload = read_member(url, matched[0])
        if args.output:
            with open(args.output, "wb") as handle:
                handle.write(payload)
        else:
            sys.stdout.buffer.write(payload)
        return

    print(url)
    print(
        f"{len(entries)} entries, {size} bytes compressed, "
        f"{sum(e['uncompressed'] for e in entries)} bytes uncompressed"
    )
    listed = sorted(entries, key=lambda e: e["uncompressed"], reverse=True)
    if not args.all:
        listed = listed[: args.top]
    for entry in listed:
        print(f"{entry['uncompressed']:>12} {entry['compressed']:>12}  {entry['name']}")


if __name__ == "__main__":
    main()
