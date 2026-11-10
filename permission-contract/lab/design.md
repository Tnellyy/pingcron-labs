# Synthetic permission-contract fixture

This toy HTTP receiver tests predetermined requests against stored scope and tenant permissions. It executes no model and implements neither MCP nor OAuth. It is not a jailbreak, product vulnerability, protocol-conformance or real authentication test.

Eight cases, three repetitions, fresh SQLite state per case: read control200; broad credential write with read-only intent metadata200; reader write403; reader A reads tenant B403; reader claims write scope403; broad write with readOnlyHint=true200; reader write with readOnlyHint=false403; unknown credential401. Client metadata is untrusted and cannot change the server's stored authorization. The hint field is an illustrative request field, not an actual MCP annotation.

The receiver verifies a public synthetic credential against its fixture table, checks stored action permissions, selects the resource with a tenant predicate, then acts. Mutation and audit share one SQLite transaction. An independent literal case plan expects status, response keys, full final resource rows, and mutation count. The runner queries durable SQL after the separate receiver exits and checks denial bodies contain no protected values.

The fixture shows only this deliberately implemented policy contract. Its value is a reproducible test template, not evidence about agent behavior or security of any actual service. Production requires real credential verification, expiry/audience validation, revocation, transport security, protocol handling and resource-specific authorization. No outside services, customer data or real credentials are involved.
