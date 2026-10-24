# Syncthing shared folders

This page is how a file you save on one Groundwork machine shows up on the others: the Mac, Linux, Windows, and the Omarchy mini. Syncthing is the default that does it, as a user service over the personal Tailscale tailnet. `~/Shared` is the folder. FreeTube's database files are the first app directory inside it, and the Omarchy M1 mini stays on so the other machines still have a peer when they sleep. SSH keys, tokens, and agent credentials stay in their existing locations, out of `~/Shared`.

This page is the contract. [The decision record](decisions/syncthing-shared-folders.md) explains why Syncthing, why the other candidates were set aside, and why FreeTube still has no sync of its own. Environment repos install the package, start the service, and implement `groundwork syncthing-pair`. They reference this page. They do not keep a second copy of it.

Reviewed on 2026-10-24 against [Syncthing's configuration](https://docs.syncthing.net/users/config.html), [GUI listen address](https://docs.syncthing.net/users/guilisten.html), [autostart](https://docs.syncthing.net/users/autostart.html), [config REST endpoints](https://docs.syncthing.net/rest/config.html), and [Tailscale's reserved addresses](https://tailscale.com/docs/reference/reserved-ip-addresses). Tailnet ports are recorded in [Tailscale](tailscale.md).

A device ID identifies a machine to its peers. An API key authorizes the local REST API. Both stay on the machine that created them. This repository never holds a device ID, an API key, a certificate, a MagicDNS name, or a Tailscale address.

## Default

Syncthing is installed and enabled on every Groundwork machine. It is a default, not an opt-in, in the same sense as the other tools in [one developer setup](developer-setup.md). A fresh install and a later update both converge on the same result. The service must not set `STGUIADDRESS` or `--gui-address`. The override hides the config value and does not rewrite `config.xml`. The step stays unfinished until the override is unset, the listening socket is `127.0.0.1:8384`, and the sync listen addresses below are in effect. If the tailnet address is not available yet, the apply sets that part aside and retries on the next apply. It does not record a partial install as finished, and it does not start Syncthing on the upstream listen addresses while it waits.

The service is a user service. It starts when that user logs in. It is not a system service and it does not run as an administrator.

| Environment | What "user service" means |
| --- | --- |
| macOS | Homebrew's per-user LaunchAgent, via `brew services`. The formula already runs `syncthing --no-browser --no-restart`. |
| Linux through the shared engine | The same `brew services` unit. On Linux that is a systemd user service. |
| Windows host | A per-user logon task that runs `syncthing.exe --no-console --no-browser`. A LocalSystem service is the wrong shape: the local API can read and write synced files, and the official autostart guide reserves a Windows service for an administered server. |
| Omarchy | The pacman unit `syncthing.service` on the user systemd instance: `systemctl --user enable --now syncthing.service`. The unit already passes `--no-browser`. |

The Omarchy mini is the always-on peer. Its apply also enables lingering for that user (`loginctl enable-linger`) so the user service starts at boot without a graphical login. Linger needs administrator permission; the Omarchy installer asks once at the start, and if nobody can answer it sets linger aside and retries later. Other machines do not linger. The mini's MagicDNS name is whatever Tailscale assigned. It is not written down here. Tailscale still cannot wake a machine that is powered off or unlock disk encryption before the OS starts.

WSL is not a Syncthing peer. FreeTube on Windows reads `%APPDATA%\FreeTube` on the host, so the host runs the only Syncthing for that computer. The shared engine skips the Homebrew formula when its target is WSL.

## Shared folder

One folder:

| | |
| --- | --- |
| Path | `~/Shared`, stored in Syncthing as that user's absolute home path |
| Folder id | `groundwork-shared` |
| Label | `Shared` |
| Type | `sendreceive`, which is Syncthing's folder default |

`~/Shared/FreeTube/` holds the FreeTube database files. Later app folders are further subdirectories of `~/Shared`. They are added here first, then in the environment repos.

The first launch of an unconfigured Syncthing creates a folder at `~/Sync`. Groundwork's folder is `~/Shared`, so the service environment sets `STNODEFAULTFOLDER=1` before `syncthing generate` and before the service starts. An existing `~/Sync` that a person already uses is left in place. The apply does not delete it.

Folder versioning and rescan interval stay at Syncthing's defaults. The shared folder ignore list includes the pattern `*~`, so a crash temp such as `~/Shared/FreeTube/history.db~` is not synced. The apply adds that line to `~/Shared/.stignore` when it is missing and leaves every other ignore line in place. The first create fills id, label, path, and type from the default folder object and leaves the rest of that object alone. A later apply does not `PUT` a default folder object over an existing folder. The default `paused` is false, so that `PUT` would unpause a live session. Resume, when the FreeTube rules below allow it, is `PATCH /rest/config/folders/groundwork-shared` with only `{"paused": false}`. The apply takes the same non-blocking lock as the FreeTube wrapper before it resumes, moves, or relinks. If that lock is busy, the apply does not resume, move, or relink.

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
3. Write the overrides below into that local config.
4. Create `~/Shared/FreeTube`.
5. Enable and start the user service.
6. Confirm `STGUIADDRESS` and `--gui-address` are unset, the running sync listener matches the list above, and the listening socket is `127.0.0.1:8384`. The override hides the config value. The step stays unfinished until the override is unset and the listening socket is `127.0.0.1:8384`.

When `tailscale ip -4` fails, stop before step 5. Leave the service disabled and retry on the next apply.

On a machine that is already serving, `PATCH /rest/config/options` with `listenAddresses` set to that full list, and with `relaysEnabled`, `globalAnnounceEnabled`, `localAnnounceEnabled`, and `natEnabled` set to `false`. `PATCH` replaces `listenAddresses`, so the body carries every URL. Restart the user service only when the list changed, then confirm the running sync listener, that `STGUIADDRESS` and `--gui-address` are unset, and that the listening socket is `127.0.0.1:8384`. The step stays unfinished until the override is unset and the listening socket is `127.0.0.1:8384`. Before the first `serve`, the same URLs are repeated `listenAddress` elements in `config.xml`. The API key is read from the local `config.xml` into the request header. It is not printed.

### Overrides

Each row is a setting whose upstream default would leave the tailnet. The value is what Groundwork writes.

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

### GUI address

A later apply writes `gui.address` back to `127.0.0.1:8384` when it differs. That write is `PATCH /rest/config/gui` with only `{"address":"127.0.0.1:8384"}`. A `PUT` clears the password. The service must not set `STGUIADDRESS` or `--gui-address`. The override hides the config value at runtime and does not rewrite `config.xml`. The step stays unfinished until the override is unset and the listening socket is `127.0.0.1:8384`. The GUI and the REST API share one listen address. `127.0.0.1:8384` is the upstream localhost value. `0.0.0.0` would also listen on the LAN, and that API can read and write every synced file. The Tailscale address alone would drop the local browser. Remote use is the SSH forward above.

A later apply leaves `gui.user`, `gui.password`, `options.urAccepted`, `options.crashReportingEnabled`, and folder versioning at the values already stored. Those are the person's choices. Groundwork does not write them on a later apply.

Discovery server URLs and the relay server URL stay at `default`. The enabled flags above are what turn them off. Clearing the URLs would be a second edit for the same restriction.

## FreeTube

FreeTube's package data directory stays where that package puts it. Groundwork shares four files, and only these four:

- `history.db`
- `playlists.db`
- `profiles.db`
- `settings.db`

The files live in `~/Shared/FreeTube/`. Each name in the package data directory is a symlink to the matching file. The rest of the data directory (cache, cookies, session storage, lock files, `search-history.db`, `subscription-cache.db`) stays local. Sharing the whole data directory would copy Electron files between operating systems, which FreeTube's maintainer has said is unsafe. FreeTube 0.25.3 has no supported data-directory setting. Chromium's `--user-data-dir`, and any portable-mode flag, is an unsupported launch flag that has to be passed every time. FreeTube 0.25.3 `src/datastores/index.js` checks `statSync(path)?.isSymbolicLink` without calling `isSymbolicLink`. The check is truthy for an existing path, and NeDB receives `realpathSync(path)`. `@seald-io/nedb` 4.1.2 `lib/storage.js` writes `filename~` beside that real path and renames it onto `~/Shared/FreeTube/<name>`. The data-dir symlink survives. The shared file is the compacted database. The wrapper does not move a data-dir file onto a shared file that is already present. On a new machine the data-dir name is absent, FreeTube would create a fresh database, and that move would overwrite the copy Syncthing already delivered.

The wrapper takes an exclusive non-blocking lock before any `lstat`, move, link, or `PATCH`, and holds it in the process that waits. Do not `exec` FreeTube over that process. On Unix the call is `flock(LOCK_EX|LOCK_NB)` on a descriptor kept open until resume. On Windows the call is `LockFileEx` with `LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY` on a handle kept open for the same span. The kernel releases that lock when the process dies, including a crash. A lock file, a pid file, or a delete-on-exit file is not this lock. Busy means a live holder. If the lock is busy and a FreeTube process exists, start FreeTube only to focus the running instance, and do not `PATCH` the folder. Do not classify, move, link, or resume. If the lock is busy and no FreeTube process exists, exit without launching. A second launch must not resume the folder. Only the holder launches, and only after the pause. When the kernel has released the lock, the next launch is the holder and must pause.

Before the case list, under the lock, with no FreeTube process, run temp-normalization. For each of the four names, scan both the package data directory and `~/Shared/FreeTube`. For each name, decide the empty case before any temp deletion. If the shared regular file is empty and either temp, shared or data-dir, is non-empty, print the empty file and those temps, delete nothing, and do not fall through. Do not choose by mtime. An empty shared file with a non-empty temp is not a present shared file and not leave-it, so do not launch and leave the folder paused. A symlink, including a dangling one, is never a main. Cleanup never deletes the main database (`history.db`, `playlists.db`, `profiles.db`, or `settings.db`). When that empty case does not match, if a directory has a regular `name.db`, delete only the sibling `name.db~`. Delete `name.db~` only when the main file was already there. Delete the data-dir temp only when the shared regular file is non-empty. If the data-dir name is a symlink and the temp is in the data directory, never rename onto the symlink. If `~/Shared/FreeTube/<name>` is absent and the share has no `name.db~`, rename the data-dir temp onto that shared path. If the shared file is already a regular file and that file is non-empty, delete only the data-dir temp. If both directories have a sole temp and neither has a regular main, that case ends normalization for that name. Print both temps, rename nothing, and do not launch. Do not fall through to the same-directory rename. The same-directory rename runs only when the other directory has no sole temp: when the name in that directory is not a symlink and the directory has no regular `name.db` but has `name.db~`, rename the temp onto `name.db` in that same directory. Never rename onto the data-dir symlink path. A sole `name.db~` in the data directory beside a symlink follows the shared-path rule above. A sole `~/Shared/FreeTube/<name>.db~` becomes `~/Shared/FreeTube/<name>.db`. Then classify once. A local regular database beside its sibling `name.db~` drops only that temp, and this migration path still launches once no temp remains. A restored shared file is not the migration path. The first-session path still launches once no temp remains.

Classify each data-dir path with `lstat` before launch, while FreeTube is not running. Only the lock holder runs this classification, and it runs once:

- The data-dir name is a symlink to `~/Shared/FreeTube/<name>` and that shared file is a non-empty regular file. Leave it. A symlink whose target now exists is this leave-it case. An empty shared file with a non-empty temp is not a present shared file and not leave-it.
- The data-dir name is a symlink to `~/Shared/FreeTube/<name>` and that target is absent, with no temp in either directory: do not launch. Print the missing path and stop rather than reclassifying in a loop. Leave the folder paused. That refusal does not apply to a name whose deletion the person confirmed. Resume stays per name. Resuming would announce the absence as a deletion. `groundwork-shared` is `sendreceive`: on resume Syncthing scans, treats an indexed file that is missing on disk as a local deletion, and replicates that deletion. That name is resolved when its file is back at `~/Shared/FreeTube/<name>`, or when the person confirms the deletion of that specific name. Resume only when every name is either a present shared file or a deletion the person confirmed for that specific name. Printing the path, running apply, or confirming one name does not confirm the others. Never create an empty database to fill the hole.
- The data-dir name is absent and the shared file is present. Create the symlink. Do not start FreeTube until that symlink exists. Creating that link is a launch path.
- The data-dir name is a regular file and the shared file is absent. There is no leftover temp. Move the regular file to `~/Shared/FreeTube/<name>`, then put the symlink in its place. This migration path still launches after the pause only when every name is a launch path.
- Both paths are regular files. Stop, print both paths, delete nothing, and do not launch.
- Both the data-dir name and the shared file are absent, and no `name.db~` is present. This is the first session. This first-session path still launches when the shared file is absent and there is no leftover temp, only when every name is a launch path. FreeTube creates the database as a regular file in its data directory.
- Any other `lstat` result: print the paths, change nothing, and do not launch. That includes a symlink whose target is not `~/Shared/FreeTube/<name>`, a directory, and a symlink create that fails. A failed link after a successful move is this case. Do not treat it as both paths absent.

One pass classifies all four names, then one folder decision. Launch only when every name is a launch path: leave-it, the migration path, the first session, or the link created when the data-dir name was absent and the shared file was present. If any name is both-regular, dangling, or any other `lstat` result, do not launch. Never resume while any of the four is still a regular file. If any target is still absent and no temp remains in either directory, print the missing path, do not launch, and leave the folder paused. That refusal does not apply to a name whose deletion the person confirmed. Resume stays per name. If any name is an empty shared file with a non-empty temp, do not launch and leave the folder paused. An empty shared file with a non-empty temp is not a present shared file and not leave-it. A non-empty shared file with no such pair stays the present-file case. Resume only when every name is either a present shared file or a deletion the person confirmed for that specific name. Printing the path, running apply, or confirming one name does not confirm the others.

After the process exits, leave a correct symlink alone. Still holding the lock, after the process is gone, move and symlink every regular file whose shared path is absent, then stop. The only resume is the one after that move and after all four names are classified. If the shared file is already there, stop and print both paths. Do not resume while any of the four names is still a regular file.

Desktop entries, the Dock, the Start Menu, Spotlight, and `flatpak run io.freetubeapp.FreeTube` otherwise start the package binary and skip this wrapper. The environment repo installs the wrapper as the only menu, Dock, Start Menu, Spotlight, and `flatpak run io.freetubeapp.FreeTube` command for the package. A direct binary launch is outside this contract.

On macOS, closing the window does not quit FreeTube. `window-all-closed` runs `handleQuit`, which compacts and then calls `app.quit()` only when the platform is not darwin. The Dock icon stays lit, and a Dock click opens a new window in the same process, which still has the databases loaded. The process exits on Quit. The FreeTube cheatsheet says Quit, not close the window. The wrapper waits for the FreeTube process to exit, not for the window and not for `open` or `start` to return. macOS uses `open -W`. Windows uses `start /wait`. `flatpak run` waits. Resume stays tied to process exit. Only the lock holder resumes, after its process exits and no FreeTube process remains.

The lock holder pauses folder `groundwork-shared` with `PATCH /rest/config/folders/groundwork-shared` and `paused` true before launch. Only the holder launches, and only after the pause. The pause covers compact, while NeDB renames `~/Shared/FreeTube/*.db~` onto the shared database. Temps follow the temp-normalization step above. After the process exits, run that step again, then classify all four names before any resume. If any target is still absent and no temp remains in either directory, print the missing path, do not launch, and leave the folder paused. That refusal does not apply to a name whose deletion the person confirmed. Resume stays per name. Resuming would announce the absence as a deletion. The only resume is this one, after the post-exit move and after all four names are classified. Resume only when every name is either a present shared file or a deletion the person confirmed for that specific name. A present shared file is the non-empty file back at `~/Shared/FreeTube/<name>`. An empty shared file with a non-empty temp is not a present shared file and not leave-it. A non-empty shared file with no such pair stays the present-file case. Printing the path, running apply, or confirming one name does not confirm the others. Never create an empty database to fill the hole. The migration path and the first-session path still launch once no temp remains, and only when every name is a launch path. When that per-name rule holds, and no `name.db~` remains beside a main file that was already there, the lock holder resumes with `PATCH` body `{"paused": false}` only.

A later apply takes the same non-blocking lock. If it is busy, do not resume, move, or relink. If it is acquired, re-check that no FreeTube process exists. A later apply uses the same per-name rule. Apply scans both directories and refuses the same way: if the shared regular file is empty and either temp is non-empty, print the empty file and those temps, delete nothing, do not launch, and leave the folder paused. An empty shared file with a non-empty temp is not a present shared file and not leave-it. Resume only when every name is either a present shared file or a deletion the person confirmed for that specific name, with `PATCH /rest/config/folders/groundwork-shared` body `{"paused": false}` only. Printing the path, running apply, or confirming one name does not confirm the others. If any name is still missing and that name's deletion was not confirmed, leave the folder paused. That refusal does not apply to a name whose deletion the person confirmed. Resume stays per name. Resuming would announce the absence as a deletion. Do not `PUT` a default folder object over a paused folder.

A Flatpak build cannot see `~/Shared` until the app is granted that directory. The grant is `~/Shared/FreeTube` for `io.freetubeapp.FreeTube`, and nothing broader. A native package does not need the grant.

Open FreeTube on one machine at a time. Quit it, and wait until Syncthing reports `groundwork-shared` up to date, before opening it elsewhere. Closing the window on macOS leaves the process running and the folder paused. A paused folder's `GET /rest/db/status` state is still `idle`, so the other machine's warning does not fire. Two writers append to the same NeDB files and leave `*.sync-conflict-*` copies that FreeTube will not merge. An environment repo shows that warning on the FreeTube cheatsheet. The cheatsheet says Quit, not close the window. The check is local: `GET /rest/db/status` for folder `groundwork-shared`, and a warning when the folder is not idle. The warning does not refuse to start FreeTube. An offline peer would otherwise block the machine that is in use.

If a `*.sync-conflict-*` copy appears, Quit FreeTube on every machine, print both paths, and stop. Recovery does not choose the newer file by mtime. A fresh empty database is newer than the synced one. Remove a `*.sync-conflict-*` file only after a person compares the copies.

## Pairing

Pairing is a separate command from install. Bootstrap does not have the other machine's device ID, and this repository must not gain one. The person runs the same command on both machines. Each command talks only to the Syncthing on that machine. It does not call the other machine's API, so the machines never exchange API keys.

```bash
groundwork syncthing-pair show
groundwork syncthing-pair add --device-id DEVICE_ID --name NAME --magicdns MAGICDNS
```

`DEVICE_ID`, `NAME`, and `MAGICDNS` are placeholders. `show` prints this machine's device ID and nothing else. `NAME` is a local label. `MAGICDNS` is the other machine's MagicDNS name, used only to build the two device addresses.

`add` is safe to run again with the same arguments. A second run that already matches exits 0 and does not create a second device entry or a second folder share.

1. Require the user service to be running and the GUI to be on `127.0.0.1:8384`. If the service is down, print that platform's start command and exit nonzero. Do not start a second Syncthing process.
2. On Unix, require `config.xml` and `key.pem` to be mode `0600`. On Windows, require the ACL of both `config.xml` and `key.pem` to grant only the current user, `SYSTEM`, and `Administrators`. Any other trustee fails the check. Otherwise exit nonzero. The config directory is the one this install uses: `$XDG_STATE_HOME/syncthing` or `~/.local/state/syncthing` on Linux, `~/Library/Application Support/Syncthing` on macOS, `%LOCALAPPDATA%\Syncthing` on Windows. If the pre-1.27 path `~/.config/syncthing/config.xml` exists and the new path does not, use the old path.
3. Read the API key from that file in memory. Send it only as the `X-API-Key` header to `http://127.0.0.1:8384`. The key is never an argument, an environment variable, a log line, or a file under a git checkout. `syncthing cli` is acceptable for the same calls when it loads the key itself.
4. Reject a malformed device ID, and reject this machine's own device ID. `show` is how the other machine's ID is obtained (`syncthing device-id`, `syncthing --device-id`, or `syncthing cli show system`, whichever the installed binary accepts). Print that ID only. Do not write it into a repo, a shell rc, or a world-readable file.
5. `GET /rest/config/devices/<id>`. When the device is absent, `GET /rest/config/defaults/device`, set `deviceID`, `name`, `addresses`, and `allowedNetworks` on that object, and `POST` it. When it is present and those fields already match, leave it with no device write. When they differ, `PUT` the object from the device `GET`, changing only those fields, so a re-run converges and unrelated device fields survive.
6. `GET /rest/config/folders/groundwork-shared`. When the folder is absent, start from `GET /rest/config/defaults/folder`, set the id, label, and absolute `~/Shared` path, and add this device from `GET /rest/config/defaults/device` (its `deviceID` set). When the folder is present, compare its path with the user's absolute `~/Shared` before any write decision. When the stored path is not that absolute path, stop and report it. Do not write the folder and do not retarget a folder that was moved. When the path matches and this device ID is already in `folder.devices`, do not write the folder. When the path matches and the ID is absent, append that defaults/device entry and write the folder once. That write sends the folder object from this GET. Do not `PUT` a default folder object over a paused folder.
7. Exit 0. The success line names the label and says the other machine runs `add` with this machine's device ID. It does not include the API key, the certificate, or `key.pem`.

Both directions are required. Adding machine B on machine A shows B a pending device until B adds A. After both adds, the folder is shared in both directions and the files converge. Repeat `show` and `add` for each pair. The mini is the useful first peer, because it is the one that stays on.

## What each environment repo implements

Package installation, the service manager, the Flatpak grant, and the Windows symlink privilege stay in the environment repo. The rows below are the consumption list. Versions move; the names are the package ids reviewed on 2026-10-24.

| Repo | Syncthing package and service | FreeTube package and data directory |
| --- | --- | --- |
| `groundwork-mac` | Homebrew formula `syncthing`. `brew services start syncthing`, with `STNODEFAULTFOLDER=1` added to that user service. Skip the formula when the engine target is WSL. | Homebrew cask `freetube`. Data directory `~/Library/Application Support/FreeTube/`. |
| `groundwork-linux` | The same Homebrew formula through the shared engine. `brew services` is the systemd user service. Do not also install a distro `syncthing`; two copies would be two peers. | Flatpak `io.freetubeapp.FreeTube`. Data directory `~/.var/app/io.freetubeapp.FreeTube/config/FreeTube/`. Grant that app filesystem access to `~/Shared/FreeTube` only. |
| `groundwork-windows` | Winget `Syncthing.Syncthing`, on the Windows host. Per-user logon start with `--no-console --no-browser` and `STNODEFAULTFOLDER=1`. | Winget `FreeTube.FreeTube`. Data directory `%APPDATA%\FreeTube`. `PrestonN.FreeTube` is the old publisher id and stops at 0.23.14. Creating the file symlinks needs a user who is allowed to create symlinks; if that permission is missing, set the step aside and retry, and do not mark it finished. |
| `groundwork-omarchy-mac-arm64` | Pacman `syncthing` via `omarchy pkg add syncthing` (Arch Linux ARM `extra`, aarch64), then `systemctl --user enable --now syncthing.service`. Enable linger on the mini. Confirm this package runs on the mini's 16 KiB pages before treating the install as finished. | The FreeTube package is chosen in that repo. Flatpak `io.freetubeapp.FreeTube` uses `~/.var/app/io.freetubeapp.FreeTube/config/FreeTube/` and the same narrow filesystem grant. A native `freetube-bin` install uses `~/.config/FreeTube`. Use the path that matches the package that actually launches. |

Each repo also implements `groundwork syncthing-pair` as specified above, the listen-address apply, and the FreeTube wrapper as the only menu, Dock, Start Menu, Spotlight, and `flatpak run io.freetubeapp.FreeTube` command for the package. The wrapper takes an exclusive non-blocking lock before any `lstat`, move, link, or `PATCH` and holds it in the waiting process until resume. A direct binary launch is outside this contract. Each repo shows the one-machine warning on the FreeTube cheatsheet or app list. The FreeTube cheatsheet says Quit, not close the window. Tests in those repos belong there. This repo checks that the contract still says these things and that it contains no device ID or API key.
