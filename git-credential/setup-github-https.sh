#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Idempotent setup for GitHub over HTTPS with
# per-owner gh accounts. Platform installers call it; see README.md.
#
#   setup-github-https.sh [--map OWNER=ACCOUNT]... [--helper PATH]
#
# Writes exactly two things: the Groundwork-owned file
# ${XDG_CONFIG_HOME:-~/.config}/groundwork/github-https.gitconfig, regenerated
# from the arguments (full content to FILE.lock, created exclusively, then one
# rename), and one include.path line in the global config through
# `git config --global --add`, only when it is not already included. It also
# installs the helper to a stable path and sets gh's git_protocol to https.
# A second run with the same arguments writes nothing. Verify with
# check-github-https.sh.
set -eu -o pipefail

here=$(cd "$(dirname "$0")" && pwd -P)
# shellcheck source-path=SCRIPTDIR source=github-https-lib.sh
. "$here/github-https-lib.sh"
install_dir=${XDG_DATA_HOME:-$HOME/.local/share}/groundwork/git-credential
file=$(owned_file)
helper=
maps=()

usage() { echo "usage: ${0##*/} [--map OWNER=ACCOUNT]... [--helper PATH]" >&2; exit 64; }
die() { printf 'setup-github-https: %s\n' "$1" >&2; exit "${2:-1}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --map) [ $# -ge 2 ] || usage; maps+=("$2"); shift 2 ;;
    --helper) [ $# -ge 2 ] || usage; helper=$2; shift 2 ;;
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
if [ -n "$helper" ]; then
  check_path "$helper" 64
  [ -x "$helper" ] || die "helper not executable: $helper"
else
  helper=$install_dir/owner-credential-helper.sh
  check_path "$helper" 1
fi
check_path "$file" 1
gh=$("$here/owner-credential-helper.sh" gh-path) || die "gh not found; install it or set GROUNDWORK_GH"
check_path "$gh" 1

changed=0
note() { printf 'setup-github-https: %s\n' "$*"; changed=1; }
lock=
trap 'rm -f "$lock"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# take_lock PATH: create PATH.lock exclusively, or stop.
take_lock() {
  mkdir -p "$(dirname "$1")"
  (set -C; : > "$1.lock") 2>/dev/null \
    || die "$1.lock exists: another setup is running; if none is, run: rm -f $(q "$1.lock")"
  lock=$1.lock
}

# replace PATH: rename the filled lock over PATH when the bytes differ.
# The lock is forgotten just before mv or rm, so the EXIT trap can never
# remove a lock another run has taken since.
replace() {
  local l=$lock
  if cmp -s "$l" "$1"; then lock=; rm -f "$l"; else lock=; mv -f "$l" "$1"; note "wrote $1"; fi
}

if [ "$helper" = "$install_dir/owner-credential-helper.sh" ] \
   && ! { cmp -s "$here/owner-credential-helper.sh" "$helper" && [ -x "$helper" ]; }; then
  take_lock "$helper"
  cat "$here/owner-credential-helper.sh" >> "$lock"
  chmod 0755 "$lock"
  replace "$helper"
fi

# Chain: empty reset (drops osxkeychain or store from wider scopes), the owner
# helper, then gh's helper for owners with no mapping.
take_lock "$file"
{
  printf '# Written by groundwork-core git-credential/setup-github-https.sh; rerun it to change.\n'
  printf '[credential "https://github.com"]\n\tuseHttpPath = true\n\thelper =\n\thelper = %s\n' "$helper"
  printf '\thelper = !%s auth git-credential\n' "$gh"
  if [ ${#maps[@]} -gt 0 ]; then
    printf '[ghaccount]\n'
    for m in "${maps[@]}"; do printf '\t%s = %s\n' "$(lower "${m%%=*}")" "${m#*=}"; done
  fi
} >> "$lock"
replace "$file"

"$gh" config set git_protocol https </dev/null

if ! included "$file"; then
  # The file `git config --global` writes: ~/.gitconfig unless only the XDG one exists.
  g=${GIT_CONFIG_GLOBAL:-$HOME/.gitconfig} xdg=${XDG_CONFIG_HOME:-$HOME/.config}/git/config
  [ -n "${GIT_CONFIG_GLOBAL:-}" ] || [ -e "$g" ] || [ ! -e "$xdg" ] || g=$xdg
  if [ -L "$g" ] || { command -v chezmoi >/dev/null && chezmoi source-path "$g" </dev/null >/dev/null 2>&1; }; then
    printf 'setup-github-https: %s is managed (symlink or chezmoi), so it is not edited here.\n' "$g" >&2
    printf 'Add this to its source (see "Managed gitconfigs" in the README):\n[include]\n\tpath = %s\n' "$file" >&2
    exit 1
  fi
  git config --global --add include.path "$file"
  note "included $file from the global git config"
fi

[ "$changed" = 1 ] || echo "setup-github-https: nothing changed"
