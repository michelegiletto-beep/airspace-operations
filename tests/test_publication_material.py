"""Isolated release-copy selection checks; no network or publication client."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_candidate as publisher

VERSION = "0.3.1-rc.1"


@pytest.fixture
def candidate(tmp_path):
    notes = tmp_path / f"publication/releases/{VERSION}/notes.md"
    notes.parent.mkdir(parents=True)
    notes.write_text(f"# Release {VERSION}\n\nIsolated software fixture from {{{{SOURCE_COMMIT}}}}.\n")
    image = tmp_path / f"publication/media/{VERSION}/companion.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"Isolated raster fixture, never operational evidence")
    manifest = notes.with_name("manifest.json")
    data = {"version": VERSION, "notes_path": notes.relative_to(tmp_path).as_posix(), "screenshot_path": image.relative_to(tmp_path).as_posix()}
    manifest.write_text(json.dumps(data))
    context = {"version": VERSION, "sha": "a" * 40}
    evidence = tmp_path / f"release-evidence/v{VERSION}"
    evidence.mkdir(parents=True)
    (evidence / "release-gates.json").write_text(json.dumps({"checks": {"isolated_test": True}}))
    (evidence / "standalone-archive-verification.json").write_text(json.dumps({"test_suite": {"stdout": "7 passed, 2 skipped"}}))
    archive = tmp_path / f"System-Lab-Airspace-Operations-{VERSION}.zip"
    archive.write_bytes(b"Isolated archive fixture")
    return tmp_path, notes, image, manifest, data, context, archive


def test_selected_current_material_and_real_asset_identity_are_used(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    result = publisher.candidate_notes(root, context, [archive])
    assert "/" + context["sha"] + "/" + data["screenshot_path"] in result
    assert "publication/media/v0.3/desktop-companion.jpg" not in result
    assert "{{SOURCE_COMMIT}}" not in result and context["sha"] in result
    assert publisher.digest(archive) in result and "7 passed, 2 skipped" in result
    assert "/releases/tag/v0.3.0-rc.1" in result
    assert "stable release and operational acceptance remain false" in result


def test_missing_manifest_never_falls_back_to_previous_release(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    manifest.unlink()
    old_notes = root / "publication/v0.3/release-notes.md"
    old_notes.parent.mkdir(parents=True)
    old_notes.write_text("# Release 0.3.0-rc.1\nOld reviewed release notes")
    old_image = root / "publication/media/v0.3/desktop-companion.jpg"
    old_image.parent.mkdir(parents=True)
    old_image.write_bytes(b"Isolated old test image")
    with pytest.raises(ValueError, match="manifest"):
        publisher.candidate_notes(root, context, [archive])


@pytest.mark.parametrize("change", [
    {"version": "0.3.0-rc.1"}, {"unexpected": "permitted"}, {"notes_path": None},
    {"screenshot_path": True}, {"notes_path": "publication/v0.3/release-notes.md"},
    {"notes_path": f"publication/releases/{VERSION}/nested/notes.md"},
    {"notes_path": f"publication/releases/{VERSION}/notes.txt"},
    {"screenshot_path": "runtime/private.png"},
    {"screenshot_path": "https://example.invalid/screenshot.png"},
    {"screenshot_path": "/publication/media/current.png"},
    {"screenshot_path": "publication/media/../current.png"},
    {"screenshot_path": "publication/media//current.png"},
    {"screenshot_path": "publication/media/./current.png"},
    {"screenshot_path": "publication\\media\\current.png"},
    {"screenshot_path": "publication/media/current.png?token=value"},
    {"screenshot_path": "publication/media/current image.png"},
    {"screenshot_path": "publication/media/current.svg"},
    {"screenshot_path": "publication/media/node_modules/current.png"},
    {"screenshot_path": "publication/media/generated.egg-info/current.png"},
])
def test_unsafe_mismatched_or_unpackaged_selection_is_rejected(candidate, change):
    root, notes, image, manifest, data, context, archive = candidate
    manifest.write_text(json.dumps(data | change))
    with pytest.raises(ValueError):
        publisher.candidate_notes(root, context, [archive])


@pytest.mark.parametrize("body", ["# Release 0.3.0-rc.1\nCurrent version0.3.1-rc.1 is mentioned only in prose", "# Release 0.3.1-rc.10", "Isolated prose mentions0.3.1-rc.1", "# Release 0.3.1-rc.1 extra"])
def test_matching_manifest_cannot_select_stale_or_ambiguous_release_notes(candidate, body):
    root, notes, image, manifest, data, context, archive = candidate
    notes.write_text(body)
    with pytest.raises(ValueError, match="exact candidate version"):
        publisher.candidate_notes(root, context, [archive])


@pytest.mark.parametrize("value", [[], None, "manifest", {"version": VERSION}, {"version": VERSION, "notes_path": "notes.md"}])
def test_manifest_must_be_exact_object_schema(candidate, value):
    root, notes, image, manifest, data, context, archive = candidate
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        publisher.candidate_notes(root, context, [archive])


def test_duplicate_keys_and_oversized_manifest_fail_closed(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    content = json.dumps(data)
    manifest.write_text(content[:-1] + ', "version": "' + VERSION + '"}')
    with pytest.raises(ValueError, match="Duplicate"):
        publisher.candidate_notes(root, context, [archive])
    manifest.write_text(" " * 16_385)
    with pytest.raises(ValueError, match="bounded"):
        publisher.candidate_notes(root, context, [archive])


@pytest.mark.parametrize("missing", ["notes", "image"])
def test_missing_selected_file_is_not_replaced_with_old_file(candidate, missing):
    root, notes, image, manifest, data, context, archive = candidate
    (notes if missing == "notes" else image).unlink()
    with pytest.raises(ValueError, match="required"):
        publisher.candidate_notes(root, context, [archive])


def test_explicit_review_can_reuse_existing_public_media(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    old = root / "publication/media/v0.3/desktop-companion.jpg"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"Isolated reviewed media reuse fixture")
    data["screenshot_path"] = old.relative_to(root).as_posix()
    manifest.write_text(json.dumps(data))
    result = publisher.candidate_notes(root, context, [archive])
    assert "/" + context["sha"] + "/publication/media/v0.3/desktop-companion.jpg" in result


def test_selected_symlink_cannot_escape_reviewed_source(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    outside = root / "outside.txt"
    outside.write_text("Isolated nonpublic fixture")
    image.unlink()
    try:
        image.symlink_to(outside)
    except OSError:
        pytest.skip("This host cannot create symlinks; containment cases remain tested")
    with pytest.raises(ValueError, match="Symlinks"):
        publisher.candidate_notes(root, context, [archive])
