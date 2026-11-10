# Your lease expired. Your worker continued.

A reproducible synthetic local experiment, observed November 9, 2026 Pacific time. The final run began November 10 UTC.

## Observed result

The final suite reproduced all 24 expected observations: eight cases, three repetitions. This includes deliberately unsafe outcomes. Exit 0 from the runner means the expected outcomes reproduced, not that every policy protected the resource.

Final evidence: `runs/windows-final-v2/RESULTS.json`, `RESULTS.csv`, `SUMMARY.json`, and `environment.json`. Each run directory contains the independent intent plan, both SQLite databases, worker and receiver stdout/stderr, receiver readiness records, and full result predicates/transcripts.

| Case | HTTP statuses | Accepted mutations | Final value | Meaning |
| --- | --- | --- | --- | --- |
| control_fenced | 200 | 1 | A-control | B could not acquire A's unexpired lease; A wrote before expiry |
| stale_unguarded | 200, 200 | 2 | A-old | Old A overwrote B after lease expiry |
| stale_fenced | 200, 409 | 1 | B-new | Receiver rejected token 1 after accepting token 2 |
| owner_check_toctou | 200, 200 | 2 | A-old | A's earlier successful ownership check did not protect its later write |
| restart_fenced | 200, 409 | 1 | B-new | Clean receiver restart retained the committed high-water token |
| unseen_successor | 200, 200 | 2 | B-new | A was accepted first despite B already holding the newer grant; B then wrote |
| equal_token_writes | 200, 200, 200 | 3 | A-v2 | Same-token v1, v2 and repeated v2 all created mutations |
| token_counter_reset | 200, 409 | 1 | B-new | Deliberately reset authority issued a fresh token 1, rejected against stored 2 |

All three repetitions of each row produced these values. `unseen_successor` also records the intermediate durable state A-old with high-water 1. Rejection cases assert that both resource state and accepted-mutation history remain unchanged; a separate attempt audit records the rejection.

## Run it

Use Python 3.12 or later with its standard library and permission to open loopback sockets. No packages, credentials or external services are needed. From this `lab` directory:

```text
python lab.py --output runs/my-reproduction --repeats 3
python lab.py --output runs/one-boundary-case --repeats 1 --case unseen_successor
```

The output directory must not already exist. The default short lease is 500ms and can be set with `--lease-ms`, minimum 100ms. A very busy host can fail an asserted preflight/control deadline; failures are retained, not silently retried as successes. Local process readiness and I/O have bounded harness timeouts. These settings are fault-injection controls, not production recommendations or performance measurements.

Exact command used from the workspace root on this machine:

```powershell
& '[PYTHON]' 'outputs/pingcron-article-2026-11-09/lab/lab.py' --output 'outputs/pingcron-article-2026-11-09/lab/runs/windows-final-v2' --repeats 3
```

The run's `environment.json` also records executable, command arguments, working directory, source SHA-256 hashes and runtime versions. Process records contain every child command, PID and observed exit code.

## Actual environment

- Windows 11, build 10.0.26200.
- Python 3.12.14, MSC 1944, 64-bit AMD64.
- SQLite 3.53.1.
- SQLite journal mode DELETE, synchronous 2 (FULL), busy timeout 10000ms.
- `time.monotonic_ns()` uses GetTickCount64 on this runtime. Reported resolution is 0.015625 seconds.
- No Linux, WSL, macOS, multi-host, reboot or power-failure execution is claimed.

## How the evidence is generated

`common.py` implements a toy SQLite lease authority. A grant increments the token and records a monotonic deadline in one local transaction. Expired ownership permits a successor to acquire. `worker.py` is an actual subprocess: it acquires its lease, then waits for its next stdin command. The runner withholds that command to create the pause. This is a cooperative scheduling gate, not an operating-system suspension or GC reproduction.

The runner waits until the actual monotonic deadline has elapsed, then commands B to acquire. The grant and expiry timestamps are captured. A remains alive and holds its old token in process memory. The runner commands the real workers to send HTTP mutations to a separate receiver process. A-old and B-new are supplied synthetic intent payloads, not outputs of a measured report computation.

`receiver.py` uses `BEGIN IMMEDIATE` to read the persisted high-water token and update the protected value, high-water and mutation history together. The fenced policy rejects lower tokens. The unguarded comparator intentionally omits this rejection, while retaining the same transport and data model. Its high-water column is observation only and does not protect writes.

The runner's literal expected-case table is independent of receiver decisions. It queries durable SQL state directly rather than treating HTTP success as proof. Synchronous command acknowledgements establish the event order. Clock values verify deadline passage and nondecreasing observations; equal timestamps can occur because the runtime clock has coarse resolution.

Every child exits cleanly with code 0 in the final suite. Receiver persistence tests stop the process after a completed commit and start a new process against the same database. They do not test crashes during commit or power-loss durability.

## Receiver contract checklist

1. Generate increasing tokens in the correct authority and resource namespace. Do not reuse or roll back them.
2. Send the token to the resource that owns the effect. A worker-side preflight is not atomic with a later mutation.
3. Compare the token and apply the business mutation atomically at that resource.
4. Persist the resource's high-water state across ordinary restarts.
5. Define equality deliberately. This example permits it, so repeated or reordered writes by the same holder remain possible.
6. Decide whether the required property is rejection after a newer token arrives, or immediate revocation at authority handover. The latter needs a stronger protocol than this independent high-water receiver.
7. Protect token issuance and the receiver. A number supplied by an untrusted client is not authorization.

## Boundaries

The receiver knows the highest token it has seen, not the authority's latest grant. Issuing B token 2 does not itself tell the receiver about 2. The old-token-before-new-token case intentionally allows A's write. Therefore the evidence supports rejecting lower tokens after higher ones have reached this resource, not a claim that every expired holder is immediately unable to write.

The same-token case deliberately allows all three writes, including an identical repeat. Fencing is not deduplication, exactly-once execution, payload-version ordering, or a transaction across outside services. A real protected API must implement the necessary enforcement itself.

The authority uses one local monotonic clock and one SQLite writer. It is not a distributed lease service, consensus protocol or clock-skew test. Stored deadlines are meaningful only within the same machine boot. Tokens here apply to one synthetic resource. Cross-resource scoping, authentication, authority recovery from backup, and coordinated multi-resource effects are outside this lab.

The reset case explicitly corrupts authority state for a negative test; it does not suggest ordinary grants reset their counter. The receiver correctly rejects the new lower token, preserving safety here while blocking fresh work.

## Preserved development evidence

- `runs/windows-smoke`: sandbox-restricted run, 0/8 due to Windows rejecting loopback socket connections with WinError10013. No production behavior is inferred from this access failure.
- `runs/windows-smoke-loopback`: authorized loopback run, 8/8.
- `runs/windows-final`: 23/24. One assertion incorrectly required a strictly larger timestamp for two causally ordered events. Their timestamps were equal at the actual clock's 15.625ms resolution. All case business outcomes matched the plan.
- `runs/windows-final-v2`: corrected predicate requires nondecreasing clock values and explicit acknowledged command order, 24/24. Prior evidence is preserved.

The final source hashes appear in its environment and summary files. Independent review records, when completed, are separate from the author's run and do not overwrite it.

## Primary sources

These sources justify the mechanism and implementation choices, not a claim that our experiment tests their products:

- [Hazelcast FencedLock 5.7](https://docs.hazelcast.com/hazelcast/5.7/data-structures/fencedlock).
- [Martin Kleppmann: How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html).
- [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html).

Sources checked November 9, 2026. See `design.md` for the original hypotheses and strongest objections.
