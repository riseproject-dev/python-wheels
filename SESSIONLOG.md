# Session log

- Fixed queue liveness by continuing controller reconciliation after every dispatcher decision, including decisions made just before retry eligibility.
- Added append-only App-authored tracking-issue ledger comments with concise revision/state summaries, workflow links, and folded prefilled commands.
- Made trusted fork publication rewrite every proposed commit so both author and committer use the `riseproject-dev[bot]` identity.
- Diagnosed the dispatcher stall as reuse of an already-terminal Work graph after a valid worker `no_change` result was misclassified as rejected.
- Began fixing liveness by preserving `no_change`, making runner-label checks target-contract driven, and fencing terminal graph reuse.
- Added a main-branch pipeline-code push wake-up so deployed fixes reconcile immediately without relying on sparse GitHub schedule delivery or manual dispatch.
