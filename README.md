# PingCron Labs

Runnable experiments and observed results behind PingCron technical articles. Synthetic fixtures, explicit limits, and runnable code.

## Lease fencing

[Your lock expired. Your worker kept writing.](lease-fencing/README.md)

Eight conditions test stale workers, atomic receiver fencing, preflight races, restart persistence and the boundary before a newer token reaches the receiver. 24 final builder observations and 8 independent reproductions. Synthetic Windows lab; earlier failures retained.

[Download source and results](lease-fencing/lease-fencing-source-and-results.zip?raw=true) · [Method and limits](lease-fencing/lab/README.md)

## Retry idempotency

[Your request timed out. Your retry created a duplicate.](retry-idempotency/README.md)

Twelve conditions test ambiguous HTTP outcomes, stable operation keys, atomic receiver-side deduplication, receiver crashes, concurrency and accidentally suppressed legitimate work. 36 builder observations and 12 independent reproductions. Windows verified.

[Download source and results](retry-idempotency/retry-lab-source-and-results.zip?raw=true) · [Read results](retry-idempotency/lab/results/windows-final/RESULTS.json) · [Method and limits](retry-idempotency/lab/README.md)

## Backup evidence

[A backup can exit 0 and restore the wrong data](backup-wrong-source/README.md)

A small SQLite experiment with eight conditions, three repetitions, independently reviewed code, and exact observed stage outcomes. Tested on Windows. All fixtures are synthetic.

[Download the lab and results](backup-wrong-source/lab-source-and-results.zip?raw=true) · [Read the results](backup-wrong-source/lab/results/windows-final/RESULTS.csv) · [Method and limits](backup-wrong-source/lab/README.md)

Personal machine paths in public logs are replaced with documented placeholders. Reviewed Python source files are unchanged. Each lab records its limitations; no production reliability or automatic repair guarantee is implied.
