# Brave, the default browser

Brave is the default browser Groundwork offers on the Mac, on Linux, on Windows, and on Omarchy. It is a choice of default, not a rule about how someone develops. A person can keep another browser. Shields, Brave's built-in blocker, blocks ads and trackers. Brave is Chromium-based, so Chrome Web Store extensions and Chromium policies work, and each OS in the family has an official install path.

This page is the contract. [The decision record](decisions/default-browser-brave.md) says why Brave, and why the other candidates were set aside. The machine-readable spec is [`browser/brave.json`](../browser/brave.json). [`browser/README.md`](../browser/README.md) is the field reference. Environment repos install Brave, render the policies, and offer the extension. They reference this page. They do not keep a second copy.

Reviewed on 2026-10-29 against Brave's policy templates in [brave-core](https://github.com/brave/brave-core) `cd9be34acde11812242364dded5f6aa7284be206`, Chromium's [PasswordManagerEnabled](https://github.com/chromium/chromium/blob/main/components/policy/resources/templates/policy_definitions/PasswordManager/PasswordManagerEnabled.yaml) template, [Brave's Linux install page](https://brave.com/linux/), the [AUR `brave-bin` package](https://aur.archlinux.org/packages/brave-bin), [Omarchy's browser manual](https://github.com/omacom/omarchy/blob/quattro/manual/23-browsers.md) and [`omarchy-install-browser`](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-install-browser), the [Homebrew cask `brave-browser`](https://formulae.brew.sh/cask/brave-browser), [winget `Brave.Brave`](https://github.com/microsoft/winget-pkgs/tree/master/manifests/b/Brave/Brave), and [Windows default-app settings](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-default-apps-settings).

## What "default" means

The browser is Brave's release channel. It is not Brave Origin. On Linux the desktop id is `brave-browser.desktop`. On macOS the bundle id is `com.brave.Browser`.

Groundwork makes Brave the default once, automatically, on every OS. Brave becomes the default the first time it is installed and passes that OS's check, and the environment switches the default with the OS's preferred method from the table under "Setting the default". It never overrides a default the person chose later, it respects a saved "no", and when the current default was chosen by the person it only offers. A default was not chosen by the person when it is unset or is the OS's or distribution's shipped default: Safari on macOS, Edge on Windows, Chromium on Omarchy, or the distribution's packaged default browser on other Linux. Nothing is uninstalled automatically, and no profile data is deleted. A prompt to import data or to install an extension defaults to no. A run with no desktop session, such as SSH, cron, or headless, does not change the default or ask. It prints one line and leaves the machine as it is. A run in a desktop session, `update-all` included, may make the one-time switch.

That one line names the preferred method and the exact command in the table below. A Chrome, Chromium, or Brave install from any other source gets the same one line. Brave installed from Flatpak or Snap is a non-preferred source: Brave's Linux page says those packages are not yet working as well as the native packages.

Bookmarks, history, and extensions move with Brave's own importer at `brave://settings/importData`. Passwords stay in Bitwarden, the only extension Groundwork offers. `PasswordManagerEnabled` is false when Bitwarden is the password manager. Groundwork does not copy a profile directory.

## Install

Install with the OS's preferred method. The commands below are what the one-line notice prints. The environment repo owns the installer. This repository does not run it.

| OS | Preferred method | Command the notice prints |
| --- | --- | --- |
| Debian, Ubuntu, Mint | Official Brave apt repository, package `brave-browser`, amd64 and arm64 | `sudo apt install brave-browser` |
| Fedora 41 and newer | Official Brave repository via `dnf config-manager addrepo`, package `brave-browser` | `sudo dnf install brave-browser` |
| openSUSE | Official Brave repository, package `brave-browser` | `sudo zypper install brave-browser` |
| Arch | AUR `brave-bin`, maintained by Brave, `x86_64` and `aarch64` | The environment's AUR helper installing `brave-bin` |
| Omarchy | `omarchy-install-browser brave`, which installs AUR `brave-bin` and creates `/etc/brave/policies/managed` | `omarchy-install-browser brave` |
| macOS | Homebrew cask `brave-browser` (checksum-checked, `auto_updates`, macOS 13 or newer) | `brew install --cask brave-browser` |
| Windows | winget `Brave.Brave`, user or machine scope | `winget install --id Brave.Brave` |

The apt, dnf, and zypper repository files and keys are the ones on [brave.com/linux](https://brave.com/linux/). Copying only the install line, without that repository, does not install Brave.

## Setting the default

Jason decided on 2026-10-30 to make the full switch to Brave on every OS. The first time Brave is installed and passes that OS's check, the environment sets the default once, using the method below, and prints one line saying so and how to switch back. Where the OS forces a confirmation, automatic means Groundwork starts the change once and the person confirms it. A default the person changes later is never overridden. A saved decline is respected. When the current default was chosen by the person, meaning it is not unset and not the OS's or distribution's shipped default, Groundwork only offers, and the offer waits for a yes.

| OS | Method |
| --- | --- |
| macOS | Homebrew formula `defaultbrowser`. It returns before the person clicks the confirmation dialog, so Groundwork triggers it once, the person clicks, and Groundwork re-checks the default afterwards. Choosing "Keep Safari" in the dialog counts as done, as a decline, and is never asked again. The argument is the handler `defaultbrowser` prints for Brave. |
| Windows | Windows does not let programs set the default. Groundwork opens `ms-settings:defaultapps` on Brave's page once, automatically, and the person confirms. It never uses UserChoice-hash workarounds. |
| Linux, except Omarchy | `xdg-settings set default-web-browser brave-browser.desktop` |
| Omarchy | `omarchy default browser brave`, to switch back `omarchy default browser chromium` |

`omarchy-default-browser` with no argument prints the current default. Its examples also show `omarchy default browser brave`. Either form is the Omarchy command.

With no desktop session, such as SSH or cron, Groundwork does not change the default. It defers to the next run in a desktop session and prints one line saying so.

Each environment records the one-time state, done or declined, in its own per-user state file, for example `%LOCALAPPDATA%\Groundwork\brave-default.json` on Windows. A recorded state is never asked or applied again.

## Policies and extensions

`browser/brave.json` is the only list of policy overrides. Each one differs from Brave's effective default and has a reason. Leo, Brave's AI assistant, is off: `BraveAIChatEnabled` is false. That one policy removes Leo's sidebar and the address-bar Leo provider. There is no second policy for the address bar or the new tab page. The new-tab day-zero input pref ships off.

`BraveLocalAIEnabled` is false. Jason decided on 2026-10-29 to turn off Brave's AI features because he uses separate AI tools. This policy is the master switch for local AI, including later on-device surfaces. The history-embeddings pref is already false. Unset would leave that switch on.

Bitwarden (`nngceckbapebfimnlniiiahkandclblb`) is the only extension Groundwork offers, on every OS. It is offered, never force-installed. Jason decided on 2026-10-29 to stick with Bitwarden only. No AI or other extensions are offered. `PasswordManagerEnabled` is false only when Bitwarden is the password manager, so the built-in manager does not compete with it. uBlock Origin Lite stays out with the rest. Shields already blocks ads and trackers, and two blockers on one page cause breakage.

Privacy-preserving product analytics (P3A) and the daily usage ping are off. The usage ping is sent to `usage-ping.brave.com`. Package updates, Sparkle on macOS, and Brave's Windows updater do not use that ping.

## Where Omarchy differs

Chromium stays installed. It is part of the Omarchy base system, and web apps fall back to it. Groundwork does not remove it.

Omarchy's installer creates `/etc/brave/policies/managed` and applies Omarchy's theme and browser flags. Groundwork adds its policy JSON in that directory. It does not replace Omarchy's theme or flags, and it does not tell an Omarchy machine to run `chezmoi apply`.

Brave Origin is a different install (`omarchy-install-browser brave-origin`, desktop id `brave-origin.desktop`). This contract is Brave release. Do not install Brave Origin to satisfy it. Origin builds compile some of these features out, so the same policy file is the wrong tool there.
