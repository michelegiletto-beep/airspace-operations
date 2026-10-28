"""Authenticated coordination, fleet and agent-workflow application services."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update

from .identity import require_role
from .storage import records, jobs, organisations, identifier, now


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    action: Literal["pause", "resume", "cancel"]


class Advance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


def queue_agent_step(store, workflow, actor, conn=None):
    """Idempotent bounded continuation; model execution belongs to a worker."""
    def insert(connection):
        connection.execute(update(organisations).where(organisations.c.id == actor["organisation_id"]).values(audit_seq=organisations.c.audit_seq))
        active = connection.execute(select(jobs).where(jobs.c.organisation_id == actor["organisation_id"], jobs.c.kind == "agent_orchestration", jobs.c.state.in_(["Queued", "Running"]))).mappings().all()
        existing = next((dict(job) for job in active if job["payload"].get("workflow_id") == workflow["id"]), None)
        if existing:
            return existing
        row = dict(id=identifier(), organisation_id=actor["organisation_id"], actor_id=workflow["created_by"], kind="agent_orchestration", state="Queued",
                   payload={"workflow_id": workflow["id"], "workflow_version": workflow["version"]}, result=None, attempts=0, lease_until=None,
                   deadline=workflow["data"]["scope"]["deadline"], error=None, version=1, created_at=now())
        connection.execute(jobs.insert().values(**row))
        store.append_audit(connection, actor["organisation_id"], actor["id"], "agent.step.queued", {"workflow_id": workflow["id"], "job_id": row["id"], "workflow_version": workflow["version"]})
        return row
    if conn is not None:
        return insert(conn)
    with store.engine.begin() as connection:
        return insert(connection)


def install_coordination_routes(app, store, current):
    from .orchestration import WorkflowRequest, WorkflowRepository, capability_catalog
    from .fleet import (MaintenanceAssessment, MaintenancePlanRequest, SavedMaintenanceAssessment,
                        WorkOrderControl, assess_maintenance, plan_maintenance, verify_maintenance_plan,
                        maintenance_workspace, assess_saved_maintenance, transition_work_order)
    from .europe import CrossBorderPlan, country_catalogue, assess_cross_border
    from .sharing import SharingTerms, SharingDecision, create_agreement, list_agreements, decide_agreement
    from .dispatch import DispatchDecision, acknowledge_pilot, release_dispatch

    repository = WorkflowRepository(store)

    @app.get("/api/v1/agent-capabilities")
    @app.get("/api/v1/workflow-tools")
    def agent_capabilities(user=Depends(current)):
        return capability_catalog()

    @app.get("/api/v1/agent-workflows")
    def workflow_list(user=Depends(current)):
        return {"items": repository.list(user["organisation_id"])}

    @app.post("/api/v1/agent-workflows", status_code=201)
    def workflow_create(payload: WorkflowRequest, user=Depends(current)):
        return repository.create(payload, user)

    @app.get("/api/v1/agent-workflows/{workflow_id}")
    def workflow_get(workflow_id: str, user=Depends(current)):
        return repository.get(workflow_id, user["organisation_id"])

    @app.post("/api/v1/agent-workflows/{workflow_id}/control")
    def workflow_control(workflow_id: str, payload: Control, user=Depends(current)):
        workflow = repository.control(workflow_id, user, payload.action, payload.expected_version)
        with store.engine.begin() as conn:
            conn.execute(update(organisations).where(organisations.c.id == user["organisation_id"]).values(audit_seq=organisations.c.audit_seq))
            current_workflow = repository._row(conn, workflow_id, user["organisation_id"])
            # A later control or worker decision owns its new jobs. A delayed
            # pause cleanup must never cancel a concurrently resumed revision.
            if current_workflow["version"] != workflow["version"] or current_workflow["status"] != workflow["status"]:
                return current_workflow
            conn.execute(update(jobs).where(jobs.c.organisation_id == user["organisation_id"], jobs.c.kind == "agent_orchestration", jobs.c.payload["workflow_id"].as_string() == workflow_id, jobs.c.state.in_(["Queued", "Running"])).values(state="Cancelled", lease_until=None, version=jobs.c.version+1))
            if payload.action == "resume":
                if current_workflow["status"] == "Queued" and current_workflow["version"] == workflow["version"]:
                    queue_agent_step(store, current_workflow, user, conn=conn)
        return workflow

    @app.post("/api/v1/agent-workflows/{workflow_id}/advance", status_code=202)
    def workflow_advance(workflow_id: str, payload: Advance, user=Depends(current)):
        workflow = repository.get(workflow_id, user["organisation_id"])
        if workflow["version"] != payload.expected_version:
            raise HTTPException(409, "Workflow changed; reload before starting")
        if workflow["created_by"] != user["id"]:
            raise HTTPException(403, "The accountable workflow preparer must start its configured tools")
        if workflow["status"] != "Queued":
            raise HTTPException(409, "Only a queued, current workflow may start; review or reconcile its state")
        return queue_agent_step(store, workflow, user)

    @app.get("/api/v1/coordination/countries")
    def countries(user=Depends(current)):
        return {"items": country_catalogue(), "scope": "European geographical catalogue; registered does not mean validated legal coverage"}

    @app.post("/api/v1/coordination/assess")
    def coordinate(payload: CrossBorderPlan, user=Depends(current)):
        require_role(user, {"regulatory", "planner", "reviewer"})
        payload = payload.model_copy(update={"actor_id": user["id"], "operator_organisation_id": user["organisation_id"]})
        return assess_cross_border(payload)

    @app.get("/api/v1/fleet/aircraft/{aircraft_id}/maintenance")
    def aircraft_maintenance(aircraft_id: str, user=Depends(current)):
        return maintenance_workspace(store, user, aircraft_id)

    @app.post("/api/v1/fleet/aircraft/{aircraft_id}/maintenance/assess")
    def aircraft_maintenance_assess(aircraft_id: str, payload: SavedMaintenanceAssessment, user=Depends(current)):
        require_role(user, {"fleet_manager", "planner", "reviewer"})
        return assess_saved_maintenance(store, user, aircraft_id, payload)

    @app.post("/api/v1/fleet/maintenance/assess")
    def maintenance_assess(payload: MaintenanceAssessment, user=Depends(current)):
        require_role(user, {"fleet_manager", "planner", "reviewer"})
        return assess_maintenance(payload.model_copy(update={"actor_id": user["id"]}))

    @app.post("/api/v1/fleet/maintenance/plan")
    def maintenance_plan(payload: MaintenancePlanRequest, user=Depends(current)):
        require_role(user, {"fleet_manager", "planner"})
        payload = payload.model_copy(update={"actor_id": user["id"]})
        result = plan_maintenance(payload)
        return {**result, "independent_verification": verify_maintenance_plan(payload, result)}

    @app.post("/api/v1/fleet/work-orders/{work_order_id}/control")
    def work_order_control(work_order_id: str, payload: WorkOrderControl, user=Depends(current)):
        return transition_work_order(store, work_order_id, user, payload)

    @app.get("/api/v1/sharing/agreements")
    def agreements(user=Depends(current)):
        return list_agreements(store, user)

    @app.post("/api/v1/sharing/agreements", status_code=201)
    def agreement_create(payload: SharingTerms, user=Depends(current)):
        return create_agreement(store, user, payload)

    @app.post("/api/v1/sharing/agreements/{agreement_id}/{action}")
    def agreement_decide(agreement_id: str, action: Literal["offer", "accept", "reject", "revoke"], payload: SharingDecision, user=Depends(current)):
        return decide_agreement(store, agreement_id, user, action, payload.expected_version, payload.reason)

    @app.post("/api/v1/schedule/{schedule_id}/pilot-acknowledgement")
    def pilot_ack(schedule_id: str, payload: DispatchDecision, user=Depends(current)):
        return acknowledge_pilot(store, schedule_id, user, payload)

    @app.post("/api/v1/schedule/{schedule_id}/dispatch-release")
    def dispatch_release(schedule_id: str, payload: DispatchDecision, user=Depends(current)):
        return release_dispatch(store, schedule_id, user, payload)
