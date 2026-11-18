---
# Rejected route (plan 15.3): built-in cross-repository PR-branch push from a
# queue worker. It compiles, but gh-aw v1.2.2's Claim delivery verifier has
# no case for push_to_pull_request_branch, so a native Result could never be
# recorded for it (work_queue_delivery.cjs verifyBuiltinDeliveryOutput).
# Kept so a future gh-aw release that changes either fact is noticed.
name: Rejected direct push fixture
on:
  workflow_dispatch:
permissions:
  contents: read
engine: claude
network:
  allowed: [defaults]
tools:
  work-queue:
    require-assignment: true
    worker: true
checkout:
  - repository: riseproject-upstreaming/example
    path: ./fork
    current: true
    ref: riscv64
safe-outputs:
  push-to-pull-request-branch:
    target: "*"
    required-title-prefix: "[riscv64] "
    target-repo: riseproject-upstreaming/example
    fallback-as-pull-request: false
    head-github-app:
      client-id: ${{ vars.RISEPROJECT_APP_CLIENT_ID }}
      private-key: ${{ secrets.RISEPROJECT_APP_PRIVATE_KEY }}
      owner: riseproject-upstreaming
      repositories: [example]
---
# fixture
