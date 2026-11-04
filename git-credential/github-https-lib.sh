# shellcheck shell=bash
# Target: bash 3.2+. Shared by setup-github-https.sh and check-github-https.sh;
# source it, do not run it.

q() { printf '%q' "$1"; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
# git outside any repository, so a repository's own config never counts.
nrepo() { (cd / && env -u GIT_DIR -u GIT_WORK_TREE git "$@"); }
# The Groundwork-owned file setup regenerates and the global config includes.
owned_file() { printf '%s\n' "${XDG_CONFIG_HOME:-$HOME/.config}/groundwork/github-https.gitconfig"; }

# included FILE: does the global config (with includes) read FILE?
included() {
  local o
  while IFS= read -r o; do
    o=${o#file:}
    [ -n "$o" ] && [ "$o" -ef "$1" ] && return 0
  done <<EOF
$(nrepo config --global --includes --show-origin --list 2>/dev/null | cut -f1 | sort -u)
EOF
  return 1
}

# probe DIR OWNER: asks git itself which account it uses for OWNER's
# repositories, from DIR (or outside any repository when DIR is empty).
# Prints "user <name>", "quit" or "none". `git credential fill` only asks the
# helpers; it stores nothing (approve and reject are never called here). It
# does run the configured helpers, which may have side effects such as a
# keychain prompt; the reset at the start of our chain keeps earlier helpers
# out. stdin carries only the request, and git never prompts. Only the
# username line is kept: the password is dropped inside the pipe, never stored.
probe() {
  local out user
  out=$( { printf 'protocol=https\nhost=github.com\npath=%s/groundwork-doctor-probe.git\n\n' "$2" \
      | (cd "${1:-/}" && env -u GIT_DIR -u GIT_WORK_TREE GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never \
           git credential fill 2>&3) | sed -n 's/^username=/user /p'; } 3>&1 )
  user=$(printf '%s\n' "$out" | sed -n '/^user /{p;q;}')
  if [ -n "$user" ]; then printf '%s\n' "$user"
  else case "$out" in *"told us to quit"*) echo quit ;; *) echo none ;; esac
  fi
}
