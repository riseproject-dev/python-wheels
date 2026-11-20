# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Parser for the explicit ``/upstreaming`` command grammar (plan section 7.3).

Only the first nonblank line of a comment is considered. It must be a single
unquoted, non-fenced command. Anything else (quoted examples, fenced blocks,
multiple commands, unknown verbs or fields, malformed values) is rejected.
The parser never interprets commands embedded in other text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

COMMAND_VERSION = 1
PREFIX = "/upstreaming"

_SHA = r"[0-9a-f]{40}"
_ID = r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}"
_INT = r"[0-9]{1,9}"
_REASON = r".{1,2000}"

# verb -> {field: regex}; every listed field is required unless it is in
# OPTIONAL for that verb; no other fields are allowed.
#
# ``contribution`` is always optional: a command is posted on the
# contribution's own tracking issue, and the controller resolves it from that
# issue. If given, it must match the issue's contribution.
#
# ``revision`` is required for commands that change or approve work (so an
# approval cannot apply to work that moved since you read it) and optional
# for stop commands (stopping is always safe, a stale stop is honored).
GRAMMAR: dict[str, dict[str, str]] = {
    "pause": {"contribution": _ID, "revision": _INT, "reason": _REASON},
    "resume": {"contribution": _ID, "revision": _INT, "reason": _REASON},
    "park": {"contribution": _ID, "revision": _INT, "reason": _REASON},
    "request-handoff": {"contribution": _ID, "revision": _INT, "head": _SHA},
    "approve-handoff": {"contribution": _ID, "revision": _INT, "head": _SHA},
    "register-upstream-pr": {
        "contribution": _ID,
        "revision": _INT,
        "url": r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[0-9]{1,9}",
    },
    "clarify": {"contribution": _ID, "revision": _INT, "decision": _ID, "answer": _REASON},
    "revise-scope": {"contribution": _ID, "revision": _INT, "proposal": _ID},
    "block": {"contribution": _ID, "revision": _INT, "reason": _REASON},
    "abandon": {"contribution": _ID, "revision": _INT, "reason": _REASON},
    # Start a new lifecycle generation on the same tracking issue. This is
    # deliberately allowed only after abandon and requires an exact revision.
    "restart": {"contribution": _ID, "revision": _INT, "reason": _REASON},
    # Re-run investigation on an existing development PR, then require a new
    # worker pass with the refreshed dossier and current prompts.
    "refresh": {"contribution": _ID, "revision": _INT, "reason": _REASON},
    "resolve-operation": {
        "operation": _ID,
        "disposition": r"confirmed|not-launched|failed",
        "evidence": _ID,
    },
    "authorize-followup": {"contribution": _ID, "revision": _INT, "proposal": _ID},
    # Investigation -> provisioning: a RISE owner approves the dossier's scope.
    # ``class`` is the admission class; ``backup`` is the backup owner's login
    # (the commenter becomes the primary owner). ``paths`` optionally narrows
    # the patch surface (comma-separated globs; default: the dossier's
    # allowed_paths, else .github/workflows/*).
    "approve-scope": {"contribution": _ID, "revision": _INT,
                      "class": r"configuration_integration|architecture_correctness|optimized_backend",
                      "backup": r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})",
                      "paths": r"[A-Za-z0-9_.*/?\[\]{},-]{1,500}"},
    # Explicit human override for an automatically parked dossier. Development
    # remains automated after this stale-proof bounded-scope decision.
    "force-develop": {"contribution": _ID, "revision": _INT,
                      "class": r"configuration_integration|architecture_correctness|optimized_backend",
                      "paths": r"[A-Za-z0-9_.*/?\[\]{},-]{1,500}", "reason": _REASON},
    # Provisioning -> development: verify a human-created fork, its riscv64
    # branch and the upstream base, then record them (trusted code reads them).
    "provision": {"contribution": _ID, "revision": _INT},
}

# Commands that stop work; processed before everything else in a tick.
URGENT = frozenset({"pause", "park", "block", "abandon"})

OPTIONAL: dict[str, frozenset[str]] = {
    verb: frozenset({"contribution"} | ({"revision"} if verb in URGENT else set())
                    | ({"reason"} if verb == "pause" else set()))
    for verb in GRAMMAR if verb != "resolve-operation"
}
OPTIONAL["resolve-operation"] = frozenset()
OPTIONAL["approve-scope"] = OPTIONAL["approve-scope"] | {"paths"}

_TOKEN_RE = re.compile(r'\s*([a-z][a-z-]*)=("((?:[^"\\]|\\.)*)"|[^\s"]+)')


class CommandError(ValueError):
    pass


@dataclass(frozen=True)
class Command:
    verb: str
    args: dict[str, str] = field(default_factory=dict)
    version: int = COMMAND_VERSION

    @property
    def contribution(self) -> str | None:
        return self.args.get("contribution")

    @property
    def revision(self) -> int | None:
        r = self.args.get("revision")
        return int(r) if r is not None else None


def looks_like_command(body: str) -> bool:
    """Cheap pre-filter used before entering the serialized controller."""
    first = _first_nonblank(body)
    return first is not None and first.startswith(PREFIX + " ")


def _first_nonblank(body: str) -> str | None:
    for line in body.splitlines():
        if line.strip():
            return line
    return None


def parse(body: str) -> Command:
    """Parse a comment body into a Command or raise CommandError."""
    if not isinstance(body, str):
        raise CommandError("comment body is not text")
    if len(body.encode("utf-8")) > 16384:
        raise CommandError("comment too large")
    first = _first_nonblank(body)
    if first is None:
        raise CommandError("empty comment")
    if first != first.lstrip():
        # Indented lines render as code blocks in Markdown.
        raise CommandError("command must not be indented")
    if first.startswith((">", "```", "~~~")):
        raise CommandError("quoted or fenced text is not a command")
    if not first.startswith(PREFIX + " "):
        raise CommandError("first nonblank line is not an /upstreaming command")
    rest_lines = body.splitlines()
    idx = rest_lines.index(first)
    for line in rest_lines[idx + 1:]:
        if line.lstrip().startswith(PREFIX):
            raise CommandError("multiple commands in one comment")

    text = first[len(PREFIX):].strip()
    verb, _, tail = text.partition(" ")
    if verb not in GRAMMAR:
        raise CommandError(f"unknown command {verb!r}")
    spec = GRAMMAR[verb]
    args: dict[str, str] = {}
    pos = 0
    tail = tail.rstrip()
    while pos < len(tail):
        m = _TOKEN_RE.match(tail, pos)
        if not m:
            raise CommandError(f"malformed arguments near {tail[pos:pos + 20]!r}")
        key = m.group(1)
        value = m.group(3) if m.group(3) is not None else m.group(2)
        if m.group(3) is not None:
            value = re.sub(r"\\(.)", r"\1", value)
        if key in args:
            raise CommandError(f"duplicate field {key!r}")
        if key == "version":
            if value != str(COMMAND_VERSION):
                raise CommandError(f"unsupported command version {value!r}")
        elif key not in spec:
            raise CommandError(f"unknown field {key!r} for {verb}")
        else:
            if not re.fullmatch(spec[key], value, flags=re.DOTALL):
                raise CommandError(f"invalid value for {key!r}")
            args[key] = value
        pos = m.end()
    missing = set(spec) - set(args) - OPTIONAL.get(verb, frozenset())
    if missing:
        raise CommandError(f"missing fields: {', '.join(sorted(missing))}")
    return Command(verb=verb, args=args)
