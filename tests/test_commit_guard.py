#!/usr/bin/env python3
"""Behavior checks for commit-guard/commit-identity-guard.sh on temp repos."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "commit-guard" / "commit-identity-guard.sh"


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.repo = t / "repo"
        self.repo.mkdir()
        self.deny = t / "denylist"
        self.deny.write_text("# comment\n\nalt-account\nexample-org\n")
        self.env = {
            "PATH": os.environ["PATH"], "HOME": str(t),
            "GROUNDWORK_COMMIT_DENYLIST": str(self.deny),
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "Test User", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test User", "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        self.git("init", "-q", "-b", "main")

    def git(self, *a, env=None, **kw):
        return subprocess.run(["git", *a], cwd=self.repo, env=env or self.env,
                              capture_output=True, text=True, **kw)

    def msg_check(self, text, env=None):
        p = self.repo / "MSG"
        p.write_text(text)
        return subprocess.run([str(GUARD), "commit-msg", str(p)], cwd=self.repo,
                              env=env or self.env, capture_output=True, text=True)

    def commit(self, msg, env=None):
        (self.repo / "f").write_text(msg)
        self.git("add", "f")
        r = self.git("commit", "-q", "-m", msg, "--allow-empty", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def push_check(self, local, remote="0" * 40):
        return subprocess.run([str(GUARD), "pre-push", "origin", "url"], cwd=self.repo,
                              env=self.env, capture_output=True, text=True,
                              input=f"refs/heads/main {local} refs/heads/main {remote}\n")

    def test_valid_commit(self):
        self.assertEqual(self.msg_check("feat: x\n").returncode, 0)

    def test_bad_trailer_any_case(self):
        for t in ("Co-authored-by: A <a@example.com>", "CO-AUTHORED-BY: A", "  co-Authored-By : A"):
            r = self.msg_check(f"feat: x\n\n{t}\n")
            self.assertEqual(r.returncode, 1, t)
            self.assertIn("Co-authored-by", r.stderr)

    def test_comment_line_ignored(self):
        self.assertEqual(self.msg_check("feat: x\n# Co-authored-by: a\n").returncode, 0)

    def test_agent_session_allowed(self):
        self.assertEqual(self.msg_check("feat: x\n\nAgent-Session: abc-123\n").returncode, 0)

    def test_denylisted_author_and_committer(self):
        for key in ("AUTHOR", "COMMITTER"):
            env = dict(self.env, **{f"GIT_{key}_NAME": "Alt-Account"})
            r = self.msg_check("feat: x\n", env=env)
            self.assertEqual(r.returncode, 1, key)
            self.assertIn(key.lower(), r.stderr)
        env = dict(self.env, GIT_AUTHOR_EMAIL="me@Example-Org.test")
        self.assertEqual(self.msg_check("feat: x\n", env=env).returncode, 1)

    def test_personal_email_not_rejected(self):
        env = dict(self.env, GIT_AUTHOR_EMAIL="someone@gmail.com")
        self.assertEqual(self.msg_check("feat: x\n", env=env).returncode, 0)

    def test_missing_denylist_disables_identity_rule(self):
        self.deny.unlink()
        env = dict(self.env, GIT_AUTHOR_NAME="alt-account")
        self.assertEqual(self.msg_check("feat: x\n", env=env).returncode, 0)

    def test_pre_push_valid_and_agent_session(self):
        self.commit("one")
        sha = self.commit("two\n\nAgent-Session: s1")
        self.assertEqual(self.push_check(sha).returncode, 0)

    def test_pre_push_catches_any_commit_in_range(self):
        self.commit("one")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.commit("bad\n\nCo-authored-by: A <a@example.com>")
        sha = self.commit("tip")
        r = self.push_check(sha, remote=base)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Co-authored-by", r.stderr)
        # Outside the pushed range is not checked.
        self.assertEqual(self.push_check(base, remote=base).returncode, 0)

    def test_pre_push_denylisted_committer(self):
        env = dict(self.env, GIT_COMMITTER_NAME="example-org bot")
        sha = self.commit("one", env=env)
        r = self.push_check(sha)
        self.assertEqual(r.returncode, 1)
        self.assertIn("committer", r.stderr)

    def test_pre_push_delete_ignored(self):
        self.assertEqual(self.push_check("0" * 40, remote="a" * 40).returncode, 0)

    def test_whitespace_denylist_lines_ignored(self):
        self.deny.write_text("  \n\t\n  alt-account  \n")
        self.assertEqual(self.msg_check("feat: x\n").returncode, 0)
        env = dict(self.env, GIT_AUTHOR_NAME="alt-account")
        self.assertEqual(self.msg_check("feat: x\n", env=env).returncode, 1)

    def test_force_push_over_unfetched_remote_tip(self):
        t = Path(self.tmp.name)
        bare = t / "bare.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
        self.git("remote", "add", "origin", str(bare))
        base = self.commit("base")
        self.git("push", "-q", "origin", "main")
        other = t / "other"
        subprocess.run(["git", "clone", "-q", str(bare), str(other)], env=self.env, check=True)
        (other / "g").write_text("g")
        for c in (["add", "g"], ["commit", "-q", "-m", "unfetched"], ["push", "-q", "origin", "main"]):
            subprocess.run(["git", *c], cwd=other, env=self.env, check=True)
        rsha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=other, env=self.env,
                              capture_output=True, text=True).stdout.strip()
        self.assertNotEqual(self.git("cat-file", "-e", rsha).returncode, 0)
        bad = self.commit("bad\n\nCo-authored-by: A <a@example.com>")
        r = self.push_check(bad, remote=rsha)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Co-authored-by", r.stderr)

    def merged_main_branch(self):
        """Branch already on the remote, then merges a main whose new commit
        carries a GitHub-style co-author trailer. Returns (branch tip, remote tip)."""
        t = Path(self.tmp.name)
        bare = t / "bare.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)],
                       env=self.env, check=True)
        self.git("remote", "add", "origin", str(bare))
        self.commit("base")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "-b", "feat")
        rsha = self.commit("feat one")
        self.assertEqual(self.git("push", "-q", "origin", "feat").returncode, 0)
        other = t / "other"
        subprocess.run(["git", "clone", "-q", str(bare), str(other)], env=self.env, check=True)
        (other / "g").write_text("g")
        msg = "squash (#1)\n\nCo-authored-by: someone <1+someone@users.noreply.github.com>"
        for c in (["add", "g"], ["commit", "-q", "-m", msg], ["push", "-q", "origin", "main"]):
            subprocess.run(["git", *c], cwd=other, env=self.env, check=True)
        self.assertEqual(self.git("fetch", "-q", "origin").returncode, 0)
        r = self.git("merge", "-q", "--no-edit", "origin/main")
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.git("rev-parse", "HEAD").stdout.strip(), rsha

    def branch_push_check(self, local, remote):
        return subprocess.run([str(GUARD), "pre-push", "origin", "url"], cwd=self.repo,
                              env=self.env, capture_output=True, text=True,
                              input=f"refs/heads/feat {local} refs/heads/feat {remote}\n")

    def test_branch_merging_published_main_pushes(self):
        tip, rsha = self.merged_main_branch()
        r = self.branch_push_check(tip, rsha)
        self.assertEqual(r.returncode, 0, r.stderr)
        # Also through git itself, with the guard as the pre-push hook.
        hooks = Path(self.tmp.name) / "hooks"
        hooks.mkdir()
        (hooks / "pre-push").write_text(f'#!/bin/sh\nexec "{GUARD}" pre-push "$@"\n')
        (hooks / "pre-push").chmod(0o755)
        self.git("config", "core.hooksPath", str(hooks))
        r = self.git("push", "-q", "origin", "feat")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_new_trailer_commit_after_merge_blocked(self):
        _, rsha = self.merged_main_branch()
        bad = self.commit("mine\n\nCo-authored-by: A <a@example.com>")
        tip = self.commit("tip")
        r = self.branch_push_check(tip, rsha)
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"in commit {bad}", r.stderr)
        self.assertEqual(r.stderr.count("Co-authored-by trailer"), 1, r.stderr)

    def test_new_branch_merging_published_main_pushes(self):
        tip, _ = self.merged_main_branch()
        r = self.branch_push_check(tip, "0" * 40)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_remote_tracking_ref_fails_closed(self):
        tip, rsha = self.merged_main_branch()
        self.assertEqual(self.git("update-ref", "-d", "refs/remotes/origin/main").returncode, 0)
        r = self.branch_push_check(tip, rsha)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Co-authored-by", r.stderr)
        self.assertIn("git fetch", r.stderr)
        # No remote-tracking refs at all: a new ref checks all reachable history.
        self.assertEqual(self.git("update-ref", "-d", "refs/remotes/origin/feat").returncode, 0)
        self.assertEqual(self.branch_push_check(tip, "0" * 40).returncode, 1)

    def test_commit_from_other_remote_still_checked(self):
        # A denylisted commit fetched from another remote (work, upstream,
        # fork) is not on origin, so pushing it to origin is blocked.
        tip, rsha = self.merged_main_branch()
        t = Path(self.tmp.name)
        work = t / "work.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(work)],
                       env=self.env, check=True)
        wclone = t / "wclone"
        subprocess.run(["git", "clone", "-q", str(work), str(wclone)], env=self.env, check=True)
        wenv = dict(self.env, GIT_AUTHOR_NAME="Alt-Account")
        (wclone / "w").write_text("w")
        for c in (["add", "w"], ["commit", "-q", "-m", "work"], ["push", "-q", "origin", "main"]):
            subprocess.run(["git", *c], cwd=wclone, env=wenv, check=True)
        self.git("remote", "add", "work", str(work))
        self.assertEqual(self.git("fetch", "-q", "work").returncode, 0)
        r = self.git("checkout", "-q", "-b", "from-work", "work/main")
        self.assertEqual(r.returncode, 0, r.stderr)
        wsha = self.git("rev-parse", "HEAD").stdout.strip()
        r = subprocess.run([str(GUARD), "pre-push", "origin", "url"], cwd=self.repo,
                           env=self.env, capture_output=True, text=True,
                           input=f"refs/heads/from-work {wsha} refs/heads/from-work {'0' * 40}\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("author matches the local denylist", r.stderr)
        self.assertIn(f"in commit {wsha}", r.stderr)
        # Pushing it to the work remote, which already has it, passes.
        r = subprocess.run([str(GUARD), "pre-push", "work", "url"], cwd=self.repo,
                           env=self.env, capture_output=True, text=True,
                           input=f"refs/heads/copy {wsha} refs/heads/copy {'0' * 40}\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        # A bare-URL push (no remote name) matches no tracking refs: fails closed.
        r = subprocess.run([str(GUARD), "pre-push", str(work), str(work)], cwd=self.repo,
                           env=self.env, capture_output=True, text=True,
                           input=f"refs/heads/feat {tip} refs/heads/feat {'0' * 40}\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Co-authored-by", r.stderr)

    def test_rev_list_failure_refuses_push(self):
        r = self.push_check("f" * 40)
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusing push", r.stderr)

    def test_doctor(self):
        t = Path(self.tmp.name)
        (t / ".claude").mkdir()
        gitcfg = t / "gitconfig"
        gitcfg.write_text("[user]\n\tname = A\n\temail = a@example.com\n")
        env = dict(self.env, GIT_CONFIG_GLOBAL=str(gitcfg))
        run = lambda: subprocess.run([str(GUARD), "doctor"], cwd=self.repo, env=env,
                                     capture_output=True, text=True)
        self.assertEqual(run().returncode, 1)
        (t / ".claude" / "settings.json").write_text('{"attribution": {"commit": "", "pr": ""}}')
        self.assertEqual(run().returncode, 0, run().stdout)


PATTERNS = GUARD.parent / "owner-remote-patterns"
OWNER = "jasondockery"


class ScopeTest(unittest.TestCase):
    """Real git: which remotes turn on core.hooksPath through the patterns."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        include = t / ".config" / "groundwork" / "commit-guard.gitconfig"
        include.parent.mkdir(parents=True)
        include.write_text("[core]\n\thooksPath = /guard/hooks\n")
        self.env = {"PATH": os.environ["PATH"], "HOME": str(t),
                    "XDG_CONFIG_HOME": str(t / ".config"),
                    "GIT_CONFIG_GLOBAL": str(t / "gitconfig"), "GIT_CONFIG_SYSTEM": "/dev/null"}
        glob = "".join(f"[{c}{c.upper()}]" if c.upper() != c else c for c in OWNER)
        for line in PATTERNS.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                key = f"includeIf.hasconfig:remote.*.url:{line.replace('<owner>', glob)}.path"
                subprocess.run(["git", "config", "--file", self.env["GIT_CONFIG_GLOBAL"],
                                key, str(include)], env=self.env, check=True)
        self.repo = t / "repo"

    def hooks_path(self, url):
        subprocess.run(["rm", "-rf", str(self.repo)], check=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], env=self.env, check=True)
        subprocess.run(["git", "-C", str(self.repo), "remote", "add", "origin", url],
                       env=self.env, check=True)
        r = subprocess.run(["git", "-C", str(self.repo), "config", "--get", "core.hooksPath"],
                           env=self.env, capture_output=True, text=True)
        return r.stdout.strip()

    def test_guarded(self):
        for url in (f"https://github.com/{OWNER}/r.git", f"git@github.com:{OWNER}/r.git",
                    f"ssh://git@github.com/{OWNER}/r.git", f"git@github-personal:{OWNER}/r.git",
                    f"ssh://git@github.com:22/{OWNER}/r.git", "ssh://git@github.com:22/JasonDockery/r",
                    f"ssh://git@ssh.github.com:443/{OWNER}/r.git",
                    f"ssh://git@github-personal/{OWNER}/r.git", f"ssh://github.com:22/{OWNER}/r"):
            self.assertEqual(self.hooks_path(url), "/guard/hooks", url)

    def test_not_guarded(self):
        for url in (f"ssh://git@github.com:22/{OWNER}2/r.git", f"ssh://git@github.com:22/other/{OWNER}/r",
                    "ssh://git@github.com:22/other/r.git", f"https://github.com/{OWNER}2/r",
                    # Accepted gaps (docs/commit-identity.md).
                    f"https://github.com:443/{OWNER}/r.git", f"https://user@github.com/{OWNER}/r",
                    f"git+ssh://git@github.com:22/{OWNER}/r"):
            self.assertEqual(self.hooks_path(url), "", url)

    def test_doc_lists_every_pattern(self):
        doc = (GUARD.parents[1] / "docs" / "commit-identity.md").read_text()
        for line in PATTERNS.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                self.assertIn(f"\n{line}\n", doc)


if __name__ == "__main__":
    unittest.main()
