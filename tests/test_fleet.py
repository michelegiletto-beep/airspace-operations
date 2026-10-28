"""Isolated artificial maintenance fixtures; never operational history."""
from copy import deepcopy

import pytest
from hypothesis import given, strategies as st

from airspace.fleet import assess_maintenance, plan_maintenance, verify_maintenance_plan


def maintenance_input():
    return {"actor_id": "test-only", "at": "2030-01-02T10:00:00Z", "forecast_end": "2030-01-02T11:00:00Z", "forecast_flight_seconds": 600, "forecast_cycles": 1,
            "program": {"id": "test-program", "version": 1, "aircraft_id": "test-aircraft", "configuration_id": "test-config", "status": "Approved", "approved_by": "test-reviewer", "valid_from": "2030-01-01T00:00:00Z", "valid_until": "2031-01-01T00:00:00Z", "tasks": [{"id": "test-inspection", "title": "Isolated software-test inspection", "source_ref": "test-only-instructions", "source_version": "test-only", "interval_calendar_days": 30, "interval_flight_seconds": 3600, "interval_cycles": 10, "required_qualifications": ["test-maintenance-scope"]}]},
            "usage": {"aircraft_id": "test-aircraft", "configuration_id": "test-config", "record_version": 1, "measured_at": "2030-01-02T09:00:00Z", "total_flight_seconds": 1000, "total_cycles": 3, "evidence_ref": "test-only-usage"},
            "completions": [{"task_id": "test-inspection", "configuration_id": "test-config", "completed_at": "2030-01-01T00:00:00Z", "total_flight_seconds": 0, "total_cycles": 0, "evidence_ref": "test-only-completion", "performed_by": "test-technician", "reviewed_by": "test-reviewer", "state": "Released"}]}


def work_order():
    return {"id": "test-work", "version": 1, "aircraft_id": "test-aircraft", "configuration_id": "test-config", "program_id": "test-program", "program_version": 1, "task_ids": ["test-inspection"], "window": {"start": "2030-01-03T10:00:00Z", "end": "2030-01-03T14:00:00Z"}, "duration_seconds": 1800, "state": "Draft", "required_qualifications": ["test-maintenance-scope"], "source_ref": "test-only-instructions"}


def maintenance_plan():
    order = work_order()
    return {"actor_id": "test-only", "work_orders": [order], "technicians": [{"id": "test-technician", "version": 1, "availability": [order["window"]], "qualifications": {"test-maintenance-scope": "2031-01-01T00:00:00Z"}, "qualification_evidence_ref": "test-only"}], "facilities": [{"id": "test-facility", "version": 1, "availability": [order["window"]], "capacity": 1, "scope_task_ids": ["test-inspection"], "evidence_ref": "test-only"}], "aircraft_busy": []}


def test_maintenance_triggers_are_source_bound_and_configuration_specific():
    request = maintenance_input()
    result = assess_maintenance(request)
    assert result["serviceable_for_forecast"]
    assert result["tasks"][0]["limits"] == {"calendar_due": "2030-01-31T00:00:00Z", "total_flight_seconds": 3600, "total_cycles": 10}
    assert result["tasks"][0]["remaining"]["flight_seconds"] == 2600
    request["usage"]["configuration_id"] = "changed-configuration"
    assert not assess_maintenance(request)["serviceable_for_forecast"]


@pytest.mark.parametrize("mutation", ["hours", "cycles", "calendar", "forecast-hours", "forecast-cycles", "forecast-calendar", "self-review", "counter-reset", "defect", "program-expiry"])
def test_due_missing_or_contradictory_maintenance_never_returns_serviceable(mutation):
    request = maintenance_input()
    if mutation == "hours": request["usage"]["total_flight_seconds"] = 3600
    elif mutation == "cycles": request["usage"]["total_cycles"] = 10
    elif mutation == "calendar": request["at"] = request["forecast_end"] = "2030-01-31T00:00:00Z"
    elif mutation == "forecast-hours": request["forecast_flight_seconds"] = 2600
    elif mutation == "forecast-cycles": request["forecast_cycles"] = 7
    elif mutation == "forecast-calendar": request["forecast_end"] = "2030-01-31T00:00:00Z"
    elif mutation == "self-review": request["completions"][0]["reviewed_by"] = "test-technician"
    elif mutation == "counter-reset": request["completions"][0]["total_cycles"] = 5
    elif mutation == "defect": request["open_safety_defects"] = ["Isolated software-test defect"]
    else: request["program"]["valid_until"] = "2030-01-02T10:30:00Z"
    assert not assess_maintenance(request)["serviceable_for_forecast"]


def test_planned_or_completed_unreleased_work_does_not_reset_utilisation():
    request = maintenance_input()
    request["usage"]["total_cycles"] = 10
    order = work_order()
    order["state"] = "Work Complete"
    request["work_orders"] = [order]
    result = assess_maintenance(request)
    assert not result["serviceable_for_forecast"]
    assert result["unavailability"][0]["state"] == "Work Complete"
    assert result["tasks"][0]["state"] == "Due"


def test_missing_program_or_usage_is_incomplete_without_default_limits():
    result = assess_maintenance({"actor_id": "test-only", "at": "2030-01-01T00:00:00Z"})
    assert result["status"] == "Incomplete"
    assert not result["serviceable_for_forecast"]
    assert result["tasks"] == []


def test_equally_recent_contradictory_completion_counters_are_not_arbitrarily_selected():
    payload = maintenance_input()
    conflicting = deepcopy(payload["completions"][0])
    conflicting.update(total_flight_seconds=500, total_cycles=1, evidence_ref="test-only-contradictory-source")
    payload["completions"].append(conflicting)
    assessment = assess_maintenance(payload)
    assert not assessment["serviceable_for_forecast"]
    assert assessment["tasks"][0]["state"] == "Contradictory Evidence"


def test_cp_sat_maintenance_avoids_aircraft_reservations_and_has_separate_verifier():
    request = maintenance_plan()
    request["aircraft_busy"] = [{"aircraft_id": "test-aircraft", "interval": {"start": "2030-01-03T10:00:00Z", "end": "2030-01-03T11:00:00Z"}, "evidence_ref": "test-only-flight-reservation"}]
    result = plan_maintenance(request)
    assert result["status"] == "OPTIMAL"
    assert result["assignments"][0]["start"] == "2030-01-03T11:00:00Z"
    assert verify_maintenance_plan(request, result)["valid"]
    result["assignments"][0].update(start="2030-01-03T10:00:00Z", end="2030-01-03T10:30:00Z")
    assert not verify_maintenance_plan(request, result)["valid"]


def test_missing_maintenance_qualification_is_infeasible():
    request = maintenance_plan()
    request["technicians"][0]["qualifications"] = {}
    assert plan_maintenance(request)["status"] == "INFEASIBLE"


@given(duration=st.integers(60, 3600))
def test_maintenance_capacity_holds_across_work_orders(duration):
    request = maintenance_plan()
    request["work_orders"][0]["duration_seconds"] = duration
    second = deepcopy(request["work_orders"][0])
    second.update(id="test-work-2", aircraft_id="test-aircraft-2")
    request["work_orders"].append(second)
    result = plan_maintenance(request)
    assert result["status"] == "OPTIMAL"
    assert verify_maintenance_plan(request, result)["valid"]
