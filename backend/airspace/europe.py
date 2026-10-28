"""Country-segment readiness with distinct legal instruments and handovers.

Registration in this catalogue is geographical scope, not legal validation.
EASA membership is not automatically treated as EU legal applicability.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select

from .scheduler import Contract, Window, snapshot_hash, stamp, utc

RULE_VERSION = "europe-country-segments-2.0.1"
EU = frozenset("AT BE BG HR CY CZ DE DK EE ES FI FR GR HU IE IT LV LT LU MT NL PL PT RO SK SI SE".split())
EASA_OTHER = frozenset({"IS", "LI", "NO", "CH"})
OTHER_EUROPE = frozenset("AL AD AM AZ BA BY GE GB MD MC ME MK RS RU SM TR UA VA XK".split())
COUNTRIES = EU | EASA_OTHER | OTHER_EUROPE
ARTICLE_13 = {"source_id": "easa-uas-xml-2026", "source_version": "June 2026", "source_checksum": "0d35166d374084346d6f4b3ac962102ef75d13963ab8d1d0360cb988ab85dc54", "anchor": "ERULES-1963177438-15488:b0002-b0009", "url": "https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-unmanned-aircraft-systems?erules-id=ERULES-1963177438-15488", "legal_status": "Binding legislation reference consolidation; currentness review required"}
OPERATOR_SUBMISSIONS = frozenset({"host_declaration_submission", "luc_host_notification"})


def country_catalogue() -> list[dict]:
    return [{"country": code, "framework": "EU Member State" if code in EU else "EASA State outside EU; adoption/applicability review required" if code in EASA_OTHER else "Separate national framework", "coverage_status": "Registered", "operationally_validated": False, "default_permission": None} for code in sorted(COUNTRIES)]


class CountryReview(Contract):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    pack_version: str = Field(min_length=1)
    status: Literal["Registered", "Requires Domain Review", "Validated", "Suspended", "Superseded"] = "Registered"
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    framework: Literal["EU UAS", "Reviewed EASA-state adoption", "National framework"]
    source_refs: list[str] = Field(default_factory=list)
    reviewed_by: str | None = None
    applicability_review_ref: str | None = None

    @model_validator(mode="after")
    def valid(self):
        self.valid_from, self.valid_until = utc(self.valid_from), utc(self.valid_until)
        if self.country not in COUNTRIES or self.valid_from >= self.valid_until:
            raise ValueError("Unknown registered European country or invalid review interval")
        if self.country not in EU and self.framework == "EU UAS":
            raise ValueError("EU applicability must not be assumed from European geography or EASA membership")
        return self


class CountryInstrument(Contract):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    kind: Literal["operational_authorisation", "declaration_home_receipt", "host_confirmation", "host_declaration_submission", "luc_terms", "luc_host_notification", "site_airspace", "u_space", "national_operating_basis"]
    issuer: str = Field(min_length=1)
    issuing_country: str = Field(pattern=r"^[A-Z]{2}$")
    recipient_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    provided_at: AwareDatetime | None = None
    operation_countries: list[str] = Field(min_length=1)
    operator_organisation_id: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    route_version: str = Field(min_length=1)
    status: Literal["Draft", "Under Review", "Recorded", "Approved", "Expired", "Suspended", "Superseded"]
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    evidence_ref: str = Field(min_length=1)
    legal_source_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        self.valid_from, self.valid_until = utc(self.valid_from), utc(self.valid_until)
        if self.issuing_country not in COUNTRIES or not set(self.operation_countries).issubset(COUNTRIES) or self.valid_from >= self.valid_until:
            raise ValueError("Instrument needs actual registered country codes and positive validity; no universal EU permission scope")
        if self.recipient_country is not None and self.recipient_country not in COUNTRIES:
            raise ValueError("Submission recipient must be an actual registered country")
        if self.provided_at is not None:
            self.provided_at = utc(self.provided_at)
        if self.kind in OPERATOR_SUBMISSIONS and (not self.recipient_country or not self.provided_at):
            raise ValueError("Operator submission needs its actual recipient country, provision timestamp and documented delivery evidence_ref; no host-authority response is implied")
        return self


class CountrySegment(Contract):
    id: str = Field(min_length=1)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    interval: Window
    country_review_id: str = Field(min_length=1)
    country_review_version: int = Field(ge=1)
    legal_route: Literal["Operational Authorisation", "STS Declaration", "LUC Privilege", "Open Category", "National or Certified"]
    permission_requirements_reviewed: bool = False
    required_instrument_kinds: list[str] = Field(default_factory=list)
    instrument_ids: list[str] = Field(default_factory=list)
    local_conditions_review_ref: str | None = None
    local_mitigations_ref: str | None = None
    source_freshness_review_ref: str | None = None


class BorderHandover(Contract):
    from_segment_id: str = Field(min_length=1)
    to_segment_id: str = Field(min_length=1)
    procedure_ref: str = Field(min_length=1)
    responsible_person_id: str = Field(min_length=1)
    acknowledgement_ref: str | None = None
    contingency_coordination_ref: str | None = None


class CrossBorderPlan(Contract):
    actor_id: str = Field(min_length=1)
    mission_id: str = Field(min_length=1)
    mission_version: int = Field(ge=1)
    operator_organisation_id: str = Field(min_length=1)
    registration_country: str = Field(pattern=r"^[A-Z]{2}$")
    configuration_id: str = Field(min_length=1)
    route_version: str = Field(min_length=1)
    operation_interval: Window
    segments: list[CountrySegment] = Field(min_length=1, max_length=100)
    country_reviews: list[CountryReview] = Field(default_factory=list, max_length=100)
    instruments: list[CountryInstrument] = Field(default_factory=list, max_length=1000)
    handovers: list[BorderHandover] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid(self):
        if self.registration_country not in COUNTRIES:
            raise ValueError("Operator registration country is not in the geographical catalogue")
        for collection in (self.segments, self.country_reviews, self.instruments):
            if len({item.id for item in collection}) != len(collection):
                raise ValueError("Segment, review and instrument IDs must each be unique")
        return self


def assess_cross_border(payload: CrossBorderPlan | dict) -> dict:
    request = payload if isinstance(payload, CrossBorderPlan) else CrossBorderPlan.model_validate(payload)
    findings, results = [], []
    reviews = {review.id: review for review in request.country_reviews}
    instruments = {instrument.id: instrument for instrument in request.instruments}
    ordered = sorted(request.segments, key=lambda segment: segment.interval.start)
    if ordered[0].interval.start != request.operation_interval.start or ordered[-1].interval.end != request.operation_interval.end:
        findings.append("Country segments do not cover the full reviewed operation interval")
    for previous, following in zip(ordered, ordered[1:]):
        if previous.interval.end != following.interval.start:
            findings.append("Country segments overlap or have an unreviewed time gap")
        if previous.country != following.country:
            handovers = [handover for handover in request.handovers if handover.from_segment_id == previous.id and handover.to_segment_id == following.id]
            if len(handovers) != 1 or not handovers[0].acknowledgement_ref or not handovers[0].contingency_coordination_ref:
                findings.append(f"{previous.id}->{following.id}: accountable handover acknowledgement and contingency coordination are incomplete")
    for segment in ordered:
        missing, review = [], reviews.get(segment.country_review_id)
        if segment.country not in COUNTRIES:
            missing.append("Country is outside the registered geographical catalogue")
        if not request.operation_interval.start <= segment.interval.start < segment.interval.end <= request.operation_interval.end:
            missing.append("Segment lies outside the proposed operation interval")
        if not review or review.version != segment.country_review_version or review.country != segment.country or review.status != "Validated" or not review.reviewed_by or not review.applicability_review_ref or not review.source_refs or not review.valid_from <= segment.interval.start < segment.interval.end <= review.valid_until:
            missing.append("Current accountable country-pack and applicability review is missing")
        if not segment.permission_requirements_reviewed or not segment.required_instrument_kinds and segment.legal_route != "Open Category":
            missing.append("Required legal instruments have not been explicitly reviewed")
        if not segment.local_conditions_review_ref or not segment.local_mitigations_ref or not segment.source_freshness_review_ref:
            missing.append("Local conditions, mitigations and authoritative-source freshness review are incomplete")
        required = set(segment.required_instrument_kinds)
        if segment.country not in EU or request.registration_country not in EU or review and review.framework != "EU UAS":
            # Cross-jurisdiction adoption and bilateral rules require a separate
            # reviewed basis; the Article 13 shortcuts are not assumed here.
            required.add("national_operating_basis")
        elif segment.legal_route == "Operational Authorisation":
            required.add("operational_authorisation")
            if segment.country != request.registration_country:
                required.add("host_confirmation")
        elif segment.legal_route == "STS Declaration":
            required.add("declaration_home_receipt")
            if segment.country != request.registration_country:
                # Article 13(3), preserved b0006: the operator provides copies of
                # its declaration and home confirmation of receipt/completeness.
                required.add("host_declaration_submission")
        elif segment.legal_route == "LUC Privilege":
            required.add("luc_terms")
            if segment.country != request.registration_country:
                # Article 13(4), b0007-b0009, requires provision of terms and
                # locations; it does not require a new host-issued approval.
                required.add("luc_host_notification")
        elif segment.legal_route == "National or Certified":
            required.add("national_operating_basis")
        elif segment.legal_route == "Open Category":
            # An open-category applicability review is still required. No
            # operational-authorisation or Article13 confirmation is invented.
            pass
        decisions = []
        for kind in sorted(required):
            matches = []
            for reference in segment.instrument_ids:
                instrument = instruments.get(reference)
                if instrument and instrument.kind == kind and instrument.status == "Approved" and instrument.operator_organisation_id == request.operator_organisation_id and instrument.configuration_id == request.configuration_id and instrument.route_version == request.route_version and segment.country in instrument.operation_countries and instrument.valid_from <= segment.interval.start < segment.interval.end <= instrument.valid_until:
                    expected_issuer = segment.country if kind in {"host_confirmation", "site_airspace", "u_space", "national_operating_basis"} else request.registration_country
                    submission_scoped = kind not in OPERATOR_SUBMISSIONS or (instrument.recipient_country == segment.country and instrument.provided_at <= segment.interval.start)
                    if instrument.issuing_country == expected_issuer and submission_scoped:
                        matches.append(instrument.id)
            decisions.append({"kind": kind, "instrument_ids": matches, "state": "Recorded In Scope" if len(matches) == 1 else "Missing or Ambiguous", "record_role": "Operator Documented Submission" if kind in OPERATOR_SUBMISSIONS else "Legal Instrument Evidence", "review_meaning": "Internal evidence review; no authority issuance or response"})
            if len(matches) != 1:
                missing.append(f"{kind}: a single unexpired, operator/configuration/route/country-scoped instrument is required")
        results.append({"segment_id": segment.id, "country": segment.country, "state": "Readiness Evidence Recorded" if not missing else "Blocked", "findings": missing, "decisions": decisions})
        findings.extend(f"{segment.id}: {finding}" for finding in missing)
    return {"rule_version": RULE_VERSION, "input_snapshot": snapshot_hash(request), "actor_id": request.actor_id, "created_at": stamp(datetime.now(timezone.utc).replace(microsecond=0)),
            "status": "Blocked" if findings else "Country Readiness Evidence Recorded; Internal Review Required", "ready_for_internal_review": not findings, "segments": results, "findings": findings,
            "source": ARTICLE_13, "authority_status": "No universal European permission; country instruments, U-space responses and internal dispatch remain distinct"}


def validate_persisted_coordination(conn, tenant, mission_row, assignment, actor_id):
    """Check current country/instrument record versions inside dispatch lock."""
    from .storage import records
    raw = mission_row["data"].get("coordination")
    if not raw:
        raise HTTPException(422, "A country-segment coordination plan is required before internal dispatch release")
    plan = CrossBorderPlan.model_validate({**raw, "actor_id": actor_id, "mission_id": mission_row["id"], "mission_version": mission_row["version"], "operator_organisation_id": tenant})
    if plan.operation_interval.start != datetime.fromisoformat(assignment["start"].replace("Z", "+00:00")) or plan.operation_interval.end != datetime.fromisoformat(assignment["end"].replace("Z", "+00:00")):
        raise HTTPException(422, "Country segment timing differs from the current reserved assignment")
    for review in plan.country_reviews:
        row = conn.execute(select(records).where(records.c.id == review.id, records.c.kind == "country_review", records.c.organisation_id == tenant)).mappings().first()
        if not row or row["status"] != "Approved" or row["version"] != review.version or row["data"].get("country_review") != review.model_dump(mode="json"):
            raise HTTPException(409, "Country review snapshot is stale, unapproved or unavailable")
    for instrument in plan.instruments:
        row = conn.execute(select(records).where(records.c.id == instrument.id, records.c.kind == "country_instrument", records.c.organisation_id == tenant)).mappings().first()
        if not row or row["status"] != "Approved" or row["version"] != instrument.version or row["data"].get("instrument") != instrument.model_dump(mode="json"):
            raise HTTPException(409, "Country-specific legal instrument is stale, unapproved or unavailable")
        if instrument.kind in OPERATOR_SUBMISSIONS and instrument.provided_at > datetime.now(timezone.utc):
            raise HTTPException(422, "A future-dated operator submission cannot support current internal dispatch")
    result = assess_cross_border(plan)
    if not result["ready_for_internal_review"]:
        raise HTTPException(422, {"message": "Country-segment readiness is blocked", "assessment": result})
    return result
