#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Read-only doctor check for GitHub over
# HTTPS with per-owner gh accounts. See README.md.
#
#   check-github-https.sh [--helper PATH] [--root DIR]... [REPO]...
#
# Checks the helper chain, gh's git protocol, that every mapped account is
# logged in to gh, and, for the given repos (and the repos found up to three
# levels under each --root): SSH GitHub remotes no insteadOf rewrites, and
# owners with no mapping while more than one gh account is logged in.
# Prints ok:, FAIL: and fix: lines; exits 1 when anything fails. Writes nothing.
set -u

here=$(cd "$(dirname "$0")" && pwd -P)
helper=$here/owner-credential-helper.sh
repos=()
roots=()
while [ $# -gt 0 ]; do
  case "$1" in
    --helper) [ $# -ge 2 ] || exit 64; helper=$2; shift 2 ;;
    --root) [ $# -ge 2 ] || exit 64; roots+=("$2"); shift 2 ;;
    -h|--help) echo "usage: ${0##*/} [--helper PATH] [--root DIR]... [REPO]..." >&2; exit 64 ;;
    *) repos+=("$1"); shift ;;
  esac
done

rc=0
ok() { printf 'ok: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*"; rc=1; }
fix() { printf '  fix: %s\n' "$*"; }
note() { printf 'note: %s\n' "$*"; }

key=credential.https://github.com
mapped=$(git config --get-regexp '^ghaccount\.' 2>/dev/null || true)
setup_cmd=$here/setup-github-https.sh
[ "$helper" = "$here/owner-credential-helper.sh" ] || setup_cmd="$setup_cmd --helper $helper"
while read -r k v; do
  [ -n "$k" ] && setup_cmd="$setup_cmd --map ${k#ghaccount.}=$v"
done <<EOF
$mapped
EOF

if [ "$(git config --get "$key.useHttpPath" 2>/dev/null)" = true ]; then
  ok "$key.useHttpPath is true"
else
  fail "$key.useHttpPath is not true, so helpers never see the repository owner"
  fix "git config --global $key.useHttpPath true"
fi

# Expect exactly: empty reset, the owner helper, gh's helper.
chain=()
while IFS= read -r line; do chain+=("$line"); done <<EOF
$(git config --get-all "$key.helper" 2>/dev/null; echo x)
EOF
unset 'chain[${#chain[@]}-1]'
ghh=${chain[2]:-}
ghh_path=${ghh#!}
ghh_path=${ghh_path% auth git-credential}
if [ "${#chain[@]}" -eq 3 ] && [ -z "${chain[0]}" ] && [ "${chain[1]}" = "$helper" ] \
   && [ "$ghh" != "$ghh_path" ] && [ "!$ghh_path auth git-credential" = "$ghh" ]; then
  ok "$key.helper chain: reset, owner helper, gh"
else
  fail "$key.helper chain is missing or out of order (want: empty reset, $helper, !<gh> auth git-credential)"
  fix "$setup_cmd"
  ghh_path=
fi
if [ ! -x "$helper" ]; then
  fail "owner helper is not executable: $helper"
  fix "$setup_cmd"
fi
if [ -n "$ghh_path" ]; then
  if [ ! -x "$ghh_path" ]; then
    fail "gh helper points at a missing gh: $ghh_path"
    fix "$setup_cmd"
  elif case "$ghh_path" in */mise/installs/*) true ;; *) false ;; esac; then
    fail "gh helper uses a versioned mise path that breaks on upgrade: $ghh_path"
    fix "$setup_cmd"
  fi
fi

accounts=
gh=$("$helper" gh-path 2>/dev/null) || gh=
if [ -z "$gh" ]; then
  fail "gh not found"
  fix "install gh, or set GROUNDWORK_GH to its path"
else
  if [ "$("$gh" config get -h github.com git_protocol </dev/null 2>/dev/null)" = https ]; then
    ok "gh git_protocol is https"
  else
    fail "gh git_protocol for github.com is not https"
    fix "$gh config set -h github.com git_protocol https"
  fi
  # Only account names are taken from the status text; it is never printed.
  accounts=$(GH_PROMPT_DISABLED=1 "$gh" auth status --hostname github.com </dev/null 2>&1 \
    | sed -nE 's/.*Logged in to github\.com account ([A-Za-z0-9-]+).*/\1/p' | sort -u)
fi
n_accounts=$(printf '%s' "$accounts" | grep -c . || true)

while read -r k v; do
  [ -n "$k" ] || continue
  if printf '%s\n' "$accounts" | grep -qxF -- "$v"; then
    ok "$k: $v is logged in to gh"
  else
    fail "$k maps to $v, which is not logged in to gh"
    fix "gh auth login --hostname github.com --git-protocol https   # sign in as $v"
  fi
done <<EOF
$mapped
EOF

for r in ${roots[@]+"${roots[@]}"}; do
  while IFS= read -r g; do repos+=("${g%/.git}"); done <<EOF
$(find "$r" -maxdepth 3 -name .git -prune -print 2>/dev/null)
EOF
done

owners=
for r in ${repos[@]+"${repos[@]}"}; do
  [ -n "$r" ] || continue
  if ! git -C "$r" rev-parse --git-dir >/dev/null 2>&1; then
    fail "not a git repository: $r"
    fix "pass a repository path, or use --root DIR"
    continue
  fi
  # `git remote -v` shows each URL after insteadOf rewriting.
  while read -r name url _; do
    [ -n "$url" ] || continue
    path='' prefix=''
    if [[ "$url" =~ ^https://([^/@]+@)?github\.com/(.*)$ ]]; then
      path=${BASH_REMATCH[2]}
    elif [[ "$url" =~ ^([^@/:]+@)?(github\.com|ssh\.github\.com|github-[A-Za-z0-9._-]+):([^/].*)$ ]]; then
      prefix="${BASH_REMATCH[1]}${BASH_REMATCH[2]}:" path=${BASH_REMATCH[3]}
    elif [[ "$url" =~ ^ssh://([^@/]+@)?(github\.com|ssh\.github\.com|github-[A-Za-z0-9._-]+)(:[0-9]+)?/(.*)$ ]]; then
      prefix="ssh://${BASH_REMATCH[1]}${BASH_REMATCH[2]}${BASH_REMATCH[3]}/" path=${BASH_REMATCH[4]}
    fi
    [ -n "$path" ] || continue
    if [ -n "$prefix" ]; then
      fail "$r: remote $name uses SSH ($prefix${path%%/*}/...) and no insteadOf rewrites it"
      fix "git config --global --add url.https://github.com/.insteadOf $prefix"
    fi
    owners=$(printf '%s\n%s\t%s' "$owners" "${path%%/*}" "$r")
  done <<EOF
$(git -C "$r" remote -v 2>/dev/null | awk '{print $1, $2}' | sort -u)
EOF
done

seen=
while IFS="$(printf '\t')" read -r owner r; do
  [ -n "$owner" ] || continue
  case " $seen " in *" $owner "*) continue ;; esac
  seen="$seen $owner"
  if git config --get "ghaccount.$owner" >/dev/null 2>&1; then
    continue
  elif [ "$n_accounts" -gt 1 ]; then
    fail "owner $owner ($r) has no gh account mapping and $n_accounts accounts are logged in, so gh uses whichever is active"
    # shellcheck disable=SC2086 # account names hold no spaces or globs
    fix "git config --global ghaccount.$owner <account>   # one of: $(printf '%s ' $accounts)"
  else
    note "owner $owner ($r) has no mapping; gh's active account serves it"
  fi
done <<EOF
$owners
EOF

exit $rc
