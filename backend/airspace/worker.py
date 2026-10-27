"""Bounded durable internal workflows. No external correspondence or aircraft tools."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, select, update
from .storage import jobs, records, users, now, identifier
from .workflows import missing_evidence

TOOL_ROLES = {"regulatory_monitor": {"regulatory"}, "evidence_collection": {"regulatory"}, "case_preparation": {"regulatory"}, "site_screening": {"planner", "regulatory"}, "scheduling_proposal": {"planner"}, "incident_summary": {"incident_coordinator"}, "commercial_analysis": {"analyst"}}


def run_once(store):
    stamp = now()
    with store.engine.begin() as conn:
        exhausted = conn.execute(select(jobs).where(jobs.c.state == "Running", jobs.c.lease_until < stamp, jobs.c.attempts >= 3)).mappings().all()
        for job in exhausted:
            changed = conn.execute(update(jobs).where(jobs.c.id == job["id"], jobs.c.version == job["version"], jobs.c.state == "Running").values(state="Failed", error="Retry budget exhausted after worker interruption", lease_until=None, version=jobs.c.version + 1))
            if changed.rowcount:
                store.append_audit(conn, job["organisation_id"], job["actor_id"], "job.exhausted", {"job_id": job["id"], "attempts": job["attempts"]})
        candidate = conn.execute(select(jobs).where(or_(jobs.c.state == "Queued", and_(jobs.c.state == "Running", jobs.c.lease_until < stamp)), jobs.c.attempts < 3).order_by(jobs.c.created_at).limit(1)).mappings().first()
        if not candidate:
            return None
        candidate = dict(candidate)
        if candidate["deadline"] and datetime.fromisoformat(candidate["deadline"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
            conn.execute(update(jobs).where(jobs.c.id == candidate["id"]).values(state="Expired", error="Deadline exceeded"))
            return {"id": candidate["id"], "state": "Expired"}
        version = candidate["version"]
        lease = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
        result = conn.execute(update(jobs).where(jobs.c.id == candidate["id"], jobs.c.version == version, jobs.c.state == candidate["state"]).values(state="Running", lease_until=lease, attempts=candidate["attempts"] + 1, version=version + 1))
        if result.rowcount != 1:
            return None
    try:
        with store.engine.connect() as conn:
            actor = conn.execute(select(users).where(users.c.id == candidate["actor_id"], users.c.organisation_id == candidate["organisation_id"], users.c.disabled == 0)).mappings().first()
            if not actor:
                raise ValueError("Accountable actor is unavailable")
            if actor["role"] not in TOOL_ROLES.get(candidate["kind"], set()):
                raise ValueError("Accountable actor lacks this tool permission")
            # Context remains tenant-filtered even when a model is unavailable.
            rows = [dict(x) for x in conn.execute(select(records).where(records.c.organisation_id == candidate["organisation_id"])).mappings().all()]
        kind = candidate["kind"]
        if kind in {"case_preparation", "evidence_collection"}:
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
        if kind=="regulatory_monitor" and not result.get("success"):
            state,error="Failed","Regulatory source check failed; last successful check is preserved in the source record"
        else:
            state, error = "Completed", None
    except Exception as exc:
        result, state, error = None, "Failed", type(exc).__name__ + ": workflow failed; inspect validated inputs"
    with store.engine.begin() as conn:
        changed = conn.execute(update(jobs).where(jobs.c.id == candidate["id"], jobs.c.state == "Running", jobs.c.version == version + 1).values(state=state, result=result, error=error, lease_until=None, version=version + 2))
        if changed.rowcount:
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
    return {"id": candidate["id"], "state": state}
