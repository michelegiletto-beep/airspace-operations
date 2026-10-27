"""Artificial records in this module are isolated software test fixtures only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from airspace.scheduler import ScheduleRequest, snapshot_hash, solve_schedule, verify_schedule


def schedule_input():
    window = {"start": "2026-10-25T00:00:00Z", "end": "2026-10-25T04:00:00Z"}
    feed = {"source_id": "test-only", "source_version": "test-1", "evidence_ref": "test-fixture", "observed_at": window["start"], "valid_until": window["end"], "suitable": True, "operational_use_accepted": True}
    permission = {"id": "test-permission", "kind": "operating_basis", "issuer_type": "Competent Authority", "status": "Approved", "valid_from": window["start"], "valid_until": window["end"], "evidence_ref": "test-only", "configuration_id": "test-config", "route_version": "test-route-1", "revision": 1}
    mission = {"id": "test-operation-1", "revision": 1, "window": window, "duration_seconds": 600, "payload_kg": 1, "configuration_id": "test-config", "route_version": "test-route-1", "site_id": "test-site", "required_qualifications": ["test-pilot-scope"], "permission_requirements_reviewed": True, "required_permission_kinds": ["operating_basis"], "permissions": [permission], "route_approved": True, "weather": feed, "airspace": deepcopy(feed), "u_space_required": False}
    return {"actor_id": "test-only-actor", "input_revision": 1, "local_timezone": "Europe/Luxembourg", "missions": [mission], "aircraft": [{"id": "test-aircraft", "revision": 1, "configuration_id": "test-config", "serviceable": True, "payload_capacity_kg": 2, "availability": [window], "maintenance_due": window["end"], "usable_flight_seconds": 3600, "turnaround_seconds": 60, "readiness_evidence_ref": "test-only", "battery_evidence_ref": "test-only", "policy_ref": "test-only"}], "personnel": [{"id": "test-person", "revision": 1, "availability": [window], "qualifications": {"test-pilot-scope": window["end"]}, "max_duty_seconds": 14400, "duty_already_seconds": 0, "policy_ref": "test-only"}], "sites": [{"id": "test-site", "concurrent_capacity": 1, "availability": [window], "capacity_evidence_ref": "test-only"}], "max_solver_seconds": 2}


def test_real_cp_sat_and_independent_verifier():
    payload = schedule_input()
    result = solve_schedule(payload)
    assert result["status"] == "OPTIMAL"
    assert result["solver"]["name"] == "OR-Tools CP-SAT"
    assert result["verification"]["valid"]
    assert result["assignments"][0]["start"] == "2026-10-25T00:00:00Z"
    assert not result.get("released", False)


@pytest.mark.parametrize("mutation", ["missing-weather", "unknown-uspace", "missing-permission", "unreviewed"])
def test_missing_evidence_never_yields_schedule(mutation):
    payload = schedule_input()
    mission = payload["missions"][0]
    if mutation == "missing-weather":
        mission["weather"] = None
    elif mutation == "unknown-uspace":
        mission["u_space_required"] = None
    elif mutation == "missing-permission":
        mission["permissions"] = []
    else:
        mission["permission_requirements_reviewed"] = False
    result = solve_schedule(payload)
    assert result["status"] == "INCOMPLETE"
    assert result["assignments"] == []


@pytest.mark.parametrize("mutation", ["expiry", "configuration", "weather", "research", "qualification", "maintenance", "battery", "payload", "suspended"])
def test_hard_prerequisites_cannot_be_traded_for_objective(mutation):
    payload = schedule_input()
    mission = payload["missions"][0]
    if mutation == "expiry":
        mission["permissions"][0]["valid_until"] = "2026-10-25T00:00:01Z"
    elif mutation == "configuration":
        mission["permissions"][0]["configuration_id"] = "superseded-test-configuration"
    elif mutation == "weather":
        mission["weather"]["suitable"] = False
    elif mutation == "research":
        mission["airspace"]["operational_use_accepted"] = False
    elif mutation == "qualification":
        payload["personnel"][0]["qualifications"] = {}
    elif mutation == "maintenance":
        payload["aircraft"][0]["maintenance_due"] = "2026-10-25T00:00:01Z"
    elif mutation == "battery":
        payload["aircraft"][0]["usable_flight_seconds"] = 599
    elif mutation == "payload":
        payload["aircraft"][0]["payload_capacity_kg"] = 0.5
    else:
        mission["permissions"][0]["status"] = "Suspended"
    result = solve_schedule(payload)
    assert result["status"] == "INFEASIBLE"
    assert not result["assignments"]


def test_resource_conflicts_and_dependencies_are_solved():
    payload = schedule_input()
    second = deepcopy(payload["missions"][0])
    second.update(id="test-operation-2", depends_on=["test-operation-1"])
    payload["missions"].append(second)
    result = solve_schedule(payload)
    first, second = result["assignments"]
    assert datetime.fromisoformat(second["start"].replace("Z", "+00:00")) - datetime.fromisoformat(first["end"].replace("Z", "+00:00")) >= timedelta(seconds=60)
    assert result["verification"]["valid"]


def test_duplicate_reservations_and_stale_snapshot_rejected_by_verifier():
    payload = schedule_input()
    result = solve_schedule(payload)
    result["assignments"].append(deepcopy(result["assignments"][0]))
    checked = verify_schedule(payload, result)
    assert not checked["valid"]
    assert "Every proposed operation must appear exactly once" in checked["findings"]
    changed = schedule_input()
    changed["aircraft"][0]["revision"] += 1
    assert not verify_schedule(changed, solve_schedule(payload))["valid"]


def test_verifier_detects_tampering_even_with_current_digest():
    payload = schedule_input()
    result = solve_schedule(payload)
    payload["missions"][0]["weather"]["suitable"] = False
    result["input_snapshot"] = snapshot_hash(ScheduleRequest.model_validate(payload))
    checked = verify_schedule(payload, result)
    assert not checked["valid"]
    assert any("unsuitable weather" in finding for finding in checked["findings"])


def test_dst_fall_back_explicit_offsets_differ_by_one_hour():
    payload = schedule_input()
    payload["missions"][0]["locked_start"] = "2026-10-25T02:30:00+02:00"
    early = solve_schedule(payload)
    payload["missions"][0]["locked_start"] = "2026-10-25T02:30:00+01:00"
    late = solve_schedule(payload)
    assert early["assignments"][0]["start"] == "2026-10-25T00:30:00Z"
    assert late["assignments"][0]["start"] == "2026-10-25T01:30:00Z"


def test_ambiguous_naive_time_and_forged_authority_issuer_rejected():
    payload = schedule_input()
    payload["missions"][0]["locked_start"] = "2026-10-25T02:30:00"
    with pytest.raises(ValidationError):
        ScheduleRequest.model_validate(payload)
    payload = schedule_input()
    payload["missions"][0]["permissions"][0]["issuer_type"] = "Accountable Reviewer"
    with pytest.raises(ValidationError):
        ScheduleRequest.model_validate(payload)


def test_cross_midnight_duty_span_includes_idle_gap():
    import json
    payload = schedule_input()
    payload = json.loads(json.dumps(payload).replace("2026-10-25T00:00:00Z", "2026-10-24T23:00:00Z"))
    payload["personnel"][0]["max_duty_seconds"] = 1200
    payload["missions"][0]["locked_start"] = "2026-10-24T23:30:00Z"
    second = deepcopy(payload["missions"][0])
    second.update(id="test-operation-2", locked_start="2026-10-25T00:30:00Z")
    payload["missions"].append(second)
    assert solve_schedule(payload)["status"] == "INFEASIBLE"


def test_cross_midnight_assignment_preserves_utc_dates():
    import json
    payload = json.loads(json.dumps(schedule_input()).replace("2026-10-25T00:00:00Z", "2026-10-24T23:00:00Z"))
    payload["missions"][0].update(duration_seconds=1200, locked_start="2026-10-24T23:50:00Z")
    result = solve_schedule(payload)
    assert result["assignments"][0]["start"] == "2026-10-24T23:50:00Z"
    assert result["assignments"][0]["end"] == "2026-10-25T00:10:00Z"
    assert result["verification"]["valid"]


def test_dispatch_decisions_are_separate_and_self_review_blocked():
    from airspace.operations import assess_dispatch
    mission = schedule_input()["missions"][0]
    for kind, issuer in (("safety_review", "Accountable Reviewer"), ("internal_dispatch", "Accountable Reviewer"), ("pilot_acknowledgement", "Pilot")):
        instrument = deepcopy(mission["permissions"][0])
        instrument.update(id="test-" + kind, kind=kind, issuer_type=issuer)
        mission["permissions"].append(instrument)
    request = {"actor_id": "test-only-actor", "mission": mission, "start": "2026-10-25T00:00:00Z", "end": "2026-10-25T00:10:00Z", "aircraft_serviceable": True, "configuration_id": "test-config", "pilot_id": "test-person", "pilot_qualified_until": "2026-10-25T04:00:00Z", "prepared_by": "test-author", "reviewer_id": "test-reviewer"}
    result = assess_dispatch(request)
    assert result["status"] == "Eligible for Internal Release Review"
    assert len(result["decisions"]) == 4
    assert not result["release_created"]
    assert result["flight_execution"] == "Not Executed"
    request["reviewer_id"] = request["prepared_by"]
    assert assess_dispatch(request)["status"] == "Blocked"
    request["reviewer_id"] = "test-reviewer"
    mission["permissions"] = [p for p in mission["permissions"] if p["kind"] != "pilot_acknowledgement"]
    blocked = assess_dispatch(request)
    assert blocked["status"] == "Blocked"
    assert any(d["kind"] == "pilot_acknowledgement" and d["state"] == "Blocked" for d in blocked["decisions"])


def test_manually_locked_double_booking_is_infeasible():
    payload = schedule_input()
    payload["missions"][0]["locked_start"] = "2026-10-25T00:00:00Z"
    second = deepcopy(payload["missions"][0])
    second["id"] = "test-operation-2"
    payload["missions"].append(second)
    assert solve_schedule(payload)["status"] == "INFEASIBLE"


@settings(max_examples=15, deadline=None)
@given(first=st.integers(1, 1200), second=st.integers(1, 1200), turnaround=st.integers(0, 120))
def test_generated_feasible_schedules_satisfy_independent_constraints(first, second, turnaround):
    payload = schedule_input()
    payload["aircraft"][0]["turnaround_seconds"] = turnaround
    payload["missions"][0]["duration_seconds"] = first
    another = deepcopy(payload["missions"][0])
    another.update(id="test-operation-2", duration_seconds=second)
    payload["missions"].append(another)
    result = solve_schedule(payload)
    assert result["status"] == "OPTIMAL"
    assert verify_schedule(payload, result)["valid"]
