# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""Artifact redirects drop credentials and reject unexpected origins."""
from email.message import Message
import unittest
import urllib.request

from upstreaming import collect


class TestArtifactRedirect(unittest.TestCase):
    def request(self):
        return urllib.request.Request("https://api.github.com/repos/o/r/actions/artifacts/1/zip",
                                      headers={"Authorization": "Bearer secret"})

    def test_cross_origin_blob_redirect_drops_authorization(self):
        redirected = collect._ArtifactRedirect().redirect_request(
            self.request(), None, 302, "Found", Message(),
            "https://productionresults.blob.core.windows.net/actions-results/file.zip?sig=x")
        self.assertIsNone(redirected.get_header("Authorization"))

    def test_unexpected_cross_origin_is_rejected(self):
        with self.assertRaises(collect.CollectError):
            collect._ArtifactRedirect().redirect_request(
                self.request(), None, 302, "Found", Message(), "https://example.com/file.zip")

    def test_same_origin_keeps_authorization(self):
        redirected = collect._ArtifactRedirect().redirect_request(
            self.request(), None, 302, "Found", Message(), "https://api.github.com/next")
        self.assertEqual(redirected.get_header("Authorization"), "Bearer secret")
