"""Durable generation-budget fault tests; no actual model or operational data."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Barrier

from fastapi import HTTPException
import pytest
from sqlalchemy import select, update

from airspace import assistant
from airspace.assistant import CompanionBudgetExhausted, _reserve_generation
from airspace.storage import Store, audit, jobs, records, users
from airspace.worker import run_once
from test_companion import TestOnlyReplyService, begin, finish


class IsolatedWorkerCrash(BaseException):
    """Bypass worker's Exception handler to model actual process interruption."""


def message_row(store, pending):
    with store.engine.connect() as conn:
        return dict(conn.execute(select(records).where(records.c.id == pending["user_message"]["id"])).mappings().one())


def expire_lease(store, pending):
    with store.engine.begin() as conn:
        conn.execute(update(jobs).where(jobs.c.id == pending["job"]["id"]).values(
            lease_until=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()))


def claim_without_generation(store, pending):
    candidate = pending["job"]
    with store.engine.begin() as conn:
        conn.execute(update(jobs).where(jobs.c.id == candidate["id"]).values(
            state="Running", attempts=candidate["attempts"] + 1, version=candidate["version"] + 1,
            lease_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()))
    return candidate


def test_format_repair_uses_exactly_declared_job_budget(environment):
    service = TestOnlyReplyService(invalid="invalid structured output")
    store, client, author, auth, base, pending = begin(environment, "How do I review a source?", service=service)
    initial = message_row(store, pending)["data"]["generation_budget"]
    assert initial["job_id"] == pending["job"]["id"] and initial["reservations"] == []
    _, detail = finish(store, client, auth, base)
    assert len(service.views) == 2
    ledger = message_row(store, pending)["data"]["generation_budget"]
    assert len(ledger["reservations"]) == ledger["max_model_calls"] == 2
    reply = detail["messages"][-1]["data"]
    assert reply["model"]["model_calls"] == 2
    assert reply["model"]["generation_budget"]["reserved_calls"] == 2
    assert store.verify_audit(author["organisation_id"])["valid"]


def test_one_call_limit_does_not_gain_a_repair_call(environment):
    service = TestOnlyReplyService(invalid="invalid structured output")
    store, client, author, auth, base, pending = begin(environment, "How do I inspect a record?", service=service,
        options={"budget": {"max_model_calls": 1}})
    finish(store, client, auth, base)
    assert len(service.views) == 1
    assert len(message_row(store, pending)["data"]["generation_budget"]["reservations"]) == 1


def test_crash_after_reservation_before_generation_never_refunds_allowance(environment, monkeypatch):
    store, client, author, auth, base, pending = begin(environment, "How do I inspect a record?")
    service = store._companion_services
    reserve = assistant._reserve_generation
    def reserve_then_stop(*args):
        result = reserve(*args)
        raise IsolatedWorkerCrash("Isolated interruption after durable charge")
    monkeypatch.setattr(assistant, "_reserve_generation", reserve_then_stop)
    for expected in (1, 2):
        with pytest.raises(IsolatedWorkerCrash):
            run_once(store)
        assert len(message_row(store, pending)["data"]["generation_budget"]["reservations"]) == expected
        expire_lease(store, pending)
    monkeypatch.setattr(assistant, "_reserve_generation", reserve)
    result, detail = finish(store, client, auth, base)
    assert result["state"] == "Failed" and service.views == []
    reply = detail["messages"][-1]["data"]
    assert reply["model"]["status"]["state"] == "Budget Exhausted"
    assert reply["model"]["model_calls"] == 0
    assert reply["model"]["generation_budget"]["reserved_calls"] == 2


def test_crashes_during_generation_and_store_restart_keep_total_calls_bounded(environment):
    class CrashService:
        def __init__(self): self.calls = 0
        def generate(self, view, budget, cancelled):
            self.calls += 1
            raise IsolatedWorkerCrash("Isolated process interruption during model service")
    service = CrashService()
    store, client, author, auth, base, pending = begin(environment, "How do I inspect a record?", service=service)
    with pytest.raises(IsolatedWorkerCrash): run_once(store)
    expire_lease(store, pending)
    restarted = Store(store.url, store.key)
    restarted._companion_services = service
    try:
        restarted.migrate()
        with pytest.raises(IsolatedWorkerCrash): run_once(restarted)
        expire_lease(restarted, pending)
        assert run_once(restarted)["state"] == "Failed"
    finally:
        restarted.engine.dispose()
    assert service.calls == 2
    detail = client.get(base, headers=auth).json()
    assert detail["messages"][-1]["data"]["model"]["generation_budget"]["reserved_calls"] == 2
    assert len(detail["messages"]) == 2
    assert store.verify_audit(author["organisation_id"])["valid"]


def test_concurrent_reservations_cannot_exceed_the_job_limit(environment):
    store, _, author, _, _, pending = begin(environment, "How do I inspect a record?")
    candidate = claim_without_generation(store, pending)
    barrier = Barrier(4)
    def reserve():
        barrier.wait(timeout=5)
        try:
            return _reserve_generation(store, candidate, author)
        except CompanionBudgetExhausted:
            return None
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(reserve) for _ in range(3)]
        barrier.wait(timeout=5)
        results = [future.result(timeout=10) for future in futures]
    assert sum(result is not None for result in results) == 2
    ledger = message_row(store, pending)["data"]["generation_budget"]
    assert len(ledger["reservations"]) == len({item["id"] for item in ledger["reservations"]}) == 2
    assert {item["job_version"] for item in ledger["reservations"]} == {candidate["version"] + 1}
    with store.engine.connect() as conn:
        charges = conn.execute(select(audit).where(audit.c.action == "companion.generation.reserved")).mappings().all()
    assert len(charges) == 2 and store._companion_services.views == []


@pytest.mark.parametrize("change", ["expired_lease", "expired_deadline", "reclaimed_version", "cancelled", "changed_role", "wrong_actor", "other_tenant", "changed_scope"])
def test_stale_lease_scope_or_actor_cannot_reserve_generation(environment, change):
    store, _, author, _, _, pending = begin(environment, "How do I inspect a record?")
    _, _, _, peer, other, _ = environment
    candidate = claim_without_generation(store, pending)
    actor = author
    with store.engine.begin() as conn:
        if change in {"expired_lease", "expired_deadline"}:
            field = "lease_until" if change == "expired_lease" else "deadline"
            conn.execute(update(jobs).where(jobs.c.id == candidate["id"]).values(**{field: (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}))
        elif change == "reclaimed_version":
            conn.execute(update(jobs).where(jobs.c.id == candidate["id"]).values(version=candidate["version"] + 2))
        elif change == "cancelled":
            conn.execute(update(jobs).where(jobs.c.id == candidate["id"]).values(state="Cancelled"))
        elif change == "changed_role":
            conn.execute(update(users).where(users.c.id == author["id"]).values(role="viewer"))
        elif change == "wrong_actor": actor = peer
        elif change == "other_tenant": actor = other
        else:
            row = message_row(store, pending)
            data = deepcopy(row["data"]); data["scope_checksum"] = "invalid-isolated-fixture-checksum"
            conn.execute(update(records).where(records.c.id == row["id"]).values(data=data))
    with pytest.raises((HTTPException, InterruptedError)):
        _reserve_generation(store, candidate, actor)
    assert message_row(store, pending)["data"]["generation_budget"]["reservations"] == []


@pytest.mark.parametrize("invalid", [None, {"max_model_calls": 2}, "invalid ledger"])
def test_missing_or_malformed_historical_accounting_never_starts_generation(environment, invalid):
    store, client, author, auth, base, pending = begin(environment, "How do I inspect a record?")
    with store.engine.begin() as conn:
        row = message_row(store, pending)
        data = deepcopy(row["data"])
        if invalid is None: data.pop("generation_budget")
        else: data["generation_budget"] = invalid
        conn.execute(update(records).where(records.c.id == row["id"]).values(data=data))
    _, detail = finish(store, client, auth, base)
    assert store._companion_services.views == []
    assert detail["messages"][-1]["data"]["model"]["status"]["state"] == "Budget Unavailable"


def test_reservation_audit_failure_rolls_back_charge_before_model_service(environment, monkeypatch):
    store, client, author, auth, base, pending = begin(environment, "How do I inspect a record?")
    append = store.append_audit
    def unavailable(conn, tenant, actor, action, payload):
        if action == "companion.generation.reserved":
            raise RuntimeError("Isolated audit storage interruption")
        return append(conn, tenant, actor, action, payload)
    monkeypatch.setattr(store, "append_audit", unavailable)
    assert run_once(store)["state"] == "Failed"
    assert store._companion_services.views == []
    assert message_row(store, pending)["data"]["generation_budget"]["reservations"] == []


def test_approved_procedure_guidance_spends_no_generation_allowance(environment):
    store, client, author, auth, base, pending = begin(environment, "How do I inspect an incident?", workspace="incidents")
    _, detail = finish(store, client, auth, base)
    assert store._companion_services.views == []
    assert message_row(store, pending)["data"]["generation_budget"]["reservations"] == []
    assert detail["messages"][-1]["data"]["model"]["generation_budget"]["reserved_calls"] == 0


def test_material_context_revision_blocks_reservation_before_any_call(environment):
    store, client, author, _, _, headers = environment
    response = client.post("/api/v1/records/case", headers=headers(author["email"]), json={"title": "Isolated version-bound budget fixture"})
    assert response.status_code == 201
    context = response.json()
    _, _, _, _, _, pending = begin(environment, "How do I review this record?", context=[context["id"]])
    candidate = claim_without_generation(store, pending)
    with store.engine.begin() as conn:
        conn.execute(update(records).where(records.c.id == context["id"]).values(version=context["version"] + 1))
    with pytest.raises(HTTPException, match="current inputs changed"):
        _reserve_generation(store, candidate, author)
    assert message_row(store, pending)["data"]["generation_budget"]["reservations"] == []
    assert store._companion_services.views == []


def test_stale_worker_failure_cannot_clear_newer_claims_pending_turn(environment):
    store, client, author, auth, base, pending = begin(environment, "How do I inspect a record?")
    def reclaim_inflight():
        with store.engine.begin() as conn:
            current = conn.execute(select(jobs).where(jobs.c.id == pending["job"]["id"])).mappings().one()
            conn.execute(update(jobs).where(jobs.c.id == current["id"]).values(
                version=current["version"] + 1, attempts=current["attempts"] + 1,
                lease_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()))
    store._companion_services = TestOnlyReplyService(before_return=reclaim_inflight)
    assert run_once(store)["state"] == "Failed"
    detail = client.get(base, headers=auth).json()
    assert detail["conversation"]["data"]["active_message_id"] == pending["user_message"]["id"]
    assert detail["active_job"]["state"] == "Running"
    assert len(detail["messages"]) == 1 and detail["messages"][0]["status"] == "Queued"
    assert len(detail["messages"][0]["data"]["generation_budget"]["reservations"]) == 1


def test_cleanup_requires_exact_terminal_job_revision(environment):
    store, client, author, auth, base, pending = begin(environment, "How do I inspect a record?")
    candidate = claim_without_generation(store, pending)
    assistant.mark_companion_job_failure(store, candidate, "Isolated stale failure", expected_job_version=2)
    assert client.get(base, headers=auth).json()["conversation"]["data"]["active_message_id"]
    with store.engine.begin() as conn:
        conn.execute(update(jobs).where(jobs.c.id == candidate["id"]).values(state="Failed", version=4))
    assistant.mark_companion_job_failure(store, candidate, "Isolated wrong revision", expected_job_version=3)
    assert client.get(base, headers=auth).json()["conversation"]["data"]["active_message_id"]
    assistant.mark_companion_job_failure(store, candidate, "Isolated current failure", expected_job_version=4)
    detail = client.get(base, headers=auth).json()
    assert detail["conversation"]["data"]["active_message_id"] is None
    assert detail["messages"][0]["status"] == "Failed"


def test_returned_attempts_are_correlated_with_persisted_reservations(environment):
    store, client, author, auth, base, pending = begin(environment, "How do I inspect a record?")
    _, detail = finish(store, client, auth, base)
    ledger = message_row(store, pending)["data"]["generation_budget"]
    reply = detail["messages"][-1]["data"]
    assert [item["generation_reservation_id"] for item in reply["model"]["attempts"]] == [item["id"] for item in ledger["reservations"]]
