# Syncthing shared folders

This page is how a file you save on one Groundwork machine shows up on the others: the Mac, Linux, Windows, and the Omarchy mini. Syncthing is the default that does it, as a user service over the personal Tailscale tailnet. `~/Shared` is one Syncthing folder, `groundwork-shared`. FreeTube's four databases are a second folder, `groundwork-freetube`, at `~/Shared/FreeTube`. An Obsidian vault is a third folder, `groundwork-obsidian`, at the vault path each machine saved, outside `~/Shared`. The Omarchy M1 mini stays on so the other machines still have a peer when they sleep. SSH keys, tokens, and agent credentials stay in their existing locations, out of `~/Shared`.

This page is the contract. [The decision record](decisions/syncthing-shared-folders.md) explains why Syncthing, why the other candidates were set aside, why FreeTube still has no sync of its own, and how the Obsidian folder's open points were decided. Environment repos install the package, start the service, and implement `groundwork syncthing-pair`. They reference this page. They do not keep a second copy of it.

Reviewed on 2026-10-24 against [Syncthing's configuration](https://docs.syncthing.net/users/config.html), [GUI listen address](https://docs.syncthing.net/users/guilisten.html), [autostart](https://docs.syncthing.net/users/autostart.html), [config REST endpoints](https://docs.syncthing.net/rest/config.html), and [Tailscale's reserved addresses](https://tailscale.com/docs/reference/reserved-ip-addresses). Tailnet ports are recorded in [Tailscale](tailscale.md). The pause check and the index drop were read on 2026-10-29 in Syncthing 2.1.7 [`ResetFolder`](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/model/model.go#L2923-L2931). The restart after a successful reset was read the same day in [`postSystemReset`](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/api/api.go#L986-L1018) and [`fatal`](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/api/api.go#L504-L510). [`Serve`](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/api/api.go#L449-L460) keeps accepting requests until it sees that exit and shuts the server down. [`State`](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/model/model.go#L2658-L2667) returns `""` when the folder has no runner. `startTime` on `GET /rest/system/status` is the process start ([`usage_report.go`](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/ur/usage_report.go#L42), exposed at [`api.go`](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/api/api.go#L1066)). The [public reset page](https://docs.syncthing.net/rest/system-reset-post.html) says the call erases the index and restarts Syncthing. It does not state the pause check.

The Obsidian folder was reviewed on 2026-10-31 against Syncthing's [folder types](https://docs.syncthing.net/users/foldertypes.html), [file versioning](https://docs.syncthing.net/users/versioning.html), [ignoring files](https://docs.syncthing.net/users/ignoring.html), [conflicting changes](https://docs.syncthing.net/users/syncing.html), and the device attributes `autoAcceptFolders` and `introducer` in [Syncthing's configuration](https://docs.syncthing.net/users/config.html). Obsidian's side was read the same day in [Sync your notes across devices](https://obsidian.md/help/sync-notes), [Sync settings and selective syncing](https://obsidian.md/help/sync/settings), [Switch to Obsidian Sync](https://obsidian.md/help/sync/switch), and the community [Obsidian Hub Syncthing page](https://publish.obsidian.md/hub/02+-+Community+Expansions/02.05+All+Community+Expansions/Auxiliary+Tools/Syncthing).

A device ID identifies a machine to its peers. An API key authorizes the local REST API. Both stay on the machine that created them. This repository never holds a device ID, an API key, a certificate, a MagicDNS name, or a Tailscale address.

## Default

Syncthing is installed and enabled on every Groundwork machine. It is a default, not an opt-in, in the same sense as the other tools in [one developer setup](developer-setup.md). A fresh install and a later update both converge on the same result. The service must not set `STGUIADDRESS` or `--gui-address`. The override hides the config value and does not rewrite `config.xml`. The step stays unfinished until the override is unset, the listening socket is `127.0.0.1:8384`, and the sync listen addresses below are in effect. If `tailscale ip -4` fails, the apply sets the listen-address part aside and retries on the next apply. It does not record a partial install as finished, it does not start Syncthing on the upstream listen addresses while it waits, and a later apply does not PATCH `listenAddresses`. Refuse to apply or wrap, and refuse `groundwork syncthing-pair`, when the Syncthing binary is older than 2.1.2.

The service is a user service. It starts when that user logs in. It is not a system service and it does not run as an administrator.

| Environment | What "user service" means |
| --- | --- |
| macOS | Homebrew's per-user LaunchAgent, via `brew services`. The formula already runs `syncthing --no-browser --no-restart`. |
| Linux through the shared engine | The same `brew services` unit. On Linux that is a systemd user service. |
| Windows host | A per-user logon task that runs `syncthing.exe --no-console --no-browser`. A LocalSystem service is the wrong shape: the local API can read and write synced files, and the official autostart guide reserves a Windows service for an administered server. |
| Omarchy | The pacman unit `syncthing.service` on the user systemd instance: `systemctl --user enable --now syncthing.service`. The unit already passes `--no-browser`. |

The Omarchy mini is the always-on peer. Its apply also enables lingering for that user (`loginctl enable-linger`) so the user service starts at boot without a graphical login. Linger needs administrator permission; the Omarchy installer asks once at the start, and if nobody can answer it sets linger aside and retries later. Other machines do not linger. The mini's MagicDNS name is whatever Tailscale assigned. It is not written down here. Tailscale still cannot wake a machine that is powered off or unlock disk encryption before the OS starts.

WSL is not a Syncthing peer. FreeTube on Windows reads `%APPDATA%\FreeTube` on the host, so the host runs the only Syncthing for that computer. The shared engine skips the Homebrew formula when its target is WSL.

## Shared folders

`~/Shared` stays one Syncthing folder. The FreeTube wrapper never pauses `groundwork-shared`. The four FreeTube databases are folder `groundwork-freetube`, so a FreeTube session does not stop the rest of the share. A FreeTube session pauses and resumes only `groundwork-freetube`.

| | `groundwork-shared` | `groundwork-freetube` | `groundwork-obsidian` |
| --- | --- | --- | --- |
| Path | `~/Shared`, that user's absolute home path | `~/Shared/FreeTube`, that same home, absolute | That machine's saved vault path, absolute, never inside `~/Shared` |
| Label | `Shared` | `FreeTube` | `Obsidian` |
| Type | `sendreceive` | `sendreceive`, or `receiveonly` while a missing database is restored | `receiveonly` when first added, `sendreceive` after the person confirms that machine |
| Versioning | Syncthing's default, no versioning | trash can: `versioning.type` `trashcan`, `cleanoutDays` `0` | trash can: `versioning.type` `trashcan`, `cleanoutDays` `0` |
| Added by | install and pairing | install and pairing | pairing only, and only on a machine with a saved vault path |

Syncthing does not support a folder nested inside another as a general feature. These two still share a parent path because the databases have to be paused on their own. `/FreeTube` is the first pattern in `~/Shared/.stignore`. The first matching pattern wins, so that line is never appended under a `!` rule. The pattern `*~` in `~/Shared/FreeTube/.stignore` keeps a crash temp such as `history.db~` from being synced. Both files are written before either folder is added and before the first scan. Without the parent ignore, `groundwork-shared` would index the databases, and a fresh local file would publish through the parent while `groundwork-freetube` was paused or receive-only. `.stignore` itself is not synced.

If `GET /rest/db/browse?folder=groundwork-shared&prefix=FreeTube` already lists any file, stop. Remove every other device from that folder's object, taken from GET, and write that object before touching the index. Write `/FreeTube` as the first pattern. `groundwork-shared` must be paused before `POST /rest/system/reset?folder=groundwork-shared`. Syncthing 2.1.7 `ResetFolder` returns `folder must be paused when resetting` while that folder still has a runner. When it does not, `ResetFolder` drops that folder's index and does not scan. An implementation may ask the owner to pause Shared in the GUI. On Syncthing 2.1.2 or newer it may instead `PATCH /rest/config/folders/groundwork-shared` with only `{"paused": true}`. Do not send that PATCH on an older binary. If the folder is not paused yet, do not reset and do not resume.

A successful POST returns `{"ok": "resetting folder groundwork-shared"}`. That call writes the body and then enqueues the exit. The API keeps accepting requests until the server shuts down, so the first probe that still succeeds is the process that is exiting. The restarted process loads the saved config, so `groundwork-shared` is still paused. `ResetFolder` does not scan. The scan that skips `FreeTube` runs when that unpaused folder starts.

Record `startTime` from `GET /rest/system/status` before the POST. That value is the process start time.

Do not resume when the reset response returns. A resume sent to the process that is still exiting leaves the new process paused. After a successful POST, wait until a probe fails because the old process is gone. Use `GET /rest/system/ping`. Then wait until the API answers again. Only then retry `PATCH /rest/config/folders/groundwork-shared` with only `{"paused": false}` until the new process accepts it.

A lost response is a POST that returns no status code. Compare a later `GET /rest/system/status` `startTime` with the value recorded before the POST. A different `startTime` is the new process: unpause that process after `GET /rest/system/ping` answers. The same `startTime`, with ping still succeeding, means this process never exited: resume it.

Resume the current process when the POST returned an error and that process never exited. A probe that still succeeds, with no gap where the probe failed, and the same `startTime`, is that case. An interrupt before the POST is that case when the process never exited. An interrupt after a successful POST is not that case. It waits for the probe to fail, then for the new API, then retries the unpause. When the owner paused Shared in the GUI, use the same split, so the share does not stay stopped.

After the new process accepts the unpause, poll `GET /rest/db/status?folder=groundwork-shared` until a sample has been `scanning` or `scan-waiting` and the latest sample is `idle`. That is the finished initial scan. A paused folder has no runner, so `state` is `""`. A dropped index before the runner starts is also `""`. The runner then sets `starting`, then a brief `idle`, and the first scan is already due, so it moves to `scan-waiting` and `scanning` before a poll can treat that early `idle` as finished. Only after a sample has been `scanning` or `scan-waiting` and the latest sample is `idle`, require `GET /rest/db/browse?folder=groundwork-shared&prefix=FreeTube` to be empty. Share the parent only then. Do not announce those entries as deletions.

`groundwork-freetube` uses trash-can versioning. Syncthing archives a file when a remote device replaces or deletes it, and moves that old copy to `.stversions`. A fresh empty database is newer than the history it replaces, and FreeTube will not merge the two. `cleanoutDays` `0` keeps the trash-can copy until a person removes it. `groundwork-shared` keeps the default of no versioning. The rescan interval stays at Syncthing's default on both folders.

Later app folders are further subdirectories of `~/Shared`, added here first and then in the environment repos. A new app folder that must be paused on its own cannot sit inside `groundwork-shared` unless that parent ignores it the same way. The Obsidian vault is not an app folder under `~/Shared`. It stays where the person keeps it, and the [Obsidian vault](#obsidian-vault) rules below apply.

The first launch of an unconfigured Syncthing creates a folder at `~/Sync`. Groundwork's folder is `~/Shared`, so the service environment sets `STNODEFAULTFOLDER=1` before `syncthing generate` and before the service starts. An existing `~/Sync` that a person already uses is left in place. The apply does not delete it.

The first create of each folder fills id, label, path, and type from the default folder object and leaves the rest of that object alone, then sets trash-can versioning on `groundwork-freetube` only. A later apply does not `PUT` a default folder object over an existing folder. The default `paused` is false, so that `PUT` would unpause a live session. Resume, when the FreeTube rules below allow it, is `PATCH /rest/config/folders/groundwork-freetube` with only `{"paused": false}`. The apply never pauses `groundwork-shared` for a FreeTube session and never resumes it for FreeTube. The only pause of `groundwork-shared` is the index reset above. When the apply paused that folder, it uses the reset split above: record `startTime` before the POST, resume this process when the POST errored or the response was lost and `startTime` is unchanged, and unpause the new process only after it answers. The apply takes the same non-blocking lock as the FreeTube wrapper before it resumes, moves, or relinks. If that lock is busy, the apply does not resume, move, or relink.

## What the apply changes

Syncthing's GUI listens on a single address. The upstream value `127.0.0.1:8384` is already localhost, so Groundwork keeps it. From another machine, forward that loopback port over the tailnet the same way as any other local service:

```bash
ssh -N -L 127.0.0.1:18384:127.0.0.1:8384 LOCAL_USER@MACHINE
```

Open `http://127.0.0.1:18384`. The local port is 18384 because 8384 is this machine's own GUI. `LOCAL_USER` and `MACHINE` are the destination's login and MagicDNS name.

The sync listener is the bind address that has to change. The value `default` means `tcp://0.0.0.0:22000`, `quic://0.0.0.0:22000`, and `dynamic+https://relays.syncthing.net/endpoint`: every interface, plus the public relay pool. Groundwork replaces that value, and turns off the discovery, relay, and NAT options that would still leave the tailnet. The apply writes:

- `tcp://127.0.0.1:22000`
- `tcp://<tailscale-ipv4>:22000` and `quic://<tailscale-ipv4>:22000`, from `tailscale ip -4`
- `tcp://[<tailscale-ipv6>]:22000` and `quic://[<tailscale-ipv6>]:22000`, from `tailscale ip -6`, when that command prints an address

Syncthing has no interface-name syntax such as `%tailscale0`. The apply substitutes the current addresses. A later apply rewrites the list when the addresses change, and restarts the user service only when the list changed. Addresses are compared as a set.

Order on a new machine:

1. Install the package.
2. Run `syncthing generate` with `STNODEFAULTFOLDER=1` when `config.xml` is absent. Generate writes the certificate and config and exits. It does not listen.
3. Create `~/Shared` and `~/Shared/FreeTube`.
4. Write `/FreeTube` as the first pattern in `~/Shared/.stignore`, and `*~` in `~/Shared/FreeTube/.stignore`. Do this before either folder is added and before the first scan.
5. Write the overrides below into that local config, including both folders. `groundwork-obsidian` is not written at install. Pairing adds it.
6. Enable and start the user service.
7. Confirm `STGUIADDRESS` and `--gui-address` are unset, the running sync listener matches the list above, and the listening socket is `127.0.0.1:8384`. The override hides the config value. The step stays unfinished until the override is unset and the listening socket is `127.0.0.1:8384`.

When `tailscale ip -4` fails on a machine that has not served yet, stop before step 6. Leave the service disabled and retry on the next apply.

When `tailscale ip -4` fails on a machine that is already serving, do not PATCH `listenAddresses`. Keep the addresses already in effect. Retry that list on the next apply. Do not replace the list with localhost only, and do not restore `default`. The four flags below may still be set in a PATCH that omits `listenAddresses`.

When `tailscale ip -4` succeeds on a machine that is already serving, `PATCH /rest/config/options` with `listenAddresses` set to that full list, and with `relaysEnabled`, `globalAnnounceEnabled`, `localAnnounceEnabled`, and `natEnabled` set to `false`. `PATCH` replaces `listenAddresses`, so the body carries every URL. Restart the user service only when the list changed, then confirm the running sync listener, that `STGUIADDRESS` and `--gui-address` are unset, and that the listening socket is `127.0.0.1:8384`. The step stays unfinished until the override is unset and the listening socket is `127.0.0.1:8384`. Before the first `serve`, the same URLs are repeated `listenAddress` elements in `config.xml`. The API key is read from the local `config.xml` into the request header. It is not printed.

Refuse to apply or wrap, and refuse `groundwork syncthing-pair`, when `syncthing --version` or `GET /rest/system/version` is older than 2.1.2. Through 2.1.1, a folder `PATCH` ran SetDefaults and reset every omitted field (upstream issues 10389 and 10746, fixed by PR 10763 in 2.1.2). The body `{"paused": true}` is safe only on 2.1.2 and newer. Do not send that PATCH, and do not launch FreeTube through the wrapper, on an older binary.

### Overrides

Each row is a setting Groundwork changes from the upstream default. The value is what Groundwork writes.

| Setting | Value | Reason |
| --- | --- | --- |
| `listenAddress` in config.xml; `listenAddresses` on REST | localhost TCP 22000, plus TCP and QUIC on the current Tailscale IPv4 and, when present, IPv6 addresses | `default` listens on every interface and joins the public relay pool. The pre-start file repeats the XML element `listenAddress`. A running process is updated with `PATCH /rest/config/options` field `listenAddresses`. |
| `options.relaysEnabled` | `false` | With relays left on, a peer that is briefly unreachable over the tailnet is contacted through the public relay pool. |
| `options.globalAnnounceEnabled` | `false` | Global announce publishes this device to Syncthing's public discovery servers. Peers use an explicit MagicDNS address instead. |
| `options.localAnnounceEnabled` | `false` | Local announce broadcasts on the LAN and dials whatever answers. Those machines are outside the tailnet. |
| `options.natEnabled` | `false` | UPnP and NAT-PMP ask the home router to open port 22000. |
| `STNODEFAULTFOLDER` | `1` | The first start otherwise creates `~/Sync`. The shared folder is `~/Shared`. Set this in the service environment. |
| `device.addresses` | `tcp://MAGICDNS:22000` and `quic://MAGICDNS:22000` | With discovery off, the upstream address `dynamic` has no way to find the peer. `MAGICDNS` is the other machine's MagicDNS name, entered at pair time. |
| `device.allowedNetworks` | `100.64.0.0/10` and `fd7a:115c:a1e0::/48` | An empty list, which is the upstream default, accepts that device from any network. These two prefixes are Tailscale's IPv4 and IPv6 ranges. |
| `folder.versioning` on `groundwork-freetube` | type `trashcan`, param `cleanoutDays` `0` | Versioning archives a remote replace or delete into `.stversions`. The default, no versioning, drops the previous database. A fresh empty database is newer than the history it replaces, and FreeTube will not merge the two. `cleanoutDays` 0 does not purge the trash can on a timer. |
| `folder.versioning` on `groundwork-obsidian` | type `trashcan`, param `cleanoutDays` `0` | A note deleted or overwritten on another machine is archived into the vault's `.stversions` instead of dropped. The trash can keeps one copy per path, so a note edited many times a day does not pile up copies. This is a safety net for sync, not note history. |

### GUI address

A later apply writes `gui.address` back to `127.0.0.1:8384` when it differs. That write is `PATCH /rest/config/gui` with only `{"address":"127.0.0.1:8384"}`. A `PUT` clears the password. The service must not set `STGUIADDRESS` or `--gui-address`. The override hides the config value at runtime and does not rewrite `config.xml`. The step stays unfinished until the override is unset and the listening socket is `127.0.0.1:8384`. The GUI and the REST API share one listen address. `127.0.0.1:8384` is the upstream localhost value. `0.0.0.0` would also listen on the LAN, and that API can read and write every synced file. The Tailscale address alone would drop the local browser. Remote use is the SSH forward above.

A later apply leaves `gui.user`, `gui.password`, `options.urAccepted`, `options.crashReportingEnabled`, and folder versioning on `groundwork-shared` at the values already stored. Those are the person's choices. Groundwork does not write them on a later apply. On `groundwork-freetube` and `groundwork-obsidian`, a later apply writes trash-can versioning back when `versioning.type` is not `trashcan` or `cleanoutDays` is not `0`. That write changes only the versioning object.

Discovery server URLs and the relay server URL stay at `default`. The enabled flags above are what turn them off. Clearing the URLs would be a second edit for the same restriction.

## FreeTube

FreeTube's package data directory stays where that package puts it. Groundwork shares four files, and only these four:

- `history.db`
- `playlists.db`
- `profiles.db`
- `settings.db`

The files live in `~/Shared/FreeTube/`. Each name in the package data directory is a symlink to the matching file. The rest of the data directory (cache, cookies, session storage, lock files, `search-history.db`, `subscription-cache.db`) stays local. Sharing the whole data directory would copy Electron files between operating systems, which FreeTube's maintainer has said is unsafe. FreeTube 0.25.3 has no supported data-directory setting. Chromium's `--user-data-dir`, and any portable-mode flag, is an unsupported launch flag that has to be passed every time. FreeTube 0.25.3 `src/datastores/index.js` checks `statSync(path)?.isSymbolicLink` without calling `isSymbolicLink`. The check is truthy for an existing path, and NeDB receives `realpathSync(path)`. `@seald-io/nedb` 4.1.2 `lib/storage.js` writes `filename~` beside that real path and renames it onto `~/Shared/FreeTube/<name>`. The data-dir symlink survives. The shared file is the compacted database. The wrapper does not move a data-dir file onto a shared file that is already present. Moving a local database into that folder while `global` has a live copy would publish a fresh file over history that has not arrived.

The wrapper takes an exclusive non-blocking lock before any `lstat`, move, link, or `PATCH`, and holds it in the process that waits. Do not `exec` FreeTube over that process. On Unix the call is `flock(LOCK_EX|LOCK_NB)` on a descriptor kept open until resume. On Windows the call is `LockFileEx` with `LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY` on a handle kept open for the same span. The kernel releases that lock when the process dies, including a crash. A lock file, a pid file, or a delete-on-exit file is not this lock. Busy means a live holder. If the lock is busy and a FreeTube process exists, start FreeTube only to focus the running instance, and do not `PATCH` the folder. Do not classify, move, link, or resume. If the lock is busy and no FreeTube process exists, exit without launching. A second launch must not resume the folder. Only the holder launches, and only after the pause. When the kernel has released the lock, the next launch is the holder and must pause. Pause and resume only `groundwork-freetube`. The FreeTube wrapper never pauses `groundwork-shared`. Refuse to wrap when Syncthing is older than 2.1.2.

Decide every missing name from `global` on `GET /rest/db/file` for folder `groundwork-freetube`. Do not decide peer presence from `availability`. `availability` lists only connected devices, so a sleeping peer is omitted. A live copy is `global.deleted` false and `global.invalid` false. The cluster has no copy of a name when the folder is unpaused, a sync with each device in `folder.devices` has completed (`GET /rest/db/completion` for that device and folder is complete), and the GET has no global file or `global.deleted` is true. If `global.invalid` is true, stop and do not launch. Do not publish a local file while a live copy exists.

The one create path is that check for all four names, plus the person's confirmation. One machine may then create. A local regular main, with the shared file absent, is migrated: when a main and a sibling temp exist, quarantine the temp and migrate the main only. Both the data-dir name and the shared file absent, and no `name.db~` present, is the first session. FreeTube creates the database as a regular file in its data directory. Still holding the lock, after the process is gone, move that regular file to `~/Shared/FreeTube/<name>` and put the symlink in its place. Without that confirmation, create nothing, move nothing, resume nothing, and do not launch. Never create an empty database to fill the hole.

A live copy is restored through receive-only. `PATCH /rest/config/folders/groundwork-freetube` with only `{"type": "receiveonly"}` and leave that folder unpaused. `GET /rest/db/localchanged?folder=groundwork-freetube`. `POST /rest/db/revert` only when that list is the missing name and no other local changes. If other databases in that list have local edits, move those files aside, revert, and move them back. Revert rolls back every local change in the folder. If any other local change is not one of the four databases, do not revert. Stay `receiveonly` and unpaused until `local.deleted` is false and the path is a regular file. Do not launch while the type is `receiveonly`. When every name is on disk, `PATCH` only `{"type": "sendreceive"}`. A file on disk, including a 0-byte file, is a present shared file.

Never promote `name.db~` when a main file exists. Do not rename a temp onto `name.db`, onto a symlink, or onto `~/Shared/FreeTube/<name>`. A symlink is not a main. Cleanup never deletes the main database (`history.db`, `playlists.db`, `profiles.db`, or `settings.db`). Quarantine moves `name.db~` outside the package data directory and outside `~/Shared`, so NeDB cannot rename it onto the database and neither folder syncs it. A temp with no main is not a database to publish: leave it, do not launch, and do not rename it. Do not choose by mtime.

Classify each data-dir path with `lstat` before launch, while FreeTube is not running. Only the lock holder runs this classification, and it runs once:

- The data-dir name is a symlink to `~/Shared/FreeTube/<name>` and that shared file exists. Leave it. A symlink whose target now exists is this leave-it case. A file on disk, including a 0-byte file, is a present shared file.
- The data-dir name is a symlink to `~/Shared/FreeTube/<name>` and that target is absent. Do not launch. Print the missing path and stop rather than reclassifying in a loop. A live `global` copy is restored through receive-only. The confirmed create path is the only way to replace a missing file when the cluster has no copy. Never create an empty database to fill the hole.
- The data-dir name is absent and the shared file is present. Create the symlink. Do not start FreeTube until that symlink exists.
- The data-dir name is a regular file and the shared file is absent. On the confirmed create path, quarantine the temp and migrate the main only, then put the symlink in its place. While a live copy exists, or before the cluster check has completed, create nothing, move nothing, resume nothing, and do not launch.
- Both paths are regular files. Stop, print both paths, delete nothing, and do not launch.
- Both the data-dir name and the shared file are absent, and no `name.db~` is present. This is a first session only on the confirmed create path. Otherwise create nothing, move nothing, resume nothing, and do not launch.
- Any other `lstat` result: print the paths, change nothing, and do not launch. That includes a symlink whose target is not `~/Shared/FreeTube/<name>`, a directory, and a symlink create that fails. A failed link after a successful move is this case. Do not treat it as both paths absent.

One pass classifies all four names, then one folder decision. Launch when every name is already present locally, or when the person confirmed the one create path and every absent name is that create. If any name is both-regular or any other `lstat` result, do not launch. Do not resume `sendreceive` while any of the four names is still a regular file in the package data directory.

Offer deletion confirmation only when `global.deleted` is true and every other device in `folder.devices` has connected since that deletion. A device has connected since the deletion when it is connected now and `GET /rest/db/completion` for it is complete, or its `lastSeen` from `GET /rest/stats/device` is after `global.modified`. Tell the person a live copy may still be in `.stversions` on a peer. A paused folder's `GET /rest/db/status` `state` is `""`, which is not `idle`, so the check runs only while the folder is unpaused. A live `global` copy is restored through receive-only and is not offered for confirmation. Resume stays per name. Printing the path, running apply, or confirming one name does not confirm the others. Resuming `sendreceive` while an indexed file is missing announces the absence as a deletion and replicates it.

After the process exits, leave a correct symlink alone. If the shared file is already there, stop and print both paths. The wrapper does not move a data-dir file onto a shared file that is already present. Still holding the lock, after the process is gone, a move runs only on the confirmed create path, and only when the shared path is absent.

Desktop entries, the Dock, the Start Menu, Spotlight, and `flatpak run io.freetubeapp.FreeTube` otherwise start the package binary and skip this wrapper. The environment repo installs the wrapper as the only menu, Dock, Start Menu, Spotlight, and `flatpak run io.freetubeapp.FreeTube` command for the package. A direct binary launch is outside this contract.

On macOS, closing the window does not quit FreeTube. `window-all-closed` runs `handleQuit`, which compacts and then calls `app.quit()` only when the platform is not darwin. The Dock icon stays lit, and a Dock click opens a new window in the same process, which still has the databases loaded. The process exits on Quit. The FreeTube cheatsheet says Quit, not close the window. The wrapper waits for the FreeTube process to exit, not for the window and not for `open` or `start` to return. macOS uses `open -W`. Windows uses `start /wait`. `flatpak run` waits. Resume stays tied to process exit. Only the lock holder resumes, after its process exits and no FreeTube process remains.

The lock holder pauses folder `groundwork-freetube` with `PATCH /rest/config/folders/groundwork-freetube` and `paused` true before launch. Only the holder launches, and only after the pause. The FreeTube wrapper never pauses `groundwork-shared`. The pause covers compact, while NeDB renames `~/Shared/FreeTube/*.db~` onto the shared database. After the process exits, classify all four names before any resume. The only `sendreceive` resume is this one. Leaving `groundwork-freetube` unpaused while its type is `receiveonly` is the restore above, and it is not this resume. Resume only when every name is either a present shared file or a deletion the person confirmed for that specific name. A present shared file is the file on disk at `~/Shared/FreeTube/<name>`, including a 0-byte file. Offer deletion confirmation only when `global.deleted` is true and every other device has connected since that deletion. Printing the path, running apply, or confirming one name does not confirm the others. Never create an empty database to fill the hole. Never promote `name.db~` when a main file exists. When that rule holds, the lock holder resumes with `PATCH /rest/config/folders/groundwork-freetube` body `{"paused": false}` only.

A later apply refuses a Syncthing older than 2.1.2. A later apply takes the same non-blocking lock. If it is busy, do not resume, move, or relink. If it is acquired, re-check that no FreeTube process exists. A later apply uses the same per-name rule. A live `global` copy is restored through receive-only and is not created or migrated. The one create path is the same confirmed cluster check. Until that confirmation, create nothing, move nothing, resume nothing. Resume only when every name is either a present shared file or a deletion the person confirmed for that specific name, with `PATCH /rest/config/folders/groundwork-freetube` body `{"paused": false}` only. The apply never pauses `groundwork-shared` except for the index reset, and when it paused that folder it uses the reset split above, including `startTime` for a lost response. Do not `PUT` a default folder object over a paused folder.

A Flatpak build cannot see `~/Shared` until the app is granted that directory. The grant is `~/Shared/FreeTube` for `io.freetubeapp.FreeTube`, and nothing broader. A native package does not need the grant.

Open FreeTube on one machine at a time. Quit it, and wait until Syncthing reports `groundwork-freetube` up to date, before opening it elsewhere. Closing the window on macOS leaves the process running and `groundwork-freetube` paused. `groundwork-shared` keeps syncing. A paused folder's `GET /rest/db/status` `state` is `""`, so that state is not `idle` while the folder is paused. Two writers append to the same NeDB files and leave `*.sync-conflict-*` copies that FreeTube will not merge. An environment repo shows that warning on the FreeTube cheatsheet. The cheatsheet says Quit, not close the window. The check is local: `GET /rest/db/status` for folder `groundwork-freetube`, and a warning when the folder is not idle. The warning does not refuse to start FreeTube. An offline peer would otherwise block the machine that is in use.

If a `*.sync-conflict-*` copy appears, Quit FreeTube on every machine, print both paths, and stop. Recovery does not choose the newer file by mtime. A fresh empty database is newer than the synced one. Remove a `*.sync-conflict-*` file only after a person compares the copies.

## Obsidian vault

Folder `groundwork-obsidian`, label `Obsidian`, shares one Obsidian vault between the person's machines. It replaces iCloud or a paid sync service for that vault. It is sync, not a backup. Note history belongs to a tool built for it, such as the Obsidian Git community plugin or a separate backup.

### Saved vault path

Each environment repo asks once for this machine's vault and saves the answer in that machine's local state, outside any git checkout. "No vault on this machine" is a valid saved answer. The answer is an absolute path in that user's home. It may differ between machines, for example `~/Documents/Obsidian/<vault>` on the mini and another folder on the Mac. Groundwork does not guess a path, and does not pick the first vault it finds. This repository never holds a vault path.

Before any write for this folder, check the saved path. Skip `groundwork-obsidian` and say so, and keep going with the other folders, when any of these is true:

- No vault is saved for this machine.
- The saved path is not absolute, or is not inside that user's home, or is the home itself.
- The saved path is `~/Shared`, is inside `~/Shared`, or contains `~/Shared`. The vault is never nested inside `~/Shared`, and `~/Shared` is never nested inside the vault.
- The saved path is, contains, or is inside the path of another folder in this Syncthing config.
- The saved path is inside iCloud Drive (`~/Library/Mobile Documents`). Obsidian's own help says to avoid syncing the same vault with more than one service.
- The saved path does not exist, is not a directory, or has no `.obsidian` directory in it.

Never create a vault, never create the saved directory, and never move, rename, or relocate an existing vault. If the vault folder is missing, skip it and print the saved path. Writing `.stignore` into a missing path would create it, so the check comes first. When the stored folder path in Syncthing differs from the saved path, stop and report both. Do not retarget the folder. The person turns off Obsidian Sync for a vault before sharing it here.

### Ignore file

Write these three lines as the first three patterns of `<vault>/.stignore` before the folder is added and before the first scan:

```text
/.obsidian/workspace.json
/.obsidian/workspace-mobile.json
/.obsidian/cache
```

Obsidian rewrites the open panes and files in `workspace.json` on desktop and `workspace-mobile.json` on mobile whenever the layout changes, so two running machines make conflict copies of them. `/.obsidian/cache` is cache data that each machine rebuilds for itself. The leading `/` anchors each line to the vault root, so a folder of notes that happens to be named `.obsidian` deeper down is not affected. The first matching pattern wins, so these lines come before any `!` pattern. Lines the person already has in that `.stignore` stay below them. A later apply adds any of the three that is missing and changes nothing else in the file. `.stignore` itself is not synced, so every machine writes its own.

Everything else in `.obsidian` syncs: `app.json`, `appearance.json`, `core-plugins.json`, `community-plugins.json`, hotkeys, themes, snippets, `graph.json`, `workspaces.json` (named layouts the person saved), and `plugins/`, including each plugin's `data.json`. Those are the vault's settings, and Obsidian Sync syncs the same groups by default. A plugin that writes a per-device cache inside its own folder is a per-plugin ignore line the person adds. Groundwork does not add one.

### First pairing

`groundwork syncthing-pair add` creates `groundwork-obsidian` as `receiveonly` on every machine. It never creates it as `sendreceive`. A receive-only folder takes the cluster's files and does not send its own. Its existing notes stay on disk and are listed as local changes. When a note at the same path arrives from the cluster, the cluster copy wins and the local copy is kept beside it as a `*.sync-conflict-*` file. That copy is not sent while the folder is receive-only. Nothing in the local vault is deleted and nothing leaves it.

The person then names the machine whose vault is the source:

```bash
groundwork syncthing-pair obsidian-promote
```

`obsidian-promote` is the only path from `receiveonly` to `sendreceive`. It runs on one machine at a time:

1. Require the same service, GUI, file-mode, and version checks as `add`. Re-check the saved path rules above. Require `groundwork-obsidian` to exist with the saved path and type `receiveonly`. When the type is already `sendreceive`, exit 0 and change nothing.
2. Require `GET /rest/db/status?folder=groundwork-obsidian` to be `idle`. Require at least one other device in `folder.devices` to be connected, and `GET /rest/db/completion` for each connected device and this folder to be complete. Print the name of each device that is not connected.
3. `GET /rest/db/localchanged?folder=groundwork-obsidian`. Those are the files this machine has that the cluster does not, including any `*.sync-conflict-*` copies made above. Print the count and the paths. Never print note contents.
4. When that list is empty, `PATCH /rest/config/folders/groundwork-obsidian` with only `{"type": "sendreceive"}`. Nothing merges, because this machine already matches the cluster.
5. When that list is not empty, ask once. Say that these files will be sent to every machine that shares the vault, and that a file at the same path on another machine becomes a `*.sync-conflict-*` copy there. Conflict copies are normal files after they are made, so they also reach every machine. When `globalFiles` in step 2's status is above zero, another machine is already a source, and the prompt says this merges two vaults. Only a typed yes promotes. Any other answer, no terminal, or an interrupt leaves the folder `receiveonly` and changes nothing.

Groundwork never calls `POST /rest/db/revert` on `groundwork-obsidian`. Revert deletes files that exist only on this machine. A person who wants this machine to match the cluster exactly can press Revert Local Changes in the GUI after reading what it removes.

The first machine promoted has nothing to receive, so its whole vault is the list in step 3 and the prompt is its source confirmation. A machine joining a vault that is already shared starts receive-only, fills from the cluster, and is promoted when its list is empty or the person accepts what is in it. When two machines already hold different vaults, nothing merges until the person types yes on the second one.

### Sharing

`groundwork-obsidian` is shared only with devices that `groundwork syncthing-pair add` already added. Pairing never sets `autoAcceptFolders` or `introducer` to `true`, and never accepts a pending device or a pending folder. When the other machine offers `groundwork-obsidian` first, this machine's `add` creates the folder itself at the saved path with the rules above. Accepting the offer in the GUI would use the GUI's suggested path, not the saved vault. The apply never adds this folder at install, never changes its type, and never pauses it.

## Pairing

Pairing is a separate command from install. Bootstrap does not have the other machine's device ID, and this repository must not gain one. The person runs the same command on both machines. Each command talks only to the Syncthing on that machine. It does not call the other machine's API, so the machines never exchange API keys.

```bash
groundwork syncthing-pair show
groundwork syncthing-pair add --device-id DEVICE_ID --name NAME --magicdns MAGICDNS
groundwork syncthing-pair obsidian-promote
```

`DEVICE_ID`, `NAME`, and `MAGICDNS` are placeholders. `show` prints this machine's device ID and nothing else. `NAME` is a local label. `MAGICDNS` is the other machine's MagicDNS name, used only to build the two device addresses. `obsidian-promote` is described in [First pairing](#first-pairing).

`add` is safe to run again with the same arguments. A second run that already matches exits 0 and does not create a duplicate device entry or a duplicate share of any folder.

1. Require the user service to be running and the GUI to be on `127.0.0.1:8384`. If the service is down, print that platform's start command and exit nonzero. Do not start a second Syncthing process.
2. On Unix, require `config.xml` and `key.pem` to be mode `0600`. On Windows, require the ACL of both `config.xml` and `key.pem` to grant only the current user, `SYSTEM`, and `Administrators`. Any other trustee fails the check. Otherwise exit nonzero. The config directory is the one this install uses: `$XDG_STATE_HOME/syncthing` or `~/.local/state/syncthing` on Linux, `~/Library/Application Support/Syncthing` on macOS, `%LOCALAPPDATA%\Syncthing` on Windows. If the pre-1.27 path `~/.config/syncthing/config.xml` exists and the new path does not, use the old path.
3. Read the API key from that file in memory. Send it only as the `X-API-Key` header to `http://127.0.0.1:8384`. The key is never an argument, an environment variable, a log line, or a file under a git checkout. `syncthing cli` is acceptable for the same calls when it loads the key itself.
4. Reject a malformed device ID, and reject this machine's own device ID. `show` is how the other machine's ID is obtained (`syncthing device-id`, `syncthing --device-id`, or `syncthing cli show system`, whichever the installed binary accepts). Print that ID only. Do not write it into a repo, a shell rc, or a world-readable file.
5. `GET /rest/config/devices/<id>`. When the device is absent, `GET /rest/config/defaults/device`, set `deviceID`, `name`, `addresses`, and `allowedNetworks` on that object, and `POST` it. When it is present and those fields already match, leave it with no device write. When they differ, `PUT` the object from the device `GET`, changing only those fields, so a re-run converges and unrelated device fields survive.
6. For each of `groundwork-shared` and `groundwork-freetube`, `GET /rest/config/folders/<id>`. The path for `groundwork-shared` is the user's absolute `~/Shared`. The path for `groundwork-freetube` is the user's absolute `~/Shared/FreeTube`. When the folder is absent, start from `GET /rest/config/defaults/folder`, set the id, label, and that absolute path, and add this device from `GET /rest/config/defaults/device` (its `deviceID` set). On `groundwork-freetube`, set trash-can versioning with `cleanoutDays` `0`. When the folder is present, compare its path with that absolute path before any write decision. When the stored path is not that absolute path, stop and report it. Do not write the folder and do not retarget a folder that was moved. When the path matches and this device ID is already in `folder.devices`, do not write the folder. When the path matches and the ID is absent, append that defaults/device entry and write the folder once. That write sends the folder object from this GET. Do not `PUT` a default folder object over a paused folder. On `groundwork-freetube`, when versioning is not trash-can with `cleanoutDays` `0`, set that versioning on the object from this GET and write it once.
7. For `groundwork-obsidian`, apply the [saved vault path](#saved-vault-path) rules first. When they say skip, print why and the saved path, leave any existing `groundwork-obsidian` object alone, and continue. Otherwise `GET /rest/config/folders/groundwork-obsidian`. When the folder is absent, write the three [ignore lines](#ignore-file) into `<vault>/.stignore` first, then start from `GET /rest/config/defaults/folder`, set id `groundwork-obsidian`, label `Obsidian`, the saved absolute path, type `receiveonly`, and trash-can versioning with `cleanoutDays` `0`, add the device from this run the same way as step 6, and `POST` it. When the folder is present, use the same path comparison and device rule as step 6. Never change its type here. When versioning is not trash-can with `cleanoutDays` `0`, set it on the object from this GET and write it once.
8. Exit 0. The success line names the label and says the other machine runs `add` with this machine's device ID. It does not include the API key, the certificate, or `key.pem`.

Both directions are required. Adding machine B on machine A shows B a pending device until B adds A. After both adds, `groundwork-shared` and `groundwork-freetube` are shared in both directions and the files converge. `groundwork-obsidian` is shared in both directions but stays receive-only on each machine until `obsidian-promote` runs there. Repeat `show` and `add` for each pair. The mini is the useful first peer, because it is the one that stays on.

## What each environment repo implements

Package installation, the service manager, the Flatpak grant, and the Windows symlink privilege stay in the environment repo. The rows below are the consumption list. Package ids move; the names below were reviewed on 2026-10-24. Apply and the wrapper refuse a Syncthing binary older than 2.1.2. The packages below were 2.1.7 on that date.

| Repo | Syncthing package and service | FreeTube package and data directory |
| --- | --- | --- |
| `groundwork-mac` | Homebrew formula `syncthing`. `brew services start syncthing`, with `STNODEFAULTFOLDER=1` added to that user service. Skip the formula when the engine target is WSL. | Homebrew cask `freetube`. Data directory `~/Library/Application Support/FreeTube/`. |
| `groundwork-linux` | The same Homebrew formula through the shared engine. `brew services` is the systemd user service. Do not also install a distro `syncthing`; two copies would be two peers. | Flatpak `io.freetubeapp.FreeTube`. Data directory `~/.var/app/io.freetubeapp.FreeTube/config/FreeTube/`. Grant that app filesystem access to `~/Shared/FreeTube` only. |
| `groundwork-windows` | Winget `Syncthing.Syncthing`, on the Windows host. Per-user logon start with `--no-console --no-browser` and `STNODEFAULTFOLDER=1`. | Winget `FreeTube.FreeTube`. Data directory `%APPDATA%\FreeTube`. `PrestonN.FreeTube` is the old publisher id and stops at 0.23.14. Creating the file symlinks needs a user who is allowed to create symlinks; if that permission is missing, set the step aside and retry, and do not mark it finished. |
| `groundwork-omarchy-mac-arm64` | Pacman `syncthing` via `omarchy pkg add syncthing` (Arch Linux ARM `extra`, aarch64), then `systemctl --user enable --now syncthing.service`. Enable linger on the mini. Confirm this package runs on the mini's 16 KiB pages before treating the install as finished. | The FreeTube package is chosen in that repo. Flatpak `io.freetubeapp.FreeTube` uses `~/.var/app/io.freetubeapp.FreeTube/config/FreeTube/` and the same narrow filesystem grant. A native `freetube-bin` install uses `~/.config/FreeTube`. Use the path that matches the package that actually launches. |

Each repo also implements `groundwork syncthing-pair` as specified above, the listen-address apply, and the FreeTube wrapper as the only menu, Dock, Start Menu, Spotlight, and `flatpak run io.freetubeapp.FreeTube` command for the package. The wrapper takes an exclusive non-blocking lock before any `lstat`, move, link, or `PATCH` and holds it in the waiting process until resume. A direct binary launch is outside this contract. Each repo shows the one-machine warning on the FreeTube cheatsheet or app list. Each repo also asks once for the saved Obsidian vault path, keeps it in local state outside any git checkout, and implements `groundwork syncthing-pair obsidian-promote`. A machine with no saved vault skips `groundwork-obsidian`. The FreeTube cheatsheet says Quit, not close the window. Tests in those repos belong there. This repo checks that the contract still says these things and that it contains no device ID or API key.
