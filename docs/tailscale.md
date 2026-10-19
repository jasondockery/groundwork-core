# Tailscale across Groundwork environments

Use one personal tailnet to reach your computers by MagicDNS name, then use each destination's supported SSH service. Keep agent work on the machine that owns its repository and credentials; connect from another machine without copying secrets.

This is the shared security and connection guide. Package installation, service startup, and OS permissions belong to the environment repos: [Omarchy on Apple Silicon](https://github.com/jasondockery/groundwork-omarchy-mac-arm64/blob/main/docs/remote-access.md) and [macOS/Linux provisioning](https://github.com/jasondockery/groundwork-mac). The learning curriculum remains in the original [Groundwork site](https://jasondockery.github.io/groundwork/) for now.

Reviewed against official documentation on 2026-10-18. A tailnet is your Tailscale network. Work devices must follow the organization's policy; do not bridge personal and work networks or copy credentials between them.

## Set up the tailnet once

1. Protect the identity-provider account used for Tailscale with MFA or a passkey. Use that same Tailscale identity on your personal computers.
2. Enable device approval in the admin console and approve only machines you recognize. Enable MagicDNS so names work without an IP-address list.
3. Keep personal desktops and laptops user-owned rather than tagged, so the owner-based policy below applies. Keep their node-key expiry enabled and check renewal before traveling. An unattended server can have a deliberate exception with a documented recovery path; disabling expiry everywhere is not the default.
4. Review access controls. A default allow-all rule permits more than SSH; adding a narrow rule does not override a wider existing grant. Keep the policy in your own private administration records, outside this public-ready repo.

For a new personal tailnet used only for terminal access, this is a minimal policy example. For an existing tailnet, reconcile it with the current policy instead of replacing unrelated rules:

```json
{
  "grants": [
    {
      "src": ["autogroup:member"],
      "dst": ["autogroup:self"],
      "ip": ["tcp:22"]
    }
  ],
  "ssh": [
    {
      "action": "check",
      "src": ["autogroup:member"],
      "dst": ["autogroup:self"],
      "users": ["autogroup:nonroot"]
    }
  ]
}
```

The network grant allows SSH to your own user-owned devices. The separate SSH rule uses the default 12-hour reauthentication period and excludes root. It omits a custom `checkPeriod`, which requires a paid plan. Use explicit permitted local account names instead of `autogroup:nonroot` if a destination has other users. Tagged servers and devices owned by another identity need their own reviewed rules; they are intentionally outside this example.

Use the policy editor's validation and tests before saving: your devices should reach each other on TCP 22, other users should not reach them, and root SSH should be denied. This template is guidance, not a claim that your tailnet has been configured or tested.

## Enroll each machine locally

Install through the environment's supported package source and start its service. Use interactive browser sign-in and device approval, keeping reusable auth keys out of these repositories. Enable client DNS settings so Tailscale can manage MagicDNS. Do not add static machine addresses to hosts files or copy another OS's resolver workaround.

Tailscale SSH destinations need both a network rule for TCP 22 and an SSH rule. Enabling Tailscale SSH does not enable a public OpenSSH daemon; existing ordinary SSH on other interfaces is independent. Use the destination's setup guide for the exact command and preserve unrelated Tailscale preferences. Never add `--reset` just to silence an existing-options warning.

## From your other machines

Install Tailscale and sign in to the same personal tailnet on each source. Any Tailscale platform can be an SSH client:

| Destination | How inbound terminal access works |
|---|---|
| Omarchy or other Linux | Enable Tailscale SSH after reviewing network and SSH policy. |
| macOS with the normal Tailscale app | Enable macOS Remote Login for selected users. Connect with ordinary SSH over the tailnet; authorize your SSH key on that Mac. The app cannot serve Tailscale SSH. |
| Headless macOS using open-source `tailscale` + `tailscaled` | Tailscale SSH is supported. Use this variant only deliberately; do not run it alongside the desktop Tailscale app. |
| Windows | Use Tailscale on the Windows host and Windows OpenSSH Server for selected users. WSL2 is a separate Linux environment; reaching the Windows host does not automatically expose a WSL SSH server. |

From a source terminal, substitute the destination's local login name and MagicDNS machine name:

```bash
tailscale status
tailscale ping MACHINE
ssh LOCAL_USER@MACHINE
```

The uppercase words are placeholders, not literal hostnames. `tailscale ping` checks the Tailscale path; a successful ping does not prove the port or SSH policy allows the login. A relayed path still works; a direct path is usually faster. Authenticate in the browser when check mode requests it.

Repeat the SSH test in both directions for every pair you need before leaving a machine unattended. In the remote shell, run `hostname`, then `tmux attach` or `herdr`; detach with `Ctrl+Space`, then `d`. Keep GitHub SSH keys separate: they authenticate Git operations, not Tailscale SSH. Never disable SSH host-key checking to work around a mismatch.

## Agent tools and screens

Run T3 Code on the machine that owns the repository and agent credentials. Keep its web interface on loopback. For a remote service listening on `127.0.0.1:3000`, for example, forward it from the source machine:

```bash
ssh -N -L 127.0.0.1:3300:127.0.0.1:3000 LOCAL_USER@MACHINE
```

Open `http://127.0.0.1:3300` locally. For T3 Code, substitute its actual listening port printed at startup. Do not bind agent interfaces to `0.0.0.0` just to reach them remotely.

Tailscale enrollment alone does not install or enable a desktop-sharing server. Groundwork prepares the appropriate desktop path in each environment; local OS permissions, device enrollment, and cross-machine acceptance remain necessary. Headless systems, development containers, and WSL do not get a desktop server from the Unix provisioning engine.

| Destination | Server and supported client |
|---|---|
| Apple Silicon Omarchy | Its installer configures authenticated WayVNC to start with the logged-in desktop, restricted to the Tailscale interface. Use macOS Screen Sharing or a supported VNC client on TCP 5900. |
| macOS desktop | Native Screen Sharing; approve it once in System Settings and allow only intended local users. macOS then owns automatic startup. Use Screen Sharing from another Mac. |
| Other Linux desktop | Use the desktop's supported sharing service; GNOME uses its native Remote Desktop settings and RDP client. Follow the Linux environment guide instead of installing a competing desktop or applying Omarchy files. |
| Windows host | Native RDP on supported Windows editions, with Network Level Authentication and a Tailscale-scoped host firewall rule. Use Windows App or another supported RDP client. Windows Home cannot host native RDP. WSL is not the Windows desktop server. |

For desktop access, add a separate owner-scoped network grant to your private tailnet policy. Retain the SSH grant/check-mode rule above. Include only the ports actually selected on your hosts: TCP 5900 for VNC/Screen Sharing, TCP 3389 for Windows RDP, or the actual port shown by the Linux RDP server (often 3389 or 3390). For example, when only VNC is selected:

```json
{
  "src": ["autogroup:member"],
  "dst": ["autogroup:self"],
  "ip": ["tcp:5900"]
}
```

This is one grant object to reconcile into `grants`, not a replacement policy. Validate that your own approved devices can reach the selected port and other users cannot. An SSH check-mode rule applies to SSH, not to VNC or RDP authentication. A broader existing allow rule still overrides the intended restriction; review all effective grants.

The service must also be installed, running, authenticated, and allowed by the host firewall. Tailnet rules do not filter ordinary LAN traffic. Omarchy enforces `tailscale0` on the listening socket; native OS services may listen on other interfaces, so use their supported host/network restrictions when needed. Do not disable a firewall or open a router port to work around a failed connection. No Funnel, subnet routes, or exit node is required.

Verify viewing and keyboard/mouse control from a second device, then repeat after reboot and desktop login. Desktop startup does not bypass disk encryption, OS privacy consent, the lock screen, or sleep/power limitations. Use terminal access separately for recovery. Passwords, certificates, tailnet policy, and machine addresses stay local, outside Git.

## Keep it working

- Use each environment's supported updater for its Tailscale client; desktop apps and OS packages have different update owners. Review security updates promptly.
- Recheck device approval, access controls, key expiry, and sleeping/reboot behavior before travel. Tailscale cannot wake a powered-off computer or unlock FileVault/LUKS before the OS starts.
- Avoid reauthentication or changes to DNS, SSH policy, or Tailscale service state through your only remote connection. Keep a local or other independent recovery path.
- If a name fails, check Tailscale status, device approval, client DNS settings, and expiry before editing DNS files. On macOS, `nslookup` and `host` can bypass the system resolver; test with `ssh` or `ping` too.
- Remove retired devices from the admin console. Do not put reusable auth keys, Tailscale state files, SSH keys, machine names, or account identifiers in this repo.

Official references: [security best practices](https://tailscale.com/docs/reference/best-practices/security), [grants](https://tailscale.com/docs/features/access-control/grants), [Tailscale SSH](https://tailscale.com/docs/features/tailscale-ssh), [MagicDNS](https://tailscale.com/docs/features/magicdns), [macOS variants](https://tailscale.com/docs/concepts/macos-variants), and [key expiry](https://tailscale.com/docs/features/access-control/key-expiry).
