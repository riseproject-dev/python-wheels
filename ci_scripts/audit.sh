#!/bin/bash

# SPDX-FileCopyrightText: 2024 Rivos Inc.
# SPDX-FileCopyrightText: 2026 The RISE Project

# SPDX-License-Identifier: Apache-2.0

# This script is based on the one located here:
# https://gitlab.com/riseproject/python/wheel_builder/-/blob/main/ci_scripts/audit.sh
# It is designed to run pip-audit against the list of packages built by RISE to
# identify any vulnerabilities that may need to be addressed. You can view the
# PyPI page for more details: https://pypi.org/project/pip-audit/
set -e

apt-get update -qq && apt-get install -qq -y python3 python3-venv
python3 -m venv packages-$1-venv
. packages-$1-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pip-audit
python -m pip_audit -r packages.txt --format json --output audit-report.json || true

