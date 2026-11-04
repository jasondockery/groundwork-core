# shellcheck shell=bash
# Target: bash 3.2+. Shared by setup-github-https.sh and check-github-https.sh;
# source it, do not run it. Problem reporters print PROBLEM<TAB>FIX lines.

q() { printf '%q' "$1"; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
# git outside any repository, so a repository's own config never counts.
nrepo() { (cd / && env -u GIT_DIR -u GIT_WORK_TREE git "$@"); }

# The file `git config --global` writes, by git's own rule.
global_file() {
  local xdg=${XDG_CONFIG_HOME:-$HOME/.config}/git/config
  if [ -n "${GIT_CONFIG_GLOBAL:-}" ]; then printf '%s\n' "$GIT_CONFIG_GLOBAL"
  elif [ ! -e "$HOME/.gitconfig" ] && [ -e "$xdg" ]; then printf '%s\n' "$xdg"
  else printf '%s\n' "$HOME/.gitconfig"
  fi
}

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

# matches_github SUBSECTION: does credential.<SUBSECTION>.helper apply to
# https://github.com/<owner>/<repo>? Scheme and host compare without case; a
# wildcard is assumed to match.
matches_github() {
  local s
  s=$(lower "$1")
  case "$s" in https://github.com:443*) s=https://github.com${s#https://github.com:443} ;; esac
  case "$s" in ''|*'*'*|https://github.com|https://github.com/*) return 0 ;; esac
  return 1
}

# chain_problems DIR HELPER GH_ENTRY FALLBACK_FIX: compares the helpers git
# runs for github.com (inside repository DIR, or outside any repository when
# DIR is empty, with includes, includeIf and every scope) against
# HELPER, GH_ENTRY. Prints a problem per foreign helper; returns 1 if any.
chain_problems() {
  local dir=$1 helper=$2 ghh=$3 line o rest k v sub list='' reset='' seen=0 n=0 rc=0 done_=''
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    o=${line%%$'\t'*} rest=${line#*$'\t'}
    k=${rest%% *} v=${rest#* }
    [ "$k" = "$rest" ] && v=''
    sub=${k#credential.} sub=${sub%.helper}
    [ "$k" = credential.helper ] && sub=''
    matches_github "$sub" || continue
    o=${o#file:}
    case "$o" in /*) ;; *) [ -z "$dir" ] || o=$dir/$o ;; esac
    if [ -z "$v" ]; then list='' reset=$o$'\t'$k; continue; fi
    [ "$v" = "$helper" ] && seen=1
    list=$list$o$'\t'$k$'\t'$v$'\n'
  done <<EOF
$(if [ -n "$dir" ]; then git -C "$dir" config --includes --show-origin --get-regexp '^credential\..*helper$'
  else nrepo config --includes --show-origin --get-regexp '^credential\..*helper$'; fi 2>/dev/null)
EOF
  report() {
    case "$done_" in *"|$2|$3|"*) return 0 ;; esac
    done_="$done_|$2|$3|"
    printf '%s in %s %s\tgit config --file %s --unset-all %s%s\n' "$3" "$2" "$1" "$(q "$2")" "$(q "$3")" "$4"
    rc=1
  }
  case "$list" in
    *$'\t'"$helper"$'\n'*) ;;
    *) if [ "$seen" = 1 ] && [ -n "$reset" ]; then
         report "resets the github.com chain after the owner helper" "${reset%%$'\t'*}" "${reset#*$'\t'}" \
           "   # if a chezmoi template writes it, drop that block from the template"
       elif [ "$seen" = 0 ]; then
         printf 'git does not run the owner helper for github.com\t%s\n' "$4"; rc=1
       fi ;;
  esac
  while IFS=$'\t' read -r o k v; do
    [ -n "$k" ] || continue
    n=$((n + 1))
    if [ "$n" -eq 1 ] && [ "$v" = "$helper" ]; then continue; fi
    if [ "$n" -eq 2 ] && [ "$v" = "$ghh" ]; then continue; fi
    if [ "$n" -gt 2 ]; then
      report "runs after gh's helper, so it is sent every token git approves" "$o" "$k" \
        "   # re-add it above the github.com section if other hosts need it"
    else
      report "runs ahead of the owner helper for github.com" "$o" "$k" ""
    fi
  done <<EOF
$list
EOF
  return $rc
}

# map_problems OWNER WANT TARGET: what the helper sees for ghaccount.OWNER
# (global config with includes) must be exactly one value, WANT, from TARGET.
# An empty WANT means the value git uses now.
map_problems() {
  local owner=$1 want=$2 target=$3 o v n=0 last='' all='' fixes=''
  while IFS=$'\t' read -r o v; do
    [ -n "$o" ] || continue
    n=$((n + 1)) last=$v
    all="$all${all:+, }$v (${o#file:})"
  done <<EOF
$(nrepo config --global --includes --show-origin --get-all "ghaccount.$owner" 2>/dev/null)
EOF
  [ -n "$want" ] || want=$last
  [ "$n" -le 1 ] && [ "$last" = "$want" ] && return 0
  while IFS=$'\t' read -r o v; do
    o=${o#file:}
    [ -n "$o" ] || continue
    if [ "$v" != "$want" ] || ! [ "$o" -ef "$target" ]; then
      case "$fixes" in *"$(q "$o") "*) continue ;; esac
      fixes="$fixes${fixes:+; }git config --file $(q "$o") --unset-all ghaccount.$owner"
    fi
  done <<EOF
$(nrepo config --global --includes --show-origin --get-all "ghaccount.$owner" 2>/dev/null)
EOF
  [ -n "$fixes" ] || fixes="git config --file $(q "$target") --replace-all ghaccount.$owner $want"
  printf 'ghaccount.%s has more than one value or not the expected one; the helper uses %s; values: %s\t%s\n' \
    "$owner" "$last" "$all" "$fixes"
  return 1
}
