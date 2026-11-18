# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Publication gate: exact Claim Result and artifact identity, from the
gh-aw v1.2.2 ``work-queue replay --json`` projection shape."""

import copy
import hashlib
import unittest

from upstreaming import queue_result as qr

WF = ".github/workflows/upstreaming-worker.lock.yml"
DATA = b"PK-fake-zip"
DIGEST = "sha256:" + hashlib.sha256(DATA).hexdigest()


def projection():
    return {
        "works": {"w1": {"work_id": "w1", "state": "completed", "claim_id": "c1", "barrier": "verified",
                         "result_commit_id": "q_r",
                         "result": {"version": 1, "outputs": [{"type": "upload_artifact", "resource": {
                             "kind": "artifact", "repository": "o/r", "id": "55", "target_run_id": "100",
                             "name": "claim-abc-upstreaming-out", "digest": DIGEST}}]}}},
        "claims": {"c1": {"kind": "Claim", "work_id": "w1", "claim_id": "c1", "dispatch_id": "d1",
                          "handle": "h", "state": "completed"}},
        "dispatches": {"d1": {"dispatch_id": "d1", "state": "bound", "run": {
            "run_id": "100", "run_attempt": 1, "repository": "o/r", "workflow": WF}}},
    }


def resolve(p, **kw):
    args = dict(work_id="w1", claim_id="c1", dispatch_id="d1", run_id="100", workflow=WF)
    args.update(kw)
    return qr.resolve(p, **args)


class TestReplayOutput(unittest.TestCase):
    def test_projection_on_stdout_or_stderr(self):
        import json
        import subprocess
        data = json.dumps(projection())
        for stdout, stderr in ((data, ""), ("", data)):
            p = subprocess.CompletedProcess([], 0, stdout, stderr)
            self.assertEqual(qr.replay_output(p), projection())
        for data in ('{}', '[]', 'warning\n{}'):
            with self.assertRaises(ValueError):
                qr.replay_output(subprocess.CompletedProcess([], 0, "", data))


class TestResolve(unittest.TestCase):
    def test_ok(self):
        a = resolve(projection())
        self.assertEqual((a.artifact_id, a.digest, a.result_commit), (55, DIGEST, "q_r"))
        p = projection()
        import json
        p["works"]["w1"]["result"] = json.dumps(p["works"]["w1"]["result"])   # RawMessage as string
        self.assertEqual(resolve(p).artifact_id, 55)

    def test_rejections(self):
        def mut(f):
            p = copy.deepcopy(projection())
            f(p)
            return p
        out0 = projection()["works"]["w1"]["result"]["outputs"][0]
        cases = {
            "missing work": mut(lambda p: p["works"].clear()),
            "other claim owns work": mut(lambda p: p["works"]["w1"].update(claim_id="c2")),
            "pending delivery": mut(lambda p: p["works"]["w1"].update(barrier="pending")),
            "failed delivery": mut(lambda p: p["works"]["w1"].update(barrier="failed")),
            "claim cancelled": mut(lambda p: p["claims"]["c1"].update(state="cancelled")),
            "claim other dispatch": mut(lambda p: p["claims"]["c1"].update(dispatch_id="d9")),
            "other run": mut(lambda p: p["dispatches"]["d1"]["run"].update(run_id="101")),
            "rerun attempt": mut(lambda p: p["dispatches"]["d1"]["run"].update(run_attempt=2)),
            "other workflow": mut(lambda p: p["dispatches"]["d1"]["run"].update(workflow="x.lock.yml")),
            "no artifact": mut(lambda p: p["works"]["w1"]["result"].update(outputs=[{"type": "noop"}])),
            "two artifacts": mut(lambda p: p["works"]["w1"]["result"].update(outputs=[out0, out0])),
            "foreign run artifact": mut(lambda p: p["works"]["w1"]["result"]["outputs"][0]["resource"].update(target_run_id="7")),
            "bad name": mut(lambda p: p["works"]["w1"]["result"]["outputs"][0]["resource"].update(name="x")),
        }
        for name, p in cases.items():
            with self.subTest(name), self.assertRaises(qr.ResultError):
                resolve(p)

    def test_metadata_and_bytes(self):
        a = resolve(projection())
        good = {"id": 55, "name": a.name, "expired": False, "workflow_run": {"id": 100}, "digest": DIGEST}
        qr.check_artifact_metadata(good, a)
        for change in ({"expired": True}, {"workflow_run": {"id": 9}}, {"digest": "sha256:" + "0" * 64},
                       {"name": "x"}):
            with self.subTest(change), self.assertRaises(qr.ResultError):
                qr.check_artifact_metadata({**good, **change}, a)
        qr.check_bytes(DATA, a)
        with self.assertRaises(qr.ResultError):
            qr.check_bytes(DATA + b"x", a)


if __name__ == "__main__":
    unittest.main()
