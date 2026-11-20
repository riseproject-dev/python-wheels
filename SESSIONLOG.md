# Session log

- Fixed queue liveness by continuing controller reconciliation after every dispatcher decision, including decisions made just before retry eligibility.
- Added append-only App-authored tracking-issue ledger comments with concise revision/state summaries, workflow links, and folded prefilled commands.
- Made trusted fork publication rewrite every proposed commit so both author and committer use the `riseproject-dev[bot]` identity.
