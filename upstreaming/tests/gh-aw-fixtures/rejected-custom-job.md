---
# Rejected route (plan 15.3): a credentialed custom safe-output job in a
# queue worker. gh-aw v1.2.2 refuses it:
#   work-queue: custom job "fork-push" requires a trusted per-Claim
#   delivery adapter with mode prepared
name: Rejected custom job fixture
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
safe-outputs:
  jobs:
    fork-push:
      description: "Push the patch to the fork"
      runs-on: ubuntu-latest
      inputs:
        patch:
          description: "patch"
          required: true
          type: string
      permissions:
        contents: read
      steps:
        - run: echo push
---
# fixture
