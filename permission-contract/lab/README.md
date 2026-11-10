# A permission contract, not an agent benchmark

This synthetic local HTTP fixture sends predetermined read and write requests to a receiver with stored credential permissions and tenant checks. It does not run a model, implement MCP or OAuth, exercise a real integration, or demonstrate a product vulnerability. The results establish only this toy receiver's deliberately specified contract.

## Observed results

Final run: `runs/windows-final-v2`. All 24 cases passed their expected predicates, eight cases repeated three times. Exit 0 means the expected contract outcomes reproduced. An allowed write is not called a security breach: the broad synthetic credential was explicitly authorized to write.

| Case | Actual HTTP status | Resource mutations | Observation |
| --- | --- | --- | --- |
| read_control | 200 | 0 | Tenant A reader receives resource A |
| broad_prompt_write | 200 | 1 | Broad credential writes despite client intent metadata |
| scoped_write_denied | 403 | 0 | Same request body with reader credential is denied |
| tenant_read_denied | 403 | 0 | Tenant A reader receives no resource B value |
| claimed_scope_denied | 403 | 0 | Claimed client write scope does not elevate reader |
| hint_does_not_restrict | 200 | 1 | Client hint does not restrict broad server authority |
| hint_cannot_elevate | 403 | 0 | Client hint does not elevate reader authority |
| unknown_credential | 401 | 0 | Unknown synthetic credential receives no data |

Every denied request preserves both tenants' complete resource rows and creates no mutation row. The response body contains only an error. A separate audit record records the attempted action and decision.

The paired broad/scoped write uses the same `INTENT_WRITE` request in `lab.py`:

```json
{
  "action": "write",
  "resource": "resource-A",
  "value": "changed-by-fixture",
  "client_metadata": {"prompt_intent": "read_only"}
}
```

The differing server-stored credential changes the outcome. No model read or disobeyed that metadata. The harness deliberately sent the write request in both cases.

## Run

Python 3.12 or later, standard library only. From this directory:

```text
python lab.py --output runs/my-reproduction --repeats 3
python lab.py --output runs/one-case --repeats 1 --case tenant_read_denied
```

Output must be a new directory. The receiver binds only 127.0.0.1 on an ephemeral port. Local socket permission is required. No model/API calls, real credentials, production services, package downloads or customer data are used. The fixture credential strings are public synthetic data and are not usable outside this toy server.

Exact observed command from the workspace root:

```powershell
& '[PYTHON]' 'outputs/pingcron-2026-11-09-article-and-replies/permission-lab/lab.py' --output 'outputs/pingcron-2026-11-09-article-and-replies/permission-lab/runs/windows-final-v2' --repeats 3
```

Observed environment: Windows 11 build 10.0.26200, Python 3.12.14, SQLite 3.53.1. No portability claim is made for systems not run. `environment.json` records exact runtime, argv and source hashes. Receiver connections explicitly configure SQLite DELETE journal and FULL synchronization.

## Evidence

- `RESULTS.json`: full plans, before/after SQL, HTTP response bodies, predicates and process exits.
- `RESULTS.csv`: compact observed table.
- `SUMMARY.json`: passed/failed count and exact source hashes.
- Per-case directories: independent literal plan, exact request URL/headers/body, response, receiver stdout/stderr, readiness/PID, state database and result.
- `final-manifest.json`: hashes and sizes of final evidence files.

The runner compares complete resource rows, expected mutation rows, status, exact response body, audit decision and unchanged server policy. It inspects the database after the separate receiver exits cleanly; it does not infer state solely from HTTP status. Expected outcomes are literal fixture data, not computed from the receiver's authorization result.

`runs/windows-final` preserves an earlier 0/24 development run that failed before sending HTTP requests because a local variable shadowed the imported HTTP module. The corrected `windows-final-v2` is the article dataset. The failed run is not evidence of any permission outcome.

## Implementation boundary

`receiver.py` looks up the presented synthetic credential in its own SQLite policy table. Action permission comes from that stored row. Resource selection includes the stored tenant ID as a SQL predicate. Client metadata never changes either value. An accepted write and its mutation/audit records share a database transaction.

The field named `readOnlyHint` here is explicitly untrusted caller metadata used as a teaching example. In MCP, `readOnlyHint` is a tool annotation, not this request schema. This fixture is not a valid MCP ToolCall or MCP security test. Similarly, the request's `prompt_intent` field is not a model instruction being executed.

Trusted tool annotations and enforced client allowlists can contribute to real defense in depth. These results do not establish that every hint or client policy is useless. This fixture tests only the independent server authorization boundary and does not implement discovery filtering or client-side enforcement.

Production authentication and authorization require additional work: real credential validation, issuer and audience constraints, expiry/revocation, protocol-compliant errors, transport security, resource-specific policy, and a complete set of routes and actions. None is certified by this simple credential lookup. It does not test hidden tools, OAuth scopes, token exchange, consent screens, agent persistence, prompt injection or jailbreak success rates.

Read permission itself can expose sensitive data. A read-only credential is not automatically harmless. Tenant restriction is separately checked here, but other confidentiality policies are outside the fixture.

See `design.md` for the scope and planned checks. Article technical claims about real MCP/OAuth must cite their primary specifications separately from these local observations.
