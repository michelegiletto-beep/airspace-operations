# Monitoring API integration verification

Executed on 27 October 2026 from the product directory:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_monitoring_api.py -q
```

Actual completion output:

```text
..................                                                       [100%]
18 passed in 35.28s
```

The tests use the real FastAPI routes, tenant-scoped SQLAlchemy Store, persistent record revisions, independent procedure-review transitions, evidence references and audit-chain verification. Each test receives an isolated temporary SQLite database. Runtime storage is redirected to the test temporary directory, and no external feed, production data store or operational aircraft is contacted.

Verified boundaries include:

- Explicit manual-import rights attestation, required source rights reference and permitted user roles.
- Tenant-scoped aircraft, mission and expected-aircraft references.
- Live and historical-replay separation, mismatched-mode quarantine and truthful unknown freshness without a monitoring policy.
- Duplicate redelivery with changed receipt time, concurrent duplicate imports and contradictory source-event reuse.
- Current independently approved monitoring-policy requirements, deterministic stale-track alerts and alert deduplication.
- Alert acknowledgement authentication, roles, tenant isolation, optimistic version checks, ownership, notification separation, persistent history and audit integrity.
- Prohibited generic alert creation.
- Deterministic incident assessment with missing or unapproved procedures, no invented checklist steps, no aircraft commands, truthful external-notification state, linked timeline isolation and explicit degraded-snapshot metadata.

All artificial observations and approval fixtures are confined to isolated software tests. Passing this suite does not establish live provider connectivity, operational acceptance, certified surveillance, qualified aviation review or authority permission.
