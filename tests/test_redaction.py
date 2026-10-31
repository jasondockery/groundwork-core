#!/usr/bin/env python3
"""Run the shared credential redaction vectors against the reference helper."""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "redaction"
HELPER = DIR / "redact-url.sh"
CHECK = DIR / "check-redact-url.sh"
VECTORS = DIR / "redact-url-vectors.tsv"
DOC = ROOT / "docs" / "credential-redaction.md"
TOKEN_RE = re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}")


class RedactionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = self.tmp.name
        self.env = {"PATH": os.environ["PATH"], "HOME": t,
                    "XDG_CONFIG_HOME": os.path.join(t, ".config"),
                    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

    def run_cmd(self, *args, env=None):
        return subprocess.run([str(a) for a in args], env=env or self.env,
                              capture_output=True, text=True)

    def vectors(self):
        for line in VECTORS.read_text().splitlines():
            if line and not line.startswith("#"):
                yield line.split("\t")

    def test_reference_passes_every_vector(self):
        r = self.run_cmd(CHECK, HELPER)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(" 0 failed", r.stdout)

    def test_wrong_helper_fails(self):
        r = self.run_cmd(CHECK, "echo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL", r.stdout)

    def test_authority_only_cut_fails(self):
        script = Path(self.tmp.name) / "authority-only.sh"
        script.write_text('u=$1; s=${u%%://*}://; r=${u#*://}; a=${r%%/*}; p=${r#"$a"}\n'
                          '[[ $a == *@* ]] && a="***@${a##*@}"; printf "%s%s\\n" "$s" "$a${p%%[?#]*}"\n')
        r = self.run_cmd(CHECK, "bash", script)
        self.assertEqual(r.returncode, 1)
        self.assertIn("slash in password", r.stdout)

    def test_usage_and_bad_vectors(self):
        self.assertEqual(self.run_cmd(CHECK).returncode, 2)
        bad = Path(self.tmp.name) / "bad.tsv"
        bad.write_text("https://example.com/x\n")
        env = dict(self.env, REDACT_URL_VECTORS=str(bad))
        self.assertEqual(self.run_cmd(CHECK, HELPER, env=env).returncode, 2)
        env["REDACT_URL_VECTORS"] = str(bad) + ".missing"
        self.assertEqual(self.run_cmd(CHECK, HELPER, env=env).returncode, 2)

    def test_vectors_hold_no_literal_token(self):
        self.assertIsNone(TOKEN_RE.search(VECTORS.read_text()))

    def test_every_vector_has_three_columns(self):
        rows = list(self.vectors())
        self.assertGreater(len(rows), 20)
        for row in rows:
            self.assertEqual(len(row), 3, row)

    def test_limit_vectors_match_doc(self):
        doc = DOC.read_text()
        limits = [row for row in self.vectors() if row[2].startswith("limit:")]
        self.assertGreaterEqual(len(limits), 3)
        for inp, out, _ in limits:
            self.assertIn(f"`{inp}`", doc)
            self.assertIn(f"`{out}`", doc)

    def test_sourced_helper(self):
        r = self.run_cmd("bash", "-c", f'source "{HELPER}"; redact_url "https://u:p@h/o/r?q"')
        self.assertEqual(r.stdout, "https://***@h/o/r\n")
        self.assertEqual(self.run_cmd(HELPER).returncode, 2)


if __name__ == "__main__":
    unittest.main()
