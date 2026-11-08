#!/usr/bin/env bash
# Shared disk cleanup for Groundwork environments. Contract: docs/disk-cleanup.md.
# Target: bash 3.2+ (stock macOS /bin/bash) and GNU or BSD userland.
# shellcheck source-path=SCRIPTDIR
set -euo pipefail

usage() {
  cat <<'EOF'
Shared disk cleanup for Groundwork environments. An environment repo calls this
from update-all with its own steps file. It installs nothing.

Usage:
  disk-cleanup.sh run --steps FILE              clean, ask, then report
  disk-cleanup.sh run --steps FILE --dry-run    show what would be cleared; change nothing
  disk-cleanup.sh run --steps FILE --report-only
                                                print only the disk report
  disk-cleanup.sh never-touch                   print the never-touch list
  disk-cleanup.sh check-path PATH...            exit 1 when a path is on the list
  disk-cleanup.sh check-command -- ARG...       exit 1 when a command would be refused
  disk-cleanup.sh test-lanes                    list running test processes; exit 0
                                                when any run, 1 when none, 2 when unknown
  disk-cleanup.sh test-lanes --classify         read command lines on stdin and print
                                                the matching label or - for each
  disk-cleanup.sh -h|--help                     show this help

Levels:
  Automatic   runs without asking; removes only what its tool can rebuild.
  Ask first   shows sizes, defaults to no, and needs a terminal.
  Report      only reads: free space, biggest folders, extra paths.

Docker and tool-cache steps are skipped, and say why, while test processes run.
Docker is never started, and a remote endpoint or builder is refused.

Exit status: 0 finished, 1 a step failed or was refused, 64 bad usage,
125 a stopped process could not be confirmed gone, 129/130/143 interrupted.
EOF
}

die_usage() {
  echo "disk-cleanup: $1" >&2
  echo "Run 'disk-cleanup.sh --help' for usage." >&2
  exit 64
}

dc_mode="act"
dc_steps_file=""

parse_run_args() {
  local report_only=0 dry_run=0
  while (($#)); do
    case "$1" in
      --steps)
        [[ "$#" -ge 2 && "$2" != -* ]] || die_usage "--steps needs a file."
        dc_steps_file="$2"
        shift
        ;;
      --dry-run) dry_run=1 ;;
      --report-only) report_only=1 ;;
      -h | --help)
        usage
        exit 0
        ;;
      -*) die_usage "unknown option: $1" ;;
      *) die_usage "unexpected argument: $1" ;;
    esac
    shift
  done
  [[ -n "$dc_steps_file" ]] || die_usage "run needs --steps FILE."
  if [[ "$dry_run" -eq 1 && "$report_only" -eq 1 ]]; then
    die_usage "--dry-run and --report-only cannot be combined."
  fi
  [[ "$dry_run" -eq 0 ]] || dc_mode="dry-run"
  [[ "$report_only" -eq 0 ]] || dc_mode="report-only"
}

# ---- Policy --------------------------------------------------------------------

dc_override() { # policy-name env-name min max
  local name="$1" env_name="$2" min="$3" max="$4" value
  value="${!env_name:-}"
  [[ -n "$value" ]] || return 0
  if [[ ! "$value" =~ ^[0-9]{1,9}$ ]] || ((10#$value < min || 10#$value > max)); then
    die_usage "$env_name must be a whole number from $min through $max."
  fi
  printf -v "$name" '%s' "$((10#$value))"
}

dc_load_policy() {
  # shellcheck source=policy.env
  . "$dc_root/policy.env"
  dc_override DC_LOW_FREE_PERCENT GROUNDWORK_DISK_LOW_FREE_PERCENT 1 99
  dc_override DC_NPM_CACHE_CLEAN_MIB GROUNDWORK_DISK_NPM_CLEAN_MIB 1 1048576
  dc_override DC_STEP_DEADLINE_SECONDS GROUNDWORK_DISK_STEP_DEADLINE_SECONDS 1 3600
  dc_override DC_OBSERVE_DEADLINE_SECONDS GROUNDWORK_DISK_OBSERVE_DEADLINE_SECONDS 1 600
  dc_override DC_REPORT_DEADLINE_SECONDS GROUNDWORK_DISK_REPORT_DEADLINE_SECONDS 1 1800
  dc_override DC_PROMPT_DEADLINE_SECONDS GROUNDWORK_DISK_PROMPT_DEADLINE_SECONDS 1 3600
}

# ---- Never-touch list ----------------------------------------------------------

dc_expand_home() { # path; sets dc_expanded
  # shellcheck disable=SC2088 # A literal tilde is what these patterns match.
  case "$1" in
    "~") dc_expanded="$HOME" ;;
    "~/"*) dc_expanded="$HOME/${1#\~/}" ;;
    /*) dc_expanded="$1" ;;
    # Cleanup commands run from HOME, so a relative path means one under HOME.
    *) dc_expanded="$HOME/$1" ;;
  esac
}

# Sets dc_canonical to the path with every symlink resolved, keeping the part
# that does not exist yet as written. Returns 1 when it cannot be resolved.
dc_canonicalize() {
  local path remainder="" parent name link hops=0
  dc_expand_home "$1"
  path="$dc_expanded"
  while [[ "$path" != "/" && "$path" == */ ]]; do path="${path%/}"; done
  while [[ -L "$path" ]]; do
    hops=$((hops + 1))
    [[ "$hops" -le 32 ]] || return 1
    link="$(readlink -- "$path")" || return 1
    case "$link" in
      /*) path="$link" ;;
      *) path="${path%/*}/$link" ;;
    esac
    while [[ "$path" != "/" && "$path" == */ ]]; do path="${path%/}"; done
  done
  while [[ ! -e "$path" && ! -L "$path" ]]; do
    name="${path##*/}"
    parent="${path%/*}"
    [[ -n "$parent" ]] || parent="/"
    remainder="/$name$remainder"
    [[ "$parent" != "$path" ]] || return 1
    path="$parent"
  done
  case "$remainder/" in
    */../* | */./*) return 1 ;;
  esac
  if [[ -d "$path" ]]; then
    path="$(cd -P -- "$path" 2>/dev/null && pwd -P)" || return 1
  else
    parent="${path%/*}"
    [[ -n "$parent" ]] || parent="/"
    name="${path##*/}"
    parent="$(cd -P -- "$parent" 2>/dev/null && pwd -P)" || return 1
    path="${parent%/}/$name"
  fi
  if [[ "$path" == "/" ]]; then
    dc_canonical="${remainder:-/}"
  else
    dc_canonical="$path$remainder"
  fi
}

# Returns 0 and sets DC_PROTECT_REASON when the path must not be touched.
dc_path_protected() {
  local entry why canonical home_canonical dir
  DC_PROTECT_REASON=""
  if ! dc_canonicalize "$1"; then
    DC_PROTECT_REASON="it could not be resolved safely"
    return 0
  fi
  canonical="$dc_canonical"
  if ! dc_canonicalize "$HOME"; then
    DC_PROTECT_REASON="the home folder could not be resolved safely"
    return 0
  fi
  home_canonical="$dc_canonical"
  if [[ "$canonical" == "/" || "$canonical" == "$home_canonical" ]]; then
    DC_PROTECT_REASON="it is the whole disk or home folder"
    return 0
  fi
  while IFS=$'\t' read -r entry why; do
    case "$entry" in "" | \#*) continue ;; esac
    dc_canonicalize "$entry" || continue
    case "$canonical/" in
      "$dc_canonical/"*)
        DC_PROTECT_REASON="$entry is on the never-touch list ($why)"
        return 0
        ;;
    esac
    case "$dc_canonical/" in
      "$canonical/"*)
        DC_PROTECT_REASON="it contains $entry, which is on the never-touch list ($why)"
        return 0
        ;;
    esac
  done <"$dc_root/never-touch.tsv"
  case "$canonical/" in
    */.git/*)
      DC_PROTECT_REASON="it is inside a .git directory"
      return 0
      ;;
    */pnpm/store/* | */.pnpm-store/*)
      DC_PROTECT_REASON="it is in a pnpm store, which only pnpm store prune may change"
      return 0
      ;;
    */docker/volumes/*)
      DC_PROTECT_REASON="it is Docker volume data"
      return 0
      ;;
  esac
  if [[ -n "${dc_pnpm_store:-}" ]]; then
    case "$canonical/" in
      "$dc_pnpm_store/"*)
        DC_PROTECT_REASON="it is in the pnpm store, which only pnpm store prune may change"
        return 0
        ;;
    esac
    case "$dc_pnpm_store/" in
      "$canonical/"*)
        DC_PROTECT_REASON="it contains the pnpm store, which only pnpm store prune may change"
        return 0
        ;;
    esac
  fi
  # Any folder holding .git is a checkout. A dotfiles repo at HOME itself does
  # not make everything under HOME a checkout, so the walk stops there. A store
  # generation is a v<major> folder holding files/, wherever it was configured.
  dir="$canonical"
  while [[ "$dir" != "/" && "$dir" != "$home_canonical" && -n "$dir" ]]; do
    if [[ -e "$dir/.git" ]]; then
      DC_PROTECT_REASON="it is inside the repo checkout at $dir"
      return 0
    fi
    if [[ "${dir##*/}" =~ ^v[0-9]+$ && -d "$dir/files" ]]; then
      DC_PROTECT_REASON="it is in a pnpm store, which only pnpm store prune may change"
      return 0
    fi
    dir="${dir%/*}"
  done
  return 1
}

# A wrapper or interpreter could run anything, so what it would touch cannot be
# checked. These can never be cleanup tools, even if a steps file asks.
dc_wrapper_tools=" sh bash zsh dash ksh fish env eval exec xargs nohup nice ionice timeout gtimeout command builtin busybox toybox stdbuf setsid doas su sudo python python2 python3 perl ruby node awk gawk sed "
# Fail closed: only the tools a cleanup step is known to need may run.
dc_allowed_tools=" docker npm pnpm apt-get paccache yay xcrun brew rm "
# Words these tools take that are not paths, so a folder named ~/cache or ~/image
# does not stop a command. An rm argument is always a path.
dc_command_words=" builder image prune cache clean simctl delete unavailable runtime store "

# A steps file names any other tool it runs, so the list stays visible in review.
dc_allow_tool() { # name
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._+-]*$ ]] || dc_invalid_steps "bad tool name: $1."
  case "$dc_wrapper_tools" in
    *" $1 "*) dc_invalid_steps "$1 could run anything, so it cannot be a cleanup tool." ;;
  esac
  dc_allowed_tools="$dc_allowed_tools$1 "
}

# Returns 0 when a cleanup command may run; otherwise sets DC_REFUSE_REASON.
dc_command_allowed() {
  local start=0 tool arg value index
  local -a argv
  argv=("$@")
  DC_REFUSE_REASON=""
  if [[ "${#argv[@]}" -eq 0 ]]; then
    DC_REFUSE_REASON="the command is empty"
    return 1
  fi
  if [[ "${argv[0]}" == sudo ]]; then
    if [[ "${argv[1]:-}" != -n || "${#argv[@]}" -lt 3 || "${argv[2]}" == -* ]]; then
      DC_REFUSE_REASON="a cleanup step may only use sudo -n COMMAND, so it never asks for a password"
      return 1
    fi
    start=2
  fi
  tool="${argv[$start]}"
  case "$tool" in
    */*)
      DC_REFUSE_REASON="a cleanup tool is named without a path: $tool"
      return 1
      ;;
  esac
  case "$dc_wrapper_tools" in
    *" $tool "*)
      DC_REFUSE_REASON="$tool could run anything, so the never-touch list could not be checked"
      return 1
      ;;
  esac
  case "$dc_allowed_tools" in
    *" $tool "*) ;;
    *)
      DC_REFUSE_REASON="$tool is not a known cleanup tool"
      return 1
      ;;
  esac
  case "$tool" in
    docker)
      for arg in "${argv[@]}"; do
        case "$arg" in
          *volume* | -v)
            DC_REFUSE_REASON="Docker volumes are on the never-touch list"
            return 1
            ;;
        esac
      done
      case "${argv[$((start + 1))]:-} ${argv[$((start + 2))]:-}" in
        "builder prune" | "image prune") ;;
        *)
          DC_REFUSE_REASON="the only Docker cleanup commands allowed are builder prune and image prune"
          return 1
          ;;
      esac
      ;;
    pnpm)
      if [[ "${#argv[@]}" -ne $((start + 3)) || "${argv[$((start + 1))]}" != store || "${argv[$((start + 2))]}" != prune ]]; then
        DC_REFUSE_REASON="pnpm stores are on the never-touch list; only pnpm store prune is allowed"
        return 1
      fi
      ;;
  esac
  # Cleanup runs from HOME, so even one relative word can name ~/.ssh or ~/code.
  for ((index = start + 1; index < ${#argv[@]}; index++)); do
    arg="${argv[$index]}"
    value="$arg"
    case "$arg" in
      *=*) value="${arg#*=}" ;;
      --*) continue ;;
      -?*/*) value="${arg:2}" ;;
      -*) continue ;;
    esac
    [[ -n "$value" ]] || continue
    if [[ "$tool" != rm && "$value" == "$arg" ]]; then
      case "$dc_command_words" in
        *" $value "*) continue ;;
      esac
    fi
    if dc_path_protected "$value"; then
      DC_REFUSE_REASON="$value: $DC_PROTECT_REASON"
      return 1
    fi
  done
  return 0
}

cmd_never_touch() {
  local entry why
  echo "Disk cleanup never deletes, moves, or prunes these:"
  while IFS=$'\t' read -r entry why; do
    case "$entry" in "" | \#*) continue ;; esac
    printf '  %s: %s\n' "$entry" "$why"
  done <"$dc_root/never-touch.tsv"
  cat <<'EOF'
  Docker volumes: never docker volume prune or docker system prune --volumes
  Any pnpm store: only pnpm store prune
  Any repo checkout or .git: the contents are never touched
EOF
}

cmd_check_path() {
  local path status=0
  for path in "$@"; do
    if dc_path_protected "$path"; then
      printf 'protected: %s: %s\n' "$path" "$DC_PROTECT_REASON"
      status=1
    fi
  done
  return "$status"
}

cmd_check_command() {
  [[ "${1:-}" == "--" ]] || die_usage "check-command needs -- before the command."
  shift
  [[ "$#" -gt 0 ]] || die_usage "check-command needs a command after --."
  if ! dc_command_allowed "$@"; then
    printf 'refused: %s\n' "$DC_REFUSE_REASON"
    return 1
  fi
}

# ---- Text ----------------------------------------------------------------------

# Keep tabs and newlines; drop every other control byte, so a folder name or a
# tool's output cannot steer the terminal.
dc_clean_text() {
  LC_ALL=C tr -d '\000-\010\013-\037\177'
}

dc_format_kib() {
  LC_ALL=C awk -v kib="$1" 'BEGIN {
    split("KiB MiB GiB TiB", unit, " ")
    i = 1
    value = kib + 0
    while (value >= 1024 && i < 4) { value /= 1024; i++ }
    if (i == 1) printf "%d %s", value, unit[i]
    else printf "%.1f %s", value, unit[i]
  }'
}

dc_home_display() { # path; prints it with HOME shown as ~
  # shellcheck disable=SC2088 # A literal tilde is the point of this output.
  case "$1" in
    "$HOME") printf '~' ;;
    "$HOME"/*) printf '~/%s' "${1#"$HOME"/}" ;;
    *) printf '%s' "$1" ;;
  esac
}

dc_quote_argv() {
  local first=1 arg
  for arg in "$@"; do
    if [[ "$first" -eq 1 ]]; then first=0; else printf ' '; fi
    case "$arg" in
      *[!A-Za-z0-9_./=:@%+-]*) printf '%q' "$arg" ;;
      *) printf '%s' "$arg" ;;
    esac
  done
}

dc_indent_tail() { # file lines
  [[ -s "$1" ]] || return 0
  tail -n "$2" "$1" | dc_clean_text | sed 's/^/      /'
}

# ---- Bounded processes ---------------------------------------------------------

dc_leader_running() {
  local state
  kill -0 "$1" 2>/dev/null || return 1
  state="$(ps -o stat= -p "$1" 2>/dev/null | tr -d '[:space:]' || true)"
  [[ -n "$state" ]] || return 0
  [[ "$state" != Z* ]]
}

dc_group_alive() {
  local snapshot
  # No member at all answers without paying for a full process list.
  kill -0 -- "-$1" 2>/dev/null || return 1
  snapshot="$(LC_ALL=C ps -eo pgid=,stat= 2>/dev/null)" || return 0
  awk -v wanted="$1" '$1 == wanted && $2 !~ /^Z/ { found = 1 } END { exit !found }' <<<"$snapshot"
}

# TERM, a short grace, then KILL. Returns 1 when the group could not be confirmed gone.
dc_stop_group() {
  local group="$1" try
  kill -TERM -- "-$group" 2>/dev/null || true
  for try in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    dc_group_alive "$group" || break
    sleep 0.1
  done
  if dc_group_alive "$group"; then
    kill -KILL -- "-$group" 2>/dev/null || true
    for try in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
      dc_group_alive "$group" || break
      sleep 0.1
    done
  fi
  : "$try"
  if dc_group_alive "$group"; then
    echo "    The process could not be confirmed stopped." >&2
    return 1
  fi
  wait "$group" 2>/dev/null || true
}

dc_restore_traps() {
  if [[ -n "$1" ]]; then eval "$1"; else trap - HUP; fi
  if [[ -n "$2" ]]; then eval "$2"; else trap - INT; fi
  if [[ -n "$3" ]]; then eval "$3"; else trap - TERM; fi
}

# Run argv in its own process group with a hard deadline, a heartbeat, and
# cancellation of the whole group. Output "-" inherits the terminal; a file gets
# stdout, and FILE.err gets stderr. Returns the command's status, or 124 only at
# this deadline. A signal this process saw, or a group that could not be confirmed
# gone, ends the whole run from here: a command that merely exits 130 is a failed
# command, not an interrupted run. Never call this from a command substitution.
dc_bounded() {
  local label="$1" seconds="$2" output="$3"
  shift 3
  local child started now beat status=0 monitor=0 leader_gone=0 gone_at=0
  local saved_hup saved_int saved_term signal_status=0 pause=0.01
  saved_hup="$(trap -p HUP || true)"
  saved_int="$(trap -p INT || true)"
  saved_term="$(trap -p TERM || true)"
  trap 'signal_status=129' HUP
  trap 'signal_status=130' INT
  trap 'signal_status=143' TERM
  case "$-" in *m*) monitor=1 ;; esac
  set -m
  if [[ "$output" == "-" ]]; then
    "$@" </dev/null &
  else
    "$@" </dev/null >"$output" 2>"$output.err" &
  fi
  child=$!
  [[ "$monitor" -eq 1 ]] || set +m
  started="$(date +%s)"
  beat=$((started + DC_HEARTBEAT_SECONDS))
  while :; do
    if [[ "$leader_gone" -eq 0 ]] && ! dc_leader_running "$child"; then
      leader_gone=1
      gone_at="$(date +%s)"
      wait "$child" 2>/dev/null || status=$?
    fi
    if [[ "$leader_gone" -eq 1 ]] && ! dc_group_alive "$child"; then
      break
    fi
    now="$(date +%s)"
    if [[ "$signal_status" -ne 0 ]]; then
      trap '' HUP INT TERM
      dc_stop_group "$child" || signal_status=125
      dc_restore_traps "$saved_hup" "$saved_int" "$saved_term"
      exit "$signal_status"
    fi
    if [[ "$now" -gt $((started + seconds)) ]]; then
      echo "    $label passed its ${seconds}s limit, so it was stopped." >&2
      trap '' HUP INT TERM
      if ! dc_stop_group "$child"; then
        dc_restore_traps "$saved_hup" "$saved_int" "$saved_term"
        exit 125
      fi
      dc_restore_traps "$saved_hup" "$saved_int" "$saved_term"
      return 124
    fi
    if [[ "$leader_gone" -eq 1 && "$now" -gt $((gone_at + 5)) ]]; then
      echo "    $label left a background process behind, so it was stopped." >&2
      trap '' HUP INT TERM
      if ! dc_stop_group "$child"; then
        dc_restore_traps "$saved_hup" "$saved_int" "$saved_term"
        exit 125
      fi
      dc_restore_traps "$saved_hup" "$saved_int" "$saved_term"
      [[ "$status" -ne 0 ]] || status=70
      return "$status"
    fi
    if [[ "$now" -ge "$beat" ]]; then
      echo "    Still running: $label ($((now - started))s elapsed)" >&2
      beat=$((now + DC_HEARTBEAT_SECONDS))
    fi
    # Most queries answer at once; wait a little longer each time up to a tenth.
    sleep "$pause"
    case "$pause" in
      0.01) pause=0.03 ;;
      *) pause=0.1 ;;
    esac
  done
  dc_restore_traps "$saved_hup" "$saved_int" "$saved_term"
  [[ "$signal_status" -eq 0 ]] || exit "$signal_status"
  # 124 means this deadline, so a command's own 124 is an ordinary failure.
  [[ "$status" -ne 124 ]] || status=1
  return "$status"
}

dc_in_home() {
  cd "$HOME"
  exec "$@"
}

dc_temp_counter=0
dc_temp() { # sets dc_tempfile
  dc_temp_counter=$((dc_temp_counter + 1))
  dc_tempfile="$dc_work/t.$dc_temp_counter"
}

# Read-only query from HOME. Leaves stdout in dc_output and returns its status.
dc_query() { # label argv...
  local label="$1" status=0
  shift
  dc_temp
  dc_output="$dc_tempfile"
  dc_bounded "$label" "$DC_OBSERVE_DEADLINE_SECONDS" "$dc_output" dc_in_home "$@" || status=$?
  return "$status"
}

# Sets dc_kib. Returns nonzero when the size could not be measured in full.
dc_measure_kib() { # path
  local value
  dc_kib=""
  dc_query "measure $(dc_home_display "$1")" du -sk -- "$1" || return "$?"
  value="$(awk 'NR == 1 && $1 ~ /^[0-9]+$/ { print $1 }' "$dc_output")"
  [[ -n "$value" ]] || return 1
  dc_kib="$value"
}

# Run a cleanup command after screening it against the never-touch list. Leaves
# output in dc_output. Returns 77 for a refused command.
dc_mutate() { # label argv...
  local label="$1" status=0
  shift
  if ! dc_command_allowed "$@"; then
    DC_ACT_TEXT="refused: $DC_REFUSE_REASON"
    return 77
  fi
  printf '    Running: %s\n' "$(dc_quote_argv "$@")"
  dc_temp
  dc_output="$dc_tempfile"
  dc_bounded "$label" "$DC_STEP_DEADLINE_SECONDS" "$dc_output" dc_in_home "$@" || status=$?
  # 77 means refused, so a command's own 77 is an ordinary failure.
  [[ "$status" -ne 77 ]] || status=1
  return "$status"
}

# Put a tool managed by mise ahead of PATH, so cleanup acts on the copy the user
# works with. A machine without mise keeps its PATH.
dc_prefer_mise_tool() { # tool
  local path
  command -v mise >/dev/null 2>&1 || return 0
  dc_query "mise which $1" mise which "$1" || return 0
  path="$(head -n 1 "$dc_output")"
  case "$path" in
    /*/"$1") PATH="${path%/*}:$PATH" ;;
  esac
}

# ---- Test lanes ----------------------------------------------------------------

# Reads "pid command" lines; prints "label<TAB>pid" for each running test process.
dc_match_lanes() {
  LC_ALL=C awk -F '\t' -v patterns="$dc_root/test-lanes.tsv" '
    BEGIN {
      while ((getline line < patterns) > 0) {
        if (line ~ /^#/ || line == "") continue
        split(line, field, "\t")
        n++
        label[n] = field[1]
        pattern[n] = field[2]
      }
      close(patterns)
    }
    {
      text = $0
      pid = text
      sub(/^[ ]*/, "", pid)
      sub(/[ ].*$/, "", pid)
      sub(/^[ ]*[0-9]+[ ]+/, "", text)
      text = text " "
      for (i = 1; i <= n; i++) {
        if (text ~ pattern[i]) {
          print label[i] "\t" pid
          break
        }
      }
    }'
}

# Sets dc_lanes_active, dc_lanes_unknown, and dc_lane_summary. Unknown counts as
# active: a cleanup that cannot rule a test run out stands down.
dc_refresh_lanes() {
  local listing matches
  dc_lanes_active=0
  dc_lanes_unknown=0
  dc_lane_summary=""
  if ! awk -F '\t' '!/^#/ && $2 != "" { found = 1 } END { exit !found }' "$dc_root/test-lanes.tsv" 2>/dev/null; then
    dc_lanes_active=1
    dc_lanes_unknown=1
    dc_lane_summary="the test-run patterns could not be read, so a test run cannot be ruled out"
    return 0
  fi
  if ! listing="$(ps -eww -o pid=,command= 2>/dev/null)" || [[ -z "$listing" ]]; then
    dc_lanes_active=1
    dc_lanes_unknown=1
    dc_lane_summary="running processes could not be listed, so a test run cannot be ruled out"
    return 0
  fi
  if ! matches="$(dc_match_lanes <<<"$listing" | awk -F '\t' -v self="$$" '$2 != self')"; then
    dc_lanes_active=1
    dc_lanes_unknown=1
    dc_lane_summary="the process list could not be checked, so a test run cannot be ruled out"
    return 0
  fi
  [[ -n "$matches" ]] || return 0
  dc_lanes_active=1
  dc_lane_summary="test processes are running: $(awk -F '\t' '
    NR <= 3 { printf "%s%s (pid %s)", (NR > 1 ? ", " : ""), $1, $2 }
    END { if (NR > 3) printf ", and %d more", NR - 3 }' <<<"$matches")"
}

cmd_test_lanes() {
  local line
  if [[ "${1:-}" == "--classify" ]]; then
    [[ "$#" -eq 1 ]] || die_usage "test-lanes --classify takes no other arguments."
    while IFS= read -r line; do
      printf '1 %s\n' "$line" | dc_match_lanes | cut -f 1 | grep . || echo "-"
    done
    return 0
  fi
  [[ "$#" -eq 0 ]] || die_usage "unexpected argument: $1"
  dc_refresh_lanes
  if [[ "$dc_lanes_active" -eq 0 ]]; then
    echo "No test processes are running."
    return 1
  fi
  printf '%s\n' "$dc_lane_summary"
  [[ "$dc_lanes_unknown" -eq 0 ]] || return 2
}

# ---- Steps ---------------------------------------------------------------------

dc_step_levels=()
dc_step_lanes=()
dc_step_ids=()
dc_step_titles=()

dc_step() { # level lane id title
  [[ "$#" -eq 4 ]] || dc_invalid_steps "dc_step needs a level, lane, id, and title."
  case "$1" in auto | ask) ;; *) dc_invalid_steps "unknown level: $1" ;; esac
  case "$2" in tool | any) ;; *) dc_invalid_steps "unknown lane: $2" ;; esac
  [[ "$3" =~ ^[a-z0-9-]+$ ]] || dc_invalid_steps "bad step id: $3"
  dc_step_levels+=("$1")
  dc_step_lanes+=("$2")
  dc_step_ids+=("$3")
  dc_step_titles+=("$4")
}

dc_invalid_steps() {
  echo "disk-cleanup: the steps file is invalid: $1 Nothing was changed." >&2
  exit 1
}

dc_load_steps() {
  local i fn
  [[ -r "$dc_steps_file" && -f "$dc_steps_file" ]] || dc_invalid_steps "$dc_steps_file cannot be read."
  bash -n "$dc_steps_file" 2>/dev/null || dc_invalid_steps "$dc_steps_file has a syntax error."
  # shellcheck source=/dev/null
  . "$dc_steps_file"
  declare -F dc_adapter_steps >/dev/null || dc_invalid_steps "dc_adapter_steps is missing."
  dc_adapter_steps
  for ((i = 0; i < ${#dc_step_ids[@]}; i++)); do
    fn="${dc_step_ids[$i]//-/_}"
    declare -F "dc_plan_$fn" >/dev/null || dc_invalid_steps "dc_plan_$fn is missing."
    declare -F "dc_act_$fn" >/dev/null || dc_invalid_steps "dc_act_$fn is missing."
  done
}

dc_plan_reset() {
  DC_PLAN_STATE="unavailable"
  DC_PLAN_TEXT="its check did not report a result"
  DC_PLAN_COMMAND=""
  DC_PLAN_BY_HAND=""
  DC_PLAN_QUESTION=""
  DC_PLAN_KEY=""
}

dc_plan() { # index
  dc_plan_reset
  "dc_plan_${dc_step_ids[$1]//-/_}"
}

dc_cleared=0
dc_failed=0
dc_failed_names=""

dc_note_failure() { # title
  dc_failed=$((dc_failed + 1))
  dc_failed_names="${dc_failed_names:+$dc_failed_names, }$1"
}

dc_act() { # index
  local title="${dc_step_titles[$1]}" fn="${dc_step_ids[$1]//-/_}" status=0
  DC_ACT_TEXT=""
  "dc_act_$fn" || status=$?
  case "$status" in
    0)
      dc_cleared=$((dc_cleared + 1))
      printf '  %s: cleared.%s\n' "$title" "${DC_ACT_TEXT:+ $DC_ACT_TEXT}"
      ;;
    77)
      dc_note_failure "$title"
      printf '  %s: %s\n' "$title" "$DC_ACT_TEXT"
      ;;
    124)
      dc_note_failure "$title"
      printf '  %s: stopped at its time limit; some of it may be gone. The next run tries again.\n' "$title"
      ;;
    *)
      dc_note_failure "$title"
      printf '  %s: failed (exit %s). The next run tries again.\n' "$title" "$status"
      if [[ -n "${dc_output:-}" ]]; then
        dc_indent_tail "$dc_output" 3
        dc_indent_tail "$dc_output.err" 3
      fi
      ;;
  esac
}

dc_lock_held=0

dc_lock_acquire() {
  [[ "$dc_lock_held" -eq 0 ]] || return 0
  declare -F dc_adapter_lock_acquire >/dev/null || return 0
  if dc_adapter_lock_acquire; then
    dc_lock_held=1
    return 0
  fi
  return 1
}

dc_lock_release() {
  [[ "$dc_lock_held" -eq 1 ]] || return 0
  dc_lock_held=0
  if declare -F dc_adapter_lock_release >/dev/null; then
    dc_adapter_lock_release || true
  fi
}

dc_print_would() {
  case "$DC_PLAN_COMMAND" in
    "") ;;
    *) printf '    %s: %s\n' "$1" "$DC_PLAN_COMMAND" ;;
  esac
}

# Lane-sensitive steps stop here while a test process runs.
dc_lane_blocks() { # index
  [[ "${dc_step_lanes[$1]}" == tool ]] || return 1
  [[ "$dc_mode" == act ]] && dc_refresh_lanes
  [[ "$dc_lanes_active" -eq 1 ]]
}

dc_auto_phase() {
  local i title busy
  echo
  echo "Automatic"
  for ((i = 0; i < ${#dc_step_ids[@]}; i++)); do
    [[ "${dc_step_levels[$i]}" == auto ]] || continue
    title="${dc_step_titles[$i]}"
    busy=0
    if dc_lane_blocks "$i"; then
      busy=1
      if [[ "$dc_mode" == act ]]; then
        printf '  %s: skipped because %s. The next run tries again.\n' "$title" "$dc_lane_summary"
        continue
      fi
    fi
    dc_plan "$i"
    case "$DC_PLAN_STATE" in
      ready)
        if [[ "$dc_mode" == dry-run ]]; then
          printf '  %s: %s\n' "$title" "$DC_PLAN_TEXT"
          dc_print_would "Would run"
          [[ "$busy" -eq 0 ]] || printf '    Would be skipped right now because %s.\n' "$dc_lane_summary"
        elif ! dc_lock_acquire; then
          printf '  %s: skipped because another Groundwork maintenance run holds the lock.\n' "$title"
        elif dc_lane_blocks "$i"; then
          # Planning can take a while, so a test run may have started since.
          printf '  %s: skipped because %s. The next run tries again.\n' "$title" "$dc_lane_summary"
        else
          printf '  %s: %s\n' "$title" "$DC_PLAN_TEXT"
          dc_act "$i"
        fi
        ;;
      nothing) printf '  %s: nothing to clear (%s).\n' "$title" "$DC_PLAN_TEXT" ;;
      elsewhere) printf '  %s: %s\n' "$title" "$DC_PLAN_TEXT" ;;
      *) printf '  %s: not available (%s).\n' "$title" "$DC_PLAN_TEXT" ;;
    esac
  done
  dc_lock_release
}

# 0 yes, 1 no or no answer in time, 2 input ended.
dc_ask() { # question
  local answer normalized status asked_at
  while :; do
    printf '%s [y/N] ' "$1" >&2
    status=0
    asked_at="$(date +%s)"
    IFS= read -r -t "$DC_PROMPT_DEADLINE_SECONDS" answer || status=$?
    # Bash 3.2 returns 1 for both a timeout and end of input, so the clock decides.
    if [[ "$status" -gt 128 ]] || { [[ "$status" -ne 0 ]] \
      && [[ "$(date +%s)" -ge $((asked_at + DC_PROMPT_DEADLINE_SECONDS)) ]]; }; then
      echo >&2
      echo "  No answer within ${DC_PROMPT_DEADLINE_SECONDS}s, so it stays." >&2
      return 1
    fi
    if [[ "$status" -ne 0 ]]; then
      echo >&2
      return 2
    fi
    normalized="$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')"
    case "$normalized" in
      y | yes) return 0 ;;
      "" | n | no) return 1 ;;
      *) echo "Please answer y or n." >&2 ;;
    esac
  done
}

dc_ask_phase() {
  local i title interactive=0 answer_status question
  local -a ready_indexes confirmed_indexes ready_keys ready_questions
  ready_indexes=()
  confirmed_indexes=()
  ready_keys=()
  ready_questions=()
  [[ ! -t 0 || ! -t 2 ]] || interactive=1
  echo
  echo "Ask first"
  for ((i = 0; i < ${#dc_step_ids[@]}; i++)); do
    [[ "${dc_step_levels[$i]}" == ask ]] || continue
    title="${dc_step_titles[$i]}"
    if dc_lane_blocks "$i" && [[ "$dc_mode" == act ]]; then
      printf '  %s: not offered because %s.\n' "$title" "$dc_lane_summary"
      continue
    fi
    dc_plan "$i"
    case "$DC_PLAN_STATE" in
      ready)
        printf '  %s: %s\n' "$title" "$DC_PLAN_TEXT"
        if [[ "$dc_mode" == dry-run ]]; then
          dc_print_would "Would ask, then run"
          [[ "${dc_step_lanes[$i]}" != tool || "$dc_lanes_active" -eq 0 ]] \
            || printf '    Would not be offered right now because %s.\n' "$dc_lane_summary"
        elif [[ "$interactive" -eq 0 ]]; then
          printf '    Not asked because there is no terminal. To clear it yourself: %s\n' \
            "${DC_PLAN_BY_HAND:-$DC_PLAN_COMMAND}"
        else
          ready_indexes+=("$i")
          ready_keys+=("$DC_PLAN_KEY")
          ready_questions+=("${DC_PLAN_QUESTION:-Clear $title?}")
        fi
        ;;
      nothing) printf '  %s: nothing to clear (%s).\n' "$title" "$DC_PLAN_TEXT" ;;
      elsewhere) printf '  %s: %s\n' "$title" "$DC_PLAN_TEXT" ;;
      *) printf '  %s: not available (%s).\n' "$title" "$DC_PLAN_TEXT" ;;
    esac
  done
  [[ "${#ready_indexes[@]}" -gt 0 ]] || return 0
  echo
  echo "Answer each question; the default is no. Nothing runs until every question is answered."
  for ((i = 0; i < ${#ready_indexes[@]}; i++)); do
    question="${ready_questions[$i]}"
    answer_status=0
    dc_ask "$question" || answer_status=$?
    case "$answer_status" in
      0) confirmed_indexes+=("$i") ;;
      1) ;;
      *)
        echo "  Input ended before every question was answered, so nothing here was cleared."
        return 0
        ;;
    esac
  done
  [[ "${#confirmed_indexes[@]}" -gt 0 ]] || return 0
  echo
  for ((i = 0; i < ${#confirmed_indexes[@]}; i++)); do
    local slot="${confirmed_indexes[$i]}" index
    index="${ready_indexes[$slot]}"
    title="${dc_step_titles[$index]}"
    if ! dc_lock_acquire; then
      printf '  %s: skipped because another Groundwork maintenance run holds the lock.\n' "$title"
      continue
    fi
    if dc_lane_blocks "$index"; then
      printf '  %s: skipped because %s.\n' "$title" "$dc_lane_summary"
      continue
    fi
    dc_plan "$index"
    if [[ "$DC_PLAN_STATE" != ready || "$DC_PLAN_KEY" != "${ready_keys[$slot]}" ]]; then
      printf '  %s: skipped because it changed after the question. Run this again to see the new sizes.\n' "$title"
      continue
    fi
    dc_act "$index"
  done
  dc_lock_release
}

# ---- Report --------------------------------------------------------------------

# Sets dc_free_* from df -Pk. Returns 1 when the output cannot be read.
dc_read_free_space() {
  local line
  dc_free_total=""
  dc_free_avail=""
  dc_query "read free space" df -Pk "$HOME" || return 1
  line="$(LC_ALL=C awk 'NR == 2 {
    for (i = 2; i + 3 <= NF; i++) {
      if ($i ~ /^[0-9]+$/ && $(i + 1) ~ /^[0-9]+$/ && $(i + 2) ~ /^[0-9]+$/ && $(i + 3) ~ /%$/) {
        print $i, $(i + 2)
        exit
      }
    }
  }' "$dc_output")"
  [[ -n "$line" ]] || return 1
  dc_free_total="${line%% *}"
  dc_free_avail="${line##* }"
  [[ "$dc_free_total" -gt 0 ]]
}

dc_report_free_space() {
  local percent
  dc_low_space=0
  if ! dc_read_free_space; then
    echo "  Free space: could not be measured, so it cannot be called healthy."
    return 0
  fi
  percent=$((dc_free_avail * 100 / dc_free_total))
  printf '  Free space: %s of %s (%s%%) on the volume holding your home folder.\n' \
    "$(dc_format_kib "$dc_free_avail")" "$(dc_format_kib "$dc_free_total")" "$percent"
  if ((dc_free_avail * 100 < DC_LOW_FREE_PERCENT * dc_free_total)); then
    dc_low_space=1
  fi
}

dc_print_top() { # heading file
  local size path
  echo "  $1"
  if [[ ! -s "$2" ]]; then
    echo "    none measured"
    return 0
  fi
  LC_ALL=C sort -t "$(printf '\t')" -k1,1nr "$2" | head -n "$DC_TOP_FOLDERS" >"$2.top"
  while IFS=$'\t' read -r size path; do
    printf '    %10s  %s\n' "$(dc_format_kib "$size")" "$(dc_home_display "$path" | dc_clean_text)"
  done <"$2.top"
}

# Runs in its own process group under one deadline. Each folder gets its own du,
# so a stopped scan keeps every folder that finished: du buffers its output and a
# single du over the whole home folder would lose all of it.
dc_scan_worker() { # NUL-separated folder list
  local status=0
  nice -n 10 xargs -0 -n 1 -P "$DC_SCAN_JOBS" du -xsk -- <"$1" || status=$?
  [[ "$status" -eq 0 ]] || return 1
}

dc_report_folders() {
  local status=0 list raw home_rows code_rows code_root="$HOME/code" code_scan="" unfinished path_line
  dc_temp
  list="$dc_tempfile"
  : >"$list"
  dc_temp
  raw="$dc_tempfile"
  : >"$raw"
  home_rows="$raw.home"
  code_rows="$raw.code"
  : >"$home_rows"
  : >"$code_rows"
  # A real ~/code is measured by its children, so it is not walked twice. A
  # symlinked one is not a folder under HOME, and its children are measured where
  # they really live.
  if [[ -d "$code_root" ]]; then
    code_scan="$(cd -P -- "$code_root" 2>/dev/null && pwd -P)" || code_scan=""
  fi
  status=0
  dc_query "list folders" find "$HOME" -mindepth 1 -maxdepth 1 -type d ! -path "$code_root" -print0 || status=$?
  [[ "$status" -ne 0 ]] || cat "$dc_output" >>"$list"
  if [[ -n "$code_scan" ]]; then
    status=0
    dc_query "list code folders" find "$code_scan" -mindepth 1 -maxdepth 1 -type d -print0 || status=$?
    [[ "$status" -ne 0 ]] || cat "$dc_output" >>"$list"
  fi
  status=0
  if [[ -s "$list" ]]; then
    dc_bounded "measure folders" "$DC_REPORT_DEADLINE_SECONDS" "$raw" dc_scan_worker "$list" || status=$?
  fi
  LC_ALL=C awk -v home="$HOME/" -v code="$code_scan/" -v home_rows="$home_rows" -v code_rows="$code_rows" '
    function direct_child(path, parent, rest) {
      if (index(path, parent) != 1) return 0
      rest = substr(path, length(parent) + 1)
      return rest != "" && index(rest, "/") == 0
    }
    {
      if (index($0, "\t") == 0) next
      size = substr($0, 1, index($0, "\t") - 1)
      if (size !~ /^[0-9]+$/) next
      path = substr($0, index($0, "\t") + 1)
      if (code != "/" && direct_child(path, code)) {
        print size "\t" path > code_rows
        code_total += size
        code_seen = 1
      } else if (direct_child(path, home)) {
        print size "\t" path > home_rows
      }
    }
    END {
      if (code_seen && code == home "code/") print code_total "\t" home "code" > home_rows
    }' "$raw"
  dc_print_top "Biggest folders under ~:" "$home_rows"
  dc_print_top "Biggest folders under ~/code:" "$code_rows"
  case "$status" in
    0) ;;
    124)
      unfinished="$(LC_ALL=C tr '\0' '\n' <"$list" | LC_ALL=C awk -F '\t' '
        NR == FNR { if (index($0, "\t")) done[substr($0, index($0, "\t") + 1)] = 1; next }
        !($0 in done)' "$raw" - | head -n 5)"
      echo "  The folder scan stopped at its ${DC_REPORT_DEADLINE_SECONDS}s limit, so these lists are incomplete."
      if [[ -n "$unfinished" ]]; then
        echo "  Did not finish in time, and these are often the biggest:"
        while IFS= read -r path_line; do
          printf '    %s\n' "$(dc_home_display "$path_line" | dc_clean_text)"
        done <<<"$unfinished"
      fi
      ;;
    *) echo "  Some folders could not be read, so these sizes can be low." ;;
  esac
}

# Called by a steps file from dc_adapter_report_paths.
dc_report_path() { # label path note
  local status=0
  [[ -e "$2" ]] || return 0
  dc_measure_kib "$2" || status=$?
  if [[ "$status" -ne 0 || -z "${dc_kib:-}" ]]; then
    printf '  %s: at %s, but it could not be read. %s\n' "$1" "$(dc_home_display "$2")" "${3:-}"
    return 0
  fi
  printf '  %s: %s at %s. %s\n' "$1" "$(dc_format_kib "$dc_kib")" "$(dc_home_display "$2")" "${3:-}"
}

dc_report() {
  echo
  echo "Disk report"
  dc_report_free_space
  dc_report_folders
  if declare -F dc_adapter_report_paths >/dev/null; then
    dc_adapter_report_paths
  fi
  if [[ "$dc_low_space" -eq 1 ]]; then
    printf '  Warning: less than %s%% of this volume is free.%s\n' \
      "$DC_LOW_FREE_PERCENT" "${DC_LOW_SPACE_HINT:+ $DC_LOW_SPACE_HINT}"
  fi
}

# ---- Run -----------------------------------------------------------------------

# Default stores are recognized by path and shape. A store configured elsewhere needs
# pnpm's own answer. This query must never download a package manager or a tool.
dc_load_pnpm_store() {
  local status=0 store
  dc_pnpm_store=""
  command -v pnpm >/dev/null 2>&1 || return 0
  COREPACK_ENABLE_NETWORK=0 MISE_OFFLINE=1 MISE_AUTO_INSTALL=0 MISE_EXEC_AUTO_INSTALL=0 \
    MISE_NOT_FOUND_AUTO_INSTALL=0 MISE_TASK_RUN_AUTO_INSTALL=0 \
    dc_query "pnpm store path" pnpm store path || status=$?
  store="$(head -n 1 "$dc_output" 2>/dev/null || true)"
  case "$status:$store" in
    0:/*[[:cntrl:]]*) ;;
    0:/*)
      if dc_canonicalize "$store"; then
        dc_pnpm_store="$dc_canonical"
        return 0
      fi
      ;;
  esac
  dc_pnpm_note="pnpm's store location could not be read, so only its usual locations and shape are recognized."
}

dc_work=""
dc_pnpm_note=""
dc_on_exit() {
  local status=$?
  trap - EXIT
  case "$status" in
    129 | 130 | 143)
      echo "Disk cleanup was interrupted. A step that had already started may have finished part of its work." >&2
      ;;
    125)
      echo "Disk cleanup stopped because a process could not be confirmed gone. A step that had already started may have finished part of its work." >&2
      ;;
  esac
  dc_lock_release || true
  [[ -z "$dc_work" ]] || rm -rf -- "$dc_work" || true
  exit "$status"
}

cmd_run() {
  dc_load_steps
  trap dc_on_exit EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  dc_work="$(mktemp -d "${TMPDIR:-/tmp}/groundwork-disk-cleanup.XXXXXX")"
  if declare -F dc_adapter_prepare >/dev/null; then
    dc_adapter_prepare
  fi
  if [[ "$dc_mode" == report-only ]]; then
    dc_report
    return 0
  fi
  dc_load_pnpm_store
  if [[ "$dc_mode" == dry-run ]]; then
    echo "Disk cleanup (dry run: nothing is changed)"
  else
    echo "Disk cleanup"
  fi
  [[ -z "$dc_pnpm_note" ]] || printf '  %s\n' "$dc_pnpm_note"
  dc_refresh_lanes
  if [[ "$dc_lanes_active" -eq 1 ]]; then
    printf '  Docker and tool-cache steps stand down because %s.\n' "$dc_lane_summary"
  fi
  dc_auto_phase
  dc_ask_phase
  dc_report
  if [[ "$dc_failed" -gt 0 ]]; then
    echo
    printf 'Disk cleanup finished with %s failed step(s): %s\n' "$dc_failed" "$dc_failed_names"
    return 1
  fi
}

# ---- Main ----------------------------------------------------------------------

main() {
  [[ "$#" -gt 0 ]] || {
    usage >&2
    exit 64
  }
  local subcommand="$1"
  shift
  case "$subcommand" in
    -h | --help)
      usage
      exit 0
      ;;
    run) parse_run_args "$@" ;;
    never-touch)
      [[ "$#" -eq 0 ]] || die_usage "never-touch takes no arguments."
      ;;
    check-path)
      [[ "$#" -gt 0 ]] || die_usage "check-path needs at least one path."
      ;;
    check-command | test-lanes) ;;
    *) die_usage "unknown command: $subcommand" ;;
  esac
  [[ -n "${HOME:-}" ]] || {
    echo "disk-cleanup: HOME is not set. Nothing was changed." >&2
    exit 1
  }
  case "$HOME" in
    /*) ;;
    *)
      echo "disk-cleanup: HOME must be an absolute path. Nothing was changed." >&2
      exit 1
      ;;
  esac
  case "${BASH_SOURCE[0]}" in
    */*) dc_root="${BASH_SOURCE[0]%/*}" ;;
    *) dc_root="." ;;
  esac
  dc_root="$(cd -P -- "$dc_root" && pwd -P)"
  dc_load_policy
  # shellcheck source=shared-steps.sh
  . "$dc_root/shared-steps.sh"
  case "$subcommand" in
    run) cmd_run ;;
    never-touch) cmd_never_touch ;;
    check-path) cmd_check_path "$@" ;;
    check-command) cmd_check_command "$@" ;;
    test-lanes) cmd_test_lanes "$@" ;;
  esac
}

main "$@"
