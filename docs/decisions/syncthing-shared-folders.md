# Decision: Syncthing over Tailscale for shared folders

Status: accepted
Date: 2026-10-24
Issue: [groundwork-core#14](https://github.com/jasondockery/groundwork-core/issues/14)
Amended: 2026-10-31, [groundwork-core#47](https://github.com/jasondockery/groundwork-core/issues/47), Obsidian vault

The operational contract is [Syncthing shared folders](../syncthing.md). This page records why that contract exists.

Reviewed on 2026-10-24 against the [Syncthing configuration reference](https://docs.syncthing.net/users/config.html), the [FreeTube data-location page](https://docs.freetubeapp.io/usage/data-location/), [FreeTube issue 370](https://github.com/FreeTubeApp/FreeTube/issues/370), FreeTube 0.25.3, the [Dropbox Linux package index](https://linux.dropbox.com/debian/pool/main/), and the [rclone Google Drive client-id notice](https://rclone.org/drive/#making-your-own-client-id).

The Obsidian section was reviewed on 2026-10-31 against Syncthing's [folder types](https://docs.syncthing.net/users/foldertypes.html), [file versioning](https://docs.syncthing.net/users/versioning.html), [ignoring files](https://docs.syncthing.net/users/ignoring.html), [conflicting changes](https://docs.syncthing.net/users/syncing.html), and [configuration](https://docs.syncthing.net/users/config.html); Obsidian's [Sync your notes across devices](https://obsidian.md/help/sync-notes), [Sync settings and selective syncing](https://obsidian.md/help/sync/settings), and [Switch to Obsidian Sync](https://obsidian.md/help/sync/switch); the community [Obsidian Hub Syncthing page](https://publish.obsidian.md/hub/02+-+Community+Expansions/02.05+All+Community+Expansions/Auxiliary+Tools/Syncthing); and the Syncthing forum thread [Problems with .obsidian folder](https://forum.syncthing.net/t/problems-with-obsidian-folder/25397) (2025-10-01 and 2025-10-02 posts).

## Decision

Syncthing, carried over the existing personal Tailscale tailnet, is how Groundwork shares files across machines. Every `groundwork-mac`, `groundwork-linux`, `groundwork-windows`, and `groundwork-omarchy-mac-arm64` machine installs it and enables it as a user service. It is a default. It is not an opt-in extra.

The shared folder is `~/Shared` (`groundwork-shared`). FreeTube's database files live at `~/Shared/FreeTube` and are a second Syncthing folder, `groundwork-freetube`, with trash-can versioning. The wrapper never pauses `~/Shared`. An index reset of `groundwork-shared` pauses that folder first. A successful reset restarts Syncthing. The unpause waits until a probe fails and the new API answers, then retries. A lost response resumes the same process when `startTime` is unchanged. After a sample has been `scanning` or `scan-waiting` and the latest sample is `idle`, the FreeTube browse must be empty. A paused folder's `state` is `""`. The scan runs when the folder is unpaused. The wrapper still never pauses it. The Omarchy M1 mini (Asahi, aarch64, 16 KiB pages) is the always-on peer, so a laptop still has somewhere to sync when other desktops are asleep.

## Why Syncthing

The machines are no longer all Macs. A folder that depends on iCloud Drive leaves the Omarchy mini, other Linux machines, and Windows outside the share. Syncthing is a peer sync program: each machine holds the folder, and a change on one machine propagates to the others. It has no account and no central copy.

Current packages cover the whole family. Homebrew's `syncthing` formula is 2.1.7 and publishes bottles for Apple Silicon and for Linux arm64 and x86_64. Arch Linux ARM's `extra` repository publishes `syncthing` for aarch64 (2.1.7-1 as of 2026-10-21). Winget publishes `Syncthing.Syncthing` 2.1.7. The same program can run on the Mac, on Linux through the shared engine, on the Windows host, and on the mini.

The tailnet is already the path between these machines. Syncthing rides that path. Device IDs, API keys, and Tailscale addresses stay on the machine.

## Alternatives

### Google Drive via rclone

rclone can copy a folder to Google Drive, including with a client-side encrypted remote. That still puts the files in a Google account. During 2026 Google is retiring rclone's shared OAuth client id, so a working remote needs a private client id and client secret plus a token. Drive is also a scheduled copy to a cloud, which is a different job from a folder that stays live between machines that are sometimes off. Groundwork does not take that account, those secrets, or that quota as the default.

### Dropbox

Dropbox's Linux client packages, including the 2026.09.28 builds in its Debian pool, are amd64 and i386. There is no Linux ARM client. The Omarchy mini is aarch64, so Dropbox cannot be the share that every Groundwork machine joins. Dropbox would also be another cloud account, which is the dependency this decision is leaving.

### Nextcloud

Nextcloud can run on Linux ARM, and distro packages of the desktop client exist for that architecture. The cost is the server: a PHP application, a database, a web server, and TLS, kept patched on a machine that must stay up. That is a service to administer, with accounts in front of a central copy. Groundwork's need is a folder the person's own machines already hold. Syncthing has no server process to operate.

## FreeTube has no native sync

FreeTube 0.25.3, the current Homebrew cask and winget release on the review date, stores subscriptions, history, playlists, and settings as local NeDB files. [Issue 370](https://github.com/FreeTubeApp/FreeTube/issues/370) is still open. On 2026-01-26 the maintainer again described a third-party sync server as out of scope, and described export and import from Data Settings as the only supported way to move data between installs.

There is no supported data-directory setting. Chromium's `--user-data-dir` flag can move the whole profile, and FreeTube's maintainer has said a non-standard Chromium flag is unsupported and must be passed on every launch. Groundwork does not use that flag and does not change any FreeTube preference. The share is the four database files, linked into the package's normal data directory while FreeTube is closed. On 0.25.3 `src/datastores/index.js` checks `statSync(path)?.isSymbolicLink` without calling it, so the check is truthy for an existing path and NeDB receives `realpathSync(path)`. `@seald-io/nedb` 4.1.2 writes `filename~` beside that real path and renames it onto `~/Shared/FreeTube/<name>`. The data-dir symlink survives, and the shared file is the compacted database. The launch path classifies each data-dir name with `lstat` before start, leaves a correct symlink alone after exit, and does not move a data-dir file onto a shared file that is already present. An absent file is not created or migrated while `global` has a live copy. One confirmed create runs when the cluster has no copy. The [shared-folder page](../syncthing.md) is the procedure.

`search-history.db` and `subscription-cache.db` stay in that local directory. Search history is per machine. The subscription cache is rebuilt from the subscriptions in `profiles.db`.

## One machine at a time

NeDB files are append-style. FreeTube assumes it is the only writer. Syncthing will happily sync a file that two running copies append to, and the result is a `*.sync-conflict-*` copy beside the database. FreeTube does not merge those copies. Watching or subscribing on two machines at once can drop history or subscriptions.

Open FreeTube on one machine at a time. Quit FreeTube, and wait until `groundwork-freetube` is up to date, before opening it on another machine. The cheatsheet says Quit, not close the window. Closing the window pauses only that folder, so `~/Shared` keeps syncing. The mini stays on so Syncthing has a peer; FreeTube on the mini is still a writer and follows the same rule. The [shared-folder page](../syncthing.md) has the warning an environment repo can show at launch. A hard lock across machines is the wrong tool: an offline peer would block the machine that is actually in use.

## Obsidian vault

An Obsidian vault is a third folder, `groundwork-obsidian`, so notes reach the Mac, the Omarchy mini, and the other machines without iCloud or a paid sync service. Obsidian's own help names Syncthing as an option and says it works best with one device always on, which is the mini's job here. The [shared-folder page](../syncthing.md#obsidian-vault) is the procedure. Each open point in issue 47 was decided as follows.

### Opt-in per machine, inside a default service

Syncthing stays a default, and so do `groundwork-shared` and `groundwork-freetube`. The vault folder is opt-in per machine: it exists only where the person saved a vault path, and "no vault" is a saved answer. Three things push it that way. The vault is personal writing, not app state Groundwork created. Its path differs between machines, so any default would be a guess, and a guess at the wrong folder shares the wrong notes. And a first pairing between two machines that already have notes could merge two different vaults. The environment repos still ask the question by default, so a person who wants the vault shared does not have to find a setting.

### Trash can, not simple versioning

`groundwork-obsidian` uses trash-can versioning with `cleanoutDays` `0`, the same as FreeTube. Syncthing archives only changes that arrive from another device, so the hazard it covers is a remote delete or overwrite of a note. The trash can keeps one copy per path and replaces it on the next archive. Simple versioning keeps several timestamped copies per path. Notes are edited constantly, so simple versioning would fill `.stversions` with copies of every remote edit, and it still would not be history: a local edit is never archived. One copy per path is enough to undo a bad sync. `cleanoutDays` `0` means a deleted note stays recoverable until a person removes it. Real note history is Obsidian Git or a backup, and the contract says so.

### Ignore lines

The ignore file has three lines, anchored to the vault root: `/.obsidian/workspace.json`, `/.obsidian/workspace-mobile.json`, and `/.obsidian/cache`. The Obsidian Hub's Syncthing page names the two workspace files as the most important ones, because they track open panes and files. A Syncthing forum reply on 2025-10-02 gives the same cause: Obsidian writes `workspace.json` while the copy is in flight. `/.obsidian/cache` is cache data, and the issue named it. The anchor matters because Syncthing matches a pattern without a leading slash at any depth.

Nothing else is ignored. `appearance.json`, `graph.json`, hotkeys, themes, snippets, and `plugins/` stay synced, because they are the vault's settings and the reason to share `.obsidian` at all. Obsidian Sync's own defaults sync main settings, appearance, themes and snippets, hotkeys, and core plugin settings. The forum advice to ignore all of `.obsidian` was set aside: Obsidian's help offers that only for people who want separate settings on each device, and the Hub page warns it stops plugins and configuration from syncing. If a specific plugin's per-device file later causes conflicts, that is one more line, added with a source.

### First pairing is receive-only

Two existing vaults joined as send-and-receive would merge on the first scan. Files only on one side go to the other. A file at the same path with different contents is a conflict, Syncthing renames the copy with the older modification time to `*.sync-conflict-*`, and it propagates conflict copies as normal files. That is the merge the issue says must never happen without a clear prompt.

So pairing creates the folder `receiveonly` on every machine. Syncthing's folder-type page says a receive-only folder keeps local changes and does not send them, and that a locally changed file later changed by the cluster resolves with the cluster as the winner and a local conflict copy that is not sent. The local notes stay on disk. `groundwork syncthing-pair obsidian-promote` is the one switch to `sendreceive`. It requires this machine's own completion to be 100 first, so it never waits on a receive-only peer that cannot catch up. It then lists `GET /rest/db/localchanged` and sorts each entry into new, changed, or deleted. A receive-only folder records local edits and local deletions as well as new files, and after promotion an edit replaces that note everywhere and a deletion deletes it everywhere, with one copy left in each machine's trash can. So it promotes silently only when that list is empty, and otherwise needs a typed yes after saying what each class will do and whether another machine is already a source. Machines are promoted one at a time, each after the previous promote has reached it. The first machine promoted is the source, confirmed by that same prompt. Groundwork never calls revert on this folder, because revert deletes files that exist only on that machine.

A per-machine flag naming the source at `add` time was set aside. It would be a second way in, and it would let `add` on the wrong machine publish a vault before the person had seen what was in it.

### Path rules

The path is the saved one, absolute, in the user's home, under the state key `syncthing.obsidian_vault` that every environment repo shares. Setup asks, `add` asks when setup did not, and a run with no terminal skips the folder. `groundwork syncthing-pair obsidian-vault` changes or clears the answer. Every check compares resolved real paths, case-insensitively on macOS, so a symlink or a case difference cannot slip past it. It is never inside `~/Shared` and never contains it, so no file belongs to two folders. It is not inside iCloud Drive, because Obsidian's help says to avoid syncing one vault with more than one service. A missing path is skipped and reported, never created. A folder already stored at another path is reported, never retargeted. Groundwork never creates, moves, or relocates a vault.

### Sharing

The folder goes only to devices `groundwork syncthing-pair add` already added. `autoAcceptFolders` and `introducer` stay `false`, which is Syncthing's default, so an unknown device cannot be introduced into the vault and a folder offer is not taken with the GUI's suggested path.
