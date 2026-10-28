"""Explicit bilateral aircraft sharing and a redacted physical-resource ledger.

An aircraft agreement never transfers operating authorisations, pilot privileges
or a provider permission. Both organisations retain their tenant boundaries.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import and_, or_, select, update

from .europe import COUNTRIES
from .scheduler import Contract, Aircraft, Window, snapshot_hash, stamp, utc
from .storage import (records, organisations, users, sharing_agreements,
                      resource_locks, fleet_reservations, reservations, identifier, now)

RULE_VERSION = "bilateral-aircraft-sharing-2.0.0"


def validate_aircraft_identity(conn, tenant, newdata, current_row=None):
    """Admission guard; ordinary edits cannot change a physical-owner binding.

    A borrowed asset is a new local record linked to the named counterpart's
    accepted agreement. Ownership transfer is outside this ordinary editor.
    """
    fields = ("sharing_agreement_id", "owner_organisation_id", "owner_aircraft_id")
    previous = current_row["data"] if current_row else {}
    was_bound = any(previous.get(field) for field in fields)
    will_bind = any(newdata.get(field) for field in fields)
    if current_row and not was_bound and will_bind:
        raise HTTPException(422, "An owned aircraft record cannot become a borrowed alias through ordinary editing; create a separate explicitly shared record")
    if was_bound and any(newdata.get(field) != previous.get(field) for field in fields):
        raise HTTPException(422, "The aircraft's existing owner and sharing-agreement binding is immutable")
    if not will_bind:
        return None
    if any(not isinstance(newdata.get(field), str) or not newdata[field].strip() for field in fields):
        raise HTTPException(422, "A shared alias needs an explicit agreement, owner organisation and owner aircraft")
    agreement = conn.execute(select(sharing_agreements).where(sharing_agreements.c.id == newdata["sharing_agreement_id"], sharing_agreements.c.operator_organisation_id == tenant)).mappings().first()
    if not agreement or not agreement["accepted_actor_id"] or not was_bound and agreement["state"] != "Accepted":
        raise HTTPException(422, "Only the named accepting operator may create this borrowed aircraft alias")
    terms = SharingTerms.model_validate({key: value for key, value in agreement["terms"].items() if key not in {"asset_snapshot", "decision"}})
    if terms.owner_organisation_id != newdata["owner_organisation_id"] or terms.aircraft_id != newdata["owner_aircraft_id"]:
        raise HTTPException(422, "Borrowed aircraft identity differs from the actual accepted agreement")
    configurations = [newdata.get("configuration_id"), newdata.get("scheduler", {}).get("configuration_id") if isinstance(newdata.get("scheduler"), dict) else None]
    if not any(configurations) or any(configuration and configuration != terms.configuration_id for configuration in configurations):
        raise HTTPException(422, "Borrowed aircraft configuration must match its explicit agreement")
    if not was_bound:
        if terms.valid_until <= datetime.now(timezone.utc):
            raise HTTPException(422, "An expired agreement cannot create a new operational sharing alias")
        _owner_aircraft(conn, terms.owner_organisation_id, terms.aircraft_id, terms.aircraft_version, terms.configuration_id)
    return {"sharing_agreement_id": agreement["id"], "agreement_version": agreement["version"], "owner_organisation_id": terms.owner_organisation_id, "owner_aircraft_id": terms.aircraft_id}


class SharingTerms(Contract):
    owner_organisation_id: str = Field(min_length=1)
    operator_organisation_id: str = Field(min_length=1)
    aircraft_id: str = Field(min_length=1)
    aircraft_version: int = Field(ge=1)
    configuration_id: str = Field(min_length=1)
    agreement_reference: str = Field(min_length=1)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    countries: list[str] = Field(min_length=1)
    route_versions: list[str] = Field(min_length=1)
    permitted_purposes: list[str] = Field(min_length=1)
    maintenance_responsible_organisation_id: str = Field(min_length=1)
    operating_responsibility_ref: str = Field(min_length=1)
    maintenance_responsibility_ref: str = Field(min_length=1)
    insurance_evidence_ref: str = Field(min_length=1)
    data_sharing_rights_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        self.valid_from, self.valid_until = utc(self.valid_from), utc(self.valid_until)
        if self.owner_organisation_id == self.operator_organisation_id:
            raise ValueError("A bilateral agreement needs two different organisations")
        if self.valid_from >= self.valid_until or not set(self.countries).issubset(COUNTRIES):
            raise ValueError("Sharing terms need a positive interval and explicit registered countries")
        if self.maintenance_responsible_organisation_id not in {self.owner_organisation_id, self.operator_organisation_id}:
            raise ValueError("Maintenance responsibility must be assigned to one of the contracting organisations")
        return self


class SharingDecision(Contract):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)


def _principal(conn, user, allowed={"fleet_manager", "reviewer"}):
    row = conn.execute(select(users).where(users.c.id == user["id"], users.c.organisation_id == user["organisation_id"], users.c.disabled == 0)).mappings().first()
    if not row or row["role"] not in allowed or row["role"] != user.get("role"):
        raise HTTPException(403, "A current authorised fleet manager or reviewer is required")


def _lock_parties(conn, owner, operator):
    # Fixed ordering prevents two agreement transitions locking counterparties
    # in opposite orders. No private organisation record is returned.
    for tenant in sorted({owner, operator}):
        if conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq)).rowcount != 1:
            raise HTTPException(422, "The explicit counterpart organisation is unavailable")


def _owner_aircraft(conn, owner, aircraft_id, expected_version, configuration_id):
    row = conn.execute(select(records).where(records.c.id == aircraft_id, records.c.organisation_id == owner, records.c.kind == "aircraft")).mappings().first()
    if not row or row["status"] != "Approved" or row["version"] != expected_version:
        raise HTTPException(409, "Owner aircraft readiness is unavailable, changed or unapproved")
    try:
        snapshot = Aircraft.model_validate(row["data"].get("scheduler", {}))
    except ValueError:
        raise HTTPException(422, "Owner aircraft lacks a valid reviewed scheduling baseline")
    if snapshot.configuration_id != configuration_id or not snapshot.serviceable:
        raise HTTPException(422, "Owner aircraft configuration or serviceability does not match the offer")
    if row["data"].get("sharing_agreement_id"):
        raise HTTPException(422, "A borrowed alias cannot be offered onward as an owned aircraft")
    return dict(row), snapshot


def _shared_snapshot(snapshot: Aircraft, terms: SharingTerms) -> dict:
    availability = [{"start": stamp(max(window.start, terms.valid_from)), "end": stamp(min(window.end, terms.valid_until))} for window in snapshot.availability if max(window.start, terms.valid_from) < min(window.end, terms.valid_until)]
    # No private evidence content, personnel, customer, contacts, maintenance
    # history, financial figures or operating permissions cross this boundary.
    return {"aircraft_id": terms.aircraft_id, "configuration_id": snapshot.configuration_id, "serviceable": snapshot.serviceable,
            "payload_capacity_kg": snapshot.payload_capacity_kg, "availability": availability, "maintenance_due": stamp(utc(snapshot.maintenance_due)),
            "usable_flight_seconds": snapshot.usable_flight_seconds, "turnaround_seconds": snapshot.turnaround_seconds,
            "snapshot_digest": snapshot_hash(snapshot), "owner_record_version": terms.aircraft_version,
            "data_classification": "Explicitly shared aircraft readiness claims; operator must review its own readiness and legal basis"}


def _project(row, tenant):
    if tenant not in {row["owner_organisation_id"], row["operator_organisation_id"]} or row["state"] == "Draft" and tenant != row["owner_organisation_id"]:
        raise HTTPException(404, "Sharing agreement not found")
    terms = dict(row["terms"])
    return {"id": row["id"], "version": row["version"], "state": "Expired" if row["state"] == "Accepted" and utc(datetime.fromisoformat(terms["valid_until"].replace("Z", "+00:00"))) <= datetime.now(timezone.utc) else row["state"],
            "owner_organisation_id": row["owner_organisation_id"], "operator_organisation_id": row["operator_organisation_id"], "aircraft_id": row["aircraft_id"], "terms": terms,
            "created_at": row["created_at"], "updated_at": row["updated_at"], "offer_actor_id": row["offer_actor_id"], "accepted_actor_id": row["accepted_actor_id"],
            "boundary": "Bilateral shared terms and allowlisted asset claims only; no authority or aircraft-command delegation"}


def list_agreements(store, user) -> dict:
    tenant = user["organisation_id"]
    with store.engine.connect() as conn:
        rows = conn.execute(select(sharing_agreements).where(or_(sharing_agreements.c.owner_organisation_id == tenant, and_(sharing_agreements.c.operator_organisation_id == tenant, sharing_agreements.c.state != "Draft"))).order_by(sharing_agreements.c.updated_at.desc()).limit(500)).mappings().all()
    return {"items": [_project(dict(row), tenant) for row in rows], "scope": "Explicit owner/operator agreements only"}


def create_agreement(store, user, payload: SharingTerms | dict):
    terms = payload if isinstance(payload, SharingTerms) else SharingTerms.model_validate(payload)
    if terms.owner_organisation_id != user["organisation_id"]:
        raise HTTPException(403, "Only the owning organisation can prepare an aircraft-sharing offer")
    with store.engine.begin() as conn:
        _principal(conn, user)
        _lock_parties(conn, terms.owner_organisation_id, terms.operator_organisation_id)
        _lock_resource(conn, terms.owner_organisation_id, terms.aircraft_id)
        _, aircraft = _owner_aircraft(conn, terms.owner_organisation_id, terms.aircraft_id, terms.aircraft_version, terms.configuration_id)
        row = {"id": identifier(), "owner_organisation_id": terms.owner_organisation_id, "operator_organisation_id": terms.operator_organisation_id,
               "aircraft_id": terms.aircraft_id, "version": 1, "state": "Draft", "terms": {**terms.model_dump(mode="json"), "asset_snapshot": _shared_snapshot(aircraft, terms)},
               "offer_actor_id": user["id"], "accepted_actor_id": None, "created_at": now(), "updated_at": now()}
        conn.execute(sharing_agreements.insert().values(**row))
        store.append_audit(conn, user["organisation_id"], user["id"], "sharing.prepared", {"agreement_id": row["id"], "version": 1, "input_snapshot": snapshot_hash(terms)})
    return _project(row, user["organisation_id"])


def decide_agreement(store, agreement_id, user, action, expected_version, reason):
    if action not in {"offer", "accept", "reject", "revoke"}:
        raise HTTPException(404, "Unknown agreement transition")
    if not isinstance(reason, str) or not reason.strip():
        raise HTTPException(422, "A recorded agreement decision rationale is required")
    with store.engine.begin() as conn:
        _principal(conn, user)
        found = conn.execute(select(sharing_agreements).where(sharing_agreements.c.id == agreement_id, or_(sharing_agreements.c.owner_organisation_id == user["organisation_id"], sharing_agreements.c.operator_organisation_id == user["organisation_id"]))).mappings().first()
        if not found:
            raise HTTPException(404, "Sharing agreement not found")
        # Do not disclose a counterparty's private draft through transition errors.
        _project(dict(found), user["organisation_id"])
        _lock_parties(conn, found["owner_organisation_id"], found["operator_organisation_id"])
        _lock_resource(conn, found["owner_organisation_id"], found["aircraft_id"])
        row = dict(conn.execute(select(sharing_agreements).where(sharing_agreements.c.id == agreement_id)).mappings().one())
        if row["version"] != expected_version:
            raise HTTPException(409, "Agreement changed; review the current terms")
        owner, operator = row["owner_organisation_id"], row["operator_organisation_id"]
        terms = SharingTerms.model_validate({key: value for key, value in row["terms"].items() if key != "asset_snapshot" and key != "decision"})
        if action == "offer":
            if user["organisation_id"] != owner or row["state"] != "Draft":
                raise HTTPException(403, "Only the owner can offer its current draft")
            _owner_aircraft(conn, owner, row["aircraft_id"], terms.aircraft_version, terms.configuration_id)
            if terms.valid_until <= datetime.now(timezone.utc):
                raise HTTPException(422, "Expired sharing terms cannot be offered")
            row["state"] = "Offered"
        elif action == "accept":
            if user["organisation_id"] != operator or row["state"] != "Offered" or user["id"] == row["offer_actor_id"]:
                raise HTTPException(403, "The named counterpart must explicitly accept the offered terms")
            _owner_aircraft(conn, owner, row["aircraft_id"], terms.aircraft_version, terms.configuration_id)
            if terms.valid_until <= datetime.now(timezone.utc):
                raise HTTPException(422, "Expired sharing terms cannot be accepted")
            row.update(state="Accepted", accepted_actor_id=user["id"])
        elif action == "reject":
            if user["organisation_id"] != operator or row["state"] != "Offered":
                raise HTTPException(403, "Only the named counterpart can reject offered terms")
            row["state"] = "Rejected"
        else:
            if row["state"] not in {"Draft", "Offered", "Accepted"}:
                raise HTTPException(409, "Agreement is already terminal")
            row["state"] = "Revoked"
            # Preserve the reservation's physical exclusion until its operator
            # explicitly cancels/reconciles the schedule; revocation is no flight command.
            conn.execute(update(fleet_reservations).where(fleet_reservations.c.agreement_id == agreement_id, fleet_reservations.c.state == "Reserved").values(state="Suspended"))
            affected = conn.execute(select(fleet_reservations.c.operator_organisation_id, fleet_reservations.c.schedule_id, fleet_reservations.c.mission_id).where(fleet_reservations.c.agreement_id == agreement_id, fleet_reservations.c.state == "Suspended")).all()
            from .dispatch import _suspend_rows
            for operator_id, schedule_id, mission_id in sorted(set(affected)):
                releases = conn.execute(select(records).where(records.c.organisation_id == operator_id, records.c.kind == "dispatch_release", records.c.data["schedule_id"].as_string() == schedule_id, records.c.data["mission_id"].as_string() == mission_id, records.c.status.in_(["Under Review", "Internally Released"]))).mappings().all()
                _suspend_rows(conn, store, releases, user, "Aircraft sharing agreement revoked", agreement_id)
        row.update(version=row["version"] + 1, updated_at=now(), terms={**row["terms"], "decision": {"actor_id": user["id"], "at": now(), "reason": reason, "action": action}})
        changed = conn.execute(update(sharing_agreements).where(sharing_agreements.c.id == agreement_id, sharing_agreements.c.version == expected_version).values(**row))
        if changed.rowcount != 1:
            raise HTTPException(409, "Concurrent agreement transition rejected")
        for tenant in sorted({owner, operator}):
            store.append_audit(conn, tenant, user["id"], f"sharing.{action}", {"agreement_id": agreement_id, "version": row["version"], "state": row["state"], "actor_organisation_id": user["organisation_id"]})
    return _project(row, user["organisation_id"])


def check_shared_aircraft(conn, tenant, local_aircraft, mission, start, end):
    """Resolve only a local reviewed alias's explicit accepted agreement."""
    local_row = conn.execute(select(records).where(records.c.id == local_aircraft.id, records.c.organisation_id == tenant, records.c.kind == "aircraft")).mappings().first()
    if not local_row:
        raise HTTPException(422, "Local aircraft record is unavailable")
    agreement_id = local_row["data"].get("sharing_agreement_id")
    if not agreement_id:
        return {"owner_organisation_id": tenant, "aircraft_id": local_aircraft.id, "agreement_id": None, "operator_organisation_id": tenant, "owner_record_version": local_row["version"], "usable_flight_seconds": local_aircraft.usable_flight_seconds}
    row = conn.execute(select(sharing_agreements).where(sharing_agreements.c.id == agreement_id, sharing_agreements.c.operator_organisation_id == tenant)).mappings().first()
    if not row or row["state"] != "Accepted" or not row["accepted_actor_id"]:
        raise HTTPException(422, "Shared aircraft agreement is missing, unaccepted, revoked or suspended")
    terms = SharingTerms.model_validate({key: value for key, value in row["terms"].items() if key not in {"asset_snapshot", "decision"}})
    if not terms.valid_from <= start < end <= terms.valid_until or local_aircraft.configuration_id != terms.configuration_id or mission.route_version not in terms.route_versions:
        raise HTTPException(422, "Shared aircraft assignment is outside agreement dates, configuration or route scope")
    if local_row["data"].get("owner_aircraft_id") != terms.aircraft_id or local_row["data"].get("owner_organisation_id") != terms.owner_organisation_id:
        raise HTTPException(422, "Borrowed alias does not match the explicit owner and aircraft")
    mission_row = conn.execute(select(records).where(records.c.id == mission.id, records.c.organisation_id == tenant, records.c.kind == "mission")).mappings().first()
    countries = {segment.get("country") for segment in (mission_row["data"].get("coordination", {}).get("segments", []) if mission_row else [])}
    purpose = mission_row["data"].get("purpose") if mission_row else None
    if not countries or not countries.issubset(set(terms.countries)) or purpose not in terms.permitted_purposes:
        raise HTTPException(422, "Shared aircraft needs explicit country segments and a permitted mission purpose")
    _, original = _owner_aircraft(conn, terms.owner_organisation_id, terms.aircraft_id, terms.aircraft_version, terms.configuration_id)
    if not any(window.start <= start and end <= window.end for window in original.availability) or utc(original.maintenance_due) < end:
        raise HTTPException(422, "Owner's current aircraft availability or maintenance validity blocks this assignment")
    if local_aircraft.payload_capacity_kg > original.payload_capacity_kg or local_aircraft.usable_flight_seconds > original.usable_flight_seconds or local_aircraft.turnaround_seconds < original.turnaround_seconds:
        raise HTTPException(422, "Borrower's readiness claim exceeds the owner's explicitly shared limits")
    maintenance = conn.execute(select(records).where(records.c.organisation_id == terms.owner_organisation_id, records.c.kind == "maintenance_work_order", records.c.data["work_order"]["aircraft_id"].as_string() == terms.aircraft_id, records.c.status.in_(["Scheduled", "In Progress", "Work Complete", "Under Review"]))).mappings().all()
    for work in maintenance:
        interval = Window.model_validate(work["data"]["work_order"]["window"])
        if work["status"] != "Scheduled" or interval.start < end and interval.end > start:
            raise HTTPException(422, "The physical aircraft is unavailable under its owner's maintenance workflow")
    from .fleet import validate_fleet_for_schedule
    from types import SimpleNamespace
    # This internally validates only the explicitly contracted owner's asset.
    # Neither its program nor unrelated operating records are returned.
    owner_forecast = {"assignments": [{"aircraft_id": original.id, "mission_id": mission.id, "start": stamp(start), "end": stamp(end)}]}
    try:
        validate_fleet_for_schedule(conn, terms.owner_organisation_id, SimpleNamespace(actor_id=f"sharing-check:{row['id']}", aircraft=[original]), owner_forecast)
    except (HTTPException, ValueError):
        raise HTTPException(422, "The physical aircraft is unavailable under its owner's maintenance readiness evidence")
    return {"owner_organisation_id": terms.owner_organisation_id, "aircraft_id": terms.aircraft_id, "agreement_id": row["id"], "agreement_version": row["version"], "operator_organisation_id": tenant, "owner_record_version": terms.aircraft_version, "usable_flight_seconds": original.usable_flight_seconds}


def _lock_resource(conn, owner, aircraft_id):
    key = f"aircraft:{owner}:{aircraft_id}"
    if conn.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    elif conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        raise HTTPException(503, "Physical-resource locking is not implemented for this database")
    conn.execute(insert(resource_locks).values(resource_key=key, generation=0).on_conflict_do_nothing(index_elements=["resource_key"]))
    conn.execute(update(resource_locks).where(resource_locks.c.resource_key == key).values(generation=resource_locks.c.generation + 1))


def lock_owned_aircraft_set_mutation(conn, tenant, aircraft_ids):
    """Lock a complete owner's dependency set in one global party/resource order."""
    assets = sorted(set(aircraft_ids))
    def counterparties():
        contracted = conn.execute(select(sharing_agreements.c.operator_organisation_id).where(sharing_agreements.c.owner_organisation_id == tenant, sharing_agreements.c.aircraft_id.in_(assets), sharing_agreements.c.state == "Accepted")).scalars().all()
        allocated = conn.execute(select(fleet_reservations.c.operator_organisation_id).where(fleet_reservations.c.owner_organisation_id == tenant, fleet_reservations.c.aircraft_id.in_(assets), fleet_reservations.c.state.in_(["Reserved", "Suspended"]))).scalars().all()
        return {tenant, *contracted, *allocated}
    parties = counterparties()
    for party in sorted(parties):
        if conn.execute(update(organisations).where(organisations.c.id == party).values(audit_seq=organisations.c.audit_seq)).rowcount != 1:
            raise HTTPException(409, "Explicit aircraft counterpart is unavailable")
    # An agreement/booking may have committed between the initial read and the
    # owner lock. Abort instead of taking a newly discovered lock out of order.
    if not counterparties().issubset(parties):
        raise HTTPException(409, "Aircraft sharing counterpart changed while acquiring locks; reload and retry")
    for aircraft_id in assets:
        _lock_resource(conn, tenant, aircraft_id)
    return sorted(parties)


def lock_aircraft_mutation(conn, tenant, aircraft_id):
    """Owner mutation prelock over explicitly linked counterparties only."""
    return lock_owned_aircraft_set_mutation(conn, tenant, [aircraft_id])


def lock_schedule_parties(conn, tenant, schedule_id):
    """Cancellation prelock works after revocation, expiry or unserviceability."""
    def scope():
        rows = conn.execute(select(fleet_reservations.c.owner_organisation_id, fleet_reservations.c.aircraft_id).where(fleet_reservations.c.operator_organisation_id == tenant, fleet_reservations.c.schedule_id == schedule_id)).all()
        legacy = conn.execute(select(reservations.c.resource_id).where(reservations.c.organisation_id == tenant, reservations.c.schedule_id == schedule_id, reservations.c.resource_kind == "aircraft")).scalars().all()
        return set(rows) | {(tenant, resource_id) for resource_id in legacy if not rows}
    assets = scope()
    parties = {tenant, *(owner for owner, _ in assets)}
    for party in sorted(parties):
        conn.execute(update(organisations).where(organisations.c.id == party).values(audit_seq=organisations.c.audit_seq))
    if not scope().issubset(assets):
        raise HTTPException(409, "Schedule resource scope changed while acquiring cancellation locks; reload and retry")
    for owner, asset in sorted(assets):
        _lock_resource(conn, owner, asset)
    return sorted(parties)


def lock_physical_aircraft(conn, tenant, request, result):
    """Mutation-only prelock: call before taking a caller-only tenant lock.

    Resolve through authorised local aliases, lock all counterpart organisations
    in one order, then physical resources in one order. Re-read after locks.
    Read-only assessments must continue using check_shared_aircraft directly.
    """
    aircraft, missions = {item.id: item for item in request.aircraft}, {item.id: item for item in request.missions}
    identities = []
    for assignment in result.get("assignments", []):
        start, end = (utc(datetime.fromisoformat(assignment[key].replace("Z", "+00:00"))) for key in ("start", "end"))
        identities.append(check_shared_aircraft(conn, tenant, aircraft[assignment["aircraft_id"]], missions[assignment["mission_id"]], start, end))
    for organisation in sorted({tenant, *(item["owner_organisation_id"] for item in identities)}):
        if conn.execute(update(organisations).where(organisations.c.id == organisation).values(audit_seq=organisations.c.audit_seq)).rowcount != 1:
            raise HTTPException(409, "Aircraft counterpart is unavailable")
    for owner, asset in sorted({(item["owner_organisation_id"], item["aircraft_id"]) for item in identities}):
        _lock_resource(conn, owner, asset)
    verified = []
    for assignment, previous in zip(result.get("assignments", []), identities):
        start, end = (utc(datetime.fromisoformat(assignment[key].replace("Z", "+00:00"))) for key in ("start", "end"))
        current = check_shared_aircraft(conn, tenant, aircraft[assignment["aircraft_id"]], missions[assignment["mission_id"]], start, end)
        if current != previous:
            raise HTTPException(409, "Physical aircraft or agreement changed while acquiring reservation locks")
        verified.append(current)
    return verified


def reserve_physical_aircraft(conn, tenant, request, result, schedule_id):
    aircraft = {item.id: item for item in request.aircraft}
    missions = {item.id: item for item in request.missions}
    resolved = []
    for assignment in result.get("assignments", []):
        start = utc(datetime.fromisoformat(assignment["start"].replace("Z", "+00:00")))
        end = utc(datetime.fromisoformat(assignment["end"].replace("Z", "+00:00")))
        craft = aircraft[assignment["aircraft_id"]]
        identity = check_shared_aircraft(conn, tenant, craft, missions[assignment["mission_id"]], start, end)
        resolved.append((assignment, identity, start, end, craft.turnaround_seconds))
    for owner, asset in sorted({(identity["owner_organisation_id"], identity["aircraft_id"]) for _, identity, *_ in resolved}):
        _lock_resource(conn, owner, asset)
    from datetime import timedelta
    for assignment, identity, start, end, turnaround in resolved:
        current_identity = check_shared_aircraft(conn, tenant, aircraft[assignment["aircraft_id"]], missions[assignment["mission_id"]], start, end)
        if current_identity != identity:
            raise HTTPException(409, "Aircraft or agreement changed while acquiring its physical reservation lock")
        identity = current_identity
        first, last = start.isoformat(), (end + timedelta(seconds=turnaround)).isoformat()
        conflict = conn.execute(select(fleet_reservations.c.id).where(fleet_reservations.c.owner_organisation_id == identity["owner_organisation_id"], fleet_reservations.c.aircraft_id == identity["aircraft_id"], fleet_reservations.c.state.in_(["Reserved", "Suspended"]), fleet_reservations.c.start < last, fleet_reservations.c.end > first)).first()
        if conflict:
            raise HTTPException(409, "The physical aircraft is unavailable in the requested interval")
        prior = conn.execute(select(fleet_reservations).where(fleet_reservations.c.owner_organisation_id == identity["owner_organisation_id"], fleet_reservations.c.aircraft_id == identity["aircraft_id"], fleet_reservations.c.state.in_(["Reserved", "Suspended"]))).mappings().all()
        if any(item["owner_record_version"] is None or item["flight_seconds"] is None for item in prior):
            raise HTTPException(409, "Unversioned physical reservations require reconciliation before further booking")
        seconds = int((end - start).total_seconds())
        consumed = sum(item["flight_seconds"] for item in prior if item["owner_record_version"] == identity["owner_record_version"])
        # Preserve existing 0.1 reservations during the additive migration. They
        # must not vanish merely because the new physical ledger did not exist.
        legacy = conn.execute(select(reservations).where(reservations.c.organisation_id == identity["owner_organisation_id"], reservations.c.resource_kind == "aircraft", reservations.c.resource_id == identity["aircraft_id"], reservations.c.state == "Reserved", reservations.c.schedule_id != schedule_id)).mappings().all()
        for item in legacy:
            if any(previous["schedule_id"] == item["schedule_id"] and previous["mission_id"] == item["mission_id"] for previous in prior):
                continue
            if item["start"] < last and item["end"] > first:
                raise HTTPException(409, "The physical aircraft is unavailable in the requested interval")
            historical = conn.execute(select(records).where(records.c.id == item["schedule_id"], records.c.organisation_id == identity["owner_organisation_id"], records.c.kind == "schedule")).mappings().first()
            if not historical:
                raise HTTPException(409, "Existing aircraft reservation provenance requires reconciliation")
            if historical["data"].get("input_record_versions", {}).get(identity["aircraft_id"]) == identity["owner_record_version"]:
                original_assignment = next((entry for entry in historical["data"].get("result", {}).get("assignments", []) if entry["mission_id"] == item["mission_id"]), None)
                if not original_assignment:
                    raise HTTPException(409, "Existing aircraft flight-time budget requires reconciliation")
                consumed += int((datetime.fromisoformat(original_assignment["end"].replace("Z", "+00:00")) - datetime.fromisoformat(original_assignment["start"].replace("Z", "+00:00"))).total_seconds())
        if consumed + seconds > identity["usable_flight_seconds"]:
            raise HTTPException(409, "The physical aircraft's reviewed flight-time budget is already allocated")
        conn.execute(fleet_reservations.insert().values(id=identifier(), owner_organisation_id=identity["owner_organisation_id"], operator_organisation_id=tenant, aircraft_id=identity["aircraft_id"], agreement_id=identity["agreement_id"], schedule_id=schedule_id, mission_id=assignment["mission_id"], owner_record_version=identity["owner_record_version"], flight_seconds=seconds, start=first, end=last, state="Reserved"))
    return [{"mission_id": assignment["mission_id"], **identity} for assignment, identity, *_ in resolved]


def release_physical_reservations(conn, tenant, schedule_id):
    return conn.execute(update(fleet_reservations).where(fleet_reservations.c.operator_organisation_id == tenant, fleet_reservations.c.schedule_id == schedule_id, fleet_reservations.c.state.in_(["Reserved", "Suspended"])).values(state="Released")).rowcount
