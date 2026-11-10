# Independent adversary review: read-only intent and receiver permissions

## Verdict: PASS for the bounded lab and exact article draft

The reviewer did not implement the original fixture or write the article. I read both Python modules, the README/design boundaries, raw final observations, research and exact claim map/article. I independently reproduced all eight cases and tested two isolated deliberately broken receiver copies. No material technical defect remains in the stated toy contract or current prose. This is a draft/artifact verdict, not approval of a production security boundary, eventual images or publication.

## Literal scope

**No model, MCP implementation, OAuth server, production account or real credential was exercised.** The runner issued predetermined local HTTP requests to a deliberately specified server policy. `prompt_intent` was inert request metadata, not an instruction executed by a model. The toy caller field named `readOnlyHint` was not a real MCP server tool annotation. The broad synthetic credential was explicitly authorized to write; its HTTP 200 was not a breach, jailbreak or bypass.

The useful contribution is a reproducible authorization contract and a checklist that separates operation permission from resource ownership. It is established access-control engineering, not a novel vulnerability. Its applicability to an agent workflow is a design question, not measured model behavior.

## Independent reproduction

Ran the bundled Python 3.12.14 interpreter against permission-lab/lab.py with `--output outputs/pingcron-2026-11-09-article-and-replies/permission-lab/runs/reviewer-independent --repeats 1` over loopback-only HTTP. All eight observations matched. Both final builder and reviewer environments identify the same two source hashes.

| Case | Independent HTTP | Accepted mutations | Meaning |
|---|---:|---:|---|
| read_control | 200 | 0 | Reader receives only its allowed A resource |
| broad_prompt_write | 200 | 1 | Broad stored permission allows the fixed write |
| scoped_write_denied | 403 | 0 | Reader cannot perform the identical write body |
| tenant_read_denied | 403 | 0 | A reader receives no B resource data |
| claimed_scope_denied | 403 | 0 | Caller metadata does not elevate the reader |
| hint_does_not_restrict | 200 | 1 | Caller hint does not narrow broad server policy |
| hint_cannot_elevate | 403 | 0 | Caller hint does not elevate reader policy |
| unknown_credential | 401 | 0 | Unknown fixture identity receives an error only |

The broad and reader paired request bodies are equal. Their credential and isolated receiver address differ. The grader checks complete resource rows, exact response bodies, mutation history, audit decisions, unchanged policy rows and clean process exit. I independently queried all 32 final-builder/reviewer SQLite databases: integrity checks passed and resource rows matched retained observations. Denials still append an audit record; 'no mutation' in the article correctly concerns the protected resource and resource-mutation history.

The builder's 24 final observations are eight cases repeated three times. My eight are independent executions of the same final source. These are bounded contract checks, not a failure rate, attack-success rate or comprehensive security assessment. The earlier 0/24 module-shadowing run is honestly retained and explicitly not counted as permission evidence.

## Deliberate faults prove the checks can fail meaningfully

Created reviewer-only source copies under `permission-lab/reviewer-mutation-checks/`. Original source bytes remained unchanged. Each variant retained a passing own-tenant read control, avoiding the weak explanation that the whole server was simply broken.

1. **Removed server action-permission check.** The reader's write returned 200, changed A to `changed-by-fixture` version 1, and added one mutation. The unchanged grader exited 1 with six failed checks: status, body, protected rows, mutation history, audit decision and denial payload. This demonstrates detection of the specified missing action check.
2. **Removed the tenant predicate from resource selection.** The A reader received B's `B-private-fixture` value with 200. The unchanged grader exited 1 with four failed checks: status, body, audit and denial payload. Both resource rows stayed unchanged, demonstrating why unchanged state alone cannot establish read confidentiality.

Raw copied source, process commands/stdout/stderr and results are retained. `REVIEWER-MUTATION-RESULTS.json` summarizes the four executions: two positive controls and two expected negative detections. Do not add these to the original suite's counts or describe the deliberately broken copies as production vulnerabilities.

## Remaining technical limits

The tested matrix is eight fixed cases, not every operation/tenant/route combination. Cross-tenant read is tested; broad-credential cross-tenant write is not separately exercised. Missing/expired/revoked credentials, audience validation, alternate routes, concurrency, timing channels, enumeration, egress and other execution paths are outside this fixture. Synthetic lookup is not complete authentication. SQL parameter binding and stored policy support the intended toy behavior but do not establish overall application security.

A filtered discovery list is not the same evidence as invocation denial. A genuinely enforced client or gateway allowlist can be a real boundary. The article preserves that distinction instead of dismissing all client controls. Similarly, a trusted tool annotation can inform an enforced policy; the annotation alone is not that enforcement. Read-only is not confidentiality, and permitted reads can still expose sensitive data.

The standard-library reproduction uses Windows 11, Python 3.12.14 and SQLite 3.53.1. No unexecuted platform claim is needed. Local socket access was separately authorized for this reproduction. No real service or account was contacted by the lab.

## Research and exact prose

The research uses dated November 7 captures and explicitly says it lacks a new November 9 X census. It separates the captured 17x author-relative outlier from other merely high-view or below-baseline examples, reduced baseline sizes, unequal exposure ages and unverified external research claims. It does not infer fixed X boosts or guaranteed bookmark behavior. The current topic is an editorial hypothesis, not a proven winning format. No article prose relies on the optional model-release announcement or its benchmarks.

I reopened the three cited primary MCP pages. The annotation explanation supports hints versus enforcement and trust; the pinned tools specification distinguishes list/call and requires access controls; the pinned authorization specification scopes its flow to HTTP and makes MCP authorization optional while specifying token audience/permission handling. The article confines those claims to the specifications, separately from the toy results.

The exact 1,006-word article opens with concrete response/state differences and immediately says no model made the requests. The two compact tables provide useful reference material. It does not claim a model disobeyed a prompt, a real annotation was bypassed, all hints are useless, or a valid token grants every resource. The conclusion asks where actual refusal occurs and how unchanged data is demonstrated. The writing is serious, specific and natural, with zero em dashes, no fabricated customer story, no product pitch and no unsupported reach promise.

No exact-copy repair was required. The writer elected to keep the new reviewer mutation findings in artifact evidence rather than lengthen the article; that is accurate and does not diminish the stated article claims.

Primary sources independently checked:

- https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/
- https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization

## Artifact identities and later gates

| Artifact | SHA-256 |
|---|---|
| article.md | f4a96cfdcd6a56012ac50f01f404ef903e1b7f2af1056d92cd3e35a27d80050d |
| permission-lab/lab.py | e476639cadef76c62a4da6999541fd511b91e06c8c6a51c8d72b0a1d5ad1aa12 |
| permission-lab/receiver.py | 1a1b1ec35dd3f7c6bd4a8be111741e8536cd99f1c29b984c1527ea4a75488fce |
| runs/windows-final-v2/RESULTS.json | 4393a17a2dbff55ceff9a06c264995a2135c452f415a7463ebfabbcdb52333ed |
| runs/reviewer-independent/RESULTS.json | 04518ccfbc8d3dd4e1dd97888174dd84830375023a124d816c5ba9af8d540a98 |
| reviewer-mutation-checks/REVIEWER-MUTATION-RESULTS.json | 98bfd0babf6f300d6e6f4e39203876e07e2f91b7baebb1f9e4a18af821025ebc |

The article links to a local README and is not represented as a public download. A later public release needs path/privacy review and actual accessible URLs. Images, if added, need exact evidence review and every-image native mobile checks at both required viewports. This report does not claim those assets or publication have already passed. No browser or account mutation was performed by this reviewer.

## Four-image addendum: PASS for the local draft

I independently viewed the cover and all three body figures at static image widths of 360 and 390 pixels, plus the narrower 232-pixel proofs. Labels are readable; no overlap or clipping was observed. These are actual resized PNG views, not inferred from font sizes. They are not native X viewport screenshots. Body figures are 750 by 980 pixels, with essential text at least 46 source pixels, equivalent to about 14.2 pixels at a 232-pixel content width. Cover foreground and headline are comfortably inset in the inspected uncropped proofs.

The diagrams do not impersonate product screens or terminal output. The cover is a conceptual credential/gate illustration. Figure 1 correctly distinguishes the identical write body from different credentials: broad HTTP 200 with one resource mutation, reader HTTP 403 with zero. It visibly states that no model ran the test. Figure 2 is explicitly conceptual in its caption; it distinguishes intent, behavior descriptions and enforcement, includes server/host/gateway enforcement, and does not claim an actual MCP pipeline was measured. Figure 3 accurately shows own-resource read 200, own-resource write 403 and other-tenant read 403. It tells the reader to inspect returned data and stored state. Its caption excludes untested cross-tenant writes and other confidentiality paths.

I recomputed all four image digests and every cited result-file digest against the visual manifest. I reopened the corresponding SQLite files read-only and compared complete resources and mutation rows with retained JSON. All values depicted agree with those files and the earlier independent reproduction. The broad credential's permitted write is not presented as a security breach.

| Final visual | SHA-256 |
|---|---|
| visuals/cover.png | 4050996aa1f852a352d495b4ca0d80a762dafbce4c8cde05e7f09cc4992c17cf |
| visuals/01-same-write-body.png | c65ccc5749ae06181450346e9cfb8250b8963786c859aab28e530ea57558a8b9 |
| visuals/02-policy-layers.png | a650d47cbeb0dcf982ef6212ee7519f64fb6448f98c714332939f02f39435089 |
| visuals/03-reader-boundaries.png | bc8264eeb43fe8184d0c51ed416624a16befb8c5ecae92da9a27ee63679938a6 |

I also read article-with-images.md. Its original prose is exactly preserved after removing the added image/caption lines and normalizing whitespace. The four captions are accurate and there are zero em dashes. Requested a minor formatting repair: blank lines before image blocks, especially after the table and title. This changes no factual claim or asset.

This is a completed local-draft visual review only. Native X inline checks at both 360 and 390 viewport widths, actual crop behavior and saved screenshot evidence remain unperformed and required before any later publication. No publication or browser action was performed by this reviewer.

Formatting repair independently verified: all four image blocks now have preceding blank lines; original prose remains identical after the stated normalization. Final article-with-images.md SHA-256: 01d9b17f494688932b9471956924692c6f74ef7978997a2da61874a5b37e19d6. PASS for this exact local draft with the four hashed images above. Native/publication gates remain unchanged.
