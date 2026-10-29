# Decision: Syncthing over Tailscale for shared folders

Status: accepted
Date: 2026-10-24
Issue: [groundwork-core#14](https://github.com/jasondockery/groundwork-core/issues/14)

The operational contract is [Syncthing shared folders](../syncthing.md). This page records why that contract exists.

Reviewed on 2026-10-24 against the [Syncthing configuration reference](https://docs.syncthing.net/users/config.html), the [FreeTube data-location page](https://docs.freetubeapp.io/usage/data-location/), [FreeTube issue 370](https://github.com/FreeTubeApp/FreeTube/issues/370), FreeTube 0.25.3, the [Dropbox Linux package index](https://linux.dropbox.com/debian/pool/main/), and the [rclone Google Drive client-id notice](https://rclone.org/drive/#making-your-own-client-id).

## Decision

Syncthing, carried over the existing personal Tailscale tailnet, is how Groundwork shares files across machines. Every `groundwork-mac`, `groundwork-linux`, `groundwork-windows`, and `groundwork-omarchy-mac-arm64` machine installs it and enables it as a user service. It is a default. It is not an opt-in extra.

The shared folder is `~/Shared` (`groundwork-shared`). FreeTube's database files live at `~/Shared/FreeTube` and are a second Syncthing folder, `groundwork-freetube`, with trash-can versioning. The wrapper never pauses `~/Shared`. An index reset of `groundwork-shared` pauses that folder first. A successful reset restarts Syncthing, and the unpause is retried on the new process after the API answers. The scan runs when the folder is unpaused. The wrapper still never pauses it. The Omarchy M1 mini (Asahi, aarch64, 16 KiB pages) is the always-on peer, so a laptop still has somewhere to sync when other desktops are asleep.

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
