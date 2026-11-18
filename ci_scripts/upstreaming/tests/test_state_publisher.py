# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Section 21: state publisher final-tree checks, hostile publisher inputs."""

import json
import tempfile
import unittest
from pathlib import Path

from ci_scripts.upstreaming import publisher, state
from ci_scripts.upstreaming.common import canonical_json
from ci_scripts.upstreaming.tests.helpers import commit_files, contribution, git, init_repo, policy


class TestStateDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = init_repo(Path(self.tmp.name) / "control")
        self.base = commit_files(self.repo, {"README.md": "x\n", ".github/workflows/a.yml": "on: push\n"})
        self.p = policy()
        self.rec = contribution()
        self.path = state.record_path("contributions", self.rec)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, cand):
        return state.validate_state_diff(self.repo, self.base, cand, self.p)

    def test_valid_state_commit(self):
        c = commit_files(self.repo, {self.path: canonical_json(self.rec)})
        rep = self.check(c)
        self.assertTrue(rep.ok, rep.problems)

    def test_rejects_non_state_and_mixed(self):
        c = commit_files(self.repo, {self.path: canonical_json(self.rec),
                                     ".github/workflows/a.yml": "on: [push, schedule]\n"})
        rep = self.check(c)
        self.assertIn(".github/workflows/a.yml: outside upstreaming-state/", rep.problems)

    def test_rejects_invalid_schema_and_identity_mismatch(self):
        bad = dict(self.rec, phase="shipping")
        c = commit_files(self.repo, {self.path: canonical_json(bad)})
        self.assertFalse(self.check(c).ok)
        git(self.repo, "reset", "-q", "--hard", self.base)
        c = commit_files(self.repo, {"upstreaming-state/contributions/other.json": canonical_json(self.rec)})
        self.assertTrue(any("identity" in p for p in self.check(c).problems))

    def test_rejects_symlink_mode_and_secret(self):
        link = self.repo / "upstreaming-state/contributions/link.json"
        link.parent.mkdir(parents=True)
        link.symlink_to("../../README.md")
        git(self.repo, "add", str(link.relative_to(self.repo)))
        git(self.repo, "commit", "-q", "-m", "l")
        self.assertTrue(any("mode 120000" in p for p in self.check(git(self.repo, "rev-parse", "HEAD")).problems))
        git(self.repo, "reset", "-q", "--hard", self.base)
        c = commit_files(self.repo, {self.path: canonical_json(self.rec)}, mode=0o755)
        self.assertTrue(any("mode 100755" in p for p in self.check(c).problems))
        git(self.repo, "reset", "-q", "--hard", self.base)
        leaked = dict(self.rec, blocked_reason="token ghp_" + "A" * 36)
        c = commit_files(self.repo, {self.path: canonical_json(leaked)})
        self.assertTrue(any("credential" in p for p in self.check(c).problems))

    def test_rejects_delete_rename_escape_and_stale_base(self):
        c1 = commit_files(self.repo, {self.path: canonical_json(self.rec)})
        base2 = c1
        (self.repo / "docs").mkdir()
        git(self.repo, "mv", self.path, "docs/escaped.json")
        git(self.repo, "commit", "-q", "-m", "mv")
        rep = state.validate_state_diff(self.repo, base2, git(self.repo, "rev-parse", "HEAD"), self.p)
        self.assertTrue(any("deletion" in p for p in rep.problems))
        self.assertTrue(any("docs/escaped.json: outside" in p for p in rep.problems))
        # Candidate not directly on top of the trusted base (concurrent main commit).
        rep = state.validate_state_diff(self.repo, self.base, git(self.repo, "rev-parse", "HEAD"), self.p)
        self.assertTrue(any("single commit" in p for p in rep.problems))

    def test_case_collision(self):
        other = dict(self.rec, contribution_id="Example--proj/12")
        c = commit_files(self.repo, {self.path: canonical_json(self.rec),
                                     state.record_path("contributions", other): canonical_json(other)})
        self.assertTrue(any("collides" in p for p in self.check(c).problems))

    def test_store_roundtrip_and_event_sequence(self):
        st = state.StateStore(self.repo, self.p)
        st.stage("contributions", self.rec)
        ev = {"schema_version": 1, "contribution_id": self.rec["contribution_id"], "sequence": 0,
              "at": self.rec["created_at"], "kind": "x", "from": {}, "to": {},
              "cause": {"type": "observation", "id": None}, "revision_bumped": False}
        p1 = st.stage("events", ev)
        p2 = st.stage("events", ev)
        self.assertNotEqual(p1, p2)
        st.write_staged()
        self.assertEqual(len(st.load_all("events")), 2)
        self.assertEqual(st.next_event_sequence(self.rec["contribution_id"]), 2)
        (self.repo / self.path).write_text(json.dumps(dict(self.rec, schema_version=9)))
        with self.assertRaises(state.StateError):
            st.load_all("contributions")


class TestPublisherValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = init_repo(Path(self.tmp.name) / "fork")
        self.base = commit_files(self.repo, {
            ".github/workflows/wheels.yml": "on: [push]\njobs: {}\n",
            "pyproject.toml": "[project]\nname='p'\n",
            "src/a.c": "int a;\n"})
        self.scope = publisher.Scope(allowed_globs=[".github/workflows/*", "pyproject.toml", "src/*"])

    def tearDown(self):
        self.tmp.cleanup()

    def validate(self, cand, expected=None, **kw):
        sc = publisher.Scope(**{**self.scope.__dict__, **kw})
        return publisher.validate_update(self.repo, base=self.base, expected_head=expected or self.base,
                                         candidate=cand, scope=sc)

    def test_ok_append(self):
        c = commit_files(self.repo, {".github/workflows/wheels.yml": "on: [push]\njobs: {riscv: {}}\n"},
                         msg="ci: build riscv64 wheels")
        rep = self.validate(c)
        self.assertTrue(rep.ok, rep.problems)
        self.assertTrue(rep.touches_workflows)

    def test_outside_scope_and_hostile_paths(self):
        c = commit_files(self.repo, {"setup.py": "import os\n"})
        self.assertTrue(any("outside the approved" in p for p in self.validate(c).problems))

    def test_symlink_submodule_exec(self):
        (self.repo / "src/link").symlink_to("/etc/passwd")
        git(self.repo, "add", "src/link")
        git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{self.base},src/sub")
        git(self.repo, "commit", "-q", "-m", "x")
        c = git(self.repo, "rev-parse", "HEAD")
        probs = self.validate(c).problems
        self.assertTrue(any("symlink" in p for p in probs))
        self.assertTrue(any("submodule" in p for p in probs))
        git(self.repo, "reset", "-q", "--hard", self.base)
        c = commit_files(self.repo, {"src/run.sh": "#!/bin/sh\n"}, mode=0o755)
        self.assertTrue(any("executable" in p for p in self.validate(c).problems))

    def test_forbidden_workflow_content(self):
        for content, what in [
            ("on: pull_request_target\n", "pull_request_target"),
            ("permissions:\n  id-token: write\n", "OIDC"),
            ("env:\n  T: ${{ secrets.PYPI_TOKEN }}\n", "secret"),
            ("run: echo \"${{ github.event.issue.body }}\"\n", "untrusted"),
            ("- uses: pypa/gh-action-pypi-publish@release/v1\n", "publication"),
        ]:
            with self.subTest(what):
                git(self.repo, "reset", "-q", "--hard", self.base)
                c = commit_files(self.repo, {".github/workflows/wheels.yml": "on: [push]\n" + content})
                self.assertTrue(any(what in p for p in self.validate(c).problems), what)

    def test_debug_commits_and_upstream_facing(self):
        commit_files(self.repo, {".github/workflows/wheels.yml": "on: [push]\n# fork\n"},
                     msg="{debug} run wheel jobs on the fork")
        c = commit_files(self.repo, {"src/a.c": "int a = 1;\n"}, msg="fix riscv64 build")
        self.assertEqual(len(publisher.debug_commits(self.repo, self.base, c)), 1)
        self.assertTrue(self.validate(c).ok)
        self.assertTrue(any("{debug}" in p for p in self.validate(c, upstream_facing=True).problems))

    def test_history_modes(self):
        h1 = commit_files(self.repo, {"src/a.c": "int a = 1;\n"})
        git(self.repo, "reset", "-q", "--hard", self.base)
        h2 = commit_files(self.repo, {"src/a.c": "int a = 2;\n"})
        self.assertTrue(any("does not descend from the expected head" in p
                            for p in self.validate(h2, expected=h1).problems))
        self.assertTrue(self.validate(h2, expected=h1, history="rewrite").ok)
        git(self.repo, "checkout", "-q", "--orphan", "x")
        orphan = commit_files(self.repo, {"src/a.c": "x\n"})
        self.assertTrue(any("approved upstream base" in p
                            for p in self.validate(orphan, history="rewrite").problems))

    def test_lease(self):
        args = publisher.lease_refspec("1" * 40, "2" * 40)
        self.assertEqual(args[0], "--force-with-lease=refs/heads/riscv64:" + "2" * 40)
        with self.assertRaises(ValueError):
            publisher.lease_refspec("1" * 40, "2" * 40, ref="main")
        with self.assertRaises(ValueError):
            publisher.lease_refspec("1" * 40, "")

    def test_safe_env_ignores_user_config(self):
        env = publisher.safe_env()
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("GITHUB_TOKEN", env)


if __name__ == "__main__":
    unittest.main()
