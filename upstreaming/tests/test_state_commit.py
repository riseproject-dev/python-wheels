# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Section 21: state-only push with a concurrent downstream commit."""

import tempfile
import unittest
from pathlib import Path

from upstreaming import state, state_commit
from upstreaming.tests.helpers import commit_files, contribution, git, init_repo, policy


class TestStateCommit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin = root / "origin.git"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.other = init_repo(root / "other")
        commit_files(self.other, {"README.md": "x\n"})
        git(self.other, "remote", "add", "origin", str(self.origin))
        git(self.other, "push", "-q", "origin", "HEAD:main")
        self.pub = root / "pub"
        git(root, "clone", "-q", str(self.origin), str(self.pub))
        self.rec = contribution()
        self.path = state.record_path("contributions", self.rec)
        self.p = policy(read_only=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_only_refuses(self):
        with self.assertRaises(state_commit.PublishError):
            state_commit.publish(self.pub, remote="origin", branch="main",
                                 records_for=lambda tip: {self.path: self.rec},
                                 message="state", policy=policy())

    def test_race_rebuilds_on_new_tip_without_reverting(self):
        # A downstream commit lands between our fetch and push.
        calls = []

        def records_for(tip):
            calls.append(tip)
            if len(calls) == 1:
                commit_files(self.other, {"docs/packages/x.yaml": "v\n"}, msg="downstream")
                git(self.other, "push", "-q", "origin", "HEAD:main")
            return {self.path: self.rec}

        sha = state_commit.publish(self.pub, remote="origin", branch="main", records_for=records_for,
                                   message="state: update", policy=self.p, recheck=lambda tip: True)
        self.assertEqual(len(calls), 2)
        files = git(self.origin, "ls-tree", "-r", "--name-only", sha).split("\n")
        self.assertIn("docs/packages/x.yaml", files)  # downstream commit preserved
        self.assertIn(self.path, files)
        self.assertEqual(git(self.origin, "rev-parse", "main"), sha)

    def test_recheck_failure_defers(self):
        with self.assertRaises(state_commit.PublishError):
            state_commit.publish(self.pub, remote="origin", branch="main",
                                 records_for=lambda tip: {self.path: self.rec}, message="s",
                                 policy=self.p, recheck=lambda tip: False)

    def test_refuses_non_state_and_invalid(self):
        with self.assertRaises(state_commit.PublishError):
            state_commit.publish(self.pub, remote="origin", branch="main",
                                 records_for=lambda tip: {".github/workflows/x.yml": {}}, message="s",
                                 policy=self.p)
        with self.assertRaises(state_commit.PublishError):
            state_commit.publish(self.pub, remote="origin", branch="main",
                                 records_for=lambda tip: {self.path: dict(self.rec, phase="bogus")},
                                 message="s", policy=self.p)


if __name__ == "__main__":
    unittest.main()


class TestRecordsFromCheckout(unittest.TestCase):
    def test_changed_state_files_only(self):
        with tempfile.TemporaryDirectory() as d:
            repo = init_repo(Path(d) / "r")
            rec = contribution()
            path = state.record_path("contributions", rec)
            commit_files(repo, {"README.md": "x\n"})
            from upstreaming.common import canonical_json
            (repo / path).parent.mkdir(parents=True)
            (repo / path).write_text(canonical_json(rec))
            (repo / "README.md").write_text("changed\n")    # outside state: ignored
            got = state_commit.records_from_checkout(repo, "HEAD")
            self.assertEqual(list(got), [path])
            git(repo, "add", path)
            git(repo, "commit", "-q", "-m", "s")
            (repo / path).unlink()
            with self.assertRaises(state_commit.PublishError):
                state_commit.records_from_checkout(repo, "HEAD")
