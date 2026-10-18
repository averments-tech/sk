#!/usr/bin/env python3
"""Small dependency-free regression checks for OpenWrt Zapret's local UI and CGI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
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
        self.assertNotIn('class="shortcut-grid"', self.html)
        self.assertNotIn('id="compatibility"', self.html)
        self.assertNotIn('id="protocols"', self.html)
        self.assertIn("skip-link", self.html)
        self.assertIn('content="light"', self.html)
        self.assertIn("color-scheme:light", self.html)
        self.assertIn("theme-color", self.html)
        self.assertNotRegex(self.html, r"https?://(?:fonts\.googleapis|cdnjs|cdn\.)")
        self.assertIn("OpenWrt Zapret 0.5.15", self.html)
        self.assertIn("<b>0.5.15</b>", self.html)
    def test_navigation_only_targets_live_panel_sections(self) -> None:
        for target in ("overview", "zapret-service", "list-check", "mihomo", "system", "console"):
            self.assertIn(f'href="#{target}"', self.html)
            self.assertIn(f'id="{target}"', self.html)
        self.assertNotIn("shortcut-card", self.html)
        self.assertNotIn("compat-section", self.html)
        self.assertNotIn("protocol-section", self.html)
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


    def test_ten_theme_variants_are_local_and_console_commands_are_allowlisted(self) -> None:
        options = re.findall(r'<option value="([a-z]+)">', self.html)
        self.assertEqual(options, ["cobalt", "apple", "violet", "ocean", "mint",
                                   "emerald", "rose", "amber", "coral", "graphite"])
        self.assertIn('id="theme-picker"', self.html)
        self.assertIn('localStorage.setItem("openwrt-zapret-theme"', self.html)
        self.assertIn('id="console"', self.html)
        self.assertIn('class="console-state">SHELL OFF', self.html)
        self.assertIn("локального CGI", self.html)
        self.assertIn("произвольный shell отключён", self.html)
        self.assertIn('data-console-command="config-test"', self.html)
        self.assertIn('data-console-command="status"', self.html)
        self.assertIn('data-console-command="clear"', self.html)
        self.assertIn('data-console-command="help"', self.html)

        start = self.html.index("    function parseConsoleCommand(raw){")
        end = self.html.index("\n    const consoleOutput", start)
        parser = self.html[start:end]
        harness = parser + """
const assert=require('node:assert/strict');
for(const command of ['help','status','config-test','clear']) assert.equal(parseConsoleCommand(command),command);
for(const command of ['status; reboot','status arg','sh','help\\nrm -rf /','']) assert.equal(parseConsoleCommand(command),null);
"""
        subprocess.run(["node", "-e", harness], check=True)

    def test_light_console_redesign_is_local_and_reduced_motion_safe(self) -> None:
        self.assertIn('id="light-console-redesign"', self.html)
        self.assertIn("--paper:#f4f7fb", self.html)
        self.assertIn("Кобальт", self.html)
        self.assertIn("Аметист", self.html)
        self.assertIn("prefers-reduced-motion:reduce", self.html)
        self.assertNotIn("platform-chip", self.html)
        self.assertIn('content="light"', self.html)

    def test_removed_reference_catalog_stays_documented_outside_the_panel(self) -> None:
        self.assertNotIn('id="protocols"', self.html)
        self.assertNotIn('data-protocol-card', self.html)
        sources = (ROOT / "SOURCES.md").read_text(encoding="utf-8")
        for source in ("https://wiki.metacubex.one/en/config/proxies/vless/",
                       "https://wiki.metacubex.one/en/config/proxies/hysteria2/",
                       "https://github.com/bol-van/zapret2"):
            self.assertIn(source, sources)
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

    def test_theme_picker_is_local_and_platform_claims_are_removed(self) -> None:
        self.assertNotIn("platform-row", self.html)
        self.assertNotIn(">macOS</span>", self.html)
        self.assertNotIn(">Linux</span>", self.html)
        self.assertIn('id="theme-picker"', self.html)
        self.assertIn('aria-label="Выбрать цветовой вариант панели"', self.html)
        self.assertIn('localStorage.setItem("openwrt-zapret-theme"', self.html)
        self.assertIn('themePicker.addEventListener("change"', self.html)
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
        self.assertIn("OpenWrt Zapret 0.5.15 установлена",
                      (ROOT / "install.sh").read_text(encoding="utf-8"))
    def test_status_cgi_returns_well_formed_service_json(self) -> None:
        headers, body = run_cgi("www/cgi-bin/routercare-status", "GET")
        self.assertIn("application/json", headers)
        self.assertIs(body["ok"], True)
        self.assertEqual(set(body["services"]), {"zapret", "zapret2", "mihomo"})
        self.assertIn(body["services"]["zapret"], {"running", "stopped", "not_found"})
        self.assertEqual(set(body["strategy"]), {"state", "markers"})
        self.assertIn(body["strategy"]["state"], {"detected", "unavailable", "not_applicable"})

    def test_strategy_status_reads_allowlisted_markers_without_exposing_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = temp / "zapret"
            config.write_text("config zapret 'main'\n option NFQWS_OPT '\n#v7\n#Yv27\n#Dv1\n#Gv1\n#udp443\n#PKH\n--private-option=do-not-show\n'\n", encoding="utf-8")
            script = (ROOT / "www/cgi-bin/routercare-status").read_text(encoding="utf-8")
            script = script.replace("/etc/config/zapret", str(config))
            script = script.replace("$(service_state zapret nfqws)", '"running"')
            script = script.replace("$(service_state zapret2 nfqws2)", '"stopped"')
            script_path = temp / "status-cgi"
            script_path.write_text(script, encoding="utf-8")
            env = os.environ.copy()
            env["REQUEST_METHOD"] = "GET"
            output = subprocess.run(["sh", str(script_path)], env=env, text=True,
                                    capture_output=True, check=True).stdout
            body = json.loads(re.split(r"\r?\n\r?\n", output, maxsplit=1)[1])
            self.assertEqual(body["strategy"], {"state": "detected", "markers": "v7 / Yv27 / Dv1 / Gv1 / udp443"})
            self.assertNotIn("PKH", body["strategy"]["markers"])
            self.assertNotIn("do-not-show", output)
            self.assertIn("--private-option=do-not-show", config.read_text(encoding="utf-8"))
            conflict_script = temp / "status-cgi-conflict"
            conflict_script.write_text(script.replace('zapret2_state="stopped"', 'zapret2_state="running"'), encoding="utf-8")
            conflict_output = subprocess.run(["sh", str(conflict_script)], env=env, text=True,
                                             capture_output=True, check=True).stdout
            conflict_body = json.loads(re.split(r"\r?\n\r?\n", conflict_output, maxsplit=1)[1])
            self.assertEqual(conflict_body["strategy"], {"state": "not_applicable", "markers": ""})

    def test_mihomo_checker_rejects_non_get_without_running_a_check(self) -> None:
        headers, body = run_cgi("www/cgi-bin/routercare-mihomo-check", "POST")
        self.assertIn("405 Method Not Allowed", headers)
        self.assertEqual(body, {"result": "method_not_allowed"})

    def test_upstream_sources_are_kept_in_docs_not_in_main_ui(self) -> None:
        self.assertNotIn('id="compatibility"', self.html)
        self.assertNotIn("Strategies.md", self.html)
        sources = (ROOT / "SOURCES.md").read_text(encoding="utf-8")
        for item in ("https://github.com/StressOzz/Zapret-Manager/blob/main/Strategies.md",
                     "https://github.com/bol-van/zapret2",
                     "Код, логотипы, стратегии и списки StressOzz не копировались"):
            self.assertIn(item, sources)

if __name__ == "__main__":
    unittest.main(verbosity=2)
