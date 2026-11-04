#!/usr/bin/env python3
"""Behavior checks for git-credential/: real git and the real scripts, with a
temp HOME, temp global git config, and a fake gh on PATH."""

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


class GitCredentialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        (t / "bin").mkdir()
        gh = t / "bin" / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.gitconfig = t / "gitconfig"
        self.env = {
            "PATH": f"{t / 'bin'}:{os.environ['PATH']}", "HOME": str(t),
            "XDG_CONFIG_HOME": str(t / "config"), "GNUPGHOME": str(t / "gnupg"),
            "TMPDIR": str(t), "GIT_CONFIG_GLOBAL": str(self.gitconfig),
            "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
            "FAKE_GH_STATE": str(t), "FAKE_GH_ACCOUNTS": "personal work-account",
        }

    def run_(self, *cmd, input=None, cwd=None):
        return subprocess.run([str(c) for c in cmd], env=self.env, input=input, cwd=cwd,
                              capture_output=True, text=True, timeout=30)

    def git(self, *a, **kw):
        return self.run_("git", *a, **kw)

    def setup(self, *extra):
        r = self.run_(SETUP, "--map", "example-org=work-account", *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def fill(self, path):
        r = self.git("credential", "fill",
                     input=f"protocol=https\nhost=github.com\npath={path}\n\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        return dict(line.split("=", 1) for line in r.stdout.splitlines())

    def repo(self, name, url):
        r = Path(self.tmp.name) / "code" / name
        self.git("init", "-q", r)
        self.git("-C", r, "remote", "add", "origin", url)
        return r

    def check(self, *args):
        return self.run_(CHECK, *args)

    def test_routes_by_owner_through_git(self):
        self.setup()
        got = self.fill("example-org/repo.git")
        self.assertEqual((got["username"], got["password"]), ("work-account", "tok-work-account"))
        # Owner keys are case-insensitive, like GitHub owners.
        self.assertEqual(self.fill("Example-Org/repo.git")["password"], "tok-work-account")
        # Unmapped owner: gh's helper answers with the active account.
        self.assertEqual(self.fill("someone/repo.git")["password"], "tok-personal")

    def test_helper_prints_nothing_when_it_does_not_route(self):
        self.setup()
        for stdin in ("protocol=https\nhost=github.com\npath=someone/r.git\n\n",
                      "protocol=https\nhost=example.com\npath=example-org/r.git\n\n",
                      "protocol=https\nhost=github.com\n\n"):
            r = self.run_(HELPER, "get", input=stdin)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""), stdin)
        # gh fails for the account (logged out): nothing, so gh's helper answers.
        self.env["FAKE_GH_ACCOUNTS"] = "personal"
        r = self.run_(HELPER, "get", input="protocol=https\nhost=github.com\npath=example-org/r\n\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = self.run_(HELPER, "store", input="protocol=https\nhost=github.com\npassword=x\n\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_setup_replaces_chain_in_order_and_is_idempotent(self):
        # What `gh auth setup-git` and a macOS git leave behind.
        self.gitconfig.write_text('[credential]\n\thelper = osxkeychain\n'
                                  '[credential "https://github.com"]\n\thelper =\n'
                                  '\thelper = !/opt/gh/2.0/bin/gh auth git-credential\n')
        self.setup("--ssh-alias", "github-personal")
        first = self.gitconfig.read_bytes()
        r = self.setup("--ssh-alias", "github-personal")
        self.assertIn("nothing changed", r.stdout)
        self.assertEqual(self.gitconfig.read_bytes(), first)
        gh = Path(self.tmp.name) / "bin" / "gh"
        chain = self.git("config", "--get-all", KEY).stdout.splitlines()
        self.assertEqual(chain, ["", str(HELPER), f"!{gh} auth git-credential"])
        rewrites = self.git("config", "--get-all", "url.https://github.com/.insteadOf").stdout.split()
        self.assertEqual(sorted(rewrites), sorted(["git@github.com:", "ssh://git@github.com/",
                                                   "git@github-personal:", "ssh://git@github-personal/"]))
        self.assertEqual(self.git("config", "ghaccount.example-org").stdout.strip(), "work-account")
        self.assertEqual((Path(self.tmp.name) / "proto").read_text().strip(), "https")
        # Configured state passes the doctor, including an aliased SSH remote.
        r = self.check(self.repo("a", "git@github-personal:example-org/a.git"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("FAIL", r.stdout)

    def assert_fail_with_fix(self, out, needle):
        lines = out.splitlines()
        hits = [i for i, l in enumerate(lines) if l.startswith("FAIL:") and needle in l]
        self.assertTrue(hits, f"no FAIL with {needle!r} in:\n{out}")
        for i in hits:
            self.assertTrue(i + 1 < len(lines) and lines[i + 1].startswith("  fix: "), out)

    def test_doctor_failures_each_have_a_fix(self):
        repo = self.repo("w", "git@github-work:example-org/w.git")
        self.repo("u", "https://github.com/unmapped-owner/u.git")
        self.git("config", "--global", "ghaccount.example-org", "gone-account")
        before = self.gitconfig.read_bytes()
        r = self.check("--root", Path(self.tmp.name) / "code")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.gitconfig.read_bytes(), before)  # read-only
        self.assertFalse((Path(self.tmp.name) / "proto").exists())
        for needle in ("useHttpPath", "chain is missing", "git_protocol",
                       "maps to gone-account", "owner unmapped-owner", "remote origin uses SSH"):
            self.assert_fail_with_fix(r.stdout, needle)
        self.assertIn("insteadOf git@github-work:", r.stdout)
        self.assertNotIn("tok-", r.stdout + r.stderr)
        # Misordered chain, and one logged-in account makes an unmapped owner a note.
        self.setup()
        self.git("config", "--global", "--unset-all", KEY)
        for v in (str(HELPER), "", f"!{Path(self.tmp.name) / 'bin' / 'gh'} auth git-credential"):
            self.git("config", "--global", "--add", KEY, v)
        self.env["FAKE_GH_ACCOUNTS"] = "work-account"
        r = self.check(repo, Path(self.tmp.name) / "code" / "u")
        self.assert_fail_with_fix(r.stdout, "chain is missing or out of order")
        self.assertIn("note: owner unmapped-owner", r.stdout)
        self.assertNotIn("FAIL: owner", r.stdout)


if __name__ == "__main__":
    unittest.main()
