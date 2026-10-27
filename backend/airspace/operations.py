"""Deterministic operational decision support. No aircraft command capability.

Evidence is an explicit input. Missing evidence cannot be converted into a
favourable result. All examples and artificial records belong in tests only.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from .scheduler import Contract, Mission, Window, snapshot_hash, stamp

RULE_VERSION = "operations-1.1.0"
SORA_25_SNAPSHOT = "0d35166d374084346d6f4b3ac962102ef75d13963ab8d1d0360cb988ab85dc54"
SORA_25_SECTION = "https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-unmanned-aircraft-systems?erules-id=ERULES-1963177438-24086"
# June 2026 eRules AMC1 Article 11, S.4.7.3. The text refers to
# Table 7 but the published caption reads Table 3. Preserve this discrepancy.
SAIL_25_TABLE = {
    2: ("I", "II", "IV", "VI"), 3: ("II", "II", "IV", "VI"),
    4: ("III", "III", "IV", "VI"), 5: ("IV", "IV", "IV", "VI"),
    6: ("V", "V", "V", "VI"), 7: ("VI", "VI", "VI", "VI"),
}


def utc(value: datetime) -> datetime:
    """Preserve source subsecond precision; scheduling has a stricter contract."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A UTC offset is required")
    return value.astimezone(timezone.utc)
SORA_SOURCES = {
    "2.5": {"identifier": "ED Decision 2025/018/R", "url": "https://www.easa.europa.eu/en/document-library/agency-decisions/ed-decision-2025018r", "anchor": "Annex; AMC1 Article 11; SORA 2.5", "legal_status": "Acceptable means of compliance and guidance; not an operational authorisation"},
    "2.0": {"identifier": "ED Decision 2019/021/R", "url": "https://www.easa.europa.eu/en/document-library/agency-decisions/ed-decision-2019021r", "anchor": "Annex; AMC1 Article 11; SORA 2.0", "legal_status": "Historical methodology; jurisdiction and case applicability require review"},
}


def trace(payload: dict | Contract, rule: str) -> dict:
    data = payload.model_dump(mode="json") if isinstance(payload, Contract) else payload
    return {"rule_version": f"{RULE_VERSION}/{rule}", "input_snapshot": snapshot_hash(data), "actor_id": data.get("actor_id"),
            "created_at": stamp(datetime.now(timezone.utc).replace(microsecond=0)), "model_version": None,
            "source_versions": data.get("source_versions", []), "authority_status": "Internal decision support; no authority-issued permission"}


class EvidenceRecord(Contract):
    id: str = Field(min_length=1)
    source_anchor: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    conops_version: str = Field(min_length=1)
    methodology: Literal["2.0", "2.5"]
    category: Literal["Design Claim", "Simulation", "Laboratory", "Field", "Authority Record", "Document Review"]
    review_status: Literal["Draft", "Under Review", "Approved", "Rejected", "Superseded"]
    reviewed_by: str | None = None


class SoraCalculationInputs(Contract):
    final_grc: int | None = Field(default=None, ge=1, le=10)
    residual_arc: Literal["ARC-a", "ARC-b", "ARC-c", "ARC-d"] | None = None
    flight_mode: Literal["BVLOS", "VLOS", "BVLOS with Airspace Observers"] | None = None
    maximum_speed_m_s: float | None = Field(default=None, gt=0)
    reviewed_inputs_ref: str | None = None
    reviewed_by: str | None = None
    source_snapshot_checksum: str | None = None


def sora_25_lookups(inputs: SoraCalculationInputs, methodology: str) -> dict:
    """Narrow source-bound calculations, never a complete SORA assessment."""
    findings = []
    result = {"status": "Missing Evidence", "SAIL": None, "TMPR": None, "adjacent_ground_outer_distance_m": None,
              "source_snapshot_checksum": SORA_25_SNAPSHOT, "source_version": "EASA EAR UAS June 2026 / ED Decision 2025/018/R",
              "source_url": SORA_25_SECTION, "rule_version": "sora25-lookups-1.0.0", "qualified_validation": "Requires Domain Review", "findings": findings}
    if methodology != "2.5":
        findings.append("This calculation implements only the source-bound SORA 2.5 tables; historical editions are kept separate")
        return result
    if inputs.source_snapshot_checksum != SORA_25_SNAPSHOT:
        findings.append("Reviewed source snapshot does not match the implemented June 2026 table version")
        return result
    if not inputs.reviewed_inputs_ref or not inputs.reviewed_by:
        findings.append("Input GRC/ARC/mode/speed claims need an accountable review reference; they cannot be inferred by this lookup")
        return result
    if inputs.final_grc is None or inputs.residual_arc is None:
        findings.append("Reviewed final GRC and residual ARC are both required for SAIL lookup")
    elif inputs.final_grc > 7:
        result["SAIL"] = "Outside SORA specific-category scope"
        findings.append("Final GRC exceeds the published SORA table scope; no SAIL is assigned")
    else:
        row = max(2, inputs.final_grc)
        column = ("ARC-a", "ARC-b", "ARC-c", "ARC-d").index(inputs.residual_arc)
        result["SAIL"] = SAIL_25_TABLE[row][column]
        result["sail_source_anchor"] = f"ERULES-1963177438-24086:b{461 + row - 2:04d}"
        result["sail_source_description"] = "S.4.7.3, table referenced as Table 7; caption in this publication is Table 3"
    if inputs.residual_arc is None or inputs.flight_mode is None:
        findings.append("Residual ARC and reviewed segment flight mode are required for tactical-mitigation lookup")
    elif inputs.flight_mode == "BVLOS":
        arc = inputs.residual_arc[-1]
        result["TMPR"] = {"a": "No requirement", "b": "Low", "c": "Medium", "d": "High"}[arc]
        result["tmpr_source_anchor"] = f"ERULES-1963177438-24086:b{426 - (ord(arc) - ord('a')):04d}"
        result["tmpr_source_description"] = "S.4.6.3 BVLOS operations, Table 6; supporting compliance evidence remains required"
    else:
        result["TMPR"] = "VLOS deconfliction scheme and applicable observer procedures require review"
        result["tmpr_source_anchor"] = "ERULES-1963177438-24086:b0415-b0417,b0432-b0436"
    if inputs.maximum_speed_m_s is None:
        findings.append("Maximum speed with configuration evidence is required for adjacent-ground outer-distance calculation")
    else:
        result["adjacent_ground_outer_distance_m"] = min(35000.0, max(5000.0, inputs.maximum_speed_m_s * 180))
        result["adjacent_distance_formula"] = "min(35000 m, max(5000 m, maximum_speed_m_s * 180 s))"
        result["adjacent_distance_source_anchor"] = "ERULES-1963177438-24086:b0486-b0489"
        result["adjacent_distance_limitation"] = "Distance from operational volume only; not a containment robustness result or ground-risk-buffer calculation; assess S.4.8.3(a) and all other applicability conditions separately"
    if not findings:
        result["status"] = "Calculated; Requires Domain Review"
    elif result["SAIL"] is not None or result["TMPR"] is not None or result["adjacent_ground_outer_distance_m"] is not None:
        result["status"] = "Partial Calculation; Requires Domain Review"
    return result


class RiskRequest(Contract):
    actor_id: str = Field(min_length=1)
    methodology: Literal["2.0", "2.5"]
    configuration_id: str = Field(min_length=1)
    conops_version: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2)
    evidence: dict[str, list[EvidenceRecord]] = Field(default_factory=dict)
    methodology_applicability_review_ref: str | None = None
    calculation_inputs: SoraCalculationInputs | None = None
    source_versions: list[str] = Field(default_factory=list)


SORA_REQUIREMENTS = (
    ("conops", "Operation, aircraft configuration, operating volumes, personnel and limitations"),
    ("ground_risk", "Ground-risk inputs, population evidence and source precision"),
    ("ground_mitigations", "Applicable strategic ground-risk mitigations and supporting evidence"),
    ("initial_air_risk", "Airspace structure, traffic evidence, environment and initial air-risk assessment"),
    ("strategic_air_mitigations", "Restrictions, assumptions, exposure and strategic air mitigations"),
    ("residual_air_risk", "Residual air-risk assessment linked to ConOps and mitigations"),
    ("tactical_mitigation", "Tactical mitigation performance requirements and evidence"),
    ("sail", "Version-specific SAIL determination with reviewed calculation trace"),
    ("containment", "Containment and adjacent-area assessment"),
    ("operational_safety_objectives", "Applicable operational safety objectives and assurance evidence"),
)


def assess_sora(payload: dict | RiskRequest) -> dict:
    """Version-bound evidence workbench, deliberately not a SORA risk calculator.

    Table transcription and qualified domain validation are not present. Even a
    complete evidence register therefore cannot produce an assessed risk class.
    """
    request = payload if isinstance(payload, RiskRequest) else RiskRequest.model_validate(payload)
    findings, requirements = [], []
    if not request.methodology_applicability_review_ref:
        findings.append("Methodology applicability for this jurisdiction and case has not been reviewed")
    for key, description in SORA_REQUIREMENTS:
        records = request.evidence.get(key, [])
        accepted, mismatches = [], []
        for record in records:
            reasons = []
            if record.methodology != request.methodology:
                reasons.append("different SORA edition")
            if record.configuration_id != request.configuration_id:
                reasons.append("different aircraft configuration")
            if record.conops_version != request.conops_version:
                reasons.append("different ConOps version")
            if record.review_status != "Approved" or not record.reviewed_by:
                reasons.append("accountable review is incomplete")
            if reasons:
                mismatches.append({"id": record.id, "reasons": reasons})
            else:
                accepted.append(record.id)
        requirements.append({"id": key, "description": description, "state": "Evidence Recorded" if accepted else "Missing Evidence", "accepted_evidence": accepted,
                             "rejected_for_reuse": mismatches, "methodology": request.methodology, "source": SORA_SOURCES[request.methodology]})
        if not accepted:
            findings.append(f"{key}: no approved evidence matching methodology, aircraft configuration and ConOps")
    unknown = sorted(set(request.evidence) - {r[0] for r in SORA_REQUIREMENTS})
    if unknown:
        findings.append("Unmapped evidence categories: " + ", ".join(unknown))
    calculation = sora_25_lookups(request.calculation_inputs, request.methodology) if request.calculation_inputs else None
    findings.append("A complete SORA calculation and OSO compliance determination is not implemented; any supplied SORA 2.5 lookup remains subject to qualified domain review")
    return {**trace(request, "sora-evidence"), "status": "Missing Evidence" if any(r["state"] == "Missing Evidence" for r in requirements) else "Requires Domain Review",
            "methodology": request.methodology, "requirements": requirements, "findings": findings,
            "calculation_status": calculation["status"] if calculation else "Not Implemented", "calculation": calculation,
            "risk_classes": {"GRC": None, "ARC": None, "SAIL": None}, "source_versions": request.source_versions or [SORA_SOURCES[request.methodology]["identifier"]]}


class DispatchRequest(Contract):
    actor_id: str = Field(min_length=1)
    mission: Mission
    start: AwareDatetime
    end: AwareDatetime
    aircraft_serviceable: bool | None = None
    configuration_id: str | None = None
    pilot_id: str | None = None
    pilot_qualified_until: AwareDatetime | None = None
    independent_review_required: bool = True
    prepared_by: str = Field(min_length=1)
    reviewer_id: str | None = None
    source_versions: list[str] = Field(default_factory=list)


def assess_dispatch(payload: dict | DispatchRequest) -> dict:
    request = payload if isinstance(payload, DispatchRequest) else DispatchRequest.model_validate(payload)
    mission, errors = request.mission, []
    start, end = utc(request.start), utc(request.end)
    if not mission.window.start <= start < end <= mission.window.end:
        errors.append("Assignment is outside the proposed operation window")
    if (end - start).total_seconds() != mission.duration_seconds:
        errors.append("Assigned duration differs from the reviewed operation")
    if request.aircraft_serviceable is not True:
        errors.append("Aircraft serviceability is missing or blocked")
    if request.configuration_id != mission.configuration_id:
        errors.append("Aircraft configuration has changed or is unknown")
    if not request.pilot_id or not request.pilot_qualified_until or utc(request.pilot_qualified_until) < end:
        errors.append("Pilot identity or applicable qualification validity is missing")
    if not request.reviewer_id:
        errors.append("Accountable dispatch reviewer is missing")
    if request.independent_review_required and request.reviewer_id == request.prepared_by:
        errors.append("Configured second review cannot be performed by the preparer")
    if not mission.permission_requirements_reviewed or not mission.required_permission_kinds or "operating_basis" not in mission.required_permission_kinds:
        errors.append("Applicable legal operating basis and permission requirements need review")
    required = set(mission.required_permission_kinds) | {"safety_review", "internal_dispatch", "pilot_acknowledgement"}
    if mission.u_space_required is None:
        errors.append("U-space applicability is unknown")
    elif mission.u_space_required:
        required.add("u_space")
    decisions = []
    for kind in sorted(required):
        candidates = [p for p in mission.permissions if p.kind == kind and p.status == "Approved" and p.configuration_id == mission.configuration_id and p.route_version == mission.route_version and p.valid_from <= start < end <= p.valid_until]
        decisions.append({"kind": kind, "state": "Recorded and in scope" if len(candidates) == 1 else "Blocked", "instrument_ids": [p.id for p in candidates]})
        if len(candidates) != 1:
            errors.append(f"{kind}: no single unambiguous, valid and in-scope instrument")
    if not mission.route_approved:
        errors.append("Approved route version is missing")
    for name in ("weather", "airspace") + (("provider",) if mission.u_space_required else ()):
        feed = getattr(mission, name)
        if feed is None or not feed.suitable or not feed.operational_use_accepted or not feed.observed_at <= start < end <= feed.valid_until:
            errors.append(f"{name}: missing, stale, unsuitable or unaccepted source")
    return {**trace(request, "dispatch"), "status": "Blocked" if errors else "Eligible for Internal Release Review", "findings": errors,
            "decisions": decisions, "flight_execution": "Not Executed", "release_created": False,
            "limitation": "Assessment does not reserve resources, grant approval or command flight; the server must atomically recheck current records and reviewer permissions"}


class Position(Contract):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    altitude_m: float | None = None
    vertical_reference: Literal["AGL", "AMSL", "FL", "Unknown"] = "Unknown"
    horizontal_uncertainty_m: float = Field(ge=0)
    vertical_uncertainty_m: float | None = Field(default=None, ge=0)
    crs: Literal["EPSG:4326"] = "EPSG:4326"
    terrain_elevation_amsl_m: float | None = None
    terrain_evidence_ref: str | None = None
    terrain_uncertainty_m: float | None = Field(default=None, ge=0)


class Zone(Contract):
    id: str = Field(min_length=1)
    source_anchor: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    purpose: Literal["Operationally Accepted", "Research Only"]
    geometry: dict
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    lower_m: float | None = None
    upper_m: float | None = None
    vertical_reference: Literal["AGL", "AMSL", "FL", "Unknown"] = "Unknown"
    source_precision_m: float = Field(ge=0)
    restriction: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        self.valid_from, self.valid_until = utc(self.valid_from), utc(self.valid_until)
        if self.valid_until <= self.valid_from:
            raise ValueError("Zone validity must be positive")
        if self.lower_m is not None and self.upper_m is not None and self.lower_m > self.upper_m:
            raise ValueError("Zone upper vertical bound is below the lower bound")
        kind = self.geometry.get("type")
        if kind == "Circle":
            centre = self.geometry.get("coordinates", [])
            radius = self.geometry.get("radius_m")
            if len(centre) != 2 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in centre) or not -180 <= centre[0] <= 180 or not -90 <= centre[1] <= 90 or not isinstance(radius, (int, float)) or not math.isfinite(radius) or radius <= 0 or radius > 100000:
                raise ValueError("Circle needs a WGS84 centre and a radius in (0, 100000] metres")
        elif kind == "Polygon":
            rings = self.geometry.get("coordinates", [])
            if not rings or len(rings) > 10 or sum(len(ring) for ring in rings) > 2000:
                raise ValueError("A polygon needs at least one ring")
            for ring in rings:
                if len(ring) < 4 or ring[0] != ring[-1] or any(len(p) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p) or not -180 <= p[0] <= 180 or not -90 <= p[1] <= 90 for p in ring):
                    raise ValueError("Polygon rings must be closed WGS84 longitude/latitude pairs")
        else:
            raise ValueError("Supported screening geometry: Circle or Polygon")
        return self


class SiteScreenRequest(Contract):
    actor_id: str = Field(min_length=1)
    point: Position
    at: AwareDatetime
    zones: list[Zone] = Field(default_factory=list, max_length=1000)
    coverage: dict[str, str] = Field(default_factory=dict)
    source_versions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def bounded(self):
        from pyproj import Geod
        geod, work = Geod(ellps="WGS84"), 0
        for zone in self.zones:
            if zone.geometry["type"] == "Polygon":
                for ring in zone.geometry["coordinates"]:
                    for a, b in zip(ring, ring[1:]):
                        work += 1 + int(abs(geod.inv(*a, *b)[2]) // 250)
                        if work > 50000:
                            raise ValueError("Polygon screening exceeds bounded geometric work limit; narrow the area or split the request")
        return self


def geodesic_distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    from pyproj import Geod
    return abs(float(Geod(ellps="WGS84").inv(a[0], a[1], b[0], b[1])[2]))


def _polygon_relation(position: Position, rings: list, precision: float) -> tuple[bool | None, bool, str | None]:
    """Local geodesic polygon screening, bounded to 100 km from the query.

    Edges are densified along the ellipsoid and projected into query-centred
    azimuthal equidistant coordinates. A 2 m numerical envelope is added to the
    input precision. Complex/self-intersecting rings are explicitly unsupported.
    """
    from pyproj import Geod, Transformer
    geod = Geod(ellps="WGS84")
    transformer = Transformer.from_crs("EPSG:4326", f"+proj=aeqd +lat_0={position.latitude} +lon_0={position.longitude} +datum=WGS84 +units=m", always_xy=True)
    near_boundary, inside_rings = False, []
    for ring in rings:
        vertices = []
        for a, b in zip(ring, ring[1:]):
            if max(geodesic_distance_m((position.longitude, position.latitude), tuple(a)), geodesic_distance_m((position.longitude, position.latitude), tuple(b))) > 100000:
                return None, False, "Polygon exceeds the documented 100 km local screening envelope"
            distance = geodesic_distance_m(tuple(a), tuple(b))
            points = [tuple(a)] + (geod.npts(*a, *b, int(distance // 250)) if distance >= 250 else [])
            vertices.extend(transformer.transform(*point) for point in points)
        vertices.append(vertices[0])
        # Reject malformed polygons instead of making a favourable finding from
        # an ambiguous winding. Boundary contact is kept as uncertainty below.
        def orientation(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        # Original projected vertices suffice to detect crossing rings without
        # quadratic work over the densified geometric approximation.
        original = [transformer.transform(*point) for point in ring]
        for i in range(len(original) - 1):
            for j in range(i + 2, len(original) - 1):
                if i == 0 and j == len(original) - 2:
                    continue
                a, b, c, d = original[i], original[i + 1], original[j], original[j + 1]
                if orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0:
                    return None, False, "Self-intersecting polygon requires correction at its source"
        if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(original, original[1:]))) < 0.001:
            return None, False, "Degenerate polygon has no reliable interior"
        inside = False
        for a, b in zip(vertices, vertices[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            t = max(0, min(1, -(a[0] * dx + a[1] * dy) / (dx * dx + dy * dy))) if dx * dx + dy * dy else 0
            if math.hypot(a[0] + t * dx, a[1] + t * dy) <= precision + position.horizontal_uncertainty_m + 2:
                near_boundary = True
            if (a[1] > 0) != (b[1] > 0) and 0 < a[0] + (b[0] - a[0]) * (-a[1]) / (b[1] - a[1]):
                inside = not inside
        inside_rings.append(inside)
    return inside_rings[0] and not any(inside_rings[1:]), near_boundary, None


def _vertical_relation(point: Position, zone: Zone) -> str:
    if point.altitude_m is None or point.vertical_uncertainty_m is None or point.vertical_reference in {"Unknown", "FL"} or zone.vertical_reference in {"Unknown", "FL"}:
        return "Unknown"
    altitude = point.altitude_m
    if point.vertical_reference != zone.vertical_reference:
        if point.terrain_elevation_amsl_m is None or not point.terrain_evidence_ref or point.terrain_uncertainty_m is None:
            return "Unknown"
        altitude += point.terrain_elevation_amsl_m if point.vertical_reference == "AGL" else -point.terrain_elevation_amsl_m
    uncertainty = point.vertical_uncertainty_m + (point.terrain_uncertainty_m or 0 if point.vertical_reference != zone.vertical_reference else 0)
    low, high = altitude - uncertainty, altitude + uncertainty
    if zone.lower_m is None or zone.upper_m is None:
        return "Unknown"
    if high < zone.lower_m or low > zone.upper_m:
        return "Outside"
    return "Inside" if low >= zone.lower_m and high <= zone.upper_m else "Boundary Uncertainty"


def screen_site(payload: dict | SiteScreenRequest) -> dict:
    request = payload if isinstance(payload, SiteScreenRequest) else SiteScreenRequest.model_validate(payload)
    now, findings, intersects = utc(request.at), [], []
    for topic in ("geographical_zones", "airspace", "terrain", "population", "obstacles", "site_access", "emergency_arrangements"):
        if not request.coverage.get(topic):
            findings.append(f"Missing authoritative coverage or reviewed evidence for {topic}")
    for zone in request.zones:
        if not zone.valid_from <= now < zone.valid_until:
            findings.append(f"{zone.id}: source is not applicable at the requested time")
            continue
        if zone.geometry["type"] == "Circle":
            distance = geodesic_distance_m((request.point.longitude, request.point.latitude), tuple(zone.geometry["coordinates"]))
            inside = distance <= zone.geometry["radius_m"]
            uncertain = abs(distance - zone.geometry["radius_m"]) <= zone.source_precision_m + request.point.horizontal_uncertainty_m
            reason = None
        else:
            inside, uncertain, reason = _polygon_relation(request.point, zone.geometry["coordinates"], zone.source_precision_m)
        if reason:
            findings.append(f"{zone.id}: {reason}")
        vertical = _vertical_relation(request.point, zone)
        if inside is not False or uncertain:
            relation = "Unresolved" if inside is None or vertical == "Unknown" else "Potential Intersection" if uncertain or vertical == "Boundary Uncertainty" else "Intersection" if vertical == "Inside" else "Outside Vertical Bounds"
            intersects.append({"zone_id": zone.id, "relation": relation, "vertical_relation": vertical, "horizontal_boundary_uncertain": uncertain,
                               "restriction": zone.restriction, "source_anchor": zone.source_anchor, "source_version": zone.source_version, "permitted_purpose": zone.purpose})
            if relation != "Outside Vertical Bounds":
                findings.append(f"{zone.id}: {relation}; review restriction and any required permission")
        if zone.purpose != "Operationally Accepted":
            findings.append(f"{zone.id}: research data cannot establish operational feasibility")
    if not request.zones:
        findings.append("No authoritative zone geometries supplied; an empty overlay does not establish absence of restrictions")
    return {**trace(request, "site-screen"), "status": "Requires Review" if intersects else "Incomplete" if findings else "Screened; Requires Domain Review",
            "findings": findings, "zone_results": intersects, "distance_method": "WGS84 ellipsoid / PROJ geodesic; local polygon screening within 100 km",
            "limitation": "Candidate-site screening only; no route approval, legal feasibility, separation service or obstacle clearance determination", "source_versions": sorted(set(request.source_versions + [z.source_version for z in request.zones]))}


class TelemetryEvent(Contract):
    event_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    aircraft_id: str = Field(min_length=1)
    mission_id: str = Field(min_length=1)
    observed_at: AwareDatetime
    received_at: AwareDatetime
    sequence: int | None = Field(default=None, ge=0)
    position: Position
    mode: Literal["Live", "Historical Replay"]
    source_version: str = Field(min_length=1)


class MonitoringPolicy(Contract):
    stale_after_seconds: int = Field(gt=0)
    source_ref: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    operational_use_accepted: bool


class TelemetryRequest(Contract):
    actor_id: str = Field(min_length=1)
    now: AwareDatetime
    mode: Literal["Live", "Historical Replay"]
    policy: MonitoringPolicy | None = None
    events: list[TelemetryEvent] = Field(default_factory=list, max_length=10000)
    previous_events: list[TelemetryEvent] = Field(default_factory=list, max_length=10000)
    expected_aircraft_ids: list[str] = Field(default_factory=list)
    source_versions: list[str] = Field(default_factory=list)


def evaluate_telemetry(payload: dict | TelemetryRequest) -> dict:
    request = payload if isinstance(payload, TelemetryRequest) else TelemetryRequest.model_validate(payload)
    now = utc(request.now)
    records, seen, latest, alerts, observations = [], {}, {}, [], []
    def event_digest(event):
        # Transport receipt time changes on redelivery; source observation
        # identity and content, rather than receipt time, define a duplicate.
        content = event.model_dump(mode="json")
        content.pop("received_at")
        return snapshot_hash(content)
    # Never allow a prior replay record to become the latest live position.
    for event in request.previous_events:
        if event.mode != request.mode:
            continue
        seen[(event.source_id, event.event_id)] = event_digest(event)
        key = event.aircraft_id
        if utc(event.observed_at) <= utc(event.received_at) <= now and (key not in latest or utc(event.observed_at) > utc(latest[key].observed_at)):
            latest[key] = event
    for event in request.events:
        key, digest = (event.source_id, event.event_id), event_digest(event)
        state = "Accepted"
        if event.mode != request.mode:
            state = "Quarantined: live and replay stores must be separate"
        elif key in seen:
            state = "Duplicate" if seen[key] == digest else "Quarantined: contradictory reuse of source event identifier"
        elif not utc(event.observed_at) <= utc(event.received_at) <= now:
            state = "Quarantined: inconsistent or future timestamps"
        elif event.aircraft_id in latest and utc(event.observed_at) < utc(latest[event.aircraft_id].observed_at):
            state = "Archived Out of Order"
        elif event.aircraft_id in latest and utc(event.observed_at) == utc(latest[event.aircraft_id].observed_at):
            state = "Quarantined: contradictory observations at the same timestamp"
        elif event.aircraft_id in latest and event.source_id == latest[event.aircraft_id].source_id and event.sequence is not None and latest[event.aircraft_id].sequence is not None and event.sequence <= latest[event.aircraft_id].sequence:
            state = "Quarantined: non-increasing source sequence"
        if state in {"Accepted", "Archived Out of Order"}:
            seen[key] = digest
            records.append(event.model_dump(mode="json"))
        if state == "Accepted":
            latest[event.aircraft_id] = event
        observations.append({"source_id": event.source_id, "event_id": event.event_id, "state": state})
        if state.startswith("Quarantined"):
            alerts.append({"type": "Telemetry Integrity", "aircraft_id": event.aircraft_id, "evidence_event_id": event.event_id, "message": state})
    for aircraft_id in sorted(set(request.expected_aircraft_ids) | set(latest)):
        event = latest.get(aircraft_id)
        if event is None:
            alerts.append({"type": "Telemetry Missing", "aircraft_id": aircraft_id, "message": "No verified position available"})
            continue
        age = (now - utc(event.observed_at)).total_seconds()
        if request.policy is not None and age > request.policy.stale_after_seconds:
            alerts.append({"type": "Telemetry Loss", "aircraft_id": aircraft_id, "evidence_event_id": event.event_id, "age_seconds": age, "policy_ref": request.policy.source_ref})
    policy_missing = request.policy is None
    return {**trace(request, "telemetry"), "status": "Missing Monitoring Policy" if policy_missing else "Degraded" if alerts else "Observed",
            "mode": request.mode, "observations": observations, "accepted_records": records, "alerts": alerts,
            "latest_verified": [{**event.model_dump(mode="json"), "age_seconds": (now - utc(event.observed_at)).total_seconds(),
                                  "freshness": "Unknown" if policy_missing else "Stale" if (now - utc(event.observed_at)).total_seconds() > request.policy.stale_after_seconds else "Within Configured Freshness", "predicted": False} for event in latest.values()],
            "operational_use": bool(request.policy and request.policy.operational_use_accepted),
            "limitation": "Authorised cooperative telemetry only; coverage is incomplete and proximity is not certified Detect and Avoid; no position is extrapolated"}


class Procedure(Contract):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    incident_types: list[str] = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    status: Literal["Draft", "Approved", "Superseded", "Suspended"]
    approved_by: str | None = None
    source_ref: str = Field(min_length=1)
    valid_until: AwareDatetime
    steps: list[str] = Field(min_length=1)


class IncidentRequest(Contract):
    actor_id: str = Field(min_length=1)
    incident_type: str = Field(min_length=1)
    aircraft_configuration_id: str = Field(min_length=1)
    assigned_owner_id: str | None = None
    created_at: AwareDatetime
    now: AwareDatetime
    acknowledged_at: AwareDatetime | None = None
    escalation_after_seconds: int | None = Field(default=None, gt=0)
    escalation_policy_ref: str | None = None
    procedure: Procedure | None = None
    source_versions: list[str] = Field(default_factory=list)


def incident_checklist(payload: dict | IncidentRequest) -> dict:
    request = payload if isinstance(payload, IncidentRequest) else IncidentRequest.model_validate(payload)
    findings, steps = [], []
    now, created = utc(request.now), utc(request.created_at)
    if created > now:
        raise ValueError("Incident creation cannot be after evaluation time")
    if request.acknowledged_at and not created <= utc(request.acknowledged_at) <= now:
        raise ValueError("Acknowledgement must be within the recorded incident timeline")
    if not request.assigned_owner_id:
        findings.append("Assign an accountable incident owner")
    procedure = request.procedure
    if procedure is None or procedure.status != "Approved" or not procedure.approved_by or procedure.configuration_id != request.aircraft_configuration_id or request.incident_type not in procedure.incident_types or utc(procedure.valid_until) <= now:
        findings.append("No current approved procedure matches this incident type and aircraft configuration; escalate to the accountable person")
    else:
        steps = [{"order": index + 1, "text": text, "status": "Pending", "procedure_id": procedure.id, "procedure_version": procedure.version, "source_ref": procedure.source_ref} for index, text in enumerate(procedure.steps)]
    if request.escalation_after_seconds is None or not request.escalation_policy_ref:
        escalation = "Missing Approved Escalation Policy"
        findings.append("Escalation timing cannot be inferred; record the approved operator policy")
    elif request.acknowledged_at:
        escalation = "Acknowledged"
    elif (now - created).total_seconds() >= request.escalation_after_seconds:
        escalation = "Escalation Required"
    else:
        escalation = "Awaiting Acknowledgement"
    return {**trace(request, "incident"), "status": "Requires Accountable Action" if findings or escalation == "Escalation Required" else "Procedure Available",
            "findings": findings, "checklist": steps, "escalation": escalation, "owner": request.assigned_owner_id,
            "notification": {"state": "Not Sent", "external_contacts": "No automatic external correspondence"},
            "flight_command_capability": False, "reportability": "Requires jurisdiction-specific source-backed assessment"}


class FinancialInput(Contract):
    value: Decimal = Field(ge=0)
    provenance: Literal["Documented Fact", "Customer Provided", "Analyst Assumption"]
    evidence_ref: str = Field(min_length=1)
    as_of: str = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def valid(self):
        from datetime import date
        date.fromisoformat(self.as_of)
        if not self.value.is_finite():
            raise ValueError("Financial inputs must be finite")
        return self


class EconomicsRequest(Contract):
    actor_id: str = Field(min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    period: str = Field(min_length=1)
    planned_missions: FinancialInput | None = None
    revenue_per_mission: FinancialInput | None = None
    variable_cost_per_mission: FinancialInput | None = None
    fixed_cost: FinancialInput | None = None
    capacity_missions: FinancialInput | None = None
    regulatory_blockers: list[str] = Field(default_factory=list)
    source_versions: list[str] = Field(default_factory=list)


def calculate_economics(payload: dict | EconomicsRequest) -> dict:
    request = payload if isinstance(payload, EconomicsRequest) else EconomicsRequest.model_validate(payload)
    fields = ("planned_missions", "revenue_per_mission", "variable_cost_per_mission", "fixed_cost", "capacity_missions")
    missing = [f for f in fields if getattr(request, f) is None]
    values = {name: None for name in ("total_revenue", "total_cost", "cost_per_mission", "contribution_before_fixed_cost", "period_contribution", "resource_utilisation", "break_even_missions")}
    if not missing:
        count, revenue, variable, fixed, capacity = (getattr(request, f).value for f in fields)
        values.update(total_revenue=str(count * revenue), total_cost=str(fixed + count * variable), contribution_before_fixed_cost=str(count * (revenue - variable)), period_contribution=str(count * (revenue - variable) - fixed),
                      cost_per_mission=str(variable + fixed / count) if count > 0 else None,
                      resource_utilisation=str(count / capacity) if capacity > 0 else None,
                      break_even_missions=str(fixed / (revenue - variable)) if revenue > variable else None)
    return {**trace(request, "economics"), "status": "Incomplete" if missing else "Calculated Forecast", "missing_inputs": missing, "currency": request.currency, "period": request.period,
            "values": values, "formulas": {"total_revenue": "planned_missions * revenue_per_mission", "total_cost": "fixed_cost + planned_missions * variable_cost_per_mission", "cost_per_mission": "variable_cost_per_mission + fixed_cost / planned_missions", "period_contribution": "planned_missions * (revenue_per_mission - variable_cost_per_mission) - fixed_cost", "resource_utilisation": "planned_missions / capacity_missions", "break_even_missions": "fixed_cost / (revenue_per_mission - variable_cost_per_mission), only if unit margin > 0"},
            "units": {"money": request.currency, "volume": "missions per stated period", "resource_utilisation": "ratio"},
            "regulatory_blockers": request.regulatory_blockers, "stage_gate": "Blocked" if request.regulatory_blockers else "Requires Operational and Commercial Review", "forecast": True,
            "uncertainty": "Conditional on supplied inputs; no probability distribution or demand evidence inferred", "input_provenance": {name: getattr(request, name).model_dump(mode="json") if getattr(request, name) else None for name in fields}}


def connector_catalog() -> list[dict]:
    """Public capability declarations, never fabricated connection results."""
    return [
        {"id": "authoritative-regulatory-http", "name": "Official regulatory documents", "capabilities": ["Read-only source ingestion"], "status": "Requires Real Integration Test", "authentication": "Public source-specific access", "geography": "Source-specific", "licence": "Review source-specific reuse terms", "permitted_purpose": "Regulatory research", "freshness_expectation": "Recorded per source", "schema_version": "1", "live_test": None},
        {"id": "operator-telemetry-import", "name": "Authorised operator telemetry import", "capabilities": ["Read-only event ingestion", "Historical replay in separate mode"], "status": "Not Connected", "authentication": "Tenant-authenticated manual import", "geography": "Operator-declared", "licence": "Operator consent and data-processing terms required", "permitted_purpose": "Configured operator monitoring after acceptance", "freshness_expectation": "Approved monitoring policy required", "schema_version": "TelemetryRequest/1", "live_test": None},
        {"id": "eurocontrol-ead-basic", "name": "EUROCONTROL EAD Basic", "capabilities": ["Research-only access boundary"], "status": "Not Connected", "authentication": "EUROCONTROL account and terms", "geography": "Provider coverage", "licence": "Provider terms; no assumed redistribution", "permitted_purpose": "Research Only", "operational_use_allowed": False, "freshness_expectation": "Not accepted for operations", "schema_version": None, "live_test": None, "source": "https://www.eurocontrol.int/service/european-ais-database"},
        {"id": "u-space-provider", "name": "Provider-specific U-space services", "capabilities": ["Typed permission response records"], "status": "Not Connected", "authentication": "Provider contract and scoped credentials required", "geography": "Designated coverage must be verified", "licence": "Provider-specific", "permitted_purpose": "Not Operationally Validated", "freshness_expectation": "Provider contract required", "schema_version": "Permission/1", "live_test": None},
    ]
