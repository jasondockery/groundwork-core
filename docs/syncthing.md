# Syncthing shared folders

Syncthing is the default shared folder across Groundwork machines. It runs as a user service on each machine and syncs `~/Shared` over the personal Tailscale tailnet. FreeTube's database files are the first app directory inside that folder. The Omarchy M1 mini stays on so the other machines still have a peer when they sleep.

This page is the contract. [The decision record](decisions/syncthing-shared-folders.md) explains why Syncthing, why the other candidates were set aside, and why FreeTube still has no sync of its own. Environment repos install the package, start the service, and implement `groundwork syncthing-pair`. They reference this page. They do not keep a second copy of it.

Reviewed on 2026-10-24 against [Syncthing's configuration](https://docs.syncthing.net/users/config.html), [GUI listen address](https://docs.syncthing.net/users/guilisten.html), [autostart](https://docs.syncthing.net/users/autostart.html), [config REST endpoints](https://docs.syncthing.net/rest/config.html), and [Tailscale's reserved addresses](https://tailscale.com/docs/reference/reserved-ip-addresses). Tailnet ports are recorded in [Tailscale](tailscale.md).

A device ID identifies a machine to its peers. An API key authorizes the local REST API. Both stay on the machine that created them. This repository never holds a device ID, an API key, a certificate, a MagicDNS name, or a Tailscale address.

## Default

Syncthing is installed and enabled on every Groundwork machine. It is a default, not an opt-in, in the same sense as the other tools in [one developer setup](developer-setup.md). A fresh install and a later update both converge on the same result. The step is finished only after the listen addresses below are in effect. If the tailnet address is not available yet, the apply sets that part aside and retries on the next apply. It does not record a partial install as finished, and it does not start Syncthing on the upstream listen addresses while it waits.

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

Folder versioning, rescan interval, ignore patterns, and the other folder fields stay at Syncthing's defaults. The apply fills id, label, path, and type from the table, then leaves the rest of the default folder object alone.

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
6. Confirm the running listener matches the list above. That confirmation is what marks the step finished.

When `tailscale ip -4` fails, stop before step 5. Leave the service disabled and retry on the next apply.

On a machine that is already serving with the upstream listener, patch the same settings over the localhost REST API, restart the user service, and confirm. The API key is read from the local `config.xml` into the request header. It is not printed.

### Overrides

Each row is a setting whose upstream default would leave the tailnet. The value is what Groundwork writes.

| Setting | Value | Reason |
| --- | --- | --- |
| `options.listenAddress` | localhost TCP 22000, plus TCP and QUIC on the current Tailscale IPv4 and, when present, IPv6 addresses | `default` listens on every interface and joins the public relay pool. |
| `options.relaysEnabled` | `false` | With relays left on, a peer that is briefly unreachable over the tailnet is contacted through the public relay pool. |
| `options.globalAnnounceEnabled` | `false` | Global announce publishes this device to Syncthing's public discovery servers. Peers use an explicit MagicDNS address instead. |
| `options.localAnnounceEnabled` | `false` | Local announce broadcasts on the LAN and dials whatever answers. Those machines are outside the tailnet. |
| `options.natEnabled` | `false` | UPnP and NAT-PMP ask the home router to open port 22000. |
| `options.announceLANAddresses` | `false` | Announcing the LAN address hands paired devices a path that is not the tailnet. |
| `STNODEFAULTFOLDER` | `1` in the service environment | The first start otherwise creates `~/Sync`. The shared folder is `~/Shared`. |
| `device.addresses` | `tcp://MAGICDNS:22000` and `quic://MAGICDNS:22000` | With discovery off, the upstream address `dynamic` has no way to find the peer. `MAGICDNS` is the other machine's MagicDNS name, entered at pair time. |
| `device.allowedNetworks` | `100.64.0.0/10` and `fd7a:115c:a1e0::/48` | An empty list, which is the upstream default, accepts that device from any network. These two prefixes are Tailscale's IPv4 and IPv6 ranges. |

### Kept defaults

The apply checks these and, if a previous run changed them, puts the upstream value back. They are listed so a later change has to add a row to the override table with a reason.

| Setting | Kept value | Reason |
| --- | --- | --- |
| `gui.address` | `127.0.0.1:8384` | The GUI and the REST API share one listen address. This is the upstream localhost default. `0.0.0.0` would also listen on the LAN, and that API can read and write every synced file. The Tailscale address alone would drop the local browser. Remote use is the SSH forward above. |
| `gui.user` and `gui.password` | unset | The GUI is on localhost. A password is an extra setting, and the API key remains the local credential. |
| `options.urAccepted` | unset (`0`, ask) | Usage reporting is the person's choice. The tailnet restriction does not require an answer. |
| `options.crashReportingEnabled` | upstream default | Crash reporting is independent of where the sync listener binds. |
| folder versioning | upstream default (off) | Versioning is a backup policy. Conflict copies from NeDB are handled by closing the second writer, not by a versioning scheme. |

Discovery server URLs and the relay server URL stay at `default`. The enabled flags above are what turn them off. Clearing the URLs would be a second edit for the same restriction.

## FreeTube

FreeTube's package data directory stays where that package puts it. Groundwork shares four files, and only these four:

- `history.db`
- `playlists.db`
- `profiles.db`
- `settings.db`

The files live in `~/Shared/FreeTube/`. Each name in the package data directory is a symlink to the matching file. The rest of the data directory (cache, cookies, session storage, lock files, `search-history.db`, `subscription-cache.db`) stays local. Pointing Syncthing at the whole data directory would copy Electron files between operating systems, which FreeTube's maintainer has said is unsafe.

Repair runs only while FreeTube is not running. It is idempotent:

1. If the data-dir name is already a symlink to `~/Shared/FreeTube/<name>`, leave it.
2. If the data-dir name is a regular file and the shared file is absent, move the regular file to `~/Shared/FreeTube/<name>` and replace it with the symlink.
3. If both sides have a regular file, stop. Report both paths. The apply does not pick a winner and does not delete either copy.
4. If FreeTube replaced a symlink with a new regular file while the shared copy also exists, stop the same way.

A Flatpak build cannot see `~/Shared` until the app is granted that directory. The grant is `~/Shared/FreeTube` for `io.freetubeapp.FreeTube`, and nothing broader. A native package does not need the grant.

Open FreeTube on one machine at a time. Close it and wait until Syncthing reports `groundwork-shared` up to date before opening it elsewhere. Two writers append to the same NeDB files and leave `*.sync-conflict-*` copies that FreeTube will not merge. An environment repo may show that warning at launch. The check is local: `GET /rest/db/status` for folder `groundwork-shared`, and a warning when the folder is not idle. The warning does not refuse to start FreeTube. An offline peer would otherwise block the machine that is in use.

If a conflict copy appears, close FreeTube on every machine, keep the newer database, remove the conflict file, and open one machine. There is no merge step.

## Pairing

Pairing is a separate command from install. Bootstrap does not have the other machine's device ID, and this repository must not gain one. The person runs the same command on both machines. Each command talks only to the Syncthing on that machine. It does not call the other machine's API, so the machines never exchange API keys.

```bash
groundwork syncthing-pair show
groundwork syncthing-pair add --device-id DEVICE_ID --name NAME --magicdns MAGICDNS
```

`DEVICE_ID`, `NAME`, and `MAGICDNS` are placeholders. `show` prints this machine's device ID and nothing else. `NAME` is a local label. `MAGICDNS` is the other machine's MagicDNS name, used only to build the two device addresses.

`add` is safe to run again with the same arguments. A second run that already matches exits 0 and does not create a second device entry or a second folder share.

1. Require the user service to be running and the GUI to be on `127.0.0.1:8384`. If the service is down, print that platform's start command and exit nonzero. Do not start a second Syncthing process.
2. On Unix, require `config.xml` to be mode `0600`. On Windows, require an ACL that grants the current user and does not grant Everyone. Otherwise exit nonzero. The config directory is the one this install uses: `$XDG_STATE_HOME/syncthing` or `~/.local/state/syncthing` on Linux, `~/Library/Application Support/Syncthing` on macOS, `%LOCALAPPDATA%\Syncthing` on Windows. If the pre-1.27 path `~/.config/syncthing/config.xml` exists and the new path does not, use the old path.
3. Read the API key from that file in memory. Send it only as the `X-API-Key` header to `http://127.0.0.1:8384`. The key is never an argument, an environment variable, a log line, or a file under a git checkout. `syncthing cli` is acceptable for the same calls when it loads the key itself.
4. Reject a malformed device ID, and reject this machine's own device ID. `show` is how the other machine's ID is obtained (`syncthing device-id`, `syncthing --device-id`, or `syncthing cli show system`, whichever the installed binary accepts). Print that ID only. Do not write it into a repo, a shell rc, or a world-readable file.
5. `GET /rest/config/devices/<id>`. When the device is absent, `POST` it with the label, the two MagicDNS addresses, and the two Tailscale prefixes. When it is present and those fields already match, leave it. When they differ, `PUT` the object from the `GET`, changing only those fields, so a re-run converges and unrelated device fields survive.
6. `GET /rest/config/folders/groundwork-shared`. When it is absent, start from `GET /rest/config/defaults/folder`, set the id, label, and absolute `~/Shared` path, and add this device. When it is present, add this device to its device list without removing any device already there. When the stored path is not absolute `~/Shared`, stop and report it. Do not retarget a folder that was moved.
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

Each repo also implements `groundwork syncthing-pair` as specified above, the listen-address apply, the symlink repair, and the one-machine warning on the FreeTube cheatsheet or app list. Tests in those repos belong there. This repo checks that the contract still says these things and that it contains no device ID or API key.
