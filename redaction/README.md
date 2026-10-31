# Credential redaction

Reference helper and shared vectors for the contract in
[docs/credential-redaction.md](../docs/credential-redaction.md). Environment
repos copy or source `redact_url` from the `core` pin and run the vectors
against their copy. This directory installs nothing.

- `redact-url.sh`: the reference `redact_url`. Source it, or run `redact-url.sh URL`.
- `redact-url-vectors.tsv`: input, expected output, and note per line.
- `check-redact-url.sh CMD [ARG...]`: runs every vector as `CMD ARG... INPUT`.
