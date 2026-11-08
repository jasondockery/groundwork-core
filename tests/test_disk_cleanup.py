#!/usr/bin/env python3
"""Hostile fixtures for disk-cleanup/disk-cleanup.sh.

Every tool that could change anything (docker, npm, and the rest) is a logging
fake on a closed PATH, in a synthetic HOME. "Nothing changed" is proved by the
command log and the surviving files. Prompts run on a real pseudo-terminal.
"""

import errno
import os
import pty
import select
import shutil
import signal
import stat
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "disk-cleanup"
SCRIPT = DIR / "disk-cleanup.sh"
VECTORS = DIR / "test-lane-vectors.tsv"
DOC = ROOT / "docs" / "disk-cleanup.md"

SYSTEM_TOOLS = (
    "awk bash cat cksum cut date df du find grep head mkdir mktemp nice ps "
    "readlink rm sed sleep sort tail touch tr wc xargs"
).split()

FAKE_DOCKER = r"""#!/bin/bash
printf 'docker %s\n' "$*" >>"$FAKE_LOG"
state="$FAKE_STATE/docker"
case "$1 ${2:-}" in
  "context inspect") cat "$state/host" ;;
  "info --format") [[ ! -f "$state/down" ]] || exit 1; echo 29.0.0 ;;
  "buildx version") [[ ! -f "$state/no-buildx" ]] || exit 1; echo github.com/docker/buildx v0.38 ;;
  "buildx inspect") printf 'Name:          default\nDriver:        %s\n' "$(cat "$state/driver")" ;;
  "system df") cat "$state/df" ;;
  "image ls") cat "$state/images" ;;
  "ps --all")
    cat "$state/containers"
    # Something starts between the question and the answer.
    [[ ! -f "$state/change-after-first-list" ]] || echo "new-container" >>"$state/containers"
    ;;
  "builder prune") printf 'ID\tRECLAIMABLE\tSIZE\nabc\ttrue\t1GB\nTotal:\t1.2GB\n' ;;
  "image prune") printf 'Deleted Images:\nTotal reclaimed space: 5GB\n' ;;
  *) echo "fake docker: unexpected: $*" >&2; exit 99 ;;
esac
"""

FAKE_NPM = r"""#!/bin/bash
printf 'npm %s\n' "$*" >>"$FAKE_LOG"
case "$1 ${2:-}" in
  "config get") cat "$FAKE_STATE/npm-cache-path" ;;
  "cache clean") rm -rf "$HOME/.npm/_cacache" ;;
  *) echo "fake npm: unexpected: $*" >&2; exit 99 ;;
esac
"""

STEPS = """\
dc_adapter_steps() {
  dc_step auto tool npm-cache "npm cache"
  dc_step auto tool docker-build-cache "Docker build cache"
  dc_step ask tool docker-images "Unused Docker images"
  dc_step ask any trash "Trash"
}
DC_TRASH_DIR="$HOME/.Trash"
DC_LOW_SPACE_HINT="Try the hint."
"""

MUTATING = ("prune", "cache clean", "rm -rf", "volume")


class Fixture(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        self.state = self.root / "state"
        (self.state / "docker").mkdir(parents=True)
        self.log = self.root / "log"
        self.log.touch()
        for tool in SYSTEM_TOOLS:
            found = shutil.which(tool, path="/bin:/usr/bin:/usr/sbin:/sbin")
            self.assertIsNotNone(found, tool)
            (self.bin / tool).symlink_to(found)
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.bin),
            "TMPDIR": str(self.tmp),
            "FAKE_LOG": str(self.log),
            "FAKE_STATE": str(self.state),
            "GROUNDWORK_DISK_NPM_CLEAN_MIB": "1",
        }
        self.write_tool("docker", FAKE_DOCKER)
        self.write_tool("npm", FAKE_NPM)
        self.docker_state(
            host="unix:///run/docker.sock\n",
            driver="docker\n",
            df=(
                "Images|12|2|9GB|5GB (55%)\n"
                "Containers|2|2|1MB|0B (0%)\n"
                "Local Volumes|3|1|40GB|30GB (75%)\n"
                "Build Cache|40|0|7GB|7GB\n"
            ),
            images="sha256:aaa\nsha256:bbb\n",
            containers="c1\n",
        )
        (self.state / "npm-cache-path").write_text(f"{self.home}/.npm\n")
        self.fill(self.home / ".npm/_cacache/blob", 2048)
        self.fill(self.home / ".Trash/old-report.pdf", 16)
        self.steps = self.root / "steps.sh"
        self.steps.write_text(STEPS)
        # The lane scan must see this fixture, never the host's real test runs.
        self.fake_ps("  1 /sbin/init\n")

    def fake_ps(self, listing, fail=False):
        real = shutil.which("ps", path="/bin:/usr/bin")
        (self.state / "ps-listing").write_text(listing)
        body = '#!/bin/bash\n'
        # Only the lane scan uses command=; the bounded runner keeps the real ps.
        body += 'for arg in "$@"; do\n  if [[ "$arg" == *command=* ]]; then\n'
        body += '    exit 1\n' if fail else '    cat "$FAKE_STATE/ps-listing"; exit 0\n'
        body += '  fi\ndone\n'
        body += f'exec {real} "$@"\n'
        self.write_tool("ps", body)

    def write_tool(self, name, body):
        path = self.bin / name
        if path.exists() or path.is_symlink():
            path.unlink()
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def docker_state(self, **files):
        for name, text in files.items():
            (self.state / "docker" / name).write_text(text)

    def fill(self, path, kib):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * (kib * 1024))

    def commands(self):
        return self.log.read_text().splitlines()

    def assert_no_mutation(self):
        for line in self.commands():
            for word in MUTATING:
                self.assertNotIn(word, line)
        self.assertTrue((self.home / ".npm/_cacache/blob").exists())
        self.assertTrue((self.home / ".Trash/old-report.pdf").exists())

    def run_script(self, *args, env=None, stdin=subprocess.DEVNULL, timeout=60):
        merged = dict(self.env, **(env or {}))
        return subprocess.run(
            [str(SCRIPT), *args],
            env=merged,
            stdin=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def run_steps(self, *args, env=None):
        return self.run_script("run", "--steps", str(self.steps), *args, env=env)

    def run_pty(self, *args, answers=(), env=None, timeout=60, interrupt_on=None, interrupt_when=None, before_answer=None):
        """Drive the prompts on a real terminal. Returns (exit status, output)."""
        merged = dict(self.env, **(env or {}))
        pid, master = pty.fork()
        if pid == 0:
            os.execve(str(SCRIPT), [str(SCRIPT), "run", "--steps", str(self.steps), *args], merged)
        output = b""
        pending = list(answers)
        answered = 0
        interrupted = False
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not chunk:
                        break
                    output += chunk
                if pending and output.count(b"[y/N] ") + output.count(b"Please answer") > answered:
                    if before_answer and answered in before_answer:
                        before_answer[answered]()
                    answered += 1
                    os.write(master, pending.pop(0))
                due = interrupt_on and interrupt_on.encode() in output
                if not due and interrupt_when is not None:
                    due = interrupt_when()
                if due and not interrupted:
                    interrupted = True
                    os.write(master, b"\x03")
            else:
                os.kill(pid, signal.SIGKILL)
                self.fail(f"timed out; output so far: {output!r}")
        finally:
            os.close(master)
        _, status = os.waitpid(pid, 0)
        code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 128 + os.WTERMSIG(status)
        return code, output.decode(errors="replace").replace("\r\n", "\n")


class UsageTest(Fixture):
    def test_help_runs_no_tool_and_exits_zero(self):
        for args in (("--help",), ("-h",), ("run", "--help")):
            result = self.run_script(*args)
            self.assertEqual(result.returncode, 0, args)
            self.assertIn("--dry-run", result.stdout)
        self.assertEqual(self.commands(), [])

    def test_bad_usage_exits_64_and_changes_nothing(self):
        for args in (
            (),
            ("frobnicate",),
            ("run",),
            ("run", "--steps"),
            ("run", "--steps", str(self.steps), "--yes"),
            ("run", "--steps", str(self.steps), "extra"),
            ("run", "--steps", str(self.steps), "--dry-run", "--report-only"),
            ("never-touch", "extra"),
            ("check-path",),
            ("check-command", "docker"),
            ("check-command", "--"),
            ("test-lanes", "extra"),
        ):
            result = self.run_script(*args)
            self.assertEqual(result.returncode, 64, args)
        self.assertEqual(self.commands(), [])
        self.assert_no_mutation()

    def test_bad_threshold_override_exits_64(self):
        for value in ("0", "abc", "-1", "9999999999"):
            result = self.run_steps(env={"GROUNDWORK_DISK_NPM_CLEAN_MIB": value})
            self.assertEqual(result.returncode, 64, value)
        self.assertEqual(self.commands(), [])

    def test_invalid_steps_file_changes_nothing(self):
        cases = {
            "missing adapter function": "true\n",
            "syntax error": "dc_adapter_steps() {\n",
            "bad level": 'dc_adapter_steps() { dc_step always tool npm-cache "x"; }\n',
            "bad lane": 'dc_adapter_steps() { dc_step auto sometimes npm-cache "x"; }\n',
            "bad id": 'dc_adapter_steps() { dc_step auto tool "npm cache" "x"; }\n',
            "no functions": 'dc_adapter_steps() { dc_step auto tool nothing-here "x"; }\n',
        }
        for name, body in cases.items():
            self.steps.write_text(body)
            result = self.run_steps()
            self.assertEqual(result.returncode, 1, name)
            self.assertIn("Nothing was changed", result.stderr, name)
        self.steps.unlink()
        self.assertEqual(self.run_steps().returncode, 1)
        self.assertEqual(self.commands(), [])
        self.assert_no_mutation()


class NeverTouchTest(Fixture):
    def setUp(self):
        super().setUp()
        (self.home / ".ssh").mkdir()
        (self.home / "project/.git").mkdir(parents=True)
        (self.home / "project/src").mkdir()
        (self.home / "safe").mkdir()
        (self.home / "link-to-ssh").symlink_to(self.home / ".ssh")

    def protected(self, path):
        return self.run_script("check-path", str(path)).returncode == 1

    def test_named_paths_their_contents_and_their_parents(self):
        for path in (
            "~/.t3", "~/.t3/state/db", "~/.aws", "~/.aws/credentials", "~/.ssh", "~/.ssh/id_ed25519",
            "~/.config/gh", "~/.config/gh/hosts.yml", "~/.config", "~/code", "~/code/app",
            "~/.colima", "~/.lima/default/diffdisk", "/var/lib/docker/volumes/db/_data",
            "~", "/",
        ):
            self.assertTrue(self.protected(path), path)

    def test_git_pnpm_docker_and_checkouts_anywhere(self):
        for path in (
            self.home / "project", self.home / "project/src", self.home / "project/src/new-file",
            self.home / "project/.git/config", self.home / "elsewhere/.git/objects",
            self.home / "Library/pnpm/store/v11", self.home / ".local/share/pnpm/store",
            self.home / "work/.pnpm-store/v3", self.home / "x/docker/volumes/db",
        ):
            self.assertTrue(self.protected(path), path)

    def test_a_symlink_cannot_hide_a_protected_path(self):
        self.assertTrue(self.protected(self.home / "link-to-ssh"))
        self.assertTrue(self.protected(self.home / "link-to-ssh/id"))
        self.assertTrue(self.protected(self.home / "safe/../.ssh"))
        self.assertTrue(self.protected(self.home / "nothing-here/../.ssh"))

    def test_ordinary_paths_pass(self):
        for path in (self.home / "safe", self.home / "safe/x", self.home / ".npm", self.home / ".Trash/x", self.tmp):
            self.assertFalse(self.protected(path), path)

    def test_a_folder_holding_home_is_protected(self):
        self.assertTrue(self.protected(self.root))

    def test_a_dotfiles_repo_at_home_does_not_protect_everything(self):
        (self.home / ".git").mkdir()
        self.assertFalse(self.protected(self.home / "safe/x"))
        self.assertTrue(self.protected(self.home / ".git/config"))

    def test_commands(self):
        refused = (
            ["docker", "volume", "prune"],
            ["docker", "volume", "rm", "db"],
            ["docker", "system", "prune", "--volumes"],
            ["docker", "system", "prune", "-a"],
            ["docker", "image", "prune", "--volumes"],
            ["docker", "rmi", "x"],
            ["pnpm", "store", "path"],
            ["pnpm", "store", "prune", "--force"],
            ["rm", "-rf", "~/.ssh"],
            ["rm", "-rf", ".ssh"],
            ["rm", "-rf", f"{self.home}/.aws"],
            ["rm", "-rf", f"{self.home}/project/src"],
            ["find", f"{self.home}/code", "-delete"],
            ["unknown-tool", "x"],
            ["/usr/bin/docker", "builder", "prune"],
            ["brew", f"--path={self.home}/.ssh"],
            ["npm", "cache", "clean", "--force", "--cache=.ssh"],
            ["npm", "cache", "clean", "--force", "--cache=code"],
            ["npm", "cache", "clean", "--force", "--cache", ".aws"],
            ["paccache", "-r", "-c", ".ssh"],
            ["paccache", f"-c{self.home}/.ssh"],
            ["docker", "builder", "prune", "--volumes=true"],
            ["bash", "-c", "rm -rf ~/.ssh"],
            ["env", "rm", "-rf", "x"],
            ["nice", "rm", "-rf", ".ssh"],
            ["nice", "-n", "10", "rm", "-rf", ".ssh"],
            ["timeout", "60", "docker", "volume", "prune", "--force"],
            ["command", "rm", "-rf", ".ssh"],
            ["busybox", "rm", "-rf", ".ssh"],
            ["python3", "-c", "x"],
            ["sudo", "paccache", "-r"],
            ["sudo", "-n", "rm", "-rf", "/"],
            ["sudo", "-n", "docker", "volume", "prune"],
            ["sudo", "-n", "-E", "docker", "volume", "prune"],
            ["sudo", "-n", "--", "docker", "volume", "prune"],
            ["sudo", "-n", "-u", "root", "rm", "-rf", ".ssh"],
            ["sudo", "-n", "env", "rm", "-rf", "x"],
            ["/usr/bin/sudo", "-n", "paccache", "-ruk1"],
            ["sudo"],
            ["sudo", "-n"],
        )
        for argv in refused:
            result = self.run_script("check-command", "--", *argv)
            self.assertEqual(result.returncode, 1, argv)
            self.assertIn("refused", result.stdout, argv)
        allowed = (
            ["docker", "builder", "prune", "--all", "--force", "--filter", "until=168h"],
            ["docker", "image", "prune", "--all", "--force"],
            ["pnpm", "store", "prune"],
            ["npm", "cache", "clean", "--force"],
            ["sudo", "-n", "paccache", "-ruk1"],
            ["sudo", "-n", "apt-get", "clean"],
            ["rm", "-f", f"{self.home}/.npm/old"],
            ["xcrun", "simctl", "delete", "unavailable"],
            ["xcrun", "simctl", "runtime", "delete", "ABC-123"],
            ["yay", "-Sc", "--aur", "--noconfirm"],
        )
        for argv in allowed:
            self.assertEqual(self.run_script("check-command", "--", *argv).returncode, 0, argv)

    def test_a_refusal_says_why(self):
        for argv, reason in (
            (["nice", "rm", "-rf", ".ssh"], "could run anything"),
            (["env", "rm", "-rf", "x"], "could run anything"),
            (["sudo", "-n", "env", "rm"], "could run anything"),
            (["sudo", "paccache", "-r"], "sudo -n COMMAND"),
            (["sudo", "-n", "-E", "paccache", "-r"], "sudo -n COMMAND"),
            (["sudo", "-n", "--", "paccache", "-r"], "sudo -n COMMAND"),
            (["unknown-tool"], "not a known cleanup tool"),
            (["/usr/bin/docker", "image", "prune"], "without a path"),
        ):
            self.assertIn(reason, self.run_script("check-command", "--", *argv).stdout, argv)

    def test_a_folder_named_like_a_subcommand_does_not_stop_a_command(self):
        (self.home / "builder/.git").mkdir(parents=True)
        (self.home / "cache/.git").mkdir(parents=True)
        self.assertEqual(self.run_script("check-command", "--", "docker", "builder", "prune").returncode, 0)
        self.assertEqual(self.run_script("check-command", "--", "npm", "cache", "clean", "--force").returncode, 0)
        # An rm argument is always a path.
        self.assertEqual(self.run_script("check-command", "--", "rm", "-rf", "cache").returncode, 1)

    def test_a_steps_file_can_name_a_tool_but_never_a_wrapper(self):
        for wrapper in ("env", "nice", "timeout", "bash", "python3", "busybox", "sudo"):
            self.steps.write_text(f'dc_adapter_steps() {{ dc_allow_tool {wrapper}; }}\n')
            result = self.run_steps()
            self.assertEqual(result.returncode, 1, wrapper)
            self.assertIn("could run anything", result.stderr, wrapper)
        self.steps.write_text('dc_adapter_steps() { dc_allow_tool "bad name"; }\n')
        self.assertEqual(self.run_steps().returncode, 1)
        self.assertEqual(self.commands(), [])

    def test_a_pnpm_store_anywhere_is_recognized_by_its_shape(self):
        (self.home / "custom-store/v10/files").mkdir(parents=True)
        self.assertTrue(self.protected(self.home / "custom-store/v10"))
        self.assertTrue(self.protected(self.home / "custom-store/v10/files/00/abc"))
        (self.home / "release/v10").mkdir(parents=True)
        self.assertFalse(self.protected(self.home / "release/v10/notes"))

    def pnpm_tool(self, body):
        self.write_tool("pnpm", '#!/bin/bash\nprintf "pnpm %s net=%s offline=%s\\n" "$*" "${COREPACK_ENABLE_NETWORK:-}" "${MISE_OFFLINE:-}" >>"$FAKE_LOG"\n' + body)

    def test_pnpms_own_store_is_protected_and_the_query_cannot_download(self):
        store = self.home / "elsewhere-store"
        self.pnpm_tool(f'echo {store}\n')
        (self.state / "npm-cache-path").write_text(f"{store}/npm\n")
        result = self.run_steps()
        self.assertIn("pnpm store path net=0 offline=1", self.commands())
        self.assertIn("in the pnpm store", result.stdout)
        self.assertNotIn("npm cache clean --force", self.commands())

    def test_a_failed_pnpm_query_is_said_and_never_called_clean(self):
        for body in ("exit 1\n", "echo not-absolute\n", "printf '/x\\033y\\n'\n"):
            self.pnpm_tool(body)
            result = self.run_steps("--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("pnpm's store location could not be read", result.stdout, body)
        self.assertNotIn("\033", result.stdout)

    def test_a_hostile_step_is_refused_before_it_runs(self):
        self.write_tool("logged", '#!/bin/bash\nprintf "logged %s\\n" "$*" >>"$FAKE_LOG"\n')
        self.steps.write_text(textwrap.dedent("""\
            dc_adapter_steps() {
              dc_allow_tool logged
              dc_step auto any wipe-volumes "Volumes"
              dc_step auto any wipe-ssh "SSH"
              dc_step auto any harmless "Harmless"
            }
            dc_plan_wipe_volumes() { DC_PLAN_STATE=ready; DC_PLAN_TEXT=x; }
            dc_act_wipe_volumes() { dc_mutate v docker volume prune --force; }
            dc_plan_wipe_ssh() { DC_PLAN_STATE=ready; DC_PLAN_TEXT=x; }
            dc_act_wipe_ssh() { dc_mutate s logged "$HOME/.ssh"; }
            dc_plan_harmless() { DC_PLAN_STATE=ready; DC_PLAN_TEXT=x; }
            dc_act_harmless() { dc_mutate h logged fine; }
            """))
        result = self.run_steps()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Volumes: refused: Docker volumes are on the never-touch list", result.stdout)
        self.assertIn("SSH: refused", result.stdout)
        self.assertIn("2 failed step(s): Volumes, SSH", result.stdout)
        self.assertEqual(self.commands(), ["logged fine"])

    def test_the_list_names_every_required_item(self):
        result = self.run_script("never-touch")
        self.assertEqual(result.returncode, 0)
        for item in ("~/.t3", "~/.aws", "~/.ssh", "~/.config/gh", "Docker volumes", "pnpm store prune", ".git"):
            self.assertIn(item, result.stdout)
        doc = DOC.read_text()
        for item in ("~/.t3", "~/.aws", "~/.ssh", "~/.config/gh", "Docker volumes", "pnpm store prune", ".git"):
            self.assertIn(item, doc)


class TestLaneTest(Fixture):
    def test_vectors(self):
        rows = []
        for line in VECTORS.read_text().splitlines():
            if line and not line.startswith("#"):
                rows.append(line.split("\t", 1))
        self.assertGreater(len(rows), 20)
        result = subprocess.run(
            [str(SCRIPT), "test-lanes", "--classify"],
            env=self.env,
            input="\n".join(row[1] for row in rows) + "\n",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [row[0] for row in rows])

    def test_status_says_what_is_running(self):
        self.fake_ps("  10 /sbin/launchd\n")
        self.assertEqual(self.run_script("test-lanes").returncode, 1)
        self.fake_ps("  10 /sbin/launchd\n  20 node /w/node_modules/vitest/vitest.mjs run\n")
        result = self.run_script("test-lanes")
        self.assertEqual(result.returncode, 0)
        self.assertIn("vitest (pid 20)", result.stdout)
        self.fake_ps("", fail=True)
        self.assertEqual(self.run_script("test-lanes").returncode, 2)

    def test_tool_steps_stand_down_and_say_why(self):
        self.fake_ps("  20 node /w/node_modules/vitest/vitest.mjs run\n  30 pnpm test\n")
        result = self.run_steps()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("npm cache: skipped because test processes are running: vitest (pid 20), package manager test (pid 30)", result.stdout)
        self.assertIn("Docker build cache: skipped because", result.stdout)
        self.assertIn("Unused Docker images: not offered because", result.stdout)
        self.assertEqual([c for c in self.commands() if "docker" in c or "npm" in c], [])
        self.assertIn("Disk report", result.stdout)
        self.assert_no_mutation()

    def test_a_step_on_the_any_lane_still_runs(self):
        self.fake_ps("  20 pnpm test\n")
        self.write_tool("logged", '#!/bin/bash\nprintf "logged %s\\n" "$*" >>"$FAKE_LOG"\n')
        self.steps.write_text(textwrap.dedent("""\
            dc_adapter_steps() { dc_allow_tool logged; dc_step auto any unrelated "Unrelated"; }
            dc_plan_unrelated() { DC_PLAN_STATE=ready; DC_PLAN_TEXT=x; }
            dc_act_unrelated() { dc_mutate u logged go; }
            """))
        self.run_steps()
        self.assertEqual(self.commands(), ["logged go"])

    def test_an_unknown_process_list_counts_as_running(self):
        self.fake_ps("", fail=True)
        result = self.run_steps()
        self.assertIn("could not be listed", result.stdout)
        self.assertEqual([c for c in self.commands() if "prune" in c or "clean" in c], [])
        self.assert_no_mutation()

    def test_missing_or_empty_patterns_stand_down(self):
        self.fake_ps("  20 node /w/node_modules/vitest/vitest.mjs run\n")
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "disk-cleanup"
            shutil.copytree(DIR, copy)
            script = copy / "disk-cleanup.sh"
            patterns = copy / "test-lanes.tsv"
            for broken in ("missing", "only comments"):
                if broken == "missing":
                    patterns.unlink()
                else:
                    patterns.write_text("# nothing here\n")
                result = subprocess.run([str(script), "test-lanes"], env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, broken)
                self.assertIn("patterns could not be read", result.stdout, broken)
                result = subprocess.run([str(script), "run", "--steps", str(self.steps)], env=self.env,
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True)
                self.assertIn("patterns could not be read", result.stdout, broken)
                self.assert_no_mutation()

    def test_a_lane_that_starts_while_a_step_plans_stops_that_step(self):
        self.fake_ps("  10 /sbin/launchd\n")
        self.write_tool("docker", FAKE_DOCKER.replace(
            '"system df") cat "$state/df" ;;',
            '"system df") printf "  20 pnpm test\\n" >"$FAKE_STATE/ps-listing"; cat "$state/df" ;;',
        ))
        result = self.run_steps()
        self.assertIn("Docker build cache: skipped because test processes are running", result.stdout)
        self.assertEqual([c for c in self.commands() if "prune" in c], [])

    def test_a_lane_that_starts_later_stops_the_next_step(self):
        # The npm step starts a lane; the Docker step must see it.
        self.fake_ps("  10 /sbin/launchd\n")
        self.write_tool("npm", FAKE_NPM.replace(
            '"cache clean") rm -rf "$HOME/.npm/_cacache" ;;',
            '"cache clean") printf "  20 pnpm test\\n" >"$FAKE_STATE/ps-listing" ;;',
        ))
        result = self.run_steps()
        self.assertIn("npm cache clean --force", "\n".join(self.commands()))
        self.assertIn("Docker build cache: skipped because", result.stdout)
        self.assertEqual([c for c in self.commands() if "prune" in c], [])


class DryRunTest(Fixture):
    def test_shows_every_level_and_runs_nothing_that_changes_state(self):
        result = self.run_steps("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry run: nothing is changed", result.stdout)
        self.assertIn("Would run: npm cache clean --force", result.stdout)
        self.assertIn("Would run: docker builder prune --all --force --filter until=168h", result.stdout)
        self.assertIn("Would ask, then run: docker image prune --all --force", result.stdout)
        self.assertRegex(result.stdout, r"Trash: 1 item\(s\), \d+ KiB\.")
        self.assertIn("Disk report", result.stdout)
        self.assert_no_mutation()

    def test_does_not_prompt_on_a_terminal(self):
        code, output = self.run_pty("--dry-run")
        self.assertEqual(code, 0, output)
        self.assertNotIn("[y/N]", output)
        self.assert_no_mutation()

    def test_says_a_step_would_stand_down(self):
        self.fake_ps("  20 pnpm test\n")
        result = self.run_steps("--dry-run")
        self.assertIn("Would be skipped right now because test processes are running", result.stdout)
        self.assertIn("Would not be offered right now because", result.stdout)
        self.assert_no_mutation()

    def test_report_only_runs_no_step(self):
        result = self.run_steps("--report-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Disk report", result.stdout)
        self.assertNotIn("Automatic", result.stdout)
        self.assertEqual(self.commands(), [])


class AutomaticTest(Fixture):
    def test_runs_exact_commands_without_a_terminal_and_never_asks(self):
        result = self.run_steps()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.commands()
        self.assertIn("npm cache clean --force", commands)
        self.assertIn("docker builder prune --all --force --filter until=168h", commands)
        self.assertNotIn("docker image prune --all --force", commands)
        self.assertFalse(any("volume" in c for c in commands))
        self.assertFalse((self.home / ".npm/_cacache/blob").exists())
        self.assertTrue((self.home / ".Trash/old-report.pdf").exists())
        self.assertIn("Not asked because there is no terminal", result.stdout)
        self.assertIn("Docker build cache: cleared. Total: 1.2GB", result.stdout)
        self.assertIn("npm cache: cleared. Freed", result.stdout)

    def test_runs_from_home_so_a_project_config_is_not_consulted(self):
        self.write_tool("npm", FAKE_NPM.replace('printf \'npm %s\\n\' "$*" >>"$FAKE_LOG"',
                                                'printf "npm-from %s\\n" "$PWD" >>"$FAKE_LOG"'))
        project = self.root / "elsewhere"
        project.mkdir()
        subprocess.run([str(SCRIPT), "run", "--steps", str(self.steps)], env=self.env, cwd=project,
                       capture_output=True, stdin=subprocess.DEVNULL)
        self.assertIn(f"npm-from {self.home}", self.commands())

    def test_npm_cache_under_the_limit_stays(self):
        self.fill(self.home / ".npm/_cacache/blob", 100)
        result = self.run_steps()
        self.assertIn("npm cache: nothing to clear", result.stdout)
        self.assertNotIn("npm cache clean --force", self.commands())

    def test_npm_cache_at_a_protected_path_is_not_cleaned(self):
        (self.state / "npm-cache-path").write_text(f"{self.home}/.ssh/npm\n")
        result = self.run_steps()
        self.assertIn("protected path", result.stdout)
        self.assertNotIn("npm cache clean --force", self.commands())

    def test_a_missing_tool_is_reported_not_an_error(self):
        (self.bin / "docker").unlink()
        (self.bin / "npm").unlink()
        result = self.run_steps()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Docker is not installed", result.stdout)
        self.assertIn("npm is not installed", result.stdout)

    def test_a_failed_step_is_named_and_later_steps_still_run(self):
        self.write_tool("npm", FAKE_NPM.replace('"cache clean") rm -rf "$HOME/.npm/_cacache" ;;',
                                                '"cache clean") echo "disk says no" >&2; exit 3 ;;'))
        result = self.run_steps()
        self.assertEqual(result.returncode, 1)
        self.assertIn("npm cache: failed (exit 3)", result.stdout)
        self.assertIn("disk says no", result.stdout)
        self.assertIn("1 failed step(s): npm cache", result.stdout)
        self.assertIn("docker builder prune --all --force --filter until=168h", self.commands())
        self.assertIn("Disk report", result.stdout)

    def test_a_command_that_exits_130_is_a_failed_step_not_an_interrupted_run(self):
        for status in (125, 129, 130, 143):
            self.log.write_text("")
            self.write_tool("npm", FAKE_NPM.replace('"cache clean") rm -rf "$HOME/.npm/_cacache" ;;',
                                                    f'"cache clean") exit {status} ;;'))
            result = self.run_steps()
            self.assertEqual(result.returncode, 1, status)
            self.assertIn(f"npm cache: failed (exit {status})", result.stdout)
            self.assertIn("Disk report", result.stdout)
            self.assertIn("docker builder prune --all --force --filter until=168h", self.commands())
            self.assertNotIn("interrupted", result.stderr)

    def test_a_query_that_exits_130_does_not_end_the_run(self):
        self.write_tool("npm", '#!/bin/bash\nexit 130\n')
        result = self.run_steps()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("npm did not say where its cache is", result.stdout)
        self.assertIn("Disk report", result.stdout)

    def test_terminal_control_bytes_in_tool_output_are_removed(self):
        self.write_tool("npm", FAKE_NPM.replace('"cache clean") rm -rf "$HOME/.npm/_cacache" ;;',
                                                '"cache clean") printf "bad\\033[2Joutput\\n" >&2; exit 3 ;;'))
        result = self.run_steps()
        self.assertNotIn("\033", result.stdout)
        self.assertIn("bad[2Joutput", result.stdout)


class DockerGuardTest(Fixture):
    def assert_docker_untouched(self, result, reason):
        self.assertIn(reason, result.stdout)
        self.assertEqual([c for c in self.commands() if "prune" in c], [])

    def test_stopped_docker_is_never_started(self):
        self.docker_state(down="")
        result = self.run_steps()
        self.assert_docker_untouched(result, "Docker is not running, and cleanup does not start it")
        self.assertFalse(any(" start" in c or "colima" in c for c in self.commands()))

    def test_ambient_environment_is_refused(self):
        for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "BUILDX_BUILDER"):
            result = self.run_steps(env={name: "tcp://example.invalid:2375"})
            self.assert_docker_untouched(result, f"{name} is set")

    def test_remote_endpoint_is_refused(self):
        for host in ("tcp://example.invalid:2375\n", "ssh://me@example.invalid\n", "\n"):
            self.docker_state(host=host)
            self.assert_docker_untouched(self.run_steps(), "the Docker endpoint is not local")

    def test_remote_builder_is_refused(self):
        self.docker_state(driver="docker-container\n")
        self.assert_docker_untouched(self.run_steps(), "not the daemon's own")

    def test_no_buildx_means_the_daemon_builder(self):
        self.docker_state(**{"no-buildx": ""})
        self.run_steps()
        self.assertIn("docker builder prune --all --force --filter until=168h", self.commands())

    def test_empty_build_cache_runs_no_prune(self):
        self.docker_state(df="Images|1|1|1GB|0B (0%)\nBuild Cache|0|0|0B|0B\n")
        result = self.run_steps()
        self.assertIn("the build cache is empty", result.stdout)
        self.assertIn("every image is in use", result.stdout)
        self.assertEqual([c for c in self.commands() if "prune" in c], [])

    def test_unreadable_sizes_are_not_called_empty(self):
        self.docker_state(df="")
        result = self.run_steps()
        self.assertIn("build cache size could not be read", result.stdout)
        self.assertIn("image sizes could not be read", result.stdout)
        self.assertEqual([c for c in self.commands() if "prune" in c], [])


class PromptTest(Fixture):
    def test_yes_runs_only_the_answered_step(self):
        code, output = self.run_pty(answers=[b"y\n", b"\n"])
        self.assertEqual(code, 0, output)
        self.assertIn("docker image prune --all --force", self.commands())
        self.assertIn("Unused Docker images: cleared. Total reclaimed space: 5GB", output)
        self.assertTrue((self.home / ".Trash/old-report.pdf").exists())

    def test_the_question_shows_the_size_and_keeps_volumes(self):
        _, output = self.run_pty(answers=[b"n\n", b"n\n"])
        self.assertIn("Remove 10 unused Docker image(s), 5GB (55%)? Containers and volumes stay", output)
        self.assertIn("Empty the Trash, 1 item(s),", output)

    def test_enter_and_no_keep_everything(self):
        code, output = self.run_pty(answers=[b"\n", b"no\n"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("docker image prune --all --force", self.commands())
        self.assertTrue((self.home / ".Trash/old-report.pdf").exists())

    def test_invalid_input_explains_and_asks_again(self):
        code, output = self.run_pty(answers=[b"maybe\n", b"n\n", b"n\n"])
        self.assertEqual(code, 0, output)
        self.assertIn("Please answer y or n.", output)
        self.assertNotIn("docker image prune --all --force", self.commands())

    def test_end_of_input_runs_nothing_even_after_a_yes(self):
        code, output = self.run_pty(answers=[b"y\n", b"\x04"])
        self.assertEqual(code, 0, output)
        self.assertIn("nothing here was cleared", output)
        self.assertNotIn("docker image prune --all --force", self.commands())
        self.assertTrue((self.home / ".Trash/old-report.pdf").exists())

    def test_interrupt_stops_with_130_and_nothing_cleared(self):
        code, output = self.run_pty(answers=[b"y\n"], interrupt_on="Empty the Trash")
        self.assertEqual(code, 130, output)
        self.assertNotIn("docker image prune --all --force", self.commands())
        self.assertTrue((self.home / ".Trash/old-report.pdf").exists())

    def test_no_answer_in_time_means_no(self):
        code, output = self.run_pty(env={"GROUNDWORK_DISK_PROMPT_DEADLINE_SECONDS": "1"})
        self.assertEqual(code, 0, output)
        self.assertIn("No answer within 1s", output)
        self.assertNotIn("docker image prune --all --force", self.commands())

    def test_a_change_after_the_question_stops_the_step(self):
        self.docker_state(**{"change-after-first-list": ""})
        code, output = self.run_pty(answers=[b"y\n", b"n\n"])
        self.assertEqual(code, 0, output)
        self.assertIn("Unused Docker images: skipped because it changed after the question", output)
        self.assertNotIn("docker image prune --all --force", self.commands())

    def test_a_larger_trash_after_the_question_stops_the_step(self):
        grow = lambda: self.fill(self.home / ".Trash/old-report.pdf", 4096)
        code, output = self.run_pty(answers=[b"n\n", b"y\n"], before_answer={1: grow})
        self.assertEqual(code, 0, output)
        self.assertIn("Trash: skipped because it changed after the question", output)
        self.assertTrue((self.home / ".Trash/old-report.pdf").exists())

    def test_a_new_reclaimable_size_after_the_question_stops_the_step(self):
        change = lambda: self.docker_state(df=(
            "Images|12|2|90GB|50GB (55%)\nBuild Cache|40|0|7GB|7GB\n"))
        code, output = self.run_pty(answers=[b"y\n", b"n\n"], before_answer={0: change})
        self.assertEqual(code, 0, output)
        self.assertIn("Unused Docker images: skipped because it changed after the question", output)
        self.assertNotIn("docker image prune --all --force", self.commands())

    def test_only_y_or_yes_is_a_yes(self):
        for answer in (b"t", b"true", b"1", b"yep", b"on"):
            self.log.write_text("")
            code, output = self.run_pty(answers=[answer + b"\n", b"n\n", b"n\n"])
            self.assertEqual(code, 0, output)
            self.assertIn("Please answer y or n.", output, answer)
            self.assertNotIn("docker image prune --all --force", self.commands(), answer)
        for answer in (b"y", b"Y", b"yes", b"YES"):
            self.log.write_text("")
            code, output = self.run_pty(answers=[answer + b"\n", b"n\n"])
            self.assertEqual(code, 0, output)
            self.assertIn("docker image prune --all --force", self.commands(), answer)

    def test_nothing_ready_asks_nothing(self):
        self.docker_state(df="Images|1|1|1GB|0B (0%)\nBuild Cache|0|0|0B|0B\n")
        (self.home / ".Trash/old-report.pdf").unlink()
        code, output = self.run_pty()
        self.assertEqual(code, 0, output)
        self.assertNotIn("[y/N]", output)


class TrashTest(Fixture):
    def empty_trash(self):
        code, output = self.run_pty(answers=[b"n\n", b"y\n"])
        return code, output

    def test_empties_every_item_and_only_the_trash(self):
        self.fill(self.home / ".Trash/folder/inner", 8)
        (self.home / ".Trash/.DS_Store").write_bytes(b"x")
        self.fill(self.home / "keep/file", 4)
        code, output = self.empty_trash()
        self.assertEqual(code, 0, output)
        self.assertIn("Trash: cleared. Freed", output)
        self.assertEqual([p.name for p in (self.home / ".Trash").iterdir() if p.name != ".DS_Store"], [])
        self.assertTrue((self.home / "keep/file").exists())

    def test_a_trashed_checkout_stays(self):
        (self.home / ".Trash/some-repo/.git").mkdir(parents=True)
        (self.home / ".Trash/parent/nested/.git").mkdir(parents=True)
        code, output = self.empty_trash()
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / ".Trash/some-repo/.git").exists())
        self.assertTrue((self.home / ".Trash/parent/nested/.git").exists())
        self.assertFalse((self.home / ".Trash/old-report.pdf").exists())
        self.assertIn("Kept: some-repo", output)
        self.assertIn("Kept 2 item(s) that hold a Git checkout", output)

    def test_a_checkout_at_any_depth_stays_with_its_files(self):
        deep = self.home / ".Trash/Archive/a/b/c/d/e"
        (deep / ".git").mkdir(parents=True)
        self.fill(deep / "only-copy.txt", 4)
        code, output = self.empty_trash()
        self.assertEqual(code, 0, output)
        self.assertTrue((deep / "only-copy.txt").exists())
        self.assertIn("Kept: Archive", output)

    def test_a_folder_that_cannot_be_fully_searched_stays(self):
        self.fill(self.home / ".Trash/Sealed/file", 4)
        real = shutil.which("find", path="/bin:/usr/bin")
        self.write_tool("find", (
            '#!/bin/bash\nfor a in "$@"; do [[ "$a" != -name || "$*" != *Sealed* ]] || { echo denied >&2; exit 1; }; done\n'
            f'exec {real} "$@"\n'
        ))
        code, output = self.empty_trash()
        self.assertEqual(code, 0, output)
        self.assertTrue((self.home / ".Trash/Sealed/file").exists())
        self.assertIn("could not be fully searched", output)

    def test_a_symlinked_info_folder_cannot_reach_a_protected_path(self):
        trash = self.home / ".local/share/Trash"
        self.fill(trash / "files/old.txt", 4)
        (self.home / ".ssh").mkdir()
        (self.home / ".ssh/old.txt.trashinfo").write_text("keep me\n")
        (trash / "info").symlink_to(self.home / ".ssh")
        self.steps.write_text(STEPS.replace('"$HOME/.Trash"', '"$HOME/.local/share/Trash"') + "DC_TRASH_LAYOUT=freedesktop\n")
        result = self.run_steps()
        self.assertIn("Trash/info is a symlink", result.stdout)
        # Only the Docker question is asked.
        code, output = self.run_pty(answers=[b"n\n"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("Empty the Trash", output)
        self.assertEqual((self.home / ".ssh/old.txt.trashinfo").read_text(), "keep me\n")
        self.assertTrue((trash / "files/old.txt").exists())

    def test_a_failed_recount_is_a_failed_step_not_cleared(self):
        real_rm = shutil.which("rm", path="/bin:/usr/bin")
        real_find = shutil.which("find", path="/bin:/usr/bin")
        self.write_tool("rm", (
            '#!/bin/bash\nfor a in "$@"; do [[ "$a" != *old-report* ]] || exit 1; done\n'
            f'exec {real_rm} "$@"\n'
        ))
        (self.state / "rm-ran").write_text("")
        self.write_tool("find", (
            '#!/bin/bash\n'
            'if [[ "$*" == *-print0* ]]; then\n'
            '  count=$(cat "$FAKE_STATE/lists" 2>/dev/null || echo 0)\n'
            '  echo $((count + 1)) >"$FAKE_STATE/lists"\n'
            '  if [[ "$count" -ge 2 ]]; then echo denied >&2; exit 1; fi\n'
            'fi\n'
            f'exec {real_find} "$@"\n'
        ))
        code, output = self.empty_trash()
        self.assertEqual(code, 1, output)
        self.assertNotIn("Trash: cleared", output)
        self.assertIn("what remains is unknown", output)
        self.assertIn("1 failed step(s): Trash", output)

    def test_an_item_that_is_a_symlink_goes_but_its_target_stays(self):
        self.fill(self.home / "target/file", 4)
        (self.home / ".Trash/link").symlink_to(self.home / "target")
        code, output = self.empty_trash()
        self.assertEqual(code, 0, output)
        self.assertFalse((self.home / ".Trash/link").is_symlink())
        self.assertTrue((self.home / "target/file").exists())

    def test_a_symlinked_trash_is_refused(self):
        self.fill(self.home / "important/file", 4)
        shutil.rmtree(self.home / ".Trash")
        (self.home / ".Trash").symlink_to(self.home / "important")
        result = self.run_steps()
        self.assertIn("is a symlink", result.stdout)
        code, output = self.run_pty(answers=[b"n\n", b"y\n"])
        self.assertTrue((self.home / "important/file").exists())

    def test_a_symlinked_freedesktop_trash_is_refused_at_either_level(self):
        self.fill(self.home / "important/files/doc", 4)
        self.fill(self.home / "other/doc", 4)
        trash = self.home / ".local/share/Trash"
        self.steps.write_text(STEPS.replace('"$HOME/.Trash"', '"$HOME/.local/share/Trash"') + "DC_TRASH_LAYOUT=freedesktop\n")
        trash.parent.mkdir(parents=True)
        trash.symlink_to(self.home / "important")
        result = self.run_steps()
        self.assertIn("share/Trash is a symlink", result.stdout)
        trash.unlink()
        trash.mkdir()
        (trash / "files").symlink_to(self.home / "other")
        result = self.run_steps()
        self.assertIn("Trash/files is a symlink", result.stdout)
        self.assertTrue((self.home / "other/doc").exists())

    def test_a_trash_inside_a_checkout_is_refused(self):
        self.steps.write_text(STEPS.replace('"$HOME/.Trash"', '"$HOME/repo/.Trash"'))
        (self.home / "repo/.git").mkdir(parents=True)
        self.fill(self.home / "repo/.Trash/x", 4)
        result = self.run_steps()
        self.assertIn("protected path", result.stdout)

    def test_freedesktop_layout_removes_the_matching_info_file(self):
        trash = self.home / ".local/share/Trash"
        self.fill(trash / "files/old.txt", 4)
        (trash / "info").mkdir(parents=True)
        (trash / "info/old.txt.trashinfo").write_text("[Trash Info]\n")
        (trash / "files/repo/.git").mkdir(parents=True)
        (trash / "info/repo.trashinfo").write_text("[Trash Info]\n")
        self.steps.write_text(STEPS.replace('"$HOME/.Trash"', '"$HOME/.local/share/Trash"') + "DC_TRASH_LAYOUT=freedesktop\n")
        code, output = self.empty_trash()
        self.assertEqual(code, 0, output)
        self.assertFalse((trash / "files/old.txt").exists())
        self.assertFalse((trash / "info/old.txt.trashinfo").exists())
        self.assertTrue((trash / "files/repo/.git").exists())
        self.assertTrue((trash / "info/repo.trashinfo").exists())

    def test_an_item_that_cannot_go_is_a_failed_step(self):
        real = shutil.which("rm", path="/bin:/usr/bin")
        self.write_tool("rm", (
            '#!/bin/bash\nfor a in "$@"; do [[ "$a" != *old-report* ]] || exit 1; done\n'
            f'exec {real} "$@"\n'
        ))
        code, output = self.empty_trash()
        self.assertEqual(code, 1, output)
        self.assertIn("1 item(s) could not be removed", output)
        self.assertIn("1 failed step(s): Trash", output)

    def test_unreadable_trash_says_so(self):
        self.write_tool("find", '#!/bin/bash\necho "Operation not permitted" >&2\nexit 1\n')
        result = self.run_steps()
        self.assertIn("Trash: not available", result.stdout)
        self.assertIn("Full Disk Access", result.stdout)

    def test_empty_trash_is_not_asked_about(self):
        (self.home / ".Trash/old-report.pdf").unlink()
        (self.home / ".Trash/.DS_Store").write_bytes(b"x")
        result = self.run_steps()
        self.assertIn("Trash: nothing to clear (the Trash is empty).", result.stdout)


class ReportTest(Fixture):
    def fake_df(self, total, avail, device="/dev/disk1"):
        self.write_tool("df", (
            "#!/bin/bash\necho 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
            f"echo '{device} {total} {total - avail} {avail} 50% /'\n"
        ))

    def report(self, **env):
        result = self.run_steps("--report-only", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_warning_threshold_boundary(self):
        self.fake_df(100000, 15000)
        output = self.report()
        self.assertIn("(15%)", output)
        self.assertNotIn("Warning: less than", output)
        self.fake_df(100000, 14999)
        output = self.report()
        self.assertIn("(14%)", output)
        self.assertIn("Warning: less than 15% of this volume is free. Try the hint.", output)

    def test_threshold_can_be_overridden_for_one_run(self):
        self.fake_df(100000, 25000)
        self.assertIn("Warning: less than 30%", self.report(GROUNDWORK_DISK_LOW_FREE_PERCENT="30"))

    def test_device_names_with_spaces_parse(self):
        self.fake_df(100000, 50000, device="//me@server/My Share")
        self.assertIn("(50%)", self.report())

    def test_unmeasured_free_space_is_never_called_healthy(self):
        self.write_tool("df", "#!/bin/bash\nexit 1\n")
        self.assertIn("could not be measured", self.report())
        self.write_tool("df", "#!/bin/bash\necho garbage\necho more garbage\n")
        self.assertIn("could not be measured", self.report())

    def test_ten_biggest_folders_under_home_and_code(self):
        for index in range(12):
            self.fill(self.home / f"dir-{index:02d}/f", 8 * (index + 1))
        for index in range(12):
            self.fill(self.home / f"code/app-{index:02d}/f", 8 * (index + 1))
        output = self.report()
        home_part = output.split("Biggest folders under ~:")[1].split("Biggest folders under ~/code:")[0]
        code_part = output.split("Biggest folders under ~/code:")[1]
        self.assertEqual(len(home_part.strip().splitlines()), 10)
        self.assertEqual(len([line for line in code_part.splitlines() if "~/code/" in line]), 10)
        self.assertNotIn("dir-00", home_part)
        self.assertIn("~/code/app-11", code_part)
        self.assertNotIn("~/code/app-00", code_part)
        # The biggest comes first, and a nested folder is not listed under home.
        self.assertIn("~/.npm", home_part.strip().splitlines()[0])
        self.assertIn("~/code\n", home_part)
        self.assertNotIn("~/code/app", home_part)
        self.assertIn("~/code/app-11", code_part.strip().splitlines()[0])

    def test_no_code_folder(self):
        self.assertIn("Biggest folders under ~/code:\n    none measured", self.report())

    def test_folder_names_cannot_steer_the_terminal(self):
        self.fill(self.home / "bad\033[2Jname/f", 8)
        output = self.report()
        self.assertNotIn("\033", output)
        self.assertIn("~/bad[2Jname", output)

    def test_scan_limit_keeps_finished_folders_and_names_the_rest(self):
        real = shutil.which("du", path="/bin:/usr/bin")
        self.fill(self.home / "quick/f", 8)
        self.fill(self.home / "code/fast-app/f", 8)
        (self.home / "huge").mkdir()
        (self.home / "code/huge-app").mkdir()
        self.write_tool("du", (
            '#!/bin/bash\nfor a in "$@"; do case "$a" in\n'
            '  *huge*) echo $$ >>"$FAKE_STATE/du.pid"; exec sleep 300 ;;\n'
            f'esac; done\nexec {real} "$@"\n'
        ))
        started = time.monotonic()
        output = self.report(GROUNDWORK_DISK_REPORT_DEADLINE_SECONDS="1")
        self.assertLess(time.monotonic() - started, 20)
        self.assertIn("stopped at its 1s limit, so these lists are incomplete", output)
        self.assertRegex(output, r"KiB  ~/quick\n")
        self.assertRegex(output, r"KiB  ~/code/fast-app\n")
        unfinished = output.split("Did not finish in time")[1]
        self.assertIn("~/huge\n", unfinished)
        self.assertIn("~/code/huge-app\n", unfinished)
        for pid in (self.state / "du.pid").read_text().split():
            self.assert_process_gone(int(pid))

    def test_a_symlinked_code_folder_is_measured_where_it_lives(self):
        real_code = self.root / "work-disk/code"
        self.fill(real_code / "app/f", 8)
        (self.home / "code").symlink_to(real_code)
        output = self.report()
        code_part = output.split("Biggest folders under ~/code:")[1]
        self.assertIn(f"{real_code}/app", code_part)

    def test_a_home_with_no_folders_measures_nothing(self):
        shutil.rmtree(self.home / ".npm")
        shutil.rmtree(self.home / ".Trash")
        self.write_tool("du", '#!/bin/bash\nprintf "du %s\\n" "$*" >>"$FAKE_LOG"\n')
        output = self.report()
        self.assertIn("Biggest folders under ~:\n    none measured", output)
        self.assertEqual(self.commands(), [])

    def assert_process_gone(self, pid):
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)
        self.fail(f"pid {pid} is still running")

    def test_unreadable_folders_say_the_sizes_can_be_low(self):
        real = shutil.which("du", path="/bin:/usr/bin")
        self.write_tool("du", (
            f'#!/bin/bash\n{real} "$@"\necho "du: x: Operation not permitted" >&2\nexit 1\n'
        ))
        self.assertIn("Some folders could not be read", self.report())

    def test_extra_report_paths(self):
        backup = self.home / "Library/Application Support/MobileSync/Backup"
        self.fill(backup / "one/Manifest.db", 16)
        self.steps.write_text(STEPS + textwrap.dedent("""\
            dc_adapter_report_paths() {
              dc_report_path "iPhone backups" "$HOME/Library/Application Support/MobileSync/Backup" "Manage them in Finder."
              dc_report_path "Absent" "$HOME/not-here" "Never printed."
            }
            """))
        output = self.report()
        self.assertIn("iPhone backups: ", output)
        self.assertIn("at ~/Library/Application Support/MobileSync/Backup. Manage them in Finder.", output)
        self.assertNotIn("Absent", output)

    def test_report_writes_nothing_under_home(self):
        before = sorted(str(p) for p in self.home.rglob("*"))
        self.report()
        self.assertEqual(sorted(str(p) for p in self.home.rglob("*")), before)


class BoundedTest(Fixture):
    def hang_steps(self):
        self.write_tool("hang", (
            '#!/bin/bash\ntrap "" TERM\nsleep 300 &\n'
            'echo "$$ $!" >"$FAKE_STATE/hang.pids"\nwait\nsleep 300\n'
        ))
        self.steps.write_text(textwrap.dedent("""\
            dc_adapter_steps() {
              dc_allow_tool hang
              dc_step auto any stuck "Stuck"
              dc_step auto any after "After"
            }
            dc_plan_stuck() { DC_PLAN_STATE=ready; DC_PLAN_TEXT=x; }
            dc_act_stuck() { dc_mutate stuck hang; }
            dc_plan_after() { DC_PLAN_STATE=ready; DC_PLAN_TEXT=x; }
            dc_act_after() { dc_mutate after npm cache clean --force; }
            """))

    def assert_gone(self):
        for pid in (self.state / "hang.pids").read_text().split():
            for _ in range(60):
                try:
                    os.kill(int(pid), 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                self.fail(f"pid {pid} survived")

    def test_a_stuck_step_stops_with_its_whole_tree_and_later_steps_run(self):
        self.hang_steps()
        started = time.monotonic()
        result = self.run_steps(env={"GROUNDWORK_DISK_STEP_DEADLINE_SECONDS": "1"})
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Stuck: stopped at its time limit", result.stdout)
        self.assertIn("npm cache clean --force", self.commands())
        self.assert_gone()

    def test_interrupting_a_step_stops_its_tree_and_exits_130(self):
        self.hang_steps()
        pids = self.state / "hang.pids"
        code, output = self.run_pty(interrupt_when=pids.exists)
        self.assertEqual(code, 130, output)
        self.assertNotIn("npm cache clean --force", self.commands())
        self.assert_gone()

    def test_a_slow_query_cannot_hang_the_run(self):
        self.write_tool("npm", '#!/bin/bash\nexec sleep 300\n')
        started = time.monotonic()
        result = self.run_steps(env={"GROUNDWORK_DISK_OBSERVE_DEADLINE_SECONDS": "1"})
        self.assertLess(time.monotonic() - started, 20)
        self.assertIn("npm did not say where its cache is", result.stdout)
        self.assertIn("Disk report", result.stdout)

    def test_a_process_left_behind_does_not_count_as_success(self):
        self.write_tool("leaky", '#!/bin/bash\nsleep 300 &\necho $! >"$FAKE_STATE/hang.pids"\nexit 0\n')
        self.steps.write_text(textwrap.dedent("""\
            dc_adapter_steps() { dc_allow_tool leaky; dc_step auto any leaky "Leaky"; }
            dc_plan_leaky() { DC_PLAN_STATE=ready; DC_PLAN_TEXT=x; }
            dc_act_leaky() { dc_mutate leaky leaky; }
            """))
        result = self.run_steps()
        self.assertEqual(result.returncode, 1)
        self.assertIn("left a background process", result.stdout + result.stderr)
        self.assertIn("Leaky: failed (exit 70)", result.stdout)
        self.assert_gone()

    def test_temporary_files_are_removed(self):
        self.run_steps()
        self.assertEqual(list(self.tmp.iterdir()), [])


class LockTest(Fixture):
    def locked_steps(self, acquire):
        self.steps.write_text(STEPS + textwrap.dedent(f"""\
            dc_adapter_lock_acquire() {{ printf 'lock acquire\\n' >>"$FAKE_LOG"; {acquire}; }}
            dc_adapter_lock_release() {{ printf 'lock release\\n' >>"$FAKE_LOG"; }}
            """))

    def test_a_held_lock_skips_every_change_but_still_reports(self):
        self.locked_steps("return 1")
        result = self.run_steps()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped because another Groundwork maintenance run holds the lock", result.stdout)
        self.assertIn("Disk report", result.stdout)
        self.assert_no_mutation()

    def test_the_lock_is_held_around_changes_and_not_during_questions(self):
        self.locked_steps("return 0")
        code, output = self.run_pty(answers=[b"y\n", b"n\n"])
        self.assertEqual(code, 0, output)
        commands = self.commands()
        first_release = commands.index("lock release")
        self.assertLess(commands.index("npm cache clean --force"), first_release)
        self.assertLess(first_release, commands.index("docker image prune --all --force"))
        second_acquire = len(commands) - 1 - commands[::-1].index("lock acquire")
        self.assertLess(first_release, second_acquire)
        self.assertLess(second_acquire, commands.index("docker image prune --all --force"))
        self.assertEqual(commands[-1], "lock release")

    def test_a_dry_run_and_a_report_never_take_the_lock(self):
        self.locked_steps("return 0")
        self.run_steps("--dry-run")
        self.run_steps("--report-only")
        self.assertNotIn("lock acquire", self.commands())


class DocsTest(unittest.TestCase):
    def test_contract_states_the_thresholds_the_policy_uses(self):
        policy = (DIR / "policy.env").read_text()
        doc = DOC.read_text()
        self.assertIn("DC_LOW_FREE_PERCENT=15", policy)
        self.assertIn("15%", doc)
        self.assertIn("DC_NPM_CACHE_CLEAN_MIB=3072", policy)
        self.assertIn("3 GiB", doc)
        self.assertIn("DC_DOCKER_BUILD_CACHE_AGE=168h", policy)
        self.assertIn("168 hours", doc)

    def test_every_policy_value_has_a_reason(self):
        lines = (DIR / "policy.env").read_text().splitlines()
        for index, line in enumerate(lines):
            if line.startswith("DC_"):
                self.assertTrue(lines[index - 1].startswith("#"), line)

    def test_the_contract_is_linked(self):
        self.assertIn("disk-cleanup.md", (ROOT / "docs/README.md").read_text())
        self.assertIn("disk-cleanup", (ROOT / "README.md").read_text())
        self.assertIn("disk-cleanup", (ROOT / "AGENTS.md").read_text())


if __name__ == "__main__":
    unittest.main()
