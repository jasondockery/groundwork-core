#!/usr/bin/env python3
"""Contract checks for the Syncthing shared-folder docs.

Run from the repo root:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "docs" / "decisions" / "syncthing-shared-folders.md"
DEFINITION = ROOT / "docs" / "syncthing.md"

DEVICE_ID = re.compile(r"\b[A-Z2-7]{7}(?:-[A-Z2-7]{7}){7}\b")
SECRET_MARKERS = (
    "Co-authored-by:",
    "redacted-account",
    "<apikey>",
    "BEGIN PRIVATE KEY",
    "BEGIN EC PRIVATE KEY",
)

OVERRIDE_SETTINGS = (
    "options.listenAddress",
    "options.relaysEnabled",
    "options.globalAnnounceEnabled",
    "options.localAnnounceEnabled",
    "options.natEnabled",
    "options.announceLANAddresses",
    "STNODEFAULTFOLDER",
    "device.addresses",
    "device.allowedNetworks",
)

KEPT_SETTINGS = (
    "gui.address",
    "gui.user",
    "options.urAccepted",
    "options.crashReportingEnabled",
)


def _table_rows(text: str, header: str) -> list[list[str]]:
    """Return body rows for the first markdown table whose header contains `header`."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("|") and header in line)
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append(cells)
    return rows


def _relative_targets(text: str, source: Path) -> list[Path]:
    targets: list[Path] = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        link = match.group(1).split("#", 1)[0].strip()
        if not link or "://" in link or link.startswith("mailto:"):
            continue
        targets.append((source.parent / link).resolve())
    return targets


class SyncthingDocsTest(unittest.TestCase):
    def test_pages_exist_and_cross_link(self) -> None:
        self.assertTrue(DECISION.is_file())
        self.assertTrue(DEFINITION.is_file())
        decision = DECISION.read_text()
        definition = DEFINITION.read_text()
        self.assertIn("docs/syncthing.md", decision.replace("../syncthing.md", "docs/syncthing.md"))
        self.assertIn("(decisions/syncthing-shared-folders.md)", definition)
        readme = (ROOT / "README.md").read_text()
        docs_index = (ROOT / "docs" / "README.md").read_text()
        self.assertIn("docs/syncthing.md", readme)
        self.assertIn("docs/decisions/syncthing-shared-folders.md", readme)
        self.assertIn("syncthing.md", docs_index)
        self.assertIn("decisions/syncthing-shared-folders.md", docs_index)

    def test_decision_covers_the_issue(self) -> None:
        text = DECISION.read_text().lower()
        for phrase in (
            "syncthing",
            "tailscale",
            "rclone",
            "google drive",
            "dropbox",
            "nextcloud",
            "freetube",
            "nedb",
            "one machine at a time",
            "0.25.3",
            "issue 370",
            "arm",
            "always-on",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("not an opt-in", text)

    def test_definition_is_the_shared_default(self) -> None:
        text = DEFINITION.read_text()
        lowered = text.lower()
        for phrase in (
            "~/Shared",
            "~/Shared/FreeTube",
            "groundwork-shared",
            "history.db",
            "playlists.db",
            "profiles.db",
            "settings.db",
            "user service",
            "127.0.0.1:8384",
            "100.64.0.0/10",
            "fd7a:115c:a1e0::/48",
            "groundwork syncthing-pair",
            "STNODEFAULTFOLDER",
            "io.freetubeapp.FreeTube",
            "FreeTube.FreeTube",
            "Syncthing.Syncthing",
            "16 KiB",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("it is a default", lowered)
        self.assertIn("not an opt-in", lowered)
        self.assertIn("brew services", lowered)
        self.assertIn("systemctl --user enable --now syncthing.service", lowered)
        self.assertIn("~/Library/Application Support/FreeTube/", text)
        self.assertIn("~/.var/app/io.freetubeapp.FreeTube/config/FreeTube/", text)
        self.assertIn("%APPDATA%\\FreeTube", text)
        self.assertIn("~/.config/FreeTube", text)

    def test_every_override_has_a_reason(self) -> None:
        text = DEFINITION.read_text()
        rows = {row[0].strip("`"): row for row in _table_rows(text, "Setting")}
        # The first table whose header contains Setting is the override table.
        override_rows = _table_rows(text, "| Setting | Value | Reason |")
        found = {row[0].strip("`") for row in override_rows}
        self.assertEqual(found, set(OVERRIDE_SETTINGS))
        for row in override_rows:
            with self.subTest(setting=row[0]):
                self.assertGreaterEqual(len(row), 3)
                self.assertGreater(len(row[2]), 40)
                self.assertNotIn("TODO", row[2])
        kept = _table_rows(text, "| Setting | Kept value | Reason |")
        kept_names = " ".join(row[0] for row in kept)
        for setting in KEPT_SETTINGS:
            with self.subTest(kept=setting):
                self.assertIn(setting, kept_names)
        gui = next(row for row in kept if "gui.address" in row[0])
        self.assertIn("127.0.0.1:8384", gui[1])
        self.assertGreater(len(gui[2]), 40)
        # `rows` is unused beyond forcing the helper to accept this file.
        self.assertIn("options.listenAddress", rows)

    def test_pairing_is_local_and_idempotent(self) -> None:
        text = DEFINITION.read_text().lower()
        for phrase in (
            "second run",
            "exits 0",
            "127.0.0.1",
            "x-api-key",
            "mode `0600`",
            "own device id",
            "does not call the other machine",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_no_secrets_or_attribution_trailers(self) -> None:
        for path in (DECISION, DEFINITION, ROOT / "README.md", ROOT / "docs" / "README.md"):
            text = path.read_text()
            with self.subTest(path=path.name, kind="device id"):
                self.assertIsNone(DEVICE_ID.search(text))
            for marker in SECRET_MARKERS:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, text)

    def test_relative_links_resolve(self) -> None:
        pages = [
            DECISION,
            DEFINITION,
            ROOT / "README.md",
            ROOT / "docs" / "README.md",
            ROOT / "docs" / "developer-setup.md",
            ROOT / "docs" / "tailscale.md",
            ROOT / "AGENTS.md",
        ]
        for source in pages:
            for target in _relative_targets(source.read_text(), source):
                with self.subTest(source=source.name, target=str(target)):
                    self.assertTrue(target.exists(), f"{source} links to missing {target}")


if __name__ == "__main__":
    unittest.main()
