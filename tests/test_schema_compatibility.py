"""Use exact prior-release code to test the private-data startup boundary."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import event, select

from airspace.identity import provision
from airspace.storage import (CURRENT_SCHEMA_VERSION, Store, identifier, now,
                              records, schema_versions, versions)


REFERENCE = Path(__file__).resolve().parent / "references/legacy_storage_v0_2_0.py"
KEY = b"isolated-schema-compatibility-test-key"


@pytest.fixture(scope="module")
def old_storage():
    provenance = json.loads(REFERENCE.with_suffix(".provenance.json").read_text())
    assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == provenance["sha256"]
    assert provenance["source_commit"] == "3d5376758493f8e791dce85968947878990c6b6f"
    spec = importlib.util.spec_from_file_location("frozen_storage_v0_2_fixture", REFERENCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.CURRENT_SCHEMA_VERSION == 2
    return module


def isolated_schema_two(tmp_path, old_storage):
    url = "sqlite:///" + (tmp_path / "compatibility.db").as_posix()
    old = old_storage.Store(url, KEY)
    old.migrate()
    actor = provision(old, "Isolated compatibility software fixture", "owner@test.invalid",
                      "regulatory", "isolated-compatibility-password")
    row = dict(id=identifier(), organisation_id=actor["organisation_id"], kind="companion_message",
               title="Isolated private test message", status="Completed",
               data={"owner_actor_id": actor["id"], "text": "Isolated software fixture only"},
               version=1, created_by=actor["id"], created_at=now(), updated_at=now())
    with old.engine.begin() as conn:
        conn.execute(records.insert().values(**row))
        old.snapshot(conn, row)
        old.append_audit(conn, actor["organisation_id"], actor["id"], "isolated.private.created", {"record_id": row["id"]})
    before = old.verify_audit(actor["organisation_id"])
    old.engine.dispose()
    return url, actor, row, before


def test_schema_two_upgrade_preserves_private_records_versions_and_audit(tmp_path, old_storage):
    url, actor, row, before = isolated_schema_two(tmp_path, old_storage)
    current = Store(url, KEY)
    try:
        current.migrate()
        current.migrate()
        assert CURRENT_SCHEMA_VERSION == 3
        with current.engine.connect() as conn:
            assert set(conn.execute(select(schema_versions.c.version)).scalars()) == {1, 2, 3}
            stored = conn.execute(select(records).where(records.c.id == row["id"])).mappings().one()
            assert dict(stored) == row
            assert conn.execute(select(versions.c.snapshot).where(versions.c.record_id == row["id"])).scalar_one() == row
        assert current.verify_audit(actor["organisation_id"]) == before
    finally:
        current.engine.dispose()


def test_actual_old_storage_rejects_schema_three_before_domain_queries(tmp_path, old_storage):
    url, actor, row, before = isolated_schema_two(tmp_path, old_storage)
    current = Store(url, KEY)
    current.migrate()
    legacy = old_storage.Store(url, KEY)
    statements = []
    event.listen(legacy.engine, "before_cursor_execute", lambda conn, cursor, statement, params, context, many: statements.append(statement.lower()))
    try:
        with pytest.raises(ValueError, match="Database schema is newer"):
            legacy.migrate()
        # The frozen implementation must reject at its real preflight. A
        # replacement function or a newly written version comparison is not used.
        assert any("schema_versions" in statement for statement in statements)
        assert not any(statement.lstrip().startswith(("create ", "alter ", "insert ", "update ", "delete ")) for statement in statements)
        assert not any("from " + table in statement for statement in statements for table in ("records", "record_versions", "users", "audit", "jobs"))
        with current.engine.connect() as conn:
            assert dict(conn.execute(select(records).where(records.c.id == row["id"])).mappings().one()) == row
            assert set(conn.execute(select(schema_versions.c.version)).scalars()) == {1, 2, 3}
        assert current.verify_audit(actor["organisation_id"]) == before
    finally:
        legacy.engine.dispose()
        current.engine.dispose()


def test_explicit_sqlite_compatibility_migration_is_idempotent(tmp_path, old_storage):
    url, actor, row, before = isolated_schema_two(tmp_path, old_storage)
    path = tmp_path / "compatibility.db"
    sql = (Path(__file__).resolve().parents[1] / "migrations/004_companion_compatibility.sqlite.sql").read_text()
    with sqlite3.connect(path) as conn:
        conn.executescript(sql)
        first = conn.execute("SELECT applied_at FROM schema_versions WHERE version=3").fetchone()[0]
        conn.executescript(sql)
        assert conn.execute("SELECT applied_at FROM schema_versions WHERE version=3").fetchone()[0] == first
        assert conn.execute("SELECT COUNT(*) FROM schema_versions WHERE version=3").fetchone()[0] == 1
    current = Store(url, KEY)
    try:
        assert current.verify_audit(actor["organisation_id"]) == before
        with current.engine.connect() as conn:
            assert conn.execute(select(records.c.data).where(records.c.id == row["id"])).scalar_one() == row["data"]
    finally:
        current.engine.dispose()


def test_current_binary_also_refuses_an_unknown_future_schema(tmp_path):
    store = Store("sqlite:///" + (tmp_path / "future.db").as_posix(), KEY)
    try:
        store.migrate()
        with store.engine.begin() as conn:
            conn.execute(schema_versions.insert().values(version=4, applied_at=now()))
        with pytest.raises(ValueError, match="Database schema is newer"):
            store.migrate()
        with store.engine.connect() as conn:
            assert set(conn.execute(select(schema_versions.c.version)).scalars()) == {1, 2, 3, 4}
    finally:
        store.engine.dispose()
