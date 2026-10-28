"""Transactional schedule reservation; proposals never become flight commands."""
from datetime import datetime, timedelta, timezone
import os
import re
from fastapi import HTTPException
from sqlalchemy import select, update
from .storage import records, reservations, organisations, users, identifier, now, canonical
from .scheduler import ScheduleRequest, verify_schedule


def validate_persisted_snapshot(conn, tenant, request, bindings):
    for collection, kind in [(request.missions, "mission"), (request.aircraft, "aircraft"), (request.personnel, "personnel"), (request.sites, "site")]:
        for resource in collection:
            row = conn.execute(select(records).where(records.c.id == resource.id, records.c.kind == kind, records.c.organisation_id == tenant)).mappings().first()
            if not row or row["data"].get("scheduler") != resource.model_dump(mode="json"):
                raise HTTPException(422, f"Current {kind} record does not match reviewed scheduler snapshot: {resource.id}")
            if row["version"] != bindings.get(resource.id):
                raise HTTPException(409, f"Stale {kind} revision: {resource.id}")
            if kind != "mission" and row["status"] != "Approved":
                raise HTTPException(422, f"{kind} readiness/capacity record requires internal approval")
    for mission in request.missions:
        for permission in mission.permissions:
            row = conn.execute(select(records).where(records.c.id == permission.id, records.c.kind == "permission", records.c.organisation_id == tenant)).mappings().first()
            if not row or row["status"] != "Approved" or row["data"].get("scheduler") != permission.model_dump(mode="json") or row["version"] != bindings.get(permission.id):
                raise HTTPException(422, "Permission snapshot does not match a current independently reviewed instrument")
            if not row["data"].get("receipt_evidence_id"):
                raise HTTPException(422, "Authority/provider instrument lacks issuer evidence")
            types = {"operational_authorisation": "operating_basis", "declaration": "operating_basis", "luc_privilege": "operating_basis", "site_permission": "site_airspace", "uspace_authorisation": "u_space"}
            if types.get(row["data"].get("permission_type")) != permission.kind:
                raise HTTPException(422, "Reviewed instrument type differs from scheduler permission kind")
            try:
                recorded_start = datetime.fromisoformat(row["data"]["valid_from"].replace("Z", "+00:00"))
                recorded_end = datetime.fromisoformat(row["data"]["valid_to"].replace("Z", "+00:00"))
            except (KeyError, AttributeError, TypeError, ValueError):
                raise HTTPException(422, "Reviewed instrument validity is missing or invalid")
            if recorded_start != permission.valid_from or recorded_end != permission.valid_until:
                raise HTTPException(422, "Reviewed issuer instrument validity differs from scheduler snapshot")
            scope = row["data"].get("scope")
            if not isinstance(scope, dict) or scope.get("configuration_id") != permission.configuration_id or scope.get("route_version") != permission.route_version:
                raise HTTPException(422, "Reviewed permission scope must identify the same configuration and route version")
            receipt_id = row["data"]["receipt_evidence_id"]
            receipt = conn.execute(select(records).where(records.c.id == receipt_id, records.c.kind == "evidence", records.c.organisation_id == tenant)).mappings().first()
            if not receipt or receipt["version"] != bindings.get(receipt_id):
                raise HTTPException(409, "Issuer receipt evidence is missing or changed; regenerate the proposal")
            evidence = receipt["data"]
            if receipt["status"] != "Approved" or not evidence.get("provenance") or not evidence.get("evidence_type") or not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("checksum", ""))):
                raise HTTPException(422, "Issuer receipt requires reviewed provenance, type and SHA-256 integrity reference")


def _same_snapshot_reservations(conn, tenant, kind, resource_id, readiness_version):
    """Prior reservations consume the same battery/duty snapshot budget.

    The current request cannot reset a budget merely by being a different
    schedule. A different verified resource revision is a distinct snapshot.
    """
    rows = conn.execute(select(reservations).where(reservations.c.organisation_id == tenant, reservations.c.resource_kind == kind, reservations.c.resource_id == resource_id, reservations.c.state == "Reserved")).mappings().all()
    result = []
    for reservation in rows:
        schedule = conn.execute(select(records).where(records.c.id == reservation["schedule_id"], records.c.organisation_id == tenant, records.c.kind == "schedule")).mappings().first()
        if schedule is None:
            raise HTTPException(409, "Reservation provenance is unavailable; administrative reconciliation required")
        if schedule["data"].get("input_record_versions", {}).get(resource_id) != readiness_version:
            continue
        assignments = [a for a in schedule["data"].get("result", {}).get("assignments", []) if a.get("mission_id") == reservation["mission_id"]]
        if len(assignments) != 1:
            raise HTTPException(409, "Reservation assignment provenance is inconsistent")
        assignment = assignments[0]
        result.append((datetime.fromisoformat(assignment["start"].replace("Z", "+00:00")), datetime.fromisoformat(assignment["end"].replace("Z", "+00:00"))))
    return result


def _validate_shared_budgets(conn, tenant, request, result, bindings):
    for aircraft in request.aircraft:
        previous = _same_snapshot_reservations(conn, tenant, "aircraft", aircraft.id, bindings[aircraft.id])
        proposed = [a for a in result["assignments"] if a["aircraft_id"] == aircraft.id]
        total = sum((end - start).total_seconds() for start, end in previous) + sum((datetime.fromisoformat(a["end"].replace("Z", "+00:00")) - datetime.fromisoformat(a["start"].replace("Z", "+00:00"))).total_seconds() for a in proposed)
        if total > aircraft.usable_flight_seconds:
            raise HTTPException(409, "Aircraft battery/readiness budget already reserved across schedules")
    for person in request.personnel:
        intervals = _same_snapshot_reservations(conn, tenant, "personnel", person.id, bindings[person.id])
        intervals += [(datetime.fromisoformat(a["start"].replace("Z", "+00:00")), datetime.fromisoformat(a["end"].replace("Z", "+00:00"))) for a in result["assignments"] if a["person_id"] == person.id]
        if intervals:
            active = sum((end - start).total_seconds() for start, end in intervals) + person.duty_already_seconds
            elapsed = (max(end for _, end in intervals) - min(start for start, _ in intervals)).total_seconds() + person.duty_already_seconds
            if max(active, elapsed) > person.max_duty_seconds:
                raise HTTPException(409, "Personnel duty episode budget already reserved across schedules")


def approve_schedule(store, schedule_id, expected_version, user, reason):
    if user["role"] != "reviewer":
        raise HTTPException(403, "Accountable assigned reviewer required")
    tenant = user["organisation_id"]
    with store.engine.begin() as conn:
        initial = conn.execute(select(records).where(records.c.id == schedule_id, records.c.organisation_id == tenant, records.c.kind == "schedule")).mappings().first()
        if initial is None:
            raise HTTPException(404, "Schedule not found")
        if initial["version"] != expected_version or initial["status"] not in {"Draft", "Under Review"}:
            raise HTTPException(409, "Schedule changed or already reserved")
        if user["id"] in {initial["created_by"], initial["data"].get("_prepared_by")} or user["id"] not in initial["data"].get("reviewer_ids", []):
            raise HTTPException(403, "Assigned independent reviewer required")
        from .sharing import lock_physical_aircraft
        lock_physical_aircraft(conn, tenant, ScheduleRequest.model_validate(initial["data"]["input"]), initial["data"]["result"])
        conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq))
        found = conn.execute(select(records).where(records.c.id == schedule_id, records.c.organisation_id == tenant, records.c.kind == "schedule")).mappings().first()
        if not found:
            raise HTTPException(404, "Schedule not found")
        row = dict(found)
        if expected_version != row["version"] or row["status"] not in {"Draft", "Under Review"}:
            raise HTTPException(409, "Schedule changed or already reserved")
        if user["id"] in {row["created_by"], row["data"].get("_prepared_by")} or user["id"] not in row["data"].get("reviewer_ids", []):
            raise HTTPException(403, "Assigned independent reviewer required")
        if not reason.strip():
            raise HTTPException(422, "Decision rationale is required")
        snapshot, result = row["data"]["input"], row["data"]["result"]
        request = ScheduleRequest.model_validate(snapshot)
        verification = verify_schedule(request, result)
        if not verification["valid"] or result["status"] not in {"FEASIBLE", "OPTIMAL"}:
            raise HTTPException(422, {"message": "Independent schedule verification failed", "findings": verification["findings"]})
        validate_persisted_snapshot(conn, tenant, request, row["data"].get("input_record_versions", {}))
        if conn.execute(select(reservations.c.id).where(reservations.c.organisation_id == tenant, reservations.c.mission_id.in_([mission.id for mission in request.missions]), reservations.c.state == "Reserved")).first():
            raise HTTPException(409, "Proposed operation already has a reservation; cancel or supersede its existing schedule before reserving a replacement")
        approvals = list(row["data"].get("_approvals", []))
        if any(approval["actor_id"] == user["id"] for approval in approvals):
            raise HTTPException(409, "Reviewer has already signed this schedule revision")
        if any(approval.get("input_snapshot") != result["input_snapshot"] for approval in approvals):
            raise HTTPException(409, "Signed schedule inputs changed; obtain a new review")
        approvals.append({"actor_id": user["id"], "at": now(), "reason": reason, "input_snapshot": result["input_snapshot"]})
        required_count = 2 if os.environ.get("AIRSPACE_REQUIRE_TWO_REVIEWERS", "false").lower() == "true" else 1
        if len(approvals) < required_count:
            row.update(status="Under Review", version=row["version"] + 1, updated_at=now(), data={**row["data"], "_approvals": approvals})
            conn.execute(update(records).where(records.c.id == schedule_id, records.c.organisation_id == tenant, records.c.version == expected_version).values(**row))
            store.snapshot(conn, row)
            store.append_audit(conn, tenant, user["id"], "schedule.reviewed", {"record_id": schedule_id, "version": row["version"], "input_snapshot": result["input_snapshot"], "required_reviewers": required_count})
            return row
        _validate_shared_budgets(conn, tenant, request, result, row["data"].get("input_record_versions", {}))
        from .fleet import validate_fleet_for_schedule
        from .sharing import reserve_physical_aircraft
        validate_fleet_for_schedule(conn, tenant, request, result)
        physical_reservations = reserve_physical_aircraft(conn, tenant, request, result, schedule_id)
        crafts = {a.id: a for a in request.aircraft}
        sites = {s.id: s for s in request.sites}
        for assignment in result["assignments"]:
            start = datetime.fromisoformat(assignment["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(assignment["end"].replace("Z", "+00:00"))
            if start <= datetime.now(timezone.utc):
                raise HTTPException(422, "Schedule is in the past; replan")
            for kind, field in [("aircraft", "aircraft_id"), ("personnel", "person_id"), ("site", "site_id")]:
                resource_id = assignment[field]
                until = end + timedelta(seconds=crafts[resource_id].turnaround_seconds) if kind == "aircraft" else end
                first, last = start.isoformat(), until.isoformat()
                conflicts = conn.execute(select(reservations).where(reservations.c.organisation_id == tenant, reservations.c.resource_kind == kind, reservations.c.resource_id == resource_id, reservations.c.state == "Reserved", reservations.c.start < last, reservations.c.end > first)).mappings().all()
                if conflicts and kind != "site":
                    raise HTTPException(409, "Resource already reserved by another schedule")
                if kind == "site":
                    events = [(first, 1), (last, -1)] + [(r["start"], 1) for r in conflicts] + [(r["end"], -1) for r in conflicts]
                    active = 0
                    for _, delta in sorted(events, key=lambda x: (x[0], x[1])):
                        active += delta
                        if active > sites[resource_id].concurrent_capacity:
                            raise HTTPException(409, "Site capacity already reserved by another schedule")
                conn.execute(reservations.insert().values(id=identifier(), organisation_id=tenant, schedule_id=schedule_id, mission_id=assignment["mission_id"], resource_kind=kind, resource_id=resource_id, start=first, end=last, state="Reserved"))
        row.update(status="Approved", version=row["version"] + 1, updated_at=now(), data={**row["data"], "_approvals": approvals, "_decision": {"actor_id": user["id"], "at": now(), "reason": reason, "meaning": "Internal resource reservation only; no dispatch or actual execution"}})
        conn.execute(update(records).where(records.c.id == schedule_id, records.c.version == expected_version).values(**row))
        store.snapshot(conn, row)
        store.append_audit(conn, tenant, user["id"], "schedule.reserved", {"record_id": schedule_id, "version": row["version"], "input_snapshot": result["input_snapshot"], "verification": verification, "reason": reason})
    return row


def cancel_schedule(store, schedule_id, expected_version, user, reason):
    """Release an internal proposal/reservation; never cancel a provider flight.

    A cancelled record is terminal. Rebooking requires a new proposal with
    current evidence and a new independent reservation decision.
    """
    if user.get("role") not in {"planner", "reviewer"}:
        raise HTTPException(403, "A planner or assigned independent reviewer is required")
    if not isinstance(reason, str) or not reason.strip():
        raise HTTPException(422, "Cancellation rationale is required")
    tenant = user["organisation_id"]
    with store.engine.begin() as conn:
        from .sharing import lock_schedule_parties
        lock_schedule_parties(conn, tenant, schedule_id)
        conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq))
        principal = conn.execute(select(users).where(users.c.id == user["id"], users.c.organisation_id == tenant, users.c.disabled == 0)).mappings().first()
        if not principal or principal["role"] != user["role"]:
            raise HTTPException(403, "Current accountable principal is unavailable or lacks the cancellation role")
        found = conn.execute(select(records).where(records.c.id == schedule_id, records.c.organisation_id == tenant, records.c.kind == "schedule")).mappings().first()
        if not found:
            raise HTTPException(404, "Schedule not found")
        row = dict(found)
        if expected_version != row["version"] or row["status"] not in {"Draft", "Under Review", "Approved", "Suspended"}:
            raise HTTPException(409, "Schedule changed or is already cancelled; create a new proposal")
        if user["role"] == "reviewer" and (user["id"] not in row["data"].get("reviewer_ids", []) or user["id"] in {row["created_by"], row["data"].get("_prepared_by")}):
            raise HTTPException(403, "Reviewer must be assigned and independent of schedule preparation")
        released = conn.execute(update(reservations).where(reservations.c.organisation_id == tenant, reservations.c.schedule_id == schedule_id, reservations.c.state == "Reserved").values(state="Released")).rowcount
        from .sharing import release_physical_reservations
        physical_released = release_physical_reservations(conn, tenant, schedule_id)
        decision = {"actor_id": user["id"], "at": now(), "reason": reason.strip(), "released_reservations": released, "released_physical_aircraft": physical_released,
                    "meaning": "Internal reservation cancellation only; no aircraft command, provider withdrawal or external notification"}
        row.update(status="Cancelled", version=row["version"] + 1, updated_at=now(), data={**row["data"], "_cancellation": decision})
        changed = conn.execute(update(records).where(records.c.id == schedule_id, records.c.organisation_id == tenant, records.c.version == expected_version).values(**row))
        if changed.rowcount != 1:
            raise HTTPException(409, "Concurrent schedule cancellation rejected")
        store.snapshot(conn, row)
        store.append_audit(conn, tenant, user["id"], "schedule.cancelled", {"record_id": schedule_id, "version": row["version"], **decision})
        from .dispatch import suspend_dispatch_for_schedule
        suspend_dispatch_for_schedule(conn, store, tenant, schedule_id, user, "Internal resource reservation was cancelled")
    return row
