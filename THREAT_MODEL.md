# Threat model

Assets: tenant evidence, personal records, source provenance, authority correspondence, approval records, credentials, model lineage and audit integrity. Trust boundaries: browser/API; identity provider; tenant/database; leased worker; source network/document parser; local inference; release/publication.

Controls: server-side roles and tenant predicates; optimistic versions; independent review; opaque expiring sessions; scrypt passwords; parameterised SQL; bounded request bodies; allowlisted source retrieval; untrusted documents never executed; no generic agent shell or aircraft commands; content-addressed documents; audit HMAC chaining; outbox in record transaction; leased bounded jobs; no customer data in release packages. TLS and host/network isolation are deployment responsibilities.

Audit chaining detects tampering against the retained HMAC secret and externally retained checkpoint. A database administrator possessing the secret can rewrite history: this is tamper-evident, not immutable storage. Backups require restricted access and a separate off-host checkpoint.

Residual risks to verify before stable release: full PostgreSQL concurrency and restoration, OIDC tenant mapping, source-parser isolation under hostile files, production egress rules, dependency advisories, external pentest, retention workflow and high-load behaviour. Local single-process portability mode is not evidence of enterprise scalability.
