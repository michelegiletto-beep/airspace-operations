# Adversarial engineering review

Review date: 27 October 2026. Scope: identity, tenant storage, workflow decisions, worker execution, deterministic domain tools, evidence objects and persistent schedule reservations. This is a source and software-test review by a separate engineering responsibility in the same development team. It is not independent professional certification, penetration-test accreditation or aviation acceptance.

## Findings and disposition

| ID | Finding | Disposition and verification |
| --- | --- | --- |
| REV-001 | Approval independence checked only the original creator, allowing a reviewer who edited another person's record to become its preparer and approve it. | Closed. Server-controlled `_prepared_by` tracks each revision; creator/current preparer cannot approve. The isolated regression edits successfully and receives HTTP 403 on self-approval. |
| REV-002 | A client could alter an ordinary data field controlling second-review requirements. | Closed. Client decision/policy metadata is rejected; `AIRSPACE_REQUIRE_TWO_REVIEWERS` is deployment-controlled. Both ordinary decisions and schedule reservation honour the configured policy. A first schedule signature creates no reservations. |
| REV-003 | Domain-model validation exceptions could become HTTP 500 responses. | Closed. Explicit validation handlers return 422 with bounded error detail and without a traceback. |
| REV-004 | A chunked body was fully materialised before checking its size. | Closed for the tested API path. Streamed chunks are bounded at 2 MB before concatenation. A header-free 2.2 MB generator returns 413. This does not measure service-wide DoS resistance. |
| REV-005 | A worker interrupted on its third attempt could remain Running indefinitely after lease expiry. | Closed. Exhausted expired leases become audited terminal Failed records. |
| REV-006 | Queued workflow kinds shared a broad role allowlist rather than per-tool permission. | Closed. Tool-role checks occur on enqueue and execution; a changed actor role causes failure before tool use. |
| REV-007 | Client-created schedule records could contain a forged solver status/result. | Closed by source inspection. Generic schedule creation and generic transition are blocked; the solver workflow creates proposals. Controlled solver input/result/version bindings cannot be replaced through ordinary edits. Independent verification is still required before reservation. |
| REV-008 | Two non-overlapping schedules could independently consume the same aircraft readiness/battery budget or personnel duty episode. | Closed for the local tested persistence profile. Existing same-resource-revision reservations consume the shared budget. Separate tests reject cumulative battery and elapsed-duty over-allocation. |
| REV-009 | Schedule approval could use changed resource or issuer-receipt evidence. | Closed for tested version races. Approval checks exact persisted snapshots, record versions, approved resource/permission states and receipt evidence version/provenance/type/digest. Reviewed instrument type, validity and route/configuration scope must match. |
| REV-010 | Schedule reservation's tenant lock did not alone prevent a concurrent resource edit whose transaction had not yet reached audit insertion. | Changed by source review. Material record edits, transitions and evidence attachment take the same tenant lock before mutation. SQLite concurrent reservation is tested; PostgreSQL transaction isolation remains an unexecuted deployment check. |
| REV-011 | Mutable attachment metadata could falsely bind an evidence record to different content. | Closed for tested creation/addition/update paths. Generic creation/addition cannot supply attachment metadata; dedicated upload computes SHA-256, and ordinary record edits cannot alter an existing attachment/digest. Download rehashes content, rejects tampering and checks tenant ownership. |
| REV-012 | Minimum-length filtering and text deduplication removed short/repeated regulatory table rows; retained SORA 2.0 material was labelled 2.5. | Closed in the corrected corpus by the regulatory implementation responsibility. All nonempty table/paragraph rows keep distinct anchors; methodology derives explicit edition sections. Independent tests compare all implemented SAIL/TMPR cells against the preserved authoritative source snapshot. |
| REV-013 | Large candidate/window products and densified geometries could consume excessive computation despite small request bodies. | Bounded in the domain engines: capped resource counts, availability windows, examined combinations, solver duration and geometry work. No service-wide load-test claim is made. |
| REV-014 | The same intended-operation identity could be booked again in another slot through a different schedule. | Closed. A currently Reserved mission identity blocks further reservations across schedules. Explicit internal cancellation releases reservations with version/role checks and audit; cancelled proposals are terminal and replacements require current independent review. |

All closed dispositions above are limited to the stated code/tests. No finding authorises flights, declares a model fit for legal reliance, or validates the authenticity of an authority document.

## Tests actually executed

From the product directory, using the local Python environment:

```powershell
$env:PYTHONPATH='backend'
.venv/Scripts/python.exe -m pytest tests/test_operations.py tests/test_scheduler.py -q
.venv/Scripts/python.exe -m pytest tests/test_planning.py -q
.venv/Scripts/python.exe -m pytest tests/test_security_review.py -q
```

Observed intermediate results: domain tests **47 passed in 2.18 s** before two additional scheduling/dispatch tests; persistent reservation tests **11 passed in 5.23 s**; adversarial API/evidence/worker tests **8 passed in 5.50 s**. Final combined command:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_operations.py tests/test_scheduler.py tests/test_planning.py tests/test_security_review.py tests/test_api.py -q
```

Observed final combined result: **74 passed in 17.66 seconds**.

After the additional duplicate-mission and cancellation fixes, `tests/test_planning.py` and `tests/test_security_review.py` were rerun together: **22 passed in 11.23 seconds**. No known critical defect remained in the SQLite paths exercised by this review; unexecuted deployment and operational assurance work remains separate below.

Final rerun of the full combined command after cancellation integration: **77 passed, 2 warnings in 16.47 seconds**. The warnings occur during OR-Tools import on Python 3.13 and concern deprecated bitwise inversion of a boolean in a dependency; the tests pass. This is a dependency compatibility observation, not an operational performance measurement.

The tests use isolated temporary databases, test-only principals and artificial records labelled as software fixtures. Actual public regulatory passages provide the SORA lookup oracle. Tests exercise cross-tenant read/export/write attempts, self-review, decision metadata injection, source/evidence mismatch, missing inputs, wrong edition, stale data, resource contention, simultaneous approvals, site capacity, transaction rollback, replay separation, telemetry integrity, object tampering, escaped HTML exports, worker failure, typed errors and chunked request bounds. Their success is software evidence only.

## Open assurance work and limitations

- PostgreSQL/PostGIS transaction and deployment tests require an actual service. The observed concurrent reservation results are from SQLite; source inspection does not establish PostgreSQL operational performance.
- OIDC is an implementation path with configured issuer/audience and explicit user mapping. A live enterprise identity provider, credential rotation and deployment-specific SSO policy have not been accepted through this review.
- Evidence provenance and authority receipts are accountable user records. A checksum proves content identity relative to an expected digest, not issuer authenticity, authority validity or a qualified person's competence. Provider signatures and external authority verification require supported provider interfaces.
- Tamper-evident audit verification assumes protected key material and trustworthy external checkpoints. A database administrator who also acquires the audit key can rewrite history. The software reports that external checkpoints are required.
- Object-store backup/restore, filesystem permissions, reverse-proxy limits, secret rotation, retention/privacy policy, endpoint rate limiting and managed-service access require deployment-specific verification. Content-addressed upload may leave unreferenced objects after a failed database transaction; garbage collection is not an assurance mechanism.
- No real operator telemetry, operational weather, aeronautical service or U-space provider acceptance occurred in these tests. Connector declarations explicitly distinguish research purpose, Not Connected and operational acceptance.
- Numerical SORA support is limited to source-bound SAIL/TMPR and adjacent-ground-distance calculations. Full ground/air-risk derivation, containment tables, OSO compliance, occurrence-reportability rules and Detect and Avoid assurance require qualified domain work. Their absence must remain visible in capability/release status.
- Public release requires separate clean-install verification, source/data/model rights review, artifact/secret scanning, dependency review and publication verification. This report alone does not clear those gates.

Stable operational release remains blocked until the applicable assurance and acceptance evidence exists. A downloadable engineering release must preserve these limitations.
