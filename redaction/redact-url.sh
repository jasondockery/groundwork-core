#!/usr/bin/env bash
# Reference implementation of the credential redaction contract
# (docs/credential-redaction.md). Source it for `redact_url`, or run it as
# `redact-url.sh URL`. It only transforms text; it reads and writes nothing.
#
# Userinfo becomes `***@` (a bare `git@` SSH user is kept). The cut is at the
# last `@` after the scheme, not at the end of the authority, so a password
# containing "/", "?" or "#" cannot leak. The query and fragment are dropped.
# GitHub-token-shaped segments (gh[pousr]_ + 36 or more characters,
# github_pat_ + 22 or more) are masked anywhere.
redact_url() {
  local url="$1" scheme="" rest userinfo
  url="$(printf '%s' "$url" | sed -E 's/gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}/***/g')"
  if [[ "$url" =~ ^([A-Za-z][A-Za-z0-9+.-]*://)(.*)$ ]]; then
    scheme="${BASH_REMATCH[1]}"
    rest="${BASH_REMATCH[2]}"
  else
    rest="$url"
  fi
  if [[ "$rest" == *@* ]]; then
    userinfo="${rest%@*}"
    rest="${rest##*@}"
    if [[ "$userinfo" == git ]]; then
      rest="git@${rest}"
    else
      rest="***@${rest}"
    fi
  fi
  rest="${rest%%[?#]*}"
  printf '%s%s\n' "$scheme" "$rest"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  [[ $# -eq 1 ]] || { printf 'usage: %s URL\n' "${0##*/}" >&2; exit 2; }
  redact_url "$1"
fi
