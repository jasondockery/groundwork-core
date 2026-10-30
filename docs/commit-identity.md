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
`pre-push` hook. For a new branch the checked range is every commit not already
on that remote. `commit-identity-guard.sh doctor` verifies the settings below
where they can be read.

Pushing straight to a URL, such as `git push https://example.com/repo.git main`,
gives the hook no remote name. Git has no remote-tracking refs for a bare URL,
so a new ref there checks all reachable history, and an old commit that matches
the denylist or carries a co-author trailer blocks every such push. Push to a
named remote instead (`git remote add origin <url>`, then `git push origin`),
which checks only commits not already on that remote.

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
