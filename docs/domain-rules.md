# Deterministic domain rules and integration contracts

Engineering version: operations-1.1.0 and schedule-1.0.0. Source checks: 27 October 2026. This document describes implemented software behaviour. It is not a statement of operational acceptance or validated legal applicability.

## Contracts

The canonical contracts are Pydantic models in `backend/airspace/operations.py` and `backend/airspace/scheduler.py`. Unknown fields, nonfinite numbers, naive timestamps and invalid coordinate ranges are rejected. Generate their JSON schemas using `Model.model_json_schema()`. The application API must supply the authenticated actor instead of trusting an actor submitted by a client, validate tenant-owned references, authorise writes and persist both input and result. Passing a standalone calculation is never an approval.

| Tool | Input model | Result and boundary |
| --- | --- | --- |
| `solve_schedule` | `ScheduleRequest` | CP-SAT proposal, solver status, objective/bound, exact input SHA-256, assignments, independent verifier result |
| `verify_schedule` | `ScheduleRequest`, proposal dictionary | Independently recomputed constraints and findings; does not call the solver candidate-building code |
| `approve_schedule` / `cancel_schedule` | Persistent store, record version, authenticated principal and rationale | Same-tenant transactional resource reservation/release; independent review policy and current evidence binding; no external flight action |
| `assess_dispatch` | `DispatchRequest` | Blocked or eligible for internal release review; never creates approval or reservation |
| `assess_sora` | `RiskRequest` | Version/configuration/ConOps-bound evidence matrix; missing evidence and reuse rejection reasons |
| `screen_site` | `SiteScreenRequest` | Point/zone spatial findings with source versions, temporal and vertical limitations |
| `evaluate_telemetry` | `TelemetryRequest` | Accepted records, quarantined observations, latest verified state, stale/missing alerts |
| `incident_checklist` | `IncidentRequest` | Approved matching procedure steps or an explicit missing-procedure limitation; acknowledgement/escalation state |
| `calculate_economics` | `EconomicsRequest` | Decimal scenario calculations, formulas, input provenance, missing inputs and regulatory stage blockers |
| `connector_catalog` | None | Capability declarations; no fabricated real connection test |

Consequential results include actor, creation time, input snapshot, deterministic rule version and model version (`null` for these engines). Retain complete snapshots, including permission revisions, source versions and accountable evidence. These engines have no aircraft command API, external messaging tool, generative-model dependency or ability to issue an authority instrument.

## Scheduling

The implemented solver is OR-Tools CP-SAT 9.14.6206. It uses optional intervals for alternative aircraft, personnel and availability-window assignments, disjunctive resource constraints, cumulative site capacity, linear flight-time budget and duty constraints, dependencies and exact manual locks. No commercial reward can relax a hard constraint. The soft objective is the sum of start-time offsets; it is a planning convenience, not a claim of fleet economics optimality.

Inputs are proposed operations, not flown missions. Required inputs include mission windows and durations, payload, reviewed route/configuration versions, applicable qualification scopes, reviewed legal operating basis, explicitly reviewed U-space applicability, permission instruments and accepted weather/airspace evidence. Missing required records return `INCOMPLETE`. An explicitly unsuitable, expired, suspended, ambiguous or out-of-scope prerequisite prevents an assignment. A competent-authority instrument, site/airspace instrument, U-space response, internal safety review, dispatch review and pilot acknowledgement have distinct kinds and permitted issuer types.

An aircraft record includes its configuration, serviceability, availability, maintenance validity, verified remaining flight-time budget, turnaround and evidence references. Battery budget is a conservative aggregate flight-time budget for the input readiness snapshot. The solver does not invent battery degradation or charging performance. Maintenance and charging can be represented by gaps in availability; charging does not automatically replenish the budget. A new verified readiness snapshot is required to account for replenishment. Battery assignment and charger allocation optimisation are not implemented.

Personnel provide scoped qualification expiries, availability, already accrued duty and an approved duty-policy reference. A request represents one duty episode. The time between the earliest and latest assignment counts, including idle gaps. Policy-driven rest resets require separate episodes; no universal UAS duty limit is assumed. Site capacity conservatively occupies the full mission interval. Separate launch and recovery queue models are not implemented.

The verifier recomputes durations, windows, locks, configuration/payload/readiness, maintenance, resource availability, qualifications, permission scope and expiry, accepted feed validity, aircraft/person overlaps, battery totals, elapsed and active duty, site capacity, predecessor completion, revisions and input digest. It runs before a solver proposal is returned as verified. The API must still atomically validate current database records and reserve resources before an internal approval; a solver result itself has no reservation effect.

The persistence layer now serialises reservation decisions with a tenant lock. It validates current approved resource snapshots and issuer receipt versions, applies configured independent second review before reserving anything, prevents duplicate proposed-operation reservations and checks cumulative battery/duty budgets across schedules using the same readiness revision. Site capacity and resource conflicts are transactionally checked. Explicit cancellation releases internal reservations and retains its decision trail; rebooking requires a new current proposal and review. Cancellation never withdraws a provider authorisation or sends an aircraft command. PostgreSQL execution remains a separate deployment-verification requirement; the concurrent persistence tests executed on SQLite.

`OPTIMAL` means the solver proved optimality for this exact supplied model/objective; `FEASIBLE` does not. `UNKNOWN` means no feasible solution or infeasibility proof was obtained before interruption/time limit. `INFEASIBLE` is reserved for a model contradiction or no admissible resource candidate. Inputs are bounded to 100 missions/resources of each type, 20,000 resource/window candidates, a one-year horizon and 30 solver seconds. One solver worker and seed zero are recorded for reproducibility. See the [official CP-SAT status documentation](https://developers.google.com/optimization/cp/cp_solver/) and [interval scheduling documentation](https://developers.google.com/optimization/scheduling/job_shop).

Schedule times have explicit UTC offsets and whole-second precision. The local IANA timezone is retained. The same local clock reading with different DST offsets is a different instant. Naive local timestamps are rejected. All reservations use half-open intervals, so a resource ending at an instant can begin another assignment at that instant if its approved turnaround is zero.

## Spatial screening

Coordinates are explicitly EPSG:4326 longitude/latitude. Distances use the WGS84 ellipsoid through pyproj 3.7.2/PROJ, including antimeridian handling. Degrees are never treated as metres. The [pyproj Geod documentation](https://pyproj4.github.io/pyproj/stable/api/geod.html) describes its geodesic interface.

The current tool screens a candidate point against time-valid circle/polygon records. Circles are limited to 100 km radius. Polygon edges follow geodesics, are densified to at most 250 m segments and projected into a query-centred azimuthal equidistant coordinate system. The query must be within 100 km of all polygon vertices. A 2 m numerical envelope is added to source precision and position uncertainty. Results near a boundary remain uncertain. This is a bounded advisory geometry implementation, not a certified airspace intersection engine. Self-crossing/degenerate rings produce unresolved findings. Complex multi-polygons and complete route/corridor/terrain-volume analysis are not implemented.

AGL and AMSL are distinct. Conversion requires terrain elevation, terrain evidence and terrain uncertainty; uncertainty intervals are propagated conservatively. Missing vertical data and pressure-based levels produce `Unknown`; the engine does not invent pressure/terrain conversions. Missing authoritative zone, airspace, population, obstacle, terrain, site-access or emergency evidence is listed. An empty overlay does not mean unrestricted airspace. Research-only data cannot establish operational feasibility.

## SORA and Detect and Avoid evidence

The workbench isolates SORA 2.0 and 2.5. Approved evidence can be reused only when the selected methodology, aircraft configuration and ConOps version match and an accountable reviewer is recorded. It distinguishes design claims, simulation, laboratory/field evidence, authority records and document review. Its requirement matrix covers ConOps, ground risk/mitigation, initial and residual air risk, strategic and tactical mitigation, SAIL evidence, containment and operational safety objectives.

A complete SORA calculator, GRC/ARC derivation, OSO compliance and Detect and Avoid assurance calculations are **not implemented or domain-validated**. Risk-class fields remain null even if all evidence categories are populated. Completing this matrix is not a complete SORA assessment. No invented threshold or learned judgement fills that gap.

The optional `calculation_inputs` object implements three narrow SORA 2.5 calculations: SAIL lookup from reviewed final GRC/residual ARC, BVLOS TMPR lookup, and adjacent-ground outer distance. They are bound to official June 2026 source checksum `0d35166d374084346d6f4b3ac962102ef75d13963ab8d1d0360cb988ab85dc54`, a declared accountable input-review reference and the exact edition. Every result remains `Requires Domain Review` and is separate from risk-class determinations. The canonical [AMC1 Article 11 section](https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-unmanned-aircraft-systems?erules-id=ERULES-1963177438-24086) provides S.4.6 Table 6 (local blocks b0423–b0426), S.4.7.3 SAIL rows (b0461–b0467), and S.4.8.3(b)(i) adjacent-distance bounds (b0486–b0489). The SAIL text refers to Table 7 while its caption reads Table 3; the implementation preserves that source discrepancy. The distance formula is `min(35000, max(5000, maximum_speed_m_s * 180))` metres. It does not determine containment robustness. These calculations do not infer input ARC/GRC or assess compliance.

EASA's [June 2026 Easy Access Rules page](https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-unmanned-aircraft-systems) identifies its 30 June 2026 revision and SORA 2.5 incorporation. [ED Decision 2025/018/R](https://www.easa.europa.eu/en/document-library/agency-decisions/ed-decision-2025018r) is the edition-specific source entry. The historical 2.0 entry is [ED Decision 2019/021/R](https://www.easa.europa.eu/en/document-library/agency-decisions/ed-decision-2019021r). These source entries do not decide national transition arrangements or validate a particular case. Those remain explicit applicability-review requirements. Exact table/paragraph transcription and qualified verification remain release limitations.

## Telemetry and incidents

Telemetry ingestion preserves event time, receipt time, source version, source precision, event identity and explicit Live/Historical Replay mode. Duplicate source identifiers with the same source observation are ignored; receipt timestamps can differ on redelivery. Conflicting identifier content, future/inconsistent timestamps, equal-time contradictory observations and nonincreasing source sequences are quarantined. Delayed older observations are archived without moving the latest verified position backwards. Source subsecond precision is retained. Replay cannot become live state. Positions are never extrapolated.

Staleness requires an approved operator policy and threshold source. Without one, freshness is `Unknown`; there is no arbitrary telemetry-loss threshold. Expected aircraft with no verified event produce missing-data findings. The source acceptance flag is explicit. This is cooperative telemetry with incomplete coverage; the display and alerts make no certified Detect and Avoid claim.

Incident steps come only from an approved, unexpired procedure matching incident type and aircraft configuration. An absent procedure produces an empty checklist and escalation to the accountable person. The engine never generates flight-critical instructions. A missing acknowledgement policy is visible; a configured overdue acknowledgement produces `Escalation Required`. No external contact is sent. Sent, delivered, acknowledged and completed states must be preserved separately by integration workflows. Jurisdiction-specific occurrence reportability/deadline rules remain unimplemented pending reviewed sources.

## Commercial planning and connectors

Economics uses Python Decimal and requires explicit currency, period, provenance, evidence/date and all required numerical inputs. Missing fields remain null. Formulas for revenue, cost, contribution, cost/mission, utilisation and break-even are returned with results. Zero denominators remain undefined; an absent positive margin has no finite break-even result. Scenarios are labelled forecasts and uncertainty is not invented. A regulatory blocker retains a blocked stage gate regardless of margin.

Connector declarations distinguish contract capability from real integration testing. Operational telemetry and provider services ship Not Connected. There is no universal European U-space API implementation. EUROCONTROL's [EAD page, EAD Basic section](https://www.eurocontrol.int/service/european-ais-database) restricts Basic data to general purposes and prohibits operational use; the connector explicitly records `operational_use_allowed: false`. Public access never implies redistribution rights.

## Executed verification

Command executed on 27 October 2026 from the product directory:

```powershell
$env:PYTHONPATH='backend'
.venv/Scripts/python.exe -m pytest tests/test_operations.py tests/test_scheduler.py -q
```

Observed result: **39 passed in 12.27 seconds**. This includes property-generated constraint combinations and geodesic symmetry checks, DST offset distinctions, missing/expired/scoped permissions, unsuitable feeds, configuration changes, battery/duty constraints, resource conflicts, locked double-booking, independent-verifier tampering, SORA edition mismatch, unknown vertical references, research-only feeds, duplicate/out-of-order/quarantined telemetry, replay separation, missing incident procedures and Decimal formulas. Artificial records exist only in isolated software tests. These results do not constitute aviation certification or live operational acceptance.

Subsequent executed combined validation, including SORA source-oracle tests, persistent reservations and adversarial API checks, returned **74 passed in 17.66 seconds**. Additional reservation/cancellation tests and their observed results are recorded in `security-review.md`; this initial result is preserved as an execution record rather than presented as the final suite size.

The final combined rerun after cancellation integration returned **77 passed, 2 dependency deprecation warnings in 16.47 seconds**.
