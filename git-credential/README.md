# GitHub over HTTPS, one gh account per owner

Reference scripts that route GitHub HTTPS credentials to a gh account by
repository owner. Environment repos call them from the `core` pin. This
directory holds no account names; the installer passes the map in, and it
lives in a Groundwork-owned git config file.

- `owner-credential-helper.sh`: the git credential helper.
- `setup-github-https.sh`: idempotent setup. Installers call it.
- `check-github-https.sh`: read-only doctor with `ok:`, `FAIL:` and `fix:`
  lines; exits 1 on any failure.
- `github-https-lib.sh`: shared by setup and the doctor; not run directly.

## Why

On 2026-11-04 SSH to GitHub failed on all three machines while HTTPS through
gh kept working, so HTTPS is the agent default. Some machines keep more than
one gh account logged in on purpose, and `gh auth git-credential` only serves
the active one; a username in the remote URL does not pick the account, and
GitHub's redirect drops it anyway. The owner helper picks the account from who
owns the repository, wherever the clone lives.

## What the helper answers

| Request | Result |
|---|---|
| github.com (any case, with or without `:443`), owner mapped, gh has a token for the account | `username=<account>`, `password=<token>` |
| github.com, owner mapped, no token (logged out, gh missing), or git cannot read the config | `quit=1`: git stops with "credential helper ... told us to quit", and one stderr line names the owner, the account and the fix |
| github.com, owner not mapped, or not mappable | nothing; gh's helper answers with the active account |
| another host, or an empty or missing `path=` | nothing |

A mapped owner fails closed on purpose: falling through would fetch or push as
whichever account happens to be active. The token goes only to the protocol's
stdout. `store` and `erase` do nothing.

The helper reads `ghaccount.*` and `groundwork.ghPath` with
`git config --global --includes`, run from outside any repository, so neither a
repository's own config nor an `includeIf` for its directory can choose an
account.

## What setup writes

```sh
core/git-credential/setup-github-https.sh \
  --map jasondockery=jasondockery --map example-org=work-account
```

Setup writes exactly two things:

1. **Its own file**, `${XDG_CONFIG_HOME:-~/.config}/groundwork/github-https.gitconfig`,
   regenerated from the arguments alone (so the installer passes the whole map
   every time):

   ```ini
   # Written by groundwork-core git-credential/setup-github-https.sh; rerun it to change.
   [credential "https://github.com"]
   	useHttpPath = true
   	helper =
   	helper = /home/me/.local/share/groundwork/git-credential/owner-credential-helper.sh
   	helper = !/home/me/.local/share/mise/shims/gh auth git-credential
   [ghaccount]
   	jasondockery = jasondockery
   	example-org = work-account
   ```

   The content goes to `<file>.lock`, created exclusively, and is renamed over
   the file only when the bytes differ. Ctrl+C or SIGTERM stops before the
   rename, so the old file stays whole. A second setup that finds the lock
   stops and prints the `rm -f` for a stale one.
2. **One include line**, `include.path = <that file>`, added with
   `git config --global --add` (git's own locked writer) only when the global
   config does not already include it. When the global file is a symlink or
   managed by chezmoi, setup does not touch it: it prints the `[include]` lines
   to add to the source and exits 1.

It also installs the helper to
`${XDG_DATA_HOME:-~/.local/share}/groundwork/git-credential/owner-credential-helper.sh`
(mode 0755, skipped when the bytes match; `--helper PATH` uses another one) and
runs `gh config set git_protocol https`. A second run with the same arguments
writes nothing and says so. Setup does not verify; run the doctor.

The empty `helper =` resets the helper list, so a helper from a wider scope
cannot answer first. On macOS that is the `osxkeychain` helper Apple's and
Homebrew's git configure system-wide; without the reset it could serve a cached
token for the wrong account.

gh is found in this order: `GROUNDWORK_GH`, the global `groundwork.ghPath`, the
mise shim `~/.local/share/mise/shims/gh`, then `gh` on `PATH`. The shim survives
gh upgrades (`gh auth setup-git` under mise writes the versioned path), but it
picks the gh version from the current directory's mise config. To pin one,
set `GROUNDWORK_GH` or `git config --global groundwork.ghPath /path/to/gh`.

### Managed gitconfigs

When `~/.gitconfig` is generated (groundwork-mac renders it from
`home/dot_gitconfig.tmpl`) or is a symlink, add the include to the source and
drop the template's own github.com helper chain, which would otherwise override
this one:

```ini
[include]
	path = ~/.config/groundwork/github-https.gitconfig
```

Then rerun setup; it finds the include and has nothing more to do.

## Map keys

`ghaccount.<owner>` is a git config key, so the owner must start with a letter
and hold only letters, digits and hyphens; git compares it without regard to
case, as GitHub does. Setup rejects other owners, and an owner that starts with
a digit falls through to gh's active account.

## Rotate or replace a token

gh holds the token, so rotating it in gh is enough. `gh auth refresh` acts on
the active account and has no `-u` flag (gh 2.103), so either sign in again as
that account (`gh auth login -h github.com --git-protocol https`), or
`gh auth switch -h github.com -u <account>`, `gh auth refresh -h github.com`,
and switch back. To add an account, log in, add `--map <owner>=<account>` to
the installer's call, and rerun it.

## Doctor

```sh
core/git-credential/check-github-https.sh --root ~/code ~/worktrees/repo/lane
```

The doctor asks git instead of modelling git's config rules. It checks:

- the owned file is included from the global config;
- the helper the owned file names exists and is executable;
- every mapped account is logged in to gh (only account names are read from
  `gh auth status`; its text is never printed);
- routing: for each mapped owner, `git credential fill` for
  `https://github.com/<owner>/groundwork-doctor-probe.git` returns the mapped
  account, run outside any repository and again inside each repository given
  or found up to three levels under each `--root`, so local config and
  `includeIf` count. Only the returned username is kept and printed; the
  password is dropped inside the pipe. `fill` stores nothing, and the doctor
  never calls `approve` or `reject`. It does run the configured helpers, which
  may have side effects such as a keychain prompt; the reset in the chain keeps
  earlier helpers out.

Anything that overrides the owned file, such as a later `useHttpPath = false`
or a leftover chain from `gh auth setup-git`, shows up as the wrong username,
with a fix line that lists the credential and map config and where each value
comes from.

## Calling it from a platform repo

The installer runs `setup-github-https.sh` with its owner map after gh is
installed and logged in, and its doctor runs `check-github-https.sh --root
<code dirs>`. Account names stay in the platform repo or on the machine.
Removing the setup means deleting the owned file, its `include.path` line
(`git config --global --unset include.path <file>`), and the installed helper.

## Testing

`tests/test_git_credential.py` runs real git and these scripts with a temp
HOME and config, a fake gh, and a fake keychain helper. Credential tests never
reach the network: every proxy setting points at a closed local port, and one
assertion proves a real `git ls-remote` fails there.

## Follow-ups

Left out to keep this to routing plus the doctor:

- rewriting SSH remotes to HTTPS (`insteadOf`, SSH host aliases) and checking
  for SSH remotes and `pushInsteadOf`;
- a static check for helpers that run after gh's and would be sent tokens on
  approve, which `fill` cannot show;
- warning when a rerun drops an owner from the map;
- a configurable location for the owned file.
