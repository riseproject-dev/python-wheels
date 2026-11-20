# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

import unittest

from upstreaming import review_response


class FakeApi:
    def __init__(self, existing=None, resolved=False):
        self.existing = existing or []
        self.resolved = resolved
        self.calls = []

    def call(self, method, path, data=None):
        self.calls.append((method, path, data))
        if method == "GET" and "/pulls/1/comments" in path:
            return list(self.existing)
        if method == "GET" and "/issues/1/comments" in path:
            return []
        return {}

    def graphql(self, query, variables):
        self.calls.append(("GRAPHQL", query, variables))
        if "reviewThreads" in query:
            return {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{
                "id": "PRRT_1", "isResolved": self.resolved,
                "comments": {"nodes": [{"databaseId": 20, "body": "change this"}]}
            }]}}}}
        self.resolved = True
        return {"resolveReviewThread": {"thread": {"id": "PRRT_1", "isResolved": True}}}


class TestReviewResponse(unittest.TestCase):
    def values(self):
        task = {"context": {"reason_evidence": [{"kind": "human_relay", "data": {
            "comments": [{"id": 20, "reviewer": "maintainer"}],
            "conversation_comments": [{"id": 30, "reviewer": "maintainer"}],
            "reviews": []}}]}}
        proposal = {"feedback_responses": [
            {"comment_id": 20, "summary": "Added riscv64 to the existing test matrix."},
            {"comment_id": 30, "summary": "Enabled the Test workflow for the pull request."}]}
        record = {"fork": {"name": "riseproject-upstreaming/proj", "pr_number": 1}}
        outcome = {"status": "published", "candidate": "a" * 40}
        return record, task, proposal, outcome

    def test_replies_then_resolves_inline_thread(self):
        api = FakeApi()
        actions = review_response.apply(api, record=self.values()[0], task=self.values()[1],
                                        proposal=self.values()[2], outcome=self.values()[3])
        self.assertEqual(actions, [{"comment_id": 20, "action": "replied"},
                                   {"comment_id": 20, "action": "resolved"},
                                   {"comment_id": 30, "action": "replied"}])
        reply = next(call for call in api.calls if "/comments/20/replies" in call[1])
        self.assertIn("@maintainer Added riscv64", reply[2]["body"])
        self.assertTrue(any(call[0] == "GRAPHQL" and "resolveReviewThread" in call[1] for call in api.calls))

    def test_marker_makes_reply_idempotent_but_unresolved_thread_is_retried(self):
        record, task, proposal, outcome = self.values()
        tag = review_response.marker(20, outcome["candidate"])
        api = FakeApi(existing=[{"body": tag}])
        actions = review_response.apply(api, record=record, task=task, proposal=proposal, outcome=outcome)
        self.assertNotIn(("POST", "/repos/riseproject-upstreaming/proj/pulls/1/comments/20/replies"),
                         [(method, path) for method, path, _ in api.calls])
        self.assertIn({"comment_id": 20, "action": "resolved"}, actions)

    def test_non_published_outcome_has_no_effect(self):
        record, task, proposal, outcome = self.values()
        api = FakeApi()
        self.assertEqual(review_response.apply(api, record=record, task=task, proposal=proposal,
                                               outcome={"status": "uncertain"}), [])
        self.assertEqual(api.calls, [])


if __name__ == "__main__":
    unittest.main()
