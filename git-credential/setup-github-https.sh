#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Idempotent setup for GitHub over HTTPS with
# per-owner gh accounts. Platform installers call it; see README.md.
#
#   setup-github-https.sh [--file PATH] [--map OWNER=ACCOUNT]...
#                         [--ssh-alias HOST]... [--helper PATH]
#
# Installs the owner helper to a stable path and regenerates one
# Groundwork-owned git config file (default
# ${XDG_CONFIG_HOME:-~/.config}/groundwork/github-https.gitconfig) from the
# arguments alone: the full content goes to PATH.lock, created exclusively,
# and replaces PATH in one rename. The user's global config is only touched
# through `git config --global --add include.path`, and only when it does not
# already include the file. Also sets gh's git_protocol. Never reads or edits
# ssh config. A second run with the same arguments changes nothing.
# Afterwards it checks what git and the helper really see, across every file
# and include, and exits 1 naming each conflict.
set -eu -o pipefail

here=$(cd "$(dirname "$0")" && pwd -P)
# shellcheck source-path=SCRIPTDIR source=github-https-lib.sh
. "$here/github-https-lib.sh"
install_dir=${XDG_DATA_HOME:-$HOME/.local/share}/groundwork/git-credential
helper=
file=$(default_file)
maps=()
aliases=()

usage() {
  echo "usage: ${0##*/} [--file PATH] [--map OWNER=ACCOUNT]... [--ssh-alias HOST]... [--helper PATH]" >&2
  exit 64
}
die() { printf 'setup-github-https: %s\n' "$1" >&2; exit "${2:-1}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --map) [ $# -ge 2 ] || usage; maps+=("$2"); shift 2 ;;
    --ssh-alias) [ $# -ge 2 ] || usage; aliases+=("$2"); shift 2 ;;
    --helper) [ $# -ge 2 ] || usage; helper=$2; shift 2 ;;
    --file) [ $# -ge 2 ] || usage; file=$2; shift 2 ;;
    *) usage ;;
  esac
done

# Values are written unquoted and helpers run through the shell; keep them safe.
check_path() {
  case "$1" in /*) ;; *) die "not an absolute path: $1" "$2" ;; esac
  case "$1" in *[!A-Za-z0-9/._+@~-]*) die "path has characters git would split: $1" "$2" ;; esac
}

# Validate every argument before the first write.
owners=' '
for m in ${maps[@]+"${maps[@]}"}; do
  case "$m" in *=*) ;; *) die "--map needs OWNER=ACCOUNT: $m" 64 ;; esac
  owner=$(lower "${m%%=*}") account=${m#*=}
  case "$owner" in [a-z]*) ;; *) die "owner must start with a letter (git config key): $owner" 64 ;; esac
  case "$owner$account" in *[!A-Za-z0-9-]*) die "owner and account are letters, digits and hyphens: $m" 64 ;; esac
  [ -n "$account" ] && [ "${account#-}" = "$account" ] || die "bad account in $m" 64
  case "$owners" in *" $owner "*) die "owner given twice: $owner" 64 ;; esac
  owners="$owners$owner "
done
for a in ${aliases[@]+"${aliases[@]}"}; do
  case "$a" in ''|-*|*[!A-Za-z0-9._-]*) die "bad ssh host alias: $a" 64 ;; esac
done
check_path "$file" 64
if [ -n "$helper" ]; then
  check_path "$helper" 64
  [ -x "$helper" ] || die "helper not executable: $helper"
else
  helper=$install_dir/owner-credential-helper.sh
  check_path "$helper" 1
fi
gh=$("$here/owner-credential-helper.sh" gh-path) || die "gh not found; install it or set GROUNDWORK_GH"
check_path "$gh" 1
ghh="!$gh auth git-credential"

changed=0
note() { printf 'setup-github-https: %s\n' "$*"; changed=1; }
lock=
trap 'rm -f "$lock"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# take_lock PATH: create PATH.lock exclusively, or stop.
take_lock() {
  mkdir -p "$(dirname "$1")"
  if ! (set -C; : > "$1.lock") 2>/dev/null; then
    die "$1.lock exists: another setup is running, or remove it if none is"
  fi
  lock=$1.lock
}

# replace PATH: rename the filled lock over PATH when the bytes differ.
replace() {
  if cmp -s "$lock" "$1"; then
    rm -f "$lock"
  else
    mv -f "$lock" "$1"
    note "wrote $1"
  fi
  lock=
}

# Install the helper; skip when the bytes already match.
if [ "$helper" = "$install_dir/owner-credential-helper.sh" ] \
   && ! { cmp -s "$here/owner-credential-helper.sh" "$helper" && [ -x "$helper" ]; }; then
  take_lock "$helper"
  cat "$here/owner-credential-helper.sh" >> "$lock"
  chmod 0755 "$lock"
  replace "$helper"
fi

# Regenerate the owned file. Chain: empty reset (drops osxkeychain or store
# from wider scopes), the owner helper, then gh's helper for unmapped owners.
take_lock "$file"
{
  printf '# Written by groundwork-core git-credential/setup-github-https.sh; rerun it to change.\n'
  printf '[credential "https://github.com"]\n\tuseHttpPath = true\n\thelper =\n\thelper = %s\n\thelper = %s\n' \
    "$helper" "$ghh"
  printf '[url "https://github.com/"]\n\tinsteadOf = git@github.com:\n\tinsteadOf = ssh://git@github.com/\n'
  for a in ${aliases[@]+"${aliases[@]}"}; do printf '\tinsteadOf = git@%s:\n\tinsteadOf = ssh://git@%s/\n' "$a" "$a"; done
  if [ ${#maps[@]} -gt 0 ]; then
    printf '[ghaccount]\n'
    for m in "${maps[@]}"; do printf '\t%s = %s\n' "$(lower "${m%%=*}")" "${m#*=}"; done
  fi
} >> "$lock"
replace "$file"

proto() { "$gh" config get -h github.com git_protocol </dev/null 2>/dev/null || true; }
if [ "$(proto)" != https ]; then
  "$gh" config set git_protocol https </dev/null
  [ "$(proto)" = https ] || "$gh" config set -h github.com git_protocol https </dev/null
  note "set gh git_protocol https"
fi

if ! included "$file"; then
  g=$(global_file)
  if [ -L "$g" ] || { command -v chezmoi >/dev/null && chezmoi source-path "$g" >/dev/null 2>&1; }; then
    printf 'setup-github-https: %s is managed (symlink or chezmoi), so it is not edited here.\n' "$g" >&2
    printf 'Add this to its source (see "chezmoi and other managed gitconfigs" in the README):\n[include]\n\tpath = %s\n' "$file" >&2
    exit 1
  fi
  git config --global --add include.path "$file"
  note "included $file from $g"
fi

# Check what git and the helper really see.
problems=$(
  for m in ${maps[@]+"${maps[@]}"}; do map_problems "$(lower "${m%%=*}")" "${m#*=}" "$file" || true; done
  chain_problems "" "$helper" "$ghh" "rerun this script" || true
)
if [ -n "$problems" ]; then
  while IFS="$tab" read -r what how; do
    [ -n "$what" ] && printf 'setup-github-https: %s\n  fix: %s\n' "$what" "$how" >&2
  done <<EOF
$problems
EOF
  exit 1
fi

[ "$changed" = 1 ] || echo "setup-github-https: already configured, nothing changed"
