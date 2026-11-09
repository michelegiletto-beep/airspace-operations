"""Restore CLI checks use only disposable isolated database files."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from airspace.storage import Store


ROOT = Path(__file__).resolve().parents[1]


def restore(source, target, tmp_path):
    env = {key: value for key, value in os.environ.items() if not key.startswith("AIRSPACE_")}
    env.update(PYTHONPATH=str(ROOT / "backend"), AIRSPACE_RUNTIME=str(tmp_path / "must-not-create-runtime"))
    return subprocess.run([sys.executable, "-B", "-m", "airspace.cli", "restore", "--input", str(source),
                           "--target", str(target)], cwd=tmp_path, env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=30)


def test_missing_restore_input_does_not_create_source_or_target(tmp_path):
    source = tmp_path / "misspelled-backup.db"
    target = tmp_path / "new-restoration" / "airspace.db"
    result = restore(source, target, tmp_path)
    assert result.returncode != 0, result.stdout
    assert not source.exists(), "A missing backup must never become an empty SQLite source"
    assert not target.parent.exists(), "Invalid input must not create the target directory"
    assert not (tmp_path / "must-not-create-runtime").exists()


@pytest.mark.parametrize("kind", ["directory", "empty", "not_sqlite", "unrelated_sqlite"])
def test_invalid_restore_input_is_rejected_before_target_mutation(tmp_path, kind):
    source = tmp_path / "invalid-backup.db"
    if kind == "directory":
        source.mkdir()
    elif kind == "empty":
        source.touch()
    elif kind == "not_sqlite":
        source.write_bytes(b"This is not a database backup.")
    else:
        with sqlite3.connect(source) as connection:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
    before = source.read_bytes() if source.is_file() else None
    target = tmp_path / "new-restoration" / "airspace.db"
    result = restore(source, target, tmp_path)
    assert result.returncode != 0
    assert "restored" not in result.stdout
    assert not target.parent.exists()
    if before is not None:
        assert source.read_bytes() == before
    assert not (tmp_path / "must-not-create-runtime").exists()


def backup(environment, tmp_path):
    store = environment[0]
    source = tmp_path / "valid-backup.db"
    with store.engine.connect() as connection, sqlite3.connect(source) as destination:
        connection.connection.driver_connection.backup(destination)
    return source


@pytest.mark.parametrize("damage", ["missing_table", "missing_column", "future_version", "missing_versions", "foreign_key"])
def test_damaged_application_backup_is_rejected_before_target_mutation(environment, tmp_path, damage):
    source = backup(environment, tmp_path)
    with sqlite3.connect(source) as connection:
        if damage == "missing_table":
            connection.execute("DROP TABLE resource_locks")
        elif damage == "missing_column":
            connection.execute("ALTER TABLE resource_locks DROP COLUMN generation")
        elif damage == "future_version":
            connection.execute("INSERT INTO schema_versions VALUES (999, 'isolated-test')")
        elif damage == "missing_versions":
            connection.execute("DELETE FROM schema_versions")
        else:
            connection.execute("UPDATE users SET organisation_id='isolated-missing-tenant'")
    before = source.read_bytes()
    target = tmp_path / "new-restoration" / "airspace.db"
    result = restore(source, target, tmp_path)
    assert result.returncode != 0
    assert not target.parent.exists()
    assert source.read_bytes() == before


def test_valid_backup_restores_records_and_audit_without_changing_source(environment, tmp_path):
    source = backup(environment, tmp_path)
    before = source.read_bytes()
    target = tmp_path / "new-restoration" / "airspace.db"
    result = restore(source, target, tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["audit_key_required"] is True
    assert source.read_bytes() == before
    with sqlite3.connect(source) as original, sqlite3.connect(target) as restored:
        names = [row[0] for row in original.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for name in names:
            assert original.execute(f'SELECT * FROM "{name}"').fetchall() == restored.execute(f'SELECT * FROM "{name}"').fetchall()
        assert restored.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert restored.execute("PRAGMA foreign_key_check").fetchall() == []
    restored_store = Store(f"sqlite:///{target.as_posix()}", environment[0].key)
    try:
        for actor in environment[2:5]:
            assert restored_store.verify_audit(actor["organisation_id"]) == environment[0].verify_audit(actor["organisation_id"])
    finally:
        restored_store.engine.dispose()
    assert not (tmp_path / "must-not-create-runtime").exists()


@pytest.mark.parametrize("same_path", [False, True])
def test_existing_or_same_target_is_never_overwritten(environment, tmp_path, same_path):
    source = backup(environment, tmp_path)
    target = source if same_path else tmp_path / "existing-target.db"
    if not same_path:
        target.write_bytes(b"Existing operator file must remain exact.")
    before_source, before_target = source.read_bytes(), target.read_bytes()
    result = restore(source, target, tmp_path)
    assert result.returncode != 0
    assert source.read_bytes() == before_source
    assert target.read_bytes() == before_target


@pytest.mark.parametrize("replacement", [False, True])
def test_failed_copy_removes_only_its_own_target(environment, tmp_path, monkeypatch, replacement):
    from airspace import cli
    source = backup(environment, tmp_path)
    before = source.read_bytes()
    target = tmp_path / "restoration.db"
    other = tmp_path / "other-writer.db"
    other.write_bytes(b"Another writer's file must survive.")
    connect = sqlite3.connect
    copied = []

    class InterruptedSource:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def backup(self, destination):
            copied.append(True)
            raise sqlite3.OperationalError("Isolated copy interruption")

    def interrupted_connect(*args, **kwargs):
        # Replace before SQLite opens the claimed path: Windows correctly
        # refuses replacing a destination that SQLite already has open.
        if replacement and not kwargs.get("uri"):
            target.unlink()
            other.replace(target)
        connection = connect(*args, **kwargs)
        return InterruptedSource(connection) if kwargs.get("uri") else connection

    monkeypatch.setattr(cli.sqlite3, "connect", interrupted_connect)
    monkeypatch.setattr(sys, "argv", ["airspace", "restore", "--input", str(source), "--target", str(target)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code != 0
    assert source.read_bytes() == before
    if replacement:
        assert not copied, "The replaced target must be rejected before copying"
        assert target.read_bytes() == b"Another writer's file must survive."
    else:
        assert copied
        assert not target.exists()
