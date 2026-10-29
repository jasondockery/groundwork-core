# Decision: Brave is the default browser

Status: accepted
Date: 2026-10-29
Issue: [groundwork-core#34](https://github.com/jasondockery/groundwork-core/issues/34)

The operational contract is [Brave, the default browser](../browser.md). The data is [`browser/`](../../browser/README.md). This page records why that default exists.

Reviewed on 2026-10-29 against brave-core `cd9be34acde11812242364dded5f6aa7284be206` (committed 2026-10-29) and Chromium's PasswordManagerEnabled template as of chromium `main` the same day. The last commit that touched that Chromium file was `df375766579b4cf97c63b55c59bd214a984d3369` on 2026-03-10. Brave's Group Policy article is [Group Policy](https://support.brave.app/hc/en-us/articles/360039248271-Group-Policy). This environment received HTTP 403 for that page, so each policy name and default below was read from the template that generates Brave's and Chromium's policy definitions. Brave documents that those templates cover Chromium policies at [chromeenterprise.google/policies](https://chromeenterprise.google/policies/).

## Decision

Brave's release channel is the default browser on every Groundwork machine: macOS, Linux, Windows, and Omarchy. One spec in this repo holds the browser choice, the policy values Groundwork sets, the extensions it offers, and the migration rule. Installers stay in the environment repos.

This supersedes the 2026-10-24 browser choice: Chrome Stable on macOS and Omarchy's Chromium on Omarchy ([groundwork-mac#27](https://github.com/jasondockery/groundwork-mac/issues/27), [groundwork-core#9](https://github.com/jasondockery/groundwork-core/issues/9), both closed).

Jason chose Brave for privacy. Shields blocks ads and trackers by default. The browser is Chromium-based, so the existing Chrome Web Store catalog and Chromium policies still apply. Every OS in the family has an official install path.

Brave release is not Brave Origin. Origin is a separate branded build. Omarchy can install it, and this decision does not.

## Policy overrides

A row is here only when the value differs from the effective default on Brave release. Brave's own templates often set `default: null`, which means the policy is unset. The effective default is the behavior the template describes for that unset state, checked against the pref registration in the same brave-core commit.

| Policy | Value | Effective upstream default | Where that default was checked |
| --- | --- | --- | --- |
| `BraveRewardsDisabled` | true | false. Unset means Rewards stays enabled. | `components/policy/resources/templates/policy_definitions/BraveSoftware/BraveRewardsDisabled.yaml` |
| `BraveWalletDisabled` | true | false. Unset means Wallet stays enabled. | `BraveWalletDisabled.yaml` in that same directory |
| `BraveVPNDisabled` | true | false. Unset means VPN stays enabled. | `BraveVPNDisabled.yaml` |
| `BraveAIChatEnabled` | false | true. Unset means AI Chat stays enabled. The pref `kEnabledByPolicy` registers true. | `BraveAIChatEnabled.yaml`; `components/ai_chat/core/common/pref_names.cc` registers `kEnabledByPolicy` true; `components/ai_chat/core/browser/utils.cc` `IsDisabledByPolicy` |
| `BraveP3AEnabled` | false | true on Brave release. Unset means P3A stays enabled. The pref registers `!IS_BRAVE_ORIGIN_BRANDED`. | `BraveP3AEnabled.yaml` ("enabled by default"); `components/p3a/p3a_service.cc` `RegisterBooleanPref(kP3AEnabled, !BUILDFLAG(IS_BRAVE_ORIGIN_BRANDED))` |
| `BraveStatsPingEnabled` | false | true. Unset means the usage ping stays enabled. The pref registers true. | `BraveStatsPingEnabled.yaml`; `browser/brave_local_state_prefs.cc` registers `kStatsReportingEnabled` true |
| `PasswordManagerEnabled` | false, only when a third-party password manager is chosen | true | Chromium `components/policy/resources/templates/policy_definitions/PasswordManager/PasswordManagerEnabled.yaml` (`default: true`). Brave's policy map does not replace this Chromium policy. |

Leo is Brave's AI assistant (AI Chat). `BraveAIChatEnabled` false is a managed preference, and `IsAIChatEnabled` is then false. Brave's `browser/ai_chat/ai_chat_policy_browsertest.cc` shows that this removes the sidebar item, the address-bar Leo autocomplete provider, the side panel entry, and the context-menu item. Those surfaces are not separate policies, so they do not get their own rows.

The new-tab day-zero input is the pref `kNtpInputDayZeroEnabled`, registered false in `pref_names.cc`. It has no policy. Groundwork does not invent one.

`BraveLocalAIEnabled` was read in `BraveLocalAIEnabled.yaml`. Unset means local AI stays enabled. That feature is on-device history embeddings, not Leo. It is not overridden.

Also checked and left unset, because the effective default is already what Groundwork wants, or because no change was called for:

| Policy | Effective default when unset | Source |
| --- | --- | --- |
| `BraveNewsDisabled` | News stays available | `BraveNewsDisabled.yaml` |
| `BraveTalkDisabled` | Talk stays available | `BraveTalkDisabled.yaml` |
| `TorDisabled` | Tor stays available when the person opens a private window with Tor | `TorDisabled.yaml` |
| `BraveWebDiscoveryEnabled` | Off | `BraveWebDiscoveryEnabled.yaml` ("disabled by default") |
| Shields | On. The templates expose per-URL exceptions, not a global off switch. No URL list is set. | `BraveShieldsDisabledForUrls.yaml`, `BraveShieldsEnabledForUrls.yaml` |

`BraveStatsPingEnabled` stays in the override list because browser updates still work with the ping off. `browser/brave_stats/buildflags.gni` sets the ping host to `https://usage-ping.brave.com`. `BraveStatsUpdater::OnServerPingTimerFired` returns before `SendServerPing` when `kStatsReportingEnabled` is false. Linux updates come from the package repository, macOS updates come from Sparkle (`auto_updates` on the Homebrew cask), and Windows updates come from Brave's updater. None of those read this pref.

P3A's template calls the feature opt-in in its opening sentence and "enabled by default" in the unset sentence. The pref registration matches the unset sentence for Brave release. The opening sentence matches Brave Origin, which Groundwork is not installing. The recorded upstream default is true.

## Extensions

Jason decided on 2026-10-29 to stick with Bitwarden only. No AI or other extensions are offered. Bitwarden (`nngceckbapebfimnlniiiahkandclblb`) is the only extension Groundwork offers in Brave, on every OS. The extension is offered, never force-installed. There is no `ExtensionInstallForcelist` entry.

The update URL is `https://clients2.google.com/service/update2/crx`. The id and URL were checked against [Bitwarden's extension deploy page](https://bitwarden.com/help/browserext-deploy/).

`PasswordManagerEnabled` stays false, and only when Bitwarden is the password manager. 1Password is not a condition and not an offered extension.

groundwork-mac's `home/dot_local/share/groundwork/browser-extensions.tsv` is not copied here. A one-row catalog file would duplicate `browser/brave.json`, so there is no `browser/extension-catalog.tsv`. That old list included 1Password, uBlock Origin Lite, and several other extensions. They are not offered. uBlock Origin Lite would also overlap Shields: Shields already blocks ads and trackers with the same kind of filter lists, and two blockers on one page cause breakage.

## Alternatives

### Chrome

The 2026-10-24 choice on macOS. Chrome does not ship Shields. A Google account and Chrome's own product reporting are the default shape of that browser. The extension catalog was already written for Chrome Web Store ids, and Brave installs those same extensions, so staying on Chrome is not required for the catalog.

### Chromium

Omarchy's base browser, and the previous Omarchy default. It has no Shields and no Brave's reward, wallet, or VPN prompts to turn off, because those features are not in it. Web apps on Omarchy keep using Chromium. That is a fallback, not the default browser.

### Firefox

Firefox has its own extension store and its own policy names. The catalog, the Chromium policy list, and Omarchy's Chromium-family browser flags would not carry over. Groundwork would be maintaining a second browser contract for a default it does not need.

### Helium

Helium is a Chromium fork aimed at removing more of the upstream browser. It does not give this family one official package path across Homebrew, winget, the Brave Linux repositories, the AUR package Brave maintains, and Omarchy's browser installer. Choosing it would be a second packaging and policy surface.

## Migration

Detect and offer, never force. Prompts default to no. Non-interactive runs and `update-all` print one line. The [browser contract](../browser.md) has the preferred command for each OS. Profile data stays until the person imports it with Brave's importer.
