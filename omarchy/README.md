# Omarchy plugins

Every `groundwork-omarchy-*` repository applies the same shell plugins from
this list. Cloned plugins are installed with `omarchy plugin add`. A built-in
plugin is enabled with `omarchy plugin enable`. The directory is data.
Installers and Hyprland configuration stay in the environment repository.

`scripts/omarchy-plugins.py` in
[groundwork-omarchy-mac-arm64](https://github.com/jasondockery/groundwork-omarchy-mac-arm64)
reads [`plugins.json`](plugins.json) and applies it. Later batches edit the
list.

## Fields

`schemaVersion` is `2`. A version 1 entry has a `repo`, and its id does not
start with `omarchy.`. Version 2 adds a built-in plugin. That plugin ships
with Omarchy, sets `builtIn` to true, omits `repo`, and is only enabled. A
version 1 reader rejects an id such as `omarchy.agents` and rejects a missing
`repo`, so the version number changed.

`plugins` is the install list. Every entry needs a `reason`: why that plugin
belongs on a Groundwork Omarchy machine. An entry without a reason does not
belong in the file.

| Field | Meaning |
| --- | --- |
| `id` | The `id` in the plugin's `manifest.json` on its default branch. It matches the same id in the [Omarchy plugin catalog](https://plugins.omarchy.org/catalog.json). A cloned id does not start with `omarchy.`. A built-in id is the id Omarchy ships. |
| `repo` | Clone URL from that catalog entry's install command. It starts with `https://github.com/` and ends in `.git`. A built-in entry omits `repo`. |
| `builtIn` | Optional. `true` when the plugin ships with Omarchy. The applier runs `omarchy plugin enable` for that id. It does not clone a repository, update a checkout, or run `setup`. |
| `reason` | Why this plugin is on the shared list. Required on every entry. |
| `batch` | The batch that added the entry. Batch 1 is the first shared list. |
| `arch` | Optional. `uname -m` names that install the plugin, such as `aarch64` and `x86_64`. The applier skips an entry whose `arch` omits the machine. |
| `section` | Optional. Bar side when the entry sets one: `left`, `center`, or `right`. Omit it and the plugin keeps its own placement. |
| `setup` | Optional. After the first install, the applier runs `command` from the plugin directory, and again when an update moves that plugin. `needsSudo` is true when the command needs administrator permission. |

`retired` lists plugins this list previously installed and now removes. Each
entry has an `id` and a `reason`. Batch 1 has an empty array.

## Batch 1

Six plugins. Each is batch 1 and is installed on `aarch64` and `x86_64`.

| Id | Reason |
| --- | --- |
| `io.github.mb-jambon.omapods` | Shows AirPods battery and listening modes. Its `setup` builds the daemon. That command installs system packages with `omarchy pkg add`, so `needsSudo` is true. |
| `io.github.wouldja.mouse` | Visual pointer and trackpad controls, including touchpads. It writes `~/.config/hypr/mouse.lua`, which loads after `input.lua`. |
| `io.github.twiking.omacontrol` | An all-in-one settings window. The OmaSettings README says that plugin continues as OmaControl. |
| `io.github.juancasanueva.plugin-manager` | The single plugin manager. Its installs and updates are pinned to verified commits, it has a marketplace browser, and it is more active than omaplug. |
| `davedes.netspeed` | Live network speed. |
| `crmne.mpris` | Media controls with album art. The built-in media widget is absent from the default bar. |

## Batch 2

Three plugins. Each is batch 2 and is applied on `aarch64` and `x86_64`.

| Id | Reason |
| --- | --- |
| `omarchy.agents` | Tracks Claude, Codex, and Grok usage limits. |
| `tornikegomareli.spaces` | Shows the apps open on each workspace and replaces the stock Workspaces bar widget. |
| `harshith.system-monitor` | Shows system load with Apple Silicon sensors and power draw, read from `/proc` and `/sys` without a daemon. |

`omarchy.agents` ships with Omarchy in `shell/plugins/agents`. Omarchy's default
bar already lists it on the right. The applier records that built-in id once,
leaves Omarchy quattro's default right-side placement alone, and never runs
`omarchy plugin enable` again after the id is recorded, so a widget someone
removed stays removed. A bare enable would not restore the right side. The
agents manifest has no `defaultSection`, so Omarchy would place it in
`centerEnd`.

`tornikegomareli.spaces` replaces the stock Workspaces bar widget,
`omarchy.workspaces`. Omarchy's default bar places that widget on the left, in
`bar.layout.left`, beside the menu. The environment applier disables it with
`omarchy plugin disable omarchy.workspaces` when that applier enables Spaces.
That disable is the bar change, and it lives in the environment repository.

## Left out

These plugins stay off the list. `retired` is for plugins the list previously
installed, so these two are recorded here only.

| Id | Reason |
| --- | --- |
| `omaplug` | Duplicates the plugin manager. |
| `io.github.twiking.omasettings` | OmaControl replaced it. The OmaSettings README says the plugin continues as OmaControl. |
