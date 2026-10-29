# Brave browser spec

This directory is data. Environment repositories install Brave, render these
policies, and offer these extensions. They do not copy this list into a second
source, and they do not put an installer here.

The contract for people is [docs/browser.md](../docs/browser.md). The decision
is [docs/decisions/default-browser-brave.md](../docs/decisions/default-browser-brave.md).

Reviewed on 2026-10-29. The policy templates and pref defaults checked that day
are listed in the decision record. A new Brave release that changes one of
those defaults, or a new AI policy that ships on by default, invalidates the
review.

## brave.json

`schemaVersion` is `1`.

`default` names the browser. `id` is `brave` and `channel` is `release`. That
is Brave's normal desktop release, not Brave Origin. `desktopIds` are
reference names an environment can match. Linux is `brave-browser.desktop`.
macOS is the bundle `com.brave.Browser`.

`policies` lists only settings that differ from Brave's effective upstream
default. Each entry has:

| Field | Meaning |
| --- | --- |
| `name` | Policy name from Brave's or Chromium's policy templates. |
| `value` | The value Groundwork writes when the entry applies. |
| `upstreamDefault` | The effective value when the policy is left unset on Brave release. This is not the template's `default: null`, which means "unset". |
| `reason` | Why Groundwork overrides that default. Required. |
| `when` | Optional. When the condition is absent, or false on this machine, the environment does not write the policy. |

An entry whose `value` equals `upstreamDefault` does not belong in the file.

`extensions` is the whole offer list. There is one entry, Bitwarden
(`nngceckbapebfimnlniiiahkandclblb`), on every OS. `install` is `offer`.
Nothing in this file is force-installed. The entry has a Chrome Web Store
extension `id` (32 characters, `a` through `p`), the store `updateUrl`, and a
`reason`. The environment does not write a force-install policy. There is no
separate catalog file: a second list would be a second source.

`notes` records what Groundwork does not offer. Jason decided on 2026-10-29 to stick with Bitwarden only. No AI or other extensions are offered.

## How each OS renders a policy

Render only the policies that apply. Skip an entry whose `when` is not met.
Write `name` and `value`. Do not write `upstreamDefault`, `reason`, or `when`
into the browser policy store.

| OS | Where the value goes |
| --- | --- |
| Linux | One JSON file in `/etc/brave/policies/managed/`, mode `0644`, owner root and group root. |
| macOS | Managed preferences for `com.brave.Browser`, delivered by a configuration profile the user approves. |
| Windows | `HKLM\Software\Policies\BraveSoftware\Brave`. The environment maps each JSON boolean to the type in Brave's policy template. |

Omarchy already creates `/etc/brave/policies/managed` when it installs Brave.
The same JSON file goes there. Omarchy's theme and flags stay Omarchy's.

## Left at Brave's default

These were checked on 2026-10-29 and are not in `policies`, because Groundwork
is not changing them:

| Policy | Effective default when unset | Why it is absent |
| --- | --- | --- |
| `BraveNewsDisabled` | News stays available | No override. |
| `BraveTalkDisabled` | Talk stays available | No override. |
| `TorDisabled` | Tor stays available for a private window with Tor | No override. |
| Shields URL exceptions | No site list | Shields stays on. There is no global "turn Shields off" policy in the template set. |
| `BraveWebDiscoveryEnabled` | Off | Already the privacy outcome. |
| `BraveLocalAIEnabled` | On | On-device history embeddings, not Leo. Leo's sidebar, address-bar provider, and side panel are `BraveAIChatEnabled`. |

Leo's address bar and new-tab surfaces are not separate policies.
`BraveAIChatEnabled` set to false removes the sidebar item and the address-bar
Leo provider. The new-tab day-zero input pref defaults to off and has no
policy of its own.
