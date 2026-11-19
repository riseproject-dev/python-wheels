# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""End to end, locally: plan -> (agent) -> verified Result -> publish -> reconcile.

GitHub is replaced by a fake read-only API and local bare repositories; the
gh-aw queue itself is replaced by a hand-written ``replay --json``
projection in the gh-aw v1.2.2 shape. Nothing touches the network.
"""

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from upstreaming import artifact, capacity, controller, fork_publish, publisher, queue_result, reconcile, work
from upstreaming.tests.helpers import commit_files, contribution, git, init_repo, policy

WF = ".github/workflows/upstreaming-worker.lock.yml"


class FakeApi:
    """Answers the GET paths collect.py uses, from in-memory data."""

    def __init__(self, heads, runs=None, jobs=None):
        self.heads, self.runs, self.jobs = heads, runs or {}, jobs or {}

    def get(self, path):
        if "/branches/" in path:
            repo = path.split("/repos/")[1].split("/branches/")[0]
            h = self.heads.get(repo)
            if h is None:
                from upstreaming.collect import CollectError
                raise CollectError("HTTP 404")
            return {"commit": {"sha": h, "commit": {"tree": {"sha": "t" * 40}}, "parents": []}}
        if path.startswith("/repos/") and path.count("/") == 3:
            name = path[len("/repos/"):]
            return {"id": 2, "full_name": name, "default_branch": "main"}
        raise AssertionError(path)

    def paginate(self, path, key=None, max_pages=10):
        if "/artifacts" in path:
            rid = int(path.split("/runs/")[1].split("/")[0])
            return [{"id": rid * 10, "name": "cp312-manylinux_riscv64-", "size_in_bytes": 10, "expired": False}] \
                if rid in self.jobs else []
        if "/actions/runs?" in path:
            sha = path.split("head_sha=")[1].split("&")[0]
            return [r for r in self.runs.get("all", []) if r["head_sha"] == sha]
        if "/jobs" in path:
            rid = int(path.split("/runs/")[1].split("/")[0])
            return self.jobs.get(rid, [])
        return []


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.root = Path(self.tmp.name)
        up = init_repo(root / "up")
        self.base = commit_files(up, {".github/workflows/wheels.yml": "on: [push]\njobs: {}\n"})
        for name in ("example/proj", "riseproject-upstreaming/proj"):
            bare = root / f"{name}.git"
            bare.parent.mkdir(parents=True, exist_ok=True)
            git(root, "init", "-q", "--bare", "-b", "main", str(bare))
            git(up, "push", "-q", str(bare), "HEAD:refs/heads/main", "HEAD:refs/heads/riscv64")
        self.fork_bare = root / "riseproject-upstreaming/proj.git"
        self._saved = (fork_publish.URL_TEMPLATE, list(fork_publish.TEST_EXTRA_CONFIG))
        fork_publish.URL_TEMPLATE = f"file://{root}/{{}}.git"
        fork_publish.TEST_EXTRA_CONFIG[:] = ["-c", "protocol.file.allow=always"]
        self.rec = contribution(activity="idle", last_ci_evidence_id=None)
        self.rec["upstream"]["base_sha"] = self.base
        self.rec["fork"]["head_sha"] = self.base
        self.now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)

    def tearDown(self):
        fork_publish.URL_TEMPLATE, extra = self._saved
        fork_publish.TEST_EXTRA_CONFIG[:] = extra
        self.tmp.cleanup()

    def fork_head(self):
        return git(self.fork_bare, "rev-parse", "refs/heads/riscv64")

    def test_full_loop(self):
        pol = policy(read_only=False)
        # 1. Controller selects a development patch; work.py builds the Work node.
        res = controller.tick(contributions={"c": self.rec}, operations={}, consumed={}, projects={}, policy=pol,
                              inputs=controller.Inputs(now=self.now, pressure=capacity.Pressure(ok=True)))
        self.assertEqual(len(res.requested_effects), 1)
        node = work.node(res.requested_effects[0], self.rec, control_repo_id="123",
                         allowed_paths=[".github/workflows/*"])
        plan = work.plan([node])
        self.assertEqual(plan["dispatch"], {"pool": "upstreaming", "max_claims": 1, "max_dispatches": 1})
        task = node["payload"]
        self.assertEqual(task["effect_contract"]["outputs"][-1], {"type": "upload_artifact", "min": 1, "max": 1})
        self.assertEqual((task["fork_name"], task["fork_repository_id"]), ("proj", 2))

        # 2. The agent (simulated): patch in a clone, write the artifact files.
        agent = self.root / "agent"
        git(self.root, "clone", "-q", "-b", "riscv64", str(self.fork_bare), str(agent))
        commit_files(agent, {".github/workflows/wheels.yml": "on: [push]\njobs: {riscv64: {runs-on: ubuntu-24.04-riscv}}\n"},
                     msg="BLD: build riscv64 wheels")
        mbox = git(agent, "format-patch", "--stdout", self.base).encode() + b"\n"
        proposal = {"schema_version": 1, "contribution_id": task["contribution_id"], "outcome": "patch",
                    "expected_revision": task["revision"], "expected_head": task["expected_head"],
                    "ref": "riscv64", "reconstruction_base": task["expected_head"], "operation": "append",
                    "fork_repository_id": 2, "changed_files": [".github/workflows/wheels.yml"],
                    "patch_digest": hashlib.sha256(mbox).hexdigest(), "diagnosis": "add riscv64 row",
                    "progress": "requirement_fixed"}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("upstreaming-out/proposal.json", json.dumps(proposal))
            z.writestr("upstreaming-out/patches.mbox", mbox)
        zdata = buf.getvalue()
        digest = "sha256:" + hashlib.sha256(zdata).hexdigest()

        # 3. Native queue processing (simulated ledger): a verified Result for this Claim.
        projection = {
            "works": {"w1": {"claim_id": "c1", "barrier": "verified", "result_commit_id": "q_r", "result": {
                "version": 1, "outputs": [{"type": "upload_artifact", "resource": {
                    "kind": "artifact", "repository": "riseproject-dev/python-wheels", "id": "900",
                    "target_run_id": "4242", "name": "claim-x-upstreaming-out", "digest": digest}}]}}},
            "claims": {"c1": {"work_id": "w1", "claim_id": "c1", "dispatch_id": "d1", "state": "completed"}},
            "dispatches": {"d1": {"run": {"run_id": "4242", "run_attempt": 1, "workflow": WF}}}}
        art = queue_result.resolve(projection, work_id="w1", claim_id="c1", dispatch_id="d1",
                                   run_id="4242", workflow=WF)
        queue_result.check_bytes(zdata, art)
        out = self.root / "in"
        zpath = self.root / "p.zip"
        zpath.write_bytes(zdata)
        artifact.extract(zpath, out)

        # 4. Publish job: preflight, then rebuild + validate + leased push.
        pf = fork_publish.preflight(record=self.rec, task=task, proposal=proposal,
                                    fork_lookup=lambda n: {"id": 2, "full_name": n, "archived": False})
        self.assertEqual(pf["fork_name"], "proj")
        ops = []
        outcome = fork_publish.publish(
            record=self.rec, task=task, proposal=json.loads((out / "proposal.json").read_text()),
            mbox=(out / "patches.mbox").read_bytes(), token=None, observe_head=self.fork_head,
            scope=publisher.Scope(allowed_globs=task["allowed_paths"]), policy=pol,
            now=self.now.isoformat(), save_operation=ops.append, workdir=self.root / "pub",
            artifact=art.__dict__)
        self.assertEqual(outcome.status, "published", outcome.reason)
        new_head = self.fork_head()
        self.assertNotEqual(new_head, self.base)
        self.assertIn("artifact:900", outcome.operation["reason_ids"])

        # 5. Reconcile: fold the publication, observe the new head and its CI.
        rec = dict(self.rec, activity="agent_running")
        runs = {"all": [{"id": 7, "head_sha": new_head, "run_attempt": 1, "status": "completed",
                         "conclusion": "success", "workflow_id": 1, "event": "push", "path": ".github/workflows/wheels.yml"}]}
        jobs = {7: [{"id": 70, "run_id": 7, "name": "build riscv64", "status": "completed",
                     "conclusion": "success", "started_at": "x", "labels": ["ubuntu-24.04-riscv"]}]}
        api = FakeApi({"riseproject-upstreaming/proj": new_head}, runs, jobs)
        snap = reconcile.Snapshot(contributions={"c": rec}, operations={}, consumed={}, projects={}, evidence={})
        pub = {"status": outcome.status, "operation": ops[-1], "artifact": art.__dict__, "task": task}
        tick = reconcile.tick(api, snap, policy=pol, now=self.now, publications=[pub],
                              pressure=capacity.Pressure(ok=True))
        kinds = [k for k, _ in tick.staged]
        final = [r for k, r in tick.staged if k == "contributions"][-1]
        self.assertEqual(final["fork"]["head_sha"], new_head)
        self.assertEqual(final["revision"], self.rec["revision"] + 1)     # head change = new work revision
        self.assertEqual(final["proposal_artifact"]["artifact_id"], 900)
        self.assertEqual(final["publication_operation_id"], ops[-1]["operation_id"])
        self.assertTrue(final["last_ci_evidence_id"].startswith("ci-2-7-1"))
        self.assertIn("evidence", kinds)
        self.assertIn("operations", kinds)
        # Passed CI on the new head: nothing more for an agent to do right now.
        self.assertEqual(tick.report["requested_effects"], [])

    def test_result_without_publication_does_not_enter_waiting_ci(self):
        # A blocked proposal is a delivered Result, but nothing is pushed.
        rec = dict(self.rec, activity="agent_running")
        api = FakeApi({"riseproject-upstreaming/proj": self.base})
        snap = reconcile.Snapshot(contributions={"c": rec}, operations={}, consumed={}, projects={}, evidence={})
        pub = {"status": "rejected", "reason": "nothing to publish (outcome blocked)", "operation": None,
               "artifact": None, "task": {"contribution_id": rec["contribution_id"], "revision": rec["revision"]}}
        tick = reconcile.tick(api, snap, policy=policy(), now=self.now, publications=[pub],
                              pressure=capacity.Pressure(ok=True), observe=False)
        final = [r for k, r in tick.staged if k == "contributions"][-1]
        self.assertEqual(final["fork"]["head_sha"], self.base)
        self.assertNotEqual(final["activity"], "waiting_ci")


if __name__ == "__main__":
    unittest.main()


class TestPublicationRetry(unittest.TestCase):
    def setUp(self):
        self.rec = contribution(activity="agent_running")
        self.now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
        self.task = {"contribution_id": self.rec["contribution_id"], "revision": self.rec["revision"]}

    def tick(self, rec, pubs, now=None):
        snap = reconcile.Snapshot(contributions={"c": rec}, operations={}, consumed={}, projects={}, evidence={})
        return reconcile.tick(None, snap, policy=policy(read_only=False), now=now or self.now, publications=pubs,
                              pressure=capacity.Pressure(ok=True), observe=False)

    def final(self, t):
        return [r for k, r in t.staged if k == "contributions"][-1]

    def test_infra_error_schedules_publish_only_retry_then_waits_for_human(self):
        pub = {"status": "infra_error", "failure_class": "infrastructure", "reason": "HTTP 502",
               "task": self.task, "worker_run_id": "4242", "publication_artifact_id": 1}
        t = self.tick(self.rec, [pub])
        rec = self.final(t)
        self.assertEqual(rec["pending_publication"]["attempts"], 1)
        self.assertEqual(rec["activity"], "waiting_capacity")
        self.assertEqual(t.report["publication_retries"], [])          # backoff not elapsed
        self.assertEqual(t.report["requested_effects"], [])            # never a new agent task
        later = self.now.replace(hour=13)
        t2 = self.tick(rec, [pub], now=later)                          # same artifact: ignored
        self.assertEqual(t2.report["publication_retries"],
                         [{"type": "retry_publication", "contribution_id": rec["contribution_id"],
                           "worker_run_id": "4242", "attempt": 2}])
        rec2 = rec
        for n, aid in ((2, 2), (3, 3)):
            rec2 = self.final(self.tick(rec2, [dict(pub, publication_artifact_id=aid, attempt=n)], now=later))
        self.assertTrue(rec2["pending_publication"]["exhausted"])
        self.assertEqual(rec2["activity"], "waiting_human")
        self.assertEqual(self.tick(rec2, [], now=later.replace(hour=20)).report["publication_retries"], [])

    def test_validation_rejection_asks_agent_stale_does_not(self):
        rej = {"status": "rejected", "failure_class": "validation", "reason": "outside scope", "task": self.task,
               "worker_run_id": "1", "publication_artifact_id": 9}
        t = self.tick(self.rec, [rej])
        # The rejection makes it fix_needed and the same tick requests one repair.
        self.assertEqual([e["task"] for e in t.report["requested_effects"]], ["development_repair"])
        self.assertEqual(self.final(t)["active_work"]["task"], "development_repair")
        # Stale: no repair is requested (the next tick re-plans from the new head).
        stale = dict(rej, failure_class="stale", publication_artifact_id=10)
        t = self.tick(dict(self.rec, last_ci_evidence_id="ev-1"), [stale])
        self.assertEqual(t.report["requested_effects"], [])
        self.assertEqual(self.final(t)["activity"], "idle")

    def test_success_after_retry_clears_pending(self):
        rec = dict(self.rec, pending_publication={"worker_run_id": "4242", "attempts": 1, "last_reason": "x",
                                                  "next_attempt_at": self.now.isoformat()})
        ok = {"status": "published", "task": self.task, "worker_run_id": "4242", "publication_artifact_id": 5,
              "operation": None, "artifact": None}
        self.assertIsNone(self.final(self.tick(rec, [ok]))["pending_publication"])


class TestDispatchRecovery(unittest.TestCase):
    """A requested task whose dispatch never reached the queue (live run
    44379808515: the dispatcher failed before submitting, and its rerun was
    skipped) is dispatched again, then handed to a human."""

    def setUp(self):
        self.now = datetime(2026, 11, 18, 20, tzinfo=timezone.utc)
        self.rec = contribution(phase="investigation", activity="agent_running", revision=1)
        self.rec["active_work"] = {"dedupe_key": "example--proj/12@1:investigation", "task": "investigation",
                                   "revision": 1, "requested_at": "2026-11-18T19:22:14+00:00",
                                   "deadline_at": "2026-11-19T01:22:14+00:00", "dispatched_run_id": None}
        self.gid = work.graph_id(self.rec["active_work"]["dedupe_key"])

    def tick(self, runs, queue, rec=None, now=None):
        snap = reconcile.Snapshot(contributions={"c": rec or self.rec}, operations={}, consumed={},
                                  projects={}, evidence={})
        return reconcile.tick(None, snap, policy=policy(read_only=False), now=now or self.now, publications=[],
                              pressure=capacity.Pressure(ok=True), observe=False,
                              dispatcher_runs=runs, queue_works=queue)

    @staticmethod
    def drun(i, conclusion="failure", status="completed", at="2026-11-18T19:22:19Z"):
        return {"id": i, "status": status, "conclusion": conclusion, "created_at": at}

    def final(self, t):
        recs = [r for k, r in t.staged if k == "contributions"]
        return recs[-1] if recs else self.rec

    def test_failed_dispatch_is_relaunched_then_waits_for_human(self):
        t = self.tick([self.drun(1)], {})
        self.assertEqual(len(t.report["dispatch_relaunch"]), 1)
        rec = self.final(t)
        self.assertEqual(rec["active_work"]["dispatched_run_id"], "1")       # recorded, still requested
        self.assertEqual(rec["activity"], "agent_running")
        # Retry budget: 1 + retries.infrastructure_per_head_failure (2) dispatcher runs.
        t = self.tick([self.drun(2, "success"), self.drun(1)], {}, rec=rec)
        self.assertEqual(len(t.report["dispatch_relaunch"]), 1)
        t = self.tick([self.drun(3), self.drun(2, "success"), self.drun(1)], {}, rec=self.final(t))
        self.assertEqual(t.report["dispatch_relaunch"], [])
        rec = self.final(t)
        self.assertEqual((rec["activity"], rec["active_work"], rec["pending_human_action"]["kind"]),
                         ("waiting_human", None, "dispatch_failed"))

    def test_running_dispatcher_or_claimed_work_is_left_alone(self):
        t = self.tick([self.drun(1, None, "in_progress")], {})
        self.assertEqual(t.report["dispatch_relaunch"], [])
        for state in ("claimed", "completed", "cancelled"):
            t = self.tick([self.drun(1)], {self.gid: state})
            self.assertEqual(t.report["dispatch_relaunch"], [], state)
            self.assertEqual(t.report["dispatch_recovery"], [], state)

    def test_lost_launch_after_grace_and_unknown_queue(self):
        t = self.tick([], {}, now=datetime(2026, 11, 18, 19, 30, tzinfo=timezone.utc))
        self.assertEqual(t.report["dispatch_relaunch"], [])                  # within the grace period
        self.assertEqual(len(self.tick([], {}).report["dispatch_relaunch"]), 1)
        # Runs from before the request do not count.
        self.assertEqual(len(self.tick([self.drun(9, at="2026-11-18T18:00:00Z")], {}).report["dispatch_relaunch"]), 1)
        # Queue or runs unknown (CLI/API failure): decide nothing.
        self.assertEqual(self.tick(None, {}).report["dispatch_relaunch"], [])
        self.assertEqual(self.tick([self.drun(1)], None).report["dispatch_relaunch"], [])

    def test_plan_replays_committed_request_with_profile_per_task(self):
        req = work.request_from_active(self.rec)
        n = work.node(req, self.rec, control_repo_id="1", allowed_paths=["x"])
        self.assertEqual((n["worker_profile"], n["graph_id"]), ("upstreaming-investigator-v2", self.gid))
        # Identical across replays (the queue admits an identical node once).
        self.assertEqual(n, work.node(work.request_from_active(self.rec), self.rec, control_repo_id="1",
                                      allowed_paths=["x"]))
        dev = dict(self.rec, phase="development", active_work=dict(self.rec["active_work"], task="development_patch"))
        self.assertEqual(work.node(work.request_from_active(dev), dev, control_repo_id="1",
                                   allowed_paths=["x"])["worker_profile"], "upstreaming-worker")
        self.assertIsNone(work.request_from_active(dict(self.rec, paused=True)))
        self.assertIsNone(work.request_from_active(dict(self.rec, revision=2)))
