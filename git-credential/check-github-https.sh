#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Read-only doctor check for GitHub over
# HTTPS with per-owner gh accounts. See README.md.
#
#   check-github-https.sh [--file PATH] [--ssh-alias HOST]... [--root DIR]... [REPO]...
#
# Checks the chain setup wrote, the helper chain git really runs (outside any
# repository and inside each repository given, so includeIf and local config
# count), the installed helper and gh paths, gh's git protocol, the owner map
# as the helper sees it, that every mapped account is logged in to gh, that
# each --ssh-alias is rewritten to HTTPS, and, for the given repos (and the
# repos found up to three levels under each --root): SSH GitHub remotes, and
# owners with no mapping while more than one gh account is logged in. Prints
# ok:, note:, FAIL: and fix: lines; exits 1 when anything fails. Writes nothing.
set -u

here=$(cd "$(dirname "$0")" && pwd -P)
# shellcheck source-path=SCRIPTDIR source=github-https-lib.sh
. "$here/github-https-lib.sh"
default_helper=${XDG_DATA_HOME:-$HOME/.local/share}/groundwork/git-credential/owner-credential-helper.sh
usage() { echo "usage: ${0##*/} [--file PATH] [--ssh-alias HOST]... [--root DIR]... [REPO]..." >&2; exit 64; }
file=$(default_file)
repos=()
roots=()
aliases=()
while [ $# -gt 0 ]; do
  case "$1" in
    --file) [ $# -ge 2 ] || usage; file=$2; shift 2 ;;
    --ssh-alias) [ $# -ge 2 ] || usage; aliases+=("$2"); shift 2 ;;
    --root) [ $# -ge 2 ] || usage; roots+=("$2"); shift 2 ;;
    -*) usage ;;
    *) repos+=("$1"); shift ;;
  esac
done
case "$file" in /*) ;; *) echo "check-github-https: --file needs an absolute path" >&2; exit 64 ;; esac
target=$file

rc=0
ok() { printf 'ok: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*"; rc=1; }
fix() { printf '  fix: %s\n' "$*"; }
note() { printf 'note: %s\n' "$*"; }
seen_problems=
# problems PREFIX: print PROBLEM<TAB>FIX lines from stdin as FAIL/fix, once
# each. Feed it with a here-document, not a pipe, so rc is kept.
problems() {
  local what how
  while IFS="$tab" read -r what how; do
    [ -n "$what" ] || continue
    # A problem already reported outside any repo is not repeated per repo;
    # one found in several repos is reported for each.
    case "$seen_problems" in *"|$what|"*|*"|$1$what|"*) continue ;; esac
    seen_problems="$seen_problems|$1$what|"
    fail "$1$what"
    fix "$how"
  done
}

key=credential.https://github.com
# The owner map as the helper sees it: global config with includes.
mapped=$(nrepo config --global --includes --get-regexp '^ghaccount\.' 2>/dev/null | awk '{print $1}' | sort -u)
raw=()
while IFS= read -r line; do raw+=("$line"); done <<EOF
$(git config --file "$target" --get-all "$key.helper" 2>/dev/null; echo x)
EOF
unset 'raw[${#raw[@]}-1]'
helper=${raw[1]:-}
ghh=${raw[2]:-}
ghh_path=${ghh#!} ghh_path=${ghh_path% auth git-credential}
[ "!$ghh_path auth git-credential" = "$ghh" ] && [ -n "$ghh_path" ] || ghh_path=

# The setup command that regenerates the target file as it is now.
setup_cmd=$(q "$here/setup-github-https.sh")
[ "$file" = "$(default_file)" ] || setup_cmd="$setup_cmd --file $(q "$file")"
if [ -n "$helper" ] && [ "$helper" != "$default_helper" ] && [ -x "$helper" ]; then
  setup_cmd="$setup_cmd --helper $(q "$helper")"
fi
while read -r k v; do
  [ -n "$k" ] && setup_cmd="$setup_cmd --map ${k#ghaccount.}=$v"
done <<EOF
$(git config --file "$target" --get-regexp '^ghaccount\.' 2>/dev/null)
EOF
have_aliases=$(git config --file "$target" --get-all url.https://github.com/.insteadOf 2>/dev/null \
  | sed -n 's/^git@\(.*\):$/\1/p' | grep -vx github.com || true)
for a in $have_aliases ${aliases[@]+"${aliases[@]}"}; do
  case " $setup_cmd " in *" --ssh-alias $a "*) ;; *) setup_cmd="$setup_cmd --ssh-alias $a" ;; esac
done

if [ "$(nrepo config --type=bool --get-urlmatch credential.useHttpPath https://github.com/o/r 2>/dev/null)" = true ]; then
  ok "$key.useHttpPath is true"
else
  fail "$key.useHttpPath is not true, so helpers never see the repository owner"
  fix "$setup_cmd"
fi

chain_ok=0
if [ "${#raw[@]}" -eq 3 ] && [ -z "${raw[0]}" ] && [ -n "$ghh_path" ] \
   && case "$helper" in /*) true ;; *) false ;; esac; then
  chain_ok=1
  ok "$key.helper chain in $target: reset, owner helper, gh"
  if [ ! -x "$helper" ]; then
    fail "owner helper is missing or not executable: $helper"
    fix "$setup_cmd"
  fi
  if [ ! -x "$ghh_path" ]; then
    fail "gh helper points at a missing gh: $ghh_path"
    fix "$setup_cmd"
  elif case "$ghh_path" in */mise/installs/*) true ;; *) false ;; esac; then
    fail "gh helper uses a versioned mise path that breaks on upgrade: $ghh_path"
    fix "$setup_cmd"
  fi
else
  fail "$key.helper chain in $target is missing or out of order (want: empty reset, owner helper, !<gh> auth git-credential)"
  fix "$setup_cmd"
fi
if ! included "$file"; then
  fail "$file is not included from the global git config, so git does not read it"
  fix "$setup_cmd"
elif [ "$chain_ok" = 1 ]; then
  problems "" <<EOF
$(chain_problems "" "$helper" "$ghh" "$setup_cmd"
  for k in $mapped; do
    map_problems "${k#ghaccount.}" "$(git config --file "$target" --get "$k" 2>/dev/null)" "$target"
  done)
EOF
fi

accounts=
gh=$("$here/owner-credential-helper.sh" gh-path 2>/dev/null) || gh=
if [ -z "$gh" ]; then
  fail "gh not found"
  fix "install gh, or set GROUNDWORK_GH to its path"
else
  if [ "$("$gh" config get -h github.com git_protocol </dev/null 2>/dev/null)" = https ]; then
    ok "gh git_protocol is https"
  else
    fail "gh git_protocol for github.com is not https"
    fix "$(q "$gh") config set -h github.com git_protocol https"
  fi
  # Only account names are taken from the status text; it is never printed.
  accounts=$(GH_PROMPT_DISABLED=1 "$gh" auth status --hostname github.com </dev/null 2>&1 \
    | sed -nE 's/.*Logged in to github\.com account ([A-Za-z0-9-]+).*/\1/p' | sort -u)
fi
n_accounts=$(printf '%s' "$accounts" | grep -c . || true)

for k in $mapped; do
  v=$(nrepo config --global --includes --get "$k")
  case $'\n'"$accounts"$'\n' in
    *$'\n'"$v"$'\n'*) ok "$k: $v is logged in to gh" ;;
    *) fail "$k maps to $v, which is not logged in to gh, so git stops for that owner"
       fix "gh auth login --hostname github.com --git-protocol https   # sign in as $v" ;;
  esac
done

for a in ${aliases[@]+"${aliases[@]}"}; do
  for u in "git@$a:o/r.git" "ssh://git@$a/o/r.git"; do
    case "$(nrepo ls-remote --get-url "$u" 2>/dev/null)" in
      https://github.com/*) ;;
      *) fail "ssh alias $a: ${u%o/r.git} is not rewritten to https://github.com/"; fix "$setup_cmd" ;;
    esac
  done
done

for r in ${roots[@]+"${roots[@]}"}; do
  while IFS= read -r g; do repos+=("${g%/.git}"); done <<EOF
$(find "$r" -maxdepth 3 -name .git -prune -print 2>/dev/null)
EOF
done

ssh_host() {
  local a
  case "$1" in github.com|ssh.github.com|github-*) return 0 ;; esac
  for a in ${aliases[@]+"${aliases[@]}"}; do [ "$1" = "$(lower "$a")" ] && return 0; done
  return 1
}

# The pushInsteadOf entry that sends PUSHURL (configured as RAW) back to SSH.
push_culprit() {
  local o k v base line
  while IFS="$tab" read -r o line; do
    [ -n "$line" ] || continue
    o=${o#file:}
    case "$o" in /*) ;; *) o=$1/$o ;; esac
    k=${line%% *} v=${line#* }
    base=${k#url.} base=${base%.pushinsteadof}
    case "$2" in "$v"*) ;; *) continue ;; esac
    case "$3" in "$base"*) printf '%s\t%s\n' "$o" "$k"; return 0 ;; esac
  done <<EOF
$(git -C "$1" config --show-origin --get-regexp '^url\..*\.pushinsteadof$' 2>/dev/null)
EOF
  return 1
}

owners=
for r in ${repos[@]+"${repos[@]}"}; do
  [ -n "$r" ] || continue
  if ! git -C "$r" rev-parse --git-dir >/dev/null 2>&1; then
    fail "not a git repository: $r"
    fix "pass a repository path, or use --root DIR"
    continue
  fi
  # Inside the repository, includeIf and local config count too.
  if [ "$chain_ok" = 1 ]; then
    problems "$r: " <<EOF
$(chain_problems "$r" "$helper" "$ghh" "$setup_cmd")
EOF
  fi
  # `git remote -v` shows each URL after insteadOf and pushInsteadOf rewriting.
  while read -r name url kind; do
    [ -n "$url" ] || continue
    lurl=$(lower "$url") path='' prefix=''
    if [[ "$lurl" =~ ^https://([^/@]+@)?github\.com(:443)?/(.*)$ ]]; then
      path=${BASH_REMATCH[3]}
    elif [[ "$lurl" =~ ^([^@/:]+@)?([a-z0-9._-]+):([^/].*)$ ]] && ssh_host "${BASH_REMATCH[2]}"; then
      prefix="${url%%:*}:" path=${BASH_REMATCH[3]} host=${BASH_REMATCH[2]}
    elif [[ "$lurl" =~ ^ssh://([^@/]+@)?([a-z0-9._-]+)(:[0-9]+)?/(.*)$ ]] && ssh_host "${BASH_REMATCH[2]}"; then
      prefix=${url:0:$((${#url} - ${#BASH_REMATCH[4]}))} path=${BASH_REMATCH[4]}
      host=${BASH_REMATCH[2]}${BASH_REMATCH[3]}
    fi
    [ -n "$path" ] || continue
    if [ -n "$prefix" ]; then
      rawurl=$(git -C "$r" config --get "remote.$name.pushurl" 2>/dev/null || git -C "$r" config --get "remote.$name.url" 2>/dev/null)
      culprit=
      [ "$kind" = "(push)" ] && culprit=$(push_culprit "$r" "$rawurl" "$url")
      if [ -n "$culprit" ]; then
        fail "$r: remote $name pushes over SSH because ${culprit#*"$tab"} in ${culprit%%"$tab"*} rewrites pushes back to SSH"
        fix "git config --file $(q "${culprit%%"$tab"*}") --unset-all ${culprit#*"$tab"}"
      else
        fail "$r: remote $name uses SSH ($prefix${path%%/*}/...) and no insteadOf rewrites it"
        case "$host" in
          github.com|ssh.github.com|*:*) fix "git -C $(q "$r") remote set-url $(q "$name") $(q "https://github.com/$path")" ;;
          *) fix "$setup_cmd --ssh-alias $host" ;;
        esac
      fi
    fi
    owners=$(printf '%s\n%s\t%s' "$owners" "${path%%/*}" "$r")
  done <<EOF
$(git -C "$r" remote -v 2>/dev/null | sort -u)
EOF
done

seen=
while IFS="$tab" read -r owner r; do
  [ -n "$owner" ] || continue
  case " $seen " in *" $owner "*) continue ;; esac
  seen="$seen $owner"
  case "$owner" in
    [a-z]*) ;;
    *) note "owner $owner ($r) cannot be mapped (git config keys start with a letter); gh's active account serves it"; continue ;;
  esac
  if nrepo config --global --includes --get "ghaccount.$owner" >/dev/null 2>&1; then
    continue
  elif [ "$n_accounts" -gt 1 ]; then
    fail "owner $owner ($r) has no gh account mapping and $n_accounts accounts are logged in, so gh uses whichever is active"
    # shellcheck disable=SC2086 # account names hold no spaces or globs
    fix "$setup_cmd --map $owner=<account>   # one of: $(printf '%s ' $accounts)"
  else
    note "owner $owner ($r) has no mapping; gh's active account serves it"
  fi
done <<EOF
$owners
EOF

exit $rc
