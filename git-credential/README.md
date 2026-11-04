# GitHub over HTTPS, one gh account per owner

Reference scripts that make HTTPS the default GitHub transport for people and
agents, and pick the gh account from the repository owner. Environment repos
call them from the `core` pin. This directory holds no account names; the map
is passed in by the installer and lives in the user's git config.

- `owner-credential-helper.sh`: a git credential helper. On `get` for
  `https://github.com/<owner>/...` it reads the global `ghaccount.<owner>` and
  answers with `gh auth token -u <account>`. `store` and `erase` do nothing.
  `gh-path` prints the gh it would run.
- `setup-github-https.sh`: idempotent setup. Installers call it.
- `check-github-https.sh`: read-only doctor check with `ok:`, `note:`, `FAIL:`
  and `fix:` lines. Exits 1 on any failure.
- `github-https-lib.sh`: shared by the two scripts above; not run directly.

## Why HTTPS, and why an owner helper

On 2026-11-04 SSH to GitHub failed on all three machines while HTTPS through
gh kept working, so HTTPS is the agent default and SSH remotes are rewritten to
it. `gh auth git-credential` only serves the active gh account; a username in
the remote URL does not choose the account, and GitHub's redirect drops it
anyway. The owner helper routes by who owns the repository, wherever the clone
lives.

## What the helper answers

| Request | Result |
|---|---|
| github.com (any case, with or without `:443`), owner mapped, gh has a token for the account | `username=<account>`, `password=<token>` |
| github.com, owner mapped, no token (logged out, gh missing) | `quit=1`: git stops with "credential helper ... told us to quit". One stderr line names the owner and account and the fix, `gh auth login -h github.com` |
| github.com, owner not mapped, or not mappable | nothing; gh's helper answers with the active account |
| another host, or no `path=` | nothing |

A mapped owner fails closed on purpose: falling through would push or fetch
as whichever account happens to be active. The token goes only to the
protocol's stdout; nothing is logged.

The helper reads `ghaccount.*` and `groundwork.ghPath` from the global config
and the files it includes (`git config --global --includes`), never from a
repository's own config, so a cloned repository cannot choose an account.

## What setup writes

```sh
core/git-credential/setup-github-https.sh \
  --map jasondockery=jasondockery --map example-org=work-account \
  --ssh-alias github-personal
```

It first copies the helper to a stable path,
`${XDG_DATA_HOME:-~/.local/share}/groundwork/git-credential/owner-credential-helper.sh`
(written to a temp file and moved into place, mode 0755, skipped when the
bytes already match), so the config does not point into a checkout that can
move. `--helper PATH` uses an existing helper instead. Then it edits one file:
the one `git config --global` writes (`GIT_CONFIG_GLOBAL`, else `~/.gitconfig`,
else `$XDG_CONFIG_HOME/git/config` when only that exists), or the absolute path
given with `--file` (a relative `--file` is rejected with exit 64). Every edit
goes to a temp copy in the same directory with the same mode, which then
replaces the file in one rename, so an interrupted run leaves the old file
whole. A symlinked target is refused; pass the real file with `--file`. The
file gets:

```ini
[credential "https://github.com"]
	useHttpPath = true
	helper =
	helper = /home/me/.local/share/groundwork/git-credential/owner-credential-helper.sh
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
`https://github.com` in the target file (for example the one
`gh auth setup-git` writes) is replaced. It never reads or edits ssh config;
SSH keys and host aliases keep working for anyone who calls them directly.

Afterwards setup checks what git and the helper really see, across every file
and include, and exits 1 instead of printing "already configured" when:

- the `--file` is not included from the global config;
- a mapped owner has another value elsewhere: the helper reads
  `git config --global --includes`, where the last value wins, so a later
  `[ghaccount]` in `~/.gitconfig` would override the `--file` one;
- a helper it does not own still runs for github.com, for example a later
  `[credential] helper = osxkeychain`, which would be sent every token git
  approves, or a later github.com section, such as a leftover from
  `gh auth setup-git`, that resets the chain.

Each problem names the file and key and the `git config --file ... --unset-all`
command that removes it. When that file is generated (a chezmoi template),
drop the block from the template instead, or the next apply puts it back.

The helper order matters. The empty `helper =` resets the list, so a helper
from a wider scope cannot answer first. On macOS that is the `osxkeychain`
helper Apple's and Homebrew's git configure system-wide; without the reset it
can serve a cached token for the wrong account before the owner helper runs.

gh is found in this order: `GROUNDWORK_GH`, then the global
`groundwork.ghPath`, then the mise shim `~/.local/share/mise/shims/gh`, then
`gh` on `PATH`. `gh auth setup-git` under mise writes the versioned install
path, which breaks on the next gh upgrade, so setup writes the shim and the
doctor flags a versioned path. The shim picks the gh version from the current
directory's mise config, so a repository that pins another gh gets that one.
When that matters, pin an absolute path with `GROUNDWORK_GH` or
`git config --global groundwork.ghPath /path/to/gh`.

### chezmoi and other managed gitconfigs

When `~/.gitconfig` is generated (groundwork-mac renders it from
`home/dot_gitconfig.tmpl`), writing into it gets reverted on the next apply.
Use a separate file instead, include it from the template, and drop the
template's own github.com helper chain:

```ini
# in the managed ~/.gitconfig
[include]
	path = ~/.config/groundwork/github.gitconfig
```

```sh
core/git-credential/setup-github-https.sh --file ~/.config/groundwork/github.gitconfig --map ...
core/git-credential/check-github-https.sh --file ~/.config/groundwork/github.gitconfig --root ~/code
```

## Map keys

`ghaccount.<owner>` is a git config key, so the owner must start with a letter
and hold only letters, digits and hyphens; git compares it without regard to
case, as GitHub does. Setup rejects other owners. An owner that starts with a
digit cannot be mapped and falls through to gh's active account; the doctor
notes it.

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
core/git-credential/check-github-https.sh [--file PATH] [--ssh-alias HOST]... \
  --root ~/code ~/worktrees/repo/lane
```

It checks:

- `useHttpPath` for github.com;
- the chain in the target file (empty reset, helper, gh), that the helper it
  names exists and is executable, and that its gh path exists and is not a
  versioned mise path;
- that a `--file` is included from the global config;
- the chain git really runs for github.com, outside any repository and again
  inside each repository checked, so `includeIf` files and local config count.
  A subsection matches whatever the case of its scheme and host, with or
  without `:443`, and one with a wildcard is assumed to match. Any helper after
  gh's, ahead of the owner helper, or a later reset is a failure;
- the owner map as the helper sees it (`git config --global --includes`): an
  owner with more than one value, or a value that differs from the target
  file's, is a failure;
- gh's `git_protocol`, and that every mapped account appears in
  `gh auth status` (only account names are read from it; its text is never
  printed);
- that each `--ssh-alias` is rewritten to `https://github.com/`;
- for the repositories passed in, and those up to three levels under each
  `--root`: SSH GitHub remotes (host compared without case) no `insteadOf` rewrites, a `pushInsteadOf` that
  sends pushes back to SSH, and, when more than one gh account is logged in,
  owners with no mapping.

Each failure is followed by the command that fixes it.

## Calling it from a platform repo

The platform installer runs `setup-github-https.sh` with its owner map and SSH
aliases after gh is installed and logged in, and runs `check-github-https.sh`
with the same `--file` and `--ssh-alias` from its own doctor. Account names stay
in the platform repo or the machine, not here. Removing the setup means
unsetting the keys above (`git config --global --unset-all
credential.https://github.com.helper`, the `url.https://github.com/.insteadOf`
values, and the `ghaccount` section), or deleting the `--file` and its include,
and removing the installed helper.
