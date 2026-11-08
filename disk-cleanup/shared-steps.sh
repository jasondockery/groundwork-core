# shellcheck shell=bash
# Steps every environment can use. A steps file names them through dc_step.
# Each step is a pair of functions, called by name from disk-cleanup.sh.
# shellcheck disable=SC2034,SC2154,SC2317,SC2329 # Called by name; the runner owns DC_* and dc_*.
#
# dc_plan_<id> reads only. It sets DC_PLAN_STATE to ready, nothing, unavailable,
# or elsewhere, and DC_PLAN_TEXT to one line a person can read. A ready step also
# sets DC_PLAN_COMMAND (what runs, or how to do it by hand). An ask-first step
# also sets DC_PLAN_QUESTION and DC_PLAN_KEY, an identity of what the question
# covers; it is compared again just before acting.
#
# dc_act_<id> changes the machine only through dc_mutate, which screens the
# command against the never-touch list and bounds it. It may set DC_ACT_TEXT.

dc_declare_shared_commands() {
  dc_allow_command docker builder prune --all --force --filter "until=$DC_DOCKER_BUILD_CACHE_AGE"
  dc_allow_command docker image prune --all --force
  dc_allow_command pnpm store prune
  # Later arguments pin the cache path the plan checked.
  dc_allow_command_prefix npm cache clean --force
}

# ---- Docker --------------------------------------------------------------------

# Returns 0 when Docker is reachable, local, and on its own builder. Otherwise
# sets DC_PLAN_TEXT to the reason. Never starts Docker.
dc_docker_usable() {
  local name host status=0 driver
  if ! command -v docker >/dev/null 2>&1; then
    DC_PLAN_TEXT="Docker is not installed"
    return 1
  fi
  for name in DOCKER_HOST DOCKER_CONTEXT DOCKER_CONFIG BUILDX_BUILDER; do
    if [[ -n "${!name:-}" ]]; then
      DC_PLAN_TEXT="$name is set, and cleanup acts only on the local Docker context and its own builder"
      return 1
    fi
  done
  dc_query "docker context" docker context inspect --format '{{.Endpoints.docker.Host}}' || status=$?
  if [[ "$status" -ne 0 ]]; then
    DC_PLAN_TEXT="the Docker context could not be read"
    return 1
  fi
  host="$(head -n 1 "$dc_output")"
  case "$host" in
    *[[:cntrl:]]*)
      DC_PLAN_TEXT="Docker returned an unsafe endpoint"
      return 1
      ;;
    unix://?*) ;;
    *)
      DC_PLAN_TEXT="the Docker endpoint is not local"
      return 1
      ;;
  esac
  status=0
  dc_query "docker info" docker info --format '{{.ServerVersion}}' || status=$?
  if [[ "$status" -ne 0 ]]; then
    DC_PLAN_TEXT="Docker is not running, and cleanup does not start it"
    return 1
  fi
  # Without the buildx plugin, builder prune runs on the daemon itself.
  status=0
  dc_query "docker buildx version" docker buildx version || status=$?
  [[ "$status" -eq 0 ]] || return 0
  status=0
  dc_query "docker buildx inspect" docker buildx inspect || status=$?
  if [[ "$status" -ne 0 ]]; then
    DC_PLAN_TEXT="the selected buildx builder could not be inspected"
    return 1
  fi
  driver="$(awk '$1 == "Driver:" { print $2; exit }' "$dc_output")"
  if [[ "$driver" != docker ]]; then
    DC_PLAN_TEXT="the selected buildx builder is not the daemon's own"
    return 1
  fi
}

# Sets dc_df_total, dc_df_active, dc_df_size, and dc_df_reclaimable for one row
# of docker system df. Returns 1 when the row is missing.
dc_docker_df_row() { # type
  local status=0 row
  dc_query "docker system df" docker system df --format '{{.Type}}|{{.TotalCount}}|{{.Active}}|{{.Size}}|{{.Reclaimable}}' || status=$?
  [[ "$status" -eq 0 ]] || return 1
  row="$(awk -F '|' -v wanted="$1" '$1 == wanted { print; exit }' "$dc_output" | dc_clean_text)"
  [[ -n "$row" ]] || return 1
  IFS='|' read -r _ dc_df_total dc_df_active dc_df_size dc_df_reclaimable <<<"$row"
}

dc_docker_is_empty_size() { # size text such as 0B or 0B (0%)
  case "$1" in
    0B | "0B "*) return 0 ;;
  esac
  return 1
}

dc_plan_docker_build_cache() {
  dc_docker_usable || return 0
  if ! dc_docker_df_row "Build Cache"; then
    DC_PLAN_TEXT="the Docker build cache size could not be read"
    return 0
  fi
  if dc_docker_is_empty_size "$dc_df_size"; then
    DC_PLAN_STATE="nothing"
    DC_PLAN_TEXT="the build cache is empty"
    return 0
  fi
  DC_PLAN_STATE="ready"
  DC_PLAN_TEXT="the build cache is $dc_df_size; entries unused for over $DC_DOCKER_BUILD_CACHE_AGE go."
  DC_PLAN_COMMAND="docker builder prune --all --force --filter until=$DC_DOCKER_BUILD_CACHE_AGE"
}

# The endpoint or builder can change after the plan read it, so check again at the
# last moment. Returns 77, a refusal, with the reason in DC_ACT_TEXT.
dc_docker_still_usable() {
  if ! dc_docker_usable; then
    DC_ACT_TEXT="not run: $DC_PLAN_TEXT."
    return 77
  fi
}

dc_act_docker_build_cache() {
  local status=0
  dc_docker_still_usable || return "$?"
  dc_mutate "docker builder prune" docker builder prune --all --force --filter "until=$DC_DOCKER_BUILD_CACHE_AGE" || status=$?
  [[ "$status" -eq 0 ]] || return "$status"
  DC_ACT_TEXT="$(grep -E '^Total' "$dc_output" | tail -n 1 | dc_clean_text | tr '\t' ' ' || true)"
}

# An identity for what image prune would act on: every image and every container,
# and the size the question states.
dc_docker_key() {
  local status=0 images
  dc_query "docker image list" docker image ls --all --quiet --no-trunc || status=$?
  [[ "$status" -eq 0 ]] || return 1
  images="$(LC_ALL=C sort "$dc_output")"
  status=0
  dc_query "docker container list" docker ps --all --quiet --no-trunc || status=$?
  [[ "$status" -eq 0 ]] || return 1
  DC_PLAN_KEY="$(printf '%s\n' "$images" | cat - "$dc_output" | LC_ALL=C sort | cksum) $dc_df_reclaimable"
}

dc_plan_docker_images() {
  local unused
  dc_docker_usable || return 0
  if ! dc_docker_df_row "Images"; then
    DC_PLAN_TEXT="the Docker image sizes could not be read"
    return 0
  fi
  if dc_docker_is_empty_size "$dc_df_reclaimable"; then
    DC_PLAN_STATE="nothing"
    DC_PLAN_TEXT="every image is in use"
    return 0
  fi
  if ! dc_docker_key; then
    DC_PLAN_TEXT="the Docker image list could not be read"
    return 0
  fi
  unused="?"
  if [[ "$dc_df_total" =~ ^[0-9]+$ && "$dc_df_active" =~ ^[0-9]+$ ]]; then
    unused=$((dc_df_total - dc_df_active))
  fi
  DC_PLAN_STATE="ready"
  DC_PLAN_TEXT="$unused unused image(s), $dc_df_reclaimable reclaimable of $dc_df_size."
  DC_PLAN_COMMAND="docker image prune --all --force"
  DC_PLAN_QUESTION="Remove $unused unused Docker image(s), $dc_df_reclaimable? Containers and volumes stay, and removed images download again when needed."
}

dc_act_docker_images() {
  local status=0
  dc_docker_still_usable || return "$?"
  dc_mutate "docker image prune" docker image prune --all --force || status=$?
  [[ "$status" -eq 0 ]] || return "$status"
  DC_ACT_TEXT="$(grep -E '^Total' "$dc_output" | tail -n 1 | dc_clean_text | tr '\t' ' ' || true)"
}

# ---- npm -----------------------------------------------------------------------

# Sets dc_npm_cache. Returns nonzero with DC_PLAN_TEXT set when it cannot be used.
dc_npm_cache_path() {
  local status=0
  if ! command -v npm >/dev/null 2>&1; then
    DC_PLAN_TEXT="npm is not installed"
    return 1
  fi
  dc_query "npm config get cache" npm config get cache || status=$?
  if [[ "$status" -ne 0 ]]; then
    DC_PLAN_TEXT="npm did not say where its cache is"
    return 1
  fi
  dc_npm_cache="$(head -n 1 "$dc_output")"
  case "$dc_npm_cache" in
    *[[:cntrl:]]*)
      DC_PLAN_TEXT="npm returned an unsafe cache path"
      return 1
      ;;
    /*) ;;
    *)
      DC_PLAN_TEXT="npm returned a cache path that is not absolute"
      return 1
      ;;
  esac
  if dc_path_protected "$dc_npm_cache"; then
    DC_PLAN_TEXT="its cache is at a protected path: $DC_PROTECT_REASON"
    return 1
  fi
  if ! dc_canonicalize "$dc_npm_cache"; then
    DC_PLAN_TEXT="its cache path could not be resolved safely"
    return 1
  fi
  dc_npm_cache="$dc_canonical"
}

dc_plan_npm_cache() {
  local limit_kib=$((DC_NPM_CACHE_CLEAN_MIB * 1024)) status=0
  dc_npm_cache_path || return 0
  if [[ ! -d "$dc_npm_cache" ]]; then
    DC_PLAN_STATE="nothing"
    DC_PLAN_TEXT="there is no cache yet"
    return 0
  fi
  dc_measure_kib "$dc_npm_cache" || status=$?
  if [[ "$status" -ne 0 ]]; then
    DC_PLAN_TEXT="the cache size could not be measured"
    return 0
  fi
  if [[ "$dc_kib" -lt "$limit_kib" ]]; then
    DC_PLAN_STATE="nothing"
    DC_PLAN_TEXT="$(dc_format_kib "$dc_kib"), under the $(dc_format_kib "$limit_kib") limit"
    return 0
  fi
  DC_PLAN_STATE="ready"
  DC_PLAN_TEXT="$(dc_format_kib "$dc_kib"), over the $(dc_format_kib "$limit_kib") limit."
  DC_PLAN_COMMAND="npm cache clean --force --cache $(dc_quote_argv "$dc_npm_cache")"
}

dc_act_npm_cache() {
  local before="$dc_kib" status=0 after_status=0
  # Pinned to the path the plan checked: npm's own answer could change by now.
  dc_mutate "npm cache clean" npm cache clean --force --cache "$dc_npm_cache" || status=$?
  [[ "$status" -eq 0 ]] || return "$status"
  dc_measure_kib "$dc_npm_cache" || after_status=$?
  if [[ "$after_status" -eq 0 && "$dc_kib" -le "$before" ]]; then
    DC_ACT_TEXT="Freed $(dc_format_kib "$((before - dc_kib))")."
  else
    DC_ACT_TEXT="The size afterwards could not be measured."
  fi
}

# ---- Trash ---------------------------------------------------------------------

# A steps file sets DC_TRASH_DIR, and DC_TRASH_LAYOUT=freedesktop for a Trash with
# files/ and info/ folders (the default is plain, macOS's ~/.Trash).
dc_trash_items_dir() {
  if [[ "${DC_TRASH_LAYOUT:-plain}" == freedesktop ]]; then
    dc_trash_items="$DC_TRASH_DIR/files"
  else
    dc_trash_items="$DC_TRASH_DIR"
  fi
}

# Writes the entries NUL-separated to dc_output. .DS_Store is Finder's own and
# does not make the Trash worth asking about.
dc_trash_list() {
  dc_query "list Trash" find "$dc_trash_items" -mindepth 1 -maxdepth 1 ! -name .DS_Store -print0
}

dc_plan_trash() {
  local status=0 count
  if [[ -z "${DC_TRASH_DIR:-}" ]]; then
    DC_PLAN_TEXT="this platform names no Trash folder"
    return 0
  fi
  if [[ -L "$DC_TRASH_DIR" ]]; then
    DC_PLAN_TEXT="$(dc_home_display "$DC_TRASH_DIR") is a symlink"
    return 0
  fi
  dc_trash_items_dir
  if [[ -L "$dc_trash_items" ]]; then
    DC_PLAN_TEXT="$(dc_home_display "$dc_trash_items") is a symlink"
    return 0
  fi
  if [[ ! -d "$dc_trash_items" ]]; then
    DC_PLAN_STATE="nothing"
    DC_PLAN_TEXT="no Trash folder here"
    return 0
  fi
  if dc_path_protected "$dc_trash_items"; then
    DC_PLAN_TEXT="the Trash folder is at a protected path: $DC_PROTECT_REASON"
    return 0
  fi
  if [[ "${DC_TRASH_LAYOUT:-plain}" == freedesktop ]]; then
    if [[ -L "$DC_TRASH_DIR/info" ]]; then
      DC_PLAN_TEXT="$(dc_home_display "$DC_TRASH_DIR/info") is a symlink"
      return 0
    fi
    if dc_path_protected "$DC_TRASH_DIR/info"; then
      DC_PLAN_TEXT="the Trash folder is at a protected path: $DC_PROTECT_REASON"
      return 0
    fi
  fi
  if ! dc_canonicalize "$dc_trash_items"; then
    DC_PLAN_TEXT="the Trash folder could not be resolved safely"
    return 0
  fi
  dc_trash_items_real="$dc_canonical"
  dc_trash_info_real=""
  if [[ "${DC_TRASH_LAYOUT:-plain}" == freedesktop ]]; then
    if ! dc_canonicalize "$DC_TRASH_DIR/info"; then
      DC_PLAN_TEXT="the Trash folder could not be resolved safely"
      return 0
    fi
    dc_trash_info_real="$dc_canonical"
  fi
  dc_trash_list || status=$?
  if [[ "$status" -ne 0 ]]; then
    DC_PLAN_TEXT="it could not be read, which on macOS usually means this terminal lacks Full Disk Access; Finder can still empty it"
    return 0
  fi
  count="$(LC_ALL=C tr -cd '\0' <"$dc_output" | wc -c | tr -d ' ')"
  if [[ "$count" -eq 0 ]]; then
    DC_PLAN_STATE="nothing"
    DC_PLAN_TEXT="the Trash is empty"
    return 0
  fi
  dc_trash_list_file="$dc_output"
  status=0
  dc_measure_kib "$dc_trash_items" || status=$?
  if [[ "$status" -ne 0 ]]; then
    DC_PLAN_TEXT="its size could not be measured, which on macOS usually means this terminal lacks Full Disk Access; Finder can still empty it"
    return 0
  fi
  DC_PLAN_KEY="$(LC_ALL=C tr '\0' '\n' <"$dc_trash_list_file" | LC_ALL=C sort | cksum) $dc_kib"
  DC_PLAN_STATE="ready"
  DC_PLAN_TEXT="$count item(s), $(dc_format_kib "$dc_kib")."
  DC_PLAN_COMMAND="rm -rf each item, keeping any that holds a Git checkout"
  DC_PLAN_BY_HAND="empty the Trash in your file manager"
  DC_PLAN_QUESTION="Empty the Trash, $count item(s), $(dc_format_kib "$dc_kib")? This cannot be undone."
}

# Returns 0 when a Trash item holds a Git checkout at any depth, or when the search
# could not finish, so an item that cannot be ruled out stays.
dc_trash_item_holds_checkout() { # item
  local found status=0
  [[ ! -L "$1" && -d "$1" ]] || return 1
  found="$(find "$1" -name .git -print 2>/dev/null)" || status=$?
  [[ "$status" -ne 0 || -n "$found" ]]
}

# Runs in its own process group under one deadline. It works from inside the folder
# the plan checked, so a path swapped for a symlink since then cannot redirect rm. A
# trashed folder holding a Git checkout stays: the never-touch list covers it
# wherever it sits.
dc_trash_worker() { # list kept-file
  local entry name
  if [[ -L "$dc_trash_items" ]] || ! cd -P -- "$dc_trash_items" 2>/dev/null \
    || [[ "$(pwd -P)" != "$dc_trash_items_real" ]]; then
    echo "    The Trash folder changed after it was checked, so nothing was removed."
    return 3
  fi
  while IFS= read -r -d '' entry; do
    name="${entry##*/}"
    [[ -n "$name" && "$entry" == "$dc_trash_items/$name" ]] || continue
    if dc_trash_item_holds_checkout "./$name"; then
      printf '%s\n' "$name" >>"$2"
      continue
    fi
    rm -rf -- "./$name" || continue
    if [[ -n "$dc_trash_info_real" ]]; then
      (
        cd -P -- "$DC_TRASH_DIR/info" 2>/dev/null \
          && [[ "$(pwd -P)" == "$dc_trash_info_real" ]] \
          && rm -f -- "./$name.trashinfo"
      ) || true
    fi
  done <"$1"
}

dc_act_trash() {
  local before="$dc_kib" status=0 kept="$dc_work/trash-kept" kept_count=0 left=0 list_status=0 size_status=0 name
  : >"$kept"
  printf '    Removing the Trash items listed above.\n'
  dc_output=""
  dc_bounded "empty Trash" "$DC_STEP_DEADLINE_SECONDS" - dc_trash_worker "$dc_trash_list_file" "$kept" || status=$?
  [[ "$status" -eq 0 ]] || return "$status"
  kept_count="$(awk 'END { print NR + 0 }' "$kept")"
  dc_trash_list || list_status=$?
  [[ "$list_status" -ne 0 ]] || left="$(LC_ALL=C tr -cd '\0' <"$dc_output" | wc -c | tr -d ' ')"
  dc_measure_kib "$dc_trash_items" || size_status=$?
  dc_output=""
  if [[ "$size_status" -eq 0 && "$dc_kib" -le "$before" ]]; then
    DC_ACT_TEXT="Freed $(dc_format_kib "$((before - dc_kib))")."
  else
    DC_ACT_TEXT="The size afterwards could not be measured."
  fi
  if [[ "$kept_count" -gt 0 ]]; then
    DC_ACT_TEXT="$DC_ACT_TEXT Kept $kept_count item(s) that hold a Git checkout or could not be fully searched; remove those yourself."
    while IFS= read -r name; do
      printf '    Kept: %s\n' "$(printf '%s' "$name" | dc_clean_text)"
    done <"$kept"
  fi
  # What remains is unknown, so this cannot be called cleared.
  if [[ "$list_status" -ne 0 ]]; then
    printf '    The Trash could not be read afterwards, so what remains is unknown.\n'
    return 1
  fi
  if [[ "$left" -gt "$kept_count" ]]; then
    printf '    %s item(s) could not be removed.\n' "$((left - kept_count))"
    return 1
  fi
}
