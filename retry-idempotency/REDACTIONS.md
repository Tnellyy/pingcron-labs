# Public evidence transformations

The public evidence is a documented derivative of retained local records. Originals remain privately archived. The five reviewed Python source files and distributed synthetic SQLite databases are byte-identical to their originals.

Only text encoding and machine-path prefixes change in exported evidence:

- Absolute lab directory prefix becomes `[LAB_ROOT]`.
- Absolute article directory prefix becomes `[ARTICLE_ROOT]`.
- Machine-specific Python interpreter path becomes `[PYTHON]`.
- The same replacements apply inside JSON-escaped and ordinary slash/backslash paths.
- Text is normalized to UTF-8 without a byte-order mark when necessary.

No numerical observation, operation/attempt/run ID, timestamp, actual exception name, business value, response, source hash or exit code is changed. Placeholders in recorded commands are provenance, not executable commands. Use the README commands to reproduce.

## Included

Five reviewed Python modules, public run instructions, both complete final/reviewer aggregate datasets and environments, final CSV, independent technical review, original intent plans, process commands/exits, receiver event logs, nonempty error logs, unchanged synthetic ledger databases and final console transcript.

Aggregate RESULTS.json already contains every attempt request/result and durable snapshot. Separate per-attempt stdout/result JSON files that duplicate that aggregate content are omitted. Empty stdout/stderr files, previous development runs, strategy research, X captures, browser state, accounts and unrelated private files are excluded. No customer or production data was used.

MANIFEST.json maps each included original evidence file to its original and public SHA-256 and identifies authored release documentation separately. The manifest is inside the downloadable ZIP. ZIP-SHA256.txt beside it records the ZIP checksum and is intentionally outside the archive to avoid a self-reference.

The target public repository has no explicit license. This release does not introduce one or imply an additional license grant.
