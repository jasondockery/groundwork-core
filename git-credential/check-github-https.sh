#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Read-only doctor check for GitHub over
# HTTPS with per-owner gh accounts. See README.md.
#
#   check-github-https.sh [--file PATH] [--ssh-alias HOST]... [--root DIR]... [REPO]...
#
# Checks the helper chain git really runs (system and global scopes with
# includes), the installed helper and gh paths it names, gh's git protocol,
# that every mapped account is logged in to gh, that each --ssh-alias is
# rewritten to HTTPS, and, for the given repos (and the repos found up to three
# levels under each --root): SSH GitHub remotes, and owners with no mapping
# while more than one gh account is logged in. Prints ok:, note:, FAIL: and
# fix: lines; exits 1 when anything fails. Writes nothing.
set -u

here=$(cd "$(dirname "$0")" && pwd -P)
# shellcheck source-path=SCRIPTDIR source=github-https-lib.sh
. "$here/github-https-lib.sh"
default_helper=${XDG_DATA_HOME:-$HOME/.local/share}/groundwork/git-credential/owner-credential-helper.sh
file=
repos=()
roots=()
aliases=()
while [ $# -gt 0 ]; do
  case "$1" in
    --file) [ $# -ge 2 ] || exit 64; file=$2; shift 2 ;;
    --ssh-alias) [ $# -ge 2 ] || exit 64; aliases+=("$2"); shift 2 ;;
    --root) [ $# -ge 2 ] || exit 64; roots+=("$2"); shift 2 ;;
    -*) echo "usage: ${0##*/} [--file PATH] [--ssh-alias HOST]... [--root DIR]... [REPO]..." >&2; exit 64 ;;
    *) repos+=("$1"); shift ;;
  esac
done
if [ -n "$file" ]; then scope=(--file "$file"); scope_s="--file $file"; else scope=(--global); scope_s=--global; fi

rc=0
ok() { printf 'ok: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*"; rc=1; }
fix() { printf '  fix: %s\n' "$*"; }
note() { printf 'note: %s\n' "$*"; }
cfg() { git config "${scope[@]}" --includes "$@" 2>/dev/null; }
# Outside any repository, so a repo's own config never counts.
nrepo() { (cd / && env -u GIT_DIR -u GIT_WORK_TREE git "$@" 2>/dev/null); }

key=credential.https://github.com
mapped=$(cfg --get-regexp '^ghaccount\.' || true)
raw=()
while IFS= read -r line; do raw+=("$line"); done <<EOF
$(git config "${scope[@]}" --get-all "$key.helper" 2>/dev/null; echo x)
EOF
unset 'raw[${#raw[@]}-1]'
helper=${raw[1]:-}
ghh=${raw[2]:-}
ghh_path=$(gh_helper_path "$ghh") || ghh_path=

setup_cmd=$here/setup-github-https.sh
[ -z "$file" ] || setup_cmd="$setup_cmd --file $file"
if [ -n "$helper" ] && [ "$helper" != "$default_helper" ] && [ -x "$helper" ]; then
  setup_cmd="$setup_cmd --helper $helper"
fi
while read -r k v; do
  [ -n "$k" ] && setup_cmd="$setup_cmd --map ${k#ghaccount.}=$v"
done <<EOF
$mapped
EOF
for a in ${aliases[@]+"${aliases[@]}"}; do setup_cmd="$setup_cmd --ssh-alias $a"; done

if [ "$(nrepo config --type=bool --get-urlmatch credential.useHttpPath https://github.com/o/r)" = true ]; then
  ok "$key.useHttpPath is true"
else
  fail "$key.useHttpPath is not true, so helpers never see the repository owner"
  fix "git config $scope_s $key.useHttpPath true"
fi

if [ "${#raw[@]}" -eq 3 ] && [ -z "${raw[0]}" ] && [ -n "$ghh_path" ] \
   && case "$helper" in /*) true ;; *) false ;; esac; then
  ok "$key.helper chain in $scope_s: reset, owner helper, gh"
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
  # The chain git really runs, across files and includes.
  eff=$(effective_chain)
  n=0 extra=0
  while IFS=$'\t' read -r o k v; do
    [ -n "$k" ] || continue
    n=$((n + 1))
    if [ "$n" -eq 1 ] && [ "$v" = "$helper" ]; then continue; fi
    if [ "$n" -eq 2 ] && [ "$v" = "$ghh" ]; then continue; fi
    extra=1
    if [ "$n" -gt 2 ]; then
      fail "$k in $o runs after gh's helper, so it is sent every token git approves"
    else
      fail "$k in $o runs ahead of the owner helper for github.com"
    fi
    fix "git config --file $o --unset-all $k   # re-add it above the github.com section if other hosts need it"
  done <<EOF
$eff
EOF
  if [ -n "$file" ] && ! printf '%s' "$eff" | cut -f1 | grep -qxF -- "$file"; then
    fail "$file is not included from the global git config, so git does not use it"
    fix "git config --global --add include.path $file"
  elif [ "$extra" = 0 ] && [ "$n" -eq 2 ]; then
    ok "git runs only the owner helper and gh for github.com"
  elif [ "$extra" = 0 ]; then
    fail "git does not run the configured chain for github.com"
    fix "$setup_cmd"
  fi
else
  fail "$key.helper chain in $scope_s is missing or out of order (want: empty reset, owner helper, !<gh> auth git-credential)"
  fix "$setup_cmd"
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
    fail "$k maps to $v, which is not logged in to gh, so git stops for that owner"
    fix "gh auth login --hostname github.com --git-protocol https   # sign in as $v"
  fi
done <<EOF
$mapped
EOF

for a in ${aliases[@]+"${aliases[@]}"}; do
  for u in "git@$a:o/r.git" "ssh://git@$a/o/r.git"; do
    case "$(nrepo ls-remote --get-url "$u")" in
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
  for a in ${aliases[@]+"${aliases[@]}"}; do [ "$1" = "$a" ] && return 0; done
  return 1
}

# The pushInsteadOf entry that sends PUSHURL (configured as RAW) back to SSH.
push_culprit() {
  local o k v base line
  while IFS=$'\t' read -r o line; do
    k=${line%% *} v=${line#* }
    base=${k#url.} base=${base%.pushinsteadof}
    case "$2" in "$v"*) ;; *) continue ;; esac
    case "$3" in "$base"*) printf '%s\t%s\n' "${o#file:}" "$k"; return 0 ;; esac
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
  # `git remote -v` shows each URL after insteadOf and pushInsteadOf rewriting.
  while read -r name url kind; do
    [ -n "$url" ] || continue
    path='' prefix=''
    if [[ "$url" =~ ^https://([^/@]+@)?github\.com/(.*)$ ]]; then
      path=${BASH_REMATCH[2]}
    elif [[ "$url" =~ ^([^@/:]+@)?([A-Za-z0-9._-]+):([^/].*)$ ]] && ssh_host "${BASH_REMATCH[2]}"; then
      prefix="${BASH_REMATCH[1]}${BASH_REMATCH[2]}:" path=${BASH_REMATCH[3]}
    elif [[ "$url" =~ ^ssh://([^@/]+@)?([A-Za-z0-9._-]+)(:[0-9]+)?/(.*)$ ]] && ssh_host "${BASH_REMATCH[2]}"; then
      prefix="ssh://${BASH_REMATCH[1]}${BASH_REMATCH[2]}${BASH_REMATCH[3]}/" path=${BASH_REMATCH[4]}
    fi
    [ -n "$path" ] || continue
    if [ -n "$prefix" ]; then
      rawurl=$(git -C "$r" config --get "remote.$name.pushurl" 2>/dev/null || git -C "$r" config --get "remote.$name.url" 2>/dev/null)
      culprit=
      [ "$kind" = "(push)" ] && culprit=$(push_culprit "$r" "$rawurl" "$url")
      if [ -n "$culprit" ]; then
        fail "$r: remote $name pushes over SSH because ${culprit#*$'\t'} in ${culprit%%$'\t'*} rewrites pushes back to SSH"
        fix "git config --file ${culprit%%$'\t'*} --unset-all ${culprit#*$'\t'}"
      else
        fail "$r: remote $name uses SSH ($prefix${path%%/*}/...) and no insteadOf rewrites it"
        fix "git config $scope_s --add url.https://github.com/.insteadOf $prefix"
      fi
    fi
    owners=$(printf '%s\n%s\t%s' "$owners" "${path%%/*}" "$r")
  done <<EOF
$(git -C "$r" remote -v 2>/dev/null | sort -u)
EOF
done

seen=
while IFS=$'\t' read -r owner r; do
  [ -n "$owner" ] || continue
  case " $seen " in *" $owner "*) continue ;; esac
  seen="$seen $owner"
  case "$owner" in
    [A-Za-z]*) ;;
    *) note "owner $owner ($r) cannot be mapped (git config keys start with a letter); gh's active account serves it"; continue ;;
  esac
  if cfg --get "ghaccount.$owner" >/dev/null; then
    continue
  elif [ "$n_accounts" -gt 1 ]; then
    fail "owner $owner ($r) has no gh account mapping and $n_accounts accounts are logged in, so gh uses whichever is active"
    # shellcheck disable=SC2086 # account names hold no spaces or globs
    fix "git config $scope_s ghaccount.$owner <account>   # one of: $(printf '%s ' $accounts)"
  else
    note "owner $owner ($r) has no mapping; gh's active account serves it"
  fi
done <<EOF
$owners
EOF

exit $rc
