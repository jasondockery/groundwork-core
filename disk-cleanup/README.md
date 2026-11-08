# Disk cleanup helper

Reference helper for the contract in [docs/disk-cleanup.md](../docs/disk-cleanup.md). An environment repo calls it in place from the `core` pin. This directory installs nothing and has no dependencies beyond bash 3.2 and standard tools, so a shell or Python updater can run it.

| File | Role |
|---|---|
| `disk-cleanup.sh` | The runner: levels, questions, dry run, report, deadlines, and the never-touch checks. |
| `shared-steps.sh` | Steps any environment can use: `docker-build-cache`, `docker-images`, `npm-cache`, `trash`. |
| `never-touch.tsv` | The paths cleanup refuses. |
| `policy.env` | Thresholds and deadlines, each with its reason. |
| `test-lanes.tsv` | How a running test process is recognized. `test-lane-vectors.tsv` holds the shared vectors. |

## A steps file

The steps file is bash, sourced by the runner. It defines functions and settings, and it changes nothing when it loads.

```bash
dc_adapter_steps() {
  #       level lane id                 title
  dc_step auto  tool npm-cache          "npm cache"
  dc_step auto  tool docker-build-cache "Docker build cache"
  dc_step auto  tool yay-cache          "yay cache"
  dc_step ask   tool docker-images      "Unused Docker images"
  dc_step ask   any  trash              "Trash"
  dc_allow_command yay -Sc --aur --noconfirm
}
DC_TRASH_DIR="$HOME/.local/share/Trash"
DC_TRASH_LAYOUT=freedesktop
DC_LOW_SPACE_HINT="Run groundwork-disk-tidy --dry-run to see what can go."

dc_plan_yay_cache() {
  command -v yay >/dev/null 2>&1 || { DC_PLAN_TEXT="yay is not installed"; return 0; }
  DC_PLAN_STATE=ready
  DC_PLAN_TEXT="old AUR builds go."
  DC_PLAN_COMMAND="yay -Sc --aur --noconfirm"
}
dc_act_yay_cache() { dc_mutate "yay cache" yay -Sc --aur --noconfirm; }
```

- `level` is `auto` or `ask`.
- `lane` is `tool` for a Docker or tool-cache step, which stands down while tests run, or `any`.
- `dc_plan_<id>` reads only, and it must guard what it runs: `dc_query ... || status=$?`. An unguarded failure stops the steps, names the step, and still prints the report, so a half-checked plan can never act. It sets `DC_PLAN_STATE` to `ready`, `nothing`, `unavailable`, or `elsewhere` (another part of the updater owns it), and `DC_PLAN_TEXT` to one line. A ready step also sets `DC_PLAN_COMMAND`, and `DC_PLAN_BY_HAND` when a person would do it differently. An ask-first step also sets `DC_PLAN_QUESTION`, and must set `DC_PLAN_KEY`, an identity of what the question covers, including any size it states, compared again before it acts.
- `dc_act_<id>` changes the machine only through `dc_mutate LABEL COMMAND...`, which runs from `$HOME`, checks the never-touch list, and enforces the deadline. It may set `DC_ACT_TEXT`. It returns the command's status. A signal the run receives ends the whole run from inside the helper, so a step does not handle one.
- `dc_allow_command COMMAND...` names one exact command the steps file runs, and `dc_allow_command_prefix COMMAND...` names one whose later arguments vary. `dc_mutate` refuses anything else, so the whole list stays visible in review. Every later argument of a prefix form is checked against the never-touch list when it runs, including a bare word, which means a path under `$HOME`. A shell, an interpreter, a wrapper, a file remover such as `rm`, or a word that names a protected path is refused in a declaration, and that stops the run before it changes anything.
- `dc_query LABEL COMMAND...` runs a bounded read-only query, leaves its stdout in the file named by `dc_output`, and returns its status.
- `dc_sudo_active` returns 0 when `sudo -n` works right now. A step that needs it checks this in its plan, and without it stays not available and says what to run by hand.
- The levels and lanes of the shared steps are fixed. `trash` and `docker-images` must be `ask`, and `docker-build-cache`, `docker-images`, and `npm-cache` must be `tool`.

Optional functions:

- `dc_adapter_prepare` runs once before the steps. `dc_prefer_mise_tool TOOL` is available there.
- `dc_adapter_report_paths` adds report lines with `dc_report_path LABEL PATH NOTE`.
- `dc_adapter_lock_acquire` and `dc_adapter_lock_release` hold the environment's maintenance lock around changes and never during questions. When acquire fails, changes are skipped and the report still runs.

## Commands

```bash
disk-cleanup.sh run --steps FILE [--dry-run | --report-only]
disk-cleanup.sh never-touch
disk-cleanup.sh check-path PATH...
disk-cleanup.sh check-command [--steps FILE] -- COMMAND...
disk-cleanup.sh test-lanes
```

`test-lanes` exits 0 when test processes run and 10 when none do. It exits 2 when the process list or the patterns cannot be read, and any other status also means a test run cannot be ruled out, so a caller stands down unless it sees 10. An updater uses it to hold back its own Docker and tool-cache work.
