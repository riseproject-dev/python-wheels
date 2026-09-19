# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Collect the sources and licence texts of the FFmpeg stack PyAV vendors.

PyAV's wheels bundle prebuilt shared libraries fetched from a pyav-ffmpeg
release. Several of them are GPL (x264, x265) or LGPL (FFmpeg, GnuTLS,
Nettle, GMP, libunistring, alsa-lib, LAME), so redistributing the wheels
carries a source-distribution obligation. pyav-ffmpeg pins every dependency
by URL and SHA-256 in scripts/pkg.py, which is what this reads.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

LICENCE_RE = re.compile(r"^(COPYING|COPYRIGHT|LICEN[CS]E|NOTICE)", re.IGNORECASE)


def load_packages(pkg_py: str):
    namespace: dict = {}
    exec(compile(pkg_py, "pkg.py", "exec"), namespace)
    # Linux riscv64 enables gnutls, alsa and libvpl; CUDA/AMF/nasm are x86-only.
    packages = (
        namespace["gnutls_group"]
        + namespace["codec_group"]
        + [
            namespace["alsa_package"],
            namespace["libvpl_package"],
            namespace["ffmpeg_package"],
        ]
    )
    return sorted(packages, key=lambda p: p.name)


def download(package, dest_dir: Path) -> Path:
    name = package.source_filename or package.source_url.rsplit("/", 1)[-1]
    # A few upstreams name their tarball after the tag alone ("v2.16.0.tar.gz").
    if package.name.replace("-", "").lower() not in name.replace("-", "").lower():
        name = f"{package.name}-{name}"
    path = dest_dir / name
    subprocess.run(
        ["curl", "--location", "--fail", "--silent", "--show-error",
         "--output", str(path), package.source_url],
        check=True,
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != package.sha256:
        raise SystemExit(
            f"{package.name}: sha256 mismatch for {package.source_url}\n"
            f"  expected {package.sha256}\n  got      {digest}"
        )
    print(f"{package.name}: {name} ({path.stat().st_size} bytes, sha256 ok)")
    return path


def extract_licences(package, tarball: Path, dest_dir: Path) -> None:
    chunks = []
    with tarfile.open(tarball) as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts
            # Top level of the archive, plus one nested directory (x265 keeps
            # its sources under source/, gnutls its licences under doc/).
            if not member.isfile() or len(parts) > 3:
                continue
            if not LICENCE_RE.match(parts[-1]):
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            text = handle.read().decode("utf-8", "replace")
            chunks.append(f"===== {'/'.join(parts[1:])} =====\n\n{text}")
    if not chunks:
        raise SystemExit(f"{package.name}: no licence file found in {tarball.name}")
    header = (
        f"Licence texts for {package.name}, bundled in this wheel as a prebuilt\n"
        f"shared library. Source: {package.source_url}\n\n"
    )
    (dest_dir / f"LICENSE.{package.name}").write_text(header + "\n\n".join(chunks))
    print(f"{package.name}: {len(chunks)} licence file(s)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pyav-dir", type=Path, required=True)
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--licenses-dir", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads((args.pyav_dir / "scripts" / "ffmpeg-latest.json").read_text())
    tag = config["url"].split("/download/")[1].split("/")[0]
    print(f"pyav-ffmpeg release: {tag}")

    args.sources_dir.mkdir(parents=True, exist_ok=True)
    args.licenses_dir.mkdir(parents=True, exist_ok=True)

    # pyav-ffmpeg carries the build recipe and the patches it applies to FFmpeg,
    # GMP, LAME and libvpx, so it is part of the corresponding source.
    recipe = args.sources_dir / f"pyav-ffmpeg-{tag}.tar.gz"
    subprocess.run(
        ["curl", "--location", "--fail", "--silent", "--show-error", "--output", str(recipe),
         f"https://github.com/PyAV-Org/pyav-ffmpeg/archive/refs/tags/{tag}.tar.gz"],
        check=True,
    )
    with tarfile.open(recipe) as tar:
        member = next(m for m in tar.getmembers() if m.name.endswith("/scripts/pkg.py"))
        pkg_py = tar.extractfile(member).read().decode()

    for package in load_packages(pkg_py):
        tarball = download(package, args.sources_dir)
        extract_licences(package, tarball, args.licenses_dir)


if __name__ == "__main__":
    sys.exit(main())
