#!/usr/bin/env bash
# Reference implementation of the commit identity contract (docs/commit-identity.md).
# Environment repos vendor or reference this file from the `core` pin and wire
# it into git hooks. This script only checks; it never edits git config.
#
#   commit-identity-guard.sh commit-msg MSG_FILE
#   commit-identity-guard.sh pre-push REMOTE URL   (ref lines on stdin)
#   commit-identity-guard.sh doctor
#
# Rules: no Co-authored-by line (any case); author and committer must not
# match a line of the user-level denylist; Agent-Session: is allowed.
set -u

denylist_file() {
  printf '%s\n' "${GROUNDWORK_COMMIT_DENYLIST:-${XDG_CONFIG_HOME:-$HOME/.config}/groundwork/commit-denylist}"
}

fail() { printf 'commit-identity-guard: %s\n' "$*" >&2; }

# check_text MESSAGE_TEXT -> 0 ok, 1 bad
check_message() {
  if printf '%s\n' "$1" | grep -v '^#' | grep -qiE '^[[:space:]]*co-authored-by[[:space:]]*:'; then
    fail "Co-authored-by trailer is not allowed"
    return 1
  fi
}

# check_ident LABEL "Name <email>" -> 0 ok, 1 bad
check_ident() {
  local f line
  f=$(denylist_file)
  [ -r "$f" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    line=${line#"${line%%[![:space:]]*}"}
    line=${line%"${line##*[![:space:]]}"}
    case "$line" in ''|'#'*) continue ;; esac
    if printf '%s' "$2" | grep -qiF -- "$line"; then
      fail "$1 matches the local denylist ($f)"
      return 1
    fi
  done < "$f"
}

check_commit() {
  local sha=$1 rc=0
  check_message "$(git log -1 --format=%B "$sha")" || { fail "  in commit $sha"; rc=1; }
  check_ident author "$(git log -1 --format='%an <%ae>' "$sha")" || { fail "  in commit $sha"; rc=1; }
  check_ident committer "$(git log -1 --format='%cn <%ce>' "$sha")" || { fail "  in commit $sha"; rc=1; }
  return $rc
}

mode_commit_msg() {
  local rc=0
  [ -f "${1:-}" ] || { fail "commit-msg needs the message file"; return 2; }
  check_message "$(cat "$1")" || rc=1
  check_ident author "$(git var GIT_AUTHOR_IDENT | sed 's/ [0-9]* [+-][0-9]*$//')" || rc=1
  check_ident committer "$(git var GIT_COMMITTER_IDENT | sed 's/ [0-9]* [+-][0-9]*$//')" || rc=1
  return $rc
}

# Checks every commit the push would publish that the pushed-to remote does
# not already have: local tip, minus the remote's old tip when it is known
# locally, minus that remote's tracking refs. Commits already on that remote
# (such as its main merged into a PR branch) are skipped. Commits fetched from
# any other remote are still checked. A push to a bare URL matches no tracking
# refs, and missing or stale ones only widen the check, so it fails closed.
mode_pre_push() {
  local remote=${1:-} lsha rsha sha rc=0 shas old blocked=0
  while read -r _ lsha _ rsha; do
    case "$lsha" in *[!0]*) ;; *) continue ;; esac   # deleting a ref
    old=
    if case "$rsha" in *[!0]*) true ;; *) false ;; esac \
       && git cat-file -e "$rsha^{commit}" 2>/dev/null; then
      old="^$rsha"
    fi
    shas=$(git rev-list "$lsha" ${old:+"$old"} --not "--remotes=${remote:-*}") \
      || { fail "rev-list failed for $lsha; refusing push"; rc=1; continue; }
    for sha in $shas; do
      check_commit "$sha" || { rc=1; blocked=1; }
    done
  done
  if [ "$blocked" = 1 ]; then
    fail "commits already on the remote-tracking refs of ${remote:-the remote} are skipped;"
    fail "if a commit above is already on the remote, run git fetch and push again"
  fi
  return $rc
}

mode_doctor() {
  local rc=0 s="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json" f
  f=$(denylist_file)
  if [ -r "$f" ]; then echo "ok: denylist at $f"; else echo "note: no denylist at $f (identity rule inactive)"; fi
  if [ -n "$(git config user.name)" ] && [ -n "$(git config user.email)" ]; then
    echo "ok: git identity set (Codex and other agents inherit it)"
  else
    echo "FAIL: git user.name or user.email unset"; rc=1
  fi
  if [ -r "$s" ] && python3 -I -c '
import json,sys
a=json.load(open(sys.argv[1])).get("attribution")
sys.exit(0 if isinstance(a,dict) and a.get("commit")=="" and a.get("pr")=="" else 1)' "$s"; then
    echo "ok: Claude Code attribution commit and pr are empty"
  else
    echo "FAIL: $s needs \"attribution\": {\"commit\": \"\", \"pr\": \"\"}"; rc=1
  fi
  echo "manual: Cursor attribution off is a UI setting this script cannot read"
  return $rc
}

case "${1:-}" in
  commit-msg) shift; mode_commit_msg "$@" ;;
  pre-push) shift; mode_pre_push "$@" ;;
  doctor) mode_doctor ;;
  *) echo "usage: $0 commit-msg FILE | pre-push REMOTE URL | doctor" >&2; exit 2 ;;
esac
