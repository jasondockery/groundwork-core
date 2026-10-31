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

# Phrases from the old temp matrix and the publish-on-first-launch path.
_REMOVED_UNSAFE_RULES = (
    "This first-session path still launches",
    "This migration path still launches",
    "rename the data-dir temp onto that shared path",
    "rename the temp onto `name.db`",
    "A sole `~/Shared/FreeTube/<name>.db~` becomes",
    "run temp-normalization",
    "leave the folder paused",
    "delete only the sibling `name.db~`",
    "The same-directory rename runs only when",
    "move and symlink every regular file whose shared path is absent, then stop",
    "A first session is allowed only when this device is the folder's only member",
    "only when this device is the folder's only member",
    "POST /rest/db/override",
    "availability is non-empty",
    "An absent shared file is never a first session or a migration",
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
            "groundwork-freetube",
            "trashcan",
            "2.1.2",
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
        for folder in ("groundwork-freetube", "groundwork-obsidian"):
            with self.subTest(versioning=folder):
                versioning = value_for(f"`folder.versioning` on `{folder}`")
                self.assertIn("trashcan", versioning)
                self.assertIn("cleanoutDays", versioning)
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
            "The FreeTube wrapper never pauses `groundwork-shared`.",
            "Pause and resume only `groundwork-freetube`.",
            "The cluster has no copy of a name when the folder is unpaused",
            "the person's confirmation",
            "Do not publish a local file while a live copy exists.",
            "global.deleted` false and `global.invalid` false",
            "Do not decide peer presence from `availability`.",
            "GET /rest/db/file",
            "receive-only",
            "POST /rest/db/revert",
            "GET /rest/db/localchanged?folder=groundwork-freetube",
            "move those files aside, revert, and move them back",
            "Stay `receiveonly` and unpaused until `local.deleted` is false and the path is a regular file.",
            "Never promote `name.db~` when a main file exists.",
            "quarantine the temp and migrate the main only",
            "Offer deletion confirmation only when `global.deleted` is true and every other device in `folder.devices` has connected since that deletion.",
            "a live copy may still be in `.stversions` on a peer",
            "`/FreeTube` as the first pattern",
            "before either folder is added and before the first scan",
            "Do not announce those entries as deletions.",
            "A file on disk, including a 0-byte file, is a present shared file.",
            "Resume only when every name is either a present shared file or a deletion the person confirmed for that specific name.",
            "Printing the path, running apply, or confirming one name does not confirm the others.",
            "Never create an empty database to fill the hole.",
            "Resuming `sendreceive` while an indexed file is missing announces the absence as a deletion",
            "If the lock is busy and no FreeTube process exists, exit without launching.",
            "Only the holder launches, and only after the pause.",
            "Do not choose by mtime.",
            "A symlink is not a main.",
            "Print the missing path and stop rather than reclassifying in a loop.",
            "One pass classifies all four names, then one folder decision.",
            "Launch when every name is already present locally, or when the person confirmed the one create path",
            "If the shared file is already there, stop and print both paths.",
            "versioning.type` `trashcan`",
            "cleanoutDays` `0`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in _REMOVED_UNSAFE_RULES:
            with self.subTest(removed=phrase):
                self.assertNotIn(phrase, text)
        self.assertEqual(text.count("PATCH /rest/config/folders/groundwork-shared"), 2)
        freetube = text.split("## FreeTube", 1)[1]
        self.assertNotIn("PATCH /rest/config/folders/groundwork-shared", freetube)
        self.assertNotIn("compacted successor", text)
        self.assertNotIn("keep the newer", text)
        self.assertLess(text.index("compare its path"), text.index("already in `folder.devices`"))
        self.assertLess(
            text.index("before either folder is added and before the first scan"),
            text.index("Enable and start the user service."),
        )
        self.assertIn("The data-dir symlink survives", decision)
        self.assertIn("classifies each data-dir name with `lstat`", decision)
        self.assertIn("while `global` has a live copy", decision)
        self.assertIn("when the cluster has no copy", decision)
        self.assertNotIn("replaces the symlink", decision)
        self.assertNotIn("moves the compacted file back", decision)
        self.assertIn("The cheatsheet says Quit, not close the window.", decision)
        self.assertIn(
            "An index reset of `groundwork-shared` pauses that folder first.",
            decision,
        )
        self.assertIn(
            "The unpause waits until a probe fails and the new API answers, then retries.",
            decision,
        )
        self.assertIn(
            "After a sample has been `scanning` or `scan-waiting` and the latest sample is `idle`, the FreeTube browse must be empty.",
            decision,
        )
        self.assertIn(
            "A paused folder's `state` is `\"\"`.",
            decision,
        )
        self.assertIn(
            "A lost response resumes the same process when `startTime` is unchanged.",
            decision,
        )
        self.assertIn("The wrapper still never pauses it.", decision)

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
            "If the shared file is already there, stop and print both paths.",
            "Do not resume `sendreceive` while any of the four names is still a regular file",
            "The FreeTube wrapper never pauses `groundwork-shared`.",
            "PATCH /rest/config/folders/groundwork-freetube",
            'body `{"paused": false}` only',
            "When `tailscale ip -4` fails on a machine that is already serving, do not PATCH `listenAddresses`.",
            "Keep the addresses already in effect.",
            "Refuse to apply or wrap",
            "older than 2.1.2",
            "10389",
            "10746",
            "The apply takes the same non-blocking lock",
            "If it is busy, do not resume, move, or relink.",
            "re-check that no FreeTube process exists",
            "Do not `PUT` a default folder object over a paused folder.",
            "Any other `lstat` result: print the paths, change nothing, and do not launch.",
            "The service must not set `STGUIADDRESS` or `--gui-address`.",
            "The override hides the config value",
            "does not rewrite `config.xml`",
            "The step stays unfinished until the override is unset and the listening socket is `127.0.0.1:8384`",
            "A later apply uses the same per-name rule.",
            "POST /rest/db/revert",
            "POST /rest/system/reset?folder=groundwork-shared",
            "must be paused before `POST /rest/system/reset?folder=groundwork-shared`",
            "folder must be paused when resetting",
            "drops that folder's index and does not scan",
            "pause Shared in the GUI",
            "Do not resume when the reset response returns.",
            "wait until a probe fails because the old process is gone",
            "GET /rest/system/ping",
            "Then wait until the API answers again.",
            'Only then retry `PATCH /rest/config/folders/groundwork-shared` with only `{"paused": false}` until the new process accepts it.',
            "Resume the current process when the POST returned an error and that process never exited.",
            "Record `startTime` from `GET /rest/system/status` before the POST.",
            "The same `startTime`, with ping still succeeding, means this process never exited: resume it.",
            "A different `startTime` is the new process: unpause that process after `GET /rest/system/ping` answers.",
            "until a sample has been `scanning` or `scan-waiting` and the latest sample is `idle`",
            'A paused folder has no runner, so `state` is `""`.',
            "The scan that skips `FreeTube` runs when that unpaused folder starts.",
            "require `GET /rest/db/browse?folder=groundwork-shared&prefix=FreeTube` to be empty",
            "If the folder is not paused yet, do not reset and do not resume.",
            "The only pause of `groundwork-shared` is the index reset above.",
            "Do not announce those entries as deletions.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in _REMOVED_UNSAFE_RULES:
            with self.subTest(removed=phrase):
                self.assertNotIn(phrase, text)
        self.assertNotIn("a lost response is not that case", text)
        self.assertNotIn("until `state` has left `idle` and returned to `idle`", text)
        self.assertNotIn("state is still `idle`", text)
        self.assertNotIn("Close it and wait", text)
        self.assertNotIn("If the shared file is absent, do not launch.", text)
        self.assertNotIn("replaces the address in config", text)
        self.assertNotIn("leave the temp so NeDB can rename it back", text)
        self.assertNotIn("then classify again", text)
        self.assertNotIn("print the missing path, and do not launch", text)
        self.assertNotIn("Apply follows the same rule", text)
        self.assertNotIn("symlink it, then resume", text)
        self.assertNotIn("or the deletion was confirmed", text)
        self.assertNotIn("wherever its main file lives", text)
        self.assertLess(
            text.index("exclusive non-blocking lock"),
            text.index("Classify each data-dir path with `lstat`"),
        )
        self.assertLess(
            text.index("Never promote `name.db~` when a main file exists."),
            text.index("Classify each data-dir path with `lstat`"),
        )

    def test_obsidian_vault_contract(self) -> None:
        text = DEFINITION.read_text()
        decision = DECISION.read_text()
        section = text.split("## Obsidian vault", 1)[1].split("\n## ", 1)[0]
        folders = _table_rows(text, "| | `groundwork-shared` |")
        by_row = {row[0]: row for row in folders}
        self.assertEqual(by_row["Label"][3], "`Obsidian`")
        self.assertIn("never inside `~/Shared`", by_row["Path"][3])
        self.assertIn("`trashcan`", by_row["Versioning"][3])
        self.assertIn("`cleanoutDays` `0`", by_row["Versioning"][3])
        self.assertIn("`receiveonly` when first added", by_row["Type"][3])
        ignore = re.search(r"```text\n(.*?)```", section, re.S)
        self.assertIsNotNone(ignore)
        self.assertEqual(
            ignore.group(1).split(),
            [
                "/.obsidian/workspace.json",
                "/.obsidian/workspace-mobile.json",
                "/.obsidian/cache",
            ],
        )
        for phrase in (
            "before the folder is added and before the first scan",
            "these lines come before any `!` pattern",
            "Everything else in `.obsidian` syncs",
            "`plugins/`",
            "It is sync, not a backup.",
            "Obsidian Git",
            "Never create a vault, never create the saved directory, and never move, rename, or relocate an existing vault.",
            "If the vault folder is missing, skip it and print the saved path.",
            "Do not retarget the folder.",
            "The vault is never nested inside `~/Shared`",
            "`~/Library/Mobile Documents`",
            "creates `groundwork-obsidian` as `receiveonly` on every machine",
            "groundwork syncthing-pair obsidian-promote",
            "is the only path from `receiveonly` to `sendreceive`",
            "GET /rest/db/localchanged?folder=groundwork-obsidian",
            'PATCH /rest/config/folders/groundwork-obsidian` with only `{"type": "sendreceive"}`',
            "Only a typed yes promotes.",
            "this merges two vaults",
            "Groundwork never calls `POST /rest/db/revert` on `groundwork-obsidian`.",
            "never sets `autoAcceptFolders` or `introducer` to `true`",
            "never accepts a pending device or a pending folder",
            "This repository never holds a vault path.",
            "`syncthing.obsidian_vault`",
            "groundwork syncthing-pair obsidian-vault --clear",
            "A run with no terminal does not ask, does not save anything, skips `groundwork-obsidian`",
            "uses resolved real paths",
            "case-insensitive",
            "Promote one machine at a time.",
            "with no `device` parameter, must report `completion` 100",
            "`needTotalItems` 0 and `pullErrors` 0",
            "Do not wait on a peer's completion",
            "page through it with `page` and `perpage`",
            "65536",
            "**new:**",
            "**changed:**",
            "**deleted:**",
            "Changed files replace that note there. Deleted files delete that note there.",
            "in its own trash can (`.stversions`)",
            "renames the copy with the older modification time",
            "always returns a `global` object",
            "An empty `global.name` means the cluster has no entry for that path.",
            "a live copy is `global.deleted` false and `global.invalid` false",
            "**new:** `deleted` is false and there is no live copy.",
            "**changed:** `deleted` is false and there is a live copy.",
            "**deleted:** `deleted` is true and there is a live copy.",
            "A deleted entry with no live copy is a local-only deletion.",
            "left out of every class, out of the prompt, and out of the count",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)
        self.assertNotIn("as `sendreceive` on", section)
        self.assertNotIn("for each connected device and this folder to be complete", section)
        self.assertNotIn("becomes a `*.sync-conflict-*` copy there", section)
        self.assertNotIn("Nothing in the local vault is deleted", section)
        self.assertNotIn("has no `global`", section)
        self.assertNotIn("or `global.deleted` is true)", section)
        self.assertLess(
            text.index("apply the [saved vault path](#saved-vault-path) rules first"),
            text.index("8. Exit 0."),
        )
        self.assertIn("type `receiveonly`, and trash-can versioning", text)
        self.assertIn("`groundwork-obsidian` is not written at install.", text)
        lowered = decision.lower()
        for phrase in (
            "issue 47",
            "opt-in per machine",
            "trash can, not simple versioning",
            "first pairing is receive-only",
            "obsidian git",
            "reviewed on 2026-10-31",
        ):
            with self.subTest(decision=phrase):
                self.assertIn(phrase, lowered)

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
