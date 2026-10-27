"""Versioned authenticated application API."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import delete, select, update

from . import __version__
from .identity import authenticate, login, require_role
from .storage import (Store, audit, canonical, identifier, idempotency, jobs,
                      local_store, now, outbox, records, sessions, users, versions)
from .workflows import KINDS, check_transition, missing_evidence

ROOT = Path(__file__).resolve().parents[2]
WRITERS = {"administrator", "regulatory", "reviewer", "planner", "pilot", "fleet_manager", "incident_coordinator", "analyst"}
JOB_KINDS = {"regulatory_monitor", "evidence_collection", "case_preparation", "site_screening", "scheduling_proposal", "incident_summary", "commercial_analysis"}
KIND_ROLES = {
    "permission": {"regulatory", "reviewer"}, "case": {"regulatory", "reviewer"},
    "evidence": {"regulatory", "reviewer", "fleet_manager", "planner"},
    "aircraft": {"fleet_manager"}, "qualification": {"fleet_manager", "reviewer"},
    "personnel": {"fleet_manager"}, "incident": {"incident_coordinator", "pilot"},
    "procedure": {"regulatory", "reviewer"}, "commercial": {"analyst"},
    "mission": {"planner", "pilot"}, "schedule": {"planner"},
    "telemetry": set(), "alert": set(), "approval": set(), "connector": {"administrator"},
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credentials(Strict):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class NewRecord(Strict):
    title: str = Field(min_length=1, max_length=240)
    data: dict[str, Any] = Field(default_factory=dict)


class EditRecord(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    data: dict[str, Any] | None = None
    expected_version: int = Field(ge=1)


class Transition(Strict):
    state: str
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=200)


class Query(Strict):
    question: str = Field(min_length=3, max_length=4000)
    jurisdiction: str = Field(min_length=2, max_length=40)
    operation_date: str
    methodology: str | None = None


class JobRequest(Strict):
    kind: str
    payload: dict = Field(default_factory=dict)
    deadline: str | None = None


def row_get(conn, tenant, kind, item_id):
    row = conn.execute(select(records).where(records.c.id == item_id, records.c.organisation_id == tenant, records.c.kind == kind)).mappings().first()
    if not row:
        raise HTTPException(404, "Record not found")
    return dict(row)


def lock_tenant(conn, tenant):
    from .storage import organisations
    conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq))


def kind_check(kind):
    if kind not in KINDS:
        raise HTTPException(404, "Unknown record kind")


def can_write(user, kind):
    require_role(user, KIND_ROLES.get(kind, WRITERS))


def check_references(conn, tenant, data):
    # References are never accepted as proof merely because they look like UUIDs.
    reference_fields = {"evidence_ids": {"evidence"}, "permission_ids": {"permission"}, "requirement_ids": {"requirement"}, "receipt_evidence_id": {"evidence"}, "submission_receipt_evidence_id": {"evidence"}, "aircraft_id": {"aircraft"}, "route_id": {"route"}, "procedure_id": {"procedure"}}
    for field, kinds in reference_fields.items():
        values = data.get(field, [])
        if values in (None, ""):
            continue
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if not isinstance(value, str):
                raise HTTPException(422, f"Invalid reference: {field}")
            found = conn.execute(select(records.c.id).where(records.c.id == value, records.c.organisation_id == tenant, records.c.kind.in_(kinds))).first()
            if not found:
                raise HTTPException(422, f"Unknown tenant reference: {field}")
    reviewers = data.get("reviewer_ids", [])
    if not isinstance(reviewers, list):
        raise HTTPException(422, "reviewer_ids must be a list")
    for reviewer in reviewers:
        if not conn.execute(select(users.c.id).where(users.c.id == reviewer, users.c.organisation_id == tenant, users.c.role == "reviewer", users.c.disabled == 0)).first():
            raise HTTPException(422, "Reviewer must be an active reviewer in this organisation")
    # Approval records are reserved server metadata.
    if any(str(key).startswith("_") for key in data) or "independent_second_reviewer" in data:
        raise HTTPException(422, "Decision metadata is server controlled")


def create_app(store: Store | None = None, serve_frontend=True):
    store = store or local_store()
    store.migrate()
    app = FastAPI(title="System Lab Airspace Operations", version=__version__, description="Decision support. No aircraft control or authority-issued permissions.", openapi_url="/api/v1/openapi.json", docs_url="/api/docs")
    app.state.store = store
    login_attempts = defaultdict(deque)

    @app.exception_handler(ValidationError)
    async def engine_validation_error(request, exc):
        return JSONResponse({"detail": json.loads(exc.json(include_input=False, include_context=False))}, status_code=422)

    @app.exception_handler(ValueError)
    async def domain_validation_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.middleware("http")
    async def protections(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 2_000_000):
            return JSONResponse({"detail": "Request body exceeds limit"}, status_code=413)
        # Bound chunked bodies as well. The API accepts JSON, never executable uploads.
        if request.method in {"POST", "PUT", "PATCH"}:
            chunks, total = [], 0
            async for chunk in request.stream():
                total += len(chunk)
                if total > 2_000_000:
                    return JSONResponse({"detail": "Request body exceeds limit"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def current(authorization: str | None = Header(default=None)):
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
        return authenticate(store, token)

    @app.get("/api/v1/health")
    def health():
        with store.engine.connect() as conn:
            conn.execute(select(1))
        return {"status": "ok", "version": __version__, "deployment_profile": "sqlite-portable" if store.url.startswith("sqlite") else "postgresql", "operational_acceptance": False}

    @app.post("/api/v1/session")
    def session(payload: Credentials, request: Request):
        address = request.client.host if request.client else "unknown"
        queue = login_attempts[address]
        stamp = time.monotonic()
        while queue and queue[0] < stamp - 60:
            queue.popleft()
        if len(queue) >= 12:
            raise HTTPException(429, "Too many sign-in attempts; retry after one minute")
        queue.append(stamp)
        return login(store, payload.email, payload.password)

    @app.delete("/api/v1/session")
    def logout(user=Depends(current), authorization: str = Header()):
        with store.engine.begin() as conn:
            conn.execute(delete(sessions).where(sessions.c.digest == hashlib.sha256(authorization[7:].encode()).hexdigest()))
            store.append_audit(conn, user["organisation_id"], user["id"], "identity.logout", {})
        return {"revoked": True}

    @app.get("/api/v1/me")
    def me(user=Depends(current)):
        return user

    @app.get("/api/v1/users")
    def colleagues(user=Depends(current)):
        with store.engine.connect() as conn:
            items = conn.execute(select(users.c.id, users.c.email, users.c.role).where(users.c.organisation_id == user["organisation_id"], users.c.disabled == 0)).mappings().all()
        return {"items": [dict(x) for x in items]}

    @app.get("/api/v1/records/{kind}")
    def list_records(kind: str, q: str = "", user=Depends(current)):
        kind_check(kind)
        stmt = select(records).where(records.c.kind == kind, records.c.organisation_id == user["organisation_id"])
        if q:
            stmt = stmt.where(records.c.title.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"))
        with store.engine.connect() as conn:
            items = conn.execute(stmt.order_by(records.c.updated_at.desc()).limit(1000)).mappings().all()
        return {"items": [dict(x) for x in items], "total": len(items), "limit": 1000}

    @app.post("/api/v1/records/{kind}", status_code=201)
    def create_record(kind: str, payload: NewRecord, user=Depends(current), idempotency_key: str | None = Header(default=None)):
        kind_check(kind)
        can_write(user, kind)
        if kind == "schedule":
            raise HTTPException(422, "Schedule records are created only by the solver workflow")
        if kind == "evidence" and "attachment" in payload.data:
            raise HTTPException(422, "Attachments can only be created by the content upload endpoint")
        if idempotency_key and len(idempotency_key) > 200:
            raise HTTPException(422, "Idempotency key is too long")
        digest = hashlib.sha256(canonical({"kind": kind, **payload.model_dump()}).encode()).hexdigest()
        tenant = user["organisation_id"]
        with store.engine.begin() as conn:
            # Serialise same-tenant mutations including idempotency lookup.
            from .storage import organisations
            conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq))
            if idempotency_key:
                prior = conn.execute(select(idempotency).where(idempotency.c.organisation_id == tenant, idempotency.c.key == idempotency_key)).mappings().first()
                if prior:
                    if prior["request_hash"] != digest:
                        raise HTTPException(409, "Idempotency key was already used for different input")
                    return prior["response"]
            check_references(conn, tenant, payload.data)
            row = dict(id=identifier(), organisation_id=tenant, kind=kind, title=payload.title.strip(), status="Draft", data={**payload.data, "_prepared_by": user["id"]}, version=1, created_by=user["id"], created_at=now(), updated_at=now())
            conn.execute(records.insert().values(**row))
            store.snapshot(conn, row)
            store.append_audit(conn, tenant, user["id"], f"{kind}.created", {"record_id": row["id"], "version": 1, "snapshot_sha256": hashlib.sha256(canonical(row).encode()).hexdigest()})
            if idempotency_key:
                conn.execute(idempotency.insert().values(organisation_id=tenant, key=idempotency_key, request_hash=digest, response=row))
        return row

    @app.get("/api/v1/records/{kind}/{item_id}")
    def get_record(kind: str, item_id: str, user=Depends(current)):
        kind_check(kind)
        with store.engine.connect() as conn:
            row = row_get(conn, user["organisation_id"], kind, item_id)
        return {**row, "missing_inputs": missing_evidence(row)}

    @app.put("/api/v1/records/{kind}/{item_id}")
    def edit_record(kind: str, item_id: str, payload: EditRecord, user=Depends(current)):
        kind_check(kind)
        can_write(user, kind)
        tenant = user["organisation_id"]
        with store.engine.begin() as conn:
            lock_tenant(conn, tenant)
            row = row_get(conn, tenant, kind, item_id)
            if row["version"] != payload.expected_version:
                raise HTTPException(409, "Record changed; reload before saving")
            if row["status"] in {"Submitted", "Superseded", "Expired"}:
                raise HTTPException(409, "Controlled record cannot be overwritten; create a revision")
            if kind == "schedule" and row["status"] in {"Approved", "Cancelled"}:
                raise HTTPException(409, "Reserved schedules require explicit cancellation; cancelled schedules require a new proposal")
            if payload.data is not None:
                check_references(conn, tenant, payload.data)
                if kind == "evidence" and row["data"].get("attachment") and any(payload.data.get(key) != row["data"].get(key) for key in ("attachment", "checksum")):
                    raise HTTPException(422, "Upload-bound attachment integrity metadata cannot be changed through record editing")
                if kind == "evidence" and payload.data.get("attachment") and not row["data"].get("attachment"):
                    raise HTTPException(422, "Attachments can only be created by the content upload endpoint")
                if kind == "schedule" and any(payload.data.get(key) != row["data"].get(key) for key in ("input", "result", "input_record_versions")):
                    raise HTTPException(422, "Solver inputs and outputs are controlled; generate a new proposal")
                row["data"] = {**payload.data, "_prepared_by": user["id"]}
            else:
                row["data"] = {**{k: v for k, v in row["data"].items() if not k.startswith("_")}, "_prepared_by": user["id"]}
            if payload.title is not None:
                row["title"] = payload.title.strip()
            row.update(version=row["version"] + 1, updated_at=now(), status="Draft")
            result = conn.execute(update(records).where(records.c.id == item_id, records.c.organisation_id == tenant, records.c.version == payload.expected_version).values(**row))
            if result.rowcount != 1:
                raise HTTPException(409, "Concurrent update rejected")
            store.snapshot(conn, row)
            store.append_audit(conn, tenant, user["id"], f"{kind}.revised", {"record_id": item_id, "version": row["version"], "approval_reset": True})
            # Material revisions produce an explicit impact task; never silently rewrite dependent records.
            if kind in {"aircraft", "route", "evidence", "procedure", "permission", "obligation"}:
                task = dict(id=identifier(), organisation_id=tenant, kind="review_task", title=f"Review impact: {row['title']}", status="Draft", data={"changed_record_id": item_id, "changed_version": row["version"], "owner": user["id"], "reason": "Controlled input changed; dependent cases and schedules require assessment"}, version=1, created_by=user["id"], created_at=now(), updated_at=now())
                conn.execute(records.insert().values(**task))
                store.snapshot(conn, task)
        return row

    @app.post("/api/v1/records/{kind}/{item_id}/transition")
    def transition(kind: str, item_id: str, payload: Transition, user=Depends(current)):
        kind_check(kind)
        if kind == "schedule":
            raise HTTPException(422, "Use the independently verified schedule reservation workflow")
        if payload.state == "Approved":
            require_role(user, {"reviewer"})
        else:
            can_write(user, kind)
        tenant = user["organisation_id"]
        with store.engine.begin() as conn:
            lock_tenant(conn, tenant)
            row = row_get(conn, tenant, kind, item_id)
            if row["version"] != payload.expected_version:
                raise HTTPException(409, "Record changed; reload before deciding")
            check_transition(row, user, payload.state, payload.reason, payload.evidence_ids)
            for evidence_id in payload.evidence_ids:
                evidence = row_get(conn, tenant, "evidence", evidence_id)
                if missing_evidence(evidence):
                    raise HTTPException(422, "Referenced evidence lacks provenance, checksum or type")
            if payload.state == "Approved":
                reviewers = row["data"].get("_approvals", [])
                if user["id"] in [x["actor_id"] for x in reviewers]:
                    raise HTTPException(409, "Reviewer has already signed this revision")
                reviewers.append({"actor_id": user["id"], "at": now(), "reason": payload.reason, "input_version": row["version"], "evidence_ids": payload.evidence_ids})
                row["data"] = {**row["data"], "_approvals": reviewers}
                required_count = 2 if os.environ.get("AIRSPACE_REQUIRE_TWO_REVIEWERS", "false").lower() == "true" else 1
                row["status"] = "Approved" if len(reviewers) >= required_count else "Under Review"
            else:
                row["status"] = payload.state
                if payload.state in {"Draft", "Missing Evidence", "Under Review", "Rejected"}:
                    row["data"] = {k: v for k, v in row["data"].items() if k != "_approvals"}
            row.update(version=row["version"] + 1, updated_at=now())
            result = conn.execute(update(records).where(records.c.id == item_id, records.c.organisation_id == tenant, records.c.version == payload.expected_version).values(**row))
            if result.rowcount != 1:
                raise HTTPException(409, "Concurrent decision rejected")
            store.snapshot(conn, row)
            store.append_audit(conn, tenant, user["id"], f"{kind}.transition", {"record_id": item_id, "requested_state": payload.state, "recorded_state": row["status"], "version": row["version"], "reason": payload.reason, "evidence_ids": payload.evidence_ids, "meaning": "Recorded internal review; authority instruments require their separate issuer evidence"})
        return row

    @app.get("/api/v1/records/{kind}/{item_id}/history")
    def history(kind: str, item_id: str, user=Depends(current)):
        with store.engine.connect() as conn:
            row_get(conn, user["organisation_id"], kind, item_id)
            rows = conn.execute(select(versions.c.snapshot).where(versions.c.record_id == item_id, versions.c.organisation_id == user["organisation_id"]).order_by(versions.c.version)).scalars().all()
        return {"items": rows}

    @app.get("/api/v1/records/case/{item_id}/export")
    def export_case(item_id: str, format: str = "json", user=Depends(current)):
        with store.engine.begin() as conn:
            row = row_get(conn, user["organisation_id"], "case", item_id)
            evidence = [row_get(conn, user["organisation_id"], "evidence", ref) for ref in row["data"].get("evidence_ids", [])]
            package = {"schema_version": "1.0", "software_version": __version__, "generated_at": now(), "accountable_actor": user["id"], "case": row, "evidence": evidence, "missing_inputs": missing_evidence(row), "authority_status": "No submission or permission implied by this export", "rule_version": "workflow-1", "model_version": None}
            package["sha256"] = hashlib.sha256(canonical(package).encode()).hexdigest()
            store.append_audit(conn, user["organisation_id"], user["id"], "case.exported", {"record_id": item_id, "input_version": row["version"], "package_sha256": package["sha256"]})
        if format == "html":
            from .evidence import report_html
            return Response(report_html(package), media_type="text/html", headers={"Content-Disposition": f'attachment; filename="case-{item_id}-v{row["version"]}.html"'})
        if format != "json":
            raise HTTPException(422, "Export format must be json or html")
        return Response(json.dumps(package, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="case-{item_id}-v{row["version"]}.json"'})

    @app.get("/api/v1/audit")
    def audit_records(user=Depends(current)):
        with store.engine.connect() as conn:
            rows = conn.execute(select(audit).where(audit.c.organisation_id == user["organisation_id"]).order_by(audit.c.sequence.desc()).limit(1000)).mappings().all()
        return {"items": [dict(x) for x in rows], "verification": store.verify_audit(user["organisation_id"])}

    @app.get("/api/v1/sources")
    def source_list(user=Depends(current)):
        path = ROOT / "sources" / "catalogue.json"
        catalogue = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"sources": [], "checked_at": None}
        return {"items": catalogue.get("sources", []), "checked_at": catalogue.get("checked_at"), "coverage": "Foundation only; national packs require qualified validation"}

    @app.post("/api/v1/retrieval")
    def retrieval(payload: Query, user=Depends(current)):
        from .regulatory import source_answer
        passages = []
        paths = list((ROOT / "sources").glob("**/passages.json"))
        if (ROOT / "sources/corpus.json").exists():
            paths.append(ROOT / "sources/corpus.json")
        for path in sorted(paths):
            content = json.loads(path.read_text(encoding="utf-8"))
            passages.extend(content if isinstance(content, list) else content.get("passages", []))
        # Private source ingestion is tenant-scoped. Other tenants never enter the ranking pool.
        tenant_path = Path(os.environ.get("AIRSPACE_RUNTIME", "runtime")) / "sources" / user["organisation_id"]
        for path in tenant_path.glob("**/passages.json"):
            content = json.loads(path.read_text(encoding="utf-8"))
            for passage in content if isinstance(content, list) else content.get("passages", []):
                if passage.get("organisation_id") == user["organisation_id"]:
                    passages.append(passage)
        passages = list({p["id"]: p for p in passages}.values())
        from .neural import configure_local_retrieval
        warning = None
        try:
            model_options = configure_local_retrieval(user["organisation_id"])
        except Exception as exc:
            model_options = {}
            warning = "Configured local neural retrieval unavailable: " + type(exc).__name__
        result = source_answer(passages, payload.question, payload.jurisdiction, payload.operation_date, tenant_id=user["organisation_id"], methodology=payload.methodology, accountable_actor=user["id"], **model_options)
        if warning:
            result.setdefault("failures", []).append(warning)
        return result

    @app.get("/api/v1/connectors")
    def connectors(user=Depends(current)):
        from .operations import connector_catalog
        return {"items": connector_catalog()}

    @app.post("/api/v1/jobs", status_code=201)
    def create_job(payload: JobRequest, user=Depends(current)):
        from .worker import TOOL_ROLES
        if payload.kind not in JOB_KINDS:
            raise HTTPException(422, "Tool is not allowlisted")
        require_role(user, TOOL_ROLES.get(payload.kind, set()))
        if payload.deadline:
            try:
                deadline = datetime.fromisoformat(payload.deadline.replace("Z", "+00:00"))
                if deadline.tzinfo is None or deadline <= datetime.now(timezone.utc):
                    raise ValueError()
            except ValueError:
                raise HTTPException(422, "Deadline must be a future timezone-aware timestamp")
        row = dict(id=identifier(), organisation_id=user["organisation_id"], kind=payload.kind, actor_id=user["id"], state="Queued", payload=payload.payload, result=None, attempts=0, lease_until=None, deadline=payload.deadline, error=None, version=1, created_at=now())
        with store.engine.begin() as conn:
            conn.execute(jobs.insert().values(**row))
            store.append_audit(conn, user["organisation_id"], user["id"], "job.created", {"job_id": row["id"], "kind": row["kind"]})
        return row

    @app.get("/api/v1/jobs")
    def job_list(user=Depends(current)):
        with store.engine.connect() as conn:
            rows = conn.execute(select(jobs).where(jobs.c.organisation_id == user["organisation_id"]).order_by(jobs.c.created_at.desc()).limit(200)).mappings().all()
        return {"items": [dict(x) for x in rows]}

    @app.post("/api/v1/jobs/{job_id}/{action}")
    def job_action(job_id: str, action: str, user=Depends(current)):
        require_role(user, {"regulatory", "planner", "incident_coordinator", "analyst"})
        allowed = {"pause": ({"Queued", "Running"}, "Paused"), "resume": ({"Paused", "Failed"}, "Queued"), "cancel": ({"Queued", "Running", "Paused", "Failed"}, "Cancelled")}
        if action not in allowed:
            raise HTTPException(404, "Unknown job action")
        before, after = allowed[action]
        with store.engine.begin() as conn:
            job = conn.execute(select(jobs).where(jobs.c.id == job_id, jobs.c.organisation_id == user["organisation_id"])).mappings().first()
            if not job:
                raise HTTPException(409, "Job unavailable or state changed")
            from .worker import TOOL_ROLES
            require_role(user, TOOL_ROLES.get(job["kind"], set()))
            if action == "resume" and job["attempts"] >= 3:
                raise HTTPException(409, "Retry budget exhausted; create a reviewed new job")
            stmt = update(jobs).where(jobs.c.id == job_id, jobs.c.organisation_id == user["organisation_id"], jobs.c.state.in_(before)).values(state=after, version=jobs.c.version + 1, lease_until=None)
            if conn.execute(stmt).rowcount != 1:
                raise HTTPException(409, "Job unavailable or state changed")
            store.append_audit(conn, user["organisation_id"], user["id"], f"job.{action}", {"job_id": job_id})
        return {"id": job_id, "state": after}

    @app.get("/api/v1/events")
    def event_stream(after: int = 0, user=Depends(current)):
        async def stream():
            cursor = after
            for _ in range(30):
                with store.engine.connect() as conn:
                    rows = conn.execute(select(audit.c.sequence, audit.c.action, audit.c.at).where(audit.c.organisation_id == user["organisation_id"], audit.c.sequence > cursor).order_by(audit.c.sequence).limit(100)).mappings().all()
                if rows:
                    for row in rows:
                        cursor = row["sequence"]
                        yield f"id: {cursor}\ndata: {canonical(dict(row))}\n\n"
                else:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type="text/event-stream")

    # Deterministic engines are exposed as advisory calculations; saved results retain their input.
    @app.post("/api/v1/schedule/propose")
    def propose_schedule(payload: dict, user=Depends(current)):
        require_role(user, {"planner"})
        from .scheduler import solve_schedule, verify_schedule
        mission_ids = payload.get("mission_ids")
        if mission_ids is not None:
            if not mission_ids:
                return {"status": "Incomplete", "missing_inputs": ["missions", "aircraft availability", "personnel qualifications", "permissions", "weather", "airspace and provider status"], "assignments": []}
            raise HTTPException(422, "Use a complete versioned scheduler input snapshot; record IDs alone do not establish resource readiness")
        snapshot = {**payload, "actor_id": user["id"]}
        result = solve_schedule(snapshot)
        verification = verify_schedule(snapshot, result)
        with store.engine.begin() as conn:
            ids = {x["id"] for key in ("missions", "aircraft", "personnel", "sites") for x in snapshot.get(key, [])}
            ids |= {p["id"] for m in snapshot.get("missions", []) for p in m.get("permissions", [])}
            permission_rows = conn.execute(select(records.c.data).where(records.c.organisation_id == user["organisation_id"], records.c.id.in_(ids), records.c.kind == "permission")).scalars().all()
            ids |= {d["receipt_evidence_id"] for d in permission_rows if d.get("receipt_evidence_id")}
            bindings = {x.id: x.version for x in conn.execute(select(records.c.id, records.c.version).where(records.c.organisation_id == user["organisation_id"], records.c.id.in_(ids))).all()}
            row = dict(id=identifier(), organisation_id=user["organisation_id"], kind="schedule", title=f"Schedule proposal {now()}", status="Draft", data={"input": snapshot, "result": result, "input_record_versions": bindings, "reviewer_ids": [], "_prepared_by": user["id"]}, version=1, created_by=user["id"], created_at=now(), updated_at=now())
            conn.execute(records.insert().values(**row))
            store.snapshot(conn, row)
            store.append_audit(conn, user["organisation_id"], user["id"], "schedule.proposed", {"input_sha256": hashlib.sha256(canonical(payload).encode()).hexdigest(), "result": result, "verification": verification})
        return {**result, "schedule_record_id": row["id"], "independent_verification": verification, "dispatch_released": False}

    @app.post("/api/v1/schedule/{schedule_id}/reserve")
    def reserve_schedule(schedule_id: str, payload: Transition, user=Depends(current)):
        from .planning import approve_schedule
        if payload.state != "Approved":
            raise HTTPException(422, "Reservation requires an explicit internal approval request")
        return approve_schedule(store, schedule_id, payload.expected_version, user, payload.reason)

    @app.post("/api/v1/schedule/{schedule_id}/cancel")
    def cancel_schedule_route(schedule_id: str, payload: Transition, user=Depends(current)):
        from .planning import cancel_schedule
        if payload.state != "Cancelled":
            raise HTTPException(422, "Cancellation requires an explicit Cancelled request")
        return cancel_schedule(store, schedule_id, payload.expected_version, user, payload.reason)

    @app.get("/api/v1/contracts")
    def contracts(user=Depends(current)):
        from .operations import RiskRequest, SiteScreenRequest, TelemetryRequest, IncidentRequest, EconomicsRequest, DispatchRequest
        from .scheduler import ScheduleRequest
        return {"schema_version": "1.0", "contracts": {model.__name__: model.model_json_schema() for model in (ScheduleRequest, RiskRequest, SiteScreenRequest, TelemetryRequest, IncidentRequest, EconomicsRequest, DispatchRequest)}, "actor_id": "Server replaces actor_id with authenticated user"}

    @app.post("/api/v1/site/screen")
    def site_screen(payload: dict, user=Depends(current)):
        from .operations import screen_site
        return screen_site({**payload, "actor_id": user["id"]})

    @app.post("/api/v1/risk/assess")
    def risk_assess(payload: dict, user=Depends(current)):
        from .operations import assess_sora
        return assess_sora({**payload, "actor_id": user["id"]})

    @app.post("/api/v1/economics")
    def economics(payload: dict, user=Depends(current)):
        from .operations import calculate_economics
        return calculate_economics({**payload, "actor_id": user["id"]})

    @app.get("/api/v1/capabilities")
    def capabilities(user=Depends(current)):
        path = ROOT / "capabilities.json"
        return json.loads(path.read_text()) if path.exists() else {"release": "Engineering build", "features": []}

    from .evidence import install_evidence_routes
    install_evidence_routes(app, store, current)
    from .monitoring import install_monitoring_routes
    install_monitoring_routes(app, store, current)
    if serve_frontend and (ROOT / "frontend" / "dist").exists():
        app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True), name="interface")
    return app
