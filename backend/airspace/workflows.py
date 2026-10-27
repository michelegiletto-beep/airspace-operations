"""Fail-closed workflow state transitions. No aviation approval is inferred."""
from datetime import datetime, timezone
from fastapi import HTTPException

KINDS = {"case", "evidence", "permission", "aircraft", "personnel", "site", "route", "mission", "incident", "procedure", "stakeholder", "commercial", "qualification", "alert", "review_task", "requirement", "risk_assessment", "corrective_action", "interpretation", "obligation", "operational_volume", "resource", "schedule", "telemetry", "approval", "correspondence", "connector", "saved_search"}
TRANSITIONS = {
    "Draft": {"Missing Evidence", "Under Review"},
    "Missing Evidence": {"Draft", "Under Review"},
    "Under Review": {"Draft", "Approved", "Rejected", "Missing Evidence"},
    "Approved": {"Submitted", "Expired", "Suspended", "Superseded"},
    "Submitted": {"Under Review", "Rejected", "Approved", "Missing Evidence"},
    "Rejected": {"Draft", "Superseded"},
    "Suspended": {"Under Review", "Expired", "Superseded"},
    "Expired": {"Superseded"},
    "Superseded": set(),
}
REQUIRED = {
    "case": ["jurisdiction", "legal_route", "conops", "owner", "aircraft_configuration_id"],
    "evidence": ["provenance", "checksum", "evidence_type"],
    "permission": ["permission_type", "issuer", "valid_from", "valid_to", "scope", "receipt_evidence_id"],
    "aircraft": ["configuration_id", "serviceability", "maintenance_valid_to"],
    "personnel": ["qualifications", "availability"],
    "route": ["geometry", "vertical_reference", "source_ids"],
    "procedure": ["content", "aircraft_configuration_id", "revision"],
    "risk_assessment": ["methodology", "conops_version", "configuration_id", "evidence_ids"],
}


def missing_evidence(row):
    data = row["data"]
    missing = [field for field in REQUIRED.get(row["kind"], []) if data.get(field) in (None, "", [])]
    missing.extend(f"requirement:{value}" for value in data.get("missing_requirement_ids", []))
    if row["kind"] == "case" and not data.get("evidence_ids"):
        missing.append("evidence_ids")
    return sorted(set(missing))


def check_transition(row, user, target, reason, evidence):
    if target not in TRANSITIONS.get(row["status"], set()):
        raise HTTPException(409, "Transition is not available from this state")
    if not reason.strip():
        raise HTTPException(422, "A recorded reason is required")
    if target in {"Under Review", "Approved", "Submitted"}:
        missing = missing_evidence(row)
        if missing:
            raise HTTPException(422, {"message": "Mandatory evidence is missing", "missing_inputs": missing})
    if target == "Approved":
        if user["role"] != "reviewer":
            raise HTTPException(403, "Only an assigned reviewer can record approval")
        if user["id"] in {row["created_by"], row["data"].get("_prepared_by")}:
            raise HTTPException(403, "Independent review required: creator cannot approve")
        if user["id"] not in row["data"].get("reviewer_ids", []):
            raise HTTPException(403, "Reviewer is not assigned to this record")
        if not evidence:
            raise HTTPException(422, "Approval requires evidence references")
        if row["kind"] == "permission":
            data = row["data"]
            if data["permission_type"] not in {"operational_authorisation", "site_permission", "uspace_authorisation", "declaration", "luc_privilege"}:
                raise HTTPException(422, "Unknown permission instrument")
            if data["receipt_evidence_id"] not in evidence:
                raise HTTPException(422, "Issuer decision receipt must be among referenced evidence")
            try:
                start = datetime.fromisoformat(data["valid_from"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(data["valid_to"].replace("Z", "+00:00"))
                if start.tzinfo is None or end.tzinfo is None or start >= end or end <= datetime.now(timezone.utc):
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise HTTPException(422, "Permission validity must be timezone-aware and unexpired")
    if target == "Submitted" and (not row["data"].get("submission_receipt_evidence_id") or row["data"]["submission_receipt_evidence_id"] not in evidence):
        raise HTTPException(422, "Submission requires a real receipt or a documented manual submission evidence record")
    if row["kind"] == "mission" and target == "Approved":
        raise HTTPException(422, "Mission dispatch requires the dedicated independently verified dispatch workflow")
