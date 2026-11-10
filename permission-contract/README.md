# Read-only intent and actual permissions

A runnable synthetic permission-contract fixture. The identical predetermined write request succeeded with a broad credential and was refused with a reader credential. The receiver checked stored action permission and tenant identity independently of caller metadata.

**No model, MCP implementation, OAuth server, production service or real credential was tested.** The permitted broad-credential write was authorized, not a breach. This is a small authorization test template, not a jailbreak benchmark or a production security certification.

## Browsing this GitHub directory

This directory exposes the reviewed source, documentation and aggregate results. The ZIP contains all 478 archived files, including the per-case requests, responses, databases, process logs and deliberately broken reviewer copies. FILES.txt and MANIFEST.json describe the complete staged package and archive, not a claim that each file is separately browsable on GitHub. Every evidence link below targets an uploaded aggregate or document; download the archive for individual run files and fault-injection source.

This web README adds this browsing explanation. The reviewed README inside the archive is unchanged, and the manifest fingerprint for README.md refers to that archived version.

## Run

Download [source and all evidence](permission-contract-source-and-results.zip), extract, then:

```console
cd lab
python lab.py --output runs/my-reproduction --repeats 3
```

Python standard library only. Observed on Windows 11, Python 3.12.14, SQLite 3.53.1. Permit local HTTP on 127.0.0.1; choose a new output directory. The fixture keys are public synthetic strings. Keep this test receiver local and do not substitute production credentials or data.

## Evidence

- [Method, matrix and limits](lab/README.md)
- [Builder: 24/24 expected outcomes](lab/runs/windows-final-v2/RESULTS.json)
- [Independent reviewer: 8/8](lab/runs/reviewer-independent/RESULTS.json)
- [Reviewer fault-injection controls](lab/reviewer-mutation-checks/REVIEWER-MUTATION-RESULTS.json)
- [Independent review](INDEPENDENT-REVIEW.md)
- [Transformations](REDACTIONS.md), [original/public fingerprints](MANIFEST.json), [complete file list](FILES.txt)

The archive also contains the initial failed development run, all per-case requests/responses, SQL databases, process logs and copied reviewer variants. The initial failure occurred before HTTP calls because a runner variable shadowed its imported HTTP module; it is not permission evidence. The corrected builder run and independent reviewer use the two reviewed source files.

The reviewer removed the action check and tenant predicate in separate intentionally broken copies. Each retained a passing read control; the unchanged grader correctly failed the affected negative case. Those expected failures demonstrate test sensitivity and are not counted as production vulnerabilities or as extra successes in the original matrix.

To reproduce those negative controls from the extracted root:

```console
python lab/reviewer-mutation-checks/scope_check_removed/lab.py --output scope-negative --case scoped_write_denied --repeats 1
python lab/reviewer-mutation-checks/tenant_read_check_removed/lab.py --output tenant-negative --case tenant_read_denied --repeats 1
```

Both commands should exit 1 because the broken implementations violate the unchanged expectations. Run `--case read_control` with a different new output folder for their positive controls.

## Boundaries

Client `prompt_intent` and `readOnlyHint` fields here are inert test metadata. In MCP, readOnlyHint is a server tool annotation, not this invented caller schema. Trusted annotations can inform an enforced host or gateway policy. This test does not evaluate that enforcement, discovery filtering or actual MCP calls.

Read-only is not confidentiality: permitted reads still reveal data. The matrix tests tenant A reading B, but not every tenant/action/route combination. Real credential validation, audience and expiry, revocation, transport security, concurrency and additional resource rules remain outside this fixture.

Reviewed source bytes and synthetic SQLite databases are unchanged. Text derivatives replace personal machine paths as documented. No new license is asserted; the public repository's existing licensing status is preserved.
