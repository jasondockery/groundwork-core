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


if __name__ == "__main__":
    unittest.main()
