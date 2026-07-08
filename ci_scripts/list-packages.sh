#!/bin/bash

# SPDX-FileCopyrightText: 2024 Rivos Inc.
# SPDX-FileCopyrightText: 2026 The RISE Project

# SPDX-License-Identifier: Apache-2.0
#
# This script is originally from:
#
# https://gitlab.com/riseproject/python/wheel_builder/-/blob/main/ci_scripts/list-packages.sh
#
# Its purpose is to test installation of each package RISE supports from the
# registry, then list the packages which were actually installed with their
# versions so that any uninstallable packages can be identified.

set -e

if [ "$#" -ne 1 ]; then
    echo "list-packages name-prefix"
    exit 1
fi

apt-get update -qq && apt-get install -qq -y python3 python3-venv
python3 -m venv packages-$1-venv
. packages-$1-venv/bin/activate
python -m pip install --upgrade pip
pip install --only-binary=:all: -r packages.txt
pip list > $1-installed.txt
