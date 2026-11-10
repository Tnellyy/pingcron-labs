# Expired leases and stale workers

Status: approved implementation design, results not yet observed.

## Bounded mechanism

Python standard-library subprocesses, a SQLite lease authority, and a separate loopback HTTP receiver with its own SQLite database. Worker A acquires a short lease and blocks at an explicit stdin command gate. The runner waits until the actual monotonic deadline passes, then B acquires a larger durable token. Each transition is acknowledged before the next step. This is controlled scheduling, not a production latency measurement or operating-system suspension test.

The authority is a single-machine toy, not distributed consensus. Monotonic deadlines apply only within this machine boot. The receiver does not query the authority. All data is synthetic and all HTTP is loopback.

Under `BEGIN IMMEDIATE`, the fenced receiver reads the resource's persisted high-water token, rejects lower tokens, otherwise writes value, high-water and mutation history together. The unguarded comparator accepts every mutation. Equality is permitted: the same holder may write repeatedly. Fencing therefore does not provide idempotency or business-version ordering within a holder.

## Matrix: three repetitions each

| Case | Sequence | Expected observation |
| --- | --- | --- |
| control_fenced | A owns unexpired lease; B attempts acquisition; A writes | B refused, A accepted |
| stale_unguarded | A pauses, expires; B acquires 2 and writes; A resumes with 1 | A overwrites B |
| stale_fenced | Same ordering, atomic fencing | A rejected; B preserved |
| owner_check_toctou | A ownership check succeeds, then pauses; expires; B writes; A writes | Separate preflight does not prevent overwrite |
| restart_fenced | B writes 2; receiver restarts on same DB; A writes 1 | Persisted fence rejects A |
| unseen_successor | B holds 2 but has not contacted sink; A writes 1 first | A accepted, then B accepted |
| equal_token_writes | A writes v1, v2, then repeats v2 using token 1 | Three mutation rows, no deduplication |
| token_counter_reset | Receiver accepted 2; deliberate authority rollback issues C token 1 | Fresh C rejected, exposing availability failure |

## Evidence and oracle

Each run records IDs, commands, process IDs/exits, worker transcripts, grant/deadline times, HTTP results, resource state, SQL mutation rows, source hashes and runtime settings. A separate literal expectation table defines statuses, final values and mutation payloads. The runner directly queries durable receiver state after important steps and shutdown. A passing suite means expected observations reproduced, including deliberate unsafe outcomes.

Adversary acceptance: control includes denied B acquisition; actual expiry precedes B grant; rejected writes leave value and high-water unchanged; equality creates distinct mutation rows; reset is explicitly injected.

## Strongest boundaries

- A lower token is rejected only after the receiver has observed a higher token. A new authority grant alone does not instantly revoke A at the independent sink. The unseen-successor case demonstrates this.
- The pause is a cooperative process gate, not evidence of how frequently a production worker pauses. No cross-host clock, consensus, partition or reboot guarantee is tested.
- Tokens are scoped to one synthetic resource and trusted authority. They are not authentication. Cross-resource namespaces and malicious token forgery are outside the experiment.
- Same-token writes are accepted, including repeats and changed payloads. Idempotency and within-holder ordering require separate mechanisms.
- A real resource must atomically enforce the fence with its mutation. Merely checking in the worker or forwarding a token is insufficient.
- Durable high-water and non-rollback token generation are required. The reset case is an explicit state-corruption injection, not ordinary behavior.

## Primary sources, checked November 9, 2026

- [Hazelcast FencedLock 5.7](https://docs.hazelcast.com/hazelcast/5.7/data-structures/fencedlock): paused holder, successor and resource-enforced fence.
- [Kleppmann: How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html): lease expiry, check-then-write race and monotonic fencing.
- [SQLite transactions](https://www.sqlite.org/lang_transaction.html): single writer and `BEGIN IMMEDIATE` behavior.

This is our bounded local implementation, not a test of Hazelcast, Redis or etcd.
