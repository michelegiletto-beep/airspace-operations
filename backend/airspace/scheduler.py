"""Bounded CP-SAT schedule proposals and an independently implemented verifier.

This module never dispatches an aircraft or issues a permission. All inputs are
operator records, not facts inferred by the solver. Time intervals are half-open.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import product
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

RULE_VERSION = "schedule-1.0.0"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A UTC offset is required; ambiguous local times are not accepted")
    if value.microsecond:
        raise ValueError("Schedule timestamps require whole-second precision")
    return value.astimezone(timezone.utc)


def stamp(value: datetime) -> str:
    return utc(value).isoformat().replace("+00:00", "Z")


def snapshot_hash(value: dict | BaseModel) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class Window(Contract):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def valid(self):
        self.start, self.end = utc(self.start), utc(self.end)
        if self.end <= self.start:
            raise ValueError("An availability interval must have positive duration")
        return self


class Permission(Contract):
    id: str = Field(min_length=1)
    kind: Literal["operating_basis", "site_airspace", "u_space", "safety_review", "internal_dispatch", "pilot_acknowledgement"]
    issuer_type: Literal["Competent Authority", "Site or Airspace Authority", "U-space Provider", "Accountable Reviewer", "Pilot", "Operator Declaration", "LUC Holder"]
    status: Literal["Draft", "Missing Evidence", "Under Review", "Submitted", "Approved", "Rejected", "Expired", "Suspended", "Superseded"]
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    evidence_ref: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    route_version: str = Field(min_length=1)
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def valid(self):
        self.valid_from, self.valid_until = utc(self.valid_from), utc(self.valid_until)
        if self.valid_until <= self.valid_from:
            raise ValueError("Permission validity must be positive")
        allowed = {
            "operating_basis": {"Competent Authority", "Operator Declaration", "LUC Holder"},
            "site_airspace": {"Site or Airspace Authority"},
            "u_space": {"U-space Provider"},
            "safety_review": {"Accountable Reviewer"},
            "internal_dispatch": {"Accountable Reviewer"},
            "pilot_acknowledgement": {"Pilot"},
        }
        if self.issuer_type not in allowed[self.kind]:
            raise ValueError("This issuer cannot issue this kind of permission or acknowledgement")
        return self


class FeedSnapshot(Contract):
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    observed_at: AwareDatetime
    valid_until: AwareDatetime
    suitable: bool
    operational_use_accepted: bool

    @model_validator(mode="after")
    def valid(self):
        self.observed_at, self.valid_until = utc(self.observed_at), utc(self.valid_until)
        if self.valid_until <= self.observed_at:
            raise ValueError("A feed snapshot needs a positive validity interval")
        return self


class Mission(Contract):
    id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    record_kind: Literal["Proposed Operation"] = "Proposed Operation"
    window: Window
    duration_seconds: int = Field(gt=0, le=86400)
    payload_kg: float = Field(ge=0)
    configuration_id: str = Field(min_length=1)
    route_version: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    required_qualifications: list[str] = Field(min_length=1)
    permission_requirements_reviewed: bool = False
    required_permission_kinds: list[str] = Field(default_factory=list)
    permissions: list[Permission] = Field(default_factory=list)
    route_approved: bool = False
    weather: FeedSnapshot | None = None
    airspace: FeedSnapshot | None = None
    u_space_required: bool | None = None
    provider: FeedSnapshot | None = None
    depends_on: list[str] = Field(default_factory=list)
    locked_start: AwareDatetime | None = None
    locked_aircraft_id: str | None = None
    locked_person_id: str | None = None

    @model_validator(mode="after")
    def valid(self):
        if self.locked_start is not None:
            self.locked_start = utc(self.locked_start)
        return self


class Aircraft(Contract):
    id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    configuration_id: str = Field(min_length=1)
    serviceable: bool
    payload_capacity_kg: float = Field(ge=0)
    availability: list[Window] = Field(min_length=1, max_length=50)
    maintenance_due: AwareDatetime
    usable_flight_seconds: int = Field(gt=0)
    turnaround_seconds: int = Field(ge=0)
    readiness_evidence_ref: str = Field(min_length=1)
    battery_evidence_ref: str = Field(min_length=1)
    policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        self.maintenance_due = utc(self.maintenance_due)
        return self


class Person(Contract):
    id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    availability: list[Window] = Field(min_length=1, max_length=50)
    qualifications: dict[str, AwareDatetime]
    max_duty_seconds: int = Field(gt=0)
    duty_already_seconds: int = Field(ge=0)
    policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        self.qualifications = {key: utc(value) for key, value in self.qualifications.items()}
        return self


class Site(Contract):
    id: str = Field(min_length=1)
    concurrent_capacity: int = Field(gt=0, le=1000)
    availability: list[Window] = Field(min_length=1, max_length=50)
    capacity_evidence_ref: str = Field(min_length=1)


class ScheduleRequest(Contract):
    actor_id: str = Field(min_length=1)
    input_revision: int = Field(ge=1)
    local_timezone: str
    missions: list[Mission] = Field(max_length=100)
    aircraft: list[Aircraft] = Field(max_length=100)
    personnel: list[Person] = Field(max_length=100)
    sites: list[Site] = Field(max_length=100)
    max_solver_seconds: float = Field(default=5, gt=0, le=30)

    @model_validator(mode="after")
    def valid(self):
        try:
            ZoneInfo(self.local_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown IANA local timezone")
        for records in (self.missions, self.aircraft, self.personnel, self.sites):
            ids = [r.id for r in records]
            if len(set(ids)) != len(ids):
                raise ValueError("Duplicate resource or mission identifiers are not permitted")
        mission_ids = {m.id for m in self.missions}
        for mission in self.missions:
            if any(dependency not in mission_ids or dependency == mission.id for dependency in mission.depends_on):
                raise ValueError("Mission dependency must identify a different mission in this request")
        return self


def incomplete_inputs(request: ScheduleRequest) -> list[str]:
    missing = []
    if request.missions and not request.aircraft:
        missing.append("No aircraft readiness records")
    if request.missions and not request.personnel:
        missing.append("No qualified personnel records")
    sites = {s.id for s in request.sites}
    for mission in request.missions:
        label = mission.id
        if not mission.permission_requirements_reviewed:
            missing.append(f"{label}: applicability and required permissions have not been reviewed")
        if not mission.required_permission_kinds:
            missing.append(f"{label}: required operating-basis instruments have not been specified")
        if "operating_basis" not in mission.required_permission_kinds:
            missing.append(f"{label}: an applicable legal operating basis must be recorded")
        if mission.u_space_required is None:
            missing.append(f"{label}: U-space applicability is unknown")
        if mission.u_space_required and "u_space" not in mission.required_permission_kinds:
            missing.append(f"{label}: required U-space permission is absent from applicability review")
        for kind in mission.required_permission_kinds:
            if not any(p.kind == kind for p in mission.permissions):
                missing.append(f"{label}: missing {kind} instrument")
        if not mission.route_approved:
            missing.append(f"{label}: route version is not internally approved")
        for name in ("weather", "airspace") + (("provider",) if mission.u_space_required else ()):
            if getattr(mission, name) is None:
                missing.append(f"{label}: missing {name} evidence")
        if mission.site_id not in sites:
            missing.append(f"{label}: missing site capacity and access window")
    return missing


def _admissible_bounds(mission: Mission) -> tuple[datetime, datetime] | None:
    lower, upper = mission.window.start, mission.window.end
    for kind in mission.required_permission_kinds:
        # Multiple instruments of one kind are alternative scopes; the conservative
        # implementation currently requires exactly one unambiguous applicable record.
        matching = [p for p in mission.permissions if p.kind == kind and p.status == "Approved" and p.configuration_id == mission.configuration_id and p.route_version == mission.route_version]
        if len(matching) != 1:
            return None
        lower, upper = max(lower, matching[0].valid_from), min(upper, matching[0].valid_until)
    for feed in (mission.weather, mission.airspace, mission.provider if mission.u_space_required else None):
        if feed is None:
            continue
        if not feed.suitable or not feed.operational_use_accepted:
            return None
        lower, upper = max(lower, feed.observed_at), min(upper, feed.valid_until)
    return lower, upper


def solve_schedule(payload: dict | ScheduleRequest) -> dict:
    request = payload if isinstance(payload, ScheduleRequest) else ScheduleRequest.model_validate(payload)
    result = {"rule_version": RULE_VERSION, "input_snapshot": snapshot_hash(request), "input_revision": request.input_revision,
              "actor_id": request.actor_id, "created_at": stamp(datetime.now(timezone.utc).replace(microsecond=0)),
              "assignments": [], "status": "INCOMPLETE", "findings": incomplete_inputs(request),
              "objective": "Minimise sum of proposed start offsets; hard constraints are never penalised away",
              "operational_status": "Advisory proposal; requires independent verification and accountable internal review"}
    if result["findings"]:
        return result
    result["source_versions"] = sorted({f"{p.id}@{p.revision}" for m in request.missions for p in m.permissions} | {f"{f.source_id}@{f.source_version}" for m in request.missions for f in (m.weather, m.airspace, m.provider) if f})
    result["model_version"] = None
    if not request.missions:
        result.update(status="EMPTY", findings=["No proposed operations supplied"])
        return result
    from ortools.sat.python import cp_model
    import ortools

    result["solver"] = {"name": "OR-Tools CP-SAT", "version": ortools.__version__, "time_limit_seconds": request.max_solver_seconds, "workers": 1, "random_seed": 0}
    model = cp_model.CpModel()
    epoch = min(m.window.start for m in request.missions)
    horizon = int((max(m.window.end for m in request.missions) - epoch).total_seconds())
    if horizon > 366 * 86400:
        result.update(status="INCOMPLETE", findings=["Scheduling horizon exceeds the bounded one-year limit"])
        return result
    offset = lambda d: int((utc(d) - epoch).total_seconds())
    aircraft_intervals, person_intervals, site_intervals = defaultdict(list), defaultdict(list), defaultdict(list)
    aircraft_energy, person_duty = defaultdict(list), defaultdict(list)
    choices, starts, ends = {}, {}, {}
    sites = {s.id: s for s in request.sites}
    combination_count, examined_windows = 0, 0
    for mission in request.missions:
        start = starts[mission.id] = model.new_int_var(0, horizon, f"start:{mission.id}")
        end = ends[mission.id] = model.new_int_var(0, horizon, f"end:{mission.id}")
        model.add(end == start + mission.duration_seconds)
        if mission.locked_start:
            model.add(start == offset(mission.locked_start))
        bounds = _admissible_bounds(mission)
        candidates = []
        if bounds:
            for aircraft, person in product(request.aircraft, request.personnel):
                if not aircraft.serviceable or aircraft.configuration_id != mission.configuration_id or aircraft.payload_capacity_kg < mission.payload_kg:
                    continue
                if mission.locked_aircraft_id and mission.locked_aircraft_id != aircraft.id:
                    continue
                if mission.locked_person_id and mission.locked_person_id != person.id:
                    continue
                if any(q not in person.qualifications for q in mission.required_qualifications):
                    continue
                for aw, pw, sw in product(aircraft.availability, person.availability, sites[mission.site_id].availability):
                    examined_windows += 1
                    if examined_windows > 100000:
                        result.update(status="INCOMPLETE", findings=["Window search exceeds bounded execution limit; reduce availability windows or resource pool"])
                        return result
                    lower = max(bounds[0], aw.start, pw.start, sw.start)
                    upper = min(bounds[1], aw.end - timedelta(seconds=aircraft.turnaround_seconds), pw.end, sw.end, utc(aircraft.maintenance_due), *(utc(person.qualifications[q]) for q in mission.required_qualifications))
                    if (upper - lower).total_seconds() < mission.duration_seconds:
                        continue
                    combination_count += 1
                    if combination_count > 20000:
                        result.update(status="INCOMPLETE", findings=["Resource-window combinations exceed bounded execution limit; reduce the planning horizon or resource pool"])
                        return result
                    present = model.new_bool_var(f"choice:{combination_count}")
                    model.add(start >= offset(lower)).only_enforce_if(present)
                    model.add(end <= offset(upper)).only_enforce_if(present)
                    ai = model.new_optional_fixed_size_interval_var(start, mission.duration_seconds + aircraft.turnaround_seconds, present, f"aircraft:{combination_count}")
                    pi = model.new_optional_fixed_size_interval_var(start, mission.duration_seconds, present, f"person:{combination_count}")
                    si = model.new_optional_fixed_size_interval_var(start, mission.duration_seconds, present, f"site:{combination_count}")
                    aircraft_intervals[aircraft.id].append(ai)
                    person_intervals[person.id].append(pi)
                    site_intervals[mission.site_id].append(si)
                    aircraft_energy[aircraft.id].append(present * mission.duration_seconds)
                    person_duty[person.id].append(present * mission.duration_seconds)
                    candidates.append((present, aircraft.id, person.id))
        choices[mission.id] = candidates
        if not candidates:
            result.update(status="INFEASIBLE", findings=[f"{mission.id}: no admissible assignment satisfies permission scope/validity, feed suitability, aircraft readiness, qualifications, capacity windows and locks"])
            return result
        model.add_exactly_one([c[0] for c in candidates])
    for intervals in aircraft_intervals.values():
        model.add_no_overlap(intervals)
    for intervals in person_intervals.values():
        model.add_no_overlap(intervals)
    for site in request.sites:
        if site_intervals[site.id]:
            model.add_cumulative(site_intervals[site.id], [1] * len(site_intervals[site.id]), site.concurrent_capacity)
    for aircraft in request.aircraft:
        model.add(sum(aircraft_energy[aircraft.id]) <= aircraft.usable_flight_seconds)
    for person in request.personnel:
        model.add(sum(person_duty[person.id]) + person.duty_already_seconds <= person.max_duty_seconds)
        # A planning request is one duty episode. Gaps between assigned duties
        # count toward its span; rest/reset policies require separate episodes.
        first = model.new_int_var(0, horizon, f"duty-first:{person.id}")
        last = model.new_int_var(0, horizon, f"duty-last:{person.id}")
        model.add(last - first + person.duty_already_seconds <= person.max_duty_seconds)
        for mission in request.missions:
            for present, _, person_id in choices[mission.id]:
                if person_id == person.id:
                    model.add(starts[mission.id] >= first).only_enforce_if(present)
                    model.add(ends[mission.id] <= last).only_enforce_if(present)
    for mission in request.missions:
        for dependency in mission.depends_on:
            model.add(starts[mission.id] >= ends[dependency])
    model.minimize(sum(starts.values()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = request.max_solver_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    result.update(status=solver.status_name(status), wall_time_seconds=solver.wall_time,
                  branches=solver.num_branches, conflicts=solver.num_conflicts)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["objective_value"] = solver.objective_value
        result["objective_bound"] = solver.best_objective_bound
        for mission in request.missions:
            chosen = next(c for c in choices[mission.id] if solver.boolean_value(c[0]))
            result["assignments"].append({"mission_id": mission.id, "mission_revision": mission.revision, "aircraft_id": chosen[1], "person_id": chosen[2], "site_id": mission.site_id,
                                          "start": stamp(epoch + timedelta(seconds=solver.value(starts[mission.id]))), "end": stamp(epoch + timedelta(seconds=solver.value(ends[mission.id])))})
        verification = verify_schedule(request, result)
        result["verification"] = verification
        if not verification["valid"]:
            result.update(status="VERIFICATION_FAILED", assignments=[])
    elif status == cp_model.INFEASIBLE:
        result["findings"] = ["No assignment meets all hard constraints; review combined availability, cumulative battery budget, duty limits, capacity, dependencies and locked assignments"]
    elif status == cp_model.UNKNOWN:
        result["findings"] = ["Search ended without a feasible assignment or proof of infeasibility; this is not evidence that a schedule exists"]
    return result


def verify_schedule(payload: dict | ScheduleRequest, proposed: dict) -> dict:
    """Recalculate assignment constraints without importing or trusting CP-SAT.

    This intentionally does not call the solver's bound/candidate construction.
    The exact input digest and revisions bind the proposal to its evidence.
    """
    request = payload if isinstance(payload, ScheduleRequest) else ScheduleRequest.model_validate(payload)
    errors = list(incomplete_inputs(request))
    if proposed.get("input_snapshot") != snapshot_hash(request):
        errors.append("Input snapshot changed; regenerate and re-review the proposal")
    missions, aircraft, persons, sites = ({r.id: r for r in collection} for collection in (request.missions, request.aircraft, request.personnel, request.sites))
    assignments = proposed.get("assignments", [])
    ids = [a.get("mission_id") for a in assignments]
    if set(ids) != set(missions) or len(ids) != len(set(ids)):
        errors.append("Every proposed operation must appear exactly once")
    usage, duty, intervals, site_events, by_mission = defaultdict(int), defaultdict(int), defaultdict(list), defaultdict(list), {}
    for assignment in assignments:
        label = assignment.get("mission_id")
        mission, craft, person, site = missions.get(label), aircraft.get(assignment.get("aircraft_id")), persons.get(assignment.get("person_id")), sites.get(assignment.get("site_id"))
        if not all((mission, craft, person, site)):
            errors.append(f"{label}: unknown mission or resource")
            continue
        try:
            start, end = utc(datetime.fromisoformat(assignment["start"].replace("Z", "+00:00"))), utc(datetime.fromisoformat(assignment["end"].replace("Z", "+00:00")))
        except (KeyError, ValueError, TypeError):
            errors.append(f"{label}: invalid offset-aware timestamps")
            continue
        by_mission[label] = (start, end)
        duration = (end - start).total_seconds()
        if duration != mission.duration_seconds:
            errors.append(f"{label}: duration mismatch")
        if assignment.get("mission_revision") != mission.revision:
            errors.append(f"{label}: stale mission revision")
        if not mission.window.start <= start < end <= mission.window.end:
            errors.append(f"{label}: outside mission window")
        if mission.site_id != site.id:
            errors.append(f"{label}: wrong site")
        if mission.locked_start and start != mission.locked_start or mission.locked_aircraft_id and craft.id != mission.locked_aircraft_id or mission.locked_person_id and person.id != mission.locked_person_id:
            errors.append(f"{label}: manually locked assignment changed")
        if not craft.serviceable or craft.configuration_id != mission.configuration_id or craft.payload_capacity_kg < mission.payload_kg:
            errors.append(f"{label}: aircraft readiness/configuration/payload mismatch")
        if utc(craft.maintenance_due) < end:
            errors.append(f"{label}: maintenance due before operation completion")
        for resource, extra in ((craft, craft.turnaround_seconds), (person, 0), (site, 0)):
            if not any(w.start <= start and end + timedelta(seconds=extra) <= w.end for w in resource.availability):
                errors.append(f"{label}: resource {resource.id} outside availability including turnaround")
        for qualification in mission.required_qualifications:
            if qualification not in person.qualifications or utc(person.qualifications[qualification]) < end:
                errors.append(f"{label}: qualification {qualification} missing or expires")
        for kind in mission.required_permission_kinds:
            applicable = [p for p in mission.permissions if p.kind == kind and p.status == "Approved" and p.configuration_id == mission.configuration_id and p.route_version == mission.route_version]
            if len(applicable) != 1 or not applicable[0].valid_from <= start < end <= applicable[0].valid_until:
                errors.append(f"{label}: invalid, ambiguous, expired or out-of-scope {kind}")
        for name in ("weather", "airspace") + (("provider",) if mission.u_space_required else ()):
            feed = getattr(mission, name)
            if feed is None or not feed.suitable or not feed.operational_use_accepted or not feed.observed_at <= start < end <= feed.valid_until:
                errors.append(f"{label}: missing, stale or unsuitable {name}")
        usage[craft.id] += duration
        duty[person.id] += duration
        intervals[("aircraft", craft.id)].append((start, end + timedelta(seconds=craft.turnaround_seconds), label))
        intervals[("person", person.id)].append((start, end, label))
        site_events[site.id] += [(start, 1), (end, -1)]
    for resource, ranges in intervals.items():
        ordered = sorted(ranges)
        for previous, following in zip(ordered, ordered[1:]):
            if following[0] < previous[1]:
                errors.append(f"Overlapping reservations for {resource[0]} {resource[1]}")
    for craft in request.aircraft:
        if usage[craft.id] > craft.usable_flight_seconds:
            errors.append(f"{craft.id}: battery flight-time budget exceeded; charging must be evidenced in a new readiness snapshot")
    for person in request.personnel:
        if duty[person.id] + person.duty_already_seconds > person.max_duty_seconds:
            errors.append(f"{person.id}: approved duty policy exceeded")
        assigned = intervals[("person", person.id)]
        if assigned and (max(a[1] for a in assigned) - min(a[0] for a in assigned)).total_seconds() + person.duty_already_seconds > person.max_duty_seconds:
            errors.append(f"{person.id}: elapsed duty span including gaps exceeds approved policy")
    for site_id, events in site_events.items():
        active = 0
        for _, delta in sorted(events, key=lambda pair: (pair[0], pair[1])):
            active += delta
            if active > sites[site_id].concurrent_capacity:
                errors.append(f"{site_id}: simultaneous capacity exceeded")
                break
    for mission in request.missions:
        for dependency in mission.depends_on:
            if dependency in by_mission and mission.id in by_mission and by_mission[dependency][1] > by_mission[mission.id][0]:
                errors.append(f"{mission.id}: predecessor {dependency} has not completed")
    return {"valid": not errors, "findings": sorted(set(errors)), "verifier_version": "independent-1.0.0", "input_snapshot": snapshot_hash(request), "checked_assignments": len(assignments)}
