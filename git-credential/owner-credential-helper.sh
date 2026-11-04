#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Git credential helper that picks the gh
# account by repository owner. See git-credential/README.md.
#
#   owner-credential-helper.sh get|store|erase   (git credential protocol)
#   owner-credential-helper.sh gh-path           (print the gh it would run)
#
# On `get` for https://github.com/<owner>/..., it looks up the global
# `ghaccount.<owner>` and prints that account's token from
# `gh auth token -u <account>`. An owner with no mapping, another host, or no
# path prints nothing and exits 0, so the next helper (gh's own) answers. A
# mapped owner whose token cannot be read fails closed: it prints `quit=1`, so
# git stops instead of trying the active gh account, and names the owner and
# account on stderr. The token is written only to stdout, in protocol form.
# `store` and `erase` do nothing. Only the global config (with its includes)
# is read, never a repository's own config.
set -u

# Read from outside any repository, so includeIf and a repository's own
# config never change the answer; setup and the doctor read the same way.
gcfg() { (cd / && env -u GIT_DIR -u GIT_WORK_TREE git config --global --includes "$@" 2>/dev/null); }

# gh lookup order: GROUNDWORK_GH, global `groundwork.ghPath`, the mise shim
# (stable across gh upgrades), then PATH.
gh_path() {
  local p
  for p in "${GROUNDWORK_GH:-}" "$(gcfg --get groundwork.ghPath)" \
           "$HOME/.local/share/mise/shims/gh"; do
    if [ -n "$p" ] && [ -x "$p" ]; then printf '%s\n' "$p"; return 0; fi
  done
  command -v gh 2>/dev/null
}

refuse() {
  printf 'owner-credential-helper: owner %s maps to gh account %s, but %s; fix: gh auth login -h github.com (sign in as %s)\n' \
    "$1" "$2" "$3" "$2" >&2
  printf 'quit=1\n'
}

get() {
  local line protocol="" host="" path="" owner account gh token
  while IFS= read -r line; do
    [ -n "$line" ] || break
    case "$line" in
      protocol=*) protocol=${line#protocol=} ;;
      host=*) host=${line#host=} ;;
      path=*) path=${line#path=} ;;
    esac
  done
  # Git applies the github.com chain to GitHub.com and github.com:443 too.
  protocol=$(printf '%s' "$protocol" | tr '[:upper:]' '[:lower:]')
  host=$(printf '%s' "$host" | tr '[:upper:]' '[:lower:]')
  host=${host%:443}
  [ "$protocol" = https ] && [ "$host" = github.com ] && [ -n "$path" ] || return 0
  owner=${path%%/*}
  # A git config variable name: a letter, then letters, digits and hyphens.
  case "$owner" in [A-Za-z]*) ;; *) return 0 ;; esac
  case "$owner" in *[!A-Za-z0-9-]*) return 0 ;; esac
  # Exit 1 means no mapping; anything higher is a config error: fail closed.
  account=$(gcfg --get "ghaccount.$owner") || {
    [ $? -eq 1 ] || {
      printf 'owner-credential-helper: cannot read ghaccount.%s; fix: run git config --global --includes --get ghaccount.%s to see the error\n' \
        "$owner" "$owner" >&2
      printf 'quit=1\n'
    }
    return 0
  }
  case "$account" in ''|-*|*[!A-Za-z0-9-]*) refuse "$owner" "$account" "that is not an account name"; return 0 ;; esac
  gh=$(gh_path) || { refuse "$owner" "$account" "gh was not found"; return 0; }
  token=$(GH_PROMPT_DISABLED=1 "$gh" auth token -h github.com -u "$account" </dev/null 2>/dev/null) || token=
  case "$token" in ''|*[[:space:]]*) refuse "$owner" "$account" "gh has no token for it"; return 0 ;; esac
  printf 'username=%s\npassword=%s\n' "$account" "$token"
}

case "${1:-}" in
  get) get; exit 0 ;;
  store|erase) cat >/dev/null; exit 0 ;;
  gh-path) gh_path ;;
  *) echo "usage: $0 get|store|erase|gh-path" >&2; exit 64 ;;
esac
