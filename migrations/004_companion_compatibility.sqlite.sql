-- Schema version 3 is a compatibility boundary for actor-private companion data.
-- Stop every older API, worker, CLI and scheduled client before this migration.
-- Do not remove the marker to downgrade. Restore a complete pre-upgrade backup
-- into a separate controlled environment if an older application is required.
-- Store.migrate applies the equivalent insert under its startup migration lock.
BEGIN IMMEDIATE;
INSERT INTO schema_versions(version, applied_at)
SELECT 3, strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')
WHERE NOT EXISTS (SELECT 1 FROM schema_versions WHERE version = 3);
COMMIT;
