# Disk cleanup

One contract for every Groundwork environment: regular cleanup keeps a machine's disk healthy, and it cannot reach data that matters. Core owns the rules, the never-touch list, the thresholds, the report, and the dry run. The helper is [`disk-cleanup/disk-cleanup.sh`](../disk-cleanup/README.md). Each environment repo calls it in place from the `core` pin at the end of `update-all`, with a steps file for its own commands.

## Three levels

| Level | What it means | Steps |
|---|---|---|
| Automatic | Runs without asking. Removes only what its tool can rebuild, so nothing is lost. | Package-manager caches, `npm cache clean --force` over 3 GiB, `docker builder prune` for cache unused for over 168 hours (a week), and platform steps such as `xcrun simctl delete unavailable` |
| Ask first | Shows the size, defaults to no, and needs a terminal. | `docker image prune --all`, simulator runtimes older than the newest per platform, and emptying the Trash |
| Report only | Reads and prints. | Free space, the 10 biggest folders under `~` and `~/code`, and extra paths such as iPhone backups |

Nothing asks without a terminal: an ask-first step prints its size and how to clear it by hand. Only `y` or `yes` is a yes. Nothing runs until every question is answered, and a question nobody answers within 300 seconds means no. A step is checked again just before it acts, and it stops if what the question covered, or the size it stated, has changed.

The report warns when less than 15% of the volume holding the home folder is free. A size that cannot be measured is reported as unknown and is never called healthy.

A failed step is named at the end, and the next run tries again. It does not fail `update-all`.

## Never touched

Cleanup never deletes, moves, or prunes these, or anything inside them:

- `~/.t3`, `~/.aws`, `~/.ssh`, and `~/.config/gh`
- Docker volumes: never `docker volume prune` or `docker system prune --volumes`, and never the VM or data folder that holds them (`~/.colima`, `~/.lima`, Docker Desktop's container, `/var/lib/docker`)
- Any pnpm store: only `pnpm store prune` may change one
- The contents of any repo checkout or its `.git`, including `~/code`. A folder in the Trash that holds a Git checkout at any depth stays there, as does one that could not be fully searched, and the run says so.

The helper screens every cleanup command against this list before running it. A folder that contains a listed path is refused too, and a symlink cannot hide one. Every argument counts, including a relative one, because cleanup runs from the home folder. Only known cleanup tools may run, and a steps file names any other tool it needs. A shell, an interpreter, or a wrapper such as `env`, `nice`, or `timeout` can never be one, because what it would run cannot be checked. `sudo` is allowed only as `sudo -n COMMAND`, so a step never asks for a password; without active permission, a step that needs it skips and prints the command.

A pnpm store is recognized by its usual paths, by its shape (a `v<major>` folder holding `files`), and by `pnpm store path`, which runs with downloads turned off. When pnpm is installed and that query fails, the run says so.

Cleanup that belongs to one work repo is out of scope: worktrees, repo temp folders, Playwright browsers, and test caches. Each work repo cleans up after itself.

## While tests run

Docker and tool-cache steps stand down, and say why, while a test process runs: vitest, jest, Playwright, or a package manager running tests. The check runs again just before each step acts. If the process list or the patterns cannot be read, a test run cannot be ruled out, so the steps stand down then too. The report still runs. [`test-lanes.tsv`](../disk-cleanup/test-lanes.tsv) holds the patterns. They start at the executable, so a shell or agent whose arguments merely mention a test runner does not count, while the runner it starts does. Installing a runner is not running it. A process the patterns do not recognize is not detected.

## Docker

Cleanup never starts Docker. It acts only on a verified local endpoint and the daemon's own builder, and it refuses a set `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_CONFIG`, or `BUILDX_BUILDER`, because `docker builder prune` acts on the selected builder, which can be remote.

## Dry run

`--dry-run` shows what each step would clear and the exact command, and whether a running test would stop it. It runs read-only queries, never asks, and changes nothing. `--report-only` prints only the report.

## Thresholds and deadlines

[`policy.env`](../disk-cleanup/policy.env) holds each value with its reason. A `GROUNDWORK_DISK_*` variable overrides a value for one run.

| Value | Default | Why |
|---|---|---|
| Low free space | under 15% | Updates and builds start failing well before a disk is full. |
| npm cache | over 3 GiB | A small cache saves real download time. |
| Docker build cache | unused for 168 hours | A week keeps what active work reuses. |
| One cleanup command | 900 seconds | A large prune can take minutes. |
| One read-only query | 60 seconds | These answer in seconds when healthy. |
| Folder scan | 120 seconds, 4 folders at once | Each folder is measured on its own, so a stopped scan keeps what finished and names what did not. |
| One question | 300 seconds | No answer in time means no. |

Every command runs in its own process group with a hard deadline and a heartbeat. At the deadline or on Ctrl-C, the whole group gets TERM, then KILL. A command that merely exits with a status such as 130 is a failed step, and the run continues; only a signal the run itself received stops it.

## Override configs

An override config written by an environment repo, such as a systemd drop-in, lists only settings that differ from upstream defaults, each with a comment giving the reason. Copying a whole upstream file hides what was changed and goes stale when upstream moves.

## What an environment repo owns

Its steps file (see [`disk-cleanup/README.md`](../disk-cleanup/README.md)), the commands inside it (Homebrew, pacman, apt, simulators), any override config, and the call from `update-all`. Windows hosts have no `update-all`; [`groundwork-windows`](https://github.com/jasondockery/groundwork-windows) says what applies there.
