# Retry idempotency: a timeout is not an outcome

Runnable synthetic evidence for the PingCron article **Your request timed out. Your retry created a duplicate.**

The local receiver can commit an effect before its client times out. Retrying without a stable operation key produces a duplicate in this experiment. A stable retained key and an atomic receiver-owned effect/key/result transaction replay the original response instead. Incorrectly sharing a key across two separate intentions can also omit legitimate work.

## Download or run

[Download the source and observed results](retry-lab-source-and-results.zip).

Python standard library only. Tested on Windows 11 with Python 3.12.14 and SQLite 3.53.1. Linux was not verified. Allow HTTP connections to 127.0.0.1 for the temporary local receiver.

```console
cd lab
python lab.py all --output results/my-run --repetitions 3
```

Use an output path that does not already exist. This starts only synthetic local fixtures and processes. No payment, email, third-party API or PingCron service is called. Do not expose this unauthenticated fault-injection receiver publicly.

Harness exit 0 means the experimental expectations matched. It does not mean all requests succeeded or all business intentions were met. Duplicate and omitted effects are expected failures in specific conditions. See the separate business_target_met field.

## Inspect the evidence

- [Lab method, commands and limitations](lab/README.md).
- [Final complete observations](lab/results/windows-final/RESULTS.json): 12 conditions repeated three times, 36 matching observations.
- [Compact CSV comparison](lab/results/windows-final/RESULTS.csv).
- [Final environment and exact source hashes](lab/results/windows-final/environment.json).
- [Independent reproduction](lab/results/reviewer-independent/RESULTS.json): all 12 conditions reproduced by a separate agent.
- [Independent technical review](INDEPENDENT-REVIEW.md).
- [Public transformations and omissions](REDACTIONS.md).
- [File provenance and SHA-256](MANIFEST.json).

Complete aggregate results contain client requests, actual errors/statuses, independent intent plans, durable state snapshots and receiver events. Per-case directories retain process commands/exits, event logs and byte-identical synthetic SQLite ledgers. Three repetitions are reproducibility checks, not estimates of production reliability.

## Boundaries

Only this receiver's own ledger insert shares the transaction with its deduplication record. This is not a solution for atomically committing an unrelated provider's email or payment, not an exactly-once delivery claim, and not a provider guarantee. Test gates make a genuine read timeout occur before or after commit; ordinary callers lack the experiment's oracle. The harness supplies keys to fresh HTTP clients and does not test recovery of a whole worker's logical identity after its own crash. Receiver restart and replay persistence are tested separately.

The five Python files are unchanged from the independently reviewed local version. The original execution had no Git commit; its recorded source hashes identify the version. Machine-specific paths in public text logs are documented placeholders. Numerical evidence and synthetic database bytes are preserved.

## License status

This release preserves the existing public repository's absence of an explicit license. No new license or additional grant is asserted by this packaging step.
