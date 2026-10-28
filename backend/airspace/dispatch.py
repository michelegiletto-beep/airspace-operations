"""Accountable internal dispatch review; never an aircraft or provider command."""
from datetime import datetime, timedelta, timezone
import os

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import select, update

from .scheduler import Contract, ScheduleRequest, snapshot_hash, verify_schedule
from .storage import records, users, organisations, reservations, fleet_reservations, identifier, now


class DispatchDecision(Contract):
    mission_id: str = Field(min_length=1)
    expected_schedule_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)


class DispatchPolicy(Contract):
    maximum_lead_seconds: int = Field(ge=0)
    validity_seconds: int = Field(gt=0)
    source_ref: str = Field(min_length=1)


def _suspend_rows(conn, store, rows, user, reason, source_record_id, target="Suspended"):
    changed = 0
    for item in rows:
        row = dict(item)
        if row["status"] not in {"Under Review", "Internally Released"}:
            continue
        row.update(status=target, version=row["version"] + 1, updated_at=now(), data={**row["data"], "_suspension": {"actor_id": user["id"], "actor_organisation_id": user["organisation_id"], "at": now(), "reason": reason, "source_record_id": source_record_id, "meaning": "Internal release eligibility invalidated; no provider or aircraft command"}})
        result = conn.execute(update(records).where(records.c.id == row["id"], records.c.organisation_id == row["organisation_id"], records.c.version == row["version"] - 1).values(**row))
        if result.rowcount:
            store.snapshot(conn, row)
            store.append_audit(conn, row["organisation_id"], user["id"], "dispatch.invalidated", {"record_id": row["id"], "version": row["version"], "state": target, "source_record_id": source_record_id, "reason": reason, "actor_organisation_id": user["organisation_id"]})
            changed += 1
    return changed


def suspend_dispatch_dependencies(conn, store, tenant, record_id, user, reason):
    """Same-tenant controlled-input change. Caller holds its mutation locks."""
    rows = conn.execute(select(records).where(records.c.organisation_id == tenant, records.c.kind == "dispatch_release", records.c.status.in_(["Under Review", "Internally Released"]))).mappings().all()
    dependent = [row for row in rows if record_id in row["data"].get("record_versions", {}) or row["data"].get("schedule_id") == record_id or row["data"].get("mission_id") == record_id]
    return _suspend_rows(conn, store, dependent, user, reason, record_id)


def suspend_dispatch_for_schedule(conn, store, tenant, schedule_id, user, reason):
    rows = conn.execute(select(records).where(records.c.organisation_id == tenant, records.c.kind == "dispatch_release", records.c.data["schedule_id"].as_string() == schedule_id, records.c.status.in_(["Under Review", "Internally Released"]))).mappings().all()
    return _suspend_rows(conn, store, rows, user, reason, schedule_id, target="Cancelled")


def suspend_dispatch_for_aircraft(conn, store, owner, aircraft_id, user, reason):
    """Cross-operator propagation follows only the explicit physical ledger."""
    scopes = conn.execute(select(fleet_reservations.c.operator_organisation_id, fleet_reservations.c.schedule_id, fleet_reservations.c.mission_id).where(fleet_reservations.c.owner_organisation_id == owner, fleet_reservations.c.aircraft_id == aircraft_id, fleet_reservations.c.state.in_(["Reserved", "Suspended"]))).all()
    count = 0
    for operator, schedule_id, mission_id in sorted(set(scopes)):
        rows = conn.execute(select(records).where(records.c.organisation_id == operator, records.c.kind == "dispatch_release", records.c.data["schedule_id"].as_string() == schedule_id, records.c.data["mission_id"].as_string() == mission_id, records.c.status.in_(["Under Review", "Internally Released"]))).mappings().all()
        count += _suspend_rows(conn, store, rows, user, reason, aircraft_id)
    return count


def _record(conn, tenant, kind, item_id):
    row = conn.execute(select(records).where(records.c.id == item_id, records.c.kind == kind, records.c.organisation_id == tenant)).mappings().first()
    if not row:
        raise HTTPException(404, "Required dispatch record not found")
    return dict(row)


def _context(conn, tenant, schedule_id, mission_id, expected_version):
    schedule = _record(conn, tenant, "schedule", schedule_id)
    if schedule["version"] != expected_version or schedule["status"] != "Approved":
        raise HTTPException(409, "Schedule is changed, unreserved or cancelled")
    request = ScheduleRequest.model_validate(schedule["data"]["input"])
    result = schedule["data"]["result"]
    verified = verify_schedule(request, result)
    if not verified["valid"]:
        raise HTTPException(422, {"message": "Schedule verification no longer passes", "findings": verified["findings"]})
    assignment = next((item for item in result["assignments"] if item["mission_id"] == mission_id), None)
    mission = next((item for item in request.missions if item.id == mission_id), None)
    if assignment is None or mission is None:
        raise HTTPException(422, "Mission is not assigned in this schedule")
    craft = next(item for item in request.aircraft if item.id == assignment["aircraft_id"])
    start, end = (datetime.fromisoformat(assignment[key].replace("Z", "+00:00")) for key in ("start", "end"))
    current_reservations = conn.execute(select(reservations).where(reservations.c.organisation_id == tenant, reservations.c.schedule_id == schedule_id, reservations.c.mission_id == mission_id, reservations.c.state == "Reserved")).mappings().all()
    for kind, field in (("aircraft", "aircraft_id"), ("personnel", "person_id"), ("site", "site_id")):
        matching = [item for item in current_reservations if item["resource_kind"] == kind and item["resource_id"] == assignment[field]]
        expected_end = end + timedelta(seconds=craft.turnaround_seconds) if kind == "aircraft" else end
        if len(matching) != 1 or datetime.fromisoformat(matching[0]["start"]) != start or datetime.fromisoformat(matching[0]["end"]) != expected_end:
            raise HTTPException(409, "Mission resources are not completely reserved for the exact reviewed assignment")
    return schedule, request, result, mission, assignment


def _current_principal(conn, user, role):
    row = conn.execute(select(users).where(users.c.id == user["id"], users.c.organisation_id == user["organisation_id"], users.c.disabled == 0)).mappings().first()
    if user.get("role") != role or not row or row["role"] != role:
        raise HTTPException(403, f"A current authorised {role} is required")


def acknowledge_pilot(store, schedule_id, user, payload: DispatchDecision | dict):
    payload = payload if isinstance(payload, DispatchDecision) else DispatchDecision.model_validate(payload)
    if not payload.reason.strip():
        raise HTTPException(422, "A nonblank acknowledgement rationale is required")
    tenant = user["organisation_id"]
    with store.engine.begin() as conn:
        conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq))
        _current_principal(conn, user, "pilot")
        schedule, request, result, mission, assignment = _context(conn, tenant, schedule_id, payload.mission_id, payload.expected_schedule_version)
        personnel = _record(conn, tenant, "personnel", assignment["person_id"])
        if personnel["data"].get("user_id") != user["id"] or personnel["status"] != "Approved":
            raise HTTPException(403, "Acknowledgement must come from the actual assigned pilot account")
        if datetime.fromisoformat(assignment["start"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
            raise HTTPException(422, "Past assignments cannot receive a new preflight acknowledgement")
        digest = snapshot_hash({"schedule_id": schedule_id, "schedule_version": schedule["version"], "assignment": assignment, "input_snapshot": result["input_snapshot"]})
        row = {"id": identifier(), "organisation_id": tenant, "kind": "pilot_acknowledgement", "title": "Pilot acknowledgement", "status": "Recorded", "version": 1, "created_by": user["id"], "created_at": now(), "updated_at": now(),
               "data": {"schedule_id": schedule_id, "schedule_version": schedule["version"], "mission_id": mission.id, "personnel_id": personnel["id"], "personnel_version": personnel["version"], "pilot_user_id": user["id"], "assignment_digest": digest, "reason": payload.reason, "meaning": "Pilot acknowledgement only; no dispatch permission or flight execution"}}
        conn.execute(records.insert().values(**row))
        store.snapshot(conn, row)
        store.append_audit(conn, tenant, user["id"], "dispatch.pilot_acknowledged", {"record_id": row["id"], "schedule_id": schedule_id, "mission_id": mission.id, "assignment_digest": digest})
    return row


def release_dispatch(store, schedule_id, user, payload: DispatchDecision | dict):
    payload = payload if isinstance(payload, DispatchDecision) else DispatchDecision.model_validate(payload)
    if not payload.reason.strip():
        raise HTTPException(422, "A nonblank dispatch-review rationale is required")
    tenant = user["organisation_id"]
    with store.engine.begin() as conn:
        _current_principal(conn, user, "reviewer")
        # Pre-read only the caller's own schedule to derive authorised sharing
        # identities; acquire ordered party/resource locks before tenant locks.
        preliminary = _record(conn, tenant, "schedule", schedule_id)
        from .sharing import lock_physical_aircraft
        lock_physical_aircraft(conn, tenant, ScheduleRequest.model_validate(preliminary["data"]["input"]), preliminary["data"]["result"])
        conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq))
        _current_principal(conn, user, "reviewer")
        schedule, request, result, mission, assignment = _context(conn, tenant, schedule_id, payload.mission_id, payload.expected_schedule_version)
        mission_row = _record(conn, tenant, "mission", mission.id)
        if user["id"] in {schedule["created_by"], schedule["data"].get("_prepared_by"), mission_row["created_by"], mission_row["data"].get("_prepared_by")} or user["id"] not in schedule["data"].get("reviewer_ids", []):
            raise HTTPException(403, "Assigned independent dispatch reviewer required")
        # Current persisted snapshots are re-read within the same mutation lock.
        from .planning import validate_persisted_snapshot
        validate_persisted_snapshot(conn, tenant, request, schedule["data"].get("input_record_versions", {}))
        from .fleet import validate_fleet_for_schedule
        from .europe import validate_persisted_coordination
        from .sharing import check_shared_aircraft
        fleet_assessments = validate_fleet_for_schedule(conn, tenant, request, result, schedule_id=schedule_id)
        country_assessment = validate_persisted_coordination(conn, tenant, mission_row, assignment, user["id"])
        craft = next(item for item in request.aircraft if item.id == assignment["aircraft_id"])
        start, end = (datetime.fromisoformat(assignment[key].replace("Z", "+00:00")) for key in ("start", "end"))
        shared_identity = check_shared_aircraft(conn, tenant, craft, mission, start, end)
        physical = conn.execute(select(fleet_reservations).where(
            fleet_reservations.c.operator_organisation_id == tenant,
            fleet_reservations.c.owner_organisation_id == shared_identity["owner_organisation_id"],
            fleet_reservations.c.aircraft_id == shared_identity["aircraft_id"],
            fleet_reservations.c.schedule_id == schedule_id,
            fleet_reservations.c.mission_id == mission.id,
            fleet_reservations.c.state == "Reserved")).mappings().first()
        if not physical or physical["agreement_id"] != shared_identity["agreement_id"] or physical["owner_record_version"] != shared_identity["owner_record_version"] or datetime.fromisoformat(physical["start"]) != start or datetime.fromisoformat(physical["end"]) != end + timedelta(seconds=craft.turnaround_seconds):
            raise HTTPException(409, "The exact current physical-aircraft reservation requires reconciliation before dispatch")
        current = datetime.now(timezone.utc)
        if current >= start:
            raise HTTPException(422, "Scheduled start passed; replan rather than release a stale assignment")
        for feed in (mission.weather, mission.airspace, mission.provider if mission.u_space_required else None):
            if feed and feed.observed_at > current:
                raise HTTPException(422, "A future-dated source observation cannot support current dispatch")
        procedure_id = mission_row["data"].get("dispatch_procedure_id")
        if not procedure_id:
            raise HTTPException(422, "Approved operator dispatch timing policy is missing")
        procedure = _record(conn, tenant, "procedure", procedure_id)
        if procedure["status"] != "Approved" or not procedure["data"].get("_approvals"):
            raise HTTPException(422, "Dispatch policy needs current independent approval")
        policy = DispatchPolicy.model_validate(procedure["data"].get("dispatch_policy", {}))
        if (start - current).total_seconds() > policy.maximum_lead_seconds:
            raise HTTPException(422, "Outside the approved dispatch-review lead window")
        safety_id = mission_row["data"].get("safety_review_id")
        if not safety_id:
            raise HTTPException(422, "Separate internal safety-case review is missing")
        safety = _record(conn, tenant, "risk_assessment", safety_id)
        if safety["status"] != "Approved" or not safety["data"].get("_approvals") or safety["data"].get("configuration_id") != mission.configuration_id or safety["data"].get("route_version") != mission.route_version:
            raise HTTPException(422, "Current safety-case review does not cover this aircraft and route")
        person = _record(conn, tenant, "personnel", assignment["person_id"])
        pilot_id = person["data"].get("user_id")
        pilot = conn.execute(select(users).where(users.c.id == pilot_id, users.c.organisation_id == tenant, users.c.role == "pilot", users.c.disabled == 0)).mappings().first()
        if not pilot or pilot_id == user["id"]:
            raise HTTPException(422, "Assigned pilot account is unavailable or not independent of dispatch review")
        digest = snapshot_hash({"schedule_id": schedule_id, "schedule_version": schedule["version"], "assignment": assignment, "input_snapshot": result["input_snapshot"]})
        acknowledgements = conn.execute(select(records).where(records.c.kind == "pilot_acknowledgement", records.c.organisation_id == tenant, records.c.data["schedule_id"].as_string() == schedule_id, records.c.data["mission_id"].as_string() == mission.id, records.c.status == "Recorded").order_by(records.c.created_at.desc())).mappings().all()
        ack = next((item for item in acknowledgements if item["created_by"] == pilot_id and item["data"].get("assignment_digest") == digest and item["data"].get("personnel_version") == person["version"]), None)
        if ack is None:
            raise HTTPException(422, "The assigned pilot has not acknowledged this exact current assignment")
        bindings = {**schedule["data"].get("input_record_versions", {}), procedure["id"]: procedure["version"], safety["id"]: safety["version"], ack["id"]: ack["version"]}
        aircraft_row = _record(conn, tenant, "aircraft", craft.id)
        usage = aircraft_row["data"].get("utilisation", {})
        if datetime.fromisoformat(usage.get("measured_at", "").replace("Z", "+00:00")) > current or any(datetime.fromisoformat(item["completed_at"].replace("Z", "+00:00")) > current for item in aircraft_row["data"].get("maintenance_completions", [])):
            raise HTTPException(422, "Future-dated measured utilisation or completed maintenance cannot support current dispatch")
        for reference in [aircraft_row["data"].get("maintenance_program_id"), *(review["id"] for review in mission_row["data"]["coordination"].get("country_reviews", [])), *(instrument["id"] for instrument in mission_row["data"]["coordination"].get("instruments", []))]:
            if reference:
                item = conn.execute(select(records).where(records.c.id == reference, records.c.organisation_id == tenant)).mappings().first()
                if item:
                    bindings[reference] = item["version"]
        decision_snapshot = snapshot_hash({"schedule_id": schedule_id, "schedule_version": schedule["version"], "mission_id": mission.id, "assignment": assignment, "bindings": bindings, "sharing": shared_identity})
        existing = conn.execute(select(records).where(records.c.kind == "dispatch_release", records.c.organisation_id == tenant, records.c.data["schedule_id"].as_string() == schedule_id, records.c.data["mission_id"].as_string() == mission.id).order_by(records.c.created_at.desc())).mappings().all()
        row = next((dict(item) for item in existing if item["data"].get("input_snapshot") == decision_snapshot and item["status"] in {"Under Review", "Internally Released"}), None)
        if row and row["status"] == "Internally Released":
            if datetime.fromisoformat(row["data"]["valid_until"]) > current:
                return row
            raise HTTPException(409, "Prior internal dispatch release expired; create a new reviewed proposal")
        if row is None:
            row = {"id": identifier(), "organisation_id": tenant, "kind": "dispatch_release", "title": "Internal dispatch review", "status": "Under Review", "version": 0, "created_by": schedule["created_by"], "created_at": now(), "updated_at": now(),
                   "data": {"schedule_id": schedule_id, "mission_id": mission.id, "input_snapshot": decision_snapshot, "record_versions": bindings, "valid_until": min(current + timedelta(seconds=policy.validity_seconds), end).isoformat(), "_approvals": [], "flight_execution": "Not Recorded", "provider_activation": "Not Performed", "aircraft_commands": False}}
        if datetime.fromisoformat(row["data"]["valid_until"]) <= current:
            raise HTTPException(409, "Dispatch-review checkpoint expired; create a new reviewed proposal")
        approvals = list(row["data"]["_approvals"])
        if user["id"] in {approval["actor_id"] for approval in approvals}:
            raise HTTPException(409, "Reviewer already signed this dispatch checkpoint")
        approvals.append({"actor_id": user["id"], "at": now(), "reason": payload.reason, "input_snapshot": decision_snapshot})
        required = 2 if os.getenv("AIRSPACE_REQUIRE_TWO_REVIEWERS", "false").lower() == "true" else 1
        row.update(version=row["version"] + 1, updated_at=now(), status="Internally Released" if len(approvals) >= required else "Under Review", data={**row["data"], "_approvals": approvals,
                   "decisions": {"legal_instruments": "Separately verified", "safety_case_review": safety["id"], "country_coordination": country_assessment["status"], "maintenance": [item["status"] for item in fleet_assessments], "pilot_acknowledgement": ack["id"], "internal_dispatch": "Released" if len(approvals) >= required else "Awaiting Independent Review"}})
        if row["version"] == 1:
            conn.execute(records.insert().values(**row))
        else:
            conn.execute(update(records).where(records.c.id == row["id"], records.c.organisation_id == tenant).values(**row))
        store.snapshot(conn, row)
        store.append_audit(conn, tenant, user["id"], "dispatch.reviewed", {"record_id": row["id"], "mission_id": mission.id, "status": row["status"], "input_snapshot": decision_snapshot, "meaning": "Internal dispatch only; no provider or aircraft command and no actual-flight claim"})
    return row
