# Commit identity guard

Reference implementation for the contract in
[docs/commit-identity.md](../docs/commit-identity.md). Environment repos vendor
or reference `commit-identity-guard.sh` from the `core` pin and wire it into
git hooks. This directory installs nothing and never edits git config.

- `commit-identity-guard.sh`: `commit-msg`, `pre-push`, and `doctor` modes.
- `commit-denylist.example`: the denylist format. The real file lives outside
  every repo.
- `owner-remote-patterns`: the `includeIf hasconfig:remote.*.url` patterns that
  scope the hooks to the owner's repositories.
