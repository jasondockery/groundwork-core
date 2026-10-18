# Move an existing Groundwork installation safely

This guide is for the few users who already installed the original `groundwork` on macOS, Linux, or Windows through WSL2. The original repo and learning curriculum remain available. These steps move the managed environment to the maintained family without deleting the old checkout, changing its remote, or copying account credentials.

There is no Groundwork-on-Omarchy migration in this task. A working Omarchy desktop uses the dedicated Omarchy repo's first-run instructions.

## Choose the destination

| Existing environment | Maintained entry point |
|---|---|
| macOS | `groundwork-mac` |
| Non-Omarchy Linux | `groundwork-linux` |
| Windows using WSL2 | `groundwork-windows`, inside the same WSL2 distro |

Linux and Windows currently route to the shared provisioning implementation in a visible `groundwork-mac` checkout. The wrapper repo is the platform entry point; the engine checkout is the chezmoi source and update owner. Do not copy or fork its managed home files into each wrapper.

## Preserve the current state

Run `chezmoi source-path` to locate the actual old source; do not assume it is `~/code/groundwork`. Inspect its Git status and preserve uncommitted edits with your normal Git workflow or a separate backup. Leave that checkout in place throughout migration.

Make a private backup outside both checkouts of your chezmoi configuration directory, any custom config path, and the current managed settings. The standard configuration directory is `${XDG_CONFIG_HOME:-$HOME/.config}/chezmoi`. Keep its permissions private: it contains stored identity and profile answers. Existing Groundwork backups and `groundwork-restore` remain your recovery path for files it previously managed; inspect their documented coverage before relying on them.

Retain `~/.ssh`, SSH agents/Keychain entries, Git local overlays, `~/.zshrc.local`, `~/.config/tmux/tmux.local.conf`, user-owned app settings, and provider credentials on the machine. Do not copy those into a repo. Port useful source edits deliberately; copying the entire old `home/` tree would replace the new defaults with historical ones.

## Prepare without applying

Clone the destination repo over HTTPS to a new directory. Public copies need no GitHub login; use an authorized account for a private fork. Do not rename the old checkout or repoint its remote. On Linux/WSL, run the entry point's `bootstrap.sh --prepare-only`; it prepares the shared engine without applying it. On macOS, clone `groundwork-mac` itself without running its bootstrap script for this migration.

Inspect the engine's changes and keep it clean before proceeding. In the commands below, `new_engine` is that engine checkout's absolute path; change its assignment if you chose another location.

## Preview with existing answers

Use the existing chezmoi config so current profile choices, identities, and overrides remain in effect:

```bash
new_engine="$HOME/code/groundwork-mac"
chezmoi --source "$new_engine" diff
```

Review every affected path. Scripts can install packages and apply defaults when you later apply; a file diff is not a preview of every external side effect, so inspect the new engine's `home/run_*` scripts too. Confirm that `reset_existing_configs` is false in the stored data unless you intentionally want the documented reset operation.

Do not use `chezmoi init --prompt` to migrate. It replays the interview with template defaults and can reset valid stored preferences. Do not use `--force`, reset an old checkout, or delete local app state to make a conflict disappear. Preserve any unrecognized custom config fields rather than replacing the whole config with a fresh interview's output.

An old installation without a multiplexer selection retains the tmux path. T3 Code Nightly and Herdr are the intended tools; authenticate providers locally in the environment where they run. Do not run `groundwork-configure` during temporary-source preview or acceptance: it uses the saved source, which still points to the old checkout.

## Apply, accept, then adopt the new source

Once the preview and script effects are understood, apply explicitly:

```bash
chezmoi --source "$new_engine" apply
```

If it fails, stop and retain the error; partial application is not a completed migration. Do not start `update-all` against the old source while repairing the new one.

Open a fresh terminal and verify shell startup, Git identity for personal/work repositories, SSH access, the selected multiplexer, Omarchy-aligned pane/tab/session keys, T3 Code Nightly, Herdr, and one small provider task. Follow the destination's Tailscale guide and test the required remote connections in both directions. Confirm local overlays and app data remain available.

After those checks pass, run `chezmoi edit-config` and change only the root `sourceDir` to the new engine checkout. Keep existing data/profile fields and unrelated config intact. Then run `chezmoi source-path` to confirm it resolves to the new engine and `chezmoi diff` to confirm the default command now uses that source. `update-all` must resolve the new source before you use it again.

After confirming that saved source selection, use `groundwork-configure` to select Both if you want Herdr primary with tmux still installed.

## Roll back or keep the old checkout

If acceptance fails, retain both checkouts and your backups. Restore the prior `sourceDir` using your private config backup or `chezmoi edit-config`, then inspect the old source's diff before reapplying it. Restoring source selection alone does not undo packages or defaults already changed; use the applicable Groundwork restore/OS recovery instructions for those effects.

Leave the original checkout until you are satisfied with the new environment. Migrating does not require archiving, deleting, rewriting, or updating the original `groundwork` repository. Later retirement is an owner decision.
