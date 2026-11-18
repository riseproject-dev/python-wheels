# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""External wheel acceptance probe (plan sections 11.4 and 12.1).

Runs in a clean, untrusted target sandbox against a downloaded wheel, never
in the credentialed publisher. Two parts:

* ``inspect_wheel``: static checks with no code execution. Filename tags,
  WHEEL/METADATA presence, RECORD hashes, payload presence, and for every
  ELF object: RISC-V machine, 64-bit, double-float ABI, ``DT_NEEDED``
  libraries outside the manylinux allowlist, and the ``.riscv.attributes``
  arch string so baseline code does not require RVV (``v``/``zve*``).
  Objects whose names are listed in ``rvv_allowed`` (isolated, runtime
  dispatched backends) may carry vector extensions.
* ``install_and_import``: binary-only install into a fresh venv with an
  isolated pip configuration and an installation report, then imports run
  from outside any source checkout, checking the module comes from the venv.

These supplement project CI and human review; they are not semantic proof.

Usage (inside the sandbox):
    python -m upstreaming.probe WHEEL [--import NAME ...] [--install]
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from packaging.utils import parse_wheel_filename

EM_RISCV = 243
EF_RISCV_RVC = 0x1
EF_RISCV_FLOAT_ABI_MASK = 0x6
EF_RISCV_FLOAT_ABI_DOUBLE = 0x4
SHT_RISCV_ATTRIBUTES = 0x70000003
DT_NEEDED = 1

# manylinux policy libraries (glibc family); anything else must be bundled.
MANYLINUX_ALLOWED = {
    "libc.so.6", "libm.so.6", "libdl.so.2", "librt.so.1", "libpthread.so.0", "libutil.so.1",
    "libgcc_s.so.1", "libstdc++.so.6", "libgomp.so.1", "libz.so.1", "libexpat.so.1",
    "libnsl.so.1", "libcrypt.so.1", "ld-linux-riscv64-lp64d.so.1",
}
MUSLLINUX_ALLOWED = {"libc.musl-riscv64.so.1", "ld-musl-riscv64.so.1", "libgcc_s.so.1",
                     "libstdc++.so.6", "libgomp.so.1", "libz.so.1"}
VECTOR_EXT = re.compile(r"(?:^|_)(v\d+p\d+|zve\d+[a-z]*\d*p\d+|zvl\d+b\d+p\d+)")


@dataclass
class ElfInfo:
    path: str
    machine_ok: bool
    rvc: bool
    double_abi: bool
    needed: list[str] = field(default_factory=list)
    arch: str | None = None
    vector: bool = False


@dataclass
class Report:
    wheel: str
    tags: list[str] = field(default_factory=list)
    elfs: list[ElfInfo] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def parse_elf(data: bytes, path: str) -> ElfInfo | None:
    if data[:4] != b"\x7fELF":
        return None
    if data[4] != 2 or data[5] != 1:
        return ElfInfo(path, False, False, False)
    (e_type, e_machine, _v, _entry, _phoff, e_shoff, e_flags, _ehs, _phes, _phn,
     e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
    info = ElfInfo(path, e_machine == EM_RISCV, bool(e_flags & EF_RISCV_RVC),
                   (e_flags & EF_RISCV_FLOAT_ABI_MASK) == EF_RISCV_FLOAT_ABI_DOUBLE)
    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        if off + 64 > len(data):
            break
        name, stype, _f, _a, soff, ssize, link, _i, _al, entsize = struct.unpack_from("<IIQQQQIIQQ", data, off)
        sections.append((name, stype, soff, ssize, link, entsize))
    # Dynamic section -> DT_NEEDED via its linked string table.
    for _n, stype, soff, ssize, link, _es in sections:
        if stype == 6 and link < len(sections):  # SHT_DYNAMIC
            stroff = sections[link][2]
            for k in range(soff, soff + ssize, 16):
                tag, val = struct.unpack_from("<qQ", data, k)
                if tag == 0:
                    break
                if tag == DT_NEEDED:
                    end = data.index(b"\0", stroff + val)
                    info.needed.append(data[stroff + val:end].decode("ascii", "replace"))
        if stype == SHT_RISCV_ATTRIBUTES:
            blob = data[soff:soff + ssize]
            m = re.search(rb"(rv64[a-z0-9_]+)\x00", blob)
            if m:
                info.arch = m.group(1).decode()
                info.vector = bool(VECTOR_EXT.search(info.arch.split("rv64", 1)[1]))
    return info


def _record_hash(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def inspect_wheel(path: Path, *, rvv_allowed: list[str] | None = None,
                  extra_allowed_libs: list[str] | None = None) -> Report:
    rep = Report(wheel=path.name)
    try:
        name, _ver, _build, tags = parse_wheel_filename(path.name)
    except Exception as e:
        rep.problems.append(f"filename: {e}")
        return rep
    rep.tags = sorted(str(t) for t in tags)
    plats = {t.platform for t in tags}
    musl = any(p.startswith("musllinux") for p in plats)
    if not any(p.endswith("_riscv64") for p in plats) and plats != {"any"}:
        rep.problems.append(f"no riscv64 platform tag in {sorted(plats)}")
    allowed = (MUSLLINUX_ALLOWED if musl else MANYLINUX_ALLOWED) | set(extra_allowed_libs or [])
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        dist_info = [n for n in names if re.match(r"^[^/]+\.dist-info/WHEEL$", n)]
        if len(dist_info) != 1:
            rep.problems.append("expected exactly one .dist-info/WHEEL")
            return rep
        di = dist_info[0].rsplit("/", 1)[0]
        for req in ("METADATA", "RECORD"):
            if f"{di}/{req}" not in names:
                rep.problems.append(f"missing {di}/{req}")
        record = {}
        if f"{di}/RECORD" in names:
            for row in csv.reader(io.StringIO(z.read(f"{di}/RECORD").decode())):
                if row:
                    record[row[0]] = row[1] if len(row) > 1 else ""
        bundled = {n.rsplit("/", 1)[-1] for n in names}
        for n in names:
            if n.endswith("/"):
                continue
            if n.startswith("/") or ".." in n.split("/"):
                rep.problems.append(f"{n}: unsafe archive path")
                continue
            data = z.read(n)
            if n != f"{di}/RECORD":
                h = record.get(n)
                if not h:
                    rep.problems.append(f"{n}: not listed in RECORD")
                elif h != _record_hash(data):
                    rep.problems.append(f"{n}: RECORD hash mismatch")
            elf = parse_elf(data, n)
            if elf is None:
                continue
            rep.elfs.append(elf)
            if not elf.machine_ok:
                rep.problems.append(f"{n}: not a 64-bit little-endian RISC-V ELF")
                continue
            if not elf.double_abi:
                rep.problems.append(f"{n}: not the lp64d (double-float) ABI")
            for lib in elf.needed:
                if lib not in allowed and lib not in bundled:
                    rep.problems.append(f"{n}: needs external {lib} (not bundled, not in policy)")
            if elf.vector and not any(re.fullmatch(p, n) for p in (rvv_allowed or [])):
                # The attribute is the link-time union of all objects, so a
                # correctly runtime-dispatched module also shows V. Only an
                # explicit reviewer allowance plus a no-V fallback run clears it.
                rep.problems.append(f"{n}: arch attributes include vector extensions ({elf.arch}); "
                                    "allow only for isolated hwprobe-dispatched code and verify the "
                                    "rv64gc fallback without V")
            if elf.arch is None:
                rep.notes.append(f"{n}: no .riscv.attributes arch string; baseline not verified")
        if record and not rep.elfs and plats != {"any"}:
            rep.notes.append("platform wheel without native payload")
    return rep


def install_and_import(wheel: Path, imports: list[str], *, index_url: str = "https://pypi.org/simple",
                       python: str = sys.executable) -> dict:
    """Binary-only install in a fresh venv, isolated from user/system pip
    configuration and caches, then import from an empty directory."""
    out: dict = {"ok": False}
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "venv"
        subprocess.run([python, "-m", "venv", str(venv)], check=True)
        py = venv / "bin" / "python"
        env = {"PATH": f"{venv}/bin:/usr/bin:/bin", "HOME": tmp, "PIP_CONFIG_FILE": os.devnull,
               "PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
               "PYTHONNOUSERSITE": "1"}
        report = Path(tmp) / "install-report.json"
        p = subprocess.run([str(py), "-m", "pip", "install", "--isolated", "--no-cache-dir",
                            "--only-binary=:all:", "--index-url", index_url, "--report", str(report),
                            str(wheel)], env=env, cwd=tmp, capture_output=True, text=True)
        out["pip_returncode"] = p.returncode
        out["pip_stderr_tail"] = p.stderr[-2000:]
        if report.exists():
            rpt = json.loads(report.read_text())
            out["resolved"] = [{"name": i["metadata"]["name"], "version": i["metadata"]["version"],
                                "url": i["download_info"]["url"],
                                "hash": (i["download_info"].get("archive_info") or {}).get("hash")}
                               for i in rpt.get("install", [])]
            bad = [r for r in out["resolved"] if not (r["url"].startswith(index_url.rsplit("/simple", 1)[0])
                                                       or r["url"].startswith("https://files.pythonhosted.org/")
                                                       or r["url"].startswith("file://"))]
            if bad:
                out["unapproved_sources"] = bad
                return out
        if p.returncode != 0:
            return out
        site = subprocess.run([str(py), "-c", "import sysconfig;print(sysconfig.get_paths()['purelib'])"],
                              env=env, cwd=tmp, capture_output=True, text=True).stdout.strip()
        out["imports"] = {}
        for mod in imports:
            r = subprocess.run([str(py), "-I", "-c", f"import importlib,sys;m=importlib.import_module({mod!r});"
                                "print(getattr(m,'__file__',''))"], env=env, cwd=tmp,
                               capture_output=True, text=True)
            loc = r.stdout.strip()
            out["imports"][mod] = {"ok": r.returncode == 0 and loc.startswith(str(venv)),
                                   "file": loc, "stderr": r.stderr[-1000:]}
            if site and loc and not loc.startswith(str(venv)):
                out["imports"][mod]["ok"] = False
        out["ok"] = all(v["ok"] for v in out["imports"].values())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wheel", type=Path)
    ap.add_argument("--import", dest="imports", action="append", default=[])
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--rvv-allowed", action="append", default=[],
                    help="regex of payload paths that are isolated RVV backends")
    ap.add_argument("--allow-lib", action="append", default=[])
    a = ap.parse_args(argv)
    rep = inspect_wheel(a.wheel, rvv_allowed=a.rvv_allowed, extra_allowed_libs=a.allow_lib)
    result = {"static": {**asdict(rep), "ok": rep.ok}}
    if a.install:
        result["install"] = install_and_import(a.wheel, a.imports)
    print(json.dumps(result, indent=2))
    return 0 if rep.ok and (not a.install or result["install"]["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())
