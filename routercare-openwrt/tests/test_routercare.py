#!/usr/bin/env python3
"""Small dependency-free regression checks for OpenWrt Zapret's local UI and CGI."""

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


class OpenWrtZapretTests(unittest.TestCase):
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
        self.assertIn('content="light"', self.html)
        self.assertIn("color-scheme:light", self.html)
        self.assertIn("theme-color", self.html)
        self.assertIn("prefers-reduced-motion:reduce", self.html)
        self.assertNotRegex(self.html, r"https?://(?:fonts\.googleapis|cdnjs|cdn\.)")
        self.assertIn("OpenWrt Zapret 0.5.11", self.html)
        self.assertIn("<b>0.5.11</b>", self.html)


    def test_domain_list_validator_is_local_and_handles_duplicates_safely(self) -> None:
        self.assertIn('id="domain-input"', self.html)
        self.assertIn('id="domain-result" role="status" aria-live="polite"', self.html)
        self.assertIn("Список не сохраняется, не отправляется и не применяется к роутеру", self.html)
        self.assertIn("не проверит доступность сайтов", self.html)
        self.assertNotRegex(self.html, r"https?://(?:fonts\\.googleapis|cdnjs|cdn\\.)")
        start = self.html.index("    function inspectDomainList(input){")
        end = self.html.index("    function renderDomainCheck(result){", start)
        function = self.html[start:end]
        harness = function + """
const assert=require('node:assert/strict');
const result=inspectDomainList(' Example.COM \\n# note\\nexample.com\\nsub.example.org\\nhttps://bad.example\\n*.wild.example\\n127.0.0.1\\n-a.example');
assert.deepEqual(result.valid,['example.com','sub.example.org']);
assert.equal(result.duplicates.length,1);
assert.equal(result.duplicates[0].line,3);
assert.equal(result.invalid.length,4);
assert.equal(result.invalid[0].line,5);
"""
        subprocess.run(["node", "-e", harness], check=True)

    def test_light_console_redesign_is_local_and_reduced_motion_safe(self) -> None:
        self.assertIn('id="light-console-redesign"', self.html)
        self.assertIn("--paper:#f4f7fb", self.html)
        self.assertIn("Кобальт", self.html)
        self.assertIn("Аметист", self.html)
        self.assertIn("prefers-reduced-motion:reduce", self.html)
        self.assertNotRegex(self.html, r"https?://(?:fonts\\.googleapis|cdnjs|cdn\\.)")

    def test_light_console_redesign_is_local_and_reduced_motion_safe(self) -> None:
        self.assertIn('id="light-console-redesign"', self.html)
        self.assertIn("--paper:#f4f7fb", self.html)
        self.assertIn("Кобальт", self.html)
        self.assertIn("Аметист", self.html)
        self.assertIn("prefers-reduced-motion:reduce", self.html)
        self.assertIn("width:16px;height:16px;flex:0 0 16px", self.html)
        self.assertIn('content="light"', self.html)

    def test_upstream_protocol_catalog_is_filterable_but_not_claimed_as_integrated(self) -> None:
        self.assertIn('id="protocols"', self.html)
        self.assertIn('id="protocol-result" role="status" aria-live="polite"', self.html)
        self.assertIn("версия на роутере не подтверждена", self.html)
        self.assertIn("Не интегрировано", self.html)
        self.assertEqual(self.html.count('data-protocol-card data-transports='), 10)
        for source in ("vless", "vmess", "trojan", "hysteria2", "tuic", "wg", "shadowsocks", "anytls", "http", "socks"):
            self.assertIn(f"https://wiki.metacubex.one/en/config/proxies/{source}/", self.html)
        start = self.html.index("    function protocolMatches(filter,transports){")
        end = self.html.index("    function filterProtocolCards(filter){", start)
        function = self.html[start:end]
        harness = function + """
const assert=require('node:assert/strict');
assert.equal(protocolMatches('all','tcp udp'),true);
assert.equal(protocolMatches('tcp','tcp udp'),true);
assert.equal(protocolMatches('udp','tcp udp'),true);
assert.equal(protocolMatches('udp','tcp'),false);
assert.equal(protocolMatches('tcp','udp'),false);
"""
        subprocess.run(["node", "-e", harness], check=True)

    def test_parallel_dpi_services_raise_read_only_warning(self) -> None:
        self.assertIn('id="dpi-conflict"', self.html)
        self.assertIn('role="status" aria-live="polite" hidden', self.html)
        self.assertIn("OpenWrt Zapret не останавливает службы и не меняет конфигурацию", self.html)
        match = re.search(r"function isDpiConflict\(services\)\{[^}]+\}", self.html)
        self.assertIsNotNone(match)
        function = match.group(0) if match else ""
        harness = function + "\nconst assert=require('node:assert/strict');" \
            + "assert.equal(isDpiConflict({zapret:'running',zapret2:'running'}),true);" \
            + "assert.equal(isDpiConflict({zapret:'stopped',zapret2:'running'}),false);" \
            + "assert.equal(isDpiConflict({zapret:'running',zapret2:'not_found'}),false);"
        subprocess.run(["node", "-e", harness], check=True)

    def test_mihomo_syntax_test_is_not_presented_as_connectivity_check(self) -> None:
        self.assertIn('id="mihomo-limit" role="note"', self.html)
        self.assertIn("не проверяет соединение с VPN-узлами или доступ в интернет", self.html)
        self.assertIn("синтаксис конфига корректен", self.html)

    def test_failed_status_request_marks_services_unknown(self) -> None:
        self.assertIn('unknown:"Нет данных"', self.html)
        catch = self.html.split("}catch(e){", 1)[1].split("}finally", 1)[0]
        body = catch
        for service_id in ("zapret-status", "zapret2", "mihomo-service"):
            self.assertIn(f'setService("{service_id}","unknown")', body)

    def test_accessible_platform_badges_and_local_accent_toggle(self) -> None:
        self.assertIn('aria-label="Клиентские платформы: macOS и Linux через браузер"', self.html)
        self.assertIn(">macOS</span>", self.html)
        self.assertIn(">Linux</span>", self.html)
        self.assertIn('id="theme-toggle"', self.html)
        self.assertIn('aria-pressed="false"', self.html)
        self.assertIn('localStorage.setItem("openwrt-zapret-accent"', self.html)
        self.assertIn("themeToggle.addEventListener(\"click\"", self.html)

    def test_flow_animation_tracks_local_api_state(self) -> None:
        self.assertIn('class="flow-track"', self.html)
        self.assertIn("@media(prefers-reduced-motion:no-preference){.hero.is-online .packet", self.html)
        self.assertIn("@media(prefers-reduced-motion:reduce){.hero.is-online .packet{animation:none;opacity:.85}}", self.html)
        match = re.search(r"function setConnectionState\(online\)\{[^}]+\}", self.html)
        self.assertIsNotNone(match)
        function = match.group(0) if match else ""
        harness = function + "\nconst assert=require('node:assert/strict');let connected=false;let c={className:''};let h={classList:{toggle:(name,on)=>{connected=on}}};global.document={getElementById:()=>c,querySelector:()=>h};setConnectionState(true);assert.equal(c.className,'connection online');assert.equal(connected,true);setConnectionState(false);assert.equal(c.className,'connection offline');assert.equal(connected,false);"
        subprocess.run(["node", "-e", harness], check=True)

    def test_service_presence_is_not_claimed_as_traffic_success(self) -> None:
        self.assertIn("Статус службы/процесса; он не подтверждает прохождение трафика.", self.html)
        self.assertIn('setService("zapret-status",d.services?.zapret)', self.html)
        self.assertIn('setService("zapret2",d.services?.zapret2)', self.html)
        self.assertIn('setService("mihomo-service",d.services?.mihomo)', self.html)

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
                     "www/cgi-bin/routercare-mihomo-check", "../install.sh",
                     "../uninstall.sh"):
            subprocess.run(["sh", "-n", str(ROOT / path)], check=True)

    def test_repository_level_installers_delegate_to_current_package(self) -> None:
        root = ROOT.parent
        self.assertIn('exec "$ROOT_DIR/routercare-openwrt/install.sh" "$@"',
                      (root / "install.sh").read_text(encoding="utf-8"))
        self.assertIn('exec "$ROOT_DIR/routercare-openwrt/uninstall.sh" "$@"',
                      (root / "uninstall.sh").read_text(encoding="utf-8"))

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

    def test_upstream_compatibility_map_is_read_only_and_linked(self) -> None:
        self.assertIn('id="compatibility"', self.html)
        self.assertIn('href="#compatibility"', self.html)
        self.assertIn("https://github.com/StressOzz/Zapret-Manager/blob/main/Strategies.md", self.html)
        self.assertIn("https://github.com/bol-van/zapret2", self.html)
        self.assertIn("Импорт и применение не выполняются", self.html)
        self.assertIn("настройки v1 не переносятся в Zapret2", self.html)
        self.assertIn("Импорт подписок, WARP, Steer, Forkozz, AmneziaWG", self.html)
        self.assertIn("код и списки из него в OpenWrt Zapret не копируются", self.html)
        self.assertIn(".compat-grid{grid-template-columns:1fr}", self.html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
