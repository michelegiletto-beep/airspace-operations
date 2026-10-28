"""Bind typed domain snapshots to server-owned identity and review state."""
from copy import deepcopy
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy import select
from .storage import records

TYPED_KINDS = {"maintenance_program": "program", "maintenance_work_order": "work_order", "country_review": "country_review", "country_instrument": "instrument"}
PROTECTED_KINDS = {"agent_workflow", "pilot_acknowledgement", "dispatch_release"}


def normalise_domain_record(row):
    key = TYPED_KINDS.get(row["kind"])
    if key is None:
        return row
    data = deepcopy(row["data"])
    payload = data.get(key, {})
    if not isinstance(payload, dict):
        raise HTTPException(422, f"{key} must be an object")
    payload.update(id=row["id"], version=row["version"])
    approvals = data.get("_approvals", [])
    reviewer = approvals[-1]["actor_id"] if approvals else None
    if row["kind"] == "maintenance_program":
        payload.update(status=row["status"] if row["status"] in {"Draft", "Under Review", "Approved", "Suspended", "Superseded"} else "Draft", approved_by=reviewer if row["status"] == "Approved" else None)
    elif row["kind"] == "country_review":
        payload.update(status="Validated" if row["status"] == "Approved" else "Requires Domain Review" if row["status"] == "Under Review" else "Suspended" if row["status"] == "Suspended" else "Superseded" if row["status"] == "Superseded" else "Registered", reviewed_by=reviewer if row["status"] == "Approved" else None)
    elif row["kind"] == "country_instrument":
        payload["status"] = row["status"] if row["status"] in {"Draft", "Under Review", "Approved", "Expired", "Suspended", "Superseded"} else "Draft"
    elif row["kind"] == "maintenance_work_order" and row["status"] == "Draft":
        payload["state"] = "Draft"
        payload["completion"] = []
        payload["actual_start"] = None
        payload["actual_end"] = None
    data[key] = payload
    row["data"] = data
    return row


def domain_model(kind):
    from .fleet import MaintenanceProgram, MaintenanceWorkOrder
    from .europe import CountryReview, CountryInstrument
    return {"maintenance_program": MaintenanceProgram, "maintenance_work_order": MaintenanceWorkOrder, "country_review": CountryReview, "country_instrument": CountryInstrument}.get(kind)


def domain_missing(row):
    model = domain_model(row["kind"]) if row["kind"] in TYPED_KINDS else None
    if model is None:
        return []
    key = TYPED_KINDS[row["kind"]]
    try:
        model.model_validate(row["data"].get(key, {}))
    except ValidationError as error:
        return [key + "." + ".".join(map(str, item["loc"])) + ": " + item["msg"] for item in error.errors(include_input=False)]
    if row["kind"] == "country_review":
        value = row["data"][key]
        return ["country_review." + field for field in ("source_refs", "applicability_review_ref") if not value.get(field)]
    return []


def require_domain_review_evidence(conn, row, evidence_ids):
    if row["kind"] not in TYPED_KINDS:
        return
    data = row["data"]
    requested = set(data.get("evidence_ids", [])) | set(evidence_ids)
    if row["kind"] == "country_instrument":
        receipt = data.get("instrument", {}).get("evidence_ref")
        if receipt not in requested:
            raise HTTPException(422, "Country instrument source or documented-submission evidence must be among the reviewed evidence")
    if not requested:
        raise HTTPException(422, "Typed maintenance and country decisions require reviewed source evidence")
    for reference in requested:
        evidence = conn.execute(select(records).where(records.c.id == reference, records.c.organisation_id == row["organisation_id"], records.c.kind == "evidence")).mappings().first()
        if not evidence or evidence["status"] != "Approved" or not evidence["data"].get("_approvals"):
            raise HTTPException(422, "Source evidence must be independently reviewed before the domain decision")
