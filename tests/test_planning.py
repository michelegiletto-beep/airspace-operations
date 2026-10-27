"""Independent persistent-reservation verification using isolated fixtures only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from airspace.identity import provision
from airspace.planning import approve_schedule, cancel_schedule
from airspace.scheduler import ScheduleRequest, solve_schedule
from airspace.storage import identifier, now, records, reservations
from test_scheduler import schedule_input


def future_input():
    day = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
    return json.loads(json.dumps(schedule_input()).replace("2026-10-25", day))


def insert_record(conn, tenant, kind, item_id, data, author_id, status="Approved"):
    row = {"id": item_id, "organisation_id": tenant, "kind": kind, "title": "Isolated test fixture " + kind, "status": status, "data": data, "version": 1, "created_by": author_id, "created_at": now(), "updated_at": now()}
    conn.execute(records.insert().values(**row))
    return row


def persist_schedule(store, author, reviewer, payload, *, persist_resources=True):
    request = ScheduleRequest.model_validate(payload)
    result = solve_schedule(request)
    assert result["status"] == "OPTIMAL"
    tenant = author["organisation_id"]
    bindings = {}
    with store.engine.begin() as conn:
        for collection, kind in ((request.missions, "mission"), (request.aircraft, "aircraft"), (request.personnel, "personnel"), (request.sites, "site")):
            for resource in collection:
                existing = conn.execute(select(records).where(records.c.id == resource.id)).mappings().first()
                if not existing:
                    insert_record(conn, tenant, kind, resource.id, {"scheduler": resource.model_dump(mode="json")}, author["id"], "Draft" if kind == "mission" else "Approved")
                bindings[resource.id] = existing["version"] if existing else 1
        for mission in request.missions:
            for permission in mission.permissions:
                receipt_id = "test-receipt-" + permission.id
                if not conn.execute(select(records.c.id).where(records.c.id == permission.id)).first():
                    insert_record(conn, tenant, "evidence", receipt_id, {"provenance": "Isolated software test; not a real authority decision", "checksum": hashlib.sha256(b"Isolated test fixture").hexdigest(), "evidence_type": "Software Test"}, author["id"])
                    insert_record(conn, tenant, "permission", permission.id, {"scheduler": permission.model_dump(mode="json"), "receipt_evidence_id": receipt_id, "permission_type": "operational_authorisation", "valid_from": permission.valid_from.isoformat(), "valid_to": permission.valid_until.isoformat(), "scope": {"configuration_id": permission.configuration_id, "route_version": permission.route_version}}, author["id"])
                bindings[permission.id] = 1
                bindings[receipt_id] = 1
        schedule_id = identifier()
        row = insert_record(conn, tenant, "schedule", schedule_id, {"input": request.model_dump(mode="json"), "result": result, "input_record_versions": bindings, "reviewer_ids": [reviewer["id"]], "_prepared_by": author["id"]}, author["id"], "Draft")
    return row


def test_transaction_reservations_prevent_double_booking(environment):
    store, _, author, reviewer, _, _ = environment
    payload = future_input()
    first = persist_schedule(store, author, reviewer, payload)
    second = persist_schedule(store, author, reviewer, payload)
    approved = approve_schedule(store, first["id"], 1, reviewer, "Isolated reservation test")
    assert approved["status"] == "Approved"
    with pytest.raises(HTTPException) as exc:
        approve_schedule(store, second["id"], 1, reviewer, "Isolated conflicting reservation")
    assert exc.value.status_code == 409
    with store.engine.connect() as conn:
        assert len(conn.execute(select(reservations)).all()) == 3
        second_state = conn.execute(select(records.c.status).where(records.c.id == second["id"])).scalar_one()
        assert second_state == "Draft"


def test_concurrent_valid_schedule_reservations_are_serialised(environment):
    store, _, author, reviewer, _, _ = environment
    payload = future_input()
    schedules = [persist_schedule(store, author, reviewer, payload) for _ in range(2)]
    def reserve(row):
        try:
            approve_schedule(store, row["id"], 1, reviewer, "Isolated concurrent reservation test")
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, schedules))
    assert sorted(outcomes) == [200, 409]
    assert store.verify_audit(author["organisation_id"])["valid"]


@pytest.mark.parametrize("kind", ["aircraft", "personnel", "site", "receipt"])
def test_changed_input_versions_and_receipts_block_approval(environment, kind):
    store, _, author, reviewer, _, _ = environment
    row = persist_schedule(store, author, reviewer, future_input())
    item_id = {"aircraft": "test-aircraft", "personnel": "test-person", "site": "test-site", "receipt": "test-receipt-test-permission"}[kind]
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == item_id).values(version=2))
    with pytest.raises(HTTPException) as exc:
        approve_schedule(store, row["id"], 1, reviewer, "Isolated stale input test")
    assert exc.value.status_code == 409
    with store.engine.connect() as conn:
        assert not conn.execute(select(reservations)).first()


def test_two_reviewers_required_before_any_reservation(environment, monkeypatch):
    store, _, author, reviewer, _, _ = environment
    second = provision(store, "Isolated software test tenant", "second-reviewer@test.invalid", "reviewer", "isolated-test-password", author["organisation_id"])
    row = persist_schedule(store, author, reviewer, future_input())
    with store.engine.begin() as conn:
        data = deepcopy(row["data"])
        data["reviewer_ids"].append(second["id"])
        conn.execute(update(records).where(records.c.id == row["id"]).values(data=data))
    monkeypatch.setenv("AIRSPACE_REQUIRE_TWO_REVIEWERS", "true")
    first_review = approve_schedule(store, row["id"], 1, reviewer, "First isolated review")
    assert first_review["status"] == "Under Review"
    with store.engine.connect() as conn:
        assert not conn.execute(select(reservations)).first()
    with pytest.raises(HTTPException):
        approve_schedule(store, row["id"], 2, reviewer, "Repeated isolated review")
    approved = approve_schedule(store, row["id"], 2, second, "Second isolated review")
    assert approved["status"] == "Approved"
    with store.engine.connect() as conn:
        assert len(conn.execute(select(reservations)).all()) == 3


def test_nonoverlap_schedules_share_same_readiness_battery_budget(environment):
    store, _, author, reviewer, _, _ = environment
    payload = future_input()
    payload["aircraft"][0]["usable_flight_seconds"] = 1000
    first = persist_schedule(store, author, reviewer, payload)
    approve_schedule(store, first["id"], 1, reviewer, "First isolated battery reservation")
    second_payload = deepcopy(payload)
    second_payload["missions"][0]["id"] = "test-operation-2"
    day = second_payload["missions"][0]["window"]["start"][:10]
    second_payload["missions"][0]["locked_start"] = day + "T01:00:00Z"
    second = persist_schedule(store, author, reviewer, second_payload)
    with pytest.raises(HTTPException) as exc:
        approve_schedule(store, second["id"], 1, reviewer, "Second isolated battery reservation")
    assert "battery/readiness budget" in exc.value.detail


def test_same_proposed_operation_cannot_be_reserved_again_in_another_time_slot(environment):
    store, _, author, reviewer, _, _ = environment
    payload = future_input()
    first = persist_schedule(store, author, reviewer, payload)
    approve_schedule(store, first["id"], 1, reviewer, "First isolated mission reservation")
    second_payload = deepcopy(payload)
    day = second_payload["missions"][0]["window"]["start"][:10]
    second_payload["missions"][0]["locked_start"] = day + "T01:00:00Z"
    # The persisted intended-operation record must reflect this new constraint,
    # preserving its identity while resetting its reviewed snapshot.
    mission = ScheduleRequest.model_validate(second_payload).missions[0]
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == mission.id).values(data={"scheduler": mission.model_dump(mode="json")}, version=2))
    second = persist_schedule(store, author, reviewer, second_payload)
    with pytest.raises(HTTPException) as exc:
        approve_schedule(store, second["id"], 1, reviewer, "Repeated isolated mission reservation")
    assert "already has a reservation" in exc.value.detail


def test_nonoverlap_schedules_share_same_personnel_duty_episode(environment):
    store, _, author, reviewer, _, _ = environment
    payload = future_input()
    payload["personnel"][0]["max_duty_seconds"] = 1200
    first = persist_schedule(store, author, reviewer, payload)
    approve_schedule(store, first["id"], 1, reviewer, "First isolated duty reservation")
    second_payload = deepcopy(payload)
    second_payload["missions"][0]["id"] = "test-operation-2"
    day = second_payload["missions"][0]["window"]["start"][:10]
    second_payload["missions"][0]["locked_start"] = day + "T01:00:00Z"
    second = persist_schedule(store, author, reviewer, second_payload)
    with pytest.raises(HTTPException) as exc:
        approve_schedule(store, second["id"], 1, reviewer, "Second isolated duty reservation")
    assert "duty episode budget" in exc.value.detail


@pytest.mark.parametrize("capacity", [1, 2])
def test_site_capacity_and_atomic_rollback_across_distinct_aircraft(environment, capacity):
    store, _, author, reviewer, _, _ = environment
    baseline = future_input()
    baseline["sites"][0]["concurrent_capacity"] = capacity
    for index in range(capacity + 1):
        payload = deepcopy(baseline)
        payload["missions"][0]["id"] = f"test-mission-capacity-{index}"
        payload["aircraft"][0]["id"] = f"test-craft-capacity-{index}"
        payload["personnel"][0]["id"] = f"test-person-capacity-{index}"
        row = persist_schedule(store, author, reviewer, payload)
        if index < capacity:
            assert approve_schedule(store, row["id"], 1, reviewer, "Isolated capacity reservation")["status"] == "Approved"
        else:
            with pytest.raises(HTTPException) as exc:
                approve_schedule(store, row["id"], 1, reviewer, "Isolated over-capacity reservation")
            assert "Site capacity" in exc.value.detail
    with store.engine.connect() as conn:
        # The failing transaction inserted aircraft/person reservations before
        # finding the site conflict; all of them must have rolled back.
        assert len(conn.execute(select(reservations)).all()) == capacity * 3


def test_cancellation_releases_transactionally_and_requires_new_reviewed_proposal(environment):
    store, _, author, reviewer, _, _ = environment
    payload = future_input()
    first = persist_schedule(store, author, reviewer, payload)
    approve_schedule(store, first["id"], 1, reviewer, "Isolated initial reservation")
    with pytest.raises(HTTPException) as stale:
        cancel_schedule(store, first["id"], 1, reviewer, "Isolated stale cancellation")
    assert stale.value.status_code == 409
    cancelled = cancel_schedule(store, first["id"], 2, reviewer, "Isolated authorised cancellation")
    assert cancelled["status"] == "Cancelled"
    assert cancelled["data"]["_cancellation"]["released_reservations"] == 3
    with store.engine.connect() as conn:
        assert not conn.execute(select(reservations).where(reservations.c.state == "Reserved")).first()
    with pytest.raises(HTTPException):
        approve_schedule(store, first["id"], 3, reviewer, "Cannot revive cancelled proposal")
    replacement = persist_schedule(store, author, reviewer, payload)
    assert approve_schedule(store, replacement["id"], 1, reviewer, "New isolated proposal review")["status"] == "Approved"
    assert store.verify_audit(author["organisation_id"])["valid"]


def test_cancellation_rejects_unauthorised_role_or_other_tenant(environment):
    store, _, author, reviewer, other, _ = environment
    row = persist_schedule(store, author, reviewer, future_input())
    with pytest.raises(HTTPException) as unauthorised:
        cancel_schedule(store, row["id"], 1, author, "Regulatory role cannot cancel")
    assert unauthorised.value.status_code == 403
    with pytest.raises(HTTPException) as cross_tenant:
        cancel_schedule(store, row["id"], 1, {**reviewer, "organisation_id": other["organisation_id"]}, "Isolated cross-tenant attempt")
    assert cross_tenant.value.status_code == 403
