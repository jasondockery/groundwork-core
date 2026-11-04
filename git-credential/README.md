# GitHub over HTTPS, one gh account per owner

Reference scripts that make HTTPS the default GitHub transport for people and
agents, and pick the gh account from the repository owner. Environment repos
call them from the `core` pin. This directory holds no account names; the map
is passed in by the installer and lives in the user's global git config.

- `owner-credential-helper.sh`: a git credential helper. On `get` for
  `https://github.com/<owner>/...` it reads `git config ghaccount.<owner>` and
  answers with `gh auth token -u <account>`. Anything else (another host, no
  `path=`, an owner with no mapping, gh failing) prints nothing, so the next
  helper answers. `store` and `erase` do nothing. `gh-path` prints the gh it
  would run.
- `setup-github-https.sh`: idempotent setup. Installers call it.
- `check-github-https.sh`: read-only doctor check with `ok:`, `FAIL:` and
  `fix:` lines. Exits 1 on any failure.

## Why HTTPS, and why an owner helper

On 2026-11-04 SSH to GitHub failed on all three machines while HTTPS through
gh kept working, so HTTPS is the agent default and SSH remotes are rewritten to
it. `gh auth git-credential` only serves the active gh account; a username in
the remote URL does not choose the account, and GitHub's redirect drops it
anyway. The owner helper routes by who owns the repository, wherever the clone
lives, and falls through to gh for every owner it does not know.

## What setup writes

```sh
core/git-credential/setup-github-https.sh \
  --map jasondockery=jasondockery --map example-org=work-account \
  --ssh-alias github-personal
```

In the global git config (`git config --global`, so `GIT_CONFIG_GLOBAL` is
honored):

```ini
[credential "https://github.com"]
	useHttpPath = true
	helper =
	helper = /path/to/core/git-credential/owner-credential-helper.sh
	helper = !/home/me/.local/share/mise/shims/gh auth git-credential
[url "https://github.com/"]
	insteadOf = git@github.com:
	insteadOf = ssh://git@github.com/
	insteadOf = git@github-personal:
	insteadOf = ssh://git@github-personal/
[ghaccount]
	jasondockery = jasondockery
	example-org = work-account
```

It also sets gh's `git_protocol` to `https`. A second run with the same
arguments changes nothing and says so. An existing helper chain for
`https://github.com` (for example the one `gh auth setup-git` writes) is
replaced, and setup reports how many entries it replaced. It never reads or
edits ssh config; SSH keys and host aliases keep working for anyone who calls
them directly. If setup is interrupted, run it again.

The helper order matters. The empty `helper =` resets the list, so a helper
from a wider scope cannot answer first. On macOS that is the `osxkeychain`
helper Apple's and Homebrew's git configure system-wide; without the reset it
can serve a cached token for the wrong account before the owner helper runs.

gh is found by a stable path, in this order: `GROUNDWORK_GH`, then
`git config groundwork.ghPath`, then the mise shim
`~/.local/share/mise/shims/gh`, then `gh` on `PATH`. `gh auth setup-git` under
mise writes the versioned install path, which breaks on the next gh upgrade;
the doctor flags that path.

## Map keys

`ghaccount.<owner>` is a git config key, so the owner must start with a letter
and hold only letters, digits and hyphens; git compares it without regard to
case, as GitHub does. Setup rejects other owners. An owner that starts with a
digit cannot be mapped and falls through to gh's active account.

## Rotate or replace a token

The helper stores nothing; gh holds the token, so rotating it in gh is enough.
`gh auth refresh` acts on the active account and has no `-u` flag (gh 2.103),
so either sign in again as that account, which replaces its stored token:

```sh
gh auth login -h github.com --git-protocol https   # choose <account>
```

or switch to it, refresh, and switch back:

```sh
gh auth switch -h github.com -u <account>
gh auth refresh -h github.com
gh auth switch -h github.com -u <previous-account>
```

To add an account, `gh auth login -h github.com --git-protocol https`, then add
`--map <owner>=<account>` to the installer's call and rerun it.

## Doctor

```sh
core/git-credential/check-github-https.sh --root ~/code ~/worktrees/repo/lane
```

It checks `useHttpPath`, the helper chain and its gh path, gh's
`git_protocol`, and that every mapped account appears in `gh auth status`. For
the repositories passed in, and those up to three levels under each `--root`,
it flags SSH GitHub remotes that no `insteadOf` rewrites and, when more than
one gh account is logged in, owners with no mapping. Each failure is followed
by the command that fixes it. Only account names are read from
`gh auth status`; its text is never printed.

Pass `--helper PATH` to both scripts when the installer copies the helper
somewhere else.

## Calling it from a platform repo

The platform installer runs `setup-github-https.sh` with its owner map and SSH
aliases after gh is installed and logged in, and runs `check-github-https.sh`
from its own doctor. Account names stay in the platform repo or the machine,
not here. Removing the setup means unsetting the keys above
(`git config --global --unset-all credential.https://github.com.helper`, the
`url.https://github.com/.insteadOf` values, and the `ghaccount` section).
