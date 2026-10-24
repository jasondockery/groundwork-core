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

FALSE_OVERRIDES = (
    "options.relaysEnabled",
    "options.globalAnnounceEnabled",
    "options.localAnnounceEnabled",
    "options.natEnabled",
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

    def test_override_values_and_reasons(self) -> None:
        text = DEFINITION.read_text()
        override_rows = _table_rows(text, "| Setting | Value | Reason |")
        by_setting = {row[0]: row[1] for row in override_rows}
        self.assertNotIn("announceLANAddresses", text)

        def value_for(needle: str) -> str:
            matches = [value for setting, value in by_setting.items() if needle in setting]
            self.assertEqual(len(matches), 1, needle)
            return matches[0]

        for setting in FALSE_OVERRIDES:
            with self.subTest(setting=setting):
                self.assertEqual(value_for(setting).strip("`"), "false")
        self.assertEqual(value_for("STNODEFAULTFOLDER").strip("`"), "1")
        networks = value_for("device.allowedNetworks")
        self.assertIn("100.64.0.0/10", networks)
        self.assertIn("fd7a:115c:a1e0::/48", networks)
        listen_setting = next(setting for setting in by_setting if "listenAddresses" in setting)
        self.assertIn("listenAddress", listen_setting)
        self.assertIn("`PATCH /rest/config/options` with `listenAddresses`", text)
        self.assertIn("repeated `listenAddress` elements in `config.xml`", text)
        for row in override_rows:
            with self.subTest(setting=row[0]):
                self.assertGreaterEqual(len(row), 3)
                self.assertGreater(len(row[2]), 40)
                self.assertNotIn("TODO", row[2])

    def test_later_apply_resets_only_the_gui_address(self) -> None:
        text = DEFINITION.read_text()
        self.assertIn("A later apply writes `gui.address` back to `127.0.0.1:8384`", text)
        self.assertIn(
            "A later apply leaves `gui.user`, `gui.password`, `options.urAccepted`, "
            "`options.crashReportingEnabled`, and folder versioning",
            text,
        )
        self.assertNotIn("puts the upstream value back", text)

    def test_freetube_lstat_lock_and_conflict(self) -> None:
        text = DEFINITION.read_text()
        decision = DECISION.read_text()
        for phrase in (
            "statSync(path)?.isSymbolicLink",
            "without calling `isSymbolicLink`",
            "realpathSync(path)",
            "filename~",
            "The data-dir symlink survives",
            "does not move a data-dir file onto a shared file that is already present",
            "Classify each data-dir path with `lstat`",
            "Leave it.",
            "The data-dir name is absent and the shared file is present.",
            "Do not start FreeTube until that symlink exists.",
            "The data-dir name is a regular file and the shared file is absent.",
            "Both paths are regular files. Stop, print both paths, delete nothing, and do not launch.",
            "leave a correct symlink alone",
            "exclusive non-blocking lock",
            "do not `PATCH` the folder",
            "A second launch must not resume the folder.",
            "Only the lock holder resumes, after its process exits and no FreeTube process remains.",
            "does not choose the newer file by mtime",
            "Remove a `*.sync-conflict-*` file only after a person compares the copies.",
            "only menu, Dock, Start Menu, Spotlight, and `flatpak run io.freetubeapp.FreeTube`",
            "A direct binary launch is outside this contract.",
            "pattern `*~`",
            "never deletes the main database",
            'PATCH /rest/config/gui` with only `{"address":"127.0.0.1:8384"}`',
            "delete only the sibling `name.db~`",
            "The data-dir name is a symlink to `~/Shared/FreeTube/<name>` and that target is absent, with no temp in either directory: do not launch.",
            "Print the missing path and stop rather than reclassifying in a loop.",
            "Before the case list, under the lock, with no FreeTube process, run temp-normalization.",
            "scan both the package data directory and `~/Shared/FreeTube`",
            "A symlink, including a dangling one, is never a main.",
            "rename the temp onto `name.db` in that same directory",
            "Never rename onto the data-dir symlink path.",
            "A local regular database beside its sibling `name.db~`",
            "A sole `name.db~` in the data directory",
            "A sole `~/Shared/FreeTube/<name>.db~` becomes `~/Shared/FreeTube/<name>.db`.",
            "A restored shared file is not the migration path.",
            "A symlink whose target now exists is this leave-it case.",
            "If the data-dir name is a symlink and the temp is in the data directory, never rename onto the symlink.",
            "rename the data-dir temp onto that shared path",
            "If the shared file is already a regular file, delete only the data-dir temp.",
            "print both temps, rename nothing, and do not launch",
            "One pass classifies all four names, then one folder decision.",
            "Launch only when every name is a launch path",
            "If any name is both-regular, dangling, or any other `lstat` result, do not launch.",
            "Never resume while any of the four is still a regular file.",
            "print the missing path, do not launch, and leave the folder paused",
            "Resuming would announce the absence as a deletion.",
            "Resume only after the file is back at `~/Shared/FreeTube/<name>`, or after the person explicitly confirms the deletion.",
            "Never create an empty database to fill the hole.",
            "A later apply uses the normal resume rule only once every shared file exists, or the deletion was confirmed",
            "This migration path still launches",
            "This first-session path still launches",
            "Delete `name.db~` only when the main file was already there.",
            "If the lock is busy and no FreeTube process exists, exit without launching.",
            "Only the holder launches, and only after the pause.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("compacted successor", text)
        self.assertNotIn("keep the newer", text)
        self.assertLess(text.index("compare its path"), text.index("already in `folder.devices`"))
        self.assertIn("The data-dir symlink survives", decision)
        self.assertIn("classifies each data-dir name with `lstat`", decision)
        self.assertNotIn("replaces the symlink", decision)
        self.assertNotIn("moves the compacted file back", decision)
        self.assertIn("The cheatsheet says Quit, not close the window.", decision)

    def test_kernel_lock_quit_and_gui_socket(self) -> None:
        text = DEFINITION.read_text()
        for phrase in (
            "before any `lstat`, move, link, or `PATCH`",
            "holds it in the process that waits",
            "Do not `exec` FreeTube over that process.",
            "`flock(LOCK_EX|LOCK_NB)` on a descriptor kept open until resume",
            "`LockFileEx` with `LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY`",
            "on a handle kept open for the same span",
            "Busy means a live holder",
            "If the lock is busy and a FreeTube process exists, start FreeTube only to focus the running instance",
            "If the lock is busy and no FreeTube process exists, exit without launching.",
            "Only the holder launches, and only after the pause.",
            "When the kernel has released the lock, the next launch is the holder and must pause.",
            "closing the window does not quit",
            "`open -W`",
            "`start /wait`",
            "The FreeTube cheatsheet says Quit, not close the window.",
            "waits for the FreeTube process to exit, not for the window",
            "not for `open` or `start` to return",
            "Resume stays tied to process exit.",
            "Still holding the lock, after the process is gone",
            "move that file into `~/Shared/FreeTube`, symlink it, then resume",
            "If the shared file is already there, stop and print both paths.",
            "Do not resume while any of the four names is still a regular file.",
            "Delete `name.db~` only when the main file was already there.",
            "rename the temp onto `name.db` in that same directory",
            "Never rename onto the data-dir symlink path.",
            "A sole `~/Shared/FreeTube/<name>.db~` becomes `~/Shared/FreeTube/<name>.db`.",
            "A restored shared file is not the migration path.",
            "The data-dir name is a symlink to `~/Shared/FreeTube/<name>` and that target is absent, with no temp in either directory: do not launch.",
            "Print the missing path and stop rather than reclassifying in a loop.",
            "A local regular database beside its sibling `name.db~`",
            "A sole `name.db~` in the data directory",
            "If the data-dir name is a symlink and the temp is in the data directory, never rename onto the symlink.",
            "rename the data-dir temp onto that shared path",
            "If the shared file is already a regular file, delete only the data-dir temp.",
            "print both temps, rename nothing, and do not launch",
            "One pass classifies all four names, then one folder decision.",
            "Launch only when every name is a launch path",
            "If any name is both-regular, dangling, or any other `lstat` result, do not launch.",
            "Never resume while any of the four is still a regular file.",
            "print the missing path, do not launch, and leave the folder paused",
            "Resuming would announce the absence as a deletion.",
            "Resume only after the file is back at `~/Shared/FreeTube/<name>`, or after the person explicitly confirms the deletion.",
            "Never create an empty database to fill the hole.",
            "A later apply uses the normal resume rule only once every shared file exists, or the deletion was confirmed",
            "This migration path still launches",
            "This first-session path still launches",
            "The apply takes the same non-blocking lock",
            "If it is busy, do not resume, move, or relink.",
            'body `{"paused": false}` only',
            "re-check that no FreeTube process exists",
            "Do not `PUT` a default folder object over a paused folder.",
            "Any other `lstat` result: print the paths, change nothing, and do not launch.",
            "The service must not set `STGUIADDRESS` or `--gui-address`.",
            "The override hides the config value",
            "does not rewrite `config.xml`",
            "The step stays unfinished until the override is unset and the listening socket is `127.0.0.1:8384`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("Close it and wait", text)
        self.assertNotIn("If the shared file is absent, do not launch.", text)
        self.assertNotIn("replaces the address in config", text)
        self.assertNotIn("leave the temp so NeDB can rename it back", text)
        self.assertNotIn("then classify again", text)
        self.assertNotIn("print the missing path, and do not launch", text)
        self.assertNotIn("Apply follows the same rule", text)
        self.assertNotIn("wherever its main file lives", text)
        self.assertLess(
            text.index("exclusive non-blocking lock"),
            text.index("Classify each data-dir path with `lstat`"),
        )
        self.assertLess(
            text.index("run temp-normalization"),
            text.index("Classify each data-dir path with `lstat`"),
        )

    def test_lead_keeps_credentials_out_of_the_share(self) -> None:
        paragraphs = [part.strip() for part in DEFINITION.read_text().split("\n\n") if part.strip()]
        lead = paragraphs[1] if paragraphs[0].startswith("#") else paragraphs[0]
        self.assertIn("how a file you save on one Groundwork machine shows up on the others", lead)
        for phrase in ("SSH keys", "tokens", "agent credentials", "~/Shared"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, lead)

    def test_tailscale_syncthing_grant_is_self(self) -> None:
        text = (ROOT / "docs" / "tailscale.md").read_text()
        blocks = re.findall(r"```json\n(.*?)```", text, re.S)
        grant = next(block for block in blocks if "22000" in block)
        self.assertIn('"dst": ["autogroup:self"]', grant)
        self.assertIn('"src": ["autogroup:member"]', grant)
        self.assertIn("tcp:22000", grant)
        self.assertIn("udp:22000", grant)

    def test_pairing_is_local_and_idempotent(self) -> None:
        original = DEFINITION.read_text()
        self.assertIn("current user, `SYSTEM`, and `Administrators`", original)
        self.assertIn("ACL of both `config.xml` and `key.pem`", original)
        text = original.lower()
        for phrase in (
            "second run",
            "exits 0",
            "127.0.0.1",
            "x-api-key",
            "mode `0600`",
            "own device id",
            "does not call the other machine",
            "do not write the folder",
            "/rest/config/defaults/device",
            "folder.devices",
            "key.pem",
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

    def test_desktop_checks_stay_out_of_the_syncthing_grant(self) -> None:
        text = (ROOT / "docs" / "tailscale.md").read_text()
        shared_at = text.index("## Shared folders")
        shared = text[shared_at:]
        self.assertLess(text.index("keyboard/mouse"), shared_at)
        self.assertNotIn("keyboard/mouse", shared)
        self.assertIn("tcp:22000", shared)
        self.assertIn("udp:22000", shared)
        self.assertIn("Leave TCP 8384 out", shared)

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
