#!/usr/bin/env python3
"""Behavior checks for git-credential/: real git and the real scripts, with a
temp HOME, temp system and global git config, and a fake gh on PATH."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "git-credential"
HELPER = DIR / "owner-credential-helper.sh"
SETUP = DIR / "setup-github-https.sh"
CHECK = DIR / "check-github-https.sh"
KEY = "credential.https://github.com.helper"

# Fake gh: a token per -u account, `auth status` in gh's text form, and
# git_protocol stored in a file. The first account in FAKE_GH_ACCOUNTS is active.
FAKE_GH = r"""#!/bin/sh
case "$1 $2" in
  "auth token")
    u=; while [ $# -gt 0 ]; do [ "$1" = -u ] && u=$2; shift; done
    case " $FAKE_GH_ACCOUNTS " in *" $u "*) echo "tok-$u" ;; *) exit 1 ;; esac ;;
  "auth status")
    for a in $FAKE_GH_ACCOUNTS; do echo "  ✓ Logged in to github.com account $a (keyring)"; done ;;
  "auth git-credential")
    [ "$3" = get ] || exit 0
    cat >/dev/null; set -- $FAKE_GH_ACCOUNTS; printf 'username=%s\npassword=tok-%s\n' "$1" "$1" ;;
  "config get") cat "$FAKE_GH_STATE/proto" 2>/dev/null ;;
  "config set") shift 2; [ "$1" = -h ] && shift 2; echo "$2" > "$FAKE_GH_STATE/proto" ;;
  *) exit 2 ;;
esac
"""

# Fake macOS keychain helper, configured system-wide the way Apple's git is.
# It answers every get and logs each call, so any use of it is visible.
FAKE_KEYCHAIN = r"""#!/bin/sh
echo "$1" >> "$FAKE_GH_STATE/keychain.log"
cat >/dev/null
[ "$1" = get ] && printf 'username=keychain\npassword=tok-keychain\n'
exit 0
"""


class GitCredentialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.t = t = Path(self.tmp.name)
        (t / "bin").mkdir()
        for name, body in (("gh", FAKE_GH), ("git-credential-osxkeychain", FAKE_KEYCHAIN)):
            (t / "bin" / name).write_text(body)
            (t / "bin" / name).chmod(0o755)
        (t / "sysconfig").write_text("[credential]\n\thelper = osxkeychain\n")
        self.gitconfig = t / "gitconfig"
        self.installed = t / "data" / "groundwork" / "git-credential" / "owner-credential-helper.sh"
        self.gh = t / "bin" / "gh"
        self.env = {
            "PATH": f"{t / 'bin'}:{os.environ['PATH']}", "HOME": str(t),
            "XDG_CONFIG_HOME": str(t / "config"), "XDG_DATA_HOME": str(t / "data"),
            "GNUPGHOME": str(t / "gnupg"), "TMPDIR": str(t),
            "GIT_CONFIG_GLOBAL": str(self.gitconfig), "GIT_CONFIG_SYSTEM": str(t / "sysconfig"),
            "GIT_TERMINAL_PROMPT": "0",
            "FAKE_GH_STATE": str(t), "FAKE_GH_ACCOUNTS": "personal work-account",
        }

    def run_(self, *cmd, input=None, cwd=None):
        return subprocess.run([str(c) for c in cmd], env=self.env, input=input,
                              cwd=cwd or self.t, capture_output=True, text=True, timeout=30)

    def git(self, *a, **kw):
        return self.run_("git", *a, **kw)

    def setup(self, *extra, rc=0):
        r = self.run_(SETUP, "--map", "example-org=work-account", *extra)
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        return r

    def fill(self, path, rc=0, host="github.com"):
        r = self.git("credential", "fill",
                     input=f"protocol=https\nhost={host}\npath={path}\n\n")
        self.assertEqual(r.returncode, rc, r.stderr)
        return dict(line.split("=", 1) for line in r.stdout.splitlines()) if rc == 0 else r

    def repo(self, name, url):
        r = self.t / "code" / name
        self.git("init", "-q", r)
        self.git("-C", r, "remote", "add", "origin", url)
        return r

    def check(self, *args):
        return self.run_(CHECK, *args)

    def assert_fail_with_fix(self, out, needle):
        lines = out.splitlines()
        hits = [i for i, l in enumerate(lines) if l.startswith("FAIL:") and needle in l]
        self.assertTrue(hits, f"no FAIL with {needle!r} in:\n{out}")
        for i in hits:
            self.assertTrue(i + 1 < len(lines) and lines[i + 1].startswith("  fix: "), out)

    def test_routes_by_owner_and_fails_closed(self):
        self.setup()
        got = self.fill("example-org/repo.git")
        self.assertEqual((got["username"], got["password"]), ("work-account", "tok-work-account"))
        # Owner keys are case-insensitive, like GitHub owners.
        self.assertEqual(self.fill("Example-Org/repo.git")["password"], "tok-work-account")
        # Git applies the github.com chain to these spellings too.
        for host in ("GitHub.com", "github.com:443"):
            self.assertEqual(self.fill("example-org/repo.git", host=host)["password"],
                             "tok-work-account", host)
        # Unmapped owner: gh's helper answers with the active account.
        self.assertEqual(self.fill("someone/repo.git")["password"], "tok-personal")
        # The empty reset keeps the system keychain helper out, for get and approve.
        r = self.git("credential", "approve", input="protocol=https\nhost=github.com\n"
                     "path=example-org/repo.git\nusername=work-account\npassword=tok-work-account\n\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.t / "keychain.log").exists())
        # A mapped owner whose account is logged out stops git; no other account is tried.
        self.env["FAKE_GH_ACCOUNTS"] = "personal"
        r = self.fill("example-org/repo.git", rc=128)
        self.assertIn("told us to quit", r.stderr)
        self.assertIn("owner example-org maps to gh account work-account", r.stderr)
        self.assertIn("gh auth login -h github.com", r.stderr)
        self.assertNotIn("tok-", r.stdout + r.stderr)

    def test_helper_falls_through_only_when_unmapped(self):
        self.setup()
        # A repository's own config cannot map an owner.
        local = self.repo("l", "https://github.com/someone/l.git")
        self.git("-C", local, "config", "ghaccount.someone", "work-account")
        for stdin in ("protocol=https\nhost=github.com\npath=someone/r.git\n\n",
                      "protocol=https\nhost=example.com\npath=example-org/r.git\n\n",
                      "protocol=https\nhost=github.com\npath=1digit/r.git\n\n",
                      "protocol=https\nhost=github.com\n\n"):
            r = self.run_(self.installed, "get", input=stdin, cwd=local)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""), stdin)
        r = self.run_(self.installed, "store", input="protocol=https\nhost=github.com\npassword=x\n\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_setup_installs_replaces_chain_and_is_idempotent(self):
        # What `gh auth setup-git` leaves behind.
        self.gitconfig.write_text('[credential "https://github.com"]\n\thelper =\n'
                                  '\thelper = !/opt/gh/2.0/bin/gh auth git-credential\n')
        self.setup("--ssh-alias", "github-personal")
        self.assertEqual(self.installed.read_bytes(), HELPER.read_bytes())
        self.assertEqual(self.installed.stat().st_mode & 0o777, 0o755)
        first = self.gitconfig.read_bytes()
        mtime = self.installed.stat().st_mtime_ns
        r = self.setup("--ssh-alias", "github-personal")
        self.assertIn("nothing changed", r.stdout)
        self.assertEqual(self.gitconfig.read_bytes(), first)
        self.assertEqual(self.installed.stat().st_mtime_ns, mtime)
        chain = self.git("config", "--get-all", KEY).stdout.splitlines()
        self.assertEqual(chain, ["", str(self.installed), f"!{self.gh} auth git-credential"])
        rewrites = self.git("config", "--get-all", "url.https://github.com/.insteadOf").stdout.split()
        self.assertEqual(sorted(rewrites), sorted(["git@github.com:", "ssh://git@github.com/",
                                                   "git@github-personal:", "ssh://git@github-personal/"]))
        self.assertEqual(self.git("config", "ghaccount.example-org").stdout.strip(), "work-account")
        self.assertEqual((self.t / "proto").read_text().strip(), "https")
        repo = self.repo("a", "git@github-personal:example-org/a.git")
        r = self.check("--ssh-alias", "github-personal", repo)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("FAIL", r.stdout)
        # A helper after gh's would receive every approved token. One added
        # by includeIf only applies inside matching repos: the doctor checks
        # from inside each repo.
        extra = self.t / "extra.gitconfig"
        extra.write_text("[credential]\n\thelper = osxkeychain\n")
        with self.gitconfig.open("a") as f:
            f.write(f'[includeIf "gitdir:{self.t}/code/"]\n\tpath = {extra}\n')
        r = self.check(repo)
        self.assert_fail_with_fix(r.stdout, f"{repo}: credential.helper in {extra} runs after gh's helper")
        # A mixed-case subsection still applies to github.com: setup refuses
        # to say "configured".
        with self.gitconfig.open("a") as f:
            f.write('[credential "https://GitHub.com"]\n\thelper = osxkeychain\n')
        r = self.setup(rc=1)
        self.assertIn("credential.https://GitHub.com.helper in", r.stderr)
        self.assertNotIn("nothing changed", r.stdout)
        self.assert_fail_with_fix(self.check().stdout, "runs after gh's helper")

    def test_file_target_for_an_included_config(self):
        target = self.t / "config" / "groundwork" / "github.gitconfig"
        r = self.setup("--file", target, rc=1)
        self.assertIn("is not included", r.stderr)
        self.assertFalse(self.gitconfig.exists())
        self.assert_fail_with_fix(self.check("--file", target).stdout, "is not included")
        self.git("config", "--global", "include.path", "~/config/groundwork/github.gitconfig")
        self.assertIn("nothing changed", self.setup("--file", target).stdout)
        self.assertEqual(self.fill("example-org/r.git")["password"], "tok-work-account")
        r = self.check("--file", target)
        self.assertEqual(r.returncode, 0, r.stdout)
        base = self.gitconfig.read_text()
        # A later map value in the global file wins for the helper.
        self.gitconfig.write_text(base + "[ghaccount]\n\texample-org = personal\n")
        self.assertEqual(self.fill("example-org/r.git")["password"], "tok-personal")
        r = self.setup("--file", target, rc=1)
        self.assertIn(f"--file {self.gitconfig} --unset-all ghaccount.example-org", r.stderr)
        self.assert_fail_with_fix(self.check("--file", target).stdout, "ghaccount.example-org has more")
        # A leftover chain later in the global file resets the included one.
        self.gitconfig.write_text(base + '[credential "https://github.com"]\n\thelper =\n'
                                  f'\thelper = !{self.gh} auth git-credential\n')
        for out in (self.setup("--file", target, rc=1).stderr, self.check("--file", target).stdout):
            self.assertIn(f"credential.https://github.com.helper in {self.gitconfig} resets", out)
            self.assertNotIn("not included", out)

    def test_setup_rejects_bad_input(self):
        for args in (["--map", "1x=y"], ["--map", "a=b;c"], ["--helper", "/p/a b"],
                     ["--helper", "rel/helper.sh"], ["--ssh-alias", "a b"], ["--file", "rel/x"]):
            r = self.run_(SETUP, *args)
            self.assertEqual(r.returncode, 64, args)
            self.assertFalse(self.gitconfig.exists(), args)
            self.assertFalse(self.installed.exists(), args)

    def test_doctor_failures_each_have_a_fix(self):
        repo = self.repo("w", "git@github-work:example-org/w.git")
        self.repo("u", "https://github.com/unmapped-owner/u.git")
        self.repo("d", "https://github.com/1digit/d.git")
        push = self.repo("p", "https://github.com/example-org/p.git")
        self.git("-C", push, "config", "url.git@github.com:.pushInsteadOf", "https://github.com/")
        self.git("config", "--global", "ghaccount.example-org", "gone-account")
        before = self.gitconfig.read_bytes()
        r = self.check("--ssh-alias", "github-work", "--root", self.t / "code")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.gitconfig.read_bytes(), before)  # read-only
        self.assertFalse((self.t / "proto").exists())
        for needle in ("useHttpPath", "is missing or out of order", "git_protocol",
                       "maps to gone-account", "owner unmapped-owner", "remote origin uses SSH",
                       "ssh alias github-work", f"pushes over SSH because url.git@github.com:.pushinsteadof in {push}/.git/config"):
            self.assert_fail_with_fix(r.stdout, needle)
        self.assertIn("insteadOf git@github-work:", r.stdout)
        self.assertIn("note: owner 1digit", r.stdout)
        self.assertNotIn("FAIL: owner 1digit", r.stdout)
        self.assertNotIn("tok-", r.stdout + r.stderr)
        # Installed helper removed, then a misordered chain; with one logged-in
        # account an unmapped owner is only a note.
        self.git("config", "--global", "--unset", "ghaccount.example-org")
        self.setup()
        self.installed.unlink()
        self.assert_fail_with_fix(self.check().stdout, "owner helper is missing")
        self.git("config", "--global", "--unset-all", KEY)
        for v in (str(self.installed), "", f"!{self.gh} auth git-credential"):
            self.git("config", "--global", "--add", KEY, v)
        self.env["FAKE_GH_ACCOUNTS"] = "work-account"
        r = self.check(repo, self.t / "code" / "u")
        self.assert_fail_with_fix(r.stdout, "missing or out of order")
        self.assertIn("note: owner unmapped-owner", r.stdout)
        self.assertNotIn("FAIL: owner", r.stdout)


if __name__ == "__main__":
    unittest.main()
