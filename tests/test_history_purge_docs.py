#!/usr/bin/env python3
"""Contract checks for the history-purge runbook."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "history-purge.md"

REQUIRED = (
    "git-filter-repo",
    "not a Groundwork default",
    "This repository does not install it.",
    "asks the owner before any install",
    "2.47",
    "--sensitive-data-removal",
    "--replace-text",
    "--replace-message",
    "--force-with-lease",
    "git push --force --mirror origin",
    "refs/pull",
    "git cat-file --batch-all-objects",
    "git rev-list --all --count",
    "commit-map",
    "Never name the purged text",
    "git filter-branch",
    "pipx install git-filter-repo",
    "mode `0600`",
    "Do not pass `--no-fetch`.",
    "delete the clone and clone again",
)


def _script() -> str:
    match = re.search(r"```python\n(.*?)```", PAGE.read_text(), re.S)
    if not match:
        raise AssertionError("history purge page has no python block")
    return match.group(1)


class HistoryPurgeDocsTest(unittest.TestCase):
    def test_page_is_linked_and_states_the_contract(self) -> None:
        text = PAGE.read_text()
        self.assertTrue(PAGE.is_file())
        for phrase in REQUIRED:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("\u2014", text)
        self.assertNotIn("\u2013", text)
        self.assertNotIn("Co-authored-by:", text)
        readme = (ROOT / "README.md").read_text()
        docs_index = (ROOT / "docs" / "README.md").read_text()
        self.assertIn("docs/history-purge.md", readme)
        self.assertIn("history-purge.md", docs_index)
        for source in (PAGE, ROOT / "README.md", ROOT / "docs" / "README.md"):
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source.read_text()):
                target = link.split("#", 1)[0].strip()
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                self.assertTrue((source.parent / target).resolve().exists(), target)

    def test_counter_reports_reachable_hits_without_printing_the_needle(self) -> None:
        script = _script()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            needle = root / "needle.txt"
            needle.write_bytes(b"secret-token-value\n")
            os.chmod(needle, 0o600)
            env = {
                **os.environ,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            }

            def git(*args: str) -> None:
                subprocess.run(["git", *args], cwd=repo, check=True, env=env, capture_output=True)

            git("init", "-b", "main")
            (repo / "note.txt").write_text("clean\n", encoding="utf-8")
            git("add", "note.txt")
            git("commit", "-m", "start")
            (repo / "note.txt").write_text("prefix secret-token-value suffix\n", encoding="utf-8")
            git("add", "note.txt")
            git("commit", "-m", "add note")
            counter = root / "count.py"
            counter.write_text(script, encoding="utf-8")
            for mode, expected in (("all", "1"), ("reachable", "1")):
                result = subprocess.run(
                    ["python3", str(counter), mode, str(needle)],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.stdout.strip(), expected)
                self.assertNotIn("secret-token-value", result.stdout)
                self.assertNotIn("secret-token-value", result.stderr)

            git("reset", "--hard", "HEAD~1")
            result = subprocess.run(
                ["python3", str(counter), "reachable", str(needle)],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.stdout.strip(), "0")
            leftover = subprocess.run(
                ["python3", str(counter), "all", str(needle)],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(leftover.stdout.strip(), "0")
            self.assertNotIn("secret-token-value", leftover.stdout)


if __name__ == "__main__":
    unittest.main()
