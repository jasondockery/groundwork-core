# Agents

This repo owns shared operational guidance and cross-environment procedures. The learning curriculum remains in the original Groundwork repo for now; its imported HTML here is historical reference. This is not a machine installer.

Read `README.md` and `AI_THESIS.md` before changing the shared pages.

## Rules

- Environment repos pin this repo as a `core` submodule. Do not copy these pages into `groundwork-mac` or `groundwork-omarchy-mac-arm64` as a second source.
- Shell keys, tmux keys, package installs, desktops, and account material belong in the environment repo.
- Do not add Homebrew, chezmoi source, Hyprland config, SSH keys, account emails, or org remotes here.
- Do not tell an Omarchy machine to run `chezmoi apply` or `bootstrap-mac.sh`.
- The original Groundwork repo stays where it is. These family repos are the split.
- Keep the original `groundwork` repo unchanged; it is curriculum and historical context for this task. Omarchy's conventions are the target where they fit, not the older Groundwork keymap.
- Tailscale policy, security guidance, MagicDNS, and connection verification have one source in `docs/tailscale.md`. Installation and OS permissions stay in environment repos.
- T3 Code Nightly and Herdr are the selected shared tool direction; do not invent an upstream `edge` channel or install anything from this documentation-only repo.
- Use [Compass](https://github.com/jasondockery/compass) as shared engineering guidance and the shared Renovate preset for dependency policy. These references do not imply receipt-verified projection or central-runner coverage.

## Layout

| Path | Role |
|---|---|
| `docs/` | Shared teaching pages. See `docs/README.md`. |
| `skills/` | Local documentation procedure and imported references; read `skills/README.md` before selecting one. |
| `skel/` | Project scaffolds a person can copy. |
| `AI_THESIS.md` | North star. Environment repos should point here rather than restating it. |
