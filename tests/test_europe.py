"""Artificial country-readiness records in isolated software tests only."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from airspace.europe import ARTICLE_13, CrossBorderPlan, assess_cross_border, country_catalogue


def cross_border_input():
    interval = {"start": "2030-01-01T10:00:00Z", "end": "2030-01-01T11:00:00Z"}
    def review(country):
        return {"id": "test-review-" + country, "version": 1, "country": country, "pack_version": "test-only", "status": "Validated", "valid_from": "2030-01-01T00:00:00Z", "valid_until": "2031-01-01T00:00:00Z", "framework": "EU UAS", "source_refs": ["test-only"], "reviewed_by": "test-reviewer", "applicability_review_ref": "test-only-applicability"}
    def segment(country, start, end):
        return {"id": "test-segment-" + country, "country": country, "interval": {"start": start, "end": end}, "country_review_id": "test-review-" + country, "country_review_version": 1, "legal_route": "Operational Authorisation", "permission_requirements_reviewed": True, "required_instrument_kinds": ["operational_authorisation"], "instrument_ids": ["test-home", "test-host"], "local_conditions_review_ref": "test-only", "local_mitigations_ref": "test-only", "source_freshness_review_ref": "test-only"}
    home = {"id": "test-home", "version": 1, "kind": "operational_authorisation", "issuer": "Isolated test authority", "issuing_country": "LU", "operation_countries": ["LU", "IT"], "operator_organisation_id": "test-operator", "configuration_id": "test-config", "route_version": "test-route", "status": "Approved", "valid_from": "2030-01-01T00:00:00Z", "valid_until": "2031-01-01T00:00:00Z", "evidence_ref": "test-only", "legal_source_ref": "test-only"}
    host = {**home, "id": "test-host", "kind": "host_confirmation", "issuing_country": "IT", "operation_countries": ["IT"]}
    return {"actor_id": "test-only", "mission_id": "test-mission", "mission_version": 1, "operator_organisation_id": "test-operator", "registration_country": "LU", "configuration_id": "test-config", "route_version": "test-route", "operation_interval": interval,
            "segments": [segment("LU", interval["start"], "2030-01-01T10:30:00Z"), segment("IT", "2030-01-01T10:30:00Z", interval["end"])], "country_reviews": [review("LU"), review("IT")], "instruments": [home, host], "handovers": [{"from_segment_id": "test-segment-LU", "to_segment_id": "test-segment-IT", "procedure_ref": "test-only", "responsible_person_id": "test-person", "acknowledgement_ref": "test-only", "contingency_coordination_ref": "test-only"}]}


def test_home_authorisation_never_substitutes_for_host_confirmation():
    payload = cross_border_input()
    assert assess_cross_border(payload)["ready_for_internal_review"]
    payload["instruments"] = payload["instruments"][:1]
    result = assess_cross_border(payload)
    assert not result["ready_for_internal_review"]
    assert any("host_confirmation" in finding for finding in result["findings"])


@pytest.mark.parametrize("mutation", ["expiry", "operator", "configuration", "country-scope", "wrong-issuer", "registered-pack", "handover", "gap", "review-version"])
def test_cross_border_hazards_fail_closed(mutation):
    payload = cross_border_input()
    if mutation == "expiry": payload["instruments"][1]["valid_until"] = "2030-01-01T10:45:00Z"
    elif mutation == "operator": payload["instruments"][1]["operator_organisation_id"] = "another-operator"
    elif mutation == "configuration": payload["instruments"][1]["configuration_id"] = "changed-config"
    elif mutation == "country-scope": payload["instruments"][1]["operation_countries"] = ["LU"]
    elif mutation == "wrong-issuer": payload["instruments"][1]["issuing_country"] = "LU"
    elif mutation == "registered-pack": payload["country_reviews"][1]["status"] = "Registered"
    elif mutation == "handover": payload["handovers"] = []
    elif mutation == "gap": payload["segments"][1]["interval"]["start"] = "2030-01-01T10:31:00Z"
    else: payload["segments"][1]["country_review_version"] = 2
    assert not assess_cross_border(payload)["ready_for_internal_review"]


@pytest.mark.parametrize("route,home_kind,submission_kind", [("STS Declaration", "declaration_home_receipt", "host_declaration_submission"), ("LUC Privilege", "luc_terms", "luc_host_notification")])
def test_article13_submission_routes_require_no_invented_host_authority_response(route, home_kind, submission_kind):
    payload = cross_border_input()
    for segment in payload["segments"]:
        segment.update(legal_route=route, required_instrument_kinds=[home_kind])
    payload["instruments"][0]["kind"] = home_kind
    payload["instruments"][1].update(kind=submission_kind, issuer="Isolated test operator submission ledger", issuing_country="LU", recipient_country="IT", provided_at="2030-01-01T09:00:00Z", evidence_ref="test-only-documented-delivery")
    result = assess_cross_border(payload)
    assert result["ready_for_internal_review"]
    assert "host_confirmation" not in {decision["kind"] for segment in result["segments"] for decision in segment["decisions"]}
    assert not any(instrument["issuing_country"] == "IT" for instrument in payload["instruments"])
    submission = next(decision for decision in result["segments"][1]["decisions"] if decision["kind"] == submission_kind)
    assert submission["record_role"] == "Operator Documented Submission"
    assert "no authority issuance or response" in submission["review_meaning"]


@pytest.mark.parametrize("route,home_kind,submission_kind", [("STS Declaration", "declaration_home_receipt", "host_declaration_submission"), ("LUC Privilege", "luc_terms", "luc_host_notification")])
@pytest.mark.parametrize("missing", ["recipient_country", "provided_at", "evidence_ref"])
def test_operator_submission_needs_actual_recipient_time_and_delivery_evidence(route, home_kind, submission_kind, missing):
    payload = cross_border_input()
    for segment in payload["segments"]:
        segment.update(legal_route=route, required_instrument_kinds=[home_kind])
    payload["instruments"][0]["kind"] = home_kind
    payload["instruments"][1].update(kind=submission_kind, issuing_country="LU", recipient_country="IT", provided_at="2030-01-01T09:00:00Z")
    payload["instruments"][1].pop(missing)
    with pytest.raises(ValidationError):
        CrossBorderPlan.model_validate(payload)


@pytest.mark.parametrize("mutation", ["origin", "recipient", "late-provision", "operation-scope"])
def test_operator_submission_country_and_delivery_scope_are_rechecked(mutation):
    payload = cross_border_input()
    for segment in payload["segments"]:
        segment.update(legal_route="STS Declaration", required_instrument_kinds=["declaration_home_receipt"])
    payload["instruments"][0]["kind"] = "declaration_home_receipt"
    submission = payload["instruments"][1]
    submission.update(kind="host_declaration_submission", issuing_country="LU", recipient_country="IT", provided_at="2030-01-01T09:00:00Z", evidence_ref="test-only-documented-delivery")
    if mutation == "origin": submission["issuing_country"] = "IT"
    elif mutation == "recipient": submission["recipient_country"] = "FR"
    elif mutation == "late-provision": submission["provided_at"] = "2030-01-01T10:31:00Z"
    else: submission["operation_countries"] = ["LU"]
    assert not assess_cross_border(payload)["ready_for_internal_review"]


def test_article13_evidence_distinctions_match_preserved_primary_provisions():
    reference = json.loads((Path(__file__).parent / "references/article13-2026.json").read_text(encoding="utf-8"))
    passages = {passage["anchor"].rsplit(":", 1)[1]: passage for passage in reference["passages"]}
    assert set(passages) == {"b0005", "b0006", "b0007", "b0008", "b0009"}
    assert all(passage["source_checksum"] == ARTICLE_13["source_checksum"] and passage["legal_status"] == "binding_legislation" for passage in passages.values())
    # These assertions come from the preserved legal text, independently of the
    # engine's kind names and dispatch implementation. They fix the distinction
    # between host confirmation under (2) and operator provision under (3)/(4).
    assert "Upon receipt of that confirmation, the UAS operator may start" in passages["b0005"]["text"]
    assert "the UAS operator shall provide" in passages["b0006"]["text"]
    assert "copy of the declaration submitted to the Member State of registration" in passages["b0006"]["text"]
    assert "copy of the confirmation of receipt and completeness" in passages["b0006"]["text"]
    assert "the UAS operator shall provide" in passages["b0007"]["text"]
    assert "copy of the term of approval received" in passages["b0008"]["text"]
    assert "location or locations of the intended operation" in passages["b0009"]["text"]


def test_open_category_does_not_invent_an_operational_authorisation_requirement():
    payload = cross_border_input()
    for segment in payload["segments"]:
        segment.update(legal_route="Open Category", required_instrument_kinds=[], instrument_ids=[])
    payload["instruments"] = []
    assert assess_cross_border(payload)["ready_for_internal_review"]


def test_geographical_registry_is_never_a_validated_country_pack():
    catalogue = country_catalogue()
    assert {"LU", "IT", "GB", "CH", "NO"}.issubset({country["country"] for country in catalogue})
    assert all(country["coverage_status"] == "Registered" and not country["operationally_validated"] for country in catalogue)
    payload = cross_border_input()
    payload["country_reviews"][1]["country"] = "CH"
    with pytest.raises(ValidationError):
        CrossBorderPlan.model_validate(payload)
