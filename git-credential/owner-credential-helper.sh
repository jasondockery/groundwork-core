#!/usr/bin/env bash
# Target: bash 3.2+ (stock macOS). Git credential helper that picks the gh
# account by repository owner. See git-credential/README.md.
#
#   owner-credential-helper.sh get|store|erase   (git credential protocol)
#   owner-credential-helper.sh gh-path           (print the gh it would run)
#
# On `get` for https://github.com/<owner>/..., it looks up
# `git config ghaccount.<owner>` and prints that account's token from
# `gh auth token -u <account>`. Anything else prints nothing and exits 0, so
# the next helper in the chain (gh's own) answers. The token is written only
# to stdout, in protocol form. `store` and `erase` do nothing.
set -u

# gh lookup order: GROUNDWORK_GH, `git config groundwork.ghPath`, the mise
# shim (stable across gh upgrades), then PATH.
gh_path() {
  local p
  for p in "${GROUNDWORK_GH:-}" "$(git config --get groundwork.ghPath 2>/dev/null)" \
           "$HOME/.local/share/mise/shims/gh"; do
    if [ -n "$p" ] && [ -x "$p" ]; then printf '%s\n' "$p"; return 0; fi
  done
  command -v gh 2>/dev/null
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
  [ "$protocol" = https ] && [ "$host" = github.com ] || return 0
  owner=${path%%/*}
  # A git config variable name: a letter, then letters, digits and hyphens.
  case "$owner" in [A-Za-z]*) ;; *) return 0 ;; esac
  case "$owner" in *[!A-Za-z0-9-]*) return 0 ;; esac
  account=$(git config --get "ghaccount.$owner" 2>/dev/null) || return 0
  case "$account" in ''|-*|*[!A-Za-z0-9-]*) return 0 ;; esac
  gh=$(gh_path) || return 0
  token=$(GH_PROMPT_DISABLED=1 "$gh" auth token -h github.com -u "$account" </dev/null 2>/dev/null) || return 0
  case "$token" in ''|*[[:space:]]*) return 0 ;; esac
  printf 'username=%s\npassword=%s\n' "$account" "$token"
}

case "${1:-}" in
  get) get; exit 0 ;;
  store|erase) cat >/dev/null; exit 0 ;;
  gh-path) gh_path ;;
  *) echo "usage: $0 get|store|erase|gh-path" >&2; exit 64 ;;
esac
