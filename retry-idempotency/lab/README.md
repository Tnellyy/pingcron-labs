# Retry after a lost response: a local failure lab

This standard-library Python experiment separates what the client observed from what the receiver committed. It uses a synthetic account ledger owned by a local HTTP receiver. No money moves, no email is sent, and no third-party or PingCron API is called.

## Run

Use Python with SQLite support and allow local HTTP connections to 127.0.0.1. Tested on Windows 11 using Python 3.12.14 and SQLite 3.53.1. Linux execution is not verified.

```console
python lab.py all --output results/my-run --repetitions 3
```

Or run one condition:

```console
python lab.py after_commit_stable_key --output results/my-stable-key --repetitions 1
```

The chosen output directory must not exist. Each case creates a fresh ledger, intent plan, receiver process and set of client processes. The receiver is terminated after the case; crash cases deliberately restart it against the same persistent ledger.

Harness exit 0 means the expected observations were reproduced. It does not mean every HTTP request succeeded or every business intent was fulfilled. In particular, duplicate effects and a suppressed legitimate operation are expected observations in the deliberately faulty conditions. `business_target_met` records the separate business outcome.

## What was observed

`results/windows-final/` contains three fresh repetitions of each of the twelve conditions, 36 observations total. All 36 matched the defined experimental expectations. Three repetitions check reproducibility, not a production failure rate.

| Condition | At first uncertainty | Final effects | Business target met? |
|---|---|---:|---|
| control | HTTP 201 | 1 | yes |
| after_commit_no_key | TimeoutError, one effect already committed | 2 | no: duplicate |
| after_commit_per_attempt_key | TimeoutError, one effect already committed | 2 | no: duplicate |
| after_commit_stable_key | TimeoutError, one effect already committed | 1 | yes: original result replayed |
| before_commit_timeout | TimeoutError, zero effects committed | 1 after retry | yes |
| payload_mismatch | First request 201, changed amount with same key 409 | 1 | yes: changed request rejected |
| distinct_intents_distinct_keys | Same payload, separate intended operations | 2 | yes |
| distinct_intents_reused_key | Same payload, wrongly shared key | 1 | no: second intent suppressed |
| concurrent_stable_key | Two requests meet before starting their transactions | 1 | yes: one original response replayed |
| crash_before_commit | Receiver exits 88 after insert but before commit | 1 after restart/retry | yes |
| crash_after_commit | Receiver exits 89 after commit but before response | 1 after restart/replay | yes |
| dedup_record_removed | Retained key explicitly removed by test control | 2 | no: replay creates another effect |

Crash cases record actual connection exceptions separately from timeouts. In all six crash observations in this Windows execution the client observed `ConnectionResetError`. Retention removal is an explicit injected action, not an observed provider TTL or background expiry policy.

## The receiver's transaction

The receiver opens an explicit `BEGIN IMMEDIATE` transaction. Within that transaction it looks up `(scope, operation_key)`, checks the canonical business-payload fingerprint, and either replays the stored original status/body or inserts the effect and stores the key, fingerprint, original status/body and effect ID together. It commits before attempting the response.

The observed SQLite settings are journal mode `delete`, synchronous `2` (FULL), busy timeout 10,000 ms and foreign keys enabled. Settings are recorded in the environment and each durable-state observation. Connections are closed explicitly. The concurrency barrier releases two requests before the transaction boundary; the SQLite write transaction then serializes them. Events prove both arrived before the first commit.

The effect and deduplication record share the same database transaction because the receiver owns the ledger insert. An external charge, email or other provider call cannot simply be included in this SQLite transaction. This lab does not solve that distributed boundary, prove exactly-once delivery, or establish a cloud-provider guarantee.

## A real timeout with deterministic ordering

The after-commit fault holds response headers behind a named `threading.Event` after the commit. The test client sends its request, confirms the gate through a read-only test control endpoint, then starts reading the response with a 0.2-second socket timeout. The server cannot send the held response until the harness releases the event. The client records an actual `TimeoutError`; the harness reads the durable ledger before releasing the gate.

The inverse gate holds before the transaction and aborts that attempt when released. It produces the same client `TimeoutError`, but the durable ledger is empty at that point. The normal caller would not know which happened from the timeout alone.

This out-of-band gate and ledger oracle belong to the experiment. A production caller does not have that visibility. The 200 ms setting is an injected read deadline, not a measured latency claim or retry recommendation. Polling only waits for explicit control state; it does not assume a commit completed because enough time elapsed.

Each retry runs in a new HTTP client process and reads a persisted attempt request. The harness remains alive and supplies the same key to those clients from its intent plan; attempt IDs change independently. There is no shared HTTP-client memory carrying a cached success result across retries. This does not test the whole job or harness crashing and recovering its logical identity from an operation outbox. Receiver restart and replay durability are tested separately.

## Why key scope matters

`operation_id` is an experimental intent label used by the independent oracle, not a uniqueness constraint. The receiver fingerprints the business payload, which contains account and amount. It deliberately excludes attempt metadata and the experimental label.

Two legitimate operations can have identical business payloads. They require different keys. Reusing a key for those separate intents returns the original response and suppresses the second effect, which is a business failure even though both requests receive 201. Conversely, generating a new key for each attempt fails to tie retries to the original intent and permits a duplicate.

The independent oracle compares exact operation labels, account and amount against the persisted plan, not just effect counts or HTTP status. The payload-mismatch condition reuses one key with a different amount and is rejected with 409 before mutation.

## Crash and retention boundaries

The before-commit crash occurs after an effect row has been inserted but before the transaction commits. The receiver process exits immediately with code 88. Reopening the database rolls back the incomplete transaction; the oracle observes no effect or dedup record, and retry commits once.

The after-commit crash exits with code 89 before sending response headers. The durable effect and cached result remain. A restarted receiver replays the original status and body for the retained stable key, including the original effect ID.

Deleting the deduplication record while retaining the effect removes that replay memory. A later request with the old key creates a second effect. The bounded claim therefore depends on retained keys and intact receiver state; it is not an unlimited promise about retries forever.

## Evidence

- `results/windows-final/environment.json`: runtime, SQLite settings, command and exact five-source-file hashes.
- `results/windows-final/RESULTS.json`: all 36 observations, each including intent plan, client errors/statuses, receiver events and durable SQL snapshots.
- `results/windows-final/RESULTS.csv`: compact derived comparison for reading; JSON contains the complete records.
- `results/windows-final/SUMMARY.json`: expectation count and any failures.
- Each distributed case directory: immutable intent plan, client and receiver process commands/exits, receiver event log, nonempty stderr and unchanged synthetic SQLite ledger. The aggregate RESULTS.json contains the complete attempt inputs, client outcomes and durable snapshots without duplicating each into separate files.
- `execution-windows-final.txt`: final execution transcript.
- `results/reviewer-independent/`: a separate reviewer reproduced all 12 conditions. Earlier development runs remain privately archived and are not included in this public release.

The final source is a standalone output artifact, not a Git working tree. Exact source hashes identify the executed version. No commit ID is invented. The final cases ran on November 8, 2026 UTC, November 7 Pacific time.

## Limits and deferred work

This is a small local ledger experiment with one receiver process at a time, cooperative fault gates and a local SQLite database. It does not test multi-region replication, asynchronous external side effects, database loss, provider idempotency contracts, backoff design, queue acknowledgements, cross-service outboxes, production load or durability after disk destruction. Local client done-marker crash windows were intentionally deferred rather than mixed into this matrix.

The receiver's control endpoints are intentionally unauthenticated test scaffolding bound to loopback. Do not expose it publicly or use it as a production service. The code accepts only synthetic plan data in this experiment. The independent adversary reproduced all 12 conditions against the same source hashes; see ../INDEPENDENT-REVIEW.md. That dated technical review is preserved as evidence, not presented as publication authorization.

Public logs replace personal machine prefixes with [LAB_ROOT], [ARTICLE_ROOT] and [PYTHON]. Source bytes and recorded numerical observations are unchanged. See ../REDACTIONS.md and ../MANIFEST.json.
