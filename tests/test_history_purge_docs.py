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
    "remote.origin.mirror",
    "--force-with-lease=refs/heads/main:<recorded-sha>",
    "--force-with-lease=refs/tags/v1.2.3:<recorded-sha>",
    "A count taken before that fetch is the wrong baseline.",
    'b"tree"',
    "This page does not use that form.",
    "--no-gc",
    'git fetch -q --prune --update-head-ok --refmap "" origin +refs/*:refs/*',
    "Do not run that command.",
    "git ls-remote origin 'refs/heads/*' 'refs/tags/*'",
    "keep that list outside the clone",
    "before the rewrite",
    "does not rename paths",
    "Stop and ask the owner.",
    "Do not repeat `--replace-text`",
    "when the local tag object is not the remote tag object",
    "Git reports everything up-to-date.",
    "deletes the pre-rewrite objects before the command returns",
    "Prune only after that patch.",
    "GitHub advertises `refs/pull/*`.",
    "kinds",
    "git filter-repo -h",
    "## Tool contract for environment repos",
    "Per-user: it installs into the user's home, with no root",
    "pipx install git-filter-repo",
    "brew install git-filter-repo",
    "mise use -g pipx:git-filter-repo",
    "explicit confirmation for each repository",
    "its owner's job",
    "Stop unless the help text contains `--sensitive-data-removal`.",
    "A missing command is the same stop.",
    "Do not compare `git filter-repo --version` to `2.47`.",
    'git update-ref "refs/remotes/origin/${branch}" "refs/heads/${branch}"',
    "Do not pass `--force` to `git update-ref` or to `git filter-repo`.",
    "git repack -ad",
    "expected freshly packed repo",
    "`git rev-list --all --count` is the same after that repack as it was before it.",
)


def _filter_repo_skip_reason() -> str | None:
    """Return why the git-filter-repo tests cannot run, or None when they can."""
    try:
        run = subprocess.run(
            ["git", "filter-repo", "-h"], capture_output=True, text=True
        )
    except OSError as error:
        return f"git is unavailable ({error})"
    if "--sensitive-data-removal" in run.stdout + run.stderr:
        return None
    return (
        "git-filter-repo 2.47 or newer (with --sensitive-data-removal) is not "
        "installed; it is an opt-in tool, see docs/history-purge.md"
    )


_SKIP_REASON = _filter_repo_skip_reason()
needs_filter_repo = unittest.skipIf(_SKIP_REASON is not None, _SKIP_REASON or "")


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
        self.assertIn("docs/decisions/worktree-conventions.md", readme)
        self.assertIn("history-purge.md", docs_index)
        self.assertIn("worktree-conventions.md", docs_index)
        self.assertNotIn("The check is `git filter-repo --version`.", text)
        fetch_at = text.index('git fetch -q --prune --update-head-ok --refmap "" origin +refs/*:refs/*')
        restore_at = text.index('git update-ref "refs/remotes/origin/${branch}" "refs/heads/${branch}"')
        repack_at = text.index("git repack -ad")
        rewrite_at = text.index("git filter-repo --sensitive-data-removal --no-gc --replace-text")
        self.assertLess(fetch_at, restore_at)
        self.assertLess(restore_at, repack_at)
        self.assertLess(repack_at, rewrite_at)
        self.assertNotIn("A bare mirror skips this check.", text)
        self.assertNotIn("so the fresh-clone check can pass", text)
        before = text.index("## Before anyone pushes")
        rewrite = text.index("## Rewrite")
        first_remote = text.index("git ls-remote origin 'refs/heads/*' 'refs/tags/*'")
        self.assertLess(before, first_remote)
        self.assertLess(first_remote, rewrite)
        verify = text.split("3. Each tip tree", 1)[1].split("\n4. ", 1)[0]
        self.assertTrue(
            "git diff-tree -r -p" in verify or "git diff-tree -r --patch" in verify,
            verify,
        )
        diff_at = text.index("git diff-tree -r -p")
        prune_at = text.index("Prune only after that patch.")
        self.assertLess(diff_at, prune_at)
        self.assertLess(prune_at, text.index("git gc --prune=now", prune_at))
        self.assertNotIn("does not advertise", text)
        self.assertNotIn("Re-add `origin`", text)
        self.assertNotIn("removes the `origin` remote", text)
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
            kinds = subprocess.run(
                ["python3", str(counter), "kinds", str(needle)],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                kinds.stdout,
                "blob 1\ncommit 0\ntag 0\ntree 0\n",
            )
            self.assertEqual(kinds.stderr, "")
            self.assertNotIn("secret-token-value", kinds.stdout)

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
            kinds = subprocess.run(
                ["python3", str(counter), "kinds", str(needle)],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                kinds.stdout,
                "blob 0\ncommit 0\ntag 0\ntree 0\n",
            )
            self.assertEqual(kinds.stderr, "")
            self.assertNotIn("secret-token-value", kinds.stdout)

    def test_counter_finds_a_filename_only_needle_in_both_modes(self) -> None:
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
            (repo / "secret-token-value.txt").write_text("clean\n", encoding="utf-8")
            git("add", "secret-token-value.txt")
            git("commit", "-m", "add a path")
            counter = root / "count.py"
            counter.write_text(script, encoding="utf-8")
            for mode in ("all", "reachable"):
                result = subprocess.run(
                    ["python3", str(counter), mode, str(needle)],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.stdout.strip(), "1")
                self.assertNotIn("secret-token-value", result.stdout)
                self.assertNotIn("secret-token-value", result.stderr)
            kinds = subprocess.run(
                ["python3", str(counter), "kinds", str(needle)],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                kinds.stdout,
                "blob 0\ncommit 0\ntag 0\ntree 1\n",
            )
            self.assertEqual(kinds.stderr, "")
            self.assertNotIn("secret-token-value", kinds.stdout)

    @needs_filter_repo
    def test_restore_remote_tracking_refs_lets_filter_repo_start(self) -> None:
        text = PAGE.read_text()
        restore = next(
            block
            for block in re.findall(r"```bash\n(.*?)```", text, re.S)
            if 'git update-ref "refs/remotes/origin/${branch}"' in block
        )
        help_run = subprocess.run(
            ["git", "filter-repo", "-h"],
            capture_output=True,
            text=True,
        )
        self.assertIn("--sensitive-data-removal", help_run.stdout + help_run.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin"
            clone = root / "clone"
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

            def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    ["git", *args],
                    cwd=cwd,
                    check=True,
                    env=env,
                    capture_output=True,
                    text=True,
                )

            origin.mkdir()
            git("init", "-b", "main", cwd=origin)
            git("commit", "--allow-empty", "-m", "start", cwd=origin)
            (origin / "note.txt").write_text("prefix secret-token-value suffix\n", encoding="utf-8")
            git("add", "note.txt", cwd=origin)
            git("commit", "-m", "add secret", cwd=origin)
            git("clone", "--no-local", str(origin), str(clone), cwd=root)
            git(
                "fetch", "-q", "--prune", "--update-head-ok", "--refmap", "",
                "origin", "+refs/*:refs/*",
                cwd=clone,
            )
            missing = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main"],
                cwd=clone,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(missing.returncode, 0)
            aborted = subprocess.run(
                [
                    "git", "filter-repo", "--sensitive-data-removal", "--no-gc",
                    "--replace-text", str(needle),
                ],
                cwd=clone,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(aborted.returncode, 1)
            self.assertIn("refs/remotes/origin/main not found", aborted.stderr)
            subprocess.run(["bash", "-c", restore], cwd=clone, env=env, check=True)
            local = git("rev-parse", "refs/heads/main", cwd=clone).stdout.strip()
            tracked = git("rev-parse", "refs/remotes/origin/main", cwd=clone).stdout.strip()
            self.assertEqual(local, tracked)
            started = subprocess.run(
                [
                    "git", "filter-repo", "--sensitive-data-removal", "--no-gc",
                    "--replace-text", str(needle),
                ],
                cwd=clone,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assertIn("New history written", started.stdout)
            self.assertNotIn("--force", restore)

    @needs_filter_repo
    def test_repack_after_pull_fetch_lets_filter_repo_start(self) -> None:
        text = PAGE.read_text()
        restore = next(
            block
            for block in re.findall(r"```bash\n(.*?)```", text, re.S)
            if 'git update-ref "refs/remotes/origin/${branch}"' in block
        )
        repack = next(
            block
            for block in re.findall(r"```bash\n(.*?)```", text, re.S)
            if block.strip() == "git repack -ad"
        )
        self.assertNotIn("--force", restore)
        self.assertNotIn("--force", repack)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin"
            clone = root / "clone"
            mirror = root / "mirror"
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

            def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    ["git", *args],
                    cwd=cwd,
                    check=True,
                    env=env,
                    capture_output=True,
                    text=True,
                )

            def rewrite(cwd: Path) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        "git", "filter-repo", "--sensitive-data-removal", "--no-gc",
                        "--replace-text", str(needle),
                    ],
                    cwd=cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                )

            def commit_count(cwd: Path) -> str:
                return git("rev-list", "--all", "--count", cwd=cwd).stdout.strip()

            origin.mkdir()
            git("init", "-b", "main", cwd=origin)
            (origin / "note.txt").write_text("prefix secret-token-value suffix\n", encoding="utf-8")
            git("add", "note.txt", cwd=origin)
            git("commit", "-m", "add secret", cwd=origin)
            git("repack", "-ad", cwd=origin)
            git("clone", "--no-local", str(origin), str(clone), cwd=root)
            git("clone", "--mirror", "--no-local", str(origin), str(mirror), cwd=root)
            (origin / "pull-only.txt").write_text("pull-only\n", encoding="utf-8")
            git("add", "pull-only.txt", cwd=origin)
            git("commit", "-m", "pull only", cwd=origin)
            git("update-ref", "refs/pull/1/head", "HEAD", cwd=origin)
            git("reset", "--hard", "HEAD~1", cwd=origin)

            def fetch(cwd: Path) -> None:
                git(
                    "fetch", "-q", "--prune", "--update-head-ok", "--refmap", "",
                    "origin", "+refs/*:refs/*",
                    cwd=cwd,
                )

            fetch(clone)
            before = commit_count(clone)
            subprocess.run(["bash", "-c", restore], cwd=clone, env=env, check=True)
            packed = rewrite(clone)
            self.assertEqual(packed.returncode, 1, packed.stderr)
            self.assertIn("expected freshly packed repo", packed.stderr)
            subprocess.run(["bash", "-c", repack], cwd=clone, env=env, check=True)
            self.assertEqual(commit_count(clone), before)
            started = rewrite(clone)
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assertIn("New history written", started.stdout)

            fetch(mirror)
            mirror_before = commit_count(mirror)
            mirror_packed = rewrite(mirror)
            self.assertEqual(mirror_packed.returncode, 1, mirror_packed.stderr)
            self.assertIn("expected freshly packed repo", mirror_packed.stderr)
            subprocess.run(["bash", "-c", repack], cwd=mirror, env=env, check=True)
            self.assertEqual(commit_count(mirror), mirror_before)
            mirror_started = rewrite(mirror)
            self.assertEqual(mirror_started.returncode, 0, mirror_started.stderr)
            self.assertIn("New history written", mirror_started.stdout)


if __name__ == "__main__":
    unittest.main()
