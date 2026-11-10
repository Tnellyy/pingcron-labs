# Independent experiment review: expired leases and stale writes

## Verdict: technically sound within the stated local scope

The reviewer did not implement the lab. I read all four final Python modules, challenged the design, independently executed all eight cases against the final source, and checked actual SQLite mutation rows and durable resource state. The final experiment supports the bounded claim: a receiver can reject an older token after accepting a newer one when the token check and mutation share one transaction. It does not prove that only the authority's current leaseholder can write at all times.

This is permission to use the observations as evidence, not an exact-article, visual, public-release or publication approval.

## Executions and independent observations

Executed the bundled Python3.12.14 runtime against lab.py with `--output outputs/pingcron-article-2026-11-09/lab/runs/reviewer-final-v2 --repeats 1`. All eight conditions reproduced. Builder final suite `lab/runs/windows-final-v2` contains three repetitions of each condition, 24 matching observations. Both sets identify the same four final source hashes.

| Condition | Independently observed accepted mutations | Result |
|---|---|---|
| control_fenced | A/token1/A-control | B acquisition refused before A expiry; A write accepted |
| stale_unguarded | B/token2/B-new, then A/token1/A-old | Stale A overwrites B |
| stale_fenced | B/token2/B-new | A receives409; B value and token2 unchanged |
| owner_check_toctou | B/token2/B-new, then A/token1/A-old | A's earlier successful ownership check does not stop stale overwrite |
| restart_fenced | B/token2/B-new | New receiver process reads retained fence; A receives409 |
| unseen_successor | A/token1/A-old, then B/token2/B-new | Old A accepted after B's grant, before sink has seen B's token |
| equal_token_writes | A/token1/A-v1, A/token1/A-v2, A/token1/A-v2 | Three mutations; equality does not deduplicate or order payload versions |
| token_counter_reset | B/token2/B-new | Explicit authority reset grants C/token1; C-fresh rejected409 |

All32 final/reviewer resource databases passed SQLite integrity checks. I queried their actual mutation histories and compared owner, token and value against retained aggregate observations. The fenced rejection leaves resource value, high-water and mutation history unchanged; rejection is recorded separately in the attempt audit. Equal-token writes produce three distinct rows, not merely a repeated final value. Final child-process exits are clean.

A passing suite means declared observations reproduced. Unsafe overwrite and omitted fresh work in the reset condition are deliberately expected negative outcomes, not successful business operations. Three repetitions are a bounded repeatability check, not a production failure-rate estimate.

## Actual expiry and causal ordering

A and B are separate worker processes. A retains token1 while waiting on an explicit stdin command gate. The runner waits until the recorded monotonic deadline is reached; B's acknowledged grant then has token2. The subsequent A command uses its retained token through real loopback HTTP. The receiver has a different SQLite database and does not query the lease authority.

The frozen receiver implements `BEGIN IMMEDIATE`, reads the durable high-water mark, rejects lower tokens or updates value/high-water and mutation history within that transaction. Equal tokens are intentionally accepted. The observer reads actual receiver state through a separate connection and literal case expectations.

A material harness precision defect was found and repaired during builder validation. The earlier24-case suite `windows-final` passed23/24 because it required strictly increasing nanosecond timestamps for causally ordered events. This Windows runtime reports GetTickCount64 with15.625ms resolution, so two different events can share a timestamp. The repair preserves nondecreasing deadline checks and adds explicit acknowledged-command event order. Worker.send waits for a response before appending its event and issuing the next command.

The independent final stale_fenced run itself demonstrates this issue: B grant and A attempt both have monotonic timestamp161090625000000, while B's acknowledged acquisition is event1 and A's write is event4. The sequence, completed HTTP operations and SQL snapshots establish causality without inventing finer timer precision. Earlier smoke, failed builder and independent-first-source records remain retained. They are not silently relabeled as final-source trials.

## Boundaries required in the article

- This is a cooperative process gate, not an operating-system suspension, measured GC pause or customer incident. The harness supplies fixture values in write commands; no stale snapshot computation was benchmarked.
- The inverse case is essential: after B receives token2 from the authority but before B reaches the sink, A/token1 is still accepted there. Highest accepted resource token is not necessarily the most recently issued authority token.
- A local preflight ownership check followed by an unguarded write does not close the pause window. The repaired check is at the mutation receiver and atomic with its own database effect.
- The restart case is a clean receiver process shutdown and restart after a completed write. It is not a crash-during-commit or power-loss durability test.
- Same-token equality allows repeated and changed payloads. Fencing does not supply idempotency or arbitrary business-version ordering within one holder.
- Counter reset is deliberate authority-state corruption/rollback. It demonstrates a dependency on non-rollback ordering, not a spontaneous provider failure or availability rate.
- One local SQLite authority does not establish distributed consensus, multi-host clock behavior, network partition safety, machine-reboot recovery, malicious-token resistance or a provider contract. Monotonic deadlines are scoped to this machine boot. The unauthenticated receiver trusts synthetic loopback callers.
- A transaction around the receiver-owned row cannot atomically include another service's email, payment or other external action. No exactly-once claim is supported. Expiry does not automatically terminate A.

Tested Windows11, Python3.12.14, SQLite3.53.1. Recorded SQLite settings: journal_mode delete, synchronous2/FULL, busy_timeout10000. Linux, distributed failover, production load and disk destruction were not tested.

## Final-source identities

SHA-256:

- common.py: 8d4e179b368acfda28c6e51ed8ba29e4672d9451fa2e724892b3a3ad4b129a86
- lab.py: bf9cbc51e8c7d46ece93f463c0351cb2b6b56e0b8b83bf1ad8ca39f6daf8f8b5
- receiver.py: c10901a029e24e4255fbd265ff32d96ab5e15ead5fa1ea8a7f985aad13c2ee05
- worker.py: 758159fe9454042059cebeb0f55378c4681c78d49bb2b6d90d1b5114e8335079
- lab/runs/windows-final-v2/RESULTS.json: 3209c1c214a23ea2651b9447eb1cec1b62e2ec2a181ad0195242ec2cca52bce5
- lab/runs/reviewer-final-v2/RESULTS.json: cb45ed34d3349995f279864c06576c5d8f615ec96be8c19615fdad172fd7d976

The exact article, claim map and images remain to be reviewed. Every final image needs native inline mobile checks at both required viewports before authorized publication. Static image proofs alone do not establish native cropping or legibility.
