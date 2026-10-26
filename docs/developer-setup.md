# One developer setup across the Groundwork family

Personal and managed machines use the same developer tools. Device policy and supported platform determine what can run; a work/personal label does not decide which coding agents are available. Each provider still requires local sign-in, and credentials and employer-specific configuration stay outside the repositories.

| Surface | Owner and desired setup |
| --- | --- |
| macOS desktop | `groundwork-mac`: Codex CLI, Claude Code, Grok Build, OpenCode, Cursor, ChatGPT and Claude desktop apps, T3 Code Nightly, Herdr, Tailscale, and Syncthing. Colima plus Docker CLI is the common Mac container default. |
| Linux and WSL2 Unix environment | `groundwork-linux` and `groundwork-windows` delegate to the `groundwork-mac` engine for the native coding CLIs and Tailscale package. Desktop Linux installs Syncthing through that engine and includes Cursor. WSL does not run Syncthing: the Windows host is the peer for that computer. WSL host apps remain a separate explicit installation. |
| Windows host | `groundwork-windows` owns explicit native app installation and Windows service guidance. The host normally owns Tailscale connectivity and the Syncthing user service; a WSL package does not enroll another node automatically. |
| Omarchy on Apple Silicon | `groundwork-omarchy-mac-arm64` preserves Omarchy’s package feed and tool configuration. Syncthing comes from the Arch package and runs as a user service. The mini is the always-on peer. The shared chezmoi engine is never applied there. Native Linux uses its supported apps and web access for services without official Linux desktop apps. |
| Shared guidance | This repository owns shared explanations, including the [Syncthing shared-folder contract](syncthing.md), not package installation or account enrollment. See [local model workflows](local-models.md) for evaluation; environment repositories own runtime installation and model downloads. |

Git identity, optional personal apps, C#/infrastructure extensions, container backend, and stable/preview release posture are independent choices. Existing valid preferences are preserved during migration. A stored historical `work` flag is compatibility input, not an ongoing tool exclusion.

Use the environment repository’s installer and updater. Homebrew refreshes itself and the eligible installed inventory in its environment; Omarchy owns its native updates; Windows apps keep their host updater. Integrity checks, release-age rules, package pins, and device policy still apply. Latest available does not establish compatibility or successful local authentication.

For macOS, follow the single [Docker Desktop to Colima migration guide](https://github.com/jasondockery/groundwork-mac/blob/main/docs/docker-desktop-to-colima.md). It explains the recommendation, scenario-dependent work, persistent data, project verification, rollback, and optional Desktop removal. Linux, WSL, and Omarchy retain their native container runtimes; Apple hardware running Linux is still Linux.

Finish [Tailscale policy and connection acceptance](tailscale.md) on each intended host. Installing a package does not sign in, approve a device, enable incoming SSH, or prove a two-way connection.

Syncthing is the default shared folder on each machine that holds `~/Shared`. Follow [Syncthing shared folders](syncthing.md) for the user service, the listen addresses, and `groundwork syncthing-pair`. Installing the package does not create the folder, restrict the listener, or pair a device.
