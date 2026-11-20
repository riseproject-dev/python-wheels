# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT

import unittest

from upstreaming import generate_doc


class TestGenerateUpstreamingDoc(unittest.TestCase):
    def test_render_links_and_orders_tracking_rows(self):
        common = {
            "tracking_issue": {"number": 42},
            "phase": "development",
            "activity": "waiting_ci",
            "fork": {
                "name": "riseproject-upstreaming/bravo",
                "pr_number": 3,
            },
            "upstream_pr": {
                "number": 7,
                "url": "https://github.com/example/bravo/pull/7",
            },
            "updated_at": "2026-11-20T15:00:00+00:00",
        }
        bravo = {**common, "upstream": {"full_name": "example/bravo"}}
        alpha = {
            **common,
            "upstream": {"full_name": "example/Alpha"},
            "tracking_issue": {"number": 41},
            "fork": None,
            "upstream_pr": None,
        }

        rendered = generate_doc.render([bravo, alpha])

        self.assertLess(rendered.index("example/Alpha"), rendered.index("example/bravo"))
        self.assertIn("https://github.com/riseproject-dev/python-wheels/issues/42", rendered)
        self.assertIn("https://github.com/riseproject-upstreaming/bravo/pull/3", rendered)
        self.assertIn("https://github.com/example/bravo/pull/7", rendered)
        self.assertIn("Development (waiting for CI)", rendered)
        self.assertEqual(rendered.count("\n| [example/"), 2)


if __name__ == "__main__":
    unittest.main()
