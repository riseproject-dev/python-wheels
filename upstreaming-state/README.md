# upstreaming-state

Durable lifecycle state for the riscv64 upstreaming pipeline. Machine-owned:
only the trusted state publisher (`upstreaming/state_commit.py`)
writes here, and every state commit is checked by
`python -m upstreaming check-state-diff` before it is pushed.

Layout and schemas: see `upstreaming/README.md`. Do not hand-edit
records; corrections go through `/upstreaming` commands or a reviewed
migration.
