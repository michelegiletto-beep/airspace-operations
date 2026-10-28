"""Internal-release verification with isolated fixtures, no real flight records."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, update

from airspace.dispatch import acknowledge_pilot, release_dispatch, suspend_dispatch_dependencies
from airspace.europe import CrossBorderPlan, assess_cross_border
from airspace.identity import provision
from airspace.planning import approve_schedule
from airspace.storage import records, reservations, fleet_reservations
from test_planning import future_input, insert_record, persist_schedule


def dispatch_fixture(environment):
    store, _, author, reviewer, _, _ = environment
    pilot = provision(store, "Isolated test tenant", "dispatch-pilot@test.invalid", "pilot", "isolated-test-password", author["organisation_id"])
    payload = future_input()
    actual_past = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    for feed in ("weather", "airspace"):
        payload["missions"][0][feed]["observed_at"] = actual_past.isoformat()
    row = persist_schedule(store, author, reviewer, payload)
    assignment = row["data"]["result"]["assignments"][0]
    mission = row["data"]["input"]["missions"][0]
    tenant = author["organisation_id"]
    country_review = {"id": "test-country-review", "version": 1, "country": "LU", "pack_version": "test-only", "status": "Validated", "valid_from": actual_past.isoformat(), "valid_until": mission["window"]["end"], "framework": "EU UAS", "source_refs": ["test-only"], "reviewed_by": reviewer["id"], "applicability_review_ref": "test-only"}
    country_instrument = {"id": "test-country-instrument", "version": 1, "kind": "operational_authorisation", "issuer": "Isolated test authority", "issuing_country": "LU", "operation_countries": ["LU"], "operator_organisation_id": tenant, "configuration_id": mission["configuration_id"], "route_version": mission["route_version"], "status": "Approved", "valid_from": actual_past.isoformat(), "valid_until": mission["window"]["end"], "evidence_ref": "test-only", "legal_source_ref": "test-only"}
    coordination = CrossBorderPlan.model_validate({"actor_id": author["id"], "mission_id": mission["id"], "mission_version": 1, "operator_organisation_id": tenant, "registration_country": "LU", "configuration_id": mission["configuration_id"], "route_version": mission["route_version"], "operation_interval": {"start": assignment["start"], "end": assignment["end"]}, "segments": [{"id": "test-LU-segment", "country": "LU", "interval": {"start": assignment["start"], "end": assignment["end"]}, "country_review_id": country_review["id"], "country_review_version": 1, "legal_route": "Operational Authorisation", "permission_requirements_reviewed": True, "required_instrument_kinds": ["operational_authorisation"], "instrument_ids": [country_instrument["id"]], "local_conditions_review_ref": "test-only", "local_mitigations_ref": "test-only", "source_freshness_review_ref": "test-only"}], "country_reviews": [country_review], "instruments": [country_instrument], "handovers": []})
    with store.engine.begin() as conn:
        insert_record(conn, tenant, "country_review", country_review["id"], {"country_review": coordination.country_reviews[0].model_dump(mode="json")}, author["id"])
        insert_record(conn, tenant, "country_instrument", country_instrument["id"], {"instrument": coordination.instruments[0].model_dump(mode="json")}, author["id"])
        insert_record(conn, tenant, "procedure", "test-dispatch-policy", {"dispatch_policy": {"maximum_lead_seconds": 5 * 86400, "validity_seconds": 120, "source_ref": "test-only-approved-policy"}, "_approvals": [{"actor_id": reviewer["id"]}]}, author["id"])
        insert_record(conn, tenant, "risk_assessment", "test-safety-case", {"configuration_id": mission["configuration_id"], "route_version": mission["route_version"], "_approvals": [{"actor_id": reviewer["id"]}]}, author["id"])
        mission_row = conn.execute(select(records).where(records.c.id == mission["id"])).mappings().one()
        conn.execute(update(records).where(records.c.id == mission["id"]).values(data={**mission_row["data"], "coordination": coordination.model_dump(mode="json"), "dispatch_procedure_id": "test-dispatch-policy", "safety_review_id": "test-safety-case"}))
        person = conn.execute(select(records).where(records.c.id == "test-person")).mappings().one()
        conn.execute(update(records).where(records.c.id == "test-person").values(data={**person["data"], "user_id": pilot["id"]}))
        aircraft = conn.execute(select(records).where(records.c.id == "test-aircraft")).mappings().one()
        data = deepcopy(aircraft["data"])
        data["utilisation"]["measured_at"] = actual_past.isoformat()
        data["maintenance_completions"][0]["completed_at"] = actual_past.isoformat()
        conn.execute(update(records).where(records.c.id == "test-aircraft").values(data=data))
    reserved = approve_schedule(store, row["id"], 1, reviewer, "Isolated initial resource review")
    return store, author, reviewer, pilot, reserved, {"mission_id": mission["id"], "expected_schedule_version": reserved["version"], "reason": "Isolated dispatch software test"}


def test_actual_assigned_pilot_and_internal_dispatch_are_distinct(environment):
    store, author, reviewer, pilot, schedule, payload = dispatch_fixture(environment)
    with pytest.raises(HTTPException) as missing_ack:
        release_dispatch(store, schedule["id"], reviewer, payload)
    assert "not acknowledged" in missing_ack.value.detail
    ack = acknowledge_pilot(store, schedule["id"], pilot, payload)
    assert ack["status"] == "Recorded"
    released = release_dispatch(store, schedule["id"], reviewer, payload)
    assert released["status"] == "Internally Released"
    assert released["data"]["flight_execution"] == "Not Recorded"
    assert released["data"]["provider_activation"] == "Not Performed"
    assert not released["data"]["aircraft_commands"]
    assert store.verify_audit(author["organisation_id"])["valid"]


def test_changed_country_permission_blocks_previously_acknowledged_dispatch(environment):
    store, _, reviewer, pilot, schedule, payload = dispatch_fixture(environment)
    acknowledge_pilot(store, schedule["id"], pilot, payload)
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == "test-country-instrument").values(status="Suspended", version=2))
    with pytest.raises(HTTPException) as blocked:
        release_dispatch(store, schedule["id"], reviewer, payload)
    assert blocked.value.status_code == 409


def test_another_pilot_or_preparer_cannot_acknowledge_or_release(environment):
    store, author, reviewer, pilot, schedule, payload = dispatch_fixture(environment)
    other = provision(store, "Isolated tenant", "other-dispatch-pilot@test.invalid", "pilot", "isolated-test-password", author["organisation_id"])
    with pytest.raises(HTTPException) as wrong_pilot:
        acknowledge_pilot(store, schedule["id"], other, payload)
    assert wrong_pilot.value.status_code == 403
    with pytest.raises(HTTPException) as preparer:
        release_dispatch(store, schedule["id"], author, payload)
    assert preparer.value.status_code == 403


def test_configured_second_review_is_required_for_internal_dispatch(environment, monkeypatch):
    store, author, reviewer, pilot, schedule, payload = dispatch_fixture(environment)
    second = provision(store, "Isolated tenant", "second-dispatch-reviewer@test.invalid", "reviewer", "isolated-test-password", author["organisation_id"])
    with store.engine.begin() as conn:
        current = conn.execute(select(records).where(records.c.id == schedule["id"])).mappings().one()
        data = deepcopy(current["data"])
        data["reviewer_ids"].append(second["id"])
        conn.execute(update(records).where(records.c.id == schedule["id"]).values(data=data))
    acknowledge_pilot(store, schedule["id"], pilot, payload)
    monkeypatch.setenv("AIRSPACE_REQUIRE_TWO_REVIEWERS", "true")
    first = release_dispatch(store, schedule["id"], reviewer, payload)
    assert first["status"] == "Under Review"
    with pytest.raises(HTTPException) as duplicate:
        release_dispatch(store, schedule["id"], reviewer, payload)
    assert duplicate.value.status_code == 409
    released = release_dispatch(store, schedule["id"], second, payload)
    assert released["status"] == "Internally Released"
    assert len(released["data"]["_approvals"]) == 2


def test_material_input_change_invalidates_existing_internal_dispatch(environment):
    store, author, reviewer, pilot, schedule, payload = dispatch_fixture(environment)
    acknowledge_pilot(store, schedule["id"], pilot, payload)
    released = release_dispatch(store, schedule["id"], reviewer, payload)
    with store.engine.begin() as conn:
        assert suspend_dispatch_dependencies(conn, store, author["organisation_id"], "test-country-instrument", author, "Isolated controlled instrument change") == 1
        row = conn.execute(select(records).where(records.c.id == released["id"])).mappings().one()
        assert row["status"] == "Suspended"
        assert row["data"]["_suspension"]["source_record_id"] == "test-country-instrument"
    assert store.verify_audit(author["organisation_id"])["valid"]


@pytest.mark.parametrize("resource_kind", ["aircraft", "personnel", "site"])
def test_partial_local_reservation_loss_blocks_dispatch(environment, resource_kind):
    store, _, reviewer, pilot, schedule, payload = dispatch_fixture(environment)
    acknowledge_pilot(store, schedule["id"], pilot, payload)
    with store.engine.begin() as conn:
        conn.execute(delete(reservations).where(reservations.c.schedule_id == schedule["id"], reservations.c.resource_kind == resource_kind))
    with pytest.raises(HTTPException) as incomplete:
        release_dispatch(store, schedule["id"], reviewer, payload)
    assert incomplete.value.status_code == 409
    assert "completely reserved" in incomplete.value.detail


@pytest.mark.parametrize("mutation", ["missing", "suspended", "timing", "owner-version"])
def test_physical_reservation_requires_exact_current_scope_before_dispatch(environment, mutation):
    store, _, reviewer, pilot, schedule, payload = dispatch_fixture(environment)
    acknowledge_pilot(store, schedule["id"], pilot, payload)
    with store.engine.begin() as conn:
        where = fleet_reservations.c.schedule_id == schedule["id"]
        if mutation == "missing": conn.execute(delete(fleet_reservations).where(where))
        elif mutation == "suspended": conn.execute(update(fleet_reservations).where(where).values(state="Suspended"))
        elif mutation == "timing": conn.execute(update(fleet_reservations).where(where).values(end="2099-01-01T00:00:00+00:00"))
        else: conn.execute(update(fleet_reservations).where(where).values(owner_record_version=99))
    with pytest.raises(HTTPException) as incomplete:
        release_dispatch(store, schedule["id"], reviewer, payload)
    assert incomplete.value.status_code == 409
    assert "physical-aircraft reservation" in incomplete.value.detail


def test_future_documented_submission_cannot_support_current_dispatch(environment):
    store, author, reviewer, pilot, schedule, payload = dispatch_fixture(environment)
    acknowledge_pilot(store, schedule["id"], pilot, payload)
    with store.engine.begin() as conn:
        mission = conn.execute(select(records).where(records.c.id == payload["mission_id"])).mappings().one()
        raw = deepcopy(mission["data"]["coordination"])
        raw["segments"][0].update(country="IT", legal_route="STS Declaration", required_instrument_kinds=["declaration_home_receipt"], instrument_ids=["test-country-instrument", "test-documented-submission"])
        raw["country_reviews"][0]["country"] = "IT"
        raw["instruments"][0].update(kind="declaration_home_receipt", operation_countries=["IT"])
        raw["instruments"].append({**raw["instruments"][0], "id": "test-documented-submission", "kind": "host_declaration_submission", "issuer": "Isolated operator submission ledger", "recipient_country": "IT", "provided_at": (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)).isoformat()})
        plan = CrossBorderPlan.model_validate(raw)
        assert assess_cross_border(plan)["ready_for_internal_review"]
        conn.execute(update(records).where(records.c.id == mission["id"]).values(data={**mission["data"], "coordination": plan.model_dump(mode="json")}))
        conn.execute(update(records).where(records.c.id == "test-country-review").values(data={"country_review": plan.country_reviews[0].model_dump(mode="json")}))
        conn.execute(update(records).where(records.c.id == "test-country-instrument").values(data={"instrument": plan.instruments[0].model_dump(mode="json")}))
        insert_record(conn, author["organisation_id"], "country_instrument", "test-documented-submission", {"instrument": plan.instruments[1].model_dump(mode="json")}, author["id"])
    with pytest.raises(HTTPException) as future:
        release_dispatch(store, schedule["id"], reviewer, payload)
    assert future.value.status_code == 422
    assert "future-dated operator submission" in future.value.detail
