# Session log

- Fixed queue liveness by continuing controller reconciliation after every dispatcher decision, including decisions made just before retry eligibility.
- Added append-only App-authored tracking-issue ledger comments with concise revision/state summaries, workflow links, and folded prefilled commands.
- Made trusted fork publication rewrite every proposed commit so both author and committer use the `riseproject-dev[bot]` identity.
- Diagnosed the dispatcher stall as reuse of an already-terminal Work graph after a valid worker `no_change` result was misclassified as rejected.
- Began fixing liveness by preserving `no_change`, making runner-label checks target-contract driven, and fencing terminal graph reuse.
- Added a main-branch pipeline-code push wake-up so deployed fixes reconcile immediately without relying on sparse GitHub schedule delivery or manual dispatch.
- The first autonomous deployment wake-up exposed invalid `recovery` event causes; changed them to schema-valid observations and added end-to-end staged-record validation.
- Autonomous recovery moved immutables to exact-head handoff, then exposed a same-tick race that retained and dispatched obsolete Work; added handoff cleanup and final-state relaunch filtering.
- Fenced late non-publishing worker outcomes so an obsolete task cannot regress an already-authoritative exact-head handoff.
