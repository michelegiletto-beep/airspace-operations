"""Controlled clock and artificial records confined to maintenance tests."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from airspace.fleet import transition_work_order, maintenance_workspace
from airspace.identity import provision
from airspace.storage import records
from test_fleet import maintenance_input, work_order
from test_planning import insert_record, future_input
from airspace.scheduler import ScheduleRequest


@pytest.fixture
def maintenance_workflow(environment, monkeypatch):
    store, _, author, reviewer, _, _ = environment
    tech = provision(store, "Isolated tenant", "maintenance-technician@test.invalid", "fleet_manager", "isolated-test-password", author["organisation_id"])
    clock = {"now": datetime(2030, 1, 2, 10, tzinfo=timezone.utc)}
    class ControlledClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"].astimezone(tz) if tz else clock["now"].replace(tzinfo=None)
    monkeypatch.setattr("airspace.fleet.datetime", ControlledClock)
    base = maintenance_input()
    base["program"]["approved_by"] = reviewer["id"]
    order = work_order()
    order.update(aircraft_record_version=1, window={"start": "2030-01-02T10:00:00Z", "end": "2030-01-02T12:00:00Z"}, duration_seconds=60)
    aircraft = ScheduleRequest.model_validate(future_input()).aircraft[0].model_dump(mode="json")
    technician = {"id": "test-maintainer", "version": 1, "availability": [order["window"]], "qualifications": {"test-maintenance-scope": "2031-01-01T00:00:00Z"}, "qualification_evidence_ref": "test-only"}
    facility = {"id": "test-maintenance-site", "version": 1, "availability": [order["window"]], "capacity": 1, "scope_task_ids": ["test-inspection"], "evidence_ref": "test-only"}
    tenant = author["organisation_id"]
    with store.engine.begin() as conn:
        insert_record(conn, tenant, "aircraft", "test-aircraft", {"scheduler": aircraft, "maintenance_program_id": "test-program", "utilisation": base["usage"]}, tech["id"])
        insert_record(conn, tenant, "maintenance_program", "test-program", {"program": base["program"], "_approvals": [{"actor_id": reviewer["id"]}]}, tech["id"])
        insert_record(conn, tenant, "personnel", technician["id"], {"user_id": tech["id"], "maintenance_technician": technician}, tech["id"])
        insert_record(conn, tenant, "personnel", "test-maintenance-reviewer", {"user_id": reviewer["id"], "maintenance_technician": {**technician, "id": "test-maintenance-reviewer"}}, tech["id"])
        insert_record(conn, tenant, "site", facility["id"], {"maintenance_facility": facility}, tech["id"])
        insert_record(conn, tenant, "evidence", "test-completion-evidence", {"checksum": "0" * 64, "provenance": "Isolated software test", "evidence_type": "Software Test", "_approvals": [{"actor_id": reviewer["id"]}]}, tech["id"])
        insert_record(conn, tenant, "maintenance_work_order", order["id"], {"work_order": order, "reviewer_ids": [reviewer["id"]], "_prepared_by": tech["id"]}, tech["id"], "Draft")
    return store, tech, reviewer, clock


def schedule_and_start(fixture):
    store, tech, reviewer, clock = fixture
    scheduled = transition_work_order(store, "test-work", tech, {"expected_version": 1, "target": "Scheduled", "reason": "Isolated maintenance scheduling", "technician_id": "test-maintainer", "facility_id": "test-maintenance-site", "scheduled_start": "2030-01-02T10:00:00Z", "scheduled_end": "2030-01-02T10:01:00Z"})
    return transition_work_order(store, scheduled["id"], tech, {"expected_version": scheduled["version"], "target": "In Progress", "reason": "Isolated recorded work start"})


def complete_and_submit(fixture):
    store, tech, reviewer, clock = fixture
    started = schedule_and_start(fixture)
    assert started["data"]["work_order"]["actual_end"] is None
    clock["now"] += timedelta(seconds=60)
    completion = {"task_id": "test-inspection", "configuration_id": "test-config", "completed_at": clock["now"].isoformat(), "total_flight_seconds": 1000, "total_cycles": 3, "evidence_ref": "test-completion-evidence", "performed_by": tech["id"], "reviewed_by": None, "state": "Recorded"}
    completed = transition_work_order(store, "test-work", tech, {"expected_version": started["version"], "target": "Work Complete", "reason": "Isolated recorded completion", "completions": [completion]})
    return transition_work_order(store, "test-work", tech, {"expected_version": completed["version"], "target": "Under Review", "reason": "Isolated review request"})


def add_second_reviewer(fixture):
    store, tech, _, _ = fixture
    second = provision(store, "Isolated tenant", "second-maintenance-reviewer@test.invalid", "reviewer", "isolated-test-password", tech["organisation_id"])
    with store.engine.begin() as conn:
        row = conn.execute(select(records).where(records.c.id == "test-work")).mappings().one()
        data = deepcopy(row["data"])
        data["reviewer_ids"].append(second["id"])
        conn.execute(update(records).where(records.c.id == row["id"]).values(data=data))
        first_person = conn.execute(select(records).where(records.c.id == "test-maintenance-reviewer")).mappings().one()
        insert_record(conn, tech["organisation_id"], "personnel", "test-second-maintenance-reviewer", {**first_person["data"], "user_id": second["id"]}, tech["id"])
    return second


def test_real_workflow_completion_is_distinct_from_serviceability_and_flight_release(maintenance_workflow):
    store, tech, reviewer, clock = maintenance_workflow
    submitted = complete_and_submit(maintenance_workflow)
    released = transition_work_order(store, "test-work", reviewer, {"expected_version": submitted["version"], "target": "Released", "reason": "Isolated independent maintenance review"})
    assert released["status"] == "Released"
    assert released["data"]["work_order"]["completion"][0]["reviewed_by"] == reviewer["id"]
    with store.engine.connect() as conn:
        aircraft = conn.execute(select(records).where(records.c.id == "test-aircraft")).mappings().one()
        assert aircraft["status"] == "Suspended"
        assert not aircraft["data"]["scheduler"]["serviceable"]
        assert aircraft["data"]["maintenance_completions"][0]["state"] == "Released"
    workspace = maintenance_workspace(store, tech, "test-aircraft")
    assert workspace["program_record"]["id"] == "test-program"
    assert store.verify_audit(tech["organisation_id"])["valid"]


def test_program_revision_and_qualification_changes_block_start_and_release(maintenance_workflow):
    store, tech, reviewer, clock = maintenance_workflow
    scheduled = transition_work_order(store, "test-work", tech, {"expected_version": 1, "target": "Scheduled", "reason": "Isolated scheduling", "technician_id": "test-maintainer", "facility_id": "test-maintenance-site", "scheduled_start": "2030-01-02T10:00:00Z", "scheduled_end": "2030-01-02T10:01:00Z"})
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == "test-program").values(version=2))
    with pytest.raises(HTTPException) as stale:
        transition_work_order(store, "test-work", tech, {"expected_version": scheduled["version"], "target": "In Progress", "reason": "Stale program test"})
    assert stale.value.status_code == 409
    # Cancellation remains possible even when its old planning inputs changed.
    assert transition_work_order(store, "test-work", tech, {"expected_version": scheduled["version"], "target": "Cancelled", "reason": "Cancel stale unstarted maintenance"})["status"] == "Cancelled"


def test_changed_maintenance_facility_cannot_start_old_assignment(maintenance_workflow):
    store, tech, _, _ = maintenance_workflow
    scheduled = transition_work_order(store, "test-work", tech, {"expected_version": 1, "target": "Scheduled", "reason": "Isolated facility planning", "technician_id": "test-maintainer", "facility_id": "test-maintenance-site", "scheduled_start": "2030-01-02T10:00:00Z", "scheduled_end": "2030-01-02T10:01:00Z"})
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == "test-maintenance-site").values(status="Suspended", version=2))
    with pytest.raises(HTTPException) as unavailable:
        transition_work_order(store, "test-work", tech, {"expected_version": scheduled["version"], "target": "In Progress", "reason": "Attempt start at changed facility"})
    assert unavailable.value.status_code == 409
    assert "facility changed" in unavailable.value.detail


def test_unqualified_reviewer_cannot_return_maintenance_order_to_released(maintenance_workflow):
    store, tech, reviewer, clock = maintenance_workflow
    submitted = complete_and_submit(maintenance_workflow)
    with store.engine.begin() as conn:
        row = conn.execute(select(records).where(records.c.id == "test-maintenance-reviewer")).mappings().one()
        data = deepcopy(row["data"])
        data["maintenance_technician"]["qualifications"] = {}
        conn.execute(update(records).where(records.c.id == row["id"]).values(data=data, version=2))
    with pytest.raises(HTTPException) as unqualified:
        transition_work_order(store, "test-work", reviewer, {"expected_version": submitted["version"], "target": "Released", "reason": "Isolated unqualified review attempt"})
    assert unqualified.value.status_code == 422


def test_second_review_policy_applies_to_maintenance_release(maintenance_workflow, monkeypatch):
    store, tech, reviewer, clock = maintenance_workflow
    submitted = complete_and_submit(maintenance_workflow)
    second = provision(store, "Isolated tenant", "second-maintenance-reviewer@test.invalid", "reviewer", "isolated-test-password", tech["organisation_id"])
    with store.engine.begin() as conn:
        row = conn.execute(select(records).where(records.c.id == "test-work")).mappings().one()
        data = deepcopy(row["data"])
        data["reviewer_ids"].append(second["id"])
        conn.execute(update(records).where(records.c.id == row["id"]).values(data=data))
        first_person = conn.execute(select(records).where(records.c.id == "test-maintenance-reviewer")).mappings().one()
        insert_record(conn, tech["organisation_id"], "personnel", "test-second-maintenance-reviewer", {**first_person["data"], "user_id": second["id"]}, tech["id"])
    monkeypatch.setenv("AIRSPACE_REQUIRE_TWO_REVIEWERS", "true")
    first = transition_work_order(store, "test-work", reviewer, {"expected_version": submitted["version"], "target": "Released", "reason": "First isolated maintenance review"})
    assert first["status"] == "Under Review"
    second_review = transition_work_order(store, "test-work", second, {"expected_version": first["version"], "target": "Released", "reason": "Second isolated maintenance review"})
    assert second_review["status"] == "Released"


def test_returned_completion_cannot_reuse_earlier_review_signature(maintenance_workflow, monkeypatch):
    store, tech, reviewer, _ = maintenance_workflow
    submitted = complete_and_submit(maintenance_workflow)
    second = add_second_reviewer(maintenance_workflow)
    monkeypatch.setenv("AIRSPACE_REQUIRE_TWO_REVIEWERS", "true")
    first = transition_work_order(store, "test-work", reviewer, {"expected_version": submitted["version"], "target": "Released", "reason": "Initial isolated review"})
    replacement = deepcopy(submitted["data"]["work_order"]["completion"])
    replacement[0]["evidence_ref"] = "test-replacement-evidence"
    with store.engine.begin() as conn:
        insert_record(conn, tech["organisation_id"], "evidence", "test-replacement-evidence", {"checksum": "1" * 64, "provenance": "Isolated replacement source", "evidence_type": "Software Test", "_approvals": [{"actor_id": reviewer["id"]}]}, tech["id"])
    returned = transition_work_order(store, "test-work", tech, {"expected_version": first["version"], "target": "Work Complete", "reason": "Replace completion source in isolated test", "completions": replacement})
    assert returned["data"]["_maintenance_approvals"] == []
    resubmitted = transition_work_order(store, "test-work", tech, {"expected_version": returned["version"], "target": "Under Review", "reason": "Review replaced evidence"})
    reviewed = transition_work_order(store, "test-work", second, {"expected_version": resubmitted["version"], "target": "Released", "reason": "First review of new evidence"})
    assert reviewed["status"] == "Under Review"
    assert len(reviewed["data"]["_maintenance_approvals"]) == 1
    released = transition_work_order(store, "test-work", reviewer, {"expected_version": reviewed["version"], "target": "Released", "reason": "Second review of new evidence"})
    assert released["status"] == "Released"


@pytest.mark.parametrize("changed", ["evidence", "prior-reviewer"])
def test_changed_review_inputs_require_fresh_maintenance_signatures(maintenance_workflow, monkeypatch, changed):
    store, _, reviewer, _ = maintenance_workflow
    submitted = complete_and_submit(maintenance_workflow)
    second = add_second_reviewer(maintenance_workflow)
    monkeypatch.setenv("AIRSPACE_REQUIRE_TWO_REVIEWERS", "true")
    first = transition_work_order(store, "test-work", reviewer, {"expected_version": submitted["version"], "target": "Released", "reason": "First isolated signature"})
    with store.engine.begin() as conn:
        item_id = "test-completion-evidence" if changed == "evidence" else "test-maintenance-reviewer"
        conn.execute(update(records).where(records.c.id == item_id).values(version=2))
    with pytest.raises(HTTPException) as stale:
        transition_work_order(store, "test-work", second, {"expected_version": first["version"], "target": "Released", "reason": "Attempt to reuse stale first signature"})
    assert stale.value.status_code == 409
