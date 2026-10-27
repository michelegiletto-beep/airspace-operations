"""Isolated software fixtures only: no operational flights or provider evidence.

These integration tests exercise the actual API, local database, audit chain and
independent procedure-review transitions. No production store or external feed is
used, and the artificial telemetry must remain confined to this test harness.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from airspace.identity import provision


@pytest.fixture
def monitoring(environment, monkeypatch, tmp_path):
    store, client, author, reviewer, other, headers = environment
    monkeypatch.setenv("AIRSPACE_RUNTIME", str(tmp_path / "isolated-runtime"))
    monkeypatch.setenv("AIRSPACE_REQUIRE_TWO_REVIEWERS", "false")
    accounts = {"regulatory": author, "reviewer": reviewer}
    for role in ("fleet_manager", "pilot", "incident_coordinator", "administrator", "viewer"):
        accounts[role] = provision(
            store, "Isolated software test tenant", f"{role}@monitoring.test.invalid",
            role, "isolated-test-password", author["organisation_id"],
        )
    accounts["other_fleet"] = provision(
        store, "Other isolated test tenant", "other-fleet@monitoring.test.invalid",
        "fleet_manager", "isolated-test-password", other["organisation_id"],
    )
    accounts["other_pilot"] = provision(
        store, "Other isolated test tenant", "other-pilot@monitoring.test.invalid",
        "pilot", "isolated-test-password", other["organisation_id"],
    )
    credentials = {role: headers(account["email"]) for role, account in accounts.items()}

    def create(kind, role, data=None, title=None):
        response = client.post(
            f"/api/v1/records/{kind}", headers=credentials[role],
            json={"title": title or f"Isolated {kind} software fixture", "data": data or {}},
        )
        assert response.status_code == 201, response.text
        return response.json()

    aircraft = create("aircraft", "fleet_manager", {"configuration_id": "isolated-config"})
    mission = create("mission", "pilot", {"aircraft_id": aircraft["id"]})
    return store, client, accounts, credentials, create, aircraft, mission


def stamp(value):
    return value.isoformat()


def event(aircraft, mission, *, mode="Live", event_id="isolated-event", age_seconds=120):
    current = datetime.now(timezone.utc)
    return {
        "event_id": event_id, "source_id": "isolated-test-source",
        "aircraft_id": aircraft["id"], "mission_id": mission["id"],
        "observed_at": stamp(current - timedelta(seconds=age_seconds)),
        "received_at": stamp(current - timedelta(seconds=1)), "sequence": 1,
        "position": {
            "longitude": 6.1, "latitude": 49.6, "horizontal_uncertainty_m": 10,
            "vertical_reference": "Unknown", "crs": "EPSG:4326",
        },
        "mode": mode, "source_version": "isolated-test-schema-1",
    }


def payload(events, *, mode="Live", expected_aircraft_ids=None, **extra):
    return {
        "events": events, "mode": mode, "permitted_use_attestation": True,
        "source_rights_reference": "Isolated software-test fixture; no operational data rights asserted",
        "expected_aircraft_ids": expected_aircraft_ids or [], **extra,
    }


def stored(client, credentials, kind):
    response = client.get(f"/api/v1/records/{kind}", headers=credentials)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_mission_aircraft_binding_is_enforced(monitoring):
    _,client,_,credentials,create,aircraft,mission=monitoring
    different=create('aircraft','fleet_manager',{'configuration_id':'different-isolated-config'})
    response=client.post('/api/v1/telemetry/import',headers=credentials['pilot'],json=payload([event(different,mission)]))
    assert response.status_code==422
    assert stored(client,credentials['pilot'],'telemetry')==[]


def test_manual_import_requires_explicit_rights_attestation(monitoring):
    _, client, _, credentials, _, aircraft, mission = monitoring
    valid = payload([event(aircraft, mission)])
    assert client.post("/api/v1/telemetry/import", json=valid).status_code == 401
    invalid = [
        {**valid, "permitted_use_attestation": False},
        {**valid, "source_rights_reference": ""},
        {**valid, "mode": "Simulation"},
    ]
    missing_attestation = dict(valid)
    missing_attestation.pop("permitted_use_attestation")
    invalid.append(missing_attestation)
    for body in invalid:
        response = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=body)
        assert response.status_code == 422, response.text
    assert stored(client, credentials["pilot"], "telemetry") == []
    assert stored(client, credentials["pilot"], "alert") == []


@pytest.mark.parametrize("role", ["regulatory", "reviewer", "incident_coordinator", "administrator", "viewer"])
def test_import_role_is_enforced_before_persistence(monitoring, role):
    _, client, _, credentials, _, aircraft, mission = monitoring
    response = client.post(
        "/api/v1/telemetry/import", headers=credentials[role], json=payload([event(aircraft, mission)]),
    )
    assert response.status_code == 403, response.text
    assert stored(client, credentials["pilot"], "telemetry") == []


@pytest.mark.parametrize("role", ["pilot", "fleet_manager"])
def test_allowed_role_imports_real_persistent_records_without_inferred_freshness(monitoring, role):
    store, client, accounts, credentials, _, aircraft, mission = monitoring
    input_event = event(aircraft, mission)
    body = payload([input_event])
    response = client.post("/api/v1/telemetry/import", headers=credentials[role], json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "Missing Monitoring Policy"
    assert result["operational_use"] is False
    assert result["latest_verified"][0]["freshness"] == "Unknown"
    assert result["latest_verified"][0]["predicted"] is False
    rows = stored(client, credentials[role], "telemetry")
    assert len(rows) == 1
    data = rows[0]["data"]
    assert data["event"]["event_id"] == input_event["event_id"]
    assert data["event"]["position"]["vertical_reference"] == "Unknown"
    assert "altitude_m" in data["event"]["position"] and data["event"]["position"]["altitude_m"] is None
    assert data["source_rights_reference"] == body["source_rights_reference"]
    assert data["source_receipt_type"] == "Authorised operator manual import"
    assert data["operational_use_accepted"] is False
    assert store.verify_audit(accounts["pilot"]["organisation_id"])["valid"]


def test_import_rejects_unknown_and_cross_tenant_aircraft_mission_references(monitoring):
    _, client, _, credentials, create, aircraft, mission = monitoring
    foreign_aircraft = create("aircraft", "other_fleet")
    foreign_mission = create("mission", "other_pilot")
    for aircraft_id, mission_id in [
        ("unknown-aircraft", mission["id"]), (aircraft["id"], "unknown-mission"),
        (foreign_aircraft["id"], mission["id"]), (aircraft["id"], foreign_mission["id"]),
    ]:
        sample = event(aircraft, mission)
        sample.update(aircraft_id=aircraft_id, mission_id=mission_id)
        response = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=payload([sample]))
        assert response.status_code == 404, response.text
    response = client.post(
        "/api/v1/telemetry/import", headers=credentials["pilot"],
        json=payload([], expected_aircraft_ids=[foreign_aircraft["id"]]),
    )
    assert response.status_code == 404
    assert stored(client, credentials["pilot"], "telemetry") == []
    assert stored(client, credentials["other_pilot"], "telemetry") == []


def test_live_replay_modes_are_separate_and_mismatched_inputs_are_quarantined(monitoring):
    _, client, _, credentials, _, aircraft, mission = monitoring
    replay = event(aircraft, mission, mode="Historical Replay")
    mismatch = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=payload([replay], mode="Live"))
    assert mismatch.status_code == 200, mismatch.text
    assert mismatch.json()["accepted_records"] == []
    assert mismatch.json()["latest_verified"] == []
    assert "Quarantined" in mismatch.json()["observations"][0]["state"]
    assert stored(client, credentials["pilot"], "telemetry") == []
    assert len(stored(client, credentials["pilot"], "alert")) == 1
    for mode in ["Historical Replay", "Live"]:
        sample = {**replay, "mode": mode}
        response = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=payload([sample], mode=mode))
        assert response.status_code == 200, response.text
        assert response.json()["mode"] == mode
        assert len(response.json()["accepted_records"]) == 1
        assert {track["mode"] for track in response.json()["latest_verified"]} == {mode}
    rows = stored(client, credentials["pilot"], "telemetry")
    assert len(rows) == 2
    assert {row["data"]["event"]["mode"] for row in rows} == {"Live", "Historical Replay"}


def test_duplicate_import_and_redelivery_receipt_do_not_duplicate_telemetry(monitoring):
    store, client, accounts, credentials, _, aircraft, mission = monitoring
    sample = event(aircraft, mission)
    first = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=payload([sample]))
    assert first.status_code == 200, first.text
    redelivery = {**sample, "received_at": stamp(datetime.now(timezone.utc) - timedelta(milliseconds=100))}
    for repeated in [sample, redelivery]:
        response = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=payload([repeated]))
        assert response.status_code == 200, response.text
        assert response.json()["accepted_records"] == []
        assert response.json()["observations"][0]["state"] == "Duplicate"
    assert len(stored(client, credentials["pilot"], "telemetry")) == 1
    assert stored(client, credentials["pilot"], "alert") == []
    assert store.verify_audit(accounts["pilot"]["organisation_id"])["valid"]


def test_concurrent_duplicate_imports_reserve_one_source_observation(monitoring):
    _, client, _, credentials, _, aircraft, mission = monitoring
    body = payload([event(aircraft, mission)])
    def import_once(_):
        return client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(import_once, range(2)))
    assert all(response.status_code == 200 for response in responses), [r.text for r in responses]
    assert sorted(len(response.json()["accepted_records"]) for response in responses) == [0, 1]
    assert len(stored(client, credentials["pilot"], "telemetry")) == 1


def test_contradictory_redelivery_is_quarantined_without_moving_last_verified_track(monitoring):
    _, client, _, credentials, _, aircraft, mission = monitoring
    sample = event(aircraft, mission)
    first = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=payload([sample]))
    assert first.status_code == 200, first.text
    contradictory = deepcopy(sample)
    contradictory["position"]["longitude"] = 7.2
    response = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=payload([contradictory]))
    assert response.status_code == 200, response.text
    assert response.json()["accepted_records"] == []
    assert "contradictory" in response.json()["observations"][0]["state"]
    assert response.json()["latest_verified"][0]["position"]["longitude"] == sample["position"]["longitude"]
    assert response.json()["latest_verified"][0]["predicted"] is False
    assert len(stored(client, credentials["pilot"], "telemetry")) == 1
    alerts = stored(client, credentials["pilot"], "alert")
    assert len(alerts) == 1 and alerts[0]["title"] == "Telemetry Integrity"


def test_stale_threshold_requires_current_independent_procedure_approval(monitoring):
    _, client, accounts, credentials, create, aircraft, mission = monitoring
    evidence = create("evidence", "regulatory", {
        "provenance": "Isolated test harness only", "checksum": "0" * 64, "evidence_type": "Software test",
    })
    data = {
        "content": "Isolated software monitoring-policy fixture, not an operational procedure.",
        "aircraft_configuration_id": "isolated-config", "revision": "isolated-1",
        "reviewer_ids": [accounts["reviewer"]["id"]],
        "monitoring_policy": {"stale_after_seconds": 10, "operational_use_accepted": True},
    }
    procedure = create("procedure", "regulatory", data)
    body = payload([event(aircraft, mission)], monitoring_procedure_id=procedure["id"])
    url = f"/api/v1/records/procedure/{procedure['id']}"
    for version, transition in [(1, "Under Review"), (2, "Approved")]:
        rejected = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=body)
        assert rejected.status_code == 422
        assert "independently approved" in rejected.json()["detail"]
        response = client.post(url + "/transition", headers=credentials["reviewer" if transition == "Approved" else "regulatory"], json={
            "state": transition, "expected_version": version, "reason": "Isolated software approval-boundary verification",
            "evidence_ids": [evidence["id"]],
        })
        assert response.status_code == 200, response.text
    accepted = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=body)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "Degraded"
    assert accepted.json()["latest_verified"][0]["freshness"] == "Stale"
    assert accepted.json()["alerts"][0]["type"] == "Telemetry Loss"
    assert accepted.json()["alerts"][0]["policy_ref"] == procedure["id"]
    assert accepted.json()["operational_use"] is True
    again = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=body)
    assert again.status_code == 200
    assert len(stored(client, credentials["pilot"], "telemetry")) == 1
    assert len(stored(client, credentials["pilot"], "alert")) == 1
    revised = client.put(url, headers=credentials["regulatory"], json={"expected_version": 3, "data": {**data, "revision": "isolated-2"}})
    assert revised.status_code == 200 and revised.json()["status"] == "Draft"
    assert client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=body).status_code == 422


def test_alert_acknowledgement_permissions_versions_ownership_and_audit(monitoring):
    store, client, accounts, credentials, create, aircraft, _ = monitoring
    aircraft_ids = [aircraft["id"]] + [create("aircraft", "fleet_manager")["id"] for _ in range(2)]
    response = client.post("/api/v1/telemetry/import", headers=credentials["pilot"], json=payload([], expected_aircraft_ids=aircraft_ids))
    assert response.status_code == 200, response.text
    alerts = stored(client, credentials["pilot"], "alert")
    assert len(alerts) == 3
    for alert, role in zip(alerts, ["pilot", "incident_coordinator", "fleet_manager"]):
        url = f"/api/v1/alerts/{alert['id']}/acknowledge"
        body = {"expected_version": 1, "reason": "Isolated acknowledgement software test"}
        assert client.post(url, json=body).status_code == 401
        for denied in ["regulatory", "reviewer", "administrator", "viewer"]:
            assert client.post(url, headers=credentials[denied], json=body).status_code == 403
        assert client.post(url, headers=credentials["other_fleet"], json=body).status_code == 404
        assert client.post(url, headers=credentials[role], json={**body, "expected_version": 99}).status_code == 409
        assert client.post(url, headers=credentials[role], json={**body, "reason": ""}).status_code == 422
        success = client.post(url, headers=credentials[role], json=body)
        assert success.status_code == 200, success.text
        changed = success.json()
        assert changed["status"] == "Acknowledged" and changed["version"] == 2
        assert changed["data"]["owner_id"] == accounts[role]["id"]
        assert changed["data"]["acknowledgement_reason"] == body["reason"]
        assert changed["data"]["acknowledged_at"]
        assert changed["data"]["notification"] == {"sent": False, "delivered": False, "acknowledged": True, "action_completed": False}
        assert client.post(url, headers=credentials[role], json={**body, "expected_version": 2}).status_code == 409
        history = client.get(f"/api/v1/records/alert/{alert['id']}/history", headers=credentials[role]).json()["items"]
        assert [row["version"] for row in history] == [1, 2]
    actions = client.get("/api/v1/audit", headers=credentials["pilot"]).json()["items"]
    assert sum(action["action"] == "alert.acknowledged" for action in actions) == 3
    assert store.verify_audit(accounts["pilot"]["organisation_id"])["valid"]


def test_alert_records_cannot_be_fabricated_through_generic_creation(monitoring):
    _, client, _, credentials, _, _, _ = monitoring
    for role in ["pilot", "fleet_manager", "incident_coordinator", "regulatory", "administrator"]:
        response = client.post("/api/v1/records/alert", headers=credentials[role], json={"title": "Isolated forbidden alert fixture"})
        assert response.status_code == 403, response.text
    assert stored(client, credentials["pilot"], "alert") == []


def test_incident_workspace_without_approved_procedure_preserves_missing_evidence(monitoring):
    _, client, accounts, credentials, create, _, _ = monitoring
    incident = create("incident", "incident_coordinator", {
        "incident_type": "Isolated software event", "aircraft_configuration_id": "isolated-config",
        "commander": accounts["incident_coordinator"]["id"],
    })
    path = f"/api/v1/incidents/{incident['id']}/workspace"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=credentials["other_fleet"]).status_code == 404
    first = client.get(path, headers=credentials["pilot"])
    assert first.status_code == 200, first.text
    result = first.json()
    assessment = result["assessment"]
    assert result["incident"]["id"] == incident["id"]
    assert assessment["owner"] == accounts["incident_coordinator"]["id"]
    assert assessment["checklist"] == []
    assert assessment["escalation"] == "Missing Approved Escalation Policy"
    assert any("No current approved procedure" in finding for finding in assessment["findings"])
    assert assessment["flight_command_capability"] is False
    assert assessment["notification"]["state"] == "Not Sent"
    assert result["external_notification_status"] == "Not Sent"
    assert result["timeline"] == []
    assert result["cache_generated_at"] and result["cache_age_at_generation_seconds"] == 0
    assert "snapshot only" in result["degraded_export_notice"]
    repeated = client.get(path, headers=credentials["pilot"]).json()["assessment"]
    for key in ["status", "findings", "checklist", "escalation", "owner", "notification", "flight_command_capability", "reportability"]:
        assert repeated[key] == assessment[key]
    create("corrective_action", "regulatory", {"incident_ids": [incident["id"]]}, "Linked isolated test remediation")
    create("corrective_action", "other_fleet", {"incident_ids": [incident["id"]]}, "Foreign isolated record must remain invisible")
    linked = client.get(path, headers=credentials["pilot"]).json()["timeline"]
    assert len(linked) == 1 and linked[0]["title"] == "Linked isolated test remediation"


def test_incident_draft_procedure_content_cannot_become_emergency_instructions(monitoring):
    _, client, accounts, credentials, create, _, _ = monitoring
    draft = create("procedure", "regulatory", {
        "content": "Isolated unapproved procedure fixture", "revision": "isolated-1",
        "aircraft_configuration_id": "isolated-config",
        "incident_procedure": {
            "incident_types": ["Isolated event"], "configuration_id": "isolated-config",
            "source_ref": "Isolated test only", "valid_until": stamp(datetime.now(timezone.utc) + timedelta(days=1)),
            "steps": ["Unapproved isolated step must never be displayed as approved"],
        },
    })
    incident = create("incident", "pilot", {
        "incident_type": "Isolated event", "aircraft_configuration_id": "isolated-config",
        "commander": accounts["pilot"]["id"], "procedure_id": draft["id"],
    })
    response = client.get(f"/api/v1/incidents/{incident['id']}/workspace", headers=credentials["pilot"])
    assert response.status_code == 200, response.text
    assert response.json()["assessment"]["checklist"] == []
    assert "Unapproved isolated step" not in str(response.json()["assessment"])
    assert any("No current approved procedure" in finding for finding in response.json()["assessment"]["findings"])
