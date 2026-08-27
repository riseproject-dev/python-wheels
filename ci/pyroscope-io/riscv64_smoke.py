# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""End-to-end smoke test for the riscv64 pyroscope-io wheel.

Upstream tests its wheels with a Go suite that runs a Pyroscope server and
the workload in separate Docker containers, which the build container cannot
do. This drives the same path in-process: point the agent at a local HTTP
server, do work, and assert the uploaded pprof carries the frames of the
function that did it.
"""

import gzip
import hashlib
import http.server
import subprocess
import sys
import threading
import time

MARKERS = {"cpu": b"smoke_cpu_burn", "mem": b"smoke_mem_churn"}
PUSH_PATH = "/push.v1.PusherService/Push"


def smoke_cpu_burn(deadline):
    value = "riscv64"
    while time.time() < deadline:
        value = hashlib.sha256(value.encode()).hexdigest()
    return value


def smoke_mem_churn(deadline):
    retained = []
    while time.time() < deadline:
        retained.append(bytearray(64 * 1024))
        if len(retained) >= 256:
            del retained[:128]
        time.sleep(0.005)
    return len(retained)


def worker(mode, url):
    import pyroscope

    options = dict(
        application_name="riscv64.smoke",
        server_address=url,
        enable_logging=True,
        upload_interval=1,
        tags={"mode": mode},
    )
    if mode == "cpu":
        options.update(cpu_enabled=True)
    else:
        options.update(cpu_enabled=False, mem_enabled=True)

    pyroscope.configure(**options)
    deadline = time.time() + 15
    try:
        if mode == "cpu":
            smoke_cpu_burn(deadline)
        else:
            smoke_mem_churn(deadline)
    finally:
        pyroscope.shutdown()


class Collector(http.server.BaseHTTPRequestHandler):
    bodies = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if self.path.endswith(PUSH_PATH):
            Collector.bodies.append(body)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):
        pass


def run(mode):
    Collector.bodies = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:%d" % server.server_address[1]
    try:
        result = subprocess.run(
            [sys.executable, "-u", __file__, "worker", mode, url],
            capture_output=True,
            text=True,
            timeout=180,
        )
    finally:
        server.shutdown()

    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit("%s worker exited with %d" % (mode, result.returncode))

    bodies = Collector.bodies
    if not bodies:
        raise SystemExit("%s: agent uploaded no profile" % mode)

    marker = MARKERS[mode]
    profiles = b"".join(gzip.decompress(body) for body in bodies)
    if marker not in profiles:
        raise SystemExit(
            "%s: %d uploads (%d bytes) carry no %s frame"
            % (mode, len(bodies), len(profiles), marker.decode())
        )
    print("%s: %d uploads, %s sampled" % (mode, len(bodies), marker.decode()))


def main():
    import pyroscope

    print("pyroscope from", pyroscope.__file__)
    print("native from", pyroscope.lib.__file__)
    if "site-packages" not in pyroscope.__file__:
        raise SystemExit("imported the source tree, not the wheel")
    for mode in ("cpu", "mem"):
        run(mode)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(sys.argv[2], sys.argv[3])
    else:
        main()
