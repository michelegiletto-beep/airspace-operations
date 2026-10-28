-- Schema version 3 is a compatibility boundary for actor-private companion data.
-- Stop every older API, worker, CLI and scheduled client before this migration.
-- Existing sessions are not fenced by a version marker. No mixed-version run.
-- Store.migrate applies the equivalent insert under this transaction lock.
BEGIN;
SELECT pg_advisory_xact_lock(719443302);
INSERT INTO schema_versions(version, applied_at)
VALUES (3, to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') || '+00:00')
ON CONFLICT (version) DO NOTHING;
COMMIT;
