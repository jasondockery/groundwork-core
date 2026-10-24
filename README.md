# groundwork-core

Shared operational guidance, skills, and project scaffolds for the Groundwork family. This repo does not install a machine and it does not apply files into a home directory. The learning curriculum stays in the original [Groundwork site](https://jasondockery.github.io/groundwork/) for now; the copied HTML here is a reference from the initial split, not the current learning destination.

| Repo | What it owns |
|---|---|
| `groundwork-core` | This repo. Shared operational guidance and cross-environment skills. |
| `groundwork-mac` | Groundwork workstation bootstrap and chezmoi source for macOS, Linux/WSL, and headless setups. It does not install Omarchy as an operating system. |
| [`groundwork-linux`](https://github.com/jasondockery/groundwork-linux) | Non-Omarchy Linux entry point and OS guidance; uses the shared engine in `groundwork-mac`. |
| [`groundwork-windows`](https://github.com/jasondockery/groundwork-windows) | Windows/WSL2 entry point and host guidance; Unix setup runs inside WSL2. |
| [`groundwork-omarchy-mac-arm64`](https://github.com/jasondockery/groundwork-omarchy-mac-arm64) | Omarchy personal overrides for Apple Silicon Macs. It stows one Hyprland input file and enables the Caps Lock keyd mapping by default, with an opt-out. |

The Apple Silicon Omarchy operating-system installer is the upstream [omarchy-mac-installer](https://github.com/omacom/omarchy-mac-installer). It is separate from `groundwork-mac` and from these personal configuration repositories.

For native Omarchy on an Apple Silicon Mac, install Omarchy Mac first with the upstream installer, then apply [groundwork-omarchy-mac-arm64](https://github.com/jasondockery/groundwork-omarchy-mac-arm64) after the first successful boot and base-system update. Its README has the current edge install sequence. Do not apply `groundwork-mac` to Omarchy.

An environment repo pins this one as a git submodule named `core`.

```bash
git clone --recurse-submodules https://github.com/jasondockery/groundwork-mac.git
```

Update the pin from inside an environment repo:

```bash
git submodule update --remote core
```

Review the diff, then commit the new submodule pointer. Edit the shared pages here, not as a second copy inside an environment repo.

## What is here

- `AI_THESIS.md`, the north star for the family
- `docs/`, the pages that teach the path, agent supervision, and the learning tracks
- [`skills/README.md`](skills/README.md), the local documentation procedure and
  imported reference material; active shared engineering skills belong to Compass
- `skel/`, project scaffolds
- [`docs/ai-tools-and-remote-access.md`](docs/ai-tools-and-remote-access.md), shared T3 Code, Herdr, and Tailscale guidance
- [`docs/tailscale.md`](docs/tailscale.md), the common tailnet security and connection guide referenced by each environment
- [`docs/syncthing.md`](docs/syncthing.md), the shared-folder default (Syncthing over the tailnet, `~/Shared`, FreeTube's database files) and [`docs/decisions/syncthing-shared-folders.md`](docs/decisions/syncthing-shared-folders.md), the decision record
- [`docs/migrating-from-groundwork.md`](docs/migrating-from-groundwork.md), migration for existing macOS, Linux, and Windows/WSL2 users while the old repo remains available

## What stays in an environment repo

Shell config, tmux keys, Homebrew, chezmoi, macOS defaults, Hyprland, keyd, and package names. Omarchy's tmux prefix is Ctrl+Space, with Ctrl+B still available. `groundwork-mac` uses that prefix and Omarchy's no-prefix chords (`Alt+Enter`, `Alt+Shift+Enter`, `Alt+Escape`, `Ctrl+Alt+Arrow`, `Alt+Left`, and `Alt+Right`). Omarchy keeps its own tmux file and desktop Super keys. Install operations remain in environment repos.

When an installer needs an administrator password, it asks once at the start if a terminal is available. When nobody is there to answer, it sets aside only those privileged steps, continues the rest, and retries them on the next apply from a terminal. That partial install is not recorded as finished. A prerequisite for everything after it, such as the Linux packages Homebrew itself needs, stops and prints the recovery command instead of continuing. `groundwork-linux` and `groundwork-windows` use the `groundwork-mac` engine for this. Omarchy asks in its own `install.sh` before the first privileged change.

The copied HTML pages in `docs/` still carry the original site navigation, including links to environment pages that are absent here. Use the original Groundwork site for curriculum while that migration is deferred. Current operational guides are the linked Markdown documents; do not direct a new learner into the copied HTML navigation.

## Why a submodule

This repo is shared by more than one installer and each installer should choose when it picks up a change. A submodule records that exact commit. chezmoi's external sources are for pulling third-party files into a home-directory source tree. They are the wrong tool for sharing these docs. A subtree would copy the files into each environment repo and hide which commit they came from.

## Omarchy boundary

See [Updating Groundwork](docs/updating.md) for the common `update-all` and
`groundwork-update` workflow, platform ownership, and retry behavior.

On Omarchy, do not apply `groundwork-mac`. The [Omarchy manual](https://omarchy.org/manual/dotfiles/) treats `~/.config` as the user's files and `/usr/share/omarchy` as the package. [groundwork-omarchy-mac-arm64](https://github.com/jasondockery/groundwork-omarchy-mac-arm64) only overrides files Omarchy already expects the user to own.

## Common setup and container migration

[One developer setup](docs/developer-setup.md) explains the common tool set and independent preferences. On macOS, use Colima plus Docker CLI by default and follow the single [Docker Desktop migration and removal guide](https://github.com/jasondockery/groundwork-mac/blob/main/docs/docker-desktop-to-colima.md). Installation and platform behavior stay in the environment repositories.
