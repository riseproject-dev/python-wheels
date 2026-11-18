# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Trigger compatibility audit (plan section 6.4).

Answers, for every workflow in ``.github/workflows``: would a ``push`` to
``main`` that changes only the given paths start it? The intended behavior
is that a state-only push (``upstreaming-state/**``) starts nothing: no
agent recursion, downstream rebuild, website deployment or publication.

This is a static reading of ``on.push`` branch/path filters. It is evidence,
not proof: GitHub's own evaluation (App-token pushes, path-filter limits on
large diffs) still has to be confirmed in Stage A.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _load(text: str) -> dict:
    return yaml.load(text, Loader=_Loader) or {}


@dataclass
class Finding:
    workflow: str
    triggered: bool
    why: str


def _on(doc: dict) -> dict:
    on = doc.get(True, doc.get("on"))
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return {k: None for k in on}
    return on or {}


def _glob_to_re(pattern: str) -> re.Pattern:
    """GitHub filter-pattern semantics: ``*`` excludes ``/``, ``**`` matches
    anything, ``?`` one char. Good enough for an audit."""
    out = ""
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        else:
            out += re.escape(c)
        i += 1
    return re.compile("^" + out + "$")


def _match(patterns: list[str], path: str) -> bool:
    """Ordered include/exclude (``!``) semantics."""
    hit = False
    for p in patterns:
        neg = p.startswith("!")
        if _glob_to_re(p[1:] if neg else p).match(path):
            hit = not neg
    return hit


def push_triggers(doc: dict, changed: list[str], branch: str = "main") -> tuple[bool, str]:
    on = _on(doc)
    if "push" not in on:
        return False, "no push trigger"
    cfg = on["push"] or {}
    branches = cfg.get("branches")
    if branches is not None and not any(fnmatch.fnmatchcase(branch, b) for b in branches):
        return False, "branch filter excludes main"
    if "branches-ignore" in cfg and any(fnmatch.fnmatchcase(branch, b) for b in cfg["branches-ignore"]):
        return False, "branches-ignore excludes main"
    if "tags" in cfg and branches is None:
        return False, "tag-only push trigger"
    if "paths" in cfg:
        hits = [p for p in changed if _match(cfg["paths"], p)]
        return (bool(hits), f"paths match {hits[:3]}" if hits else "paths filter excludes all changes")
    if "paths-ignore" in cfg:
        rest = [p for p in changed if not _match(cfg["paths-ignore"], p)]
        return (bool(rest), "paths-ignore leaves changes" if rest else "paths-ignore covers all changes")
    return True, "push trigger without path filter"


def audit(workflows_dir: Path, changed: list[str]) -> list[Finding]:
    out = []
    for p in sorted(workflows_dir.glob("*.y*ml")):
        doc = _load(p.read_text(encoding="utf-8"))
        trig, why = push_triggers(doc, changed)
        out.append(Finding(p.name, trig, why))
    return out


def workflow_run_consumers(workflows_dir: Path) -> list[str]:
    """Workflows that would start from another workflow's completion; each
    must be an explicitly allowlisted observation path."""
    out = []
    for p in sorted(workflows_dir.glob("*.y*ml")):
        doc = _load(p.read_text(encoding="utf-8"))
        if "workflow_run" in _on(doc):
            out.append(p.name)
    return out


def classify_commit(changed: list[str]) -> str:
    """state | code | mixed. A mixed commit is classified by its complete
    diff: state paths never suppress tests for the code part, and the state
    publisher rejects any non-state path outright."""
    state = [c for c in changed if c.startswith("upstreaming-state/")]
    if state and len(state) == len(changed):
        return "state"
    return "mixed" if state else "code"
