# shellcheck shell=bash
# Target: bash 3.2+. Shared by setup-github-https.sh and check-github-https.sh;
# source it, do not run it. Defines no globals beyond its functions.

# effective_chain: the helpers git runs for https://github.com/<owner>/<repo>,
# from the system and global scopes with includes, in git's read order. An
# empty value resets the list, as git does. One line per entry, after the
# last reset: ORIGIN<TAB>KEY<TAB>VALUE.
effective_chain() {
  local scope line origin rest k v sub out=''
  for scope in --system --global; do
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      origin=${line%%$'\t'*} rest=${line#*$'\t'}
      k=${rest%% *} v=${rest#* }
      [ "$k" = "$rest" ] && v=''
      sub=${k#credential.} sub=${sub%.helper}
      [ "$k" = credential.helper ] && sub=''
      case "$sub" in
        ''|https://github.com|https://github.com/*) ;;
        *) continue ;;
      esac
      if [ -z "$v" ]; then out=''; else out="$out${origin#file:}"$'\t'"$k"$'\t'"$v"$'\n'; fi
    done <<EOF
$(git config "$scope" --includes --show-origin --get-regexp '^credential\..*helper$' 2>/dev/null)
EOF
  done
  printf '%s' "$out"
}

# gh_helper_path VALUE: prints <gh> for "!<gh> auth git-credential", else fails.
gh_helper_path() {
  local p=${1#!}
  p=${p% auth git-credential}
  [ "!$p auth git-credential" = "$1" ] && [ "$p" != "$1" ] && printf '%s\n' "$p"
}
