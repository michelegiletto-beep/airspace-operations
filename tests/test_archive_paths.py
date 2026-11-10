"""Archive verification path planning never touches operator runtime stores."""
import importlib.util
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from release_support import archive_workspace, isolated_archive_environment


def test_windows_default_ignores_long_project_and_uses_short_os_temp(tmp_path, monkeypatch):
    import tempfile
    short = Path(tempfile.gettempdir()).resolve()
    monkeypatch.setattr("release_support.tempfile.gettempdir", lambda: str(short))
    project = tmp_path / ("long-project-" * 20)
    try:
        destination, plan = archive_workspace(project, ["airspace-operations/file.txt"], platform="win32")
    except ValueError as error:
        # During archive verification TEMP already names its owned nested work
        # directory. A second Windows verification may legitimately need an
        # explicit shorter root; it must fail closed rather than fall back.
        assert "shorter --work-root" in str(error)
        assert not project.exists()
        return
    assert destination.parent == short
    assert plan["selection"] == "OS temporary directory"
    assert plan["maximum_utf16_units_including_terminator"] <= 260
    assert not (destination / "airspace.db").exists()


def test_long_windows_canonical_root_is_rejected_before_mkdtemp(tmp_path, monkeypatch):
    called = []
    base = tmp_path / ("long" * 20)
    base.mkdir()
    monkeypatch.setattr("release_support.tempfile.gettempdir", lambda: str(base))
    monkeypatch.setattr("release_support.tempfile.mkdtemp", lambda **kwargs: called.append(kwargs))
    with pytest.raises(ValueError, match="shorter --work-root"):
        archive_workspace(tmp_path, ["airspace-operations/" + "x" * 118], platform="win32")
    assert not called


@pytest.mark.parametrize("root", ["", "relative/root", "C:relative", r"\\server\share", r"\\?\C:\work"])
def test_unsafe_windows_explicit_root_is_rejected(tmp_path, root):
    with pytest.raises((ValueError, OSError)):
        archive_workspace(tmp_path, ["airspace-operations/file"], work_root=root, platform="win32")


def test_missing_or_file_root_is_rejected_without_creating_it(tmp_path):
    missing = tmp_path / "missing"
    file = tmp_path / "file"
    file.write_text("preserve")
    for root in [missing, file]:
        with pytest.raises((ValueError, OSError)):
            archive_workspace(tmp_path, ["airspace-operations/file"], work_root=str(root), platform="linux")
    assert not missing.exists()
    assert file.read_text() == "preserve"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", r"airspace-operations\escape", "airspace-operations/../escape"])
def test_unsafe_archive_member_is_rejected_before_workspace_creation(tmp_path, name):
    with pytest.raises(ValueError, match="Unsafe archive"):
        archive_workspace(tmp_path, [name], platform="linux")
    assert not (tmp_path / "runtime").exists()


def test_unix_default_preserves_project_runtime_layout(tmp_path):
    destination, plan = archive_workspace(tmp_path, ["airspace-operations/file"], platform="linux")
    assert destination.parent == tmp_path / "runtime/archive-verification"
    assert plan["selection"] == "project runtime"


def test_explicit_unix_root_is_used_without_silent_fallback(tmp_path):
    destination, plan = archive_workspace(tmp_path / "project", ["airspace-operations/file"], work_root=str(tmp_path), platform="linux")
    assert destination.parent == tmp_path
    assert plan["selection"] == "explicit"


def test_unsupported_platform_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        archive_workspace(tmp_path, [], platform="unsupported")


def test_reparse_root_is_rejected_before_creating_a_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "is_junction", lambda path: path == tmp_path, raising=False)
    with pytest.raises(ValueError, match="junctions"):
        archive_workspace(tmp_path, [], work_root=str(tmp_path), platform="linux")
    assert list(tmp_path.iterdir()) == []


def test_importing_verifier_does_not_extract_install_or_run_tests(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Import must not run a verifier or touch an operator database")
    monkeypatch.setattr("subprocess.run", forbidden)
    spec = importlib.util.spec_from_file_location("isolated_archive_module", ROOT / "scripts/verify_archive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)


def test_archive_environment_discards_all_operator_airspace_configuration(tmp_path):
    original = {"AIRSPACE_DATABASE_URL": "postgresql://operator.invalid/private", "AIRSPACE_AUDIT_KEY": "private-original-key",
                "AIRSPACE_TEST_POSTGRES_URL": "postgresql://operator.invalid/tests", "AIRSPACE_OIDC_ISSUER": "private",
                "AIRSPACE_CUSTOM_OPERATOR_SETTING": "private", "KEEP": "retained"}
    env = isolated_archive_environment(tmp_path, original)
    assert env["KEEP"] == "retained"
    assert "AIRSPACE_TEST_POSTGRES_URL" not in env and "AIRSPACE_CUSTOM_OPERATOR_SETTING" not in env
    assert "AIRSPACE_OIDC_ISSUER" not in env
    assert env["AIRSPACE_AUDIT_KEY"] != original["AIRSPACE_AUDIT_KEY"]
    assert env["AIRSPACE_DATABASE_URL"].startswith("sqlite:///")
    assert not tmp_path.joinpath("runtime").exists()


def test_main_runs_every_gate_in_the_selected_workspace_with_isolated_environment(tmp_path, monkeypatch):
    import hashlib
    import json
    from types import SimpleNamespace
    import zipfile
    spec = importlib.util.spec_from_file_location("archive_wiring", ROOT / "scripts/verify_archive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project_root = tmp_path / "source"
    (project_root / "scripts").mkdir(parents=True)
    (project_root / "release").mkdir()
    (project_root / "release-evidence/v0.3.7-rc.1").mkdir(parents=True)
    content = b'__version__ = "0.3.7-rc.1"\n'
    manifest = {"version": "0.3.7-rc.1", "files": {"backend/airspace/__init__.py": hashlib.sha256(content).hexdigest()}}
    with zipfile.ZipFile(project_root / "release/System-Lab-Airspace-Operations-0.3.7-rc.1.zip", "w") as archive:
        archive.writestr("airspace-operations/backend/airspace/__init__.py", content)
        archive.writestr("airspace-operations/RELEASE_PROVENANCE.json", json.dumps(manifest))
    owned = tmp_path / "selected-workspace"
    owned.mkdir()
    chosen = []
    def choose(root, members, *, work_root):
        chosen.append((root, members, work_root))
        return owned, {"destination": str(owned), "work_root": str(tmp_path)}
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="isolated stub success", stderr="")
    monkeypatch.setattr(module, "__file__", str(project_root / "scripts/verify_archive.py"))
    monkeypatch.setattr(module, "current_version", lambda root: "0.3.7-rc.1")
    monkeypatch.setattr(module, "archive_workspace", choose)
    monkeypatch.setattr(module.subprocess, "run", run)
    monkeypatch.setattr(sys, "argv", ["verify_archive.py", "--work-root", str(tmp_path)])
    monkeypatch.setenv("AIRSPACE_DATABASE_URL", "postgresql://operator.invalid/do-not-open")
    monkeypatch.setenv("AIRSPACE_AUDIT_KEY", "do-not-use-operator-key")
    module.main()
    assert chosen and chosen[0][2] == str(tmp_path)
    assert len(calls) == 4
    for command, options in calls:
        assert options["cwd"] == owned / "airspace-operations"
        assert options["env"]["AIRSPACE_DATABASE_URL"].startswith("sqlite:///")
        assert options["env"]["AIRSPACE_AUDIT_KEY"] != "do-not-use-operator-key"
        assert options["env"]["TEMP"] == str(owned / "t")
    assert calls[-1][0][-1] == "--basetemp=" + str(owned / "t/p")
    report = json.loads((project_root / "release-evidence/v0.3.7-rc.1/standalone-archive-verification.json").read_text())
    assert report["working_paths"]["destination"] == str(owned)
    assert report["success"] and report["source_manifest_files_verified"] == 1
