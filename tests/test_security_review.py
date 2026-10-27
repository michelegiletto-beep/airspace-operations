"""Adversarial regression tests. Inputs exist only in isolated test stores."""
import base64
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from airspace.evidence import blob_path
from airspace.storage import audit, jobs, records, users
from airspace.worker import run_once


def test_reviewer_cannot_edit_then_approve_own_revision(environment):
    _, client, author, reviewer, _, headers = environment
    ah, rh = headers(author["email"]), headers(reviewer["email"])
    evidence = client.post("/api/v1/records/evidence", headers=ah, json={"title": "Isolated fixture", "data": {"provenance": "Software Test", "checksum": "0" * 64, "evidence_type": "Software Test"}}).json()
    case = client.post("/api/v1/records/case", headers=ah, json={"title": "Isolated test", "data": {"jurisdiction": "LU", "legal_route": "specific", "conops": "Isolated test fixture", "owner": author["id"], "aircraft_configuration_id": "test-only", "reviewer_ids": [reviewer["id"]], "evidence_ids": [evidence["id"]]}}).json()
    url = "/api/v1/records/case/" + case["id"]
    assert client.put(url, headers=rh, json={"expected_version": 1, "title": "Prepared by isolated reviewer"}).status_code == 200
    assert client.post(url + "/transition", headers=rh, json={"expected_version": 2, "state": "Under Review", "reason": "Isolated regression test"}).status_code == 200
    assert client.post(url + "/transition", headers=rh, json={"expected_version": 3, "state": "Approved", "reason": "Isolated regression test", "evidence_ids": [evidence["id"]]}).status_code == 403


def test_clients_cannot_set_review_policy_or_decision_metadata(environment):
    _, client, author, _, _, headers = environment
    ah = headers(author["email"])
    for data in ({"_prepared_by": "other"}, {"_approvals": []}, {"independent_second_reviewer": False}):
        assert client.post("/api/v1/records/case", headers=ah, json={"title": "Isolated attempt", "data": data}).status_code == 422


def test_typed_engine_error_is_422_not_internal_error(environment):
    _, client, author, _, _, headers = environment
    response = client.post("/api/v1/site/screen", headers=headers(author["email"]), json={"point": {"latitude": 200}})
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()


def test_chunked_request_limit_rejects_large_body(environment):
    _, client, _, _, _, _ = environment
    # No Content-Length header. This checks the streaming bound rather than a
    # header-only limit; it is not a memory/DoS performance certification.
    def chunks():
        yield b"x" * 1_100_000
        yield b"x" * 1_100_000
    assert client.post("/api/v1/session", content=chunks(), headers={"Content-Type": "application/json"}).status_code == 413


def test_exhausted_worker_lease_is_audited_terminal_failure(environment):
    store, client, author, _, _, headers = environment
    job = client.post("/api/v1/jobs", headers=headers(author["email"]), json={"kind": "case_preparation"}).json()
    with store.engine.begin() as conn:
        conn.execute(update(jobs).where(jobs.c.id == job["id"]).values(state="Running", attempts=3, lease_until=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()))
    assert run_once(store) is None
    with store.engine.connect() as conn:
        row = conn.execute(select(jobs).where(jobs.c.id == job["id"])).mappings().one()
        assert row["state"] == "Failed"
        assert conn.execute(select(audit.c.id).where(audit.c.action == "job.exhausted")).first()


def test_workflow_tools_authorised_at_enqueue_and_execution(environment):
    store, client, author, _, _, headers = environment
    ah = headers(author["email"])
    assert client.post("/api/v1/jobs", headers=ah, json={"kind": "scheduling_proposal"}).status_code == 403
    job = client.post("/api/v1/jobs", headers=ah, json={"kind": "case_preparation"}).json()
    with store.engine.begin() as conn:
        conn.execute(update(users).where(users.c.id == author["id"]).values(role="analyst"))
    assert run_once(store)["state"] == "Failed"


def test_evidence_tenant_boundary_integrity_and_metadata_binding(environment, tmp_path, monkeypatch):
    store, client, author, _, other, headers = environment
    monkeypatch.setenv("AIRSPACE_RUNTIME", str(tmp_path / "isolated-object-store"))
    ah, oh = headers(author["email"]), headers(other["email"])
    forged = {"attachment": {"sha256": "0" * 64}, "checksum": "0" * 64}
    assert client.post("/api/v1/records/evidence", headers=ah, json={"title": "Isolated metadata injection", "data": forged}).status_code == 422
    evidence = client.post("/api/v1/records/evidence", headers=ah, json={"title": "Isolated text fixture", "data": {"provenance": "Software Test", "evidence_type": "Software Test"}}).json()
    assert client.put("/api/v1/records/evidence/" + evidence["id"], headers=ah, json={"expected_version": 1, "data": forged}).status_code == 422
    url = "/api/v1/evidence/" + evidence["id"] + "/content"
    content = b"Isolated software test data; not an authority instrument."
    uploaded = client.put(url, headers=ah, json={"original_name": "test-only.txt", "media_type": "text/plain", "content_base64": base64.b64encode(content).decode(), "expected_version": 1})
    assert uploaded.status_code == 200
    assert client.get(url, headers=ah).content == content
    assert client.get(url, headers=oh).status_code == 404
    data = {k: v for k, v in uploaded.json()["data"].items() if not k.startswith("_")}
    data["checksum"] = "f" * 64
    assert client.put("/api/v1/records/evidence/" + evidence["id"], headers=ah, json={"expected_version": 2, "data": data}).status_code == 422
    path = blob_path(author["organisation_id"], uploaded.json()["data"]["checksum"])
    path.write_bytes(b"Isolated tampering test")
    assert client.get(url, headers=ah).status_code == 409


def test_controlled_html_report_escapes_untrusted_markup(environment):
    _, client, author, _, _, headers = environment
    ah = headers(author["email"])
    row = client.post("/api/v1/records/case", headers=ah, json={"title": "<script>test-only</script>", "data": {"conops": "<img src=x onerror=test-only>"}}).json()
    response = client.get("/api/v1/records/case/" + row["id"] + "/export?format=html", headers=ah)
    assert response.status_code == 200
    assert "<script>test-only</script>" not in response.text
    assert "&lt;script&gt;test-only&lt;/script&gt;" in response.text
