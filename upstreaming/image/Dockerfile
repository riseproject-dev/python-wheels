# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# Runner-free local CI reproduction image for linux/riscv64 (plan 13.1).
#
# Derived from the native runner image so the toolchain, Python/tool caches
# and package database match CI. It always builds from the runner image's
# current `prod` tag (what the ubuntu-24.04-riscv runners use).
# .github/workflows/upstreaming-image.yml rebuilds it weekly and whenever
# this directory changes, and records the base digest it resolved in the
# image's labels, so every reproduction can still name the exact base.
#
# Docker: the container uses the HOST's daemon through the bind-mounted
# /var/run/docker.sock (see run.sh). It never starts its own dockerd or
# containerd, so the runner image's daemons, docker-init (tini) PID-1
# wrapper and registration entrypoint are all removed. Docker's own
# `--init` (run.sh passes it) reaps child processes instead.
#
# This is the "derived layer" variant: deleting files in a derived layer does
# NOT erase the inherited bytes. If the published image must not contain the
# runner payload at all, switch to the filtered-copy variant
# (Dockerfile.filtered).
ARG BASE=ghcr.io/riseproject-dev/riscv-runner/runner/ubuntu-24.04:prod
FROM --platform=linux/riscv64 ${BASE}

USER root
RUN rm -rf /home/runner/actions-runner /usr/local/bin/riscv-runner-entrypoint.sh \
           /usr/local/bin/docker-init /usr/local/bin/dockerd /usr/local/bin/docker-proxy \
 && rm -f /home/runner/.credentials /home/runner/.runner \
 && (git config --system --unset-all credential.helper || true)
COPY --chmod=0755 entrypoint.sh /usr/local/bin/repro-entrypoint.sh
USER runner
ENV RUNNER_ARCH=RISCV64 UPSTREAMING_REPRO=1
WORKDIR /home/runner
ENTRYPOINT ["/usr/local/bin/repro-entrypoint.sh"]
CMD ["bash", "-l"]
