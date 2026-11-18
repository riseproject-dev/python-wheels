# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Section 21: static wheel probe (payload, linkage, baseline/RVV leakage)."""

import base64
import hashlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from ci_scripts.upstreaming import probe


def elf(arch=b"rv64i2p1_m2p0_a2p1_f2p2_d2p2_c2p0", needed=(), machine=243, flags=0x5):
    """Minimal ELF64 with a dynamic section, its string table and a
    .riscv.attributes section. Enough for probe.parse_elf, not loadable."""
    strtab = b"\0" + b"".join(n.encode() + b"\0" for n in needed)
    offs, o = [], 1
    for n in needed:
        offs.append(o)
        o += len(n) + 1
    dyn = b"".join(struct.pack("<qQ", 1, x) for x in offs) + struct.pack("<qQ", 0, 0)
    attrs = b"A" + b"\0" * 16 + b"riscv\0" + b"\x05" + arch + b"\0"
    body = strtab + dyn + attrs
    shoff = 64 + len(body)
    s_str, s_dyn, s_att = 64, 64 + len(strtab), 64 + len(strtab) + len(dyn)
    hdr = b"\x7fELF" + bytes([2, 1, 1]) + b"\0" * 9
    hdr += struct.pack("<HHIQQQIHHHHHH", 3, machine, 1, 0, 0, shoff, flags, 64, 56, 0, 64, 4, 0)
    sh = b"\0" * 64
    sh += struct.pack("<IIQQQQIIQQ", 0, 3, 0, 0, s_str, len(strtab), 0, 0, 1, 0)
    sh += struct.pack("<IIQQQQIIQQ", 0, 6, 0, 0, s_dyn, len(dyn), 1, 0, 8, 16)
    sh += struct.pack("<IIQQQQIIQQ", 0, 0x70000003, 0, 0, s_att, len(attrs), 0, 0, 1, 0)
    return hdr + body + sh


def h(data):
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def wheel(tmp, files, name="p-1.0-cp312-cp312-manylinux_2_39_riscv64.whl", break_record=None):
    path = Path(tmp) / name
    files = dict(files)
    files["p-1.0.dist-info/WHEEL"] = b"Wheel-Version: 1.0\n"
    files["p-1.0.dist-info/METADATA"] = b"Name: p\nVersion: 1.0\n"
    rec = "".join(f"{n},{h(d) if n != break_record else 'sha256=x'},{len(d)}\n" for n, d in files.items())
    rec += "p-1.0.dist-info/RECORD,,\n"
    with zipfile.ZipFile(path, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
        z.writestr("p-1.0.dist-info/RECORD", rec)
    return path


class TestProbe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_baseline(self):
        w = wheel(self.tmp.name, {"p/_x.so": elf(needed=["libc.so.6"]), "p/__init__.py": b""})
        rep = probe.inspect_wheel(w)
        self.assertTrue(rep.ok, rep.problems)
        self.assertEqual(rep.elfs[0].needed, ["libc.so.6"])
        self.assertFalse(rep.elfs[0].vector)

    def test_rvv_leak_and_allowance(self):
        files = {"p/_x.so": elf(arch=b"rv64i2p1_m2p0_a2p1_f2p2_d2p2_c2p0_v1p0_zve64d1p0")}
        w = wheel(self.tmp.name, files)
        self.assertTrue(any("vector" in p for p in probe.inspect_wheel(w).problems))
        self.assertTrue(probe.inspect_wheel(w, rvv_allowed=[r"p/_x\.so"]).ok)

    def test_external_library_and_bundled(self):
        w = wheel(self.tmp.name, {"p/_x.so": elf(needed=["libssl.so.3"])})
        self.assertTrue(any("libssl" in p for p in probe.inspect_wheel(w).problems))
        w2 = wheel(self.tmp.name, {"p/_x.so": elf(needed=["libfoo-1a2b.so"]),
                                   "p.libs/libfoo-1a2b.so": elf()},
                   name="p-1.0-cp312-cp312-manylinux_2_39_riscv64.whl")
        self.assertTrue(probe.inspect_wheel(w2).ok)

    def test_wrong_arch_abi_and_record(self):
        w = wheel(self.tmp.name, {"p/_x.so": elf(machine=62)})
        self.assertTrue(any("not a 64-bit" in p for p in probe.inspect_wheel(w).problems))
        w = wheel(self.tmp.name, {"p/_x.so": elf(flags=0x1)})
        self.assertTrue(any("lp64d" in p for p in probe.inspect_wheel(w).problems))
        w = wheel(self.tmp.name, {"p/_x.so": elf()}, break_record="p/_x.so")
        self.assertTrue(any("RECORD hash" in p for p in probe.inspect_wheel(w).problems))

    def test_wrong_platform_tag(self):
        w = wheel(self.tmp.name, {"p/_x.so": elf()}, name="p-1.0-cp312-cp312-manylinux_2_39_x86_64.whl")
        self.assertTrue(any("riscv64" in p for p in probe.inspect_wheel(w).problems))


if __name__ == "__main__":
    unittest.main()
