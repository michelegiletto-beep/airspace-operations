"""Mission-planning permissions in isolated software stores, never operator data."""
import pytest
from sqlalchemy import select, update

from airspace.identity import provision
from airspace.storage import metadata, users


# An independent expectation: an administrator account is not a planning role.
MISSION_ROLES = [
    ("administrator", False),
    ("regulatory", False),
    ("reviewer", False),
    ("planner", True),
    ("pilot", True),
    ("fleet_manager", False),
    ("incident_coordinator", False),
    ("analyst", False),
    ("viewer", False),
]
PROPOSAL = {
    "title": "Isolated permission-test intended mission",
    "data": {
        "record_origin": "Isolated software fixture only",
        "execution_recorded": False,
        "notes": "No real mission, resources, permission or flight is represented.",
    },
}


def mutation_snapshot(store):
    """Capture every persisted table after isolated identity setup and login."""
    with store.engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in metadata.sorted_tables
        }


@pytest.mark.parametrize("role,may_create", MISSION_ROLES)
def test_mission_creation_requires_planner_or_pilot_with_no_denied_mutation(
    environment, role, may_create
):
    store, client, author, _, _, headers = environment
    actor = provision(
        store,
        "Isolated software test tenant",
        f"mission-{role}@test.invalid",
        role,
        "isolated-test-password",
        author["organisation_id"],
    )
    authenticated = headers(actor["email"])
    before = mutation_snapshot(store)

    response = client.post(
        "/api/v1/records/mission",
        headers={**authenticated, "Idempotency-Key": "isolated-mission-permission"},
        json=PROPOSAL,
    )

    if not may_create:
        assert response.status_code == 403, response.text
        assert mutation_snapshot(store) == before
        assert store.verify_audit(actor["organisation_id"])["valid"]
        return

    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["status"] == "Draft" and proposal["version"] == 1
    assert proposal["organisation_id"] == actor["organisation_id"]
    assert proposal["created_by"] == actor["id"]
    assert proposal["data"]["_prepared_by"] == actor["id"]
    assert proposal["data"]["execution_recorded"] is False
    assert "aircraft_id" not in proposal["data"]
    assert "route_id" not in proposal["data"]
    saved = client.get(
        "/api/v1/records/mission/" + proposal["id"], headers=authenticated
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "Draft"
    assert saved.json()["data"] == proposal["data"]
    assert store.verify_audit(actor["organisation_id"])["valid"]


def test_existing_token_uses_current_role_before_creating_or_editing_missions(environment):
    store, client, author, _, _, headers = environment
    actor = provision(
        store,
        "Isolated software test tenant",
        "mission-revoked-planner@test.invalid",
        "planner",
        "isolated-test-password",
        author["organisation_id"],
    )
    authenticated = headers(actor["email"])
    created = client.post("/api/v1/records/mission", headers=authenticated, json=PROPOSAL)
    assert created.status_code == 201, created.text
    proposal = created.json()

    # This deliberate role change exists only in the disposable test database.
    with store.engine.begin() as connection:
        connection.execute(update(users).where(users.c.id == actor["id"]).values(role="regulatory"))

    assert client.get("/api/v1/me", headers=authenticated).json()["role"] == "regulatory"
    before = mutation_snapshot(store)
    denied_create = client.post(
        "/api/v1/records/mission", headers=authenticated, json=PROPOSAL
    )
    denied_edit = client.put(
        "/api/v1/records/mission/" + proposal["id"],
        headers=authenticated,
        json={"expected_version": 1, "title": "Denied isolated mission edit"},
    )
    assert denied_create.status_code == 403, denied_create.text
    assert denied_edit.status_code == 403, denied_edit.text
    assert mutation_snapshot(store) == before
    unchanged = client.get(
        "/api/v1/records/mission/" + proposal["id"], headers=authenticated
    ).json()
    assert unchanged["title"] == proposal["title"]
    assert unchanged["version"] == proposal["version"] == 1
    assert unchanged["data"] == proposal["data"]
    assert store.verify_audit(actor["organisation_id"])["valid"]
