# Credential redaction

One contract for every Groundwork environment that prints or records a git
remote URL. A remote can carry credentials (`https://user:token@github.com/...`),
so nothing a script prints or records may contain them. Core owns the contract,
a reference helper, [`redaction/redact-url.sh`](../redaction/redact-url.sh), and
shared test vectors, [`redaction/redact-url-vectors.tsv`](../redaction/redact-url-vectors.tsv).
Each environment repo keeps its own copy of the helper or sources it from the
pin, and runs the vectors against it.

## Printing a URL

A script that shows a remote URL in a message passes it through `redact_url`
first. The rules, in the order the helper applies them:

1. Mask every full-length GitHub token anywhere in the URL with `***`:
   `gh[pousr]_[A-Za-z0-9]{36,}` and `github_pat_[A-Za-z0-9_]{22,}`. The match
   is not word-bounded and is greedy, so the whole run is masked. A shorter run
   is not a full-length token and is left alone.
2. Split off the scheme (`[A-Za-z][A-Za-z0-9+.-]*://`) when there is one.
3. If the rest holds an `@`, cut at the **last** `@` and replace everything
   before it with `***`. The only exception is a user that is exactly `git`,
   which is kept, so `git@github.com:owner/repo` and
   `ssh://git@github.com/owner/repo` print unchanged.
4. Drop the query and fragment: everything from the first `?` or `#` after
   that cut.

The cut is at the last `@` after the scheme, not at the end of the authority.
A password may contain `/`, `?`, `#` or `@`. An authority-only cut stops at the
first `/` and printed the start of such a password
(`https://user:pa/ss@host/...` showed `user:pa`). That version was reverted.
Cutting at the last `@` always removes the whole password, at the cost of the
limit below.

## Recording a repository

A receipt, log, or any file that outlives the run never records userinfo, a
host, a port, a query, or a fragment. It records only `owner/repo`, or a local
fallback that holds no part of the URL. When the remote cannot be reduced to a
plain `owner/repo` safely (a query or fragment, an `@`, `:` or whitespace left
in the path, `x-access-token`, or anything token-shaped), nothing is recorded
from it. This is stricter than printing, so the limit below does not apply to
records.

## Known limit

Text after the last `@` is shown. A secret that is not token-shaped and sits
after an `@` in the path (or in a query or fragment that itself contains an `@`)
can still show:

| Input | Printed |
|---|---|
| `https://github.com/owner/repo/@hunter2/x` | `https://***@hunter2/x` |
| `https://user:pw@github.com/owner/repo@hunter2` | `https://***@hunter2` |
| `https://github.com/owner/repo?t=a@hunter2` | `https://***@hunter2` |

The password before the host is always hidden, and a full-length GitHub token
is masked wherever it is. The same cut also over-redacts: `https://github.com/owner/repo@v1`
prints as `https://***@v1`, hiding the host and path. Git remotes almost never
have an `@` in the path, so this is accepted rather than parsed further. Lines
tagged `limit:` in the vectors pin this behavior. A change that closes the
limit updates those vectors and this section together.

## Test vectors

[`redaction/redact-url-vectors.tsv`](../redaction/redact-url-vectors.tsv) holds
input, expected output, and a note, tab-separated. Token-shaped inputs are
written as `{{PREFIX:N}}` (for example `{{ghp_:36}}`) and expanded at run time,
so the file never holds a value a secret scanner would flag. Run them against
any implementation that takes the URL as its last argument and prints the
result:

```bash
core/redaction/check-redact-url.sh core/redaction/redact-url.sh
core/redaction/check-redact-url.sh bash path/to/wrapper-that-sources-your-helper.sh
```

It prints each failure and a count, and exits 0 when every vector passes, 1
when any fails, and 2 on a usage error or an unreadable vectors file.

## Where it is implemented

| Repo | File | Rule |
|---|---|---|
| groundwork-mac | `bootstrap-mac.sh` `redact_url` (PR #90) | Printing |
| groundwork-mac | `scripts/ci_receipt.py` `repository_from_remote` (PR #86) | Recording |
| groundwork-omarchy-mac-arm64 | `scripts/migrate-from-groundwork.sh` `redact_url` (PR #97) | Printing |

Both `redact_url` copies matched the reference function line for line, and
both passed every vector, when this contract was written.

The receipt code refuses rather than masks, and it uses its own markers: a
`gh[opsur]_` or `github_pat_` run of 16 or more characters, `x-access-token`,
and `glpat-`. Those thresholds are lower than the masking rule above on
purpose. Refusing a value that only looks like a token costs nothing, while
masking a short value would hide ordinary path text.

## Core boundary

Core is documentation and data, not a machine installer. The helper only
transforms a string and reads and writes nothing. Environment repos decide
where to print a URL and wire the vectors into their own tests.
