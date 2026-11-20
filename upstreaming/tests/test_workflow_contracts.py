# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Prevent accidental loss of the investigator and CI runtime boundaries."""
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).parents[2]
WF = ROOT / ".github/workflows"


def source(name):
    return yaml.safe_load((WF / f"{name}.md").read_text().split("---", 2)[1])


def run_scripts(value):
    if isinstance(value, dict):
        if isinstance(value.get("run"), str):
            yield value["run"]
        for child in value.values():
            yield from run_scripts(child)
    elif isinstance(value, list):
        for child in value:
            yield from run_scripts(child)


class TestWorkflowContracts(unittest.TestCase):
    def test_only_investigator_unsandboxed(self):
        investigator = source("upstreaming-investigator")
        self.assertFalse(investigator["strict"])
        self.assertFalse(investigator["sandbox"]["agent"])
        self.assertFalse(investigator["safe-outputs"]["threat-detection"])
        self.assertEqual(investigator["permissions"]["contents"], "read")
        self.assertNotIn("publish", investigator["jobs"])
        self.assertEqual(investigator["engine"]["extensions"],
                         ["npm:pi-web-access@0.48.0", "npm:pi-subagents@0.89.0"])
        self.assertNotIn("github", investigator["tools"])
        github = investigator["mcp-servers"]["github-authenticated"]
        self.assertTrue(github["required"])
        self.assertEqual(github["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"], "${{ github.token }}")
        self.assertEqual(github["env"]["GITHUB_READ_ONLY"], "1")
        self.assertIn("issue_read", github["allowed"])
        self.assertIn("pull_request_read", github["allowed"])
        graph = investigator["mcp-servers"]["project-graph"]
        self.assertTrue(graph["required"])
        self.assertEqual(graph["container"], "ghcr.io/riseproject-dev/sw-ecosystem/project-graph-mcp:latest")
        self.assertEqual(graph["allowed"], ["project_graph_query"])
        current_text = (WF / "upstreaming-investigator.md").read_text()
        self.assertIn("read-only web extension", current_text)
        self.assertIn("Do not use the web extension's anonymous GitHub fetcher", current_text)
        for name in ("upstreaming-worker", "upstreaming-dispatcher"):
            config = source(name)
            self.assertTrue(config["strict"])
            self.assertNotEqual(config.get("sandbox", {}).get("agent"), False)
            self.assertFalse(config.get("features", {}).get("dangerously-disable-sandbox-agent", False))

    def test_completeness_gate_precedes_durable_completion(self):
        lock = yaml.safe_load((WF / "upstreaming-investigator.lock.yml").read_text())
        steps = lock["jobs"]["safe_outputs"]["steps"]
        names = [s.get("name") for s in steps]
        self.assertLess(names.index("Require complete research before native queue Completion"),
                        names.index("Reconcile work queue claim"))
        self.assertLess(names.index("Require complete research before native queue Completion"),
                        names.index("Process Safe Outputs"))
        self.assertNotIn("detection", lock["jobs"])
        notify = lock["jobs"]["notify"]
        self.assertEqual(set(notify["needs"]), {"safe_outputs", "record"})
        self.assertNotIn("issues", notify["permissions"])
        notify_text = str(notify)
        self.assertIn("upstreaming.dossier_comment", notify_text)
        self.assertIn("upstreaming-publication", notify_text)

    def test_development_pr_writer_is_restricted_to_one_verified_fork(self):
        workflow = yaml.safe_load((WF / "upstreaming-dev-pr.yml").read_text())
        token = next(step for step in workflow["jobs"]["create"]["steps"] if step.get("id") == "fork-token")
        self.assertEqual(token["with"]["permission-pull-requests"], "write")
        self.assertEqual(token["with"]["permission-contents"], "read")
        self.assertEqual(token["with"]["permission-actions"], "write")
        self.assertEqual(token["with"]["permission-administration"], "write")
        self.assertEqual(token["with"]["repositories"], "${{ steps.target.outputs.fork_name }}")

    def test_provisioning_administration_is_restricted_to_one_verified_fork(self):
        provision = yaml.safe_load((WF / "upstreaming-provision.yml").read_text())
        token = next(step for step in provision["jobs"]["provision"]["steps"] if step.get("id") == "fork-token")
        self.assertEqual(token["with"]["permission-administration"], "write")
        self.assertEqual(token["with"]["repositories"], "${{ steps.create.outputs.fork_name }}")
        self.assertEqual(token["with"]["owner"], "riseproject-upstreaming")

    def test_native_workers_explicitly_dispatch_controller_after_terminal_jobs(self):
        for profile, needs in (("upstreaming-worker", {"safe_outputs", "publish"}),
                               ("upstreaming-investigator", {"safe_outputs", "record", "notify"}),
                               ("upstreaming-dispatcher", {"safe_outputs"})):
            config = source(profile)
            job = config["jobs"]["continuation"]
            self.assertEqual(set(job["needs"]), needs)
            self.assertEqual(job["if"], "always()")
            token = next(step for step in job["steps"] if step.get("id") == "control-token")
            self.assertEqual(token["with"]["owner"], "riseproject-dev")
            self.assertEqual(token["with"]["repositories"], "python-wheels")
            self.assertEqual(token["with"]["permission-contents"], "read")
            self.assertEqual(token["with"]["permission-actions"], "write")
            self.assertEqual(set(token["with"]), {"client-id", "private-key", "owner", "repositories",
                                                   "permission-contents", "permission-actions"})
            self.assertIn("upstreaming-controller.yml", str(job))

    def test_controller_pipeline_push_wakeup_excludes_state_commits(self):
        controller = yaml.safe_load((WF / "upstreaming-controller.yml").read_text())
        trigger = controller.get("on", controller.get(True))["push"]
        self.assertEqual(trigger["branches"], ["main"])
        self.assertIn("upstreaming/**", trigger["paths"])
        self.assertIn(".github/workflows/upstreaming-*.yml", trigger["paths"])
        self.assertNotIn("upstreaming-state/**", trigger["paths"])
        condition = controller["jobs"]["filter"]["if"]
        self.assertIn("github.event_name == 'push'", condition)

    def test_controller_posts_append_only_app_authored_issue_ledger(self):
        controller = yaml.safe_load((WF / "upstreaming-controller.yml").read_text())
        steps = controller["jobs"]["reconcile"]["steps"]
        token = next(step for step in steps if step.get("id") == "ledger-token")
        self.assertEqual(token["with"]["owner"], "riseproject-dev")
        self.assertEqual(token["with"]["repositories"], "python-wheels")
        self.assertEqual(token["with"]["permission-issues"], "write")
        ledger = next(step for step in steps if step.get("name") == "Append concise lifecycle entries to tracking issues")
        self.assertEqual(ledger["env"]["GH_TOKEN"], "${{ steps.ledger-token.outputs.token }}")
        self.assertIn("upstreaming.status_ledger", ledger["run"])

    def test_destination_tokens_use_only_destination_app_credentials(self):
        paths = [WF / "upstreaming-provision.yml", WF / "upstreaming-dev-pr.yml",
                 WF / "upstreaming-publish-retry.yml", WF / "upstreaming-worker.md"]
        for path in paths:
            text = path.read_text()
            blocks = re.findall(r"client-id: .*?\n\s+private-key: .*?\n\s+owner: riseproject-upstreaming", text)
            self.assertTrue(blocks, path.name)
            for block in blocks:
                self.assertIn("RISEPROJECT_UPSTREAMING_APP_CLIENT_ID", block)
                self.assertIn("RISEPROJECT_UPSTREAMING_APP_PRIVATE_KEY", block)
                self.assertNotIn("vars.RISEPROJECT_APP_CLIENT_ID", block)

    def test_controller_explains_rejected_commands_with_issue_app_token(self):
        controller = yaml.safe_load((WF / "upstreaming-controller.yml").read_text())
        steps = controller["jobs"]["reconcile"]["steps"]
        feedback = next(step for step in steps if step.get("name") == "Explain rejected commands on their tracking issues")
        self.assertEqual(feedback["env"]["GH_TOKEN"], "${{ steps.ledger-token.outputs.token }}")
        self.assertIn("upstreaming.command_feedback", feedback["run"])

    def test_controller_reconciles_current_main_not_stale_event_sha(self):
        controller = yaml.safe_load((WF / "upstreaming-controller.yml").read_text())
        for job_name in ("observe", "reconcile"):
            checkout = next(step for step in controller["jobs"][job_name]["steps"]
                            if str(step.get("uses", "")).startswith("actions/checkout@"))
            self.assertEqual(checkout["with"]["ref"], "main")
            self.assertFalse(checkout["with"]["persist-credentials"])

    def test_controller_uses_publication_artifact_not_overall_run_status(self):
        text = (WF / "upstreaming-controller.yml").read_text()
        self.assertIn('actions/workflows/$wf/runs?per_page=20', text)
        self.assertNotIn('actions/workflows/$wf/runs?status=completed', text)
        self.assertIn("Artifact existence, not overall run", text)

    def test_controller_chains_every_pipeline_completion_and_has_schedule_fallback(self):
        controller = yaml.safe_load((WF / "upstreaming-controller.yml").read_text())
        triggers = controller.get("on", controller.get(True))
        self.assertEqual(triggers["schedule"], [{"cron": "*/5 * * * *"}])
        self.assertEqual(set(triggers["workflow_run"]["workflows"]), {
            "Upstreaming investigator", "Upstreaming worker",
            "Upstreaming fork provisioning", "Upstreaming development PR",
            "Upstreaming publish retry"})
        self.assertEqual(triggers["workflow_run"]["types"], ["completed"])
        self.assertIn("labeled", triggers["issues"]["types"])
        self.assertIn("unlabeled", triggers["issues"]["types"])
        filter_if = controller["jobs"]["filter"]["if"]
        self.assertIn("github.event.action == 'unlabeled'", filter_if)
        self.assertIn("github.event.label.name == 'upstreaming-request'", filter_if)
        self.assertIn("created", triggers["issue_comment"]["types"])
        self.assertIn("contains(github.event.comment.body, '/upstreaming ')", filter_if)
        self.assertNotIn("startsWith(github.event.comment.body", filter_if)
        self.assertIn("github.event_name == 'workflow_run'", controller["jobs"]["filter"]["if"])

    def test_command_acknowledgement_is_fast_idempotent_and_not_serialized(self):
        controller = yaml.safe_load((WF / "upstreaming-controller.yml").read_text())
        self.assertNotIn("concurrency", controller)
        ack = controller["jobs"]["acknowledge-command"]
        self.assertNotIn("needs", ack)
        self.assertNotIn("concurrency", ack)
        self.assertEqual(ack["if"],
                         "github.event_name == 'issue_comment' && github.event.issue.pull_request == null")
        script = ack["steps"][-1]["run"]
        self.assertIn("awk 'NF { print; exit }'", script)
        self.assertIn("reactions?per_page=100", script)
        self.assertIn('riseproject-dev[bot]', script)
        self.assertIn("-f content='+1'", script)
        reconcile = controller["jobs"]["reconcile"]
        self.assertEqual(reconcile["concurrency"]["group"], "python-wheels-upstreaming-controller")
        self.assertFalse(reconcile["concurrency"]["cancel-in-progress"])

    def test_worker_brackets_untrusted_output_with_stop_commands(self):
        worker = source("upstreaming-worker")
        before = worker["pre-agent-steps"][0]
        self.assertIn("openssl rand -hex 32", before["run"])
        self.assertEqual(before["id"], "suspend_commands")
        self.assertIn('echo "token=$token" >> "$GITHUB_OUTPUT"', before["run"])
        self.assertIn("::stop-commands::%s", before["run"])
        after = worker["post-steps"][0]
        self.assertEqual(after["if"], "always()")
        self.assertEqual(after["env"]["STOP_COMMANDS_TOKEN"],
                         "${{ steps.suspend_commands.outputs.token }}")
        self.assertIn("printf '::%s::", after["run"])
        self.assertNotIn("gh_aw_log_guard", (WF / "upstreaming-worker.md").read_text())

    def test_prompts_require_rise_wheels_for_missing_build_and_test_dependencies(self):
        investigator = (WF / "upstreaming-investigator.md").read_text()
        worker = (WF / "upstreaming-worker.md").read_text()
        for text in (investigator, worker):
            self.assertIn("PIP_EXTRA_INDEX_URL=https://pypi.riseproject.dev/simple", text)
            self.assertIn("PIP_PREFER_BINARY=true", text)
            self.assertIn("public PyPI", text)
        self.assertIn("CIBW_ENVIRONMENT", worker)
        self.assertIn("CIBW_TEST_ENVIRONMENT", worker)
        skill = (ROOT / "skills/python-project-porting/SKILL.md").read_text()
        self.assertIn("Do not source-build a dependency when a compatible RISE wheel exists", skill)
        self.assertIn("PIP_PREFER_BINARY=true", skill)
        gotchas = (ROOT / "skills/python-project-porting/references/gotchas/dependencies-and-registry.md").read_text()
        self.assertIn("The reusable setting is the pair", gotchas)

    def test_worker_forbids_unrelated_fork_ci_debug_changes(self):
        worker = source("upstreaming-worker")
        self.assertNotIn("github", worker["tools"])
        github = worker["mcp-servers"]["github-authenticated"]
        self.assertEqual(github["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"], "${{ github.token }}")
        self.assertEqual(github["env"]["GITHUB_READ_ONLY"], "1")
        self.assertTrue(github["required"])
        text = (WF / "upstreaming-worker.md").read_text()
        self.assertIn("do not use anonymous GitHub fetching", text)
        self.assertIn("do not add `push: riscv64`", text)
        self.assertIn("do not broaden conditions", text)
        self.assertIn("`inputs.upload`", text)
        self.assertIn("commit history", text)
        self.assertIn("rejected/superseded approaches", text)
        self.assertIn("RISC-V GitHub Runners [1]", text)
        self.assertIn("[1]: https://ci.riseproject.dev/", text)
        self.assertIn("credentialless", text)
        self.assertIn("configured external OIDC trust", text)
        self.assertIn("Do not change or", text)
        self.assertIn("disable `id-token: write`", text)
        self.assertIn("publication should fail out of the box", text)
        self.assertIn("Commit structure and history updates follow the upstream project's", text)
        self.assertIn("add `riscv64`", text)
        self.assertIn("to that same list", text)
        self.assertIn("Do not introduce", text)
        self.assertIn("Add a dedicated `runs-on: ubuntu-24.04-riscv` row only", text)
        investigator = (WF / "upstreaming-investigator.md").read_text()
        self.assertIn("Explicitly classify whether Linux", investigator)
        self.assertIn("Recommend adding `riscv64` to the", investigator)

    def test_development_writers_do_not_wait_for_environment_review(self):
        worker = source("upstreaming-worker")
        self.assertNotIn("environment", worker["jobs"]["publish"])
        for name in ("upstreaming-provision.yml", "upstreaming-publish-retry.yml"):
            workflow = yaml.safe_load((WF / name).read_text())
            for job in workflow["jobs"].values():
                self.assertNotIn("environment", job, name)

    def test_dossier_comments_use_the_control_app_identity(self):
        investigator = source("upstreaming-investigator")
        retry = yaml.safe_load((WF / "upstreaming-publish-retry.yml").read_text())
        for notify in (investigator["jobs"]["notify"], retry["jobs"]["notify"]):
            self.assertNotIn("issues", notify["permissions"])
            token = next(step for step in notify["steps"] if step.get("id") == "comment-token")
            self.assertEqual(token["with"]["owner"], "riseproject-dev")
            self.assertEqual(token["with"]["repositories"], "python-wheels")
            self.assertEqual(token["with"]["permission-issues"], "write")
            publish = next(step for step in notify["steps"] if "dossier comment" in step.get("name", ""))
            self.assertEqual(publish["env"]["GH_TOKEN"], "${{ steps.comment-token.outputs.token }}")
            self.assertEqual(publish["env"]["UPSTREAMING_COMMENT_AUTHOR"], "riseproject-dev[bot]")

    def test_investigation_retry_also_publishes_verified_comment(self):
        retry = yaml.safe_load((WF / "upstreaming-publish-retry.yml").read_text())
        notify = retry["jobs"]["notify"]
        self.assertEqual(notify["needs"], "publish")
        self.assertNotIn("issues", notify["permissions"])
        self.assertIn("upstreaming.dossier_comment", str(notify))
        self.assertIn("upstreaming-publication", str(notify))

    def test_authored_python_ci_invocations_use_uv(self):
        for path in sorted(WF.glob("upstreaming-*")):
            if path.name.endswith(".lock.yml") or path.suffix not in (".md", ".yml"):
                continue  # Compiler-owned internal runtime setup is not authored here.
            text = path.read_text()
            config = yaml.safe_load(text.split("---", 2)[1] if path.suffix == ".md" else text)
            for script in run_scripts(config):
                joined = script.replace("\\\n", " ")
                self.assertIsNone(re.search(r"(?:^|[\n;&|])\s*python(?:3)?(?:\s|$)", joined),
                                  f"{path.name}: direct Python CI invocation without uv")
        sync_step = next(s for s in yaml.safe_load((WF / "upstreaming-validate.yml").read_text())["jobs"]["validate"]["steps"]
                         if s.get("name") == "Runtime dependency inventory matches authored workflow pins")
        self.assertIn("uv run --no-project python upstreaming/dependencies/sync.py", sync_step["run"])
