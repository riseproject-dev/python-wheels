#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
# Credential-free command entrypoint: no runner registration, no tokens.
for v in GITHUB_TOKEN GH_TOKEN ACTIONS_RUNTIME_TOKEN ACTIONS_ID_TOKEN_REQUEST_TOKEN \
         RUNNER_TOKEN JIT_CONFIG; do
    unset "$v"
done
exec "$@"
