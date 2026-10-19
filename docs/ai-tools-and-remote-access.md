# AI workbench and remote access

`groundwork-core` owns shared guidance. It does not install packages or apply machine configuration; each environment repo owns those operations.

## T3 Code Nightly and Herdr

Groundwork targets T3 Code Nightly (the upstream fast-moving channel) alongside Herdr. The environment repositories own the installation and supported platform details. Use `T3CODE_CHANNEL=nightly` for the official CLI installer and `t3-code@nightly` for the Homebrew desktop app. Preview releases are release-pipeline artifacts, not the selected train. Existing provider credentials and application data stay on their machine; switching the selected release train must not delete them.

The Groundwork environments install T3 Code on supported personal macOS, Linux, WSL2, headless, and Omarchy setups, and install Herdr across supported profiles. macOS desktops get T3 Code's app. Linux x86_64 and ARM64, Apple Silicon macOS headless systems, and Omarchy use its `t3` CLI and local web interface. T3 Code currently does not publish a CLI build for Intel macOS; its desktop app remains available there. Work-profile AI tools remain governed by the existing personal/work setting. WSL2 is a Linux backend; use T3 Code's desktop app on the Windows host when desired and connect it to the WSL environment.

T3 Code needs at least one agent provider installed and authenticated on the machine that runs the agent. Installing T3 Code does not sign in to Codex, Claude, or another provider. Herdr is the terminal workspace manager; it runs alongside tmux. On Omarchy, keep the stock `Ctrl+Space` tmux prefix and learn Omarchy's `Super+Ctrl+Return` Herdr launcher. Groundwork's macOS/Linux terminal defaults use `Ctrl+Space` and matching pane-navigation conventions.

The environment repositories own the install details:

- [groundwork-mac](https://github.com/jasondockery/groundwork-mac) installs both across its supported macOS and Linux-family profiles, including WSL2 and headless machines.
- [groundwork-omarchy-mac-arm64](https://github.com/jasondockery/groundwork-omarchy-mac-arm64) installs them on Apple Silicon Omarchy without replacing Omarchy's desktop, tmux, or shell defaults.

Use the upstream [T3 Code install guide](https://github.com/pingdotgg/t3code/blob/main/docs/user/install.md) and [Herdr install guide](https://herdr.dev/docs/install/) for platform limits and updates. Herdr's Windows support is beta; Groundwork does not manage a native Windows installation.

## Tailscale

Use the [shared Tailscale guide](tailscale.md) for tailnet security, MagicDNS, owner-scoped access, SSH check mode, platform capabilities, and two-way verification. Environment repos own installation, service startup, and OS permissions; they reference that guide rather than copying its policy.

For visual agent supervision, follow [desktop access](tailscale.md#agent-tools-and-screens) as well as SSH setup. Tailscale's machine list proves enrollment, not screen sharing: each host needs its appropriate desktop server and network port grant. Omarchy configures WayVNC automatically; native macOS, Linux desktop, and Windows services retain their required local permission and credential steps. Use each OS's supported client rather than forcing one protocol everywhere.
