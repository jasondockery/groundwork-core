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

Screen sharing is a separate, optional service. macOS Screen Sharing, Windows RDP, and Wayland screen-sharing servers have different setup and permissions. Add a narrowly scoped tailnet grant for the specific service only when you choose it; the terminal-only example above intentionally does not allow desktop ports. No port forwarding, Funnel, subnet routes, or exit node is required for machine-to-machine SSH.

## Keep it working

- Use each environment's supported updater for its Tailscale client; desktop apps and OS packages have different update owners. Review security updates promptly.
- Recheck device approval, access controls, key expiry, and sleeping/reboot behavior before travel. Tailscale cannot wake a powered-off computer or unlock FileVault/LUKS before the OS starts.
- Avoid reauthentication or changes to DNS, SSH policy, or Tailscale service state through your only remote connection. Keep a local or other independent recovery path.
- If a name fails, check Tailscale status, device approval, client DNS settings, and expiry before editing DNS files. On macOS, `nslookup` and `host` can bypass the system resolver; test with `ssh` or `ping` too.
- Remove retired devices from the admin console. Do not put reusable auth keys, Tailscale state files, SSH keys, machine names, or account identifiers in this repo.

Official references: [security best practices](https://tailscale.com/docs/reference/best-practices/security), [grants](https://tailscale.com/docs/features/access-control/grants), [Tailscale SSH](https://tailscale.com/docs/features/tailscale-ssh), [MagicDNS](https://tailscale.com/docs/features/magicdns), [macOS variants](https://tailscale.com/docs/concepts/macos-variants), and [key expiry](https://tailscale.com/docs/features/access-control/key-expiry).
