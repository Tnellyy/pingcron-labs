# A backup can exit 0 and restore the wrong data

A runnable SQLite failure experiment accompanying PingCron's first technical article.

The exporter can complete successfully while backing up a stale, same-schema source. An independently defined expected-data check rejects that artifact even though it is structurally valid SQLite. The stronger workflow exits nonzero; the headline does not claim it accepted the wrong data.

## Run the experiment

Python standard library only. Tested on Windows 11 with Python 3.12.14 and SQLite 3.53.1. Linux has not been verified. Allow local HTTP connections to 127.0.0.1.

```console
cd lab
python lab.py all --output results/my-run --repetitions 3
python test_predicate.py
```

Choose an output directory that does not already exist. The experiment creates only synthetic fixtures and a temporary local receiver. It uses no customer data, cloud account or PingCron credentials.

The harness exits 0 when expected observations are reproduced. Individual backup workflows can and do exit nonzero. See [the lab documentation](lab/README.md) for stage exits, method and limits.

## Evidence

- [Final observations](lab/results/windows-final/RESULTS.json): eight conditions, three repetitions, all 24 expected observations reproduced.
- [CSV policy comparison](lab/results/windows-final/RESULTS.csv): 48 policy rows sharing 24 underlying runs, not 48 independent experiments.
- [Final environment and reviewed source hashes](lab/results/windows-final/environment.json).
- [Independent review](INDEPENDENT-REVIEW.md): a separate agent reproduced all eight conditions and all four additional tests.
- [Redactions and omissions](REDACTIONS.md): public logs retain observations while replacing personal machine paths.
- [File provenance](MANIFEST.json): original and public file hashes.

The ZIP lab-source-and-results.zip contains this same runnable source and evidence package. No simulated image or invented terminal output is used as experiment evidence. Three repetitions do not estimate a production failure rate. Local HTTP does not establish off-site durability.

The nine Python files are the exact reviewed source bytes. This public repository packages a previously executed local artifact; the original execution had no Git commit, and its source hashes provide the version identity.
