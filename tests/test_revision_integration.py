"""Application integration and adversarial checks in isolated software stores."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sqlalchemy import select, update
from airspace.storage import Store, schema_versions, metadata, users, CURRENT_SCHEMA_VERSION
from airspace.identity import provision
from airspace.worker import run_once
from airspace.orchestration import DefaultServices, NativeController


class TestOnlyServices(DefaultServices):
    __test__ = False
    def __init__(self):
        super().__init__(controller_provider=lambda mode: NativeController())
    def execute(self, tool, data, scoped_records, budget):
        if tool in {"regulatory.retrieve", "neural.rerank"}:
            return {"results": [], "status": "Missing Evidence", "missing_inputs": ["Isolated test has no source library"]}
        return super().execute(tool, data, scoped_records, budget)


def test_worker_continues_bounded_steps_and_keeps_review_gate(environment, monkeypatch):
    store, client, author, _, other, headers = environment
    from airspace import orchestration
    monkeypatch.setattr(orchestration, "DefaultServices", TestOnlyServices)
    auth = headers(author["email"])
    created = client.post("/api/v1/agent-workflows", headers=auth, json={"task_kind": "regulatory_research", "objective": "Isolated source evidence test", "jurisdiction": "LU", "operation_date": "2026-10-27", "controller_mode": "native"})
    assert created.status_code == 201, created.text
    row = created.json()
    url = "/api/v1/agent-workflows/" + row["id"]
    first = client.post(url + "/advance", headers=auth, json={"expected_version": 1})
    repeated = client.post(url + "/advance", headers=auth, json={"expected_version": 1})
    assert first.status_code == repeated.status_code == 202
    assert first.json()["id"] == repeated.json()["id"]
    for _ in range(4):
        assert run_once(store)["state"] == "Completed"
    assert run_once(store) is None
    finished = client.get(url, headers=auth).json()
    assert finished["status"] == "Needs Review"
    assert finished["data"]["review_gate"]["approval_granted"] is False
    assert len(finished["data"]["receipts"]) == 4
    assert len(client.get("/api/v1/jobs", headers=auth).json()["items"]) == 4
    assert client.get(url, headers=headers(other["email"])).status_code in {404, 422}
    assert store.verify_audit(author["organisation_id"])["valid"]


def test_new_controlled_kinds_reject_generic_writes(environment):
    _, client, author, reviewer, _, headers = environment
    auth = headers(author["email"])
    for kind in ("agent_workflow", "dispatch_release", "pilot_acknowledgement"):
        assert client.post("/api/v1/records/" + kind, headers=auth, json={"title": "Attempted isolated bypass"}).status_code == 403
    assert client.post("/api/v1/jobs", headers=auth, json={"kind": "agent_orchestration", "payload": {"workflow_id": "forged"}}).status_code == 422


def test_server_binds_country_identity_and_missing_typed_inputs(environment):
    _, client, author, _, _, headers = environment
    auth = headers(author["email"])
    created = client.post("/api/v1/records/country_review", headers=auth, json={"title": "Isolated incomplete country assessment", "data": {"country_review": {"id": "forged", "version": 999, "country": "LU", "status": "Validated", "reviewed_by": "invented-authority"}}})
    assert created.status_code == 201, created.text
    row = created.json()
    snapshot = row["data"]["country_review"]
    assert snapshot["id"] == row["id"] and snapshot["version"] == 1
    assert snapshot["status"] == "Registered" and snapshot["reviewed_by"] is None
    response = client.post("/api/v1/records/country_review/" + row["id"] + "/transition", headers=auth, json={"state": "Under Review", "expected_version": 1, "reason": "Completeness must fail"})
    assert response.status_code == 422
    assert any("country_review" in value for value in response.json()["detail"]["missing_inputs"])


def test_country_catalogue_is_not_universal_permission(environment):
    _, client, author, _, _, headers = environment
    countries = client.get("/api/v1/coordination/countries", headers=headers(author["email"])).json()["items"]
    assert len(countries) >= 45
    assert all(item["coverage_status"] == "Registered" and not item["operationally_validated"] and item["default_permission"] is None for item in countries)
    assert next(item for item in countries if item["country"] == "GB")["framework"] == "Separate national framework"


def test_schema_one_upgrade_preserves_existing_identity_and_chain(tmp_path):
    path = tmp_path / "legacy.db"
    sql = (Path(__file__).resolve().parents[1] / "migrations/001_schema.sqlite.sql").read_text()
    with sqlite3.connect(path) as conn:
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_versions(version,applied_at) VALUES(1,'2026-10-27T00:00:00+00:00')")
    store = Store("sqlite:///" + path.as_posix(), b"isolated-schema-upgrade-key-32-bytes")
    user = provision(store, "Isolated legacy schema", "legacy@test.invalid", "viewer", "isolated-legacy-password")
    before = store.verify_audit(user["organisation_id"])
    store.migrate()
    store.migrate()
    assert store.verify_audit(user["organisation_id"]) == before
    with store.engine.connect() as conn:
        assert set(conn.execute(select(schema_versions.c.version)).scalars()) == set(range(1, CURRENT_SCHEMA_VERSION + 1))
    assert {"sharing_agreements", "fleet_reservations", "resource_locks"} <= set(metadata.tables)
    store.engine.dispose()


def test_api_pause_cancels_stale_step_and_resume_queues_current_version(environment, monkeypatch):
    store, client, author, _, _, headers = environment
    from airspace import orchestration
    monkeypatch.setattr(orchestration, "DefaultServices", TestOnlyServices)
    auth = headers(author["email"])
    row = client.post("/api/v1/agent-workflows", headers=auth, json={"task_kind": "regulatory_research", "objective": "Isolated pause and recovery verification", "jurisdiction": "LU", "operation_date": "2026-10-27", "controller_mode": "native"}).json()
    url = "/api/v1/agent-workflows/" + row["id"]
    client.post(url + "/advance", headers=auth, json={"expected_version": 1})
    paused = client.post(url + "/control", headers=auth, json={"action": "pause", "expected_version": 1})
    assert paused.status_code == 200, paused.text
    assert run_once(store) is None
    resumed = client.post(url + "/control", headers=auth, json={"action": "resume", "expected_version": paused.json()["version"]})
    assert resumed.status_code == 200, resumed.text
    for _ in range(4):
        assert run_once(store)["state"] == "Completed"
    assert client.get(url, headers=auth).json()["status"] == "Needs Review"
    states = [job["state"] for job in client.get("/api/v1/jobs", headers=auth).json()["items"]]
    assert states.count("Cancelled") == 1 and states.count("Completed") == 4


def test_revoked_actor_does_not_leave_an_apparently_runnable_workflow(environment):
    store, client, author, _, _, headers = environment
    auth = headers(author["email"])
    row = client.post("/api/v1/agent-workflows", headers=auth, json={"task_kind": "regulatory_research", "objective": "Isolated actor revocation check", "jurisdiction": "LU", "operation_date": "2026-10-27", "controller_mode": "native"}).json()
    client.post("/api/v1/agent-workflows/" + row["id"] + "/advance", headers=auth, json={"expected_version": 1})
    with store.engine.begin() as conn:
        conn.execute(update(users).where(users.c.id == author["id"]).values(role="viewer"))
    assert run_once(store)["state"] == "Failed"
    after = client.get("/api/v1/agent-workflows/" + row["id"], headers=auth).json()
    assert after["status"] == "Reconciliation Required"
    assert after["data"]["execution"]["tool_calls"] == 0
    assert after["data"]["artifacts"] == []


def test_country_validation_cannot_omit_sources_and_applicability_review(environment):
    _, client, author, _, _, headers = environment
    auth = headers(author["email"])
    row = client.post("/api/v1/records/country_review", headers=auth, json={"title": "Isolated semantically incomplete country review", "data": {"country_review": {"country": "LU", "pack_version": "isolated-reference", "valid_from": "2030-01-01T00:00:00Z", "valid_until": "2031-01-01T00:00:00Z", "framework": "EU UAS"}}}).json()
    response = client.post("/api/v1/records/country_review/" + row["id"] + "/transition", headers=auth, json={"state": "Under Review", "expected_version": 1, "reason": "Incomplete source review"})
    assert response.status_code == 422
    assert {"country_review.source_refs", "country_review.applicability_review_ref"} <= set(response.json()["detail"]["missing_inputs"])


def test_late_pause_cleanup_does_not_cancel_a_newer_resume(environment, monkeypatch):
    """Inject a completed concurrent resume between control and job cleanup."""
    from airspace import orchestration
    from airspace.orchestration import WorkflowRepository
    from airspace.coordination_api import queue_agent_step
    from airspace.storage import jobs
    store, client, author, _, _, headers = environment
    monkeypatch.setattr(orchestration, "DefaultServices", TestOnlyServices)
    auth = headers(author["email"])
    row = client.post("/api/v1/agent-workflows", headers=auth, json={"task_kind": "regulatory_research", "objective": "Isolated delayed pause cleanup fault injection", "jurisdiction": "LU", "operation_date": "2026-10-27", "controller_mode": "native"}).json()
    url = "/api/v1/agent-workflows/" + row["id"]
    client.post(url + "/advance", headers=auth, json={"expected_version": 1})
    original = WorkflowRepository.control
    def interleaved(repository, workflow_id, actor, action, expected_version):
        paused = original(repository, workflow_id, actor, action, expected_version)
        if action == "pause":
            resumed = original(repository, workflow_id, actor, "resume", paused["version"])
            with store.engine.begin() as conn:
                conn.execute(update(jobs).where(jobs.c.organisation_id == actor["organisation_id"], jobs.c.kind == "agent_orchestration", jobs.c.payload["workflow_id"].as_string() == workflow_id, jobs.c.state.in_(["Queued", "Running"])).values(state="Cancelled", lease_until=None, version=jobs.c.version + 1))
                queue_agent_step(store, resumed, actor, conn=conn)
        return paused
    monkeypatch.setattr(WorkflowRepository, "control", interleaved)
    response = client.post(url + "/control", headers=auth, json={"action": "pause", "expected_version": 1})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Queued" and response.json()["version"] == 3
    with store.engine.connect() as conn:
        queued = conn.execute(select(jobs).where(jobs.c.organisation_id == author["organisation_id"], jobs.c.state == "Queued")).mappings().all()
        assert len(queued) == 1 and queued[0]["payload"]["workflow_version"] == 3
    for _ in range(4):
        assert run_once(store)["state"] == "Completed"
    assert client.get(url, headers=auth).json()["status"] == "Needs Review"


def test_simultaneous_fresh_service_migrations_are_serialised(tmp_path):
    url = "sqlite:///" + (tmp_path / "fresh-start.db").as_posix()
    def migrate(_):
        service = Store(url, b"isolated-startup-migration-key-32bytes")
        try:
            service.migrate()
        finally:
            service.engine.dispose()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(migrate, range(8)))
    service = Store(url, b"isolated-startup-migration-key-32bytes")
    with service.engine.connect() as conn:
        assert set(conn.execute(select(schema_versions.c.version)).scalars()) == set(range(1, CURRENT_SCHEMA_VERSION + 1))
        assert {"sharing_agreements", "fleet_reservations", "resource_locks"} <= set(__import__('sqlalchemy').inspect(conn).get_table_names())
    service.engine.dispose()
