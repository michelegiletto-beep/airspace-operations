# Upgrading to version 0.3

Version 0.3 stores actor-private companion conversations, messages, tasks and action previews. Older application code does not enforce those privacy rules. Schema version 3 therefore marks a startup compatibility boundary even though these entities use existing tables.

The marker prevents a newly starting 0.2 API or normal worker from accepting the upgraded database. It is **not a fence for an already-running old process**, a database administrator or a client issuing direct SQL. A mixed-version or rolling upgrade is unsafe.

## Controlled upgrade

1. Plan a maintenance window and stop every old API, worker, CLI process, scheduled job and replica that can access the database or SQLite file. Stop user traffic. For Compose, stop both `api` and `worker`; stopping only one is insufficient. For PostgreSQL, confirm that older application sessions are closed. Changing a password alone does not terminate an existing session.
2. Create and verify a consistent checkpoint containing the database, complete object store, permitted source material and private audit key. Record the old application version, schema markers, organisation counts and audit heads. Use the [recovery runbook](recovery-runbook.md). Keep backups private and protect them under the organisation's retention policy.
3. Test this upgrade on a restored isolated copy before the real deployment. Build and install one reviewed 0.3 application image or source revision. Start no older application against the upgraded copy.
4. Run `airspace migrate` with the new binary while old processes remain stopped. The application applies markers 1, 2 and 3 under the existing SQLite immediate transaction or PostgreSQL advisory transaction lock. The matching explicit SQL files are `migrations/004_companion_compatibility.sqlite.sql` and `.postgresql.sql`; use the selected deployment's controlled migration procedure.
5. Verify schema version 3, audit heads, attachment integrity and existing operational records. Check that a second same-organisation account cannot read another actor's companion history, tasks, action previews or reply jobs. Confirm that tenant boundaries and normal role-specific operational workflows still work.
6. Start only the new API and worker, verify their versions and health, exercise a private companion conversation and confirmed personal task, then restore user traffic through the deployment owner's acceptance process. Local model execution and applicable operational acceptance remain separate checks.

## Rollback

Use a compatible 0.3 binary for an in-place software recovery. To return to 0.2, stop all new writers and restore the complete pre-upgrade checkpoint into a separate controlled database and object-store environment. Changes made after that checkpoint require an explicit reconciliation decision; they are not silently merged into an older format.

Never delete or lower marker 3 to force an older application to start. Do not point old services at a database that contains private companion data. Do not overwrite a running operational instance or publish backup contents as release evidence.

The isolated regression uses the exact frozen 0.2 storage source and verifies rejection before domain queries or DDL. That software test does not establish a deployment's service shutdown, PostgreSQL migration, restoration, network isolation or operational acceptance; those need their own recorded evidence.
