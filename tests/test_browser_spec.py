#!/usr/bin/env python3
"""Contract checks for the shared Brave browser spec.

Protects: a policy that copies Brave's own default, a missing reason, a
force-installed extension, a second extension, installer commands or account
data under browser/, and a second catalog file.

Run from the repo root:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "browser"
SPEC = BROWSER / "brave.json"
PAGE = ROOT / "docs" / "browser.md"
DECISION = ROOT / "docs" / "decisions" / "default-browser-brave.md"

BITWARDEN_ID = "nngceckbapebfimnlniiiahkandclblb"
ONEPASSWORD_ID = "aeblfdkhhhdcdjpifhhbdiojplfjncoa"
UBO_LITE_ID = "ddkjiahejlhfcafbddmgiahcphecmpfh"
UPDATE_URL = "https://clients2.google.com/service/update2/crx"
EXTENSION_ID = re.compile(r"^[a-p]{32}$")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DEVICE_ID = re.compile(r"\b[A-Z2-7]{7}(?:-[A-Z2-7]{7}){7}\b")

# Package commands and force-install policy names. browser/ is data, not an installer.
COMMANDS = re.compile(
    r"\b("
    r"apt-get|apt|brew|winget|dnf|zypper|pacman|yay|paru|flatpak|snap|"
    r"sudo|systemctl|msiexec|chezmoi|curl|wget|"
    r"omarchy-install-browser|omarchy-default-browser|"
    r"ExtensionInstallForcelist"
    r")\b"
)

POLICIES = {
    "BraveRewardsDisabled": (True, False),
    "BraveWalletDisabled": (True, False),
    "BraveVPNDisabled": (True, False),
    "BraveAIChatEnabled": (False, True),
    "BraveLocalAIEnabled": (False, True),
    "BraveP3AEnabled": (False, True),
    "BraveStatsPingEnabled": (False, True),
    "PasswordManagerEnabled": (False, True),
}

LEFT_UNSET = (
    "BraveNewsDisabled",
    "BraveTalkDisabled",
    "TorDisabled",
    "BraveWebDiscoveryEnabled",
    "BraveShieldsDisabledForUrls",
    "BraveShieldsEnabledForUrls",
)

LEO_REASON = "Jason uses separate AI tools; Leo's sidebar and prompts are redundant."
LOCAL_AI_REASON = (
    "Jason decided on 2026-10-29 to turn off Brave's AI features because he uses separate AI tools. "
    "This policy is the master switch for local AI. The history-embeddings pref is already false."
)
EXTENSION_KEYS = frozenset({"name", "id", "updateUrl", "install", "reason"})
EXTENSION_DECISION = "Jason decided on 2026-10-29 to stick with Bitwarden only. No AI or other extensions are offered."


def _load() -> dict:
    return json.loads(SPEC.read_text())


def _relative_targets(text: str, source: Path) -> list[Path]:
    targets: list[Path] = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        link = match.group(1).split("#", 1)[0].strip()
        if not link or "://" in link or link.startswith("mailto:"):
            continue
        targets.append((source.parent / link).resolve())
    return targets


class BrowserSpecTest(unittest.TestCase):
    def test_spec_shape(self) -> None:
        spec = _load()
        self.assertEqual(spec["schemaVersion"], 1)
        self.assertEqual(spec["default"]["id"], "brave")
        self.assertEqual(spec["default"]["channel"], "release")
        self.assertEqual(spec["default"]["desktopIds"]["linux"], "brave-browser.desktop")
        self.assertEqual(spec["default"]["desktopIds"]["macos"], "com.brave.Browser")
        self.assertEqual(set(spec), {"schemaVersion", "default", "policies", "extensions", "notes"})

    def test_every_policy_differs_from_upstream_and_has_a_reason(self) -> None:
        spec = _load()
        seen: set[str] = set()
        for policy in spec["policies"]:
            name = policy["name"]
            self.assertNotIn(name, seen)
            seen.add(name)
            self.assertIn(name, POLICIES)
            value, upstream = POLICIES[name]
            self.assertEqual(policy["value"], value)
            self.assertEqual(policy["upstreamDefault"], upstream)
            self.assertNotEqual(policy["value"], policy["upstreamDefault"])
            self.assertIsInstance(policy["reason"], str)
            self.assertGreater(len(policy["reason"].strip()), 20)
            self.assertNotIn("TODO", policy["reason"])
            allowed = {"name", "value", "upstreamDefault", "reason", "when"}
            self.assertTrue(set(policy) <= allowed)
        self.assertEqual(seen, set(POLICIES))
        for name in LEFT_UNSET:
            self.assertNotIn(name, seen)

    def test_leo_is_off_and_password_manager_is_conditioned_on_bitwarden(self) -> None:
        by_name = {policy["name"]: policy for policy in _load()["policies"]}
        leo = by_name["BraveAIChatEnabled"]
        self.assertFalse(leo["value"])
        self.assertTrue(leo["upstreamDefault"])
        self.assertEqual(leo["reason"], LEO_REASON)
        self.assertNotIn("when", leo)
        local_ai = by_name["BraveLocalAIEnabled"]
        self.assertFalse(local_ai["value"])
        self.assertTrue(local_ai["upstreamDefault"])
        self.assertEqual(local_ai["reason"], LOCAL_AI_REASON)
        self.assertNotIn("when", local_ai)
        passwords = by_name["PasswordManagerEnabled"]
        self.assertFalse(passwords["value"])
        self.assertTrue(passwords["upstreamDefault"])
        self.assertEqual(passwords["when"], "Bitwarden is the password manager.")
        self.assertNotIn("1Password", passwords["reason"])
        self.assertIn("Bitwarden", passwords["reason"])

    def test_bitwarden_is_the_only_offered_extension(self) -> None:
        spec = _load()
        self.assertEqual(len(spec["extensions"]), 1)
        extension = spec["extensions"][0]
        self.assertEqual(set(extension), set(EXTENSION_KEYS))
        self.assertEqual(extension["name"], "Bitwarden")
        self.assertEqual(extension["id"], BITWARDEN_ID)
        self.assertIsNotNone(EXTENSION_ID.fullmatch(extension["id"]))
        self.assertEqual(extension["updateUrl"], UPDATE_URL)
        self.assertEqual(extension["install"], "offer")
        self.assertNotIn("when", extension)
        self.assertGreater(len(extension["reason"].strip()), 20)
        self.assertEqual(
            spec["notes"],
            [{"offered": False, "reason": EXTENSION_DECISION}],
        )
        self.assertFalse((BROWSER / "extension-catalog.tsv").exists())
        blob = SPEC.read_text()
        self.assertNotIn(ONEPASSWORD_ID, blob)
        self.assertNotIn(UBO_LITE_ID, blob)
        self.assertNotIn("ExtensionInstallForcelist", blob)
        self.assertNotIn("1Password", blob)

    def test_no_installer_commands_or_account_data_under_browser(self) -> None:
        files = sorted(path for path in BROWSER.rglob("*") if path.is_file())
        self.assertEqual([path.relative_to(ROOT).as_posix() for path in files], ["browser/README.md", "browser/brave.json"])
        for path in files:
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertIsNone(COMMANDS.search(text))
                self.assertIsNone(EMAIL.search(text))
                self.assertIsNone(DEVICE_ID.search(text))
                self.assertNotIn("100.64.", text)
                self.assertNotIn("fd7a:115c", text)
                self.assertNotIn("BEGIN PRIVATE KEY", text)
                self.assertNotIn("Co-authored-by:", text)
                self.assertFalse(text.startswith("#!"))

    def test_docs_record_the_bitwarden_only_decision(self) -> None:
        for path in (PAGE, DECISION, BROWSER / "README.md"):
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertIn(EXTENSION_DECISION, text)
                self.assertIn(BITWARDEN_ID, text)
        page = PAGE.read_text()
        decision = DECISION.read_text()
        self.assertIn("PasswordManagerEnabled", page)
        self.assertIn("when Bitwarden is the password manager", page)
        self.assertIn("never force-installed", page)
        self.assertIn("no `browser/extension-catalog.tsv`", decision)
        self.assertIn("1Password is not a condition and not an offered extension.", decision)
        self.assertNotIn("third-party password manager", decision)
        self.assertIn("false, only when Bitwarden is the password manager", decision)
        self.assertIn("Passwords stay in Bitwarden", page)
        self.assertIn("Passwords stay in Bitwarden", decision)
        self.assertNotIn("Bookmarks, passwords,", page)
        self.assertNotIn("Profile data stays until the person imports it", decision)
        self.assertIn("It never forces.", page)
        self.assertIn("Nothing is uninstalled automatically", page)
        self.assertIn("no profile data is deleted", page)
        self.assertIn("Detect and offer, never force", decision)
        self.assertNotIn(ONEPASSWORD_ID, page)
        self.assertNotIn(ONEPASSWORD_ID, decision)
        self.assertNotIn(UBO_LITE_ID, page)

    def test_agents_and_indexes_point_at_one_source(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text()
        readme = (ROOT / "README.md").read_text()
        docs_index = (ROOT / "docs" / "README.md").read_text()
        self.assertIn("`browser/`", agents)
        self.assertIn("`docs/browser.md`", agents)
        self.assertIn("`docs/decisions/default-browser-brave.md`", agents)
        self.assertIn("browser/README.md", readme)
        self.assertIn("docs/browser.md", readme)
        self.assertIn("docs/decisions/default-browser-brave.md", readme)
        self.assertIn("browser.md", docs_index)
        self.assertIn("decisions/default-browser-brave.md", docs_index)

    def test_relative_links_resolve(self) -> None:
        pages = [
            SPEC,
            BROWSER / "README.md",
            PAGE,
            DECISION,
            ROOT / "README.md",
            ROOT / "docs" / "README.md",
            ROOT / "AGENTS.md",
        ]
        for source in pages:
            if source.suffix == ".json":
                continue
            for target in _relative_targets(source.read_text(), source):
                with self.subTest(source=source.name, target=str(target)):
                    self.assertTrue(target.exists(), f"{source} links to missing {target}")


if __name__ == "__main__":
    unittest.main()
