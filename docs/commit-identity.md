# Commit identity

One contract for every Groundwork environment: commits carry no agent
attribution and no alternate-account identity. Core owns the contract and a
reference checker, [`commit-guard/commit-identity-guard.sh`](../commit-guard/commit-identity-guard.sh).
Each environment repo installs the hooks (see the core boundary below).

## Rules

1. Reject any `Co-authored-by:` line in a commit message, in any letter case.
2. Reject a commit whose author or committer matches the local denylist.
3. Allow an optional `Agent-Session: <id>` trailer for audit.
4. Apply the same rules to every commit in a pushed range (`pre-push`), so a
   commit made with hooks off, or by a tool that bypassed them, is caught.

Not rules: the personal email address is not rejected, and a global noreply
`user.email` is not forced.

## Denylist

A plain text file outside every repository, never committed:

- default path `~/.config/groundwork/commit-denylist` (honors `XDG_CONFIG_HOME`);
- override with `GROUNDWORK_COMMIT_DENYLIST`;
- one case-insensitive substring per line, matched against `Name <email>` of the
  author and of the committer; blank lines and `#` lines are ignored;
- a missing file turns the identity rule off, and `doctor` says so.

The repo holds only the format ([`commit-denylist.example`](../commit-guard/commit-denylist.example)).
Alternate account names and organization names stay in the local file.

## Hooks

`commit-identity-guard.sh commit-msg "$1"` as the `commit-msg` hook; also checks
the identity git would record. `commit-identity-guard.sh pre-push "$@"` as the
`pre-push` hook. `commit-identity-guard.sh doctor` verifies the settings below
where they can be read.

For every pushed ref, `pre-push` checks the commits that no remote-tracking ref
already reaches: the local tip, minus the remote's old tip when it is known
locally, minus every `refs/remotes/*` ref (`git rev-list <local> ^<old> --not
--remotes`). The same rule covers a new branch, an update, and a force-push.
Commits that are already published are not checked again. That matters when a
PR branch merges `main`: GitHub squash merges can add a `Co-authored-by:`
trailer to commits on `main`, and the guard must not block a branch for
carrying them. Deleting a ref checks nothing.

The check fails closed. Missing remote-tracking refs (never fetched, deleted,
or a push straight to a URL in a clone with no remotes) mean more commits are
checked, not fewer. A commit that is on the remote but not fetched yet is
checked as well. That is stricter than needed and accepted: run `git fetch`
and push again. If git cannot compute the list, the push is refused.

## Repository scope## Repository scope

Environment repos scope the hooks to the owner's own repositories with
`includeIf "hasconfig:remote.*.url:<pattern>"` entries (git 2.36 or newer),
one per line of [`owner-remote-patterns`](../commit-guard/owner-remote-patterns):

```
https://github.com/<owner>/**
git@github.com:<owner>/**
ssh://git@github.com/<owner>/**
*:<owner>/**
ssh://*/<owner>/**
```

Each owner letter is written as a case class (`[jJ]`), so either case
matches, and the `/` after the owner keeps a look-alike such as `<owner>2`
out. In these patterns `*` never matches `/`. That is why `*:<owner>/**`
covers any scp-style host alias (`git@github-personal:<owner>/repo`), and
also why none of the first four patterns covers an ssh:// URL with a port.
`ssh://*/<owner>/**` closes that gap. It covers `ssh://git@github.com:22/<owner>/...`,
`ssh://git@ssh.github.com:443/<owner>/...` and ssh:// host aliases. It accepts
any host, the same way `*:` already does. Running the guard on a non-GitHub
remote is harmless, because it only checks. It makes
`ssh://git@github.com/<owner>/**` redundant, but that line stays so an
environment that only adds the new pattern does not need to remove anything.

Accepted gaps, still unguarded: `https://` with a port or with userinfo
(`https://user@github.com/<owner>/...`), and `git+ssh://` or `ssh+git://`
schemes. Git does not write these forms itself. A remote set to one of them
does not get the hooks.

## Agent attribution settings

Turn attribution off at the source and let the hooks be the backstop.

- Claude Code, `~/.claude/settings.json` (checked against the settings
  reference on 2026-10-30): `"attribution": {"commit": "", "pr": ""}`. This
  replaces the deprecated `includeCoAuthoredBy`. A separate
  `attribution.sessionUrl` key controls the claude.ai session link on cloud and
  Remote Control commits. Reports exist of trailers surviving empty values, so
  the hooks matter.
- Cursor: turn commit and PR attribution off in its settings. This is a UI
  setting; `doctor` cannot read it.
- Codex: uses the configured git identity. Confirm `git config user.name` and
  `user.email` are set; `doctor` checks that.

## Core boundary

Core is documentation and data, not a machine installer. The checker is a
single read-only script shipped as a reference for environment repos to link or
vendor from the pin, which is what the issue asks for (one place, no duplicated
logic). Setting `core.hooksPath`, writing `~/.claude/settings.json`, and creating
the denylist belong to each environment repo.
