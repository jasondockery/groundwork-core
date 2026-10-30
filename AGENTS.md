# Agents

This repo owns shared operational guidance and cross-environment procedures. The learning curriculum remains in the original Groundwork repo for now; its imported HTML here is historical reference. This is not a machine installer.

Read `README.md` and `AI_THESIS.md` before changing the shared pages.

## Rules

- Environment repos pin this repo as a `core` submodule. Do not copy these pages into `groundwork-mac` or `groundwork-omarchy-mac-arm64` as a second source.
- Shell keys, tmux keys, package installs, desktops, and account material belong in the environment repo.
- Do not add Homebrew, chezmoi source, Hyprland config, SSH keys, account emails, or org remotes here.
- `omarchy/` may hold data-only manifests consumed by environment repos. It must not hold installers or Hyprland config.
- Do not tell an Omarchy machine to run `chezmoi apply` or `bootstrap-mac.sh`.
- The original Groundwork repo stays where it is. These family repos are the split.
- Keep the original `groundwork` repo unchanged; it is curriculum and historical context for this task. Omarchy's conventions are the target where they fit, not the older Groundwork keymap.
- Tailscale policy, security guidance, MagicDNS, and connection verification have one source in `docs/tailscale.md`. Installation and OS permissions stay in environment repos.
- Syncthing shared folders, the FreeTube one-machine rule, and device pairing have one source in `docs/syncthing.md`. The decision record is `docs/decisions/syncthing-shared-folders.md`. Package installation and the service manager stay in the environment repos. Device IDs, API keys, and Tailscale addresses stay on the machine.
- Brave browser policy and the one offered extension have one source in `browser/`. The contract is `docs/browser.md`. The decision record is `docs/decisions/default-browser-brave.md`. Installers stay in the environment repos.
- An installer that needs administrator permission asks once at the start when a terminal is available. When nobody can enter a password, it sets aside only the steps that need that permission, continues the rest, and retries those steps on the next apply from a terminal. It does not record that partial install as finished. A step later work depends on, such as the Linux packages Homebrew itself needs, stops with a recovery command instead of continuing.
- Commit identity (no agent attribution, no alternate-account identity) has one contract in `docs/commit-identity.md` and a reference checker in `commit-guard/`. The denylist values live in a user-level file and never in this repo. Hook installation stays in the environment repos.
- T3 Code Nightly and Herdr are the selected shared tool direction; do not invent an upstream `edge` channel or install anything from this documentation-only repo.
- Engineering work follows Compass: start at `.compass/COMPASS.md`, with terms in `.compass/TERMINOLOGY.md`. Load `skills/reviewable-agent-workspaces/SKILL.md` before implementation or worktree changes, `skills/concurrent-agent-runtimes/SKILL.md` before starting or inspecting concurrent processes, and `skills/repeatable-agent-execution/SKILL.md` before the first edit in a checkout and before final proof. Selected skills, loaded from `skills/` when a task touches their area: `acceptance-evidence`, `accessible-product-development`, `agent-orchestration`, `ai-backend-change`, `ci-workflow-change`, `dependency-change`, `developer-tool-change`, `field-failure-backpressure`, `github-delivery-workflow`, `inclusive-content-design`, `inclusive-product-foundation`, `independent-code-review`, `internationalization-first`, `performance-sensitive-change`, `privacy-by-design`, `repo-contribution-etiquette`, `secure-by-design`, `shell-script-change`, `skill-authoring`, `terminal-program-ux`, `testing-strategy`, `toolchain-authority`. GitHub writes follow `repo-contribution-etiquette` (act as the account that owns the repository).
- The shared Renovate preset covers dependency policy; that reference does not imply central-runner coverage.

## Layout

| Path | Role |
|---|---|
| `docs/` | Shared teaching pages. See `docs/README.md`. |
| `skills/` | Opted-in Compass skills (receipt-verified) and local documentation skills; read `skills/README.md` before selecting one. |
| `skel/` | Project scaffolds a person can copy. |
| `omarchy/` | Data-only Omarchy plugin manifests. See `omarchy/README.md`. |
| `browser/` | Shared Brave default, policy overrides, and the one offered extension. See `browser/README.md`. |
| `commit-guard/` | Reference commit-msg and pre-push checker plus denylist format. Environment repos wire it into hooks. |
| `AI_THESIS.md` | North star. Environment repos should point here rather than restating it. |
