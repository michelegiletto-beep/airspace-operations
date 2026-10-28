"""Release-tool isolation checks using artificial files in temporary directories."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from release_support import (assert_release_writable, current_version,
                             github_payload_directory, isolated_archive_environment,
                             public_improvement_files)


def write_version(root, version="0.3.0-rc.1"):
    source = root / "backend/airspace/__init__.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('__version__ = "' + version + '"\n', encoding="utf-8")


def receipt(root, path, version, states):
    target = root / "publication" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"release": version, "states_reached": states}), encoding="utf-8")


@pytest.mark.parametrize("location", ["status.json", "history/0.2.0-rc.1.json", "v0.2/status.json"])
def test_published_version_is_protected_across_publication_ledgers(tmp_path, location):
    receipt(tmp_path, "status.json", "0.3.0-rc.1", ["Prepared"])
    receipt(tmp_path, location, "0.2.0-rc.1", ["Prepared", "Published", "Independently Retrieved"])
    with pytest.raises(SystemExit, match="frozen"):
        assert_release_writable(tmp_path, "0.2.0-rc.1")
    assert_release_writable(tmp_path, "0.3.0-rc.1")


def test_freeze_refusal_happens_before_metadata_or_archive_writes(tmp_path, monkeypatch):
    import package_release
    receipt(tmp_path, "history/0.2.0-rc.1.json", "0.2.0-rc.1", ["Published"])
    sentinel = tmp_path / "SBOM.cdx.json"
    sentinel.write_text("isolated frozen metadata", encoding="utf-8")
    monkeypatch.setattr(package_release, "ROOT", tmp_path)
    monkeypatch.setattr(package_release, "VERSION", "0.2.0-rc.1")
    monkeypatch.setattr(package_release, "build_metadata", lambda: sentinel.write_text("incorrect overwrite", encoding="utf-8"))
    with pytest.raises(SystemExit, match="frozen"):
        package_release.main()
    assert sentinel.read_text(encoding="utf-8") == "isolated frozen metadata"
    assert not (tmp_path / "release").exists()


@pytest.mark.parametrize("version", ["0.3.0-rc.1", "1.0.0"])
def test_version_is_read_from_actual_project_identity(tmp_path, version):
    write_version(tmp_path, version)
    assert current_version(tmp_path) == version


def test_version_cannot_be_a_filesystem_path(tmp_path):
    write_version(tmp_path, "../another-release")
    with pytest.raises(ValueError, match="explicit release version"):
        current_version(tmp_path)


def test_standalone_checks_cannot_inherit_external_database_or_identity(tmp_path):
    inherited = {"PATH": "isolated-test-bin", "AIRSPACE_DATABASE_URL": "postgresql+psycopg://test-role:isolated-fixture@database.invalid/test-only",
                 "AIRSPACE_TEST_POSTGRES_URL": "postgresql+psycopg://database.invalid/test-only",
                 "AIRSPACE_AUDIT_KEY": "isolated-parent-fixture-key", "AIRSPACE_OIDC_ISSUER": "https://identity.invalid",
                 "AIRSPACE_OIDC_SUBJECTS": "isolated-parent-mapping", "AIRSPACE_REQUIRE_TWO_REVIEWERS": "true",
                 "AIRSPACE_MODEL_DIR": "outside-model-fixture", "AIRSPACE_INITIAL_PASSWORD": "isolated-parent-password"}
    result = isolated_archive_environment(tmp_path, inherited)
    assert result["AIRSPACE_DATABASE_URL"] == "sqlite:///" + (tmp_path / "runtime/isolated-release-check/airspace.db").as_posix()
    assert "AIRSPACE_TEST_POSTGRES_URL" not in result
    assert not any(key.startswith("AIRSPACE_OIDC_") for key in result)
    assert "AIRSPACE_MODEL_DIR" not in result and "AIRSPACE_INITIAL_PASSWORD" not in result
    assert result["AIRSPACE_AUDIT_KEY"] != inherited["AIRSPACE_AUDIT_KEY"]
    assert result["AIRSPACE_REQUIRE_TWO_REVIEWERS"] == "false"
    assert result["PATH"] == inherited["PATH"]
    assert inherited["AIRSPACE_DATABASE_URL"].startswith("postgresql")


def test_payload_directories_separate_versions_with_explicit_legacy_compatibility(tmp_path):
    first = github_payload_directory(tmp_path, "0.2.0-rc.1")
    second = github_payload_directory(tmp_path, "0.3.0-rc.1")
    assert first != second
    assert second == tmp_path / "runtime/publication/github/v0.3.0-rc.1"
    assert github_payload_directory(tmp_path, "0.3.0-rc.1", legacy=True) == tmp_path / "runtime/publication/github"


def load_payload_script():
    spec = importlib.util.spec_from_file_location("isolated_github_payload", ROOT / "publication/prepare-github-payload.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prepared_inventory_names_exact_version_and_batch_files(tmp_path, monkeypatch):
    import gzip
    write_version(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("Isolated release preparation fixture\n", encoding="utf-8")
    corpus = tmp_path / "corpus.json"
    corpus.write_text("[]", encoding="utf-8")
    module = load_payload_script()
    monkeypatch.setattr(module, "source_files", lambda: iter([(readme, Path("README.md")), (corpus, Path("sources/corpus.json"))]))
    inventory = module.prepare_payload(tmp_path)
    assert inventory["version"] == "0.3.0-rc.1" and inventory["state"] == "Prepared"
    assert inventory["publication_performed"] is False
    assert inventory["batches"] == inventory["small_batches"] == len(inventory["batch_paths"]) == 1
    assert all(Path(path).is_file() for path in inventory["batch_paths"])
    assert Path(inventory["inventory_path"]).is_file() and Path(inventory["large_path"]).is_file()
    compressed = Path(inventory["output_directory"]) / "corpus.json.gz"
    assert json.loads(gzip.decompress(compressed.read_bytes())) == []
    old = github_payload_directory(tmp_path, "0.2.0-rc.1")
    assert not old.exists()


def test_improvement_release_is_explicitly_reviewed_not_all_future_cycles(tmp_path, monkeypatch):
    import package_release
    folder = tmp_path / "improvement"
    (folder / "cycles").mkdir(parents=True)
    (folder / "publication-manifest.json").write_text(json.dumps({"public_files": ["RECURRING_PROMPT.md", "cycles/reviewed.json"]}), encoding="utf-8")
    for relative in ("RECURRING_PROMPT.md", "cycles/reviewed.json", "cycles/unreviewed.json", "private.key"):
        (folder / relative).write_text("Isolated publication-selection fixture", encoding="utf-8")
    monkeypatch.setattr(package_release, "ROOT", tmp_path)
    selected = {relative.as_posix() for _, relative in package_release.source_files()}
    assert selected == {"improvement/publication-manifest.json", "improvement/RECURRING_PROMPT.md", "improvement/cycles/reviewed.json"}


@pytest.mark.parametrize("entry", ["../outside.json", "keys/private.json", "private/key.json", "cycle.key"])
def test_improvement_manifest_cannot_release_unsafe_or_private_paths(tmp_path, entry):
    folder = tmp_path / "improvement"
    folder.mkdir()
    (folder / "publication-manifest.json").write_text(json.dumps({"public_files": [entry]}), encoding="utf-8")
    with pytest.raises(ValueError, match="private or unsafe"):
        public_improvement_files(tmp_path)


def test_missing_reviewed_improvement_file_blocks_incomplete_release(tmp_path):
    folder = tmp_path / "improvement"
    folder.mkdir()
    (folder / "publication-manifest.json").write_text(json.dumps({"public_files": ["missing-cycle.json"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="file is missing"):
        public_improvement_files(tmp_path)
