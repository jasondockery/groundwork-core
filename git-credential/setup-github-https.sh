#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Idempotent setup for GitHub over HTTPS with
# per-owner gh accounts. Platform installers call it; see README.md.
#
#   setup-github-https.sh [--file PATH] [--map OWNER=ACCOUNT]...
#                         [--ssh-alias HOST]... [--helper PATH]
#
# Installs the owner helper to a stable path, then edits one git config file:
# the one `git config --global` writes (honors GIT_CONFIG_GLOBAL), or an
# absolute --file PATH that the global config includes. Every edit goes to a
# temp copy that replaces the file in one rename. Also sets gh's
# git_protocol. Never reads or edits ssh config. A second run with the same
# arguments changes nothing. Afterwards it checks what git and the helper
# really see, across every file and include, and exits 1 naming each conflict,
# so "already configured" is only printed when it is true.
set -eu -o pipefail

here=$(cd "$(dirname "$0")" && pwd -P)
# shellcheck source-path=SCRIPTDIR source=github-https-lib.sh
. "$here/github-https-lib.sh"
install_dir=${XDG_DATA_HOME:-$HOME/.local/share}/groundwork/git-credential
helper=
file=
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

# Helper values are run through the shell by git; keep them unquoted and safe.
check_path() {
  case "$1" in /*) ;; *) die "not an absolute path: $1" "$2" ;; esac
  case "$1" in *[!A-Za-z0-9/._+@~-]*) die "path has characters git would split: $1" "$2" ;; esac
}

# Validate every argument before the first write.
for m in ${maps[@]+"${maps[@]}"}; do
  case "$m" in *=*) ;; *) die "--map needs OWNER=ACCOUNT: $m" 64 ;; esac
  owner=${m%%=*} account=${m#*=}
  case "$owner" in [A-Za-z]*) ;; *) die "owner must start with a letter (git config key): $owner" 64 ;; esac
  case "$owner$account" in *[!A-Za-z0-9-]*) die "owner and account are letters, digits and hyphens: $m" 64 ;; esac
  [ -n "$account" ] && [ "${account#-}" = "$account" ] || die "bad account in $m" 64
done
for a in ${aliases[@]+"${aliases[@]}"}; do
  case "$a" in ''|-*|*[!A-Za-z0-9._-]*) die "bad ssh host alias: $a" 64 ;; esac
done
if [ -n "$helper" ]; then
  check_path "$helper" 64
  [ -x "$helper" ] || die "helper not executable: $helper"
else
  helper=$install_dir/owner-credential-helper.sh
  check_path "$helper" 1
fi
case "$file" in ''|/*) ;; *) die "--file needs an absolute path: $file" 64 ;; esac
target=${file:-$(global_file)}
[ ! -L "$target" ] || die "$target is a symlink; pass the file it points to with --file"
gh=$("$here/owner-credential-helper.sh" gh-path) || die "gh not found; install it or set GROUNDWORK_GH"
check_path "$gh" 1
ghh="!$gh auth git-credential"

changed=0
note() { printf 'setup-github-https: %s\n' "$*"; changed=1; }

# Install the helper atomically; skip when the bytes already match.
if [ "$helper" = "$install_dir/owner-credential-helper.sh" ] \
   && ! { cmp -s "$here/owner-credential-helper.sh" "$helper" && [ -x "$helper" ]; }; then
  mkdir -p "$install_dir"
  tmp=$(mktemp "$install_dir/.owner-credential-helper.XXXXXX")
  trap 'rm -f "$tmp"' EXIT INT TERM
  cp "$here/owner-credential-helper.sh" "$tmp"
  chmod 0755 "$tmp"
  mv -f "$tmp" "$helper"
  note "installed $helper"
fi

# Edit a copy (same directory, same mode) and rename it over the target.
mkdir -p "$(dirname "$target")"
tmp=$(mktemp "$(dirname "$target")/.gitconfig.XXXXXX")
trap 'rm -f "$tmp"' EXIT INT TERM
[ ! -e "$target" ] || cp -p "$target" "$tmp"
cfg() { git config --file "$tmp" "$@"; }

key=credential.https://github.com
[ "$(cfg --get-all "$key.useHttpPath" || true)" = true ] || cfg --replace-all "$key.useHttpPath" true

# Chain: empty reset (drops osxkeychain or store from wider scopes), the owner
# helper, then gh's helper for owners with no mapping. The trailing x keeps an
# extra empty entry at the end from comparing equal.
if [ "$(cfg --get-all "$key.helper" || true; echo x)" != "$(printf '\n%s\n%s\nx' "$helper" "$ghh")" ]; then
  cfg --unset-all "$key.helper" || true
  cfg --add "$key.helper" ""
  cfg --add "$key.helper" "$helper"
  cfg --add "$key.helper" "$ghh"
fi

prefixes=("git@github.com:" "ssh://git@github.com/")
for a in ${aliases[@]+"${aliases[@]}"}; do prefixes+=("git@$a:" "ssh://git@$a/"); done
for p in "${prefixes[@]}"; do
  case $'\n'"$(cfg --get-all url.https://github.com/.insteadOf || true)"$'\n' in
    *$'\n'"$p"$'\n'*) ;;
    *) cfg --add url.https://github.com/.insteadOf "$p" ;;
  esac
done

for m in ${maps[@]+"${maps[@]}"}; do
  [ "$(cfg --get-all "ghaccount.${m%%=*}" || true)" = "${m#*=}" ] || cfg --replace-all "ghaccount.${m%%=*}" "${m#*=}"
done

if cmp -s "$tmp" "$target"; then
  rm -f "$tmp"
else
  mv -f "$tmp" "$target"
  note "updated $target"
fi
trap - EXIT INT TERM

proto() { "$gh" config get -h github.com git_protocol </dev/null 2>/dev/null || true; }
if [ "$(proto)" != https ]; then
  "$gh" config set git_protocol https </dev/null
  [ "$(proto)" = https ] || "$gh" config set -h github.com git_protocol https </dev/null
  note "set gh git_protocol https"
fi

# Check what git and the helper really see.
problems=
if [ -n "$file" ] && ! included "$file"; then
  problems="$file is not included from the global git config, so git does not read it"$'\t'"git config --global --add include.path $(q "$file")"
else
  for m in ${maps[@]+"${maps[@]}"}; do
    problems=$problems$(map_problems "${m%%=*}" "${m#*=}" "$target" || true)$'\n'
  done
  problems=$problems$(chain_problems "" "$helper" "$ghh" "rerun this script" || true)
fi
problems=$(printf '%s\n' "$problems" | grep -v '^$' || true)
if [ -n "$problems" ]; then
  while IFS=$'\t' read -r what how; do
    printf 'setup-github-https: %s\n  fix: %s\n' "$what" "$how" >&2
  done <<EOF
$problems
EOF
  exit 1
fi

[ "$changed" = 1 ] || echo "setup-github-https: already configured, nothing changed"
