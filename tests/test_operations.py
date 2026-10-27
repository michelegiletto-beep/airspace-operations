"""All artificial data in this file is isolated software verification data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from airspace.operations import (SORA_REQUIREMENTS, SORA_25_SNAPSHOT, EconomicsRequest, SoraCalculationInputs, assess_sora, calculate_economics, connector_catalog,
                                 evaluate_telemetry, geodesic_distance_m, incident_checklist, screen_site, sora_25_lookups)


def site_input():
    return {"actor_id": "test-only", "at": "2026-10-27T12:00:00Z", "point": {"longitude": 6.13, "latitude": 49.61, "altitude_m": 100, "vertical_reference": "AGL", "horizontal_uncertainty_m": 2, "vertical_uncertainty_m": 3},
            "zones": [{"id": "test-only-zone", "source_anchor": "test:isolated-fixture", "source_version": "test-1", "purpose": "Operationally Accepted", "geometry": {"type": "Circle", "coordinates": [6.13, 49.61], "radius_m": 1000}, "valid_from": "2026-10-01T00:00:00Z", "valid_until": "2026-11-01T00:00:00Z", "lower_m": 0, "upper_m": 120, "vertical_reference": "AGL", "source_precision_m": 10, "restriction": "Isolated test restriction"}]}


def telemetry_event():
    return {"event_id": "test-event", "source_id": "test-source", "aircraft_id": "test-craft", "mission_id": "test-mission", "observed_at": "2026-10-27T12:00:00Z", "received_at": "2026-10-27T12:00:01Z", "sequence": 5,
            "position": {"longitude": 6.13, "latitude": 49.61, "altitude_m": 100, "vertical_reference": "AGL", "horizontal_uncertainty_m": 2, "vertical_uncertainty_m": 3}, "mode": "Live", "source_version": "test-only"}


def telemetry_input():
    return {"actor_id": "test-only", "now": "2026-10-27T12:00:30Z", "mode": "Live", "policy": {"stale_after_seconds": 10, "source_ref": "test-only-policy", "approved_by": "test-reviewer", "operational_use_accepted": True}, "events": [telemetry_event()], "expected_aircraft_ids": ["test-craft"]}


def test_sora_mixed_edition_and_configuration_cannot_reuse_evidence():
    payload = {"actor_id": "test-only", "methodology": "2.5", "configuration_id": "test-config-2", "conops_version": "test-conops-2", "jurisdiction": "LU", "evidence": {"initial_air_risk": [{"id": "test-only-evidence", "source_anchor": "test:fixture", "source_version": "test-1", "configuration_id": "test-config-1", "conops_version": "test-conops-1", "methodology": "2.0", "category": "Document Review", "review_status": "Approved", "reviewed_by": "test-reviewer"}]}}
    result = assess_sora(payload)
    requirement = next(r for r in result["requirements"] if r["id"] == "initial_air_risk")
    assert requirement["state"] == "Missing Evidence"
    assert len(requirement["rejected_for_reuse"][0]["reasons"]) == 3
    assert result["risk_classes"]["SAIL"] is None


def test_even_complete_sora_evidence_does_not_claim_validated_calculation():
    payload = {"actor_id": "test-only", "methodology": "2.5", "configuration_id": "test-config", "conops_version": "test-conops", "jurisdiction": "LU", "methodology_applicability_review_ref": "test:review", "evidence": {}}
    for key, _ in SORA_REQUIREMENTS:
        payload["evidence"][key] = [{"id": "test-only-" + key, "source_anchor": "test:fixture", "source_version": "test-1", "configuration_id": "test-config", "conops_version": "test-conops", "methodology": "2.5", "category": "Document Review", "review_status": "Approved", "reviewed_by": "test-reviewer"}]
    result = assess_sora(payload)
    assert result["status"] == "Requires Domain Review"
    assert result["calculation_status"] == "Not Implemented"
    assert result["risk_classes"] == {"GRC": None, "ARC": None, "SAIL": None}


def test_geodesic_reference_matches_proj_documentation():
    # PROJ/pyproj published WGS84-independent reference uses Clarke 1866;
    # this independent WGS84 equator reference is a quarter circumference.
    assert geodesic_distance_m((0, 0), (90, 0)) == pytest.approx(10018754.171394622, abs=0.001)
    assert geodesic_distance_m((179.9, 0), (-179.9, 0)) == pytest.approx(22263.898, abs=0.01)


@given(lat=st.floats(-89, 89, allow_nan=False), lon=st.floats(-179, 179, allow_nan=False))
def test_distance_symmetry_and_identity(lat, lon):
    assert geodesic_distance_m((lon, lat), (lon, lat)) == pytest.approx(0)
    assert geodesic_distance_m((lon, lat), (6, 49)) == pytest.approx(geodesic_distance_m((6, 49), (lon, lat)), rel=1e-12)


def test_site_missing_coverage_and_unknown_vertical_are_visible():
    payload = site_input()
    payload["point"]["vertical_reference"] = "Unknown"
    result = screen_site(payload)
    assert result["zone_results"][0]["relation"] == "Unresolved"
    assert any("Missing authoritative coverage" in finding for finding in result["findings"])


def test_site_circle_and_polygon_intersection():
    payload = site_input()
    assert screen_site(payload)["zone_results"][0]["relation"] == "Intersection"
    payload["zones"][0]["geometry"] = {"type": "Polygon", "coordinates": [[[6.12, 49.60], [6.14, 49.60], [6.14, 49.62], [6.12, 49.62], [6.12, 49.60]]]}
    assert screen_site(payload)["zone_results"][0]["relation"] == "Intersection"


def test_vertical_conversion_requires_terrain_source_and_uncertainty():
    payload = site_input()
    payload["zones"][0]["vertical_reference"] = "AMSL"
    payload["zones"][0]["lower_m"] = 300
    payload["zones"][0]["upper_m"] = 500
    assert screen_site(payload)["zone_results"][0]["vertical_relation"] == "Unknown"
    payload["point"].update(terrain_elevation_amsl_m=300, terrain_evidence_ref="test-only", terrain_uncertainty_m=5)
    assert screen_site(payload)["zone_results"][0]["vertical_relation"] == "Inside"


def test_research_source_and_expired_zone_never_create_clearance():
    payload = site_input()
    payload["zones"][0]["purpose"] = "Research Only"
    assert any("research data" in f for f in screen_site(payload)["findings"])
    payload["zones"][0]["valid_until"] = "2026-10-26T00:00:00Z"
    assert any("not applicable" in f for f in screen_site(payload)["findings"])


def test_polygon_with_self_crossing_or_unknown_bounds_is_unresolved():
    payload = site_input()
    payload["zones"][0]["geometry"] = {"type": "Polygon", "coordinates": [[[6.12, 49.60], [6.14, 49.62], [6.12, 49.62], [6.14, 49.60], [6.12, 49.60]]]}
    assert screen_site(payload)["zone_results"][0]["relation"] == "Unresolved"


def test_duplicate_delayed_and_contradictory_telemetry():
    payload = telemetry_input()
    duplicate = deepcopy(payload["events"][0])
    duplicate["received_at"] = "2026-10-27T12:00:05Z"
    old = deepcopy(payload["events"][0])
    old.update(event_id="test-older", observed_at="2026-10-27T11:59:00Z", sequence=4)
    conflict = deepcopy(payload["events"][0])
    conflict["position"]["latitude"] += 0.1
    payload["events"] += [duplicate, old, conflict]
    result = evaluate_telemetry(payload)
    assert [x["state"] for x in result["observations"]][:3] == ["Accepted", "Duplicate", "Archived Out of Order"]
    assert result["observations"][3]["state"].startswith("Quarantined")
    assert result["latest_verified"][0]["event_id"] == "test-event"
    assert result["latest_verified"][0]["freshness"] == "Stale"
    assert not result["latest_verified"][0]["predicted"]


def test_telemetry_subsecond_precision_is_preserved():
    payload = telemetry_input()
    payload["events"][0]["observed_at"] = "2026-10-27T12:00:00.123456Z"
    result = evaluate_telemetry(payload)
    assert ".123456" in result["latest_verified"][0]["observed_at"]


def test_telemetry_future_timestamps_and_replay_cannot_enter_live_state():
    payload = telemetry_input()
    payload["events"][0]["mode"] = "Historical Replay"
    result = evaluate_telemetry(payload)
    assert not result["latest_verified"]
    assert any(a["type"] == "Telemetry Missing" for a in result["alerts"])
    payload = telemetry_input()
    payload["events"][0]["observed_at"] = "2026-10-27T12:05:00Z"
    assert not evaluate_telemetry(payload)["accepted_records"]


def test_missing_monitoring_policy_never_invents_freshness():
    payload = telemetry_input()
    payload["policy"] = None
    result = evaluate_telemetry(payload)
    assert result["status"] == "Missing Monitoring Policy"
    assert result["latest_verified"][0]["freshness"] == "Unknown"


def test_incident_missing_procedure_never_generates_emergency_instruction():
    payload = {"actor_id": "test-only", "incident_type": "Lost Communications", "aircraft_configuration_id": "test-config", "created_at": "2026-10-27T12:00:00Z", "now": "2026-10-27T12:01:00Z", "assigned_owner_id": "test-owner", "escalation_after_seconds": 30, "escalation_policy_ref": "test-only"}
    result = incident_checklist(payload)
    assert result["checklist"] == []
    assert result["escalation"] == "Escalation Required"
    assert result["notification"]["state"] == "Not Sent"
    payload["procedure"] = {"id": "test-only-procedure", "version": "test-1", "incident_types": ["Lost Communications"], "configuration_id": "test-config", "status": "Approved", "approved_by": "test-reviewer", "source_ref": "test-only", "valid_until": "2026-11-01T00:00:00Z", "steps": ["Isolated test step; not a flight instruction"]}
    assert incident_checklist(payload)["checklist"][0]["text"] == payload["procedure"]["steps"][0]


def financial(value):
    return {"value": value, "provenance": "Analyst Assumption", "evidence_ref": "test:isolated-fixture", "as_of": "2026-10-27"}


def test_economics_missing_data_stays_empty_and_actual_decimal_formulas():
    payload = {"actor_id": "test-only", "currency": "EUR", "period": "Test only"}
    result = calculate_economics(payload)
    assert result["status"] == "Incomplete"
    assert all(value is None for value in result["values"].values())
    payload.update(planned_missions=financial("100"), revenue_per_mission=financial("10"), variable_cost_per_mission=financial("4"), fixed_cost=financial("200"), capacity_missions=financial("200"), regulatory_blockers=["Test-only unresolved permission"])
    result = calculate_economics(payload)
    assert result["values"]["cost_per_mission"] == "6"
    assert result["values"]["period_contribution"] == "400"
    assert result["values"]["resource_utilisation"] == "0.5"
    assert result["stage_gate"] == "Blocked"
    assert result["forecast"] is True


def test_financial_division_by_zero_is_undefined_not_fabricated():
    payload = {"actor_id": "test-only", "currency": "EUR", "period": "Test only", "planned_missions": financial("0"), "revenue_per_mission": financial("4"), "variable_cost_per_mission": financial("4"), "fixed_cost": financial("100"), "capacity_missions": financial("0")}
    values = calculate_economics(payload)["values"]
    assert values["cost_per_mission"] is None
    assert values["resource_utilisation"] is None
    assert values["break_even_missions"] is None


def test_connector_catalog_does_not_claim_untested_connections():
    connectors = connector_catalog()
    assert all(connector["live_test"] is None for connector in connectors)
    ead = next(c for c in connectors if c["id"] == "eurocontrol-ead-basic")
    assert ead["operational_use_allowed"] is False
    assert ead["permitted_purpose"] == "Research Only"


def lookup_inputs(**changes):
    return SoraCalculationInputs(final_grc=changes.get("final_grc", 2), residual_arc=changes.get("residual_arc", "ARC-b"), flight_mode=changes.get("flight_mode", "BVLOS"), maximum_speed_m_s=changes.get("maximum_speed_m_s", 30), reviewed_inputs_ref="test-only-review-reference", reviewed_by="test-only-reviewer", source_snapshot_checksum=SORA_25_SNAPSHOT)


def test_sora_sail_and_tmpr_all_rows_match_preserved_official_source():
    # Independent oracle: the actual downloaded regulatory passages, not a
    # second transcription of the implementation's lookup matrix.
    import json
    from pathlib import Path
    path = next((Path(__file__).resolve().parents[1] / "sources" / "snapshots" / "easa-uas-xml-2026").glob("*/passages.json"))
    by_anchor = {p["anchor"]: p for p in json.loads(path.read_text(encoding="utf-8"))}
    for grc in range(1, 8):
        source = by_anchor[f"ERULES-1963177438-24086:b{461 + max(2, grc) - 2:04d}"]
        expected = [part.strip() for part in source["text"].split("|")][1:]
        assert source["source_checksum"] == SORA_25_SNAPSHOT
        assert source["methodology"] == "SORA 2.5"
        for column, arc in enumerate(("ARC-a", "ARC-b", "ARC-c", "ARC-d")):
            result = sora_25_lookups(lookup_inputs(final_grc=grc, residual_arc=arc), "2.5")
            assert result["SAIL"] == expected[column]
            tmpr_source = by_anchor[result["tmpr_source_anchor"]]
            assert result["TMPR"] == tmpr_source["text"].split("|")[1].strip()
            assert result["qualified_validation"] == "Requires Domain Review"


@pytest.mark.parametrize("speed,expected", [(1, 5000), (5000 / 180, 5000), (30, 5400), (100, 18000), (35000 / 180, 35000), (300, 35000)])
def test_adjacent_ground_outer_distance_exact_published_bounds(speed, expected):
    result = sora_25_lookups(lookup_inputs(maximum_speed_m_s=speed), "2.5")
    assert result["adjacent_ground_outer_distance_m"] == pytest.approx(expected)
    assert result["adjacent_distance_source_anchor"].endswith("b0486-b0489")


def test_sora_lookup_cannot_mix_editions_missing_inputs_or_source_versions():
    assert sora_25_lookups(lookup_inputs(), "2.0")["SAIL"] is None
    incomplete = SoraCalculationInputs(final_grc=2, residual_arc="ARC-a")
    assert sora_25_lookups(incomplete, "2.5")["SAIL"] is None
    mismatched = lookup_inputs()
    mismatched.source_snapshot_checksum = "unreviewed-source"
    assert sora_25_lookups(mismatched, "2.5")["SAIL"] is None
    assert sora_25_lookups(lookup_inputs(final_grc=8), "2.5")["SAIL"] == "Outside SORA specific-category scope"
    assert "deconfliction" in sora_25_lookups(lookup_inputs(flight_mode="VLOS"), "2.5")["TMPR"]
