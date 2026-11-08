# Independent review of the backup experiment

A separate backup_article_adversary agent inspected the implementation, complete article and figures, and independently reran the reviewed source. The reviewer did not implement the experiment or write the article.

Review completed November 7, 2026 Pacific time, November 8 UTC. The bounded experiment passed review with no unresolved material technical defect. This is not a claim of an external human audit or production certification.

## Independent reproduction

```console
python lab.py all --output results/reviewer-independent-20261107 --repetitions 1
python test_predicate.py
```

All eight expected case observations matched. All four additional tests passed. The 16 comparison rows describe two policies sharing eight experimental runs. Windows 11, Python 3.12.14 and SQLite 3.53.1 were used. Source hashes matched the builder's final environment manifest.

The reviewer confirmed the independent fixture oracle, exact logical-value comparison, separate integrity and foreign-key assertions, fresh verifier process, explicit source-read guard probes, and separation of successful backup work from failed signal delivery. The guard is a cooperative Python audit hook, not an OS security sandbox.

The review corrected an earlier temporal description of the lost-object injection. The receiver removes the stored object before returning HTTP 201; the next GET returns HTTP 404. It also verified that storage object keys are restricted to a safe whitelist. The reviewed final documentation states those behaviors.

The original unredacted final RESULTS.json SHA-256 is 6d9444a9044d6248813c7dbabe648755d54089c4139854220a6b9401cef0f013.
The original unredacted independent RESULTS.json SHA-256 is 0ed4a8249d8d7131cb5930e6bd99c0cc62b7167bd40669c191f3b66b0aabf86e.

Public derivative hashes differ where machine paths were replaced. See MANIFEST.json for exact provenance and REDACTIONS.md for the transformation. The original reviewed evidence remains privately retained. No numerical outcome, timestamp, exit code, run ID or observed digest was changed.
