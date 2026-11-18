# upstreaming-state

Durable lifecycle state for the riscv64 upstreaming pipeline. Machine-owned:
only the trusted state publisher (`ci_scripts/upstreaming/state_commit.py`)
writes here, and every state commit is checked by
`python -m ci_scripts.upstreaming check-state-diff` before it is pushed.

Layout and schemas: see `ci_scripts/upstreaming/README.md`. Do not hand-edit
records; corrections go through `/upstreaming` commands or a reviewed
migration.
