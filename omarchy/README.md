# Omarchy plugins

Every `groundwork-omarchy-*` repository installs the same shell plugins from
this list, through `omarchy plugin add`. The directory is data. Installers and
Hyprland configuration stay in the environment repository.

`scripts/omarchy-plugins.py` in
[groundwork-omarchy-mac-arm64](https://github.com/jasondockery/groundwork-omarchy-mac-arm64)
reads [`plugins.json`](plugins.json) and applies it. Later batches edit the
list.

## Fields

`schemaVersion` is `1`.

`plugins` is the install list. Every entry needs a `reason`: why that plugin
belongs on a Groundwork Omarchy machine. An entry without a reason does not
belong in the file.

| Field | Meaning |
| --- | --- |
| `id` | The `id` in the plugin's `manifest.json` on its default branch. It matches the same id in the [Omarchy plugin catalog](https://plugins.omarchy.org/catalog.json). Ids in this file do not start with `omarchy.`. |
| `repo` | Clone URL from that catalog entry's install command. It starts with `https://github.com/` and ends in `.git`. |
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

## Left out

These plugins stay off the list. `retired` is for plugins the list previously
installed, so these two are recorded here only.

| Id | Reason |
| --- | --- |
| `omaplug` | Duplicates the plugin manager. |
| `io.github.twiking.omasettings` | OmaControl replaced it. The OmaSettings README says the plugin continues as OmaControl. |
