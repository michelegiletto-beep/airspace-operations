"""Bounded durable internal workflows. No external correspondence or aircraft tools."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, select, update
from .storage import jobs, records, users, organisations, now, identifier
from .workflows import missing_evidence

TOOL_ROLES = {"regulatory_monitor": {"regulatory"}, "evidence_collection": {"regulatory"}, "case_preparation": {"regulatory"}, "site_screening": {"planner", "regulatory"}, "scheduling_proposal": {"planner"}, "incident_summary": {"incident_coordinator"}, "commercial_analysis": {"analyst"}}
TOOL_ROLES["agent_orchestration"] = {"regulatory", "reviewer", "planner", "analyst", "fleet_manager"}
from .identity import ROLES
TOOL_ROLES["companion_reply"] = ROLES


def _mark_agent_job_failure(store, job, reason, *, expected_job_version):
    if job["kind"] == "companion_reply":
        from .assistant import mark_companion_job_failure
        mark_companion_job_failure(store, job, reason, expected_job_version=expected_job_version)
        return
    if job["kind"] != "agent_orchestration":
        return
    from copy import deepcopy
    from .orchestration import WorkflowRepository, OrchestrationError
    repository = WorkflowRepository(store)
    try:
        with store.engine.begin() as conn:
            row = repository._row(conn, job["payload"]["workflow_id"], job["organisation_id"])
            if row["status"] not in {"Queued", "Running"}:
                return
            data = deepcopy(row["data"])
            data["execution"].update(state="Reconciliation Required", inflight=None, last_error=reason)
            repository._save(conn, row, data, "Reconciliation Required", job["actor_id"], "agent.job_reconciliation")
    except OrchestrationError:
        # A concurrent user control wins; never overwrite its newer decision.
        return


def run_once(store):
    stamp = now()
    with store.engine.connect() as conn:
        exhausted = conn.execute(select(jobs).where(jobs.c.state == "Running", jobs.c.lease_until < stamp, jobs.c.attempts >= 3).order_by(jobs.c.organisation_id, jobs.c.id).limit(100)).mappings().all()
    for job in exhausted:
        with store.engine.begin() as conn:
            conn.execute(update(organisations).where(organisations.c.id == job["organisation_id"]).values(audit_seq=organisations.c.audit_seq))
            changed = conn.execute(update(jobs).where(jobs.c.id == job["id"], jobs.c.version == job["version"], jobs.c.state == "Running").values(state="Failed", error="Retry budget exhausted after worker interruption", lease_until=None, version=jobs.c.version + 1))
            if changed.rowcount:
                store.append_audit(conn, job["organisation_id"], job["actor_id"], "job.exhausted", {"job_id": job["id"], "attempts": job["attempts"]})
        if changed.rowcount:
            _mark_agent_job_failure(store, job, "Retry budget exhausted after worker interruption", expected_job_version=job["version"] + 1)
    expired = False
    with store.engine.begin() as conn:
        candidate = conn.execute(select(jobs).where(or_(jobs.c.state == "Queued", and_(jobs.c.state == "Running", jobs.c.lease_until < stamp)), jobs.c.attempts < 3).order_by(jobs.c.created_at).limit(1)).mappings().first()
        if not candidate:
            return None
        candidate = dict(candidate)
        conn.execute(update(organisations).where(organisations.c.id == candidate["organisation_id"]).values(audit_seq=organisations.c.audit_seq))
        if candidate["deadline"] and datetime.fromisoformat(candidate["deadline"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
            conn.execute(update(jobs).where(jobs.c.id == candidate["id"], jobs.c.version == candidate["version"]).values(state="Expired", error="Deadline exceeded", version=jobs.c.version+1))
            store.append_audit(conn, candidate["organisation_id"], candidate["actor_id"], "job.expired", {"job_id": candidate["id"]})
            expired = True
        version = candidate["version"]
        lease = (datetime.now(timezone.utc) + timedelta(seconds=900 if candidate["kind"] in {"agent_orchestration", "companion_reply"} else 120)).isoformat()
        if not expired:
            result = conn.execute(update(jobs).where(jobs.c.id == candidate["id"], jobs.c.version == version, jobs.c.state == candidate["state"]).values(state="Running", lease_until=lease, attempts=candidate["attempts"] + 1, version=version + 1))
            if result.rowcount != 1:
                return None
    if expired:
        _mark_agent_job_failure(store, candidate, "Execution deadline expired", expected_job_version=candidate["version"] + 1)
        return {"id": candidate["id"], "state": "Expired"}
    try:
        with store.engine.connect() as conn:
            actor = conn.execute(select(users).where(users.c.id == candidate["actor_id"], users.c.organisation_id == candidate["organisation_id"], users.c.disabled == 0)).mappings().first()
            if not actor:
                raise ValueError("Accountable actor is unavailable")
            if actor["role"] not in TOOL_ROLES.get(candidate["kind"], set()):
                raise ValueError("Accountable actor lacks this tool permission")
            # Context remains tenant-filtered even when a model is unavailable.
            rows = [dict(x) for x in conn.execute(select(records).where(records.c.organisation_id == candidate["organisation_id"], ~records.c.kind.startswith("companion_", autoescape=True))).mappings().all()]
        kind = candidate["kind"]
        if kind == "companion_reply":
            from .assistant import run_companion_reply
            result = run_companion_reply(store, candidate, dict(actor))
        elif kind == "agent_orchestration":
            from .orchestration import advance_workflow, default_services
            if not hasattr(store, "_agent_services"):
                store._agent_services = default_services()
            workflow = advance_workflow(store, candidate["payload"]["workflow_id"], dict(actor), expected_version=candidate["payload"].get("workflow_version"), services=store._agent_services)
            result = {"workflow_id": workflow["id"], "workflow_version": workflow["version"], "workflow_state": workflow["status"], "external_actions": []}
        elif kind in {"case_preparation", "evidence_collection"}:
            result = {"cases": [{"id": row["id"], "input_version": row["version"], "missing_inputs": missing_evidence(row)} for row in rows if row["kind"] == "case"], "external_actions": []}
        elif kind == "incident_summary":
            result = {"incidents": [{"id": x["id"], "title": x["title"], "version": x["version"], "status": x["status"]} for x in rows if x["kind"] == "incident"], "summary_type": "Deterministic record index", "external_actions": []}
        elif kind == "regulatory_monitor":
            from pathlib import Path
            import os
            from .regulatory import monitor_registered_source
            payload=candidate["payload"]
            if set(payload)-{"source_id","previous_checksum"} or not payload.get("source_id"):
                raise ValueError("Regulatory monitor requires only a registered source_id and optional previous_checksum")
            source_store=Path(os.environ.get("AIRSPACE_RUNTIME","runtime"))/"sources"/candidate["organisation_id"]
            result=monitor_registered_source(payload["source_id"],source_store,payload.get("previous_checksum"),organisation_id=candidate["organisation_id"])
        elif kind in {"site_screening", "scheduling_proposal", "commercial_analysis"}:
            from .operations import screen_site, calculate_economics
            from .scheduler import solve_schedule
            tool = {"site_screening": screen_site, "scheduling_proposal": solve_schedule, "commercial_analysis": calculate_economics}[kind]
            result = tool({**candidate["payload"], "actor_id": candidate["actor_id"]})
        else:
            raise ValueError("Workflow tool is not allowlisted")
        if kind == "companion_reply" and not result.get("success"):
            state, error = "Failed", "Local companion response could not be generated; inspect the recorded conversation status"
        elif kind=="regulatory_monitor" and not result.get("success"):
            state,error="Failed","Regulatory source check failed; last successful check is preserved in the source record"
        else:
            state, error = "Completed", None
    except Exception as exc:
        result, state, error = None, "Failed", type(exc).__name__ + ": workflow failed; inspect validated inputs"
    with store.engine.begin() as conn:
        conn.execute(update(organisations).where(organisations.c.id == candidate["organisation_id"]).values(audit_seq=organisations.c.audit_seq))
        changed = conn.execute(update(jobs).where(jobs.c.id == candidate["id"], jobs.c.state == "Running", jobs.c.version == version + 1).values(state=state, result=result, error=error, lease_until=None, version=version + 2))
        if changed.rowcount:
            if state == "Completed" and candidate["kind"] == "agent_orchestration" and result.get("workflow_state") == "Queued":
                from .coordination_api import queue_agent_step
                from .orchestration import WorkflowRepository
                workflow = WorkflowRepository(store)._row(conn, result["workflow_id"], candidate["organisation_id"])
                # Re-read after execution so pause/cancel can prevent continuation.
                if workflow["status"] == "Queued":
                    queue_agent_step(store, workflow, dict(actor), conn=conn)
            if state == "Completed" and candidate["kind"] == "regulatory_monitor" and result.get("content_changed"):
                # Follow explicit dependency references without mutating approved inputs.
                affected = {candidate["payload"]["source_id"]}
                pending = list(rows)
                tasks = []
                while pending:
                    found = []
                    for row in pending:
                        refs = set()
                        for key, values in row["data"].items():
                            if key.endswith("_ids") and isinstance(values, list):
                                refs.update(v for v in values if isinstance(v, str))
                        if refs & affected:
                            affected.add(row["id"])
                            found.append(row)
                    if not found:
                        break
                    for row in found:
                        pending.remove(row)
                        owner = row["data"].get("owner") or row["created_by"]
                        task = dict(id=identifier(), organisation_id=candidate["organisation_id"], kind="review_task", title=f"Regulatory change review: {row['title']}", status="Under Review", data={"owner": owner, "affected_record_id": row["id"], "affected_version": row["version"], "source_id": candidate["payload"]["source_id"], "previous_checksum": result.get("previous_checksum"), "current_checksum": result.get("current_checksum"), "job_id": candidate["id"], "existing_decision_modified": False}, version=1, created_by=candidate["actor_id"], created_at=now(), updated_at=now())
                        conn.execute(records.insert().values(**task))
                        store.snapshot(conn, task)
                        tasks.append(task["id"])
                result["review_task_ids"] = tasks
                conn.execute(update(jobs).where(jobs.c.id == candidate["id"]).values(result=result))
            store.append_audit(conn, candidate["organisation_id"], candidate["actor_id"], "job.finished", {"job_id": candidate["id"], "state": state, "attempt": candidate["attempts"] + 1})
    if state == "Failed" and changed.rowcount:
        _mark_agent_job_failure(store, candidate, error, expected_job_version=version + 2)
    return {"id": candidate["id"], "state": state}
