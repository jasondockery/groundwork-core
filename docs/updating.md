# Updating Groundwork

After setup, use the same two commands from any directory:

```bash
update-all
groundwork-update
```

`update-all` is routine maintenance for the environment you are in.
`groundwork-update` synchronizes and applies only that environment's Groundwork
configuration using saved choices. A configuration apply can install newly
declared tools; it does not mean every app or the operating system was upgraded.
Use the environment's configuration procedure to change preferences.

| Environment | Update owner and scope |
| --- | --- |
| macOS | The `groundwork-mac` chezmoi engine owns synchronization, configuration, classified Homebrew/App Store/tool upgrades, and supported maintenance. |
| Native Linux | `groundwork-linux` selects the same visible engine. Its installed commands own Groundwork configuration and supported tools; the distribution owns OS package updates. |
| WSL2 | `groundwork-windows` selects the same engine inside WSL. Its commands operate inside that Linux environment; Windows Update, native apps, and host permissions stay on Windows. |
| Omarchy on Apple Silicon | `groundwork-omarchy-mac-arm64` owns personal settings. Its `update-all` delegates system updates to `omarchy update`, then applies this layer and updates the selected T3 Nightly and installed Bitwarden user Flatpak. It never applies the chezmoi engine. |

The Linux and WSL entry-point repositories hold bootstrap and platform guidance,
not a second copy of managed configuration. Their checkout need not be pulled
before daily updates. Pull them deliberately when you need new bootstrap code or
host guidance. Core is documentation, not an installed updater. Environment
maintainers advance optional Core submodules deliberately to a reviewed commit;
daily commands do not follow Core's branch tip.

On Omarchy, `groundwork-update --check` (also `update-all --check`) fetches and
shows repository changes without advancing the checkout or changing the live
linked settings. A normal update displays the fetched changes before a
fast-forward. Local edits, detached or diverged branches, conflicting managed
settings, and concurrent updates require repair; the updater does not reset or
stash your work. Saved keyd, screen-sharing, and vault choices survive updates.

First-time setup remains separate. Existing chezmoi installations receive
`groundwork-update` on their next successful `update-all`. Existing Omarchy
installations run the updated `./install.sh` once, repeating any previously
chosen exclusions, to establish saved choices and install both commands.

A failed update can leave an already completed stage applied. Read its stage
report, repair the named problem, and retry the same command. A successful
configuration-only apply must not mark full maintenance successful or clear
pending maintenance. Fixture tests prove command behavior; app sign-in, native
desktop behavior, and remote access remain separate acceptance checks.
