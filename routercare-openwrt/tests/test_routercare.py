#!/usr/bin/env python3
"""Small dependency-free regression checks for RouterCare's local UI and CGI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "www/routercare/index.html"


class MarkupContract(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.anchors: list[str] = []
        self.status_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"] or "")
        if tag == "a" and (values.get("href") or "").startswith("#"):
            self.anchors.append((values["href"] or "")[1:])
        if values.get("role") == "status" and values.get("aria-live") == "polite":
            self.status_ids.add(values.get("id") or "")


def run_cgi(path: str, method: str) -> tuple[str, dict[str, object]]:
    env = os.environ.copy()
    env["REQUEST_METHOD"] = method
    result = subprocess.run(["sh", str(ROOT / path)], env=env, text=True,
                            capture_output=True, check=True)
    parts = re.split(r"\r?\n\r?\n", result.stdout, maxsplit=1)
    if len(parts) != 2:
        raise AssertionError(f"CGI headers/body separator missing: {path}")
    return parts[0], json.loads(parts[1])


class RouterCareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = HTML.read_text(encoding="utf-8")
        cls.markup = MarkupContract()
        cls.markup.feed(cls.html)

    def test_html_ids_and_navigation_targets_are_unique_and_valid(self) -> None:
        self.assertEqual(len(self.markup.ids), len(set(self.markup.ids)))
        for anchor in self.markup.anchors:
            self.assertIn(anchor, self.markup.ids, f"broken anchor #{anchor}")

    def test_dynamic_service_states_are_announced(self) -> None:
        for service_id in ("zapret-status", "zapret2", "mihomo-service"):
            self.assertIn(service_id, self.markup.status_ids)
            self.assertIn(f'setService("{service_id}"', self.html)

    def test_ui_keeps_reduced_motion_and_local_assets(self) -> None:
        self.assertIn("prefers-reduced-motion:reduce", self.html)
        self.assertIn("Обновление статуса", self.html)
        self.assertIn("без автообновления", self.html)
        self.assertIn("signal-grid", self.html)
        self.assertIn("skip-link", self.html)
        self.assertIn("color-scheme:light", self.html)
        self.assertNotRegex(self.html, r"https?://(?:fonts\.googleapis|cdnjs|cdn\.)")
        self.assertIn("RouterCare 0.4.3", self.html)

    def test_service_cards_stack_at_tablet_widths(self) -> None:
        tablet = re.search(r"@media\(max-width:720px\)\{(.*?)\}\s*@media\(max-width:490px\)",
                           self.html, re.DOTALL)
        self.assertIsNotNone(tablet)
        rules = tablet.group(1) if tablet else ""
        self.assertIn(".services{grid-template-columns:1fr}", rules)
        self.assertIn(".service-head{align-items:center;flex-direction:row}", rules)
        self.assertIn(".pill{margin-left:0}", rules)

    def test_mobile_controls_have_comfortable_tap_targets(self) -> None:
        self.assertRegex(self.html, r"@media\s*\(max-width:\s*720px\)[\s\S]*?\.nav a\s*\{\s*min-height:\s*44px")
        self.assertRegex(self.html, r"\.icon-button\s*\{\s*width:\s*44px;\s*height:\s*44px")
        self.assertRegex(self.html, r"\.button\s*\{\s*min-height:\s*44px")
        self.assertRegex(self.html, r"@media\s*\(max-width:\s*490px\)[\s\S]*?\.topbar\s*\{\s*flex-wrap:\s*wrap")

    def test_inline_javascript_parses(self) -> None:
        scripts = re.findall(r"<script>(.*?)</script>", self.html, re.DOTALL)
        self.assertTrue(scripts)
        for script in scripts:
            subprocess.run(["node", "--check", "-"], input=script, text=True,
                           capture_output=True, check=True)

    def test_shell_scripts_parse(self) -> None:
        for path in ("install.sh", "uninstall.sh", "www/cgi-bin/routercare-status",
                     "www/cgi-bin/routercare-mihomo-check"):
            subprocess.run(["sh", "-n", str(ROOT / path)], check=True)

    def test_status_cgi_returns_well_formed_service_json(self) -> None:
        headers, body = run_cgi("www/cgi-bin/routercare-status", "GET")
        self.assertIn("application/json", headers)
        self.assertIs(body["ok"], True)
        self.assertEqual(set(body["services"]), {"zapret", "zapret2", "mihomo"})
        self.assertIn(body["services"]["zapret"], {"running", "stopped", "not_found"})

    def test_mihomo_checker_rejects_non_get_without_running_a_check(self) -> None:
        headers, body = run_cgi("www/cgi-bin/routercare-mihomo-check", "POST")
        self.assertIn("405 Method Not Allowed", headers)
        self.assertEqual(body, {"result": "method_not_allowed"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
