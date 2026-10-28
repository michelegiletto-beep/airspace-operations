"""Bilateral sharing tests in temporary stores; all aircraft are test fixtures."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from airspace.identity import provision
from airspace.scheduler import ScheduleRequest, solve_schedule
from airspace.sharing import create_agreement, decide_agreement, list_agreements, reserve_physical_aircraft, release_physical_reservations, check_shared_aircraft, validate_aircraft_identity
from airspace.storage import records, fleet_reservations, reservations, resource_locks, identifier
from test_planning import future_input, insert_record
from test_fleet import maintenance_input


@pytest.fixture
def shared_fixture(environment):
    store, _, author, reviewer, other, _ = environment
    owner = provision(store, "Isolated owner", "owner-fleet@test.invalid", "fleet_manager", "isolated-test-password", author["organisation_id"])
    operator = provision(store, "Isolated operator", "operator-fleet@test.invalid", "fleet_manager", "isolated-test-password", other["organisation_id"])
    payload = future_input()
    original = ScheduleRequest.model_validate(payload).aircraft[0]
    baseline = original.availability[0].start - timedelta(days=1)
    maintenance = maintenance_input()
    maintenance["program"].update(approved_by=reviewer["id"], valid_from=baseline.isoformat(), valid_until=(baseline + timedelta(days=365)).isoformat())
    maintenance["program"]["tasks"][0].update(interval_calendar_days=300, interval_flight_seconds=100000, interval_cycles=1000)
    maintenance["usage"].update(measured_at=baseline.isoformat(), total_flight_seconds=0, total_cycles=0)
    maintenance["completions"][0].update(completed_at=baseline.isoformat(), performed_by=owner["id"], reviewed_by=reviewer["id"])
    maintenance["usage"]["evidence_version"] = maintenance["completions"][0]["evidence_version"] = 1
    with store.engine.begin() as conn:
        for source_ref in (maintenance["usage"]["evidence_ref"], maintenance["completions"][0]["evidence_ref"]):
            insert_record(conn, owner["organisation_id"], "evidence", source_ref, {"checksum": "0" * 64, "provenance": "Isolated software test source; no actual maintenance", "evidence_type": "Software Test", "_approvals": [{"actor_id": reviewer["id"]}]}, owner["id"])
        insert_record(conn, owner["organisation_id"], "maintenance_program", "test-program", {"program": maintenance["program"], "_approvals": [{"actor_id": reviewer["id"]}]}, owner["id"])
        insert_record(conn, owner["organisation_id"], "aircraft", original.id, {"scheduler": original.model_dump(mode="json"), "maintenance_program_id": "test-program", "utilisation": maintenance["usage"], "maintenance_completions": maintenance["completions"], "confidential_customer": "PRIVATE-TEST-MARKER", "private_authority_correspondence": "PRIVATE-TEST-CORRESPONDENCE"}, owner["id"])
    terms = {"owner_organisation_id": owner["organisation_id"], "operator_organisation_id": operator["organisation_id"], "aircraft_id": original.id, "aircraft_version": 1, "configuration_id": original.configuration_id, "agreement_reference": "Isolated software-test agreement", "valid_from": original.availability[0].start.isoformat(), "valid_until": original.availability[0].end.isoformat(), "countries": ["LU"], "route_versions": ["test-route-1"], "permitted_purposes": ["Inspection"], "maintenance_responsible_organisation_id": owner["organisation_id"], "operating_responsibility_ref": "test-only", "maintenance_responsibility_ref": "test-only", "insurance_evidence_ref": "test-only", "data_sharing_rights_ref": "test-only"}
    return store, owner, operator, payload, terms


def accepted(shared_fixture):
    store, owner, operator, payload, terms = shared_fixture
    row = create_agreement(store, owner, terms)
    offered = decide_agreement(store, row["id"], owner, "offer", 1, "Isolated offer")
    return decide_agreement(store, row["id"], operator, "accept", offered["version"], "Isolated counterpart acceptance")


def borrowed_request(shared_fixture, agreement, mission_id="test-borrower-mission", hour=0):
    store, owner, operator, payload, terms = shared_fixture
    request = deepcopy(payload)
    request["actor_id"] = operator["id"]
    request["missions"][0]["id"] = mission_id
    request["aircraft"][0]["id"] = "test-borrowed-alias"
    day = request["missions"][0]["window"]["start"][:10]
    request["missions"][0]["locked_start"] = f"{day}T{hour:02d}:00:00Z"
    typed = ScheduleRequest.model_validate(request)
    result = solve_schedule(typed)
    with store.engine.begin() as conn:
        if not conn.execute(select(records.c.id).where(records.c.id == "test-borrowed-alias")).first():
            insert_record(conn, operator["organisation_id"], "aircraft", "test-borrowed-alias", {"scheduler": typed.aircraft[0].model_dump(mode="json"), "sharing_agreement_id": agreement["id"], "owner_organisation_id": owner["organisation_id"], "owner_aircraft_id": terms["aircraft_id"]}, operator["id"])
        insert_record(conn, operator["organisation_id"], "mission", mission_id, {"purpose": "Inspection", "coordination": {"segments": [{"country": "LU"}]}}, operator["id"], "Draft")
        schedule_id = "test-shared-schedule-" + mission_id
        insert_record(conn, operator["organisation_id"], "schedule", schedule_id, {"input": typed.model_dump(mode="json"), "result": result}, operator["id"], "Draft")
    return typed, result, schedule_id


def test_private_drafts_and_owner_records_never_cross_tenant_boundary(shared_fixture):
    store, owner, operator, _, terms = shared_fixture
    draft = create_agreement(store, owner, terms)
    assert list_agreements(store, operator)["items"] == []
    assert len(list_agreements(store, owner)["items"]) == 1
    offered = decide_agreement(store, draft["id"], owner, "offer", 1, "Isolated offer")
    import json
    counterpart = json.dumps(list_agreements(store, operator))
    assert "PRIVATE-TEST" not in counterpart
    assert "private_authority_correspondence" not in counterpart
    assert "asset_snapshot" in counterpart
    with pytest.raises(HTTPException):
        decide_agreement(store, offered["id"], owner, "accept", 2, "Owner cannot accept for counterpart")


def test_unaccepted_agreement_cannot_reserve_physical_aircraft(shared_fixture):
    store, owner, operator, _, terms = shared_fixture
    draft = create_agreement(store, owner, terms)
    offered = decide_agreement(store, draft["id"], owner, "offer", 1, "Isolated offer")
    request, result, schedule_id = borrowed_request(shared_fixture, offered)
    with pytest.raises(HTTPException) as exc:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
    assert exc.value.status_code == 422


def test_owner_and_borrower_cannot_double_book_same_physical_asset(shared_fixture):
    store, owner, operator, payload, _ = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    with store.engine.begin() as conn:
        reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
        own_request = ScheduleRequest.model_validate(payload)
        own_result = solve_schedule(own_request)
        insert_record(conn, owner["organisation_id"], "schedule", "test-owner-schedule", {}, owner["id"], "Draft")
    with pytest.raises(HTTPException) as exc:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, owner["organisation_id"], own_request, own_result, "test-owner-schedule")
    assert exc.value.status_code == 409
    assert "physical aircraft" in exc.value.detail


def test_cross_operator_readiness_budget_is_not_reset_by_a_different_schedule(shared_fixture):
    store, owner, operator, payload, terms = shared_fixture
    payload["aircraft"][0]["usable_flight_seconds"] = 1000
    with store.engine.begin() as conn:
        original = conn.execute(select(records).where(records.c.id == terms["aircraft_id"])).mappings().one()
        conn.execute(update(records).where(records.c.id == terms["aircraft_id"]).values(data={**original["data"], "scheduler": ScheduleRequest.model_validate(payload).aircraft[0].model_dump(mode="json")}))
    agreement = accepted(shared_fixture)
    first = borrowed_request(shared_fixture, agreement, "test-first", 0)
    with store.engine.begin() as conn:
        reserve_physical_aircraft(conn, operator["organisation_id"], *first[:2], first[2])
    second = borrowed_request(shared_fixture, agreement, "test-second", 1)
    with pytest.raises(HTTPException) as exc:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], *second[:2], second[2])
    assert "flight-time budget" in exc.value.detail


def test_revocation_suspends_and_explicit_cancellation_releases_resource_exclusion(shared_fixture):
    store, owner, operator, _, _ = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    with store.engine.begin() as conn:
        reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
        insert_record(conn, operator["organisation_id"], "dispatch_release", "test-shared-internal-release", {"schedule_id": schedule_id, "mission_id": request.missions[0].id, "private_borrower_notes": "PRIVATE-OPERATOR-TEST-NOTE"}, operator["id"], "Internally Released")
    decide_agreement(store, agreement["id"], owner, "revoke", agreement["version"], "Isolated revocation")
    with store.engine.begin() as conn:
        assert conn.execute(select(fleet_reservations.c.state)).scalar_one() == "Suspended"
        assert conn.execute(select(records.c.status).where(records.c.id == "test-shared-internal-release")).scalar_one() == "Suspended"
        assert release_physical_reservations(conn, operator["organisation_id"], schedule_id) == 1
        assert conn.execute(select(fleet_reservations.c.state)).scalar_one() == "Released"
    assert store.verify_audit(owner["organisation_id"])["valid"]
    assert store.verify_audit(operator["organisation_id"])["valid"]


def test_owner_configuration_change_invalidates_accepted_agreement(shared_fixture):
    store, _, operator, _, terms = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == terms["aircraft_id"]).values(version=2))
    with pytest.raises(HTTPException) as exc:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
    assert exc.value.status_code == 409


def test_agreement_scope_expiry_and_owner_maintenance_are_hard_blockers(shared_fixture):
    store, owner, operator, _, terms = shared_fixture
    terms["valid_until"] = terms["valid_from"][:10] + "T00:05:00Z"
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    with pytest.raises(HTTPException) as expiry:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
    assert "outside agreement dates" in expiry.value.detail


def test_shared_country_and_purpose_require_explicit_agreement_scope(shared_fixture):
    store, _, operator, _, _ = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == request.missions[0].id).values(data={"purpose": "Unpermitted test purpose", "coordination": {"segments": [{"country": "IT"}]}}))
    with pytest.raises(HTTPException) as scope:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
    assert "country segments" in scope.value.detail


def test_owning_organisation_scheduled_maintenance_blocks_borrower(shared_fixture):
    store, owner, operator, _, terms = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    with store.engine.begin() as conn:
        insert_record(conn, owner["organisation_id"], "maintenance_work_order", "test-owner-maintenance", {"work_order": {"aircraft_id": terms["aircraft_id"], "window": request.missions[0].window.model_dump(mode="json")}}, owner["id"], "Scheduled")
    with pytest.raises(HTTPException) as blocked:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
    assert "owner's maintenance" in blocked.value.detail


def test_counterpart_can_reject_offer_without_accepting_obligations(shared_fixture):
    store, owner, operator, _, terms = shared_fixture
    row = create_agreement(store, owner, terms)
    decide_agreement(store, row["id"], owner, "offer", 1, "Isolated offer")
    rejected = decide_agreement(store, row["id"], operator, "reject", 2, "Isolated rejection")
    assert rejected["state"] == "Rejected"
    assert rejected["accepted_actor_id"] is None


def test_alias_identity_admission_requires_acceptance_and_cannot_strip_owner_binding(shared_fixture):
    store, owner, operator, payload, terms = shared_fixture
    draft = create_agreement(store, owner, terms)
    offered = decide_agreement(store, draft["id"], owner, "offer", 1, "Isolated offer")
    data = {"sharing_agreement_id": offered["id"], "owner_organisation_id": owner["organisation_id"], "owner_aircraft_id": terms["aircraft_id"], "configuration_id": terms["configuration_id"]}
    with store.engine.connect() as conn:
        with pytest.raises(HTTPException):
            validate_aircraft_identity(conn, operator["organisation_id"], data)
    agreement = decide_agreement(store, offered["id"], operator, "accept", 2, "Isolated acceptance")
    with store.engine.connect() as conn:
        assert validate_aircraft_identity(conn, operator["organisation_id"], data)["agreement_version"] == agreement["version"]
        current = {"data": data}
        for field in ("sharing_agreement_id", "owner_organisation_id", "owner_aircraft_id"):
            removed = {key: value for key, value in data.items() if key != field}
            with pytest.raises(HTTPException) as stripped:
                validate_aircraft_identity(conn, operator["organisation_id"], removed, current)
            assert stripped.value.status_code == 422
        with pytest.raises(HTTPException):
            validate_aircraft_identity(conn, operator["organisation_id"], data, {"data": {"configuration_id": terms["configuration_id"]}})
        with pytest.raises(HTTPException):
            validate_aircraft_identity(conn, owner["organisation_id"], data)
        with pytest.raises(HTTPException):
            validate_aircraft_identity(conn, operator["organisation_id"], {**data, "configuration_id": "different-configuration"}, current)


def test_owner_readiness_is_rechecked_after_acquiring_physical_lock(shared_fixture, monkeypatch):
    from airspace import sharing
    store, _, operator, _, terms = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    original_lock = sharing._lock_resource
    def inject_revision(conn, owner, asset):
        original_lock(conn, owner, asset)
        conn.execute(update(records).where(records.c.id == asset).values(version=2))
    monkeypatch.setattr(sharing, "_lock_resource", inject_revision)
    with pytest.raises(HTTPException) as stale:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
    assert stale.value.status_code == 409
    with store.engine.connect() as conn:
        assert not conn.execute(select(fleet_reservations)).first()


def test_read_only_shared_readiness_does_not_mutate_lock_or_agreement_state(shared_fixture):
    store, _, operator, _, _ = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, _ = borrowed_request(shared_fixture, agreement)
    from datetime import datetime
    assignment = result["assignments"][0]
    with store.engine.connect() as conn:
        before = conn.execute(select(resource_locks.c.generation)).scalars().all()
        identity = check_shared_aircraft(conn, operator["organisation_id"], request.aircraft[0], request.missions[0], datetime.fromisoformat(assignment["start"].replace("Z", "+00:00")), datetime.fromisoformat(assignment["end"].replace("Z", "+00:00")))
        after = conn.execute(select(resource_locks.c.generation)).scalars().all()
    assert before == after
    assert identity["agreement_id"] == agreement["id"]


def test_owner_maintenance_hour_trigger_applies_across_borrower_schedules(shared_fixture):
    store, _, operator, _, _ = shared_fixture
    with store.engine.begin() as conn:
        row = conn.execute(select(records).where(records.c.id == "test-program")).mappings().one()
        data = deepcopy(row["data"])
        data["program"]["tasks"][0]["interval_flight_seconds"] = 1000
        conn.execute(update(records).where(records.c.id == row["id"]).values(data=data))
    agreement = accepted(shared_fixture)
    first = borrowed_request(shared_fixture, agreement, "test-maint-first", 0)
    with store.engine.begin() as conn:
        reserve_physical_aircraft(conn, operator["organisation_id"], *first[:2], first[2])
    second = borrowed_request(shared_fixture, agreement, "test-maint-second", 1)
    with pytest.raises(HTTPException) as due:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], *second[:2], second[2])
    assert "owner's maintenance readiness" in due.value.detail


def test_mirrored_legacy_owner_reservation_is_not_charged_twice(shared_fixture):
    store, owner, operator, payload, terms = shared_fixture
    payload["aircraft"][0]["usable_flight_seconds"] = 1300
    with store.engine.begin() as conn:
        row = conn.execute(select(records).where(records.c.id == terms["aircraft_id"])).mappings().one()
        conn.execute(update(records).where(records.c.id == row["id"]).values(data={**row["data"], "scheduler": ScheduleRequest.model_validate(payload).aircraft[0].model_dump(mode="json")}))
    agreement = accepted(shared_fixture)
    own_request = ScheduleRequest.model_validate(payload)
    own_result = solve_schedule(own_request)
    with store.engine.begin() as conn:
        insert_record(conn, owner["organisation_id"], "schedule", "test-legacy-mirrored", {"input_record_versions": {terms["aircraft_id"]: 1}, "result": own_result}, owner["id"], "Approved")
        reserve_physical_aircraft(conn, owner["organisation_id"], own_request, own_result, "test-legacy-mirrored")
        assignment = own_result["assignments"][0]
        conn.execute(reservations.insert().values(id=identifier(), organisation_id=owner["organisation_id"], schedule_id="test-legacy-mirrored", mission_id=assignment["mission_id"], resource_kind="aircraft", resource_id=terms["aircraft_id"], start=assignment["start"].replace("Z", "+00:00"), end=assignment["end"].replace("Z", "+00:00"), state="Reserved"))
    borrowed = borrowed_request(shared_fixture, agreement, "test-after-mirrored", 1)
    with store.engine.begin() as conn:
        reserve_physical_aircraft(conn, operator["organisation_id"], *borrowed[:2], borrowed[2])
        assert len(conn.execute(select(fleet_reservations)).all()) == 2


def test_concurrent_cross_schedule_shared_reservations_have_one_winner(shared_fixture):
    store, _, operator, _, _ = shared_fixture
    agreement = accepted(shared_fixture)
    proposals = [borrowed_request(shared_fixture, agreement, f"test-concurrent-{index}") for index in range(2)]
    def reserve(proposal):
        try:
            with store.engine.begin() as conn:
                reserve_physical_aircraft(conn, operator["organisation_id"], *proposal[:2], proposal[2])
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, proposals)) == [200, 409]


@pytest.mark.parametrize("dependency", ["test-program", "test-only-completion", "test-only-usage", "test-only-instructions"])
def test_owner_maintenance_source_change_invalidates_only_explicit_release_dependants(shared_fixture, dependency):
    from airspace.fleet import lock_maintenance_dependency_mutation, suspend_maintenance_dependants
    store, owner, operator, _, terms = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    with store.engine.begin() as conn:
        reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
        insert_record(conn, operator["organisation_id"], "dispatch_release", "test-affected-borrower-release", {"schedule_id": schedule_id, "mission_id": request.missions[0].id}, operator["id"], "Internally Released")
        insert_record(conn, operator["organisation_id"], "dispatch_release", "test-unrelated-borrower-release", {"schedule_id": "unrelated-test-schedule", "mission_id": "unrelated-test-mission", "private_notes": "PRIVATE-UNRELATED-TEST-RECORD"}, operator["id"], "Internally Released")
        insert_record(conn, owner["organisation_id"], "dispatch_release", "test-owner-release", {"record_versions": {terms["aircraft_id"]: 1}}, owner["id"], "Internally Released")
        if dependency != "test-program" and not conn.execute(select(records.c.id).where(records.c.id == dependency)).first():
            insert_record(conn, owner["organisation_id"], "evidence", dependency, {"checksum": "0" * 64, "provenance": "Isolated source test", "evidence_type": "Software Test"}, owner["id"])
    with store.engine.begin() as conn:
        assert lock_maintenance_dependency_mutation(conn, owner["organisation_id"], dependency) == [terms["aircraft_id"]]
        conn.execute(update(records).where(records.c.id == dependency).values(status="Suspended", version=2))
        assert suspend_maintenance_dependants(conn, store, owner["organisation_id"], dependency, owner, "An owner maintenance source changed in an isolated test") == 2
        assert conn.execute(select(records.c.status).where(records.c.id == "test-affected-borrower-release")).scalar_one() == "Suspended"
        assert conn.execute(select(records.c.status).where(records.c.id == "test-owner-release")).scalar_one() == "Suspended"
        assert conn.execute(select(records.c.status).where(records.c.id == "test-unrelated-borrower-release")).scalar_one() == "Internally Released"
        if dependency == "test-only-instructions":
            program = conn.execute(select(records).where(records.c.id == "test-program")).mappings().one()
            assert program["status"] == "Suspended" and program["version"] == 2
            assert program["data"]["program"]["status"] == "Suspended"
            assert program["data"]["_source_suspension"]["source_record_id"] == dependency
    assert store.verify_audit(owner["organisation_id"])["valid"]
    assert store.verify_audit(operator["organisation_id"])["valid"]


@pytest.mark.parametrize("source_kind", ["usage", "completion"])
@pytest.mark.parametrize("mutation", ["suspended", "revised"])
def test_owner_maintenance_cannot_reuse_changed_source_for_new_borrowing(shared_fixture, source_kind, mutation):
    store, _, operator, _, _ = shared_fixture
    agreement = accepted(shared_fixture)
    request, result, schedule_id = borrowed_request(shared_fixture, agreement)
    source_ref = "test-only-usage" if source_kind == "usage" else "test-only-completion"
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == source_ref).values(
            status="Suspended" if mutation == "suspended" else "Approved", version=2))
    with pytest.raises(HTTPException) as blocked:
        with store.engine.begin() as conn:
            reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
    assert blocked.value.status_code == 422
    assert "maintenance readiness evidence" in blocked.value.detail
