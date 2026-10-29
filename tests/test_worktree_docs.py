#!/usr/bin/env python3
"""Contract checks for the worktree convention."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "decisions" / "worktree-conventions.md"

REQUIRED = (
    "~/worktrees/<repo>/<slug>",
    "~/.cursor/worktrees/<repository>/<name>",
    ".claude/worktrees/<name>",
    "worktree-<name>",
    "$CODEX_HOME/worktrees",
    "~/.herdr/worktrees/<repo>/<branch-slug>",
    "~/.t3/worktrees",
    "t3/",
    "git worktree add -b <slug>",
    "origin/main",
    "git worktree remove",
    "git branch -d <slug>",
    "git worktree prune",
    "extensions.worktreeConfig",
    "include_worktrees = true",
    "docs/worktrees.html",
    "Status: proposed",
    "groundwork-core#13",
)


class WorktreeDocsTest(unittest.TestCase):
    def test_page_is_linked_and_states_the_convention(self) -> None:
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
        self.assertIn("docs/decisions/worktree-conventions.md", readme)
        self.assertIn("decisions/worktree-conventions.md", docs_index)
        for source in (PAGE, ROOT / "README.md", ROOT / "docs" / "README.md"):
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source.read_text()):
                target = link.split("#", 1)[0].strip()
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                self.assertTrue((source.parent / target).resolve().exists(), target)


if __name__ == "__main__":
    unittest.main()
