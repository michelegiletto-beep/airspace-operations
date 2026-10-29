"""Isolated negative publication tests. No token, network or real release is used."""
import json
import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_candidate as publisher


@pytest.fixture
def context_fixture(tmp_path):
    source = tmp_path / "backend/airspace/__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text('__version__ = "0.3.0-rc.1"\n')
    sha = "a" * 40
    environment = {
        "CI": "true", "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
        "GITHUB_REPOSITORY": publisher.REPOSITORY, "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_API_URL": "https://api.github.com", "GITHUB_REF": "refs/heads/release/0.3.0-rc.1",
        "GITHUB_SHA": sha, "GITHUB_RUN_ID": "17", "AIRSPACE_ENGINEERING_RESULT": "success",
    }
    return tmp_path, environment, sha


@pytest.mark.parametrize("field,value", [
    ("CI", "false"), ("GITHUB_ACTIONS", "false"),
    ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_EVENT_NAME", "pull_request_target"),
    ("GITHUB_EVENT_NAME", "workflow_dispatch"),
    ("GITHUB_REPOSITORY", "other-owner/airspace-operations"),
    ("GITHUB_SERVER_URL", "https://github.com.example.invalid"),
    ("GITHUB_API_URL", "https://api.example.invalid"), ("GH_HOST", "example.invalid"),
    ("GITHUB_REF", "refs/heads/main"), ("GITHUB_REF", "refs/heads/release/0.3.0-rc.1/extra"),
    ("GITHUB_SHA", "b" * 40), ("GITHUB_SHA", "not-a-commit"),
    ("GITHUB_RUN_ID", ""), ("GITHUB_RUN_ID", "not-a-run"),
    ("AIRSPACE_ENGINEERING_RESULT", "failure"), ("AIRSPACE_ENGINEERING_RESULT", "skipped"),
])
def test_untrusted_or_wrong_publication_context_is_rejected(context_fixture, field, value):
    root, environment, sha = context_fixture
    environment[field] = value
    with pytest.raises(ValueError):
        publisher.validate_context(root, environment, sha)


def test_stable_version_cannot_enter_candidate_publisher(context_fixture):
    root, environment, sha = context_fixture
    (root / "backend/airspace/__init__.py").write_text('__version__ = "0.3.0"\n')
    environment["GITHUB_REF"] = "refs/heads/release/0.3.0"
    with pytest.raises(ValueError, match="candidate"):
        publisher.validate_context(root, environment, sha)


def test_local_published_version_is_frozen_even_if_remote_tag_is_missing(context_fixture):
    root, environment, sha = context_fixture
    (root / "publication").mkdir()
    (root / "publication/status.json").write_text(json.dumps({
        "release": "0.3.0-rc.1", "states_reached": ["Independently Retrieved"]}))
    with pytest.raises(SystemExit, match="frozen"):
        publisher.validate_context(root, environment, sha)


@pytest.mark.parametrize("relative", [
    "../outside", "/outside", "runtime/audit.key", "frontend/.env.local",
    "frontend/.env.production", "frontend/private.key", "frontend/operator.sqlite3",
    "sources/local-research/original.json", "sources/snapshots/original.json",
    "frontend/private/credential.json", "frontend/secrets/credential.json", "frontend\\secret.txt",
])
def test_private_or_escaping_asset_paths_are_rejected(tmp_path, relative):
    with pytest.raises(ValueError):
        publisher.safe_path(tmp_path, relative)


@pytest.mark.parametrize("existing", ["tag", "release"])
def test_existing_publication_prevents_any_mutation(context_fixture, monkeypatch, existing):
    root, environment, sha = context_fixture
    context = publisher.validate_context(root, environment, sha)
    calls = []
    def fake(arguments, **kwargs):
        calls.append(arguments)
        if "matching-refs" in " ".join(arguments):
            return json.dumps([{"ref": "refs/tags/" + context["tag"]}] if existing == "tag" else [])
        if arguments[:1] == ["api"] and "--slurp" in arguments:
            return json.dumps([[{"tag_name": context["tag"]}]] if existing == "release" else [[]])
        raise AssertionError("An existing release must prevent all mutating commands")
    monkeypatch.setattr(publisher, "gh", fake)
    with pytest.raises(ValueError, match="frozen"):
        publisher.publish(root, context, [], release_body="Isolated software fixture")
    assert len(calls) == 2


def test_new_tag_race_does_not_retry_or_create_release(context_fixture, monkeypatch):
    root, environment, sha = context_fixture
    context = publisher.validate_context(root, environment, sha)
    calls = []
    def fake(arguments, **kwargs):
        calls.append(arguments)
        if "matching-refs" in " ".join(arguments): return "[]"
        if "--slurp" in arguments: return "[[]]"
        if "POST" in arguments:
            raise RuntimeError("Isolated concurrent create-ref conflict")
        raise AssertionError("A failed exclusive tag creation must stop publication")
    monkeypatch.setattr(publisher, "gh", fake)
    with pytest.raises(RuntimeError, match="create-ref"):
        publisher.publish(root, context, [], release_body="Isolated software fixture")
    assert sum("POST" in arguments for arguments in calls) == 1
    assert not any(arguments[:1] == ["release"] for arguments in calls)


def test_mismatching_draft_download_is_retained_and_never_published(context_fixture, monkeypatch):
    root, environment, sha = context_fixture
    context = publisher.validate_context(root, environment, sha)
    asset = root / "isolated-candidate.zip"
    asset.write_bytes(b"isolated public software fixture")
    calls = []
    def fake(arguments, **kwargs):
        calls.append(arguments)
        if "matching-refs" in " ".join(arguments): return "[]"
        if "--slurp" in arguments: return "[[]]"
        if "POST" in arguments: return "{}"
        if arguments[:2] == ["release", "create"]:
            assert "--draft" in arguments and "--prerelease" in arguments and "--verify-tag" in arguments
            assert arguments[arguments.index("--target") + 1] == sha
            return ""
        if arguments[:2] == ["release", "download"]:
            directory = Path(arguments[arguments.index("--dir") + 1])
            directory.mkdir()
            (directory / asset.name).write_bytes(b"isolated changed download")
            return ""
        raise AssertionError("Mismatching draft assets must prevent publication and deletion")
    monkeypatch.setattr(publisher, "gh", fake)
    with pytest.raises(ValueError, match="differ"):
        publisher.publish(root, context, [asset], release_body="Isolated software fixture")
    assert not any(arguments[:2] == ["release", "edit"] for arguments in calls)
    assert not any("delete" in arguments for arguments in calls)


def proof_fixture(root, context):
    """Minimum pre-archive proof inputs, used only for rejection ordering."""
    evidence = root / "release-evidence" / ("v" + context["version"])
    evidence.mkdir(parents=True)
    (root / "release").mkdir()
    gate = {"version": context["version"], "engineering_checks_passed": True,
            "stable_release_allowed": False, "operational_acceptance": False,
            "external_ci": {"verified": True},
            "checks": {name: True for name in publisher.REQUIRED_CHECKS}}
    source = "backend/airspace/__init__.py"
    checksum = hashlib.sha256((root / source).read_bytes()).hexdigest()
    provenance = {"version": context["version"], "source_commit": context["sha"],
                  "baseline_sha256": publisher.BASELINE, "files": {source: checksum}, "gates": gate}
    ci = {"conclusion": "success", "commit": context["sha"], "run_id": context.get("run_id"),
          "local_software_input_hashes": {source: checksum}}
    (evidence / "release-gates.json").write_text(json.dumps(gate))
    (root / "release/RELEASE_PROVENANCE.json").write_text(json.dumps(provenance))
    (evidence / "ci-verification.json").write_text(json.dumps(ci))
    return evidence, gate, provenance, ci


def test_missing_container_evidence_cannot_reach_archive_validation(context_fixture):
    root, environment, sha = context_fixture
    environment["GITHUB_RUN_ID"] = "17"
    context = publisher.validate_context(root, environment, sha)
    evidence, gate, _, _ = proof_fixture(root, context)
    gate["external_ci"]["verified"] = False
    (evidence / "release-gates.json").write_text(json.dumps(gate))
    with pytest.raises(ValueError, match="gates"):
        publisher.validate_artifacts(root, context)


@pytest.mark.parametrize("field,value", [("commit", "b" * 40), ("run_id", "18"), ("conclusion", "failure")])
def test_stale_or_failed_engineering_evidence_is_rejected_before_archive(context_fixture, field, value):
    root, environment, sha = context_fixture
    environment["GITHUB_RUN_ID"] = "17"
    context = publisher.validate_context(root, environment, sha)
    evidence, _, _, ci = proof_fixture(root, context)
    ci[field] = value
    (evidence / "ci-verification.json").write_text(json.dumps(ci))
    with pytest.raises(ValueError, match="current-run CI"):
        publisher.validate_artifacts(root, context)


@pytest.mark.parametrize("change", ["working_source", "package_manifest"])
def test_source_drift_after_engineering_check_is_rejected(context_fixture, change):
    root, environment, sha = context_fixture
    environment["GITHUB_RUN_ID"] = "17"
    context = publisher.validate_context(root, environment, sha)
    _, _, provenance, _ = proof_fixture(root, context)
    source = "backend/airspace/__init__.py"
    if change == "working_source":
        (root / source).write_text('# Isolated modified source\n__version__ = "0.3.0-rc.1"\n')
    else:
        provenance["files"][source] = "f" * 64
        (root / "release/RELEASE_PROVENANCE.json").write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="Controlled source"):
        publisher.validate_artifacts(root, context)
