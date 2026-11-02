"""Regression checks for stale aliases and cross-release publication bindings."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publication_checkpoint", ROOT / "scripts/publication_checkpoint.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EV = "release-evidence/v0.3.3-rc.1/"
OLD = "cycle-20261101T105140Z-"
NEW = "cycle-20261102T011950Z-"

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def inputs():
    status = load("publication/history/0.3.3-rc.1.json")
    evidence = {"site_native": load(EV + OLD + "site-native.json"),
                "site_public": load(EV + NEW + "site100-public.json"),
                "hub_manifest": load("publication/releases/0.3.3-rc.1/huggingface/manifest.json"),
                "hub": {kind: load(EV + NEW + "hub-" + kind + "-" + head + "-reviewed-lfs.json")
                        for kind, head in (("model", "53ab0273"), ("dataset", "73c59f1f"), ("space", "b92dfde0"))},
                "space_live": load(EV + NEW + "verify-space-live.json"),
                "documentation": load(EV + NEW + "main-checkpoint.json")}
    paths = {"hub_manifest": "publication/releases/0.3.3-rc.1/huggingface/manifest.json",
             "hub_publication": EV + OLD + "hub-publication.json",
             "space_live": EV + NEW + "verify-space-live.json",
             "documentation": EV + NEW + "main-checkpoint.json"}
    return status, evidence, paths

def test_repairs_stale_current_aliases_without_changing_history_or_input():
    status, evidence, paths = inputs()
    status["destinations"][2]["saved_version_id"] = "stale"
    status["destinations"][3]["current_published_revision"] = "stale"
    before = deepcopy(status)
    result = MODULE.reconcile_current_publication(status, evidence, paths)
    assert status == before
    assert result["destinations"][2]["saved_version_id"] == evidence["site_native"]["saved"]["id"]
    assert result["destinations"][3]["current_published_revision"] == evidence["hub"]["model"]["head"]
    assert result["destinations"][2]["remote_source_commit"] == evidence["site_public"]["site_source_commit"]
    for index, kind in ((3, "model"), (4, "dataset"), (5, "space")):
        row = result["destinations"][index]
        assert row["current_published_revision"] == evidence["hub"][kind]["head"]
        assert row["prior_revision"] == evidence["hub"][kind]["expected_parent"]
        assert row["prepared_application_version"] == status["release"]
        assert row["prepared_files_manifest"] == paths["hub_manifest"]
        assert row["prior_release"] == row["previous_verified"]["release"]
    assert result["destinations"][5]["live_host_evidence"] == paths["space_live"]
    assert result["documentation_checkpoint"]["commit"] == evidence["documentation"]["github_main"]
    for previous, current in zip(status["destinations"], result["destinations"], strict=True):
        assert previous.get("previous_verified") == current.get("previous_verified")
    assert status["history"] == result["history"]
    assert status["published_archive"] == result["published_archive"]
    assert not result["full_original_specification_accepted"]
    assert not result["stable_release_allowed"] and not result["operational_acceptance"]
    assert MODULE.reconcile_current_publication(result, evidence, paths) == result

@pytest.mark.parametrize("kind", ["site_identity", "incomplete_site", "pack_source", "hub_parent", "target_digest", "space_head", "documentation", "duplicate_target", "duplicate_document", "github_alias", "wrong_repository"])
def test_rejects_incomplete_or_cross_release_evidence(kind):
    status, evidence, paths = inputs()
    if kind == "site_identity": evidence["site_native"]["saved"]["id"] = "another-version"
    elif kind == "incomplete_site": evidence["site_public"]["summary"]["verified"] -= 1
    elif kind == "pack_source": evidence["hub_manifest"]["application_source"] = "0" * 40
    elif kind == "hub_parent": evidence["hub"]["model"]["expected_parent"] = "0" * 40
    elif kind == "target_digest": evidence["hub"]["model"]["changed_files"][0]["sha256"] = "0" * 64
    elif kind == "space_head": evidence["space_live"]["head"] = "0" * 40
    elif kind == "documentation": evidence["documentation"]["exact"] -= 1
    elif kind == "duplicate_target": evidence["hub"]["model"]["changed_files"].append(deepcopy(evidence["hub"]["model"]["changed_files"][0]))
    elif kind == "github_alias": status["destinations"][0]["commit"] = "0" * 40
    elif kind == "wrong_repository": evidence["hub"]["model"]["repository"] = "another/repository"
    else: evidence["documentation"]["files"][1] = deepcopy(evidence["documentation"]["files"][0])
    before = deepcopy(status)
    with pytest.raises(ValueError): MODULE.reconcile_current_publication(status, evidence, paths)
    assert status == before
