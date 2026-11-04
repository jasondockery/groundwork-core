#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Read-only doctor check for GitHub over
# HTTPS with per-owner gh accounts. See README.md.
#
#   check-github-https.sh [--root DIR]... [REPO]...
#
# It asks git instead of modelling it. Prerequisites: the owned file is
# included from the global config, the helper it names is executable, and
# every mapped account is logged in to gh. Routing: for each mapped owner,
# `git credential fill` (see probe in the lib) must return the mapped account,
# outside any repository and inside each repository given or found up to three
# levels under each --root. Prints ok:, FAIL: and fix: lines; exits 1 when
# anything fails. Writes nothing and prints no token.
set -u

here=$(cd "$(dirname "$0")" && pwd -P)
# shellcheck source-path=SCRIPTDIR source=github-https-lib.sh
. "$here/github-https-lib.sh"
usage() { echo "usage: ${0##*/} [--root DIR]... [REPO]..." >&2; exit 64; }
file=$(owned_file)
repos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --root) [ $# -ge 2 ] || usage; while IFS= read -r g; do [ -z "$g" ] || repos+=("${g%/.git}"); done <<EOF
$(find "$2" -maxdepth 3 -name .git -prune -print 2>/dev/null)
EOF
      shift 2 ;;
    -*) usage ;;
    *) repos+=("$1"); shift ;;
  esac
done

rc=0
ok() { printf 'ok: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n  fix: %s\n' "$1" "$2"; rc=1; }

# Owner map and helper as setup wrote them; the setup command that rewrites them.
mapped=$(git config --file "$file" --get-regexp '^ghaccount\.' 2>/dev/null || true)
helper=$(git config --file "$file" --get-all credential.https://github.com.helper 2>/dev/null | sed -n 2p)
setup_cmd=$(q "$here/setup-github-https.sh")
case "$helper" in ''|*/groundwork/git-credential/owner-credential-helper.sh) ;; *) setup_cmd="$setup_cmd --helper $(q "$helper")" ;; esac
while read -r k v; do [ -z "$k" ] || setup_cmd="$setup_cmd --map ${k#ghaccount.}=$v"; done <<EOF
$mapped
EOF

if included "$file"; then ok "$file is included"; else fail "$file is not included from the global git config" "$setup_cmd"; fi
if [ -n "$helper" ] && [ -x "$helper" ]; then ok "owner helper $helper"; else fail "owner helper is missing or not executable: ${helper:-none in $file}" "$setup_cmd"; fi

accounts=
gh=$("$here/owner-credential-helper.sh" gh-path 2>/dev/null) || gh=
# Only account names are taken from the status text; it is never printed.
[ -z "$gh" ] || accounts=$(GH_PROMPT_DISABLED=1 "$gh" auth status --hostname github.com </dev/null 2>&1 \
  | sed -nE 's/.*Logged in to github\.com account ([A-Za-z0-9-]+).*/\1/p')
while read -r k v; do
  [ -n "$k" ] || continue
  case $'\n'"$accounts"$'\n' in
    *$'\n'"$v"$'\n'*) ok "$v is logged in to gh" ;;
    *) fail "${k#ghaccount.} maps to $v, which is not logged in to gh" "gh auth login --hostname github.com --git-protocol https   # sign in as $v" ;;
  esac
done <<EOF
$mapped
EOF

# check_routing DIR: each mapped owner's username, as git returns it from DIR.
check_routing() {
  local k v got where=${1:-outside any repository}
  while read -r k v; do
    [ -n "$k" ] || continue
    got=$(probe "$1" "${k#ghaccount.}")
    if [ "$got" = "user $v" ]; then
      ok "${k#ghaccount.} uses $v ($where)"
    elif [ "$got" = quit ]; then
      fail "${k#ghaccount.}: the owner helper stopped git ($where)" "gh auth login --hostname github.com --git-protocol https   # sign in as $v"
    else
      [ "$got" = none ] && got="no username" || got="username ${got#user }"
      fail "${k#ghaccount.}: git credential fill returns $got instead of $v ($where)" \
        "git -C $(q "${1:-/}") config --show-origin --get-regexp '^(credential|ghaccount)\.'   # find what overrides $(q "$file")"
    fi
  done <<EOF
$mapped
EOF
}
check_routing ""
for r in ${repos[@]+"${repos[@]}"}; do
  if git -C "$r" rev-parse --git-dir >/dev/null 2>&1; then check_routing "$r"
  else fail "not a git repository: $r" "pass a repository path, or use --root DIR"
  fi
done

exit $rc
