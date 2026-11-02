"""Isolated environment diagnostics, without real configuration or operational writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from airspace import environment_checks as checks


@pytest.mark.parametrize("value,kind,expected", [(1, 4, True), (0, 4, False), (2, 4, None), (True, 4, None), ("1", 4, None), (1, 1, None)])
def test_registry_reader_is_read_only_and_requires_a_valid_dword(monkeypatch, value, kind, expected):
    calls = []
    class Key:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            calls.append("closed")
    key = Key()
    def open_key(*args):
        calls.append(args)
        return key
    fake = SimpleNamespace(HKEY_LOCAL_MACHINE="isolated-machine-key", KEY_READ=0x20019, REG_DWORD=4,
                           OpenKey=open_key, QueryValueEx=lambda actual, name: (value, kind) if actual is key and name == "LongPathsEnabled" else pytest.fail("Unexpected registry query"))
    monkeypatch.setitem(sys.modules, "winreg", fake)
    assert checks._read_windows_long_paths() is expected
    assert calls == [("isolated-machine-key", checks.REGISTRY_KEY, 0, fake.KEY_READ), "closed"]


@pytest.mark.parametrize("enabled,status", [(True, "Enabled"), (False, "Disabled"), (None, "Unknown")])
def test_configuration_is_reported_without_claiming_io_or_process_support(tmp_path, monkeypatch, enabled, status):
    monkeypatch.setattr(checks, "_read_windows_long_paths", lambda: enabled)
    runtime = tmp_path / "never-created"
    report = checks.storage_path_diagnostics(runtime, platform="win32")
    assert report["windows_long_paths"]["registry_enabled"] is enabled
    assert report["windows_long_paths"]["registry_status"] == status
    assert report["configuration_only"] and not report["io_verified"]
    assert "process manifest" in report["windows_long_paths"]["registry_scope"]
    assert "not a complete storage budget" in report["scope"]
    assert not runtime.exists()


def test_denied_registry_read_remains_unknown_without_changing_permissions(tmp_path, monkeypatch):
    def denied():
        raise PermissionError("Isolated registry read denial")
    monkeypatch.setattr(checks, "_read_windows_long_paths", denied)
    report = checks.storage_path_diagnostics(tmp_path, platform="win32")
    assert report["windows_long_paths"]["registry_enabled"] is None
    assert report["windows_long_paths"]["registry_status"] == "Unknown"


def test_nonwindows_report_does_not_access_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(checks, "_read_windows_long_paths", lambda: pytest.fail("Registry must not be accessed"))
    report = checks.storage_path_diagnostics(tmp_path, platform="linux")
    assert not report["windows_long_paths"]["applicable"]
    assert report["windows_long_paths"]["registry_status"] == "Not Applicable"
    assert report["assessment"] == "Not Applicable"


def test_layout_budget_matches_independently_constructed_windows_paths(tmp_path, monkeypatch):
    from pathlib import PureWindowsPath
    monkeypatch.setattr(checks, "_read_windows_long_paths", lambda: False)
    root = str((tmp_path / "isolated-private-runtime").resolve())
    report = checks.storage_path_diagnostics(root, platform="win32")
    examples = {row["name"]: row for row in report["representative_layouts"]}
    blob = str(PureWindowsPath(root) / "objects" / ("t" * 36) / ("a" * 64))
    source = str(PureWindowsPath(root) / "sources" / ("t" * 36) / ("s" * 100) / ("b" * 64) / ("original.bin.tmp-" + "c" * 16))
    assert examples["evidence_blob"]["total_characters"] == len(blob.encode("utf-16-le")) // 2
    assert examples["source_snapshot_temporary_file"]["total_characters"] == len(source.encode("utf-16-le")) // 2
    assert examples["evidence_blob"]["additional_characters"] == 110
    assert examples["source_snapshot_temporary_file"]["additional_characters"] == 245
    assert report["legacy_limit_characters_including_terminator"] == 260


def test_non_bmp_runtime_characters_use_windows_utf16_units(tmp_path, monkeypatch):
    monkeypatch.setattr(checks, "_read_windows_long_paths", lambda: False)
    root = str((tmp_path / "isolated-\U0001f680").resolve())
    report = checks.storage_path_diagnostics(root, platform="win32")
    assert report["runtime_characters"] == len(root) + 1
    assert report["length_unit"] == "UTF-16 code units (Windows characters)"


def test_long_layout_is_actionable_but_never_claims_success_or_rejects_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(checks, "_read_windows_long_paths", lambda: False)
    runtime = tmp_path / ("deep" * 35)
    report = checks.storage_path_diagnostics(runtime, platform="win32")
    assert any(row["legacy_limit_reached"] for row in report["representative_layouts"])
    assert report["assessment"] == "Representative layout reaches the legacy Windows path limit"
    assert "shorter private AIRSPACE_RUNTIME" in report["guidance"]
    assert "audit key" in report["guidance"] and not report["io_verified"]
    assert not runtime.exists()


def test_actual_cli_check_retains_existing_keys_without_creating_a_runtime(tmp_path):
    root = Path(__file__).resolve().parents[1]
    runtime = tmp_path / "check-must-not-create"
    env = os.environ.copy()
    env.update(PYTHONPATH=str(root / "backend"), AIRSPACE_RUNTIME=str(runtime),
               AIRSPACE_DATABASE_URL="sqlite:///" + str(runtime / "isolated.db"))
    result = subprocess.run([sys.executable, "-m", "airspace.cli", "check"], cwd=tmp_path, env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert {"python", "database_profile", "schema_version", "docker", "pg_dump", "runtime", "operational_acceptance"}.issubset(report)
    assert report["database_profile"] == "SQLite portability"
    assert report["schema_version"] == 3 and report["operational_acceptance"] is False
    assert report["schema_status"] == "Not Inspected"
    assert report["schema_version_scope"] == "Supported schema; existing database not inspected or migrated"
    assert report["runtime"] == str(runtime.resolve())
    assert report["storage_paths"]["configuration_only"] is True
    assert report["storage_paths"]["io_verified"] is False
    assert not runtime.exists()
