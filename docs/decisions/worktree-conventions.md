# Decision: worktrees for agent lanes

Status: proposed
Date: 2026-10-29
Issue: [groundwork-core#13](https://github.com/jasondockery/groundwork-core/issues/13)

A worktree is a second working directory that shares one repository's commits, branches, and tags. Use one when two writers would otherwise edit the same checkout. This page is the shared convention. Environment repos link it. They do not copy it, and they do not install a worktree helper from it.

Read on 2026-10-29 against the [git-worktree manual](https://git-scm.com/docs/git-worktree), [Cursor worktrees](https://cursor.com/docs/configuration/worktrees), the [Cursor CLI parameters](https://cursor.com/docs/cli/reference/parameters), [Claude Code worktrees](https://code.claude.com/docs/en/worktrees), [Codex worktrees](https://developers.openai.com/codex/app/worktrees), the [Codex environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables), [Herdr configuration](https://herdr.dev/docs/configuration/) and [Herdr CLI](https://herdr.dev/docs/cli-reference/), and T3 Code's [project settings](https://github.com/pingdotgg/t3code/blob/main/docs/user/project-settings.md) and [thread sidebar](https://github.com/pingdotgg/t3code/blob/main/docs/user/thread-sidebar.md). The local rules already in [reviewable agent workspaces](../../skills/reviewable-agent-workspaces/SKILL.md) and [concurrent agent runtimes](../../skills/concurrent-agent-runtimes/SKILL.md) stay in those skills.

## Decision

Manual lanes, and any lane a person expects to find after a reboot, live at `~/worktrees/<repo>/<slug>`. `<repo>` is the repository directory name. `<slug>` is the branch name. That is the layout in use today, and it matches the manual path in the workspace skill (`~/worktrees/<repository>/<lane>`).

Tool-managed worktrees stay in the directory that tool already uses. Groundwork does not move them into `~/worktrees`, and it does not point a tool's cleaner at `~/worktrees`.

| Tool | Where a new worktree goes | Branch |
|---|---|---|
| Cursor CLI `--worktree` | `~/.cursor/worktrees/<repository>/<name>` | a generated name when you omit one |
| Claude Code `--worktree` | `.claude/worktrees/<name>` inside the repository | `worktree-<name>` |
| Codex | `$CODEX_HOME/worktrees` (`~/.codex/worktrees` when `CODEX_HOME` is unset) | detached HEAD until you create a branch |
| Herdr | `~/.herdr/worktrees/<repo>/<branch-slug>` | the branch you name, created from `--base` or `HEAD` when it is new |
| T3 Code | the `worktrees` folder of the T3 home directory (`~/.t3/worktrees`, from the same data directory whose scratch folder is `~/.t3/scratch`) | prefix `t3/` unless a setting changes it |

Cursor's `.cursor/worktrees.json` sets up a new worktree. It does not choose the directory. Codex can change its root in Settings, then Worktrees. Herdr can change `[worktrees].directory`. T3 Code can set Settings, then Worktrees, then Worktree location. Leave those at the tool default so each cleaner stays on the worktrees that tool created.

## Create a manual lane

State the base every time. Git otherwise starts from whatever the current checkout has.

```bash
git fetch origin
git worktree add -b <slug> ~/worktrees/<repo>/<slug> origin/main
```

Use that repository's default branch when it is not `main`. The slug is lowercase words separated by hyphens, and it names the change. The branch name and the directory name are the same slug. One branch is checked out in one worktree. Git refuses a second checkout of that branch, and that refusal stands.

One writing agent owns the worktree. Other agents may read a committed revision. A concurrent review uses a detached worktree at that revision: `git worktree add --detach ~/worktrees/<repo>/<slug>-review <sha>`.

A fresh worktree has tracked files only. Ignored files such as `.env` stay in the checkout that already has them. Copy them with that tool's own mechanism: Cursor's `ROOT_WORKTREE_PATH` in `.cursor/worktrees.json`, or a `.worktreeinclude` file for Claude Code and for Codex-managed worktrees. Cursor's worktree page says not to symlink a dependency directory into the worktree, because that can break the main checkout. A worktree that starts a server, database, or browser binds its own port and its own data directory. The concurrent-runtimes skill owns that isolation.

Linked worktrees share one Git config. A `git config` edit is visible from every worktree. Use `git config --worktree` only after `extensions.worktreeConfig` is on, and only for a setting that is supposed to differ.

Do not put a linked worktree inside its main checkout. Git will show it as untracked files. Do not put a manual lane under `~/.cursor/worktrees`. Cursor 3.5 cleanup keeps a machine-wide maximum (default 25, setting `cursor.worktreeMaxCount`) and can delete worktrees it finds under that root, including ones `git worktree add` created there.

## After the change merges

Remove the worktree only after its commits are on the remote default branch, or the person has abandoned the lane and the unique commits are already pushed.

1. `git worktree list` shows the path, the commit, and the branch.
2. `git status` in that worktree is clean. `git worktree remove ~/worktrees/<repo>/<slug>` then deletes the directory. The manual says `remove` refuses a worktree with modified or untracked files, and refuses the main worktree. When it refuses, read the diff. `--force` is a separate decision after that reading. A locked worktree needs `--force` twice. Leave it locked while an agent session holds the lock. Claude Code takes `git worktree lock` for the session and releases it when the session ends.
3. `git branch -d <slug>` deletes the branch after Git agrees it is merged. Stop when `-d` refuses.
4. `git worktree prune` clears administrative files after a directory was deleted without `remove`. Prefer `remove` the next time.

Herdr's `herdr worktree remove` runs `git worktree remove` and leaves the branch in place. Closing a Herdr group also leaves the checkout and the branch. Delete the merged branch with `git branch -d` afterwards.

Each tool may delete its own managed worktrees. Cursor's cap is above. Codex keeps the most recent 15 Codex-managed worktrees unless a pinned chat or a chat in progress holds one, and it stores a snapshot before deletion. Claude Code removes a clean unnamed worktree on exit and asks before removing a named one or a dirty one. T3 Code cleanup is off until someone turns it on, and it applies to T3-managed worktrees. A merge rule there requires a merged pull request whose commits are on the remote default branch. Those cleaners do not apply to `~/worktrees/<repo>/<slug>`.

## What the family repos do today

Checked on 2026-10-29:

- This repo's workspace skill already names `~/worktrees/<repository>/<lane>` for manual lanes. There is no `.cursor/worktrees.json` and no `.worktreeinclude`.
- The imported page `docs/worktrees.html` still teaches `~/code/.worktrees/<slug>/<lane>`. That file is historical curriculum from the original Groundwork site. This decision is the operational convention.
- `groundwork-mac` has the same curriculum page. Its `repos.conf` template sets `include_worktrees = true` and one discovery root, the code directory, with `max_depth = 4`. A lane at `~/worktrees/<repo>/<slug>` is visible to `groundwork-repos` when `~/worktrees` is a discovery root. The Herdr config template has no `[worktrees]` table, so Herdr's published default directory applies. No script in that repo creates `~/worktrees`.
- `groundwork-linux`, `groundwork-windows`, and `groundwork-omarchy-mac-arm64` have no worktree path, no Herdr worktree setting, and no `.cursor/worktrees.json`. Their checked-in skills repeat the same workspace rule.

## Follow-ups, each its own issue

These stay unfiled until the owner opens them.

1. In `groundwork-mac`, add `~/worktrees` as a `groundwork-repos` root so supervision sees manual lanes. The code-directory root does not include that path.
2. Add `.worktreeinclude` or `.cursor/worktrees.json` in a repository only when that repository has ignored files a new worktree must copy. This docs repo has none.
3. Leave tool directories at the tool default. A later issue that relocates Cursor, Claude Code, Codex, Herdr, or T3 Code needs a reason that the tool's own setting cannot cover.
