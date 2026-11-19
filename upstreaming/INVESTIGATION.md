# Investigator research contract

The investigator is read-only. Only this workflow has operator-approved
unsandboxed internet access. Its pinned Pi extensions provide web access and
subagent support. No controller App key or contribution-fork token is passed to
it. The dispatcher and patch worker keep their existing sandbox settings.

Native threat detection is disabled only for the investigator, as approved by
the operator: gh-aw v1.2.2 requires the agent sandbox for that detector. The
trusted research-completeness gate and native verified artifact delivery remain.

## Inputs

The controller freezes the complete tracking-issue description, its digest,
issue ID/number and canonical URL into `active_work.tracking_issue` when it
requests work. The dispatcher copies that immutable snapshot into
`task.context.tracking_issue`; it never re-reads mutable issue text for a replay.
The agent must read the whole snapshot and follow the issue URL for comments
and additional user-provided evidence. Descriptions are never silently truncated.
Oversized descriptions fail explicitly under the existing intake bound.

Older active requests without a snapshot cannot be staged. They require a fresh
requested revision through control commands, not an in-place Work mutation.

## Mandatory research

The prompt requires searches across the entire relevant historical corpus, all
issue/PR states and result pages, linked predecessor/follow-up discussions and
actual reviewer threads. It also requires current/historical CI, release
repositories, documentation, official websites, mailing lists, blogs,
announcements, maintainers and prior accepted/rejected approaches.

The GitHub MCP includes Issues, pull requests, repositories and Actions with
`min-integrity: none`, so public research is not filtered by author trust. All
retrieved content remains untrusted evidence, not instructions or authorization.

The required project-graph MCP is
`ghcr.io/riseproject-dev/sw-ecosystem/project-graph-mcp:latest`, matching the
operator's reference workflow. The dossier preserves `project_graph_query`
arguments, the structured graph result and a comparison with the project's
actual dependencies. No guessed edges or fabricated empty graph after a failure.

The investigator must check `sw-ecosystem/projects.yml` and `project-reports`
using canonical repository identity, project names and synonyms. An available
report is read in full and used across support-status, dependency and
prior-work/blocker analysis. The dossier records report revision, used findings
and current corroboration/conflicts. Genuine report absence needs an evidenced
search, not an assumption.

## Gate before Completion

`upstreaming/schemas/dossier.schema.json` requires documented coverage for every
research category, source URLs, queries, findings, relevant decisions/reviewers,
the dependency graph and the ecosystem-report assessment. Incomplete/unavailable
research is not an accepted status. A genuinely absent external channel may be
`not_applicable` only with discovery evidence and justification. Upstream issue,
PR, CI, documentation and maintainer-review research cannot be skipped.

`upstreaming/dossier_gate.py` runs in trusted `safe_outputs.pre-steps`, before
native Claim reconciliation can write Completion. It downloads staging from the
same run, reads only bounded JSON at the exact Claim namespace, rejects symlinks,
checks task/revision/head and issue-digest identity, and validates the dossier and
proposal. The proposal includes a required `develop` or `park` decision. A
`develop` decision supplies one admission class and 1..32 validated exact paths
or final-component globs. A `park` decision requires no class and no paths. Agent
files are never executed. An incomplete dossier fails the job before Completion
or upload. Explicit cancellation can proceed without a dossier but cannot smuggle
a completed intent. The trusted record job checks the verified artifact again
before accepting its dossier as evidence.

This is a completeness/provenance-shape check, not semantic proof that every
claim is true or that the model actually followed every link. Model-authored
coverage and graph evidence remain model judgment. Mechanical path and operation
gates bound development, while semantic human review occurs at upstream handoff.
The native Result proves artifact delivery, not the accuracy of research.

## Automatic lifecycle decision

A verified `develop` dossier moves directly to workflow-only fork provisioning
and bounded `riscv64` development. It does not create a scope-review prompt or
require named owners. A verified `park` dossier becomes idle and launches no
writer. An authorized human can override a parked result with a stale-proof
`force-develop` command that supplies the class, bounded paths and rationale.
Human approval is otherwise deferred until the exact clean head is ready for
upstream handoff.

The patch-development worker's detector remains unchanged. The separate Pi-only
detection incompatibility must not be silently resolved by disabling its detector
or switching its backend.

## Dependency updates and CI

See `dependencies/README.md` for weekly Dependabot coverage and coordinated
runtime/compiler updates. Authored Python CI invocations use `uv run`, including
source-pin synchronization and the hash-pinned compatibility installer. Tests
check that the research gate precedes native Completion and that only the
investigator is unsandboxed.
