from __future__ import annotations

import unittest

from ooxml_compat_normalize import web_server


class WebServerContextPathTests(unittest.TestCase):
    def test_default_context_path_prefixes_api_and_ui(self) -> None:
        self.assertEqual(web_server.CONTEXT_PATH, "/ooxml-compat-normalize")
        self.assertEqual(web_server.UI_PATH, "/ooxml-compat-normalize/")
        self.assertEqual(web_server.API_BASE, "/ooxml-compat-normalize/api")

    def test_context_path_normalization(self) -> None:
        self.assertEqual(
            web_server._normalize_context_path("custom/path/"),
            "/custom/path",
        )
        self.assertEqual(
            web_server._normalize_context_path("/custom/path/"),
            "/custom/path",
        )
        self.assertEqual(
            web_server._normalize_context_path("/"),
            "/ooxml-compat-normalize",
        )

    def test_browser_ui_uses_context_relative_api_paths(self) -> None:
        self.assertIn("post('api/audit'", web_server.INDEX_HTML)
        self.assertIn("post('api/normalize?profile='", web_server.INDEX_HTML)
        self.assertNotIn("post('/api/", web_server.INDEX_HTML)


if __name__ == "__main__":
    unittest.main()
