#!/bin/sh
# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

# Configure the identity the automation commits under: the GitHub App bot when
# the workflow minted an App token (APP_SLUG set by create-github-app-token),
# the Actions bot otherwise. The numeric account id in the address is what ties
# a commit to that bot on GitHub, and only the API knows it.

set -eu

if [ -n "${APP_SLUG:-}" ]; then
    name="${APP_SLUG}[bot]"
    id=$(gh api "/users/${APP_SLUG}%5Bbot%5D" --jq '.id')
else
    name="github-actions[bot]"
    id=41898282
fi

git config user.name "$name"
git config user.email "${id}+${name}@users.noreply.github.com"
