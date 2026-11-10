# Expired leases and stale workers

Runnable synthetic evidence for **Your lock expired. Your worker kept writing.**

An expired lease let a successor acquire while the old worker remained alive. In the unsafe ordering, the old worker overwrote the successor's result. An atomic receiver-side high-water check rejected the old token after accepting the newer token. A separate boundary case accepted the old token before the receiver saw the newer one.

## Run

Download [source and all recorded results](lease-fencing-source-and-results.zip), extract, then:

```console
cd lab
python lab.py --output runs/my-reproduction --repeats 3
```

Python standard library only. Tested on Windows 11, Python 3.12.14, SQLite 3.53.1. Allow temporary loopback HTTP on 127.0.0.1. Choose an output directory that does not already exist. No production data, credentials, external API or PingCron service is used. Do not expose the unauthenticated test receiver publicly.

## Evidence

- [Method, observed matrix and limits](lab/README.md)
- [Final builder results: 24 observations](lab/runs/windows-final-v2/RESULTS.json)
- [Independent reviewer results: 8 observations](lab/runs/reviewer-final-v2/RESULTS.json)
- [Independent review](INDEPENDENT-REVIEW.md)
- [Transformations](REDACTIONS.md) and [file fingerprints](MANIFEST.json)

Eight conditions include a working control, unsafe stale write, receiver fencing, ownership-check race, clean receiver restart, unseen successor, equal-token repeats and deliberate authority counter reset. Three builder repetitions check reproducibility, not a production failure rate. Harness success means the declared outcomes matched, including deliberately unsafe results.

The downloadable archive contains all recorded suites, including the socket-access failure and a 23/24 harness run whose strict timestamp comparison was corrected for the measured 15.625 ms clock resolution. The earlier evidence remains inspectable.

## Limits

The receiver's durable high-water token is not a live query of current lease ownership. It rejects lower tokens only after a higher one reaches it. Equality is allowed, so fencing does not deduplicate repeated work. The transaction covers this receiver-owned SQLite value only. No exactly-once, cross-service atomicity, consensus, network partition, OS-suspension, production latency, power-loss or automatic repair guarantee is claimed.

Reviewed Python source bytes are unchanged. Public text logs replace machine paths with documented placeholders. The repository's existing absence of an explicit license is preserved; no new license is asserted.
