"""Software-only publisher contract tests; no GitHub or credential access."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import publish_candidate as publisher


def context():
    return {"version": "0.3.0-rc.1", "tag": "v0.3.0-rc.1", "sha": "a" * 40, "repository": publisher.REPOSITORY, "run_id": "17"}


def test_default_entrypoint_does_not_call_github_or_publish(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    monkeypatch.setattr(publisher, "validate_context", lambda *args: context())
    monkeypatch.setattr(publisher.subprocess, "run", lambda arguments, **kwargs: SimpleNamespace(stdout="a" * 40 if arguments[1] == "rev-parse" else ""))
    def forbidden(*args, **kwargs):
        pytest.fail("Default invocation must not call the publication client")
    monkeypatch.setattr(publisher, "gh", forbidden)
    monkeypatch.setattr(sys, "argv", ["publish_candidate.py"])
    publisher.main()
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "Prepared" and result["publication_performed"] is False


def client_for(assets, calls, *, corrupt=False):
    def client(arguments, **kwargs):
        calls.append(arguments)
        if "matching-refs" in " ".join(arguments): return "[]"
        if arguments[0] == "api" and arguments[1].endswith("/releases"): return "[[]]"
        if arguments[:2] == ["release", "download"]:
            target = Path(arguments[arguments.index("--dir") + 1]); target.mkdir()
            for source in assets:
                (target / source.name).write_bytes(b"changed" if corrupt else source.read_bytes())
        return "{}"
    return client


def test_exclusive_tag_then_draft_and_verified_assets_precede_publication(tmp_path, monkeypatch):
    asset = tmp_path / "isolated-software-verification.txt"; asset.write_text("Software fixture only")
    calls = []
    monkeypatch.setattr(publisher, "gh", client_for([asset], calls))
    result = publisher.publish(tmp_path, context(), [asset], release_body="Isolated software publication contract test")
    assert result["state"] == "Published"
    mutations = [command for command in calls if command[:2] in (["api", "--method"], ["release", "create"], ["release", "edit"])]
    assert mutations[0][:3] == ["api", "--method", "POST"]
    assert "sha=" + context()["sha"] in mutations[0]
    create = mutations[1]
    assert "--draft" in create and "--prerelease" in create and "--verify-tag" in create
    assert create[create.index("--target") + 1] == context()["sha"]
    assert mutations[-1][:2] == ["release", "edit"] and "--draft=false" in mutations[-1]
    assert not any("delete" in command for command in calls)


def test_changed_uploaded_asset_retains_draft_and_never_publishes(tmp_path, monkeypatch):
    asset = tmp_path / "isolated-verification.txt"; asset.write_text("Software fixture only")
    calls = []
    monkeypatch.setattr(publisher, "gh", client_for([asset], calls, corrupt=True))
    with pytest.raises(ValueError, match="draft assets differ"):
        publisher.publish(tmp_path, context(), [asset], release_body="Isolated software publication contract test")
    assert not any(command[:2] == ["release", "edit"] for command in calls)
    assert not any("delete" in command for command in calls)


def test_workflow_scopes_write_permission_and_exact_source_checkout():
    value = (ROOT / ".github/workflows/engineering.yml").read_text()
    engineering, publish = value.split("  publish-candidate:", 1)
    assert "contents: write" not in engineering
    assert "needs: containers-postgresql" in publish
    assert "github.event_name == 'push'" in publish and "github.repository == 'michelegiletto-beep/airspace-operations'" in publish
    assert "ref: ${{ github.sha }}" in publish and "persist-credentials: false" in publish
    assert "actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38" in publish and "node-version: '22'" in publish
    assert publish.index("scripts/verify_release.py") < publish.index("scripts/package_release.py") < publish.index("scripts/verify_archive.py") < publish.index("--publish")


def test_release_body_uses_reviewed_notes_actual_asset_digest_and_source_screenshot(tmp_path):
    notes = tmp_path / "publication/v0.3/release-notes.md"
    notes.parent.mkdir(parents=True); notes.write_text("Isolated software publication text from {{SOURCE_COMMIT}}.")
    image = tmp_path / "publication/media/v0.3/desktop-companion.jpg"
    image.parent.mkdir(parents=True); image.write_bytes(b"Isolated software test image bytes")
    evidence = tmp_path / "release-evidence/v0.3.0-rc.1"; evidence.mkdir(parents=True)
    (evidence / "release-gates.json").write_text(json.dumps({"checks": {"isolated_test": True}}))
    (evidence / "standalone-archive-verification.json").write_text(json.dumps({"test_suite": {"stdout": "9 passed, 3 skipped"}}))
    archive = tmp_path / "System-Lab-Airspace-Operations-0.3.0-rc.1.zip"
    archive.write_bytes(b"Isolated software test archive bytes")
    result = publisher.candidate_notes(tmp_path, context(), [archive])
    assert context()["sha"] in result and "{{SOURCE_COMMIT}}" not in result
    assert publisher.digest(archive) in result and str(archive.stat().st_size) in result
    assert "/" + context()["sha"] + "/publication/media/v0.3/desktop-companion.jpg" in result
    assert "9 passed, 3 skipped" in result and "remains partial" in result
