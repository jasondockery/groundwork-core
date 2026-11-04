#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Idempotent setup for GitHub over HTTPS with
# per-owner gh accounts. Platform installers call it; see README.md.
#
#   setup-github-https.sh [--file PATH] [--map OWNER=ACCOUNT]...
#                         [--ssh-alias HOST]... [--helper PATH]
#
# Installs the owner helper to a stable path, then writes the user's global git
# config (git config --global, which honors GIT_CONFIG_GLOBAL), or PATH with
# --file for a file the global config includes, and gh's git_protocol. It
# never reads or edits ssh config. A second run with the same arguments
# changes nothing. Exits 1 when a helper it does not own would still run after
# gh's (for example a later `[credential] helper = osxkeychain`), so "already
# configured" is only printed when git really uses this chain.
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
if [ -n "$file" ]; then
  case "$file" in /*) ;; *) die "--file needs an absolute path: $file" 64 ;; esac
  scope=(--file "$file")
else
  scope=(--global)
fi
gh=$("$here/owner-credential-helper.sh" gh-path) || die "gh not found; install it or set GROUNDWORK_GH"
check_path "$gh" 1

changed=0
[ -z "$file" ] || mkdir -p "$(dirname "$file")"
cfg() { git config "${scope[@]}" "$@"; }
note() { printf 'setup-github-https: %s\n' "$*"; changed=1; }

# Install the helper atomically; skip when the bytes already match.
if [ "$helper" = "$install_dir/owner-credential-helper.sh" ]; then
  src=$here/owner-credential-helper.sh
  if ! { cmp -s "$src" "$helper" && [ -x "$helper" ]; }; then
    mkdir -p "$install_dir"
    tmp=$(mktemp "$install_dir/.owner-credential-helper.XXXXXX")
    trap 'rm -f "$tmp"' EXIT INT TERM
    cp "$src" "$tmp"
    chmod 0755 "$tmp"
    mv -f "$tmp" "$helper"
    trap - EXIT INT TERM
    note "installed $helper"
  fi
fi

key=credential.https://github.com
if [ "$(cfg --get-all "$key.useHttpPath" || true)" != true ]; then
  cfg --replace-all "$key.useHttpPath" true
  note "set $key.useHttpPath true"
fi

# Chain: empty reset (drops osxkeychain or store from wider scopes), the owner
# helper, then gh's helper for owners with no mapping. The swap below is not
# atomic; if it is interrupted, a rerun repairs it.
# The trailing x keeps an extra empty entry at the end from comparing equal.
want=$(printf '\n%s\n%s\nx' "$helper" "!$gh auth git-credential")
have=$(cfg --get-all "$key.helper" || true; echo x)
if [ "$have" != "$want" ]; then
  n=$(printf '%s' "${have%x}" | wc -l | tr -d ' ')
  cfg --unset-all "$key.helper" || true
  cfg --add "$key.helper" ""
  cfg --add "$key.helper" "$helper"
  cfg --add "$key.helper" "!$gh auth git-credential"
  note "set $key.helper chain: reset, $helper, $gh auth git-credential (replaced $n entries)"
fi

prefixes=("git@github.com:" "ssh://git@github.com/")
for a in ${aliases[@]+"${aliases[@]}"}; do prefixes+=("git@$a:" "ssh://git@$a/"); done
have=$(cfg --get-all url.https://github.com/.insteadOf || true)
for p in "${prefixes[@]}"; do
  if ! printf '%s\n' "$have" | grep -qxF -- "$p"; then
    cfg --add url.https://github.com/.insteadOf "$p"
    have=$(printf '%s\n%s' "$have" "$p")
    note "rewrite $p to https://github.com/"
  fi
done

for m in ${maps[@]+"${maps[@]}"}; do
  owner=${m%%=*} account=${m#*=}
  if [ "$(cfg --get-all "ghaccount.$owner" || true)" != "$account" ]; then
    cfg --replace-all "ghaccount.$owner" "$account"
    note "map owner $owner to gh account $account"
  fi
done

proto() { "$gh" config get -h github.com git_protocol </dev/null 2>/dev/null || true; }
if [ "$(proto)" != https ]; then
  "$gh" config set git_protocol https </dev/null
  [ "$(proto)" = https ] || "$gh" config set -h github.com git_protocol https </dev/null
  note "set gh git_protocol https"
fi

# What git will actually run, across files and includes.
eff=$(effective_chain)
want_eff=$(printf '%s\n%s' "$helper" "!$gh auth git-credential")
got_eff=$(printf '%s' "$eff" | cut -f3)
if [ "$got_eff" != "$want_eff" ]; then
  if [ -n "$file" ] && ! printf '%s' "$eff" | cut -f1 | grep -qxF -- "$file"; then
    printf 'setup-github-https: %s is not included from the global git config, so git does not use it\n' "$file" >&2
    printf 'setup-github-https: fix: git config --global --add include.path %s\n' "$file" >&2
  else
    printf 'setup-github-https: git also runs helpers this script does not own for github.com:\n' >&2
    while IFS=$'\t' read -r o k v; do
      case "$v" in ''|"$helper"|"!$gh auth git-credential") continue ;; esac
      printf '  %s in %s\n' "$k" "$o" >&2
    done <<EOF
$eff
EOF
    printf 'setup-github-https: remove them, or move them before the github.com section; check-github-https.sh prints the commands\n' >&2
  fi
  exit 1
fi

[ "$changed" = 1 ] || echo "setup-github-https: already configured, nothing changed"
