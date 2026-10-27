"""Artificial examples are confined to these isolated validation fixtures."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from airspace.neural import validate_annotation, LocalEncoder, ScopedCachedEncoder, _EMBEDDINGS


def record(text):
    return {"id":"isolated-test","source_id":"isolated-software-test","source_checksum":"test-checksum","document_version":"test","text":text}


def test_teacher_unsupported_annotation_is_quarantined():
    result=validate_annotation(record("This isolated test paragraph contains background context."),"yes","isolated-test-model","test-prompt")
    assert result["status"] == "Quarantined"
    assert result["ground_truth"] is False
    assert result["human_reviewed"] is False


def test_teacher_source_spans_are_exact_and_unreviewed():
    passage=record("This test operator shall retain test evidence.")
    result=validate_annotation(passage,"yes","isolated-test-model","test-prompt")
    assert result["status"] == "Machine-generated — Unreviewed"
    for span in result["source_spans"]:
        assert passage["text"][span["start"]:span["end"]] == span["text"]


def test_teacher_contradiction_and_unknown_labels_quarantined():
    assert validate_annotation(record("A test operator shall preserve the test record."),"no","test","test")["status"] == "Quarantined"
    assert validate_annotation(record("A test record."),"grant all flight permissions","test","test")["status"] == "Quarantined"


def test_local_missing_model_does_not_download_or_execute_remote_code(tmp_path):
    with pytest.raises(FileNotFoundError):
        LocalEncoder(tmp_path/"missing")


def test_cache_is_bounded_and_separates_organisation_scopes():
    class TestEncoder:
        version = "isolated-test-encoder"
        calls = 0
        def encode(self,texts):
            self.calls += 1
            return [[1.,0.] for _ in texts]
    _EMBEDDINGS.clear()
    base = TestEncoder()
    one = ScopedCachedEncoder(base,"isolated-tenant-one")
    two = ScopedCachedEncoder(base,"isolated-tenant-two")
    one.encode(["isolated software test question"])
    one.encode(["isolated software test question"])
    assert base.calls == 1
    two.encode(["isolated software test question"])
    assert base.calls == 2
    assert len(_EMBEDDINGS) == 2
    assert all("isolated software test question" not in str(k) for k in _EMBEDDINGS)
