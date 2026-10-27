"""Read-only operator telemetry imports, alert acknowledgement and incident records."""
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from .identity import require_role
from .operations import TelemetryEvent, MonitoringPolicy, evaluate_telemetry, incident_checklist
from .storage import records, organisations, identifier, now


class TelemetryImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[TelemetryEvent] = Field(max_length=1000)
    mode: str
    permitted_use_attestation: bool
    source_rights_reference: str = Field(min_length=1)
    monitoring_procedure_id: str | None = None
    expected_aircraft_ids: list[str] = Field(default_factory=list, max_length=1000)


class Acknowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=4000)


def install_monitoring_routes(app, store, current):
    from .api import row_get

    @app.post("/api/v1/telemetry/import")
    def import_events(payload: TelemetryImport, user=Depends(current)):
        require_role(user, {"pilot", "fleet_manager"})
        if payload.mode not in {"Live", "Historical Replay"} or not payload.permitted_use_attestation:
            raise HTTPException(422, "Explicit source rights attestation and separate live/replay mode are required")
        tenant = user["organisation_id"]
        with store.engine.begin() as conn:
            conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq))
            for event in payload.events:
                row_get(conn, tenant, "aircraft", event.aircraft_id)
                mission = row_get(conn, tenant, "mission", event.mission_id)
                assigned_aircraft = mission["data"].get("aircraft_id")
                if assigned_aircraft and assigned_aircraft != event.aircraft_id:
                    raise HTTPException(422, "Telemetry aircraft does not match the mission's recorded aircraft binding")
            for aircraft_id in payload.expected_aircraft_ids:
                row_get(conn, tenant, "aircraft", aircraft_id)
            previous = [r["data"]["event"] for r in conn.execute(select(records).where(records.c.organisation_id == tenant, records.c.kind == "telemetry")).mappings().all() if r["data"].get("event", {}).get("mode") == payload.mode]
            policy = None
            if payload.monitoring_procedure_id:
                procedure = row_get(conn, tenant, "procedure", payload.monitoring_procedure_id)
                if procedure["status"] != "Approved" or not procedure["data"].get("_approvals"):
                    raise HTTPException(422, "Monitoring thresholds require a current independently approved procedure")
                config = procedure["data"].get("monitoring_policy", {})
                policy = MonitoringPolicy.model_validate({**config, "source_ref": procedure["id"], "approved_by": procedure["data"]["_approvals"][-1]["actor_id"]})
            evaluation = evaluate_telemetry({"actor_id": user["id"], "now": now(), "mode": payload.mode, "events": [e.model_dump(mode="json") for e in payload.events], "previous_events": previous[-10000:], "policy": policy, "expected_aircraft_ids": payload.expected_aircraft_ids})
            for event in evaluation["accepted_records"]:
                row = dict(id=identifier(), organisation_id=tenant, kind="telemetry", title=f"{event['source_id']} · {event['event_id']}", status="Recorded", data={"event": event, "imported_at": now(), "source_rights_reference": payload.source_rights_reference, "source_receipt_type": "Authorised operator manual import", "operational_use_accepted": bool(policy and policy.operational_use_accepted)}, version=1, created_by=user["id"], created_at=now(), updated_at=now())
                conn.execute(records.insert().values(**row))
                store.snapshot(conn, row)
            existing_alerts = [dict(r) for r in conn.execute(select(records).where(records.c.organisation_id == tenant, records.c.kind == "alert")).mappings().all()]
            for alert in evaluation["alerts"]:
                correlation = ":".join([payload.mode, alert["type"], alert.get("aircraft_id", ""), alert.get("evidence_event_id", "")])
                if any(a["data"].get("correlation") == correlation for a in existing_alerts):
                    continue
                row = dict(id=identifier(), organisation_id=tenant, kind="alert", title=alert["type"], status="Unacknowledged", data={**alert, "mode": payload.mode, "correlation": correlation, "notification": {"sent": False, "delivered": False, "acknowledged": False, "action_completed": False}, "owner_id": None}, version=1, created_by=user["id"], created_at=now(), updated_at=now())
                conn.execute(records.insert().values(**row))
                store.snapshot(conn, row)
            store.append_audit(conn, tenant, user["id"], "telemetry.imported", {"mode": payload.mode, "accepted_count": len(evaluation["accepted_records"]), "observations": evaluation["observations"], "rule_version": evaluation["rule_version"], "input_snapshot": evaluation["input_snapshot"]})
        return evaluation

    @app.post("/api/v1/alerts/{item_id}/acknowledge")
    def acknowledge(item_id: str, payload: Acknowledge, user=Depends(current)):
        require_role(user, {"pilot", "incident_coordinator", "fleet_manager"})
        with store.engine.begin() as conn:
            row = row_get(conn, user["organisation_id"], "alert", item_id)
            if row["version"] != payload.expected_version or row["status"] != "Unacknowledged":
                raise HTTPException(409, "Alert changed or already acknowledged")
            row.update(status="Acknowledged", version=row["version"] + 1, updated_at=now(), data={**row["data"], "owner_id": user["id"], "acknowledged_at": now(), "acknowledgement_reason": payload.reason, "notification": {**row["data"].get("notification", {}), "acknowledged": True}})
            changed = conn.execute(update(records).where(records.c.id == item_id, records.c.organisation_id == user["organisation_id"], records.c.version == payload.expected_version).values(**row))
            if changed.rowcount != 1:
                raise HTTPException(409, "Concurrent alert acknowledgement rejected")
            store.snapshot(conn, row)
            store.append_audit(conn, user["organisation_id"], user["id"], "alert.acknowledged", {"record_id": item_id, "reason": payload.reason})
        return row

    @app.get("/api/v1/incidents/{item_id}/workspace")
    def workspace(item_id: str, user=Depends(current)):
        with store.engine.connect() as conn:
            incident = row_get(conn, user["organisation_id"], "incident", item_id)
            data = incident["data"]
            procedure = None
            if data.get("procedure_id"):
                stored = row_get(conn, user["organisation_id"], "procedure", data["procedure_id"])
                if stored["status"] == "Approved":
                    procedure = stored["data"].get("incident_procedure")
                    if procedure:
                        procedure = {**procedure, "id": stored["id"], "version": str(stored["version"]), "status": "Approved", "approved_by": stored["data"].get("_approvals", [{}])[-1].get("actor_id")}
            request = {"actor_id": user["id"], "incident_type": data.get("incident_type", "Unclassified"), "aircraft_configuration_id": data.get("aircraft_configuration_id", "Unknown"), "assigned_owner_id": data.get("commander"), "created_at": incident["created_at"], "now": now(), "acknowledged_at": data.get("acknowledged_at"), "escalation_after_seconds": None, "escalation_policy_ref": None, "procedure": procedure}
            # Escalation timing is sourced only from the approved procedure revision.
            if procedure:
                request.update(escalation_after_seconds=stored["data"].get("escalation_after_seconds"), escalation_policy_ref=stored["id"])
            result = incident_checklist(request)
            timeline = [dict(x) for x in conn.execute(select(records).where(records.c.organisation_id == user["organisation_id"], records.c.kind.in_(["telemetry", "alert", "corrective_action"]))).mappings().all() if item_id in x["data"].get("incident_ids", [])]
        return {"incident": incident, "assessment": result, "timeline": timeline, "cache_generated_at": now(), "cache_age_at_generation_seconds": 0, "degraded_export_notice": "Export retains this snapshot only; calculate age from cache_generated_at when disconnected", "external_notification_status": "Not Sent"}
