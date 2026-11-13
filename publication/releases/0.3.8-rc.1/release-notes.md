# Release 0.3.8-rc.1

This engineering candidate repairs PostgreSQL extension compatibility and rejects incomplete database initialisation. Original specification acceptance, stable release and operational acceptance remain false.

The observed failure loaded a newer PostGIS library into PostgreSQL 17.8. Extension initialisation stopped before the application role was created. After restart, the administrator readiness probe accepted the incomplete database, while API and worker authentication failed. The repair pins PostgreSQL 17.12 and rebuilt PostGIS and pgvector packages together. Readiness now authenticates the restricted application role over TCP, checks its privileges and required grants, and executes both extension libraries using read-only SQL. An isolated regression deliberately interrupts bootstrap and requires this check to reject the resulting database even when TCP connections succeed. No worker-health timeout or approval requirement was weakened.

Development source `3f1e338d1d9ebf4ff110a5b6f4a64ba5b519ec8e` passed [Linux verification 43320866252](https://github.com/michelegiletto-beep/airspace-operations/actions/runs/43320866252): 644 source tests with 20 skipped, 19 PostgreSQL checks, the interrupted-bootstrap regression, fresh container health, authenticated API and worker completion, and backup/restoration. The Windows interface separately passed 205 tests and a build. These are measurements for that source and environment. The exact release source, clean archive installation, dependencies, rights and secrets are checked separately by the release pipeline; consult its attached evidence. Earlier failed runs remain recorded.

The readiness check does not repair existing volumes. Preserve affected data, objects and the audit key and follow the controlled recovery runbook. The separately installed 0.3.7 SQLite primary is unchanged. This release neither migrates nor promotes it. Previous source tags, downloads and receipts remain intact.

The retained release screenshot records the historical 0.3.6 confirmation review. It is not a 0.3.8 container or installation result. No new screenshot or change to the animated companion is claimed. Artwork rights remain reserved under the existing notices.

No model call, training run, new operational record, aircraft command, authority decision, external submission or communication capability was added. The experimental student and dataset remain unchanged and unpromoted. Deployment-specific recovery checks, qualified review and applicable permissions remain required for operational use.
