# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Trusted control code for the riscv64 upstreaming pipeline.

See ``ci_scripts/upstreaming/README.md``. Nothing in this package performs a
remote mutation: every module is either pure policy/validation logic or a
read-only collector. Remote writers are separate, separately authorized jobs.
"""
