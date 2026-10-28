"""Maintenance evidence, measured utilisation triggers and capacity planning.

Intervals come from reviewed aircraft/operator instructions. No universal UAS
maintenance interval, release privilege or component life is invented here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import product
import os
import re
from typing import Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select, update

from .scheduler import Contract, Window, snapshot_hash, stamp, utc

RULE_VERSION = "fleet-maintenance-2.0.1"


class MaintenanceTask(Contract):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    interval_calendar_days: int | None = Field(default=None, gt=0)
    interval_flight_seconds: int | None = Field(default=None, gt=0)
    interval_cycles: int | None = Field(default=None, gt=0)
    required_qualifications: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        if not any((self.interval_calendar_days, self.interval_flight_seconds, self.interval_cycles)):
            raise ValueError("A maintenance task needs a reviewed calendar, flight-time or cycle trigger")
        return self


class MaintenanceProgram(Contract):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    aircraft_id: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    status: Literal["Draft", "Under Review", "Approved", "Suspended", "Superseded"]
    approved_by: str | None = None
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    tasks: list[MaintenanceTask] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def valid(self):
        self.valid_from, self.valid_until = utc(self.valid_from), utc(self.valid_until)
        if self.valid_from >= self.valid_until:
            raise ValueError("Program validity must have positive duration")
        if len({task.id for task in self.tasks}) != len(self.tasks):
            raise ValueError("Maintenance task identifiers must be unique")
        return self


class UtilisationSnapshot(Contract):
    aircraft_id: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    record_version: int = Field(ge=1)
    measured_at: AwareDatetime
    total_flight_seconds: int = Field(ge=0)
    total_cycles: int = Field(ge=0)
    evidence_ref: str = Field(min_length=1)
    evidence_version: int | None = Field(default=None, ge=1)


class MaintenanceCompletion(Contract):
    task_id: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    completed_at: AwareDatetime
    total_flight_seconds: int = Field(ge=0)
    total_cycles: int = Field(ge=0)
    evidence_ref: str = Field(min_length=1)
    evidence_version: int | None = Field(default=None, ge=1)
    performed_by: str = Field(min_length=1)
    reviewed_by: str | None = None
    state: Literal["Recorded", "Under Review", "Released", "Rejected", "Superseded"]


class MaintenanceWorkOrder(Contract):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    aircraft_id: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    aircraft_record_version: int | None = Field(default=None, ge=1)
    program_id: str = Field(min_length=1)
    program_version: int = Field(ge=1)
    task_ids: list[str] = Field(min_length=1)
    window: Window
    duration_seconds: int = Field(gt=0, le=31 * 86400)
    state: Literal["Draft", "Scheduled", "In Progress", "Work Complete", "Under Review", "Released", "Cancelled"] = "Draft"
    required_qualifications: list[str] = Field(min_length=1)
    technician_id: str | None = None
    facility_id: str | None = None
    technician_record_version: int | None = Field(default=None, ge=1)
    facility_record_version: int | None = Field(default=None, ge=1)
    actual_start: AwareDatetime | None = None
    actual_end: AwareDatetime | None = None
    completion: list[MaintenanceCompletion] = Field(default_factory=list)
    source_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        if (self.window.end - self.window.start).total_seconds() < self.duration_seconds:
            raise ValueError("Work duration exceeds its scheduling window")
        if self.actual_end and not self.actual_start:
            raise ValueError("Actual completion needs a recorded work start")
        if self.actual_start and self.actual_end and utc(self.actual_start) > utc(self.actual_end):
            raise ValueError("Actual completion cannot precede the recorded start")
        return self


class MaintenanceAssessment(Contract):
    actor_id: str = Field(min_length=1)
    at: AwareDatetime
    program: MaintenanceProgram | None = None
    usage: UtilisationSnapshot | None = None
    completions: list[MaintenanceCompletion] = Field(default_factory=list, max_length=5000)
    work_orders: list[MaintenanceWorkOrder] = Field(default_factory=list, max_length=1000)
    forecast_end: AwareDatetime | None = None
    forecast_flight_seconds: int = Field(default=0, ge=0)
    forecast_cycles: int = Field(default=0, ge=0)
    open_safety_defects: list[str] = Field(default_factory=list)


def assess_maintenance(payload: dict | MaintenanceAssessment) -> dict:
    request = payload if isinstance(payload, MaintenanceAssessment) else MaintenanceAssessment.model_validate(payload)
    at = utc(request.at)
    end = utc(request.forecast_end) if request.forecast_end else at
    if end < at:
        raise ValueError("Forecast completion cannot precede the assessment")
    result = {"rule_version": RULE_VERSION, "input_snapshot": snapshot_hash(request), "actor_id": request.actor_id,
              "created_at": stamp(datetime.now(timezone.utc).replace(microsecond=0)), "status": "Incomplete", "serviceable_for_forecast": False,
              "tasks": [], "findings": [], "unavailability": [], "authority_status": "Internal maintenance readiness; no aircraft command or certified release privilege"}
    findings = result["findings"]
    program, usage = request.program, request.usage
    if program is None or usage is None:
        findings.append("Current reviewed maintenance program and measured utilisation snapshot are required")
        return result
    if program.status != "Approved" or not program.approved_by or not program.valid_from <= at <= end < program.valid_until:
        findings.append("Maintenance program is unreviewed, suspended, superseded or outside its validity")
    if program.aircraft_id != usage.aircraft_id or program.configuration_id != usage.configuration_id:
        findings.append("Maintenance program does not match aircraft identity and configuration baseline")
    if utc(usage.measured_at) > at:
        findings.append("Utilisation snapshot is later than assessment time")
    if request.open_safety_defects:
        findings.append("Open safety defects require rectification and accountable serviceability review")
    for order in request.work_orders:
        if order.aircraft_id != usage.aircraft_id:
            continue
        if order.configuration_id != usage.configuration_id:
            findings.append(f"{order.id}: work order configuration differs from current aircraft")
        if order.state in {"Scheduled", "In Progress", "Work Complete", "Under Review"}:
            # Completion alone never returns an aircraft to service.
            result["unavailability"].append({"work_order_id": order.id, "start": stamp(order.actual_start or order.window.start), "end": stamp(order.actual_end or order.window.end), "state": order.state})
            if order.state in {"In Progress", "Work Complete", "Under Review"} or order.window.start < end and order.window.end > at:
                findings.append(f"{order.id}: maintenance is scheduled or lacks an independently reviewed return-to-service record")
    for task in program.tasks:
        applicable = [c for c in request.completions if c.task_id == task.id and c.configuration_id == usage.configuration_id and c.state == "Released" and c.reviewed_by and c.reviewed_by != c.performed_by and utc(c.completed_at) <= at]
        completed = max(applicable, key=lambda item: utc(item.completed_at)) if applicable else None
        item = {"task_id": task.id, "title": task.title, "source_ref": task.source_ref, "source_version": task.source_version, "state": "Missing Evidence", "limits": {}, "remaining": {}}
        if completed is None:
            findings.append(f"{task.id}: no independently reviewed matching completion/baseline record")
        elif len({(item.total_flight_seconds, item.total_cycles) for item in applicable if utc(item.completed_at) == utc(completed.completed_at)}) > 1:
            item["state"] = "Contradictory Evidence"
            findings.append(f"{task.id}: equally recent completion records disagree on measured counters")
        elif completed.total_flight_seconds > usage.total_flight_seconds or completed.total_cycles > usage.total_cycles:
            item["state"] = "Contradictory Evidence"
            findings.append(f"{task.id}: measured counters precede maintenance baseline; reconcile utilisation")
        else:
            due_now, due_forecast = False, False
            if task.interval_calendar_days:
                due = utc(completed.completed_at) + timedelta(days=task.interval_calendar_days)
                item["limits"]["calendar_due"] = stamp(due)
                item["remaining"]["calendar_seconds"] = int((due - at).total_seconds())
                due_now |= at >= due
                due_forecast |= end >= due
            if task.interval_flight_seconds:
                due = completed.total_flight_seconds + task.interval_flight_seconds
                item["limits"]["total_flight_seconds"] = due
                item["remaining"]["flight_seconds"] = due - usage.total_flight_seconds
                due_now |= usage.total_flight_seconds >= due
                due_forecast |= usage.total_flight_seconds + request.forecast_flight_seconds >= due
            if task.interval_cycles:
                due = completed.total_cycles + task.interval_cycles
                item["limits"]["total_cycles"] = due
                item["remaining"]["cycles"] = due - usage.total_cycles
                due_now |= usage.total_cycles >= due
                due_forecast |= usage.total_cycles + request.forecast_cycles >= due
            item["state"] = "Due" if due_now else "Due Before Forecast Completion" if due_forecast else "Within Reviewed Limits"
            item["baseline_evidence_ref"] = completed.evidence_ref
            if due_now or due_forecast:
                findings.append(f"{task.id}: {item['state']}; a planned work order does not reset counters")
        result["tasks"].append(item)
    result["status"] = "Blocked" if findings else "Within Reviewed Maintenance Limits"
    result["serviceable_for_forecast"] = not findings
    return result


class MaintenanceTechnician(Contract):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    availability: list[Window] = Field(min_length=1, max_length=50)
    qualifications: dict[str, AwareDatetime]
    qualification_evidence_ref: str = Field(min_length=1)


class MaintenanceFacility(Contract):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    availability: list[Window] = Field(min_length=1, max_length=50)
    capacity: int = Field(gt=0, le=100)
    scope_task_ids: list[str] = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)


class AircraftBusyInterval(Contract):
    aircraft_id: str = Field(min_length=1)
    interval: Window
    evidence_ref: str = Field(min_length=1)


class MaintenancePlanRequest(Contract):
    actor_id: str = Field(min_length=1)
    work_orders: list[MaintenanceWorkOrder] = Field(min_length=1, max_length=100)
    technicians: list[MaintenanceTechnician] = Field(min_length=1, max_length=100)
    facilities: list[MaintenanceFacility] = Field(min_length=1, max_length=100)
    aircraft_busy: list[AircraftBusyInterval] = Field(default_factory=list, max_length=1000)
    max_solver_seconds: float = Field(default=5, gt=0, le=30)


def plan_maintenance(payload: dict | MaintenancePlanRequest) -> dict:
    request = payload if isinstance(payload, MaintenancePlanRequest) else MaintenancePlanRequest.model_validate(payload)
    from ortools.sat.python import cp_model
    import ortools
    result = {"rule_version": RULE_VERSION, "input_snapshot": snapshot_hash(request), "actor_id": request.actor_id, "assignments": [], "status": "INCOMPLETE", "findings": [], "solver_version": ortools.__version__, "approval": "Proposal only"}
    for collection in (request.work_orders, request.technicians, request.facilities):
        if len({item.id for item in collection}) != len(collection):
            raise ValueError("Maintenance planning identifiers must be unique")
    epoch = min(order.window.start for order in request.work_orders)
    horizon = int((max(order.window.end for order in request.work_orders) - epoch).total_seconds())
    if horizon > 366 * 86400:
        result["findings"] = ["Maintenance planning horizon exceeds one year"]
        return result
    offset = lambda value: int((utc(value) - epoch).total_seconds())
    model = cp_model.CpModel()
    tech_intervals, aircraft_intervals, facility_intervals = defaultdict(list), defaultdict(list), defaultdict(list)
    starts, ends, choices, work = {}, {}, {}, 0
    for busy in request.aircraft_busy:
        lower, upper = max(0, offset(busy.interval.start)), min(horizon, offset(busy.interval.end))
        if upper > lower:
            aircraft_intervals[busy.aircraft_id].append(model.new_fixed_size_interval_var(lower, upper - lower, "reserved-aircraft"))
    for order in request.work_orders:
        if order.state not in {"Draft", "Scheduled"}:
            result["findings"].append(f"{order.id}: started/completed/cancelled work cannot be moved by planning")
            return result
        start = starts[order.id] = model.new_int_var(offset(order.window.start), offset(order.window.end) - order.duration_seconds, f"start:{order.id}")
        end = ends[order.id] = model.new_int_var(0, horizon, f"end:{order.id}")
        model.add(end == start + order.duration_seconds)
        candidates = []
        for technician, facility in product(request.technicians, request.facilities):
            if order.technician_id and technician.id != order.technician_id or order.facility_id and facility.id != order.facility_id:
                continue
            if not set(order.required_qualifications).issubset(technician.qualifications) or not set(order.task_ids).issubset(facility.scope_task_ids):
                continue
            for tw, fw in product(technician.availability, facility.availability):
                work += 1
                if work > 50000:
                    result["findings"] = ["Maintenance planning search exceeds bounded candidate-window limit"]
                    return result
                lower = max(order.window.start, tw.start, fw.start)
                upper = min(order.window.end, tw.end, fw.end, *(utc(technician.qualifications[q]) for q in order.required_qualifications))
                if (upper - lower).total_seconds() < order.duration_seconds:
                    continue
                chosen = model.new_bool_var(f"chosen:{work}")
                model.add(start >= offset(lower)).only_enforce_if(chosen)
                model.add(end <= offset(upper)).only_enforce_if(chosen)
                interval = model.new_optional_fixed_size_interval_var(start, order.duration_seconds, chosen, f"work:{work}")
                tech_intervals[technician.id].append(interval)
                aircraft_intervals[order.aircraft_id].append(interval)
                facility_intervals[facility.id].append(interval)
                candidates.append((chosen, technician.id, facility.id))
        if not candidates:
            result.update(status="INFEASIBLE", findings=[f"{order.id}: no qualified technician and in-scope facility fit the required window"])
            return result
        model.add_exactly_one([candidate[0] for candidate in candidates])
        choices[order.id] = candidates
    for intervals in [*tech_intervals.values(), *aircraft_intervals.values()]:
        model.add_no_overlap(intervals)
    for facility in request.facilities:
        intervals = facility_intervals[facility.id]
        if intervals:
            model.add_cumulative(intervals, [1] * len(intervals), facility.capacity)
    model.minimize(sum(starts.values()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = request.max_solver_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    result.update(status=solver.status_name(status), wall_seconds=solver.wall_time)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for order in request.work_orders:
            chosen = next(candidate for candidate in choices[order.id] if solver.boolean_value(candidate[0]))
            result["assignments"].append({"work_order_id": order.id, "work_order_version": order.version, "aircraft_id": order.aircraft_id, "technician_id": chosen[1], "facility_id": chosen[2], "start": stamp(epoch + timedelta(seconds=solver.value(starts[order.id]))), "end": stamp(epoch + timedelta(seconds=solver.value(ends[order.id])))})
        result["verification"] = verify_maintenance_plan(request, result)
        if not result["verification"]["valid"]:
            result.update(status="VERIFICATION_FAILED", assignments=[])
    return result


def verify_maintenance_plan(request: MaintenancePlanRequest | dict, result: dict) -> dict:
    request = request if isinstance(request, MaintenancePlanRequest) else MaintenancePlanRequest.model_validate(request)
    errors, tech_usage, craft_usage, site_usage = [], defaultdict(list), defaultdict(list), defaultdict(list)
    orders = {order.id: order for order in request.work_orders}
    technicians = {item.id: item for item in request.technicians}
    facilities = {item.id: item for item in request.facilities}
    assignments = result.get("assignments", [])
    ids = [assignment.get("work_order_id") for assignment in assignments]
    if set(ids) != set(orders) or len(set(ids)) != len(ids) or result.get("input_snapshot") != snapshot_hash(request):
        errors.append("Input snapshot or work-order coverage changed")
    for assignment in assignments:
        order, technician, facility = orders.get(assignment.get("work_order_id")), technicians.get(assignment.get("technician_id")), facilities.get(assignment.get("facility_id"))
        if not all((order, technician, facility)):
            errors.append("Unknown work order, technician or facility")
            continue
        try:
            start, end = utc(datetime.fromisoformat(assignment["start"].replace("Z", "+00:00"))), utc(datetime.fromisoformat(assignment["end"].replace("Z", "+00:00")))
        except (ValueError, TypeError, KeyError):
            errors.append("Invalid maintenance assignment timestamps")
            continue
        if assignment.get("aircraft_id") != order.aircraft_id or assignment.get("work_order_version") != order.version:
            errors.append("Work-order identity/version mismatch")
        if not order.window.start <= start < end <= order.window.end or (end - start).total_seconds() != order.duration_seconds:
            errors.append("Maintenance duration/window mismatch")
        if order.technician_id and order.technician_id != technician.id or order.facility_id and order.facility_id != facility.id:
            errors.append("Locked maintenance assignment changed")
        if any(q not in technician.qualifications or utc(technician.qualifications[q]) < end for q in order.required_qualifications):
            errors.append("Maintenance qualification missing or expired")
        if not set(order.task_ids).issubset(facility.scope_task_ids):
            errors.append("Maintenance facility task scope mismatch")
        if not any(window.start <= start and end <= window.end for window in technician.availability) or not any(window.start <= start and end <= window.end for window in facility.availability):
            errors.append("Maintenance assignment outside resource availability")
        tech_usage[technician.id].append((start, end))
        craft_usage[order.aircraft_id].append((start, end))
        site_usage[facility.id].extend([(start, 1), (end, -1)])
    for busy in request.aircraft_busy:
        craft_usage[busy.aircraft_id].append((busy.interval.start, busy.interval.end))
    for ranges in [*tech_usage.values(), *craft_usage.values()]:
        ranges.sort()
        if any(right[0] < left[1] for left, right in zip(ranges, ranges[1:])):
            errors.append("Maintenance overlaps another work order or aircraft reservation")
    for facility_id, events in site_usage.items():
        active = 0
        for _, delta in sorted(events, key=lambda pair: (pair[0], pair[1])):
            active += delta
            if active > facilities[facility_id].capacity:
                errors.append("Maintenance facility simultaneous capacity exceeded")
    return {"valid": not errors, "findings": sorted(set(errors)), "verifier_version": "maintenance-independent-2.0.0"}


def validate_fleet_for_schedule(conn, tenant: str, request, result: dict, schedule_id: str | None = None) -> list[dict]:
    """Persisted maintenance gate; call within the reservation/dispatch lock.

    Aircraft records opt into the new maintenance_program_id/usage contract.
    New dispatch must require these fields; legacy planning can remain advisory.
    """
    from .storage import records, reservations, fleet_reservations, sharing_agreements
    assessments = []
    for aircraft in request.aircraft:
        assignments = [item for item in result.get("assignments", []) if item["aircraft_id"] == aircraft.id]
        if not assignments:
            continue
        row = conn.execute(select(records).where(records.c.id == aircraft.id, records.c.kind == "aircraft", records.c.organisation_id == tenant)).mappings().first()
        if not row:
            raise HTTPException(422, "Aircraft record is unavailable in this operating organisation")
        data = row["data"]
        program_id = data.get("maintenance_program_id")
        if not program_id or not data.get("utilisation"):
            raise HTTPException(422, "Aircraft needs a current maintenance program and measured utilisation before internal release")
        program_row = conn.execute(select(records).where(records.c.id == program_id, records.c.kind == "maintenance_program", records.c.organisation_id == tenant)).mappings().first()
        if not program_row or program_row["status"] != "Approved":
            raise HTTPException(422, "Current independently reviewed maintenance program is missing")
        program = {**program_row["data"]["program"], "id": program_id, "version": program_row["version"], "status": "Approved", "approved_by": (program_row["data"].get("_approvals") or [{}])[-1].get("actor_id")}
        work_rows = conn.execute(select(records).where(records.c.kind == "maintenance_work_order", records.c.organisation_id == tenant)).mappings().all()
        orders, completions = [], list(data.get("maintenance_completions", []))
        for work_row in work_rows:
            raw = work_row["data"].get("work_order", {})
            if raw.get("aircraft_id") != aircraft.id:
                continue
            order = MaintenanceWorkOrder.model_validate({**raw, "id": work_row["id"], "version": work_row["version"], "state": work_row["status"]})
            orders.append(order)
            if work_row["status"] == "Released":
                completions.extend(completion.model_dump(mode="json") for completion in order.completion)
        starts = [datetime.fromisoformat(item["start"].replace("Z", "+00:00")) for item in assignments]
        ends = [datetime.fromisoformat(item["end"].replace("Z", "+00:00")) for item in assignments]
        usage = UtilisationSnapshot.model_validate(data["utilisation"])
        def verify_source(reference, expected_version):
            source = conn.execute(select(records).where(records.c.id == reference,
                records.c.organisation_id == tenant, records.c.kind == "evidence")).mappings().first()
            if not source or source["status"] != "Approved" or not source["data"].get("_approvals") or not source["data"].get("provenance") or not source["data"].get("evidence_type") or not re.fullmatch(r"[0-9a-f]{64}", str(source["data"].get("checksum", ""))) or source["version"] != expected_version:
                raise HTTPException(422, "Maintenance utilisation/completion source evidence is missing, changed or lacks current independent review")
        verify_source(usage.evidence_ref, usage.evidence_version)
        typed_completions = [MaintenanceCompletion.model_validate(item) for item in completions]
        for task in program["tasks"]:
            applicable = [item for item in typed_completions if item.task_id == task["id"] and item.configuration_id == aircraft.configuration_id and item.state == "Released" and utc(item.completed_at) <= min(starts)]
            if applicable:
                latest = max(utc(item.completed_at) for item in applicable)
                for completion in applicable:
                    if utc(completion.completed_at) == latest:
                        verify_source(completion.evidence_ref, completion.evidence_version)
        forecast_seconds = int(sum((end - start).total_seconds() for start, end in zip(starts, ends)))
        measured_at = utc(datetime.fromisoformat(data["utilisation"]["measured_at"].replace("Z", "+00:00")))
        current_missions = {item["mission_id"] for item in assignments}
        pending_seconds, pending_cycles, counted = 0, 0, set()
        prior_local = conn.execute(select(reservations).where(reservations.c.organisation_id == tenant, reservations.c.resource_kind == "aircraft", reservations.c.resource_id == aircraft.id, reservations.c.state == "Reserved")).mappings().all()
        for reserved in prior_local:
            if reserved["schedule_id"] == schedule_id or reserved["mission_id"] in current_missions:
                continue
            if datetime.fromisoformat(reserved["start"]) >= max(ends) or datetime.fromisoformat(reserved["end"]) <= measured_at:
                continue
            prior = conn.execute(select(records).where(records.c.id == reserved["schedule_id"], records.c.organisation_id == tenant, records.c.kind == "schedule")).mappings().first()
            entry = next((item for item in prior["data"].get("result", {}).get("assignments", []) if item["mission_id"] == reserved["mission_id"]), None) if prior else None
            if not entry:
                raise HTTPException(409, "Existing maintenance utilisation allocation requires reconciliation")
            pending_seconds += int((datetime.fromisoformat(entry["end"].replace("Z", "+00:00")) - datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))).total_seconds())
            pending_cycles += 1
            counted.add((reserved["schedule_id"], reserved["mission_id"]))
        owner, physical_id = tenant, aircraft.id
        if data.get("sharing_agreement_id"):
            agreement = conn.execute(select(sharing_agreements).where(sharing_agreements.c.id == data["sharing_agreement_id"], sharing_agreements.c.operator_organisation_id == tenant, sharing_agreements.c.state == "Accepted")).mappings().first()
            if not agreement:
                raise HTTPException(422, "Maintenance forecast requires a current explicit sharing agreement")
            owner, physical_id = agreement["owner_organisation_id"], agreement["aircraft_id"]
        pending_physical = conn.execute(select(fleet_reservations).where(fleet_reservations.c.owner_organisation_id == owner, fleet_reservations.c.aircraft_id == physical_id, fleet_reservations.c.state.in_(["Reserved", "Suspended"]))).mappings().all()
        for reserved in pending_physical:
            if reserved["schedule_id"] == schedule_id or reserved["mission_id"] in current_missions or (reserved["schedule_id"], reserved["mission_id"]) in counted:
                continue
            if datetime.fromisoformat(reserved["start"]) >= max(ends) or datetime.fromisoformat(reserved["end"]) <= measured_at:
                continue
            if reserved["flight_seconds"] is None:
                raise HTTPException(409, "Physical aircraft utilisation allocation requires reconciliation")
            pending_seconds += reserved["flight_seconds"]
            pending_cycles += 1
        assessment = assess_maintenance({"actor_id": request.actor_id, "at": min(starts), "forecast_end": max(ends), "forecast_flight_seconds": forecast_seconds + pending_seconds, "forecast_cycles": len(assignments) + pending_cycles, "program": program, "usage": data["utilisation"], "completions": completions, "work_orders": [order.model_dump(mode="json") for order in orders], "open_safety_defects": data.get("open_safety_defects", [])})
        assessment["planned_utilisation"] = {"current_flight_seconds": forecast_seconds, "other_reserved_flight_seconds": pending_seconds, "current_flight_cycles": len(assignments), "other_reserved_flight_cycles": pending_cycles, "meaning": "Conservative future allocation; one planned flight cycle per assigned flight, never an observed flown mission"}
        if not assessment["serviceable_for_forecast"]:
            raise HTTPException(422, {"message": "Maintenance readiness blocks the proposed assignment", "assessment": assessment})
        assessments.append(assessment)
    return assessments


def _program_source_references(data):
    references = {value for value in data.get("evidence_ids", []) if isinstance(value, str)} if isinstance(data.get("evidence_ids"), list) else set()
    program = data.get("program")
    tasks = program.get("tasks", []) if isinstance(program, dict) else []
    if isinstance(tasks, list):
        references.update(task["source_ref"] for task in tasks if isinstance(task, dict) and isinstance(task.get("source_ref"), str))
    approvals = data.get("_approvals", [])
    if isinstance(approvals, list):
        for approval in approvals:
            if isinstance(approval, dict) and isinstance(approval.get("evidence_ids"), list):
                references.update(value for value in approval["evidence_ids"] if isinstance(value, str))
    return references


def _maintenance_dependent_aircraft(conn, tenant, record_id):
    """Resolve only this owner's explicitly recorded maintenance dependencies."""
    from .storage import records
    rows = conn.execute(select(records).where(records.c.organisation_id == tenant,
        records.c.kind.in_(["aircraft", "maintenance_program", "maintenance_work_order"]))).mappings().all()
    def mapping(value):
        return value if isinstance(value, dict) else {}
    def strings(value):
        return {item for item in value if isinstance(item, str)} if isinstance(value, list) else set()
    def objects(value):
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    programs, work_assets = set(), set()
    for row in rows:
        data = row["data"]
        if row["kind"] == "maintenance_program":
            references = _program_source_references(data)
            if row["id"] == record_id or record_id in references:
                programs.add(row["id"])
        elif row["kind"] == "maintenance_work_order":
            order = mapping(data.get("work_order"))
            references = strings(data.get("evidence_ids"))
            if isinstance(order.get("source_ref"), str): references.add(order["source_ref"])
            references.update(item["evidence_ref"] for item in objects(order.get("completion")) if isinstance(item.get("evidence_ref"), str))
            if row["id"] == record_id or record_id in references:
                if isinstance(order.get("aircraft_id"), str): work_assets.add(order["aircraft_id"])
    assets = set()
    for row in rows:
        if row["kind"] != "aircraft" or row["data"].get("sharing_agreement_id"):
            continue
        data = row["data"]
        references = strings(data.get("evidence_ids"))
        usage_ref = mapping(data.get("utilisation")).get("evidence_ref")
        if isinstance(usage_ref, str): references.add(usage_ref)
        references.update(item["evidence_ref"] for item in objects(data.get("maintenance_completions")) if isinstance(item.get("evidence_ref"), str))
        program_id = data.get("maintenance_program_id")
        if row["id"] in work_assets or isinstance(program_id, str) and program_id in programs or record_id in references:
            assets.add(row["id"])
    return assets


def lock_maintenance_dependency_mutation(conn, tenant, record_id):
    """Call before a tenant-only lock when editing program or source evidence.

    An owner's source revision can affect several explicit borrowers. Lock the
    complete party set once, then canonical assets, to avoid per-asset inversion.
    """
    from .sharing import lock_owned_aircraft_set_mutation
    assets = _maintenance_dependent_aircraft(conn, tenant, record_id)
    lock_owned_aircraft_set_mutation(conn, tenant, assets)
    if not _maintenance_dependent_aircraft(conn, tenant, record_id).issubset(assets):
        raise HTTPException(409, "Maintenance dependency scope changed while acquiring locks; reload and retry")
    return sorted(assets)


def suspend_maintenance_dependants(conn, store, tenant, record_id, user, reason):
    """Invalidate existing releases without disclosing owner source records.

    Caller must already hold lock_maintenance_dependency_mutation's locks in the
    same transaction. This propagates only through owned assets and the explicit
    physical ledger, never through an unfiltered cross-tenant record query.
    """
    from .dispatch import suspend_dispatch_dependencies, suspend_dispatch_for_aircraft
    from .storage import records, now
    from .domain_records import normalise_domain_record
    changed = 0
    assets = _maintenance_dependent_aircraft(conn, tenant, record_id)
    programs = conn.execute(select(records).where(records.c.organisation_id == tenant,
        records.c.kind == "maintenance_program", records.c.status == "Approved",
        records.c.id != record_id)).mappings().all()
    for item in programs:
        if record_id not in _program_source_references(item["data"]):
            continue
        row = dict(item)
        row.update(status="Suspended", version=row["version"] + 1, updated_at=now(),
            data={**row["data"], "_source_suspension": {"source_record_id": record_id,
                "actor_id": user["id"], "at": now(), "reason": reason,
                "meaning": "Source changed; new independent program review is required"}})
        row = normalise_domain_record(row)
        conn.execute(update(records).where(records.c.id == row["id"],
            records.c.organisation_id == tenant, records.c.version == row["version"] - 1).values(**row))
        store.snapshot(conn, row)
        store.append_audit(conn, tenant, user["id"], "maintenance.program_source_invalidated",
            {"record_id": row["id"], "version": row["version"], "source_record_id": record_id, "reason": reason})
    for aircraft_id in sorted(assets):
        changed += suspend_dispatch_dependencies(conn, store, tenant, aircraft_id, user, reason)
        changed += suspend_dispatch_for_aircraft(conn, store, tenant, aircraft_id, user, reason)
    return changed


def maintenance_workspace(store, user, aircraft_id):
    from .storage import records, now
    tenant = user["organisation_id"]
    with store.engine.connect() as conn:
        aircraft = conn.execute(select(records).where(records.c.id == aircraft_id, records.c.kind == "aircraft", records.c.organisation_id == tenant)).mappings().first()
        if not aircraft:
            raise HTTPException(404, "Aircraft not found")
        aircraft = dict(aircraft)
        program_id = aircraft["data"].get("maintenance_program_id")
        program_row = conn.execute(select(records).where(records.c.id == program_id, records.c.kind == "maintenance_program", records.c.organisation_id == tenant)).mappings().first() if program_id else None
        program = None
        if program_row:
            approvals = program_row["data"].get("_approvals") or [{}]
            program = {**program_row["data"].get("program", {}), "id": program_row["id"], "version": program_row["version"], "status": program_row["status"], "approved_by": approvals[-1].get("actor_id")}
        orders = [dict(row) for row in conn.execute(select(records).where(records.c.organisation_id == tenant, records.c.kind == "maintenance_work_order", records.c.data["work_order"]["aircraft_id"].as_string() == aircraft_id)).mappings().all()]
    completions = list(aircraft["data"].get("maintenance_completions", []))
    work_orders = []
    for row in orders:
        order = {**row["data"]["work_order"], "id": row["id"], "version": row["version"], "state": row["status"]}
        work_orders.append(order)
        if row["status"] == "Released":
            completions.extend(order.get("completion", []))
    request = {"actor_id": user["id"], "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "program": program,
               "usage": aircraft["data"].get("utilisation"), "completions": completions, "work_orders": work_orders, "open_safety_defects": aircraft["data"].get("open_safety_defects", [])}
    return {"aircraft": aircraft, "program_record": dict(program_row) if program_row else None, "work_orders": orders, "assessment_input": request, "boundary": "Saved records only; missing program, usage and completion evidence remain missing"}


class SavedMaintenanceAssessment(Contract):
    at: AwareDatetime | None = None
    forecast_end: AwareDatetime | None = None
    forecast_flight_seconds: int = Field(default=0, ge=0)
    forecast_cycles: int = Field(default=0, ge=0)


def assess_saved_maintenance(store, user, aircraft_id, payload: SavedMaintenanceAssessment | dict):
    payload = payload if isinstance(payload, SavedMaintenanceAssessment) else SavedMaintenanceAssessment.model_validate(payload)
    workspace = maintenance_workspace(store, user, aircraft_id)
    request = workspace["assessment_input"]
    request.update(payload.model_dump(mode="json", exclude_none=True))
    result = assess_maintenance(request)
    return {"aircraft_id": aircraft_id, "aircraft_version": workspace["aircraft"]["version"], "assessment": result}


class WorkOrderControl(Contract):
    expected_version: int = Field(ge=1)
    target: Literal["Scheduled", "In Progress", "Work Complete", "Under Review", "Released", "Cancelled"]
    reason: str = Field(min_length=1, max_length=4000)
    technician_id: str | None = None
    facility_id: str | None = None
    scheduled_start: AwareDatetime | None = None
    scheduled_end: AwareDatetime | None = None
    completions: list[MaintenanceCompletion] = Field(default_factory=list)


def transition_work_order(store, work_order_id, user, payload: WorkOrderControl | dict):
    from .storage import records, users, organisations, now
    payload = payload if isinstance(payload, WorkOrderControl) else WorkOrderControl.model_validate(payload)
    if not payload.reason.strip():
        raise HTTPException(422, "A nonblank maintenance decision rationale is required")
    tenant = user["organisation_id"]
    current = datetime.now(timezone.utc).replace(microsecond=0)
    allowed = {"Draft": {"Scheduled", "Cancelled"}, "Scheduled": {"In Progress", "Cancelled"}, "In Progress": {"Work Complete"}, "Work Complete": {"Under Review"}, "Under Review": {"Released", "Work Complete"}}
    with store.engine.begin() as conn:
        preliminary_actor = conn.execute(select(users).where(users.c.id == user["id"], users.c.organisation_id == tenant, users.c.disabled == 0)).mappings().first()
        if not preliminary_actor or preliminary_actor["role"] != user.get("role") or preliminary_actor["role"] not in {"fleet_manager", "reviewer"}:
            raise HTTPException(403, "Current authorised maintenance actor required")
        preliminary = conn.execute(select(records).where(records.c.id == work_order_id, records.c.kind == "maintenance_work_order", records.c.organisation_id == tenant)).mappings().first()
        if not preliminary:
            raise HTTPException(404, "Maintenance work order not found")
        if payload.target != "Cancelled":
            from .sharing import lock_aircraft_mutation
            asset_id = preliminary["data"].get("work_order", {}).get("aircraft_id")
            if not asset_id:
                raise HTTPException(422, "Work order needs an actual owned aircraft before transition")
            lock_aircraft_mutation(conn, tenant, asset_id)
        conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq))
        principal = conn.execute(select(users).where(users.c.id == user["id"], users.c.organisation_id == tenant, users.c.disabled == 0)).mappings().first()
        if not principal or principal["role"] != user.get("role") or principal["role"] not in {"fleet_manager", "reviewer"}:
            raise HTTPException(403, "Current authorised maintenance actor required")
        found = conn.execute(select(records).where(records.c.id == work_order_id, records.c.kind == "maintenance_work_order", records.c.organisation_id == tenant)).mappings().first()
        if not found:
            raise HTTPException(404, "Maintenance work order not found")
        row = dict(found)
        if row["version"] != payload.expected_version or payload.target not in allowed.get(row["status"], set()):
            raise HTTPException(409, "Work order changed or transition is unavailable")
        if payload.target == "Cancelled":
            if user["role"] != "fleet_manager":
                raise HTTPException(403, "Fleet manager must cancel unstarted maintenance")
            row.update(status="Cancelled", version=row["version"] + 1, updated_at=now(), data={**row["data"], "work_order": {**row["data"]["work_order"], "state": "Cancelled", "version": row["version"] + 1}, "_maintenance_decision": {"actor_id": user["id"], "at": now(), "reason": payload.reason}})
            conn.execute(update(records).where(records.c.id == work_order_id, records.c.organisation_id == tenant, records.c.version == payload.expected_version).values(**row))
            store.snapshot(conn, row)
            store.append_audit(conn, tenant, user["id"], "maintenance.cancelled", {"work_order_id": work_order_id, "version": row["version"], "reason": payload.reason})
            return row
        order = MaintenanceWorkOrder.model_validate({**row["data"]["work_order"], "id": row["id"], "version": row["version"], "state": row["status"]})
        from .sharing import _lock_resource
        _lock_resource(conn, tenant, order.aircraft_id)
        aircraft_row = conn.execute(select(records).where(records.c.id == order.aircraft_id, records.c.kind == "aircraft", records.c.organisation_id == tenant)).mappings().first()
        program_row = conn.execute(select(records).where(records.c.id == order.program_id, records.c.kind == "maintenance_program", records.c.organisation_id == tenant)).mappings().first()
        if not aircraft_row or not program_row or program_row["status"] != "Approved" or program_row["version"] != order.program_version or aircraft_row["version"] != order.aircraft_record_version:
            raise HTTPException(409, "Maintenance aircraft/program version is missing, changed or unreviewed")
        aircraft_row = dict(aircraft_row)
        program = MaintenanceProgram.model_validate({**program_row["data"]["program"], "id": program_row["id"], "version": program_row["version"], "status": program_row["status"], "approved_by": (program_row["data"].get("_approvals") or [{}])[-1].get("actor_id")})
        if not program.approved_by or program.configuration_id != order.configuration_id or program.aircraft_id != order.aircraft_id or aircraft_row["data"].get("scheduler", {}).get("configuration_id") != order.configuration_id:
            raise HTTPException(422, "Work order does not match the reviewed maintenance/configuration baseline")
        tasks = [task for task in program.tasks if task.id in order.task_ids]
        required = {qualification for task in tasks for qualification in task.required_qualifications}
        if len(tasks) != len(set(order.task_ids)) or not required.issubset(order.required_qualifications):
            raise HTTPException(422, "Work-order task scope or qualification requirements are incomplete")
        if payload.target != "Scheduled" and not program.valid_from <= current < program.valid_until:
            raise HTTPException(422, "Current maintenance program validity expired")
        if payload.target == "Scheduled":
            if user["role"] != "fleet_manager" or not payload.technician_id or not payload.facility_id or not payload.scheduled_start or not payload.scheduled_end:
                raise HTTPException(422, "Scheduling requires a fleet manager, actual technician/facility and chosen interval")
            technician = conn.execute(select(records).where(records.c.id == payload.technician_id, records.c.kind == "personnel", records.c.organisation_id == tenant)).mappings().first()
            facility = conn.execute(select(records).where(records.c.id == payload.facility_id, records.c.kind == "site", records.c.organisation_id == tenant)).mappings().first()
            if not technician or not facility or technician["status"] != "Approved" or facility["status"] != "Approved":
                raise HTTPException(422, "Maintenance resources need current internal review")
            tech = MaintenanceTechnician.model_validate({**technician["data"].get("maintenance_technician", {}), "id": technician["id"], "version": technician["version"]})
            bay = MaintenanceFacility.model_validate({**facility["data"].get("maintenance_facility", {}), "id": facility["id"], "version": facility["version"]})
            proposal = {"actor_id": user["id"], "work_orders": [order.model_dump(mode="json")], "technicians": [tech.model_dump(mode="json")], "facilities": [bay.model_dump(mode="json")], "aircraft_busy": []}
            assignment = {"work_order_id": order.id, "work_order_version": order.version, "aircraft_id": order.aircraft_id, "technician_id": tech.id, "facility_id": bay.id, "start": stamp(utc(payload.scheduled_start)), "end": stamp(utc(payload.scheduled_end))}
            verified = verify_maintenance_plan(proposal, {"input_snapshot": snapshot_hash(MaintenancePlanRequest.model_validate(proposal)), "assignments": [assignment]})
            if not verified["valid"]:
                raise HTTPException(422, {"message": "Maintenance resource assignment is invalid", "findings": verified["findings"]})
            if not program.valid_from <= utc(payload.scheduled_start) < utc(payload.scheduled_end) <= program.valid_until:
                raise HTTPException(422, "Maintenance assignment is outside program validity")
            if aircraft_row["data"].get("sharing_agreement_id"):
                raise HTTPException(422, "Schedule maintenance in the owning organisation; borrowed-alias records cannot change the owner's serviceability")
            from .sharing import _lock_resource
            from .storage import reservations, fleet_reservations
            _lock_resource(conn, tenant, order.aircraft_id)
            first, last = utc(payload.scheduled_start).isoformat(), utc(payload.scheduled_end).isoformat()
            if conn.execute(select(reservations.c.id).where(reservations.c.organisation_id == tenant, reservations.c.resource_kind == "aircraft", reservations.c.resource_id == order.aircraft_id, reservations.c.state == "Reserved", reservations.c.start < last, reservations.c.end > first)).first() or conn.execute(select(fleet_reservations.c.id).where(fleet_reservations.c.owner_organisation_id == tenant, fleet_reservations.c.aircraft_id == order.aircraft_id, fleet_reservations.c.state.in_(["Reserved", "Suspended"]), fleet_reservations.c.start < last, fleet_reservations.c.end > first)).first():
                raise HTTPException(409, "Maintenance conflicts with an existing owner or shared-aircraft reservation")
            other = conn.execute(select(records).where(records.c.kind == "maintenance_work_order", records.c.organisation_id == tenant, records.c.id != order.id, records.c.status.in_(["Scheduled", "In Progress", "Work Complete", "Under Review"]))).mappings().all()
            facility_events = [(utc(payload.scheduled_start), 1), (utc(payload.scheduled_end), -1)]
            for item in other:
                raw = item["data"].get("work_order", {})
                busy = Window.model_validate(raw["window"])
                if busy.start < payload.scheduled_end and busy.end > payload.scheduled_start and (raw.get("aircraft_id") == order.aircraft_id or raw.get("technician_id") == tech.id):
                    raise HTTPException(409, "Aircraft or technician already has overlapping maintenance")
                if raw.get("facility_id") == bay.id:
                    facility_events.extend([(busy.start, 1), (busy.end, -1)])
            active = 0
            for _, delta in sorted(facility_events, key=lambda item: (item[0], item[1])):
                active += delta
                if active > bay.capacity:
                    raise HTTPException(409, "Maintenance facility capacity is already reserved")
            order.window = Window(start=payload.scheduled_start, end=payload.scheduled_end)
            order.technician_id, order.facility_id = tech.id, bay.id
            order.technician_record_version, order.facility_record_version = technician["version"], facility["version"]
        elif payload.target == "In Progress":
            person = conn.execute(select(records).where(records.c.id == order.technician_id, records.c.kind == "personnel", records.c.organisation_id == tenant)).mappings().first()
            if user["role"] != "fleet_manager" or not person or person["status"] != "Approved" or person["version"] != order.technician_record_version or person["data"].get("user_id") != user["id"] or not order.window.start <= current < order.window.end:
                raise HTTPException(403, "The assigned actual technician must record work within its scheduled interval")
            tech = MaintenanceTechnician.model_validate({**person["data"].get("maintenance_technician", {}), "id": person["id"], "version": person["version"]})
            if any(scope not in tech.qualifications or utc(tech.qualifications[scope]) < order.window.end for scope in required):
                raise HTTPException(422, "Technician's task qualification expired after planning")
            facility = conn.execute(select(records).where(records.c.id == order.facility_id, records.c.kind == "site", records.c.organisation_id == tenant)).mappings().first()
            if not facility or facility["status"] != "Approved" or facility["version"] != order.facility_record_version:
                raise HTTPException(409, "Maintenance facility changed or is unavailable; review the work assignment before starting")
            order.actual_start = current
            order.actual_end = None
            aircraft_row["data"] = {**aircraft_row["data"], "scheduler": {**aircraft_row["data"]["scheduler"], "serviceable": False}, "_prepared_by": user["id"]}
            aircraft_row.update(status="Suspended", version=aircraft_row["version"] + 1, updated_at=now())
            conn.execute(update(records).where(records.c.id == order.aircraft_id, records.c.organisation_id == tenant).values(**aircraft_row))
            store.snapshot(conn, aircraft_row)
            from .dispatch import suspend_dispatch_for_aircraft, suspend_dispatch_dependencies
            suspend_dispatch_for_aircraft(conn, store, tenant, order.aircraft_id, user, "Maintenance started; aircraft readiness changed")
            suspend_dispatch_dependencies(conn, store, tenant, order.aircraft_id, user, "Maintenance started; aircraft readiness changed")
            order.aircraft_record_version = aircraft_row["version"]
        elif payload.target == "Work Complete":
            if user["role"] != "fleet_manager" or not payload.completions or not order.actual_start:
                raise HTTPException(422, "Actual completion evidence and maintenance actor are required")
            if {completion.task_id for completion in payload.completions} != set(order.task_ids):
                raise HTTPException(422, "Every work-order task needs actual completion evidence")
            assigned = conn.execute(select(records).where(records.c.id == order.technician_id, records.c.kind == "personnel", records.c.organisation_id == tenant)).mappings().first()
            if not assigned or assigned["data"].get("user_id") != user["id"]:
                raise HTTPException(403, "Only the assigned actual technician can record work completion")
            usage = UtilisationSnapshot.model_validate(aircraft_row["data"].get("utilisation", {}))
            completed = []
            for completion in payload.completions:
                if completion.configuration_id != order.configuration_id or completion.performed_by != user["id"] or not order.actual_start <= utc(completion.completed_at) <= current or completion.total_flight_seconds != usage.total_flight_seconds or completion.total_cycles != usage.total_cycles:
                    raise HTTPException(422, "Completion identity, time or measured counters do not match the actual work")
                evidence = conn.execute(select(records).where(records.c.id == completion.evidence_ref, records.c.kind == "evidence", records.c.organisation_id == tenant)).mappings().first()
                if not evidence or not evidence["data"].get("checksum") or not evidence["data"].get("provenance"):
                    raise HTTPException(422, "Completion evidence needs tenant-owned content integrity and provenance")
                completed.append(completion.model_copy(update={"state": "Under Review", "reviewed_by": None, "evidence_version": evidence["version"]}))
            order.completion, order.actual_end = completed, max(utc(item.completed_at) for item in completed)
            # A returned/replaced completion is a new review checkpoint. Earlier
            # signatures cannot approve changed work or changed source evidence.
            row["data"] = {**row["data"], "_maintenance_approvals": []}
        elif payload.target == "Released":
            if user["role"] != "reviewer" or user["id"] not in row["data"].get("reviewer_ids", []) or user["id"] in {row["created_by"], row["data"].get("_prepared_by"), *(item.performed_by for item in order.completion)}:
                raise HTTPException(403, "Assigned independent maintenance reviewer required")
            if not order.completion or {item.task_id for item in order.completion} != set(order.task_ids):
                raise HTTPException(422, "Complete task evidence is required before independent maintenance release")
            reviewer_person = conn.execute(select(records).where(records.c.organisation_id == tenant, records.c.kind == "personnel", records.c.status == "Approved", records.c.data["user_id"].as_string() == user["id"])).mappings().first()
            try:
                qualified_reviewer = MaintenanceTechnician.model_validate({**(reviewer_person["data"].get("maintenance_technician", {}) if reviewer_person else {}), "id": reviewer_person["id"] if reviewer_person else "missing", "version": reviewer_person["version"] if reviewer_person else 1})
            except ValueError:
                raise HTTPException(422, "Maintenance reviewer needs a current typed qualification record")
            qualifications = qualified_reviewer.qualifications
            if any(scope not in qualifications or utc(qualifications[scope]) <= current for scope in required):
                raise HTTPException(422, "Maintenance release reviewer lacks current task-specific qualification evidence")
            evidence_versions = {}
            for completion in order.completion:
                evidence = conn.execute(select(records).where(records.c.id == completion.evidence_ref, records.c.kind == "evidence", records.c.organisation_id == tenant, records.c.status == "Approved")).mappings().first()
                if not evidence or not evidence["data"].get("_approvals"):
                    raise HTTPException(422, "Completion evidence needs independent review before maintenance release")
                evidence_versions[evidence["id"]] = evidence["version"]
            order.completion = [item.model_copy(update={"evidence_version": evidence_versions[item.evidence_ref]}) for item in order.completion]
            decision_snapshot = snapshot_hash({"work_order_id": order.id,
                "aircraft_id": order.aircraft_id, "aircraft_version": aircraft_row["version"],
                "configuration_id": order.configuration_id, "program_id": program.id, "program_version": program.version,
                "task_ids": order.task_ids, "required_qualifications": order.required_qualifications,
                "technician_id": order.technician_id, "technician_record_version": order.technician_record_version,
                "facility_id": order.facility_id, "facility_record_version": order.facility_record_version,
                "actual_start": stamp(order.actual_start) if order.actual_start else None,
                "actual_end": stamp(order.actual_end) if order.actual_end else None,
                "completions": [item.model_dump(mode="json") for item in order.completion],
                "evidence_versions": evidence_versions})
            approvals = list(row["data"].get("_maintenance_approvals", []))
            if user["id"] in {item["actor_id"] for item in approvals}:
                raise HTTPException(409, "Reviewer already signed this maintenance checkpoint")
            for approval in approvals:
                if approval.get("input_snapshot") != decision_snapshot:
                    raise HTTPException(409, "Signed maintenance work or evidence changed; return completion for a fresh review")
                prior_actor = conn.execute(select(users).where(users.c.id == approval["actor_id"], users.c.organisation_id == tenant, users.c.role == "reviewer", users.c.disabled == 0)).mappings().first()
                prior_person = conn.execute(select(records).where(records.c.id == approval.get("reviewer_personnel_id"), records.c.organisation_id == tenant, records.c.kind == "personnel", records.c.status == "Approved")).mappings().first()
                prior_qualifications = prior_person["data"].get("maintenance_technician", {}).get("qualifications", {}) if prior_person else {}
                if not prior_actor or not prior_person or prior_person["version"] != approval.get("reviewer_personnel_version") or any(scope not in prior_qualifications or utc(datetime.fromisoformat(prior_qualifications[scope].replace("Z", "+00:00"))) <= current for scope in required):
                    raise HTTPException(409, "An earlier maintenance reviewer's authority or qualification changed; obtain fresh review")
            approvals.append({"actor_id": user["id"], "at": now(), "reason": payload.reason, "input_snapshot": decision_snapshot, "evidence_versions": evidence_versions, "program_version": program.version, "aircraft_version": aircraft_row["version"], "reviewer_personnel_id": reviewer_person["id"], "reviewer_personnel_version": reviewer_person["version"]})
            row["data"] = {**row["data"], "_maintenance_approvals": approvals}
            required_reviews = 2 if os.getenv("AIRSPACE_REQUIRE_TWO_REVIEWERS", "false").lower() == "true" else 1
            if len(approvals) < required_reviews:
                order.version = row["version"] + 1
                row.update(version=order.version, updated_at=now(), data={**row["data"], "work_order": order.model_dump(mode="json")})
                conn.execute(update(records).where(records.c.id == work_order_id, records.c.organisation_id == tenant, records.c.version == payload.expected_version).values(**row))
                store.snapshot(conn, row)
                store.append_audit(conn, tenant, user["id"], "maintenance.reviewed", {"work_order_id": work_order_id, "version": row["version"], "state": "Under Review", "required_reviewers": required_reviews})
                return row
            order.completion = [item.model_copy(update={"state": "Released", "reviewed_by": user["id"]}) for item in order.completion]
            # Work completion releases this order, but does not automatically
            # clear unrelated defects, charge a battery or approve a flight.
            aircraft_row["data"] = {**aircraft_row["data"], "maintenance_completions": [*aircraft_row["data"].get("maintenance_completions", []), *(item.model_dump(mode="json") for item in order.completion)]}
            aircraft_row.update(version=aircraft_row["version"] + 1, updated_at=now())
            conn.execute(update(records).where(records.c.id == order.aircraft_id, records.c.organisation_id == tenant).values(**aircraft_row))
            store.snapshot(conn, aircraft_row)
            from .dispatch import suspend_dispatch_for_aircraft, suspend_dispatch_dependencies
            suspend_dispatch_for_aircraft(conn, store, tenant, order.aircraft_id, user, "Maintenance evidence changed; new aircraft readiness review required")
            suspend_dispatch_dependencies(conn, store, tenant, order.aircraft_id, user, "Maintenance evidence changed; new aircraft readiness review required")
            order.aircraft_record_version = aircraft_row["version"]
        elif payload.target == "Under Review" and user["role"] != "fleet_manager":
            raise HTTPException(403, "Maintenance preparer must request independent review")
        elif payload.target == "Cancelled" and user["role"] != "fleet_manager":
            raise HTTPException(403, "Fleet manager must cancel an unstarted work order")
        order.state, order.version = payload.target, row["version"] + 1
        row.update(status=payload.target, version=row["version"] + 1, updated_at=now(), data={**row["data"], "work_order": order.model_dump(mode="json"), "_maintenance_decision": {"actor_id": user["id"], "at": now(), "reason": payload.reason, "meaning": "Recorded maintenance workflow; separate aircraft readiness approval and operating permissions remain required"}})
        conn.execute(update(records).where(records.c.id == work_order_id, records.c.organisation_id == tenant, records.c.version == payload.expected_version).values(**row))
        store.snapshot(conn, row)
        store.append_audit(conn, tenant, user["id"], "maintenance.transition", {"work_order_id": row["id"], "version": row["version"], "state": payload.target, "aircraft_id": order.aircraft_id, "configuration_id": order.configuration_id, "reason": payload.reason})
    return row
