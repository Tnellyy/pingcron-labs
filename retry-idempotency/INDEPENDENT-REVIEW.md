# Independent review of the retry experiment

Reviewed November 7, 2026 Pacific time, November 8 UTC, by backup_article_adversary. This reviewer challenged the design before implementation, read all five final Python modules, and independently reran the final matrix. The reviewer did not implement the lab.

## Verdict

**The bounded experiment passes independent review and supports the measured claims in the article brief.** No unresolved material defect was found in the tested mechanism. This is approval to use the specified observations as evidence, not approval of an unwritten article or permission to publish.

The useful result is two-sided: a real client read timeout can accompany either zero or one committed effect. A retry can then duplicate one intended operation, or a poorly scoped key can suppress a second intended operation. A retained stable key and atomic receiver transaction avoided a second receiver-owned effect in the tested conditions.

## Independent execution

From the lab directory, ran:

```powershell
& '[PYTHON]' lab.py all --output results/reviewer-independent --repetitions 1
```

All 12 independent observations matched the declared expectations. The builder's final suite contains 36 matching observations: three fresh repetitions of each of 12 conditions. These counts do not mean every request succeeded or every business intention was fulfilled. Duplicate effects and omitted work are expected failures in specific conditions. `business_target_met` keeps that outcome separate from `expectation_passed`.

Both runs used Windows 11, Python 3.12.14 and SQLite 3.53.1. The observed SQLite settings were journal mode `delete`, synchronous `2` (FULL), busy timeout 10,000 ms and foreign keys enabled. All five current source hashes matched both environment manifests. Linux, other database engines and production load were not tested.

## Independently observed matrix

| Condition | First client observation | Durable state at uncertainty | After retry or second request |
|---|---|---|---|
| control | HTTP 201 | One effect | One intended effect |
| after_commit_no_key | TimeoutError | One effect, no dedup record | Two effects for one intent |
| after_commit_per_attempt_key | TimeoutError | One effect and retained first key | Two effects for one intent |
| after_commit_stable_key | TimeoutError | One effect and retained key | Same status/body replayed, one effect |
| before_commit_timeout | TimeoutError | Zero effects and zero dedup records | Retry creates one effect |
| payload_mismatch | First201, changed amount409 | First effect unchanged | One valid effect, conflicting request rejected |
| distinct_intents_distinct_keys | Two201 responses | Separate intended operations | Two effects with identical business payloads |
| distinct_intents_reused_key | Two201 responses | Second response replays first | One effect, second intent omitted |
| concurrent_stable_key | Two201 responses | Both arrivals precede first commit | One effect and identical response bodies |
| crash_before_commit | ConnectionResetError | Receiver exit88, zero committed rows | Restart and retry create one effect |
| crash_after_commit | ConnectionResetError | Receiver exit89, effect and key retained | Restart and replay preserve one effect |
| dedup_record_removed | Two201 responses | Explicit removal retains effect but deletes key | Later request creates another effect |

Crash conditions produced `ConnectionResetError` in this independent Windows run. They are not reported as timeouts. The timeout conditions produced actual `TimeoutError` exceptions from the socket read, not a renamed disconnect.

## Evidence inspected beyond the aggregate assertions

For independent run `after_commit_stable_key-r1-8bca6c71`, the receiver committed at `00:43:05.340943+00:00`, reached the after-commit gate, and withheld response headers. The client recorded `TimeoutError` at `00:43:05.554567+00:00`. A separate SQL observation at `00:43:05.575045+00:00` showed effect ID1 and its retained key, fingerprint and original201 response. The gate was released afterward. The second fresh HTTP client received the original status and body with effect ID1. Causal test gates establish the ordering; timestamps supplement rather than replace them.

The before-commit inverse independently showed zero committed rows after the same exception class. The two key-policy duplicate cases showed two rows bearing one intended operation label. The over-deduplication case showed only the first of two intended operation labels. These observations are checked against exact planned operation labels, account and amount, not merely response codes or aggregate counts.

The concurrency test recorded two request arrivals at its barrier before the first database commit. `BEGIN IMMEDIATE` then serialized receiver writes. The process-crash cases reopened the same SQLite database in a new receiver process rather than reconstructing replay state in memory.

## Adversarial findings and limits resolved

1. **Atomicity cannot include an unrelated provider by naming a local row after it.** The code mutates only a receiver-owned SQLite ledger and commits effect, dedup key, payload fingerprint and response in one transaction. It does not send money, email or another external effect. Documentation preserves this boundary. No exactly-once delivery claim is approved.
2. **A timeout must be observed, not inferred from a stopped connection.** The tested gate creates an actual read timeout. Crash cases retain their real connection exception. The 200 ms deadline is fault-injection configuration, not a measured service-latency claim or recommended retry deadline.
3. **The test caller has extra visibility.** Its control endpoint confirms which gate has been reached, and the harness reads durable state. Ordinary callers lack that test-only knowledge. The README and brief state this distinction, so the experiment demonstrates a possible timeout/commit relationship rather than pretending the instrumented client was unable to inspect its own test fixture.
4. **Changing attempt ID is not itself what causes duplicate execution.** Attempt IDs change even when stable-key replay succeeds. An early conditional opening named a new attempt ID as the cause. The writer corrected it to a new idempotency key. The distinction must survive the eventual article.
5. **Fresh HTTP client processes do not prove autonomous job recovery.** The harness stays alive and supplies request files and keys from its plan. The current test demonstrates fresh client processes receiving the same supplied key, not an application recovering its identity from a durable outbox after the whole worker or harness crashes. The README and brief now state that limitation. Receiver crash/restart persistence is genuinely tested and remains a separate claim.
6. **Payload matching cannot infer intent.** The receiver rejects changed-payload reuse with409. It correctly replays identical parameters for a reused key, but that becomes a business failure when the independent plan intended two operations. Both directions appear in the results. The article must not present a hash of parameters as a universal operation identity.
7. **Retention is part of the contract.** Explicit test removal of the dedup row allows another effect. This does not model a real provider's expiry policy or a background TTL system. The retained-key guarantee is bounded.
8. **A local done flag remains untested.** Its before/after-remote-effect crash windows were considered during design but deferred. They may be discussed as sourced design reasoning with clear limits, not shown as measured cases or invented logs.

The receiver is unauthenticated loopback test scaffolding with mutating fault-control endpoints. It must not be exposed as a production service. It has one synthetic tenant scope and no claimed authentication or multi-tenant security guarantees. No production APIs or customer data were used.

## Reviewed fingerprints

SHA-256:

| Artifact | Hash |
|---|---|
| lab/client.py | 75e6fdddc2caf137366d1089c8c10db0ddfa4ad1ec84357f4338fe9899dad731 |
| lab/common.py | 3626c9a561b83e8f135a36ff4a1c8fda36461695637e8680becd62dd66aac543 |
| lab/lab.py | 834826ba8ac924df9233550ba4b0cc4cc61758a241c7b40920ca37a332c697f0 |
| lab/ledger.py | 201246176790bacc151b61c225917937ad3cf89e5c27d40c1f3c9586a1bfa74a |
| lab/receiver.py | e6b54d102e42f22f6ab600493e8d03ef58b4f11621a37e468a514bddd2dd2f1e |
| lab/results/windows-final/RESULTS.json | 5a953ec888f9943fd28461c625975a98d312fba901ab78c127b00c1efde33901 |
| lab/results/reviewer-independent/RESULTS.json | 50e45112808816608416e1f0c1a995ba664164151114e8a02fa3d0a072929120 |

## Next editorial gate

Use the actual per-attempt-key and stable-key observations to choose the opening and title. Keep the before-commit inverse and reused-key omission, since both prevent an oversimplified recommendation. The eventual article still needs exact-copy review, evidence-derived images, public-artifact preparation and the mandatory native mobile cover checks. This experiment review does not start publication or an automation. No em dashes or invented results are needed to make the demonstrated contradiction compelling.
