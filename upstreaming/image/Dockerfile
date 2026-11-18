# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# Runner-free local CI reproduction image for linux/riscv64 (plan 13.1).
#
# Derived from the native runner image so the toolchain, Python/tool caches
# and package database match CI. The base is pinned by digest (the
# `ubuntu-24.04:prod` index resolved on 2026-11-18); mutable tags are
# discovery input only. Re-resolve and review the digest to update it.
#
# This is the "derived layer" variant: it replaces the Actions-runner
# registration entrypoint with a plain command entrypoint and removes the
# runner payload from the final filesystem view. Deleting files in a derived
# layer does NOT erase the inherited bytes; if the published image must not
# contain the runner payload at all, switch to the filtered-copy variant
# (Dockerfile.filtered). Publication to GHCR needs separate authorization.
ARG BASE=ghcr.io/riseproject-dev/riscv-runner/runner/ubuntu-24.04@sha256:48874e63b5f9007cf0424488182ce2845d303a92a211c92fd459c29a0a0620ef
FROM --platform=linux/riscv64 ${BASE}

USER root
RUN rm -rf /home/runner/actions-runner /usr/local/bin/riscv-runner-entrypoint.sh \
 && rm -f /home/runner/.credentials /home/runner/.runner \
 && git config --system --unset-all credential.helper || true
COPY --chmod=0755 entrypoint.sh /usr/local/bin/repro-entrypoint.sh
USER runner
ENV RUNNER_ARCH=RISCV64 UPSTREAMING_REPRO=1
WORKDIR /home/runner
ENTRYPOINT ["/usr/local/bin/docker-init", "--", "/usr/local/bin/repro-entrypoint.sh"]
CMD ["bash", "-l"]
