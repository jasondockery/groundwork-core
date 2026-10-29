# History purge

This page is how a person removes text from the history of a Groundwork repository. Use it when a credential has to be revoked and the old value must also leave the history, or when a private reference was committed and has to go. The rewrite changes commit ids from the first changed commit onward. It is rare. The person decides to publish it. An agent can prepare a fresh clone and the checks, then stops for that decision.

Git's own manual tells you not to use `git filter-branch` for this. It can mangle a rewrite in ways that are hard to see, and it is slow. The tool here is `git filter-repo`. Read on 2026-10-29 against the [git-filter-branch manual](https://git-scm.com/docs/git-filter-branch), [git-filter-repo 2.47.0](https://github.com/newren/git-filter-repo/blob/v2.47.0/git-filter-repo), its [install notes](https://github.com/newren/git-filter-repo/blob/v2.47.0/INSTALL.md), [GitHub's removal guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository), and the [Repology package list](https://repology.org/project/git-filter-repo/information).

Environment repos link this page. They do not copy it.

## Opt-in tool

`git-filter-repo` is not a Groundwork default. This repository does not install it. An environment repo may declare it as an optional per-user tool. An agent checks for it and asks the owner before any install. The agent does not install it, and does not use administrator permission to install it for this procedure.

The check is `git filter-repo --version`. You need 2.47 or newer, because `--sensitive-data-removal` arrived in 2.47. Repology, read on 2026-10-29, still lists older distro builds, including 2.38 and 2.34, so a package name is not a version.

The per-user command in the 2.47.0 install notes is `pipx install git-filter-repo`. Homebrew, Arch, and Ubuntu also package the name `git-filter-repo`. Use the installer that the environment already uses, then run the version check again. A build older than 2.47 does not satisfy this page.

Try the check on a terminal: run `git filter-repo --version`. If the command is missing, or the version is below 2.47, stop and ask the owner. Do not practice a rewrite on a repository you use.

## Rotate first

If the text is a password, token, or key, revoke or rotate it before any rewrite. After rotation, the old value cannot be used. GitHub does not purge history when rotation is enough. A rewrite does not expire a live credential.

A rewrite also leaves GitHub issue text, pull request text, review comments, release descriptions, and the repository description in place. It does not clean a fork someone else controls, and it does not clean another clone until that clone is replaced or walked through the steps below.

## What a rewrite changes

Run `git filter-repo` only in a fresh clone made for this purge. It changes commit ids from the first changed commit onward. It drops signatures on the commits and tags it rewrites. It removes the `origin` remote in that clone so a later push does not silently aim at the old history. It does not edit the checkout you use every day, and it does not delete that checkout.

`--replace-text` edits a blob only when the first 8192 bytes contain no NUL. That is the binary skip in 2.47.0 (`_tweak_blob`). A file without that NUL is edited, including a file that merely looks like text and is not the one you meant. A `regex:` or `glob:` line can change source that is not the secret. Use one literal line per secret, the exact bytes, and no `regex:` or `glob:` prefix. A line with no `==>` is replaced by `***REMOVED***`.

`--replace-text` does not edit commit or tag messages. Add `--replace-message` with the same literal file when the text can appear in a message.

## Before anyone pushes

1. Tell every person and every agent with a clone to stop pushing. A push of the old history after the rewrite puts the text back.
2. Write down the branch protection or ruleset that blocks a force-push. You will lift that block only for the publish step, then put the same settings back.
3. Make a fresh clone. Do not rewrite the daily checkout. `git filter-repo --sensitive-data-removal` fetches refs beyond branches and tags, including pull-request refs, and that fetch can drop unpushed commits. Do not pass `--no-fetch`.
4. Fetch `+refs/pull/*:refs/pull/*` into this fresh clone before you scan or count. A mirror clone (`git clone --mirror`) must run that fetch itself. git-filter-repo 2.47.0 skips `git fetch origin +refs/*:refs/*` when `remote.origin.mirror` is true, so `--sensitive-data-removal` does not bring `refs/pull/*` into a mirror. GitHub does not advertise those refs to the clone. On a clone that is not a mirror, also fetch `origin +refs/*:refs/*` before you record the commit count. That is the same fetch the tool runs inside the rewrite. Before you trust the scan, `git show-ref` should list the `refs/pull/` tips you expect.
5. Record `git rev-list --all --count` after that fetch and before the rewrite. The verify step compares against this number. A count taken before the pull-ref fetch is the wrong baseline.
6. Put the exact text in one file outside every repository, mode `0600`. One secret per line when there are several. Do not put that text in a shell command, a commit message, an issue, a pull request, or a support request. The rest of this page calls that file the needle file.

## Find it without printing it

Search these places. The commands print a count or a ref name, not the text.

- Every branch tip and every tag tip: `git for-each-ref refs/heads refs/tags`.
- Every object in the database, including objects no ref points at: `git cat-file --batch-all-objects`, fed to the counter below. The counter reads blobs, commits, tags, and trees. A filename is stored in a tree, so a secret that appears only as a path is a hit. Run this before the rewrite. A count of zero means the needle file does not match those stored bytes. Fix the file or stop. Do not rewrite on a guess.
- Reachable objects only, after the rewrite: the same counter with `reachable`. This is the gate. The all-object scan still sees the pre-rewrite objects until you prune, so it is the wrong gate after the rewrite.
- GitHub text the rewrite will not change: issues, pull requests, review comments, release descriptions, and the repository description. The owner runs that search. Record hit or miss for each surface. Do not paste the text into the record.

The counter reads the needle file and prints a count only. Run it from the fresh clone. `all` is the discovery scan. `reachable` is the gate.

```python
#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

mode, needle_path = sys.argv[1], Path(sys.argv[2])
needles = [line for line in needle_path.read_bytes().splitlines() if line]
if mode not in {"all", "reachable"} or not needles:
    sys.exit("usage: count.py all|reachable NEEDLE_FILE")

def objects():
    if mode == "all":
        listing = subprocess.run(
            ["git", "cat-file", "--batch-check", "--batch-all-objects"],
            check=True, capture_output=True,
        ).stdout.splitlines()
        for line in listing:
            oid, kind, size = line.split()
            if kind in {b"blob", b"commit", b"tag", b"tree"} and int(size) >= min(len(item) for item in needles):
                yield oid
        return
    commits = subprocess.run(
        ["git", "rev-list", "--all"],
        check=True, capture_output=True, text=True,
    ).stdout.split()
    named = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    blobs = [line.split()[0] for line in named if len(line.split()) >= 1]
    tags = subprocess.run(
        ["git", "for-each-ref", "--format=%(objectname)", "refs/tags"],
        check=True, capture_output=True, text=True,
    ).stdout.split()
    for oid in dict.fromkeys([*commits, *blobs, *tags]):
        yield oid.encode()

wanted = list(objects())
if not wanted:
    print(0)
    raise SystemExit
raw = subprocess.run(
    ["git", "cat-file", "--batch"],
    input=b"\n".join(wanted) + b"\n",
    check=True, capture_output=True,
).stdout
hits = 0
idx = 0
while idx < len(raw):
    nl = raw.find(b"\n", idx)
    header = raw[idx:nl].split()
    size = int(header[2])
    start = nl + 1
    body = raw[start:start + size]
    if any(item in body for item in needles):
        hits += 1
    idx = start + size + 1
print(hits)
```

The counter needs Python 3.9 or newer. Its stdout is a single integer. Its stderr stays empty on success. If `git cat-file` prints a missing object, the command fails and you stop.

## Rewrite

From the fresh clone:

```bash
git filter-repo --sensitive-data-removal --replace-text /path/to/needle-file
```

Add `--replace-message /path/to/needle-file` when a commit or tag message can contain the text. Keep the path outside the clone. If the tool prints that LFS objects were orphaned, keep the file it names. The support request needs that file.

## Verify before any push

Stop when a check fails. Delete the fresh clone if you want to start over. The daily checkout is still the old history, which is what you have until you publish.

1. Reachable hits are zero. Run the counter in `reachable` mode. It must print `0`.
2. The commit count matches the number recorded after the pull-ref fetch and before the rewrite. Compare `git rev-list --all --count` to that number. A count taken before the pull-ref fetch is the wrong baseline. On a clone that is not a mirror, `--sensitive-data-removal` fetches `+refs/*:refs/*` inside the rewrite, so that earlier count rises when pull-request commits are added even though the rewrite only replaced text. A different count from the recorded baseline means a commit was dropped or a ref was missing. Do not push.
3. Each tip tree differs only in the replaced lines. `.git/filter-repo/commit-map` maps old commits to new ones. Pair each old tip with its new tip and run `git diff-tree -r` on that pair. The old objects are still in this clone until you prune, so the diff works here. Read it on this machine. It shows the removed text. Do not copy it into an issue, a commit, or a ticket. Any other change is a stop.
4. Count moved pull-request refs with `grep -c '^refs/pull/.*/head$' .git/filter-repo/changed-refs`. Keep the first changed commit SHAs from the tool's `NOTE: First Changed Commit(s)` line. Later notes use those SHAs and that count. They do not use the text.

## Publish

At the freeze, before the rewrite, record every remote branch SHA and every remote tag SHA you will replace:

```bash
git ls-remote origin 'refs/heads/*' 'refs/tags/*'
```

Keep that list outside the clone. It is the freeze record.

Re-add `origin` only on this rewritten clone, and only for this push. Run `git ls-remote` again for the same refs. Every SHA must still match the freeze record. If one does not, stop. Someone pushed. Do not overwrite that work.

A fetch followed by `git push --force-with-lease origin main` does not check the freeze record. The fetch moves the remote-tracking ref to the new tip, and the unqualified lease then accepts that tip. That push can replace a commit that arrived after the freeze. This page does not use that form.

Push each rewritten branch with the SHA from the freeze record:

```bash
git push --force-with-lease=refs/heads/main:<recorded-sha> origin refs/heads/main
```

Push each rewritten tag the same way. `git push --force-with-lease origin tag v1.2.3` fails with stale info whether or not the tag moved, because a tag has no remote-tracking lease, and the tag stays on the old history. Use the recorded SHA:

```bash
git push --force-with-lease=refs/tags/v1.2.3:<recorded-sha> origin refs/tags/v1.2.3
```

Repeat for every rewritten ref, with that ref's name and its recorded SHA. The lease fails when the remote ref is not the recorded SHA. That failure is a stop. Do not switch that ref to `--force` unless the owner has seen which ref moved and approves that one ref.

GitHub's guide shows `git push --force --mirror origin`. This page does not use that form. A mirror push deletes a remote ref that the local clone does not have, including a branch created during the freeze, and a bare `--force` does not check that the remote is still the ref you rewrote.

Pushes of `refs/pull/*` are rejected. That rejection is expected, because GitHub marks those refs read-only. Any other rejection is branch protection. Lift only the protection you wrote down, push that ref again with `--force-with-lease=<ref>:<recorded-sha>`, and put the same protection back before you do anything else. When the only remaining failures are `refs/pull/*`, the protection is already restored.

A moved tag changes the commit a release points at. Open each release and confirm the tag still names the release you expect. If the GitHub-text search was a hit on a release description, edit that description. The rewrite does not.

## GitHub Support and other clones

Ask GitHub Support to drop the cached views and the pull-request refs. Include the owner and repository name, the pull-request count from `changed-refs`, and the first changed commit SHAs. If LFS objects were orphaned, say so and attach the file the tool named. Never name the purged text in an issue, a commit, or the support request. Support does not purge ordinary data, and it does not purge a credential that rotation already made useless.

Other clones must not `git pull` and then `git push`. That push puts the old history back. The usual fix is to delete the clone and clone again. A person who still has unpushed commits follows the colleague steps in the git-filter-repo manual: delete local tags, run `git fetch --prune --tags`, rebase onto the new history, then `git reflog expire --expire=now --all` and `git gc --prune=now`. That expire drops every reflog and every stash. Before that clone pushes, `git cat-file -t` on each first-changed SHA must fail. Do not run `git filter-repo` a second time in those clones. A second rewrite can mint different commit ids.

A fork is a separate repository. Ask that owner to delete the fork or to follow this page. GitHub cannot hand you their contact details.

## After

Delete the needle file when the owner no longer needs it for a missed hit. Do not commit it. Do not push a pre-rewrite remote, bundle, or backup into the repository.
