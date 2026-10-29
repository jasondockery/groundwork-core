# History purge

This page is how a person removes text from the history of a Groundwork repository. Use it when a credential has to be revoked and the old value must also leave the history, or when a private reference was committed and has to go. The rewrite changes commit ids from the first changed commit onward. It is rare. The person decides to publish it. An agent can prepare a fresh clone and the checks, then stops for that decision.

Git's own manual tells you not to use `git filter-branch` for this. It can mangle a rewrite in ways that are hard to see, and it is slow. The tool here is `git filter-repo`. Read on 2026-10-29 against the [git-filter-branch manual](https://git-scm.com/docs/git-filter-branch), [git-filter-repo 2.47.0](https://github.com/newren/git-filter-repo/blob/v2.47.0/git-filter-repo), its [install notes](https://github.com/newren/git-filter-repo/blob/v2.47.0/INSTALL.md), [GitHub's removal guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository), and the [Repology package list](https://repology.org/project/git-filter-repo/information).

Environment repos link this page. They do not copy it.

## Opt-in tool

`git-filter-repo` is not a Groundwork default. This repository does not install it. An environment repo may declare it as an optional per-user tool. An agent checks for it and asks the owner before any install. The agent does not install it, and does not use administrator permission to install it for this procedure.

The check is `git filter-repo -h`. Stop unless the help text contains `--sensitive-data-removal`. A missing command is the same stop. `--sensitive-data-removal` arrived in 2.47. Repology, read on 2026-10-29, still lists older distro builds, including 2.38 and 2.34, so a package name is not proof the flag is present. Do not compare `git filter-repo --version` to `2.47`. That command prints a hash of the script, not the release number.

The per-user command in the 2.47.0 install notes is `pipx install git-filter-repo`. Homebrew, Arch, and Ubuntu also package the name `git-filter-repo`. Use the installer that the environment already uses, then run `git filter-repo -h` again. Help text that does not contain `--sensitive-data-removal` does not satisfy this page.

Try the check on a terminal: run `git filter-repo -h`. Stop unless the help text contains `--sensitive-data-removal`. A missing command is the same stop. Do not practice a rewrite on a repository you use.

## Rotate first

If the text is a password, token, or key, revoke or rotate it before any rewrite. After rotation, the old value cannot be used. GitHub does not purge history when rotation is enough. A rewrite does not expire a live credential.

A rewrite also leaves GitHub issue text, pull request text, review comments, release descriptions, and the repository description in place. It does not clean a fork someone else controls, and it does not clean another clone until that clone is replaced or walked through the steps below.

## What a rewrite changes

Run `git filter-repo` only in a fresh clone made for this purge. It changes commit ids from the first changed commit onward. It drops signatures on the commits and tags it rewrites. `--sensitive-data-removal` keeps the `origin` remote. It prints `git push --force --mirror origin` while that remote is still present. Do not run that command. A mirror push deletes remote refs the clone does not have, and it does not use the freeze SHA. Push only with `--force-with-lease=<ref>:<recorded-sha>` after the checks below. The rewrite does not edit the checkout you use every day, and it does not delete that checkout.

`--replace-text` edits a blob only when the first 8192 bytes contain no NUL. That is the binary skip in 2.47.0 (`_tweak_blob`). A file without that NUL is edited, including a file that merely looks like text and is not the one you meant. A `regex:` or `glob:` line can change source that is not the secret. Use one literal line per secret, the exact bytes, and no `regex:` or `glob:` prefix. A line with no `==>` is replaced by `***REMOVED***`. `--replace-text` edits blob bytes. It does not rename paths. A secret that appears only in a filename stays in the tree.

`--replace-text` does not edit commit or tag messages. Add `--replace-message` with the same literal file when the text can appear in a message.

## Before anyone pushes

1. Tell every person and every agent with a clone to stop pushing. A push of the old history after the rewrite puts the text back.
2. Write down the branch protection or ruleset that blocks a force-push. You will lift that block only for the publish step, then put the same settings back.
3. Make a fresh clone. Do not rewrite the daily checkout. `git filter-repo --sensitive-data-removal` fetches refs beyond branches and tags, including pull-request refs, and that fetch can drop unpushed commits. Do not pass `--no-fetch`.
4. Record the freeze before the rewrite, and keep that list outside the clone:

```bash
git ls-remote origin 'refs/heads/*' 'refs/tags/*'
```

That list is the freeze record. Take it before the rewrite. A list taken after the rewrite records the remote as it is after the rewrite window, and the later lease would then authorize overwriting a commit that arrived during the rewrite.

5. Run the fetch the tool will actually run, then count. In git-filter-repo 2.47.0 the fetch is:

```bash
git fetch -q --prune --update-head-ok --refmap "" origin +refs/*:refs/*
```

A non-mirror `--sensitive-data-removal` run performs that fetch. A mirror clone has `remote.origin.mirror` set to true, and 2.47.0 skips the fetch in that case, so a mirror must run that exact command itself before the count. A non-mirror run and a mirror's own `+refs/*:refs/*` refspec both receive the `refs/pull/*` refs the remote advertises. GitHub advertises `refs/pull/*`. `--prune` removes a local ref the remote did not advertise, including a local `refs/pull/*`. The same fetch also removes `refs/remotes/origin/*`. The lease does not use those remote-tracking refs. Step 7 puts them back on a non-bare clone. The fetch also leaves more than one pack, or one pack and loose objects, so step 7 repacks before `git filter-repo`. The fresh-clone check does not pass on that restore alone. Do not fetch pull refs with another refspec and then run a shorter fetch. That shorter fetch prunes a local `refs/pull/*` the remote did not advertise. Before you trust the scan, `git show-ref` should list the `refs/pull/` tips you expect.

6. Record `git rev-list --all --count` after that fetch and before the rewrite. The verify step compares against this number. A count taken before that fetch is the wrong baseline. The repack in step 7 does not change this number.
7. After that count, and before `git filter-repo`, satisfy the fresh-clone check. Do not pass `--force`.

The fetch in step 5 deletes `refs/remotes/origin/*`. On a non-bare clone, git-filter-repo 2.47.0 stops before any rewrite when `refs/heads/<branch>` exists and `refs/remotes/origin/<branch>` does not. For every local branch:

```bash
git for-each-ref --format='%(refname:lstrip=2)' refs/heads | while read -r branch; do
  git update-ref "refs/remotes/origin/${branch}" "refs/heads/${branch}"
done
```

Do not pass `--force` to `git update-ref`. That restore does not finish the check. git-filter-repo 2.47.0 also aborts with `expected freshly packed repo` when there is more than one pack, or one pack and any loose object. The step-5 fetch stores the new `refs/pull/*` objects as loose objects, or as a second pack. That pack half runs for a non-bare clone and for a mirror. After the restore loop, run:

```bash
git repack -ad
```

A mirror skips the remote-tracking half, so it does not run the restore loop. After the mirror's own step-5 fetch, run `git repack -ad`. Then run `git filter-repo` with no `--force`. `git rev-list --all --count` is the same after that repack as it was before it. Do not pass `--force` to `git update-ref` or to `git filter-repo`. The tool's own fetch may prune `refs/remotes/origin/*` again after the check. The clone in step 3 is not a mirror, so that clone runs both the restore loop and the repack.
8. Put the exact text in one file outside every repository, mode `0600`. One secret per line when there are several. Do not put that text in a shell command, a commit message, an issue, a pull request, or a support request. The rest of this page calls that file the needle file.

## Find it without printing it

Search these places. The commands print a count or a ref name, not the text.

- Every branch tip and every tag tip: `git for-each-ref refs/heads refs/tags`.
- Every object in the database, including objects no ref points at: `git cat-file --batch-all-objects`, fed to the counter below. The counter reads blobs, commits, tags, and trees. A filename is stored in a tree, so a secret that appears only as a path is a hit. Run this before the rewrite. A count of zero means the needle file does not match those stored bytes. Fix the file or stop. Do not rewrite on a guess.
- Reachable objects only, after the rewrite: the same counter with `reachable`. This is the gate. A default run without `--no-gc` deletes the pre-rewrite objects before the command returns, so those objects are not left around for a later scan. This page passes `--no-gc`. With `--no-gc`, the all-object scan still sees the pre-rewrite objects until the verify step prunes, so that scan is still the wrong gate after the rewrite.
- `kinds`, after a non-zero `reachable` count: the same reachable objects, split into `blob`, `commit`, `tag`, and `tree`. A path hit is a `tree`. The command prints those four counts. It does not print the text.
- GitHub text the rewrite will not change: issues, pull requests, review comments, release descriptions, and the repository description. The owner runs that search. Record hit or miss for each surface. Do not paste the text into the record.

The counter reads the needle file and prints counts only. Run it from the fresh clone. `all` and `reachable` each print one integer. `kinds` prints four lines. `all` is the discovery scan. `reachable` is the gate.

```python
#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

mode, needle_path = sys.argv[1], Path(sys.argv[2])
needles = [line for line in needle_path.read_bytes().splitlines() if line]
if mode not in {"all", "reachable", "kinds"} or not needles:
    sys.exit("usage: count.py all|reachable|kinds NEEDLE_FILE")

def objects(scan):
    if scan == "all":
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

scan = "all" if mode == "all" else "reachable"
wanted = list(objects(scan))
counts = {b"blob": 0, b"commit": 0, b"tag": 0, b"tree": 0}
if wanted:
    raw = subprocess.run(
        ["git", "cat-file", "--batch"],
        input=b"\n".join(wanted) + b"\n",
        check=True, capture_output=True,
    ).stdout
    idx = 0
    while idx < len(raw):
        nl = raw.find(b"\n", idx)
        header = raw[idx:nl].split()
        size = int(header[2])
        start = nl + 1
        body = raw[start:start + size]
        if any(item in body for item in needles) and header[1] in counts:
            counts[header[1]] += 1
        idx = start + size + 1
if mode == "kinds":
    for kind in (b"blob", b"commit", b"tag", b"tree"):
        print(f"{kind.decode()} {counts[kind]}")
else:
    print(sum(counts.values()))
```

The counter needs Python 3.9 or newer. For `all` and `reachable`, stdout is a single integer. For `kinds`, stdout is `blob`, `commit`, `tag`, and `tree`, one count per line. Stderr stays empty on success. If `git cat-file` prints a missing object, the command fails and you stop.

## Rewrite

From the fresh clone, after the restore and `git repack -ad` in step 7, pass `--no-gc` so the old objects survive the diff in the next section. Do not pass `--force`:

```bash
git filter-repo --sensitive-data-removal --no-gc --replace-text /path/to/needle-file
```

Add `--replace-message /path/to/needle-file` when a commit or tag message can contain the text. Keep the path outside the clone. If the tool prints that LFS objects were orphaned, keep the file it names. The support request needs that file.

A default run without `--no-gc` runs `git reflog expire --expire=now --all` and `git gc --prune=now`. `--replace-refs` defaults to `delete-no-add`, so the old commits are not kept reachable. That run deletes the pre-rewrite objects before the command returns. `git cat-file -t` on an old tip then fails, and `git diff-tree -r` fails with `fatal: bad object`.

## Verify before any push

Stop when a check fails. Delete the fresh clone if you want to start over. The daily checkout is still the old history, which is what you have until you publish.

1. Reachable hits are zero. Run the counter in `reachable` mode. It must print `0`. If it does not, run `kinds`. When `blob`, `commit`, and `tag` are 0 and `tree` is not, the remaining hits are paths. `--replace-text` does not rename paths. Stop and ask the owner. Do not publish. Do not repeat `--replace-text` expecting it to clear a path.
2. The commit count matches the number recorded after the fetch above and before the rewrite. Compare `git rev-list --all --count` to that number. A count taken before that fetch is the wrong baseline. On a clone that is not a mirror, `--sensitive-data-removal` runs `git fetch -q --prune --update-head-ok --refmap "" origin +refs/*:refs/*` inside the rewrite, so a count taken before that fetch rises when pull-request commits are added even though the rewrite only replaced text. A different count from the recorded baseline means a commit was dropped or a ref was missing. Do not push.
3. Each tip tree differs only in the replaced lines. `.git/filter-repo/commit-map` maps old commits to new ones. Pair each old tip with its new tip and run `git diff-tree -r` on that pair while the commit-map's old objects still exist. Read the diff on this machine. It shows the removed text. Do not copy it into an issue, a commit, or a ticket. Any other change is a stop. After that diff passes, prune:

```bash
git reflog expire --expire=now --all
git gc --prune=now
```

Prune only after that diff. With `--no-gc`, the all-object scan still sees the pre-rewrite objects until this prune, so that scan is still the wrong gate. `reachable` is the gate.

4. Count moved pull-request refs with `grep -c '^refs/pull/.*/head$' .git/filter-repo/changed-refs`. Keep the first changed commit SHAs from the tool's `NOTE: First Changed Commit(s)` line. Later notes use those SHAs and that count. They do not use the text.

## Publish

`origin` is still present. Do not add it again. Do not run `git push --force --mirror origin`. The tool prints that command, and GitHub's guide shows the same command. This page does not use that form.

Run `git ls-remote origin 'refs/heads/*' 'refs/tags/*'` again. Compare it with the freeze record you stored outside the clone before the rewrite. Every SHA must still match that earlier record. If one does not, stop. Someone pushed. Do not overwrite that work. Push with the SHAs from that earlier record.

A fetch followed by `git push --force-with-lease origin main` does not check the freeze record. The fetch moves the remote-tracking ref to the new tip, and the unqualified lease then accepts that tip. That push can replace a commit that arrived after the freeze. This page does not use that form.

Push each rewritten branch with the SHA from the freeze record:

```bash
git push --force-with-lease=refs/heads/main:<recorded-sha> origin refs/heads/main
```

Push each rewritten tag the same way. `git push --force-with-lease origin tag v1.2.3` fails with stale info when the local tag object is not the remote tag object, because a tag has no remote-tracking ref, so a rewritten tag stays on the old history. When both sides already name the same object, Git reports everything up-to-date. Keep this form for the push that moves the tag:

```bash
git push --force-with-lease=refs/tags/v1.2.3:<recorded-sha> origin refs/tags/v1.2.3
```

Repeat for every rewritten ref, with that ref's name and its recorded SHA. The lease fails when the remote ref is not the recorded SHA. That failure is a stop. Do not switch that ref to `--force` unless the owner has seen which ref moved and approves that one ref.

Pushes of `refs/pull/*` are rejected. That rejection is expected, because GitHub marks those refs read-only. Any other rejection is branch protection. Lift only the protection you wrote down, push that ref again with `--force-with-lease=<ref>:<recorded-sha>`, and put the same protection back before you do anything else. When the only remaining failures are `refs/pull/*`, the protection is already restored.

A moved tag changes the commit a release points at. Open each release and confirm the tag still names the release you expect. If the GitHub-text search was a hit on a release description, edit that description. The rewrite does not.

## GitHub Support and other clones

Ask GitHub Support to drop the cached views and the pull-request refs. Include the owner and repository name, the pull-request count from `changed-refs`, and the first changed commit SHAs. If LFS objects were orphaned, say so and attach the file the tool named. Never name the purged text in an issue, a commit, or the support request. Support does not purge ordinary data, and it does not purge a credential that rotation already made useless.

Other clones must not `git pull` and then `git push`. That push puts the old history back. The usual fix is to delete the clone and clone again. A person who still has unpushed commits follows the colleague steps in the git-filter-repo manual: delete local tags, run `git fetch --prune --tags`, rebase onto the new history, then `git reflog expire --expire=now --all` and `git gc --prune=now`. That expire drops every reflog and every stash. Before that clone pushes, `git cat-file -t` on each first-changed SHA must fail. Do not run `git filter-repo` a second time in those clones. A second rewrite can mint different commit ids.

A fork is a separate repository. Ask that owner to delete the fork or to follow this page. GitHub cannot hand you their contact details.

## After

Delete the needle file when the owner no longer needs it for a missed hit. Do not commit it. Do not push a pre-rewrite remote, bundle, or backup into the repository.
