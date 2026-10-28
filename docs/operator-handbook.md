# Operator handbook

System Lab Airspace Operations · 0.2.0-rc.1 engineering candidate

Use the application to prepare, review and coordinate civilian UAS operations using actual records and evidence. Regulatory applicability, safety review, legal operating basis, site/airspace permission, U-space authorisation, internal readiness, pilot acknowledgement and actual execution remain separate decisions. The software does not issue permissions, activate a provider or control an aircraft. Read the [safety boundary](../SAFETY_BOUNDARY.md), [coverage statement](regulatory-coverage.md) and [known limitations](known-limitations.md) before operational adoption.

The six screenshots below show the actual application in an **isolated software-review workspace**. Operational registers are empty; the agent view contains a genuine public-source question and recorded software execution receipts. No aircraft, customers, flights, maintenance history or authority approvals were fabricated to populate these views. Screenshots demonstrate interface behaviour, not certification or operational acceptance.

## Access, roles and revisions

Sign in with an administrator-provisioned organisation account. Check the organisation reference and current role in the header. Timestamps use UTC unless an explicit local IANA time zone is supplied. Mission windows require `Z` or a numeric offset; a date alone is not an operating window.

| Role | Typical work |
| --- | --- |
| Administrator | Provision identities and configure services. Administrator access does not grant reviewer authority. |
| Regulatory | Prepare cases, permission/evidence records and country evidence; conduct permitted research and authorisation/site/country workflows. |
| Reviewer | Independently review assigned records, with current qualifications where required; perform admitted review and coordination actions. |
| Planner | Prepare intended missions, teams and scheduling proposals; perform admitted site, maintenance, coordination and research checks. |
| Pilot | Prepare mission/incident records and acknowledge the exact assignment linked to that pilot's actual personnel account. |
| Fleet manager | Maintain aircraft, personnel, measured utilisation, maintenance and sharing records. Maintenance start/completion also requires the assigned technician identity. |
| Incident coordinator | Maintain incident ownership, facts and actions; acknowledge permitted operational alerts. |
| Analyst | Maintain deployment scenarios and perform permitted source research. |
| Viewer | Inspect accessible records without write or approval authority. |

The server also checks record state, assignment, independence, qualifications and versions. Disabled controls commonly indicate a role or state restriction. Do not share accounts to obtain another person's approval.

Open saved items through their workspace inspector and **Open controlled record**, or the relevant specialised editor. Provenance identifies creator, timestamps and revision. Assign actual reviewer accounts before review. The creator or last preparer cannot approve that revision; organisation policy may require two independent reviewers. Material edits create a draft and reset approval. Save before transitions and controlled exports.

Mission/workflow drafts and generic record edits have scoped browser-session retention. This is not durable storage or backup; not every wizard automatically saves. Save intended records before leaving them. Signing out clears application session drafts. After a concurrent-edit error, reopen the current revision and compare changes rather than bypassing the version check.

## Starting an empty workspace

1. Have an administrator provision the actual contributors and independent reviewers. Establish operating procedures, data rights and integration responsibilities.
2. Inspect **Regulatory Library** coverage. Add genuine evidence and controlled procedures in **Safety Evidence**.
3. Record actual aircraft configurations, personnel, qualifications and source-defined maintenance in **Fleet & Personnel**. Registration alone does not establish readiness.
4. Add operator-provided candidate sites and routes in **Airspace & Sites**, preserving source limitations and vertical references.
5. Create a user-entered intended mission and connect its actual proposed resources, authorisation and country evidence.
6. Prepare scheduling baselines only when readiness, permissions, suitable source data and approved policies exist. Missing prerequisites remain blockers.

## Sources, authorisations and safety evidence

In **Regulatory Library**, inspect identity, legal status, version, licence, retrieval evidence and limitations. Research a question using the jurisdiction and relevant operation date; select the SORA edition where needed. Keep exact quotations and resolvable anchors separate from machine interpretation and reviewed interpretation.

The shipped EASA corpus is a **retrieval-date snapshot**, not an approved historical/future applicability timeline. Current release material was retrieved on 27 October 2026. Historical/future questions abstain without separately date-reviewed versions. Selecting the snapshot date permits source research; it does not prove every returned provision is current, applicable or sufficient. Luxembourg/Italy material still needs national reconciliation. Registered countries are not validated packs. See [coverage](regulatory-coverage.md).

In **Safety Evidence**, register lawful provenance, content and limitations, source anchors and configuration. Identify design, simulation, laboratory, field and correspondence evidence accurately. After creating a draft, upload a non-empty attachment up to **1,000,000 bytes**; the server calculates its digest. Externally controlled evidence needs its own genuine checksum and provenance. A machine annotation is derived data, not an observation or expert approval.

In **Authorisations**, record jurisdiction, legal route, overall authorisation owner, separate airspace workstream owner, ConOps, aircraft configuration and methodology edition. Link requirements/evidence, inspect missing inputs, assign independent reviewers and use controlled transitions. Completing the airspace section does not complete the overall application.

Keep operational authorisation, declaration/LUC basis, site/airspace permission and U-space authorisation distinct, with appropriate issuer, scope, conditions, dates and evidence. Internal case approval issues none of them. Submission requires actual receipt evidence or an explicitly documented manual-submission record; an export does not submit anything. **Download controlled case JSON** and **Download controlled case report (HTML)** retain versions, provenance and missing inputs without invented signatures or stamps.

The SORA workbench separates editions and runs only implemented source-bound calculations. Missing inputs remain incomplete; partial support does not issue a complete SORA determination. A traffic display or sensor claim is not certified Detect and Avoid evidence.

## Mission Control

Mission Control loads saved mission, resource, case and alert records. Counts describe those records. The map lacks a live traffic/operational-zone feed; an empty overlay is not an empty sky.

Use **Plan a mission** as a planner or pilot. Enter the intended civilian operation, countries in route order, explicit start/end times and limitations. Select saved aircraft, routes and personnel only when they are actual proposed resources. Leave unknown duration/payload values empty. **Save mission proposal** records an intention, not a flight.

Open the mission and use **Open controlled record** for revisions or additional documented inputs. **Fleet & Personnel → Mission teams** assigns actual personnel. Assignment does not establish qualification, availability or duty-policy validity; those receive separate checks.

![Mission Control in an empty operational review workspace](../publication/media/mission-control.jpg)

## Airspace & Sites

Use **Add intended site** or **Plan route**. Select proposed points or enter exact operator-provided longitude/latitude. Coordinates are WGS 84 in longitude/latitude order. A route needs at least two intended waypoints. Add jurisdiction, source identifiers, uncertainty and limitations, then **Save draft geometry**. The map/list inspector and **Open controlled record** provide inspection and controlled revision/review.

Natural Earth is general cartographic context, not an authoritative aeronautical chart, geozone, terrain or obstacle service. Candidate and reviewed geometry remain distinct. The display projection supplies no safety-distance calculation; backend screening uses geodesic calculations and preserves missing-coverage findings.

- **AGL/AMSL:** record a known height/altitude in metres and its source. Any required terrain conversion still needs review.
- **FL:** the guided form exposes **Pressure flight level (FL)** and stores `flight_level` separately. Never enter a flight-level number in an altitude-in-metres field. Pressure-to-terrain/sea-level conversions are not silently performed.
- **Unknown:** preserve the missing datum. Do not select a favourable reference to clear a finding.

Unknown references, unsupported conversions, stale zones and absent terrain/population/obstacle data prevent a complete assessment. Drawn geometry proves neither legal feasibility nor terrain clearance/containment.

![Airspace and Sites with geographical context and explicit missing operational layers](../publication/media/airspace-planning.jpg)

## Fleet, qualifications and maintenance

In **Fleet & Personnel → Aircraft**, register a real identity/configuration, evidence, restrictions and recorded serviceability. **Maintenance & readiness** inspects saved programme, utilisation and work. **Inspect and edit aircraft baseline** opens controlled editing/review. Material changes need renewed readiness review.

Use **Record measured aircraft utilisation** for actual timestamp, total flight seconds, total cycles and measurement evidence. Blank counters are missing, not zero. Enter zero only when measured as zero. Saving creates a draft aircraft revision, not a flown mission or serviceability approval.

In **Personnel**, preserve real roles, availability, qualification evidence/expiry and applicable organisation duty policy. Bind the personnel record to its correct user account for technician or pilot actions. Typed technician/facility and scheduling baselines may need an authorised import or documented structured fields. A name, administrator role or generic qualification label does not replace current task-specific evidence. No universal UAS duty limit is supplied.

In **Maintenance**, create a programme from actual aircraft/operator instructions: source task identifiers/versions, qualification scopes and calendar, flight-second and/or cycle triggers. No operational interval defaults are supplied. Link evidence, assign independent reviewers through the programme record, complete review and link the matching aircraft configuration.

Create a work order from saved tasks, real window, source-defined duration and work instruction. In the draft, **Assign independent maintenance reviewers before scheduling**. The controlled lifecycle is:

`Draft → Scheduled → In Progress → Work Complete → Under Review → Released`

Scheduling requires actual reviewed technicians/facilities, availability/capacity and current aircraft/programme versions. Only the assigned technician's actual account starts/completes work. Completion needs actual time, matching measured counters and genuine evidence. An assigned, qualified reviewer independent of preparer/performer releases it, including a second reviewer where configured. Only unstarted work may be cancelled. Dedicated transitions replace ordinary work-order editing after Draft; escalate blocked assignments rather than bypassing the lifecycle.

Work release does not charge a battery, clear unrelated defects, authorise a flight or automatically restore aircraft readiness. **Assess maintenance readiness** uses saved evidence; leave optional forecast use blank when unknown. See [fleet contracts](fleet-and-cross-border.md).

![Fleet and maintenance without fabricated aircraft or maintenance history](../publication/media/fleet-maintenance.jpg)

## European coordination and sharing

**Country evidence register** stores reviewed national-source scope and genuine instruments. Catalogue entries start **Registered**, with no default permission. EU Member States, EASA states outside the EU and other national frameworks remain distinct. Geography or EASA membership does not establish EU applicability.

In **Country segments & handovers**, select the intended mission and identify registration country, current aircraft/route version and interval. Add country segments with actual reviewed pack versions, legal routes, instruments, local conditions, mitigations and source-freshness evidence. Border transitions need accountable people, procedures, acknowledgement and contingency coordination. **Assess segment readiness** produces findings; saving retains a proposed mission plan and resets review.

The preserved Article 13 reference distinguishes:

| Evidence | Meaning |
| --- | --- |
| `host_confirmation` | A separate host-authority confirmation concerning local mitigations for the operational-authorisation route. |
| `declaration_home_receipt` and `host_declaration_submission` | Home declaration/confirmation plus documented operator provision of required material to the host. The submission records home origin, actual host recipient and provision timestamp; no second host-issued receipt/approval is implied. |
| `luc_terms` and `luc_host_notification` | Underlying terms and documented provision of required information to the host, with actual recipient, timestamp and delivery evidence, without inventing a host response. |

For the two operator-submission kinds the form asks for **Accountable operator / document provider**, **Origin / registration country**, **Recipient host country** and **Actual provision time**. Internal approval reviews evidence; it issues no authority instrument. National requirements, later changes and applicability need qualified review. [Cross-border guidance](fleet-and-cross-border.md) identifies the preserved source and unavailable online recheck.

In **Shared fleet**, an authorised owner prepares terms for its real reviewed aircraft/version and specifically known counterparty organisation. Terms cover dates, countries, routes, purposes, responsibility, insurance and data-sharing rights. The private draft remains owner-only. The owner offers it; the named counterparty independently accepts/rejects it. No external message is sent.

Acceptance transfers no operating authorisation, qualification, U-space approval or command authority. The operator needs its own reviewed alias and operational records; owner private evidence is not exposed. Revocation blocks relevant internal readiness and preserves physical reservation exclusions until explicit reconciliation/cancellation. It does not withdraw a provider request or terminate a flight.

![Separate country segments, evidence and bilateral sharing in European Coordination](../publication/media/european-coordination.jpg)

## Scheduling, pilot acknowledgement and dispatch

Use **Build schedule proposal** as a planner. The guided builder consumes complete saved scheduling baselines on mission, aircraft, personnel and site records. IDs or registration cards alone are insufficient. **Advanced complete input snapshot** also accepts a documented operator input conforming to the displayed `ScheduleRequest` contract. Do not invent missing weather, battery budgets, limits, qualifications, permissions or provider data.

Supply the local IANA time zone and input configuration revision. The timeline shows UTC and saved assignments only. CP-SAT handles hard constraints; an independently implemented verifier checks results. Feasible, proven optimal, infeasible and unknown/timeout outcomes differ. A commercial preference cannot trade away a hard constraint.

Open a saved run and assign independent reviewers while it is a draft. An assigned reviewer records review and reservation after current persisted versions/conflicts are rechecked. Material changes may require a new proposal. Cancellation is an explicit audited resource action.

1. The actual assigned pilot account records **assigned-pilot acknowledgement** for its future reserved assignment and exact schedule version.
2. A separate assigned reviewer requests **internal dispatch release**, rechecking current resources, instruments, country evidence, maintenance, qualifications, safety review, approved dispatch procedure/policy and exact pilot acknowledgement. Organisation policy supplies lead time/validity; no universal operational window is invented.
3. Inspect the receipt, expiry and version bindings. **Internally Released** is scope- and time-limited. This action leaves provider activation **Not Performed** and flight execution **Not Recorded**.

No scheduling, pilot or dispatch control uploads routes or sends take-off, landing or flight-termination commands.

![UTC scheduling and saved solver-run workspace without illustrative bookings](../publication/media/scheduling.jpg)

## Agent Workflows and owned companions

Choose an admitted research, authorisation, site, scheduling, maintenance, cross-border or sharing task. The application consumes the in-house general-purpose `systemlab_agentic` coordination core with aviation-specific tools/gates; it does not claim a proprietary trading engine performs UAS operations. See [agent contracts](agent-contracts.md).

Enter objective, jurisdiction, relevant operation date and selected saved records. The server freezes accountable identity and context versions. Source queries remain bounded by installed snapshot dates/coverage. Do not change dates to imply unsupported temporal coverage.

Explicitly choose the computation path:

| Mode | Behaviour |
| --- | --- |
| Local causal language model | The configured pinned causal model generates admitted next-tool proposals. Missing files/capacity produce visible blocking or deferral. |
| Local FLAN language model | Separately identified constrained-candidate likelihood selection, rather than free-form generative planning. |
| Native deterministic workflow | An explicitly chosen deterministic controller. Specialist retrieval tools may still use configured neural components. It is not labelled an LLM-controller run. |

The optional literal-language student is experimental and unpromoted for legal decisions; its signal is not interpretation or expert ground truth. A causal-model outage does not silently switch to native mode.

Inspect **Execution budget and experimental model**. Budgets cover steps, model calls, elapsed time, model/tool deadlines and retries; the contract shows allowed ranges. These are software controls, not aircraft limits. **Create scoped workflow** prepares the record. Its preparer uses **Start bounded workflow**; the worker continues admitted steps to review, blocking or a limit.

Inspect actual tool receipts, model identities, source versions, input snapshots, timestamps, failures and artifacts. **Pause**, **Resume** and **Cancel** are versioned controls for the preparer or reviewer. Resumed work may require the preparer to start it again. A running tensor/tool call may return before late output is discarded; cancellation is not hard real-time flight control.

**Needs Review** is not approval. Curate useful source-linked output through the appropriate controlled case/evidence record and reviewer process. Agents cannot approve themselves, reserve resources, release maintenance/dispatch, submit to authorities, send correspondence or operate aircraft.

Indigo/Coral use the owner's actual distributed presentation renderer and artwork under reserved rights, separately from the new Apache-2.0 adapter. **Motion on/off** pauses all companions; system reduced-motion preferences force renderer motion off. Optimised image/CSS fallback retains state text/usability when the module, image or WebGL path is unavailable. Animation is neither model-training nor aviation-performance evidence.

![Actual public-source research receipts and accountable review checkpoint](../publication/media/agent-orchestration.jpg)

## Alerts, incidents and deployment planning

Inspect recorded alerts from Mission Control and their controlled records. Pilot, incident-coordinator or fleet-manager users can record admitted acknowledgements with rationale/current version. Acknowledgement does not prove resolution; sent, delivered, acknowledged and completed are separate facts.

Authorised telemetry imports use the documented API/provider path, not a universal live connection. Live and Historical Replay remain separate. Imports need actual tenant aircraft/mission references, lawful-use attestation and source rights. Monitoring uses approved policies rather than invented thresholds. A telemetry record does not activate the map's disconnected traffic/zone layers. See [provider setup](data-provider-setup.md).

In **Incidents**, record actual facts/uncertainties, event time, command owner, affected records, configuration and approved procedure. The deterministic workspace preserves timeline/evidence. Checklists come only from current approved operator/aircraft procedures. Escalate missing procedures/contact sources to the accountable person; never substitute model-generated flight-critical instructions. External authorities/emergency services are not contacted automatically. Reporting duties/deadlines need jurisdiction-specific review; see [incident management](incident-management.md).

In **Deployment Planning**, keep approval blockers beside dated commercial inputs. Distinguish documented facts, customer figures and analyst assumptions; record units, currencies, capacity and provenance. Forecast formulas remain inspectable. Blank financial inputs remain missing; commercial scores cannot override safety or permission blockers.

## Missing inputs and blocked actions

| Finding | Next action |
| --- | --- |
| Empty registers | Add actual records or explicitly intended proposals under an authorised role. Do not manufacture activity. |
| Unsupported source date/jurisdiction | Inspect coverage, legal status, methodology and snapshot dates. Obtain a separately reviewed version; retain abstention until then. |
| Unknown datum or absent layer | Obtain lawful suitable data and a reviewed reference/conversion. Keep the assessment incomplete meanwhile. |
| Missing maintenance usage/baseline | Record actual measurements, instruction versions, completion evidence and matching configuration. Blank counters do not mean unused aircraft. |
| Technician/pilot/reviewer control unavailable | Check account-to-person binding, assignment, role, qualification, independence and state. Escalate gaps; do not share credentials. |
| No reviewer on a scheduled work order | Escalate to maintenance owner/administrator. This release assigns reviewers in Draft and forbids ordinary editing afterwards. |
| Incomplete/infeasible schedule | Inspect solver/verifier findings and current windows/baselines. Revise intentions or obtain evidence; do not relax a hard constraint for utilisation. |
| Changed revision/stale approval | Reopen, compare provenance/audit and repeat the appropriate review. Old approvals do not carry across material changes. |
| Model/budget/reconciliation blocker | Preserve receipts, inspect the named dependency and obtain administrator support. Start a new/reconciled scope when required; no silent controller substitution occurs. |
| Stale/failed connector | Inspect last successful check, coverage and permitted purpose in Administration. Silence establishes neither unchanged rules nor favourable operating conditions. |
| Missing incident procedure/contact | Escalate through the approved organisation process. Preserve unresolved information and actual notification status. |
