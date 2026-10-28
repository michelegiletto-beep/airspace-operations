"""Private companion records cannot escape through existing shared interfaces."""
import pytest
from sqlalchemy import select

from airspace.identity import provision
from airspace.orchestration import WorkflowRepository
from airspace.storage import identifier, jobs, now, records
from airspace.worker import run_once


def private_record(store, actor, kind="companion_conversation", data=None):
    row = dict(id=identifier(), organisation_id=actor["organisation_id"], kind=kind,
               title="Isolated private conversation", status="Draft", data=data or {},
               version=1, created_by=actor["id"], created_at=now(), updated_at=now())
    with store.engine.begin() as conn:
        conn.execute(records.insert().values(**row))
        store.snapshot(conn, row)
    return row


@pytest.mark.parametrize("kind", ["companion_conversation", "companion_message", "companion_action", "companion_task"])
def test_private_kinds_are_not_exposed_by_generic_records_or_history(environment, kind):
    store, client, author, reviewer, other, headers = environment
    row = private_record(store, author, kind)
    for actor in (author, reviewer, other):
        auth = headers(actor["email"])
        for path in (f"/records/{kind}", f"/records/{kind}/{row['id']}", f"/records/{kind}/{row['id']}/history"):
            assert client.get("/api/v1" + path, headers=auth).status_code == 404
        assert client.get(f"/api/v1/records/case/{row['id']}/history", headers=auth).status_code == 404
        assert client.post(f"/api/v1/records/{kind}", headers=auth, json={"title": "Isolated bypass"}).status_code == 404


def test_private_job_payload_is_visible_only_to_its_actor(environment):
    store, client, author, _, other, headers = environment
    colleague = provision(store, "Isolated software test tenant", "colleague@test.invalid", "regulatory", "isolated-test-password", author["organisation_id"])
    row = dict(id=identifier(), organisation_id=author["organisation_id"], actor_id=author["id"],
               kind="companion_reply", state="Queued", payload={"private_message": "Isolated private test text"},
               result=None, attempts=0, lease_until=None, deadline=None, error=None, version=1, created_at=now())
    with store.engine.begin() as conn:
        conn.execute(jobs.insert().values(**row))
    own, same, foreign = (headers(actor["email"]) for actor in (author, colleague, other))
    assert row["id"] in {item["id"] for item in client.get("/api/v1/jobs", headers=own).json()["items"]}
    for auth in (same, foreign):
        response = client.get("/api/v1/jobs", headers=auth)
        assert row["id"] not in {item["id"] for item in response.json()["items"]}
        assert "Isolated private test text" not in response.text
    assert client.post(f"/api/v1/jobs/{row['id']}/cancel", headers=same).status_code == 404
    assert client.post(f"/api/v1/jobs/{row['id']}/cancel", headers=own).status_code == 422
    assert client.post("/api/v1/jobs", headers=own, json={"kind": "companion_reply"}).status_code == 422


def test_private_records_cannot_become_shared_workflow_context(environment):
    store, client, author, _, _, headers = environment
    private = private_record(store, author)
    response = client.post("/api/v1/agent-workflows", headers=headers(author["email"]), json={
        "task_kind": "regulatory_research", "objective": "Isolated context admission test",
        "jurisdiction": "LU", "operation_date": "2026-10-28", "context_record_ids": [private["id"]],
        "controller_mode": "native"})
    assert response.status_code == 422


def test_private_records_cannot_become_indirect_schedule_dependencies(environment):
    store, client, author, _, _, headers = environment
    private = private_record(store, author)
    schedule = private_record(store, author, "schedule", {"input_record_versions": {private["id"]: 1}})
    response = client.post("/api/v1/agent-workflows", headers=headers(author["email"]), json={
        "task_kind": "regulatory_research", "objective": "Isolated indirect admission test",
        "jurisdiction": "LU", "operation_date": "2026-10-28", "context_record_ids": [schedule["id"]],
        "controller_mode": "native"})
    assert response.status_code == 422


def test_workflow_creation_can_rollback_with_its_confirming_transaction(environment):
    store, _, author, _, _, _ = environment
    workflow_id = None
    with pytest.raises(RuntimeError, match="Isolated rollback"):
        with store.engine.begin() as conn:
            row = WorkflowRepository(store).create({"task_kind": "regulatory_research", "objective": "Isolated atomic creation",
                "jurisdiction": "LU", "operation_date": "2026-10-28", "controller_mode": "native"}, author, conn=conn)
            workflow_id = row["id"]
            raise RuntimeError("Isolated rollback")
    with store.engine.connect() as conn:
        assert conn.execute(select(records.c.id).where(records.c.id == workflow_id)).first() is None
    assert store.verify_audit(author["organisation_id"])["valid"]


def test_source_monitor_does_not_republish_private_companion_context(environment, monkeypatch):
    store, client, author, _, _, headers = environment
    private = private_record(store, author, data={"source_ids": ["isolated-source"]})
    from airspace import regulatory
    monkeypatch.setattr(regulatory, "monitor_registered_source", lambda *args, **kwargs: {
        "success": True, "content_changed": True, "previous_checksum": "a" * 64, "current_checksum": "b" * 64})
    response = client.post("/api/v1/jobs", headers=headers(author["email"]), json={"kind": "regulatory_monitor", "payload": {"source_id": "isolated-source"}})
    assert response.status_code == 201
    assert run_once(store)["state"] == "Completed"
    with store.engine.connect() as conn:
        review_tasks = conn.execute(select(records).where(records.c.kind == "review_task")).mappings().all()
    assert not any(row["data"].get("affected_record_id") == private["id"] for row in review_tasks)
