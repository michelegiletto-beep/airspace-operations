"""Isolated release-copy selection checks; no network or publication client."""
import base64
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_candidate as publisher

VERSION = "0.3.2-rc.1"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOUMvZlYGBgYgADAAcvAJ6LDLezAAAAAElFTkSuQmCC")
JPEG = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAB//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AMn//2Q==")


@pytest.fixture
def candidate(tmp_path):
    notes = tmp_path / f"publication/releases/{VERSION}/notes.md"
    notes.parent.mkdir(parents=True)
    notes.write_text(f"# Release {VERSION}\n\nIsolated software fixture from {{{{SOURCE_COMMIT}}}}.\n")
    image = tmp_path / f"publication/media/{VERSION}/companion.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(PNG)
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
    assert "/releases/tag/v0.3.1-rc.1" in result
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


@pytest.mark.parametrize("body", ["# Release 0.3.0-rc.1\nCurrent version0.3.2-rc.1 is mentioned only in prose", "# Release 0.3.2-rc.10", "Isolated prose mentions0.3.2-rc.1", "# Release 0.3.2-rc.1 extra"])
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
    old.write_bytes(JPEG)
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


def test_unselected_mobile_capture_cannot_hide_wrong_encoding(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    mobile = image.with_name("mobile.png")
    mobile.write_bytes(JPEG)
    before = mobile.read_bytes()
    with pytest.raises(ValueError, match="requires PNG.*identify JPEG"):
        publisher.candidate_notes(root, context, [archive])
    assert mobile.read_bytes() == before


def test_reused_public_image_still_requires_its_actual_encoding(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    old = root / "publication/media/v0.3/desktop-companion.jpg"
    old.parent.mkdir(parents=True)
    old.write_bytes(PNG)
    manifest.write_text(json.dumps(data | {"screenshot_path": old.relative_to(root).as_posix()}))
    with pytest.raises(ValueError, match="requires JPEG.*identify PNG"):
        publisher.candidate_notes(root, context, [archive])


def test_nested_capture_in_candidate_namespace_is_checked(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    mobile = image.parent / "mobile" / "capture.webp"
    mobile.parent.mkdir()
    mobile.write_bytes(PNG)
    with pytest.raises(ValueError, match="requires WEBP.*identify PNG"):
        publisher.candidate_notes(root, context, [archive])


def test_previous_candidate_media_is_preserved_without_blanket_rescan(candidate):
    root, notes, image, manifest, data, context, archive = candidate
    old = root / "publication/media/0.3.1-rc.1/mobile.png"
    old.parent.mkdir(parents=True)
    old.write_bytes(JPEG)
    publisher.candidate_notes(root, context, [archive])
    assert old.read_bytes() == JPEG


def test_nonraster_flood_is_bounded_before_image_validation(candidate, monkeypatch):
    root, notes, image, manifest, data, context, archive = candidate
    monkeypatch.setattr(publisher, "MAX_PUBLICATION_MEDIA_ENTRIES", 4)
    for number in range(4):
        image.with_name(f"metadata{number}.txt").write_text("Isolated non-image fixture")
    with pytest.raises(ValueError, match="bounded entry count"):
        publisher.candidate_notes(root, context, [archive])


def test_deep_nonraster_directory_is_bounded(candidate, monkeypatch):
    root, notes, image, manifest, data, context, archive = candidate
    monkeypatch.setattr(publisher, "MAX_PUBLICATION_MEDIA_DEPTH", 2)
    metadata = image.parent / "first" / "second" / "metadata.txt"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("Isolated deeply nested non-image fixture")
    with pytest.raises(ValueError, match="bounded nesting depth"):
        publisher.candidate_notes(root, context, [archive])


def test_entry_and_depth_boundaries_allow_complete_small_namespace(candidate, monkeypatch):
    root, notes, image, manifest, data, context, archive = candidate
    monkeypatch.setattr(publisher, "MAX_PUBLICATION_MEDIA_ENTRIES", 4)
    monkeypatch.setattr(publisher, "MAX_PUBLICATION_MEDIA_DEPTH", 2)
    folder = image.parent / "mobile"
    folder.mkdir()
    (folder / "metadata.txt").write_text("Isolated non-image fixture")
    (folder / "capture.png").write_bytes(PNG)
    publisher.candidate_notes(root, context, [archive])


def test_raster_count_bound_is_retained(candidate, monkeypatch):
    root, notes, image, manifest, data, context, archive = candidate
    monkeypatch.setattr(publisher, "MAX_PUBLICATION_MEDIA_RASTERS", 1)
    image.with_name("mobile.png").write_bytes(PNG)
    with pytest.raises(ValueError, match="bounded file count"):
        publisher.candidate_notes(root, context, [archive])


@pytest.mark.parametrize("version,previous", [
    ("0.3.0-rc.1", ("0.2.0-rc.1", "0.1.0-rc.1")),
    ("0.3.1-rc.1", ("0.3.0-rc.1", "0.2.0-rc.1", "0.1.0-rc.1")),
    ("0.3.2-rc.1", ("0.3.1-rc.1", "0.3.0-rc.1", "0.2.0-rc.1", "0.1.0-rc.1")),
    ("0.3.3-rc.1", ("0.3.2-rc.1", "0.3.1-rc.1", "0.3.0-rc.1", "0.2.0-rc.1", "0.1.0-rc.1")),
    ("0.3.4-rc.1", ("0.3.3-rc.1", "0.3.2-rc.1", "0.3.1-rc.1", "0.3.0-rc.1", "0.2.0-rc.1", "0.1.0-rc.1")),
    ("0.3.5-rc.1", ("0.3.4-rc.1", "0.3.3-rc.1", "0.3.2-rc.1", "0.3.1-rc.1", "0.3.0-rc.1", "0.2.0-rc.1", "0.1.0-rc.1")),
    ("0.4.0-rc.1", ("0.3.4-rc.1", "0.3.3-rc.1", "0.3.2-rc.1", "0.3.1-rc.1", "0.3.0-rc.1", "0.2.0-rc.1", "0.1.0-rc.1")),
])
def test_release_history_adds_new_prior_candidate_without_changing_frozen_history(tmp_path, version, previous):
    if version == "0.3.0-rc.1":
        notes_relative = "publication/v0.3/release-notes.md"
        image_relative = "publication/media/v0.3/desktop-companion.jpg"
    else:
        notes_relative = f"publication/releases/{version}/notes.md"
        image_relative = f"publication/media/{version}/companion.jpg"
    notes, image = tmp_path / notes_relative, tmp_path / image_relative
    notes.parent.mkdir(parents=True)
    image.parent.mkdir(parents=True)
    notes.write_text(f"# Release {version}\n\nIsolated release history fixture.\n", encoding="utf-8")
    image.write_bytes(JPEG)
    if version != "0.3.0-rc.1":
        notes.with_name("manifest.json").write_text(json.dumps({"version": version, "notes_path": notes_relative, "screenshot_path": image_relative}), encoding="utf-8")
    evidence = tmp_path / f"release-evidence/v{version}"
    evidence.mkdir(parents=True)
    (evidence / "release-gates.json").write_text(json.dumps({"checks": {"isolated_test": True}}), encoding="utf-8")
    (evidence / "standalone-archive-verification.json").write_text(json.dumps({"test_suite": {"stdout": "1 passed"}}), encoding="utf-8")
    archive = tmp_path / f"System-Lab-Airspace-Operations-{version}.zip"
    archive.write_bytes(b"Isolated history archive fixture")
    source_bytes = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    result = publisher.candidate_notes(tmp_path, {"version": version, "sha": "a" * 40}, [archive])
    expected_history = "Previous candidates: " + ", ".join(f"[{value}](https://github.com/{publisher.REPOSITORY}/releases/tag/v{value})" for value in previous) + "."
    expected = (
        f"# Release {version}\n\nIsolated release history fixture.\n\n"
        f"![Companion workspace](https://raw.githubusercontent.com/{publisher.REPOSITORY}/{'a' * 40}/{image_relative})\n\n"
        f"Source commit: `{'a' * 40}`. Download: `{archive.name}` (32 bytes). SHA-256: `{publisher.digest(archive)}`.\n\n"
        "Engineering checks: 1 passed. Clean-install software suite: 1 passed. The original acceptance baseline remains partial; stable release and operational acceptance remain false.\n\n"
        + expected_history + "\n"
    )
    assert result == expected
    assert {path: path.read_bytes() for path in source_bytes} == source_bytes
