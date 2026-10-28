"""Real PostgreSQL coordination checks in disposable, isolated schemas only.

The URL must name the dedicated software-verification database. Every test
creates a fresh verification_<uuid> schema; public is excluded from search_path.
Artificial aircraft and permissions are isolated test inputs, never runtime data.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import os
import re
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from airspace.api import create_app
from airspace.identity import provision
from airspace.planning import cancel_schedule
from airspace.scheduler import ScheduleRequest, solve_schedule
from airspace.sharing import (decide_agreement, lock_physical_aircraft,
                              reserve_physical_aircraft)
from airspace.storage import Store, audit, fleet_reservations, jobs, records
from airspace.worker import run_once
from test_dispatch import (
    test_actual_assigned_pilot_and_internal_dispatch_are_distinct as exercise_pilot_dispatch,
    test_changed_country_permission_blocks_previously_acknowledged_dispatch as exercise_changed_instrument,
    test_material_input_change_invalidates_existing_internal_dispatch as exercise_dispatch_invalidation,
)
from test_planning import insert_record
from test_sharing import (
    accepted, borrowed_request,
    shared_fixture as build_shared_fixture,
    test_alias_identity_admission_requires_acceptance_and_cannot_strip_owner_binding as exercise_alias_identity,
    test_concurrent_cross_schedule_shared_reservations_have_one_winner as exercise_concurrent_borrowing,
    test_owner_and_borrower_cannot_double_book_same_physical_asset as exercise_owner_borrower_exclusion,
    test_owner_readiness_is_rechecked_after_acquiring_physical_lock as exercise_postlock_owner_revision,
    test_private_drafts_and_owner_records_never_cross_tenant_boundary as exercise_private_projection,
)


pytestmark = pytest.mark.skipif(
    not os.getenv("AIRSPACE_TEST_POSTGRES_URL"),
    reason="Isolated PostgreSQL service not configured; no coordination success is simulated",
)


@pytest.fixture
def pg_environment():
    """Match the API environment contract without using or dropping public tables."""
    base_url = make_url(os.environ["AIRSPACE_TEST_POSTGRES_URL"])
    if base_url.get_backend_name() != "postgresql":
        pytest.fail("AIRSPACE_TEST_POSTGRES_URL must name an isolated PostgreSQL database")
    schema = "verification_" + uuid4().hex
    assert re.fullmatch(r"verification_[0-9a-f]{32}", schema)
    administrator = create_engine(base_url, pool_pre_ping=True)
    store = client = None
    created = False
    try:
        with administrator.begin() as conn:
            conn.execute(CreateSchema(schema))
        created = True
        # Replace any supplied options: neither public nor a previous test schema
        # may participate in migration discovery or unqualified table resolution.
        isolated_url = base_url.update_query_dict({"options": "-csearch_path=" + schema})
        store = Store(isolated_url.render_as_string(hide_password=False),
                      b"isolated-postgres-coordination-test-key")

        @event.listens_for(store.engine, "connect")
        def bound_database_waits(connection, _):
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET statement_timeout = '10s'")
            connection.commit()

        with store.engine.connect() as conn:
            assert conn.execute(text("SELECT current_schema()")).scalar_one() == schema
            assert conn.execute(text("SELECT current_setting('search_path')")).scalar_one() == schema
            assert conn.execute(text("SELECT current_schemas(false)")).scalar_one() == [schema]
        store.migrate()
        with store.engine.connect() as conn:
            schemas = set(conn.execute(text(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = 'sharing_agreements' AND table_schema = :schema"
            ), {"schema": schema}).scalars())
            assert schemas == {schema}
        author = provision(store, "Isolated PG coordination owner", "author@test.invalid",
                           "regulatory", "isolated-test-password")
        reviewer = provision(store, "Isolated PG coordination owner", "reviewer@test.invalid",
                             "reviewer", "isolated-test-password", author["organisation_id"])
        other = provision(store, "Isolated PG coordination counterpart", "other@test.invalid",
                          "regulatory", "isolated-test-password")
        client = TestClient(create_app(store, serve_frontend=False))

        def headers(email):
            response = client.post("/api/v1/session", json={
                "email": email, "password": "isolated-test-password"})
            assert response.status_code == 200, response.text
            return {"Authorization": "Bearer " + response.json()["token"]}

        yield store, client, author, reviewer, other, headers
    finally:
        if client is not None:
            client.close()
        if store is not None:
            store.engine.dispose()
        if created:
            # The drop target is exclusively the schema generated above, never a
            # caller-provided name or public. No product database is dropped.
            assert re.fullmatch(r"verification_[0-9a-f]{32}", schema)
            with administrator.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
        administrator.dispose()


@pytest.fixture
def pg_shared(pg_environment):
    return build_shared_fixture.__wrapped__(pg_environment)


def test_postgres_private_shared_projection_and_record_access(pg_shared, pg_environment):
    exercise_private_projection(pg_shared)
    _, client, _, _, _, headers = pg_environment
    _, owner, operator, _, terms = pg_shared
    response = client.get("/api/v1/records/aircraft/" + terms["aircraft_id"],
                          headers=headers(operator["email"]))
    assert response.status_code == 404
    listed = client.get("/api/v1/records/aircraft", headers=headers(operator["email"]))
    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_postgres_owner_and_borrower_cannot_double_book(pg_shared):
    exercise_owner_borrower_exclusion(pg_shared)


def test_postgres_concurrent_borrower_reservations_have_one_winner(pg_shared):
    exercise_concurrent_borrowing(pg_shared)


def test_postgres_owner_revision_is_rechecked_after_canonical_lock(pg_shared, monkeypatch):
    exercise_postlock_owner_revision(pg_shared, monkeypatch)


def test_postgres_alias_cannot_remove_owner_binding(pg_shared):
    exercise_alias_identity(pg_shared)


def test_postgres_pilot_acknowledgement_and_internal_dispatch_are_separate(pg_environment):
    exercise_pilot_dispatch(pg_environment)


def test_postgres_changed_instrument_blocks_dispatch(pg_environment):
    exercise_changed_instrument(pg_environment)


def test_postgres_material_change_suspends_internal_dispatch(pg_environment):
    exercise_dispatch_invalidation(pg_environment)


def test_postgres_revoked_agreement_still_allows_internal_schedule_cancellation(pg_shared):
    store, owner, operator, payload, _ = pg_shared
    agreement = accepted(pg_shared)
    request, result, schedule_id = borrowed_request(pg_shared, agreement)
    planner = provision(store, "Isolated counterpart planner", "cancel-planner@test.invalid",
                        "planner", "isolated-test-password", operator["organisation_id"])
    with store.engine.begin() as conn:
        lock_physical_aircraft(conn, operator["organisation_id"], request, result)
        reserve_physical_aircraft(conn, operator["organisation_id"], request, result, schedule_id)
        conn.execute(update(records).where(records.c.id == schedule_id).values(status="Approved"))
        insert_record(conn, operator["organisation_id"], "dispatch_release", "test-pg-release",
                      {"schedule_id": schedule_id, "mission_id": request.missions[0].id},
                      operator["id"], "Internally Released")
    decide_agreement(store, agreement["id"], owner, "revoke", agreement["version"],
                     "Isolated PostgreSQL revocation test")
    cancelled = cancel_schedule(store, schedule_id, 1, planner,
                                "Cancel reserved proposed operation after agreement revocation")
    assert cancelled["status"] == "Cancelled"
    assert cancelled["data"]["_cancellation"]["released_physical_aircraft"] == 1
    with store.engine.connect() as conn:
        assert conn.execute(select(fleet_reservations.c.state)).scalar_one() == "Released"
        # The earlier revocation already invalidated this release. Cancellation
        # retains that historical suspension and cancels the schedule itself.
        assert conn.execute(select(records.c.status).where(records.c.id == "test-pg-release")).scalar_one() == "Suspended"
    # A new owner proposal may reserve the released interval. It receives a new
    # reservation, rather than reviving the cancelled counterpart's proposal.
    own_request = ScheduleRequest.model_validate(payload)
    own_result = solve_schedule(own_request)
    with store.engine.begin() as conn:
        insert_record(conn, owner["organisation_id"], "schedule", "test-pg-owner-rebooking",
                      {"input": own_request.model_dump(mode="json"), "result": own_result},
                      owner["id"], "Draft")
        lock_physical_aircraft(conn, owner["organisation_id"], own_request, own_result)
        reserve_physical_aircraft(conn, owner["organisation_id"], own_request,
                                  own_result, "test-pg-owner-rebooking")
        assert len(conn.execute(select(fleet_reservations).where(
            fleet_reservations.c.state == "Reserved")).all()) == 1
    assert store.verify_audit(owner["organisation_id"])["valid"]
    assert store.verify_audit(operator["organisation_id"])["valid"]


def test_postgres_owner_and_counterpart_simultaneous_booking_have_one_winner(pg_shared):
    store, owner, operator, payload, _ = pg_shared
    agreement = accepted(pg_shared)
    borrowed = borrowed_request(pg_shared, agreement)
    own_request = ScheduleRequest.model_validate(payload)
    own_result = solve_schedule(own_request)
    own_id = "test-pg-concurrent-owner"
    with store.engine.begin() as conn:
        insert_record(conn, owner["organisation_id"], "schedule", own_id,
                      {"input": own_request.model_dump(mode="json"), "result": own_result},
                      owner["id"], "Draft")
    proposals = [(owner["organisation_id"], own_request, own_result, own_id),
                 (operator["organisation_id"], *borrowed)]
    barrier = Barrier(2, timeout=5)

    def reserve(proposal):
        tenant, request, result, schedule_id = proposal
        barrier.wait()
        try:
            with store.engine.begin() as conn:
                lock_physical_aircraft(conn, tenant, request, result)
                reserve_physical_aircraft(conn, tenant, request, result, schedule_id)
            return 200
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reserve, proposal) for proposal in proposals]
        assert sorted(future.result(timeout=15) for future in futures) == [200, 409]
    with store.engine.connect() as conn:
        rows = conn.execute(select(fleet_reservations).where(
            fleet_reservations.c.state == "Reserved")).mappings().all()
        assert len(rows) == 1
        assert rows[0]["owner_organisation_id"] == owner["organisation_id"]


def test_postgres_worker_pause_wins_over_inflight_finish(pg_environment, monkeypatch):
    from airspace import worker
    store, client, author, _, _, headers = pg_environment
    auth = headers(author["email"])
    with store.engine.begin() as conn:
        insert_record(conn, author["organisation_id"], "case", "test-pg-paused-case", {},
                      author["id"], "Draft")
    entered, finish_allowed = Event(), Event()

    def blocked_assessment(_):
        entered.set()
        assert finish_allowed.wait(8), "Test must release the bounded worker gate"
        return ["Isolated software-test missing input"]

    monkeypatch.setattr(worker, "missing_evidence", blocked_assessment)
    created = client.post("/api/v1/jobs", headers=auth, json={"kind": "case_preparation"})
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_once, store)
        try:
            assert entered.wait(5), "Worker did not enter its isolated analysis gate"
            paused = client.post("/api/v1/jobs/" + job_id + "/pause", headers=auth)
            assert paused.status_code == 200, paused.text
        finally:
            finish_allowed.set()
        future.result(timeout=15)
    with store.engine.connect() as conn:
        row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().one()
        assert row["state"] == "Paused" and row["version"] == 3
        assert row["result"] is None
        finished = conn.execute(select(audit.c.payload).where(
            audit.c.organisation_id == author["organisation_id"],
            audit.c.action == "job.finished")).scalars().all()
        assert not any(item["job_id"] == job_id for item in finished)
    assert store.verify_audit(author["organisation_id"])["valid"]


def test_postgres_worker_pause_and_finish_use_consistent_lock_order(pg_environment, monkeypatch):
    from airspace import worker
    store, client, author, _, _, headers = pg_environment
    auth = headers(author["email"])
    with store.engine.begin() as conn:
        insert_record(conn, author["organisation_id"], "case", "test-pg-racing-case", {},
                      author["id"], "Draft")
    for _ in range(4):
        entered, race = Event(), Event()

        def blocked_assessment(_):
            entered.set()
            assert race.wait(8), "Test must release the bounded worker race gate"
            return ["Isolated software-test missing input"]

        monkeypatch.setattr(worker, "missing_evidence", blocked_assessment)
        created = client.post("/api/v1/jobs", headers=auth, json={"kind": "case_preparation"})
        assert created.status_code == 201, created.text
        job_id = created.json()["id"]

        def pause():
            assert race.wait(8)
            return client.post("/api/v1/jobs/" + job_id + "/pause", headers=auth)

        with ThreadPoolExecutor(max_workers=2) as pool:
            completion = pool.submit(run_once, store)
            try:
                assert entered.wait(5), "Worker did not enter its isolated analysis gate"
                control = pool.submit(pause)
            finally:
                race.set()
            outcome = control.result(timeout=15)
            completion.result(timeout=15)
        assert outcome.status_code in {200, 409}, outcome.text
        with store.engine.connect() as conn:
            row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().one()
            if outcome.status_code == 200:
                assert row["state"] == "Paused" and row["result"] is None
            else:
                assert row["state"] == "Completed" and row["result"] is not None
            assert row["version"] == 3
    assert store.verify_audit(author["organisation_id"])["valid"]
