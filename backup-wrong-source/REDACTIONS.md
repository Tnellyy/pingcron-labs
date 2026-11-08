# Public evidence provenance and redactions

The public copy is a documented derivative of retained local evidence. It is not represented as byte-identical to the private execution logs.

## Substitutions

- The absolute project lab directory prefix becomes `[LAB_ROOT]`.
- The machine-specific Python executable becomes `[PYTHON]`.
- Any absolute article project directory prefix becomes `[ARTICLE_ROOT]`.
- Both ordinary paths and JSON-escaped representations receive the same replacements.
- Text is normalized to UTF-8 without a byte-order mark where necessary.

No numeric observation, transaction value, timestamp, run ID, exit code, source hash or observed artifact digest was altered. Source files are copied byte-for-byte and match the reviewed environment manifest. Substituted paths in recorded commands are provenance placeholders, not runnable shell commands. Use the README commands to reproduce.

## Included and omitted

Included: nine reviewed Python files; final observed JSON/CSV; all nonempty final text logs and process records; independent reviewer aggregate results/environment; test transcript; documentation. Empty stdout/stderr files are omitted.

Omitted: earlier development runs, local scratch fixtures, private folder paths, original database/archive binaries, browser state and account information. Archive metadata included the machine's original source path, so original ZIPs are not published. The fixture builder deterministically recreates the logical data; a new execution has its own timestamps, run IDs, paths and byte digests.

Recorded binary digests identify the originals used during the experiment. They cannot be recomputed from this public derivative alone because those original binaries are intentionally omitted. This limitation does not prevent independent reproduction from the unchanged source. No customer or production data was used.

MANIFEST.json maps included evidence files to original and public SHA-256 values. Original filenames are relative to the private article package, never personal absolute paths. Public documentation is separately listed as authored release documentation. The package ZIP contains this manifest; ZIP-SHA256.txt beside the ZIP records the ZIP checksum and is not self-contained inside it.
