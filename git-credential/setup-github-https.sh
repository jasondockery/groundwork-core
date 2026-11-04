#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Idempotent setup for GitHub over HTTPS with
# per-owner gh accounts. Platform installers call it; see README.md.
#
#   setup-github-https.sh [--map OWNER=ACCOUNT]... [--ssh-alias HOST]... [--helper PATH]
#
# Writes only the user's global git config (git config --global, which honors
# GIT_CONFIG_GLOBAL) and gh's git_protocol. It never reads or edits ssh config.
# A second run with the same arguments changes nothing.
set -eu -o pipefail

here=$(cd "$(dirname "$0")" && pwd -P)
helper=$here/owner-credential-helper.sh
maps=()
aliases=()

usage() {
  echo "usage: ${0##*/} [--map OWNER=ACCOUNT]... [--ssh-alias HOST]... [--helper PATH]" >&2
  exit 64
}
die() { printf 'setup-github-https: %s\n' "$*" >&2; exit "${2:-1}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --map) [ $# -ge 2 ] || usage; maps+=("$2"); shift 2 ;;
    --ssh-alias) [ $# -ge 2 ] || usage; aliases+=("$2"); shift 2 ;;
    --helper) [ $# -ge 2 ] || usage; helper=$2; shift 2 ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done

# Validate every argument before the first write.
for m in ${maps[@]+"${maps[@]}"}; do
  owner=${m%%=*} account=${m#*=}
  case "$m" in *=*) ;; *) die "--map needs OWNER=ACCOUNT: $m" 64 ;; esac
  case "$owner" in [A-Za-z]*) ;; *) die "owner must start with a letter (git config key): $owner" 64 ;; esac
  case "$owner$account" in *[!A-Za-z0-9-]*) die "owner and account are letters, digits and hyphens: $m" 64 ;; esac
  [ -n "$account" ] && [ "${account#-}" = "$account" ] || die "bad account in $m" 64
done
for a in ${aliases[@]+"${aliases[@]}"}; do
  case "$a" in ''|-*|*[!A-Za-z0-9._-]*) die "bad ssh host alias: $a" 64 ;; esac
done
[ -x "$helper" ] || die "helper not executable: $helper"
gh=$("$helper" gh-path) || die "gh not found; install it or set GROUNDWORK_GH"
# Helper values are run through the shell by git; keep them unquoted and safe.
for p in "$helper" "$gh"; do
  case "$p" in /*) ;; *) die "not an absolute path: $p" ;; esac
  case "$p" in *[!A-Za-z0-9/._+@~-]*) die "path has characters git would split: $p" ;; esac
done

changed=0
cfg() { git config --global "$@"; }
note() { printf 'setup-github-https: %s\n' "$*"; changed=1; }

key=credential.https://github.com
if [ "$(cfg --get "$key.useHttpPath" || true)" != true ]; then
  cfg "$key.useHttpPath" true
  note "set $key.useHttpPath true"
fi

# Chain: empty reset (drops osxkeychain or store from wider scopes), the owner
# helper, then gh's helper for owners with no mapping.
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
  if [ "$(cfg --get "ghaccount.$owner" || true)" != "$account" ]; then
    cfg "ghaccount.$owner" "$account"
    note "map owner $owner to gh account $account"
  fi
done

proto() { "$gh" config get -h github.com git_protocol </dev/null 2>/dev/null || true; }
if [ "$(proto)" != https ]; then
  "$gh" config set git_protocol https </dev/null
  [ "$(proto)" = https ] || "$gh" config set -h github.com git_protocol https </dev/null
  note "set gh git_protocol https"
fi

[ "$changed" = 1 ] || echo "setup-github-https: already configured, nothing changed"
