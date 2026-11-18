# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Official release coverage against a frozen target contract (plan 11.2, 18.2).

This is the deterministic metadata half of release acceptance: which
official, non-yanked files cover which frozen matrix rows. It parses tags
with ``packaging`` (compressed tags, abi3, free-threaded ``t`` ABIs, libc
family/floor). Installing and running the wheels in clean target
environments is the separate probe step; ``released`` needs both.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from packaging.tags import Tag
from packaging.utils import InvalidWheelFilename, parse_wheel_filename
from packaging.version import Version

_MANY = re.compile(r"^manylinux_(\d+)_(\d+)_riscv64$")
_MUSL = re.compile(r"^musllinux_(\d+)_(\d+)_riscv64$")


@dataclass(frozen=True)
class Row:
    """One frozen target row, e.g. cp312/cp312/manylinux floor 2.39."""
    interpreter: str          # cp312, cp313, pp311 ... (free-threaded is cp313 + abi cp313t)
    abi: str                  # cp312, cp313t, abi3, none
    libc: str                 # manylinux | musllinux
    floor: tuple[int, int]    # maximum platform floor the payload may require

    @property
    def key(self) -> str:
        return f"{self.interpreter}-{self.abi}-{self.libc}_{self.floor[0]}_{self.floor[1]}"


@dataclass
class Coverage:
    version: str
    covered: dict[str, str] = field(default_factory=dict)     # row key -> filename
    missing: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing and not self.problems


def _platform(tag: Tag) -> tuple[str, tuple[int, int]] | None:
    m = _MANY.match(tag.platform)
    if m:
        return "manylinux", (int(m.group(1)), int(m.group(2)))
    m = _MUSL.match(tag.platform)
    if m:
        return "musllinux", (int(m.group(1)), int(m.group(2)))
    if tag.platform == "any":
        return "any", (0, 0)
    return None


def _abi3_ok(tag: Tag, row: Row) -> bool:
    """An abi3 wheel built for cp3X serves every CPython >= 3.X (non-free-threaded)."""
    if tag.abi != "abi3" or not tag.interpreter.startswith("cp") or row.abi.endswith("t"):
        return False
    if not row.interpreter.startswith("cp"):
        return False
    return int(tag.interpreter[3:]) <= int(row.interpreter[3:])


def row_satisfied(tags: Iterable[Tag], row: Row, *, allow_universal: bool) -> bool:
    for t in tags:
        plat = _platform(t)
        if plat is None:
            continue
        family, floor = plat
        if family == "any":
            if allow_universal and t.abi == "none":
                return True
            continue
        if family != row.libc or floor > row.floor:
            continue
        if t.interpreter == row.interpreter and t.abi == row.abi:
            return True
        if row.abi == "abi3" and _abi3_ok(t, row):
            return True
        if row.abi == row.interpreter and _abi3_ok(t, row):
            return True
    return False


def coverage(pypi_release_files: list[dict], version: str, rows: list[Row], *,
             allow_universal: bool = False) -> Coverage:
    """``pypi_release_files``: entries of the PyPI JSON API ``urls`` list for
    one version (filename, yanked, digests, upload_time_iso_8601).

    ``allow_universal`` must only be True for a genuinely architecture
    independent contract: a universal wheel never closes an acceleration gap.
    """
    cov = Coverage(version=version)
    want = Version(version)
    files = []
    for f in pypi_release_files:
        name = f.get("filename", "")
        if not name.endswith(".whl"):
            continue
        if f.get("yanked"):
            cov.problems.append(f"{name}: yanked")
            continue
        if not (f.get("digests") or {}).get("sha256"):
            cov.problems.append(f"{name}: no sha256 digest in official metadata")
            continue
        try:
            _n, v, _b, tags = parse_wheel_filename(name)
        except InvalidWheelFilename as e:
            cov.problems.append(f"{name}: {e}")
            continue
        if v != want:
            continue
        files.append((name, tags))
    for row in rows:
        hit = next((n for n, tags in files if row_satisfied(tags, row, allow_universal=allow_universal)), None)
        if hit:
            cov.covered[row.key] = hit
        else:
            cov.missing.append(row.key)
    # Yanked files of *other* rows are only a problem if they were the sole cover.
    cov.problems = [p for p in cov.problems if not p.endswith("yanked")] + [
        p for p in cov.problems if p.endswith("yanked") and cov.missing]
    return cov


def select_release(releases: dict[str, list[dict]], *, minimum: str | None) -> list[str]:
    """Candidate official versions (non-yanked, non-prerelease) newer than or
    equal to ``minimum`` (the first version expected to contain the merge),
    oldest first. Provenance (merge ancestry or maintainer confirmation) is
    checked separately: a version number is never assumed to contain a fix."""
    out = []
    for v, files in releases.items():
        try:
            ver = Version(v)
        except Exception:
            continue
        if ver.is_prerelease or ver.is_devrelease:
            continue
        if files and all(f.get("yanked") for f in files):
            continue
        if minimum and ver < Version(minimum):
            continue
        out.append(v)
    return sorted(out, key=Version)
