#!/usr/bin/env bash
# Run the shared redaction vectors against any redact_url implementation.
#
#   check-redact-url.sh CMD [ARG...]
#
# For each vector, runs `CMD ARG... INPUT` and compares its stdout (trailing
# newline removed) with the expected value. Exit 0 when every vector passes,
# 1 when any fails, 2 on usage or a bad vectors file. Set
# REDACT_URL_VECTORS to use another vectors file.
#
# Vector inputs never hold a real-looking token in the file. `{{PREFIX:N}}`
# expands at run time to PREFIX followed by N letters and digits, so
# `{{ghp_:36}}` becomes a full-length, token-shaped value.
set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
vectors=${REDACT_URL_VECTORS:-$here/redact-url-vectors.tsv}

[ $# -ge 1 ] || { printf 'usage: %s CMD [ARG...]\n' "${0##*/}" >&2; exit 2; }
[ -r "$vectors" ] || { printf 'check-redact-url: cannot read %s\n' "$vectors" >&2; exit 2; }

expand() {
  local s=$1 out="" fill
  while [[ "$s" =~ \{\{([A-Za-z_]+):([0-9]+)\}\} ]]; do
    fill=$(printf 'Ab3%.0s' $(seq 1 "${BASH_REMATCH[2]}"))
    out+="${s%%"${BASH_REMATCH[0]}"*}${BASH_REMATCH[1]}${fill:0:${BASH_REMATCH[2]}}"
    s=${s#*"${BASH_REMATCH[0]}"}
  done
  printf '%s' "$out$s"
}

pass=0 fail=0 n=0
while IFS=$'\t' read -r input expected note || [ -n "$input" ]; do
  n=$((n + 1))
  case "$input" in ''|'#'*) continue ;; esac
  if [ -z "${expected+x}" ] || [ -z "$expected" ]; then
    printf 'check-redact-url: line %d has no expected value\n' "$n" >&2
    exit 2
  fi
  in=$(expand "$input")
  want=$(expand "$expected")
  got=$("$@" "$in" 2>/dev/null)
  if [ "$got" = "$want" ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL line %d (%s)\n  input:    %s\n  expected: %s\n  got:      %s\n' \
      "$n" "${note:-no note}" "$in" "$want" "$got"
  fi
done < "$vectors"

printf '%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
