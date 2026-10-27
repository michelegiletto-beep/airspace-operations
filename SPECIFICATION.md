System Lab Airspace Operations

Master implementation specification for Codex

1. Mandate and required outcome

You are the lead software engineer and delivery owner for System Lab. Build a complete, installable software product for organisations developing and operating commercial unmanned aircraft services across Europe. Use the working product name System Lab Airspace Operations unless an existing approved System Lab naming convention requires a different descriptive name.

The product must support the work of an EU regulatory airspace specialist and the adjacent teams needed to turn an intended operation into an authorised, scheduled, monitored and auditable service. Its scope includes regulatory intelligence, site assessment, BVLOS authorisation workflows, SORA evidence, airspace integration, Detect and Avoid assurance, authority engagement, U-space coordination, operational scheduling, fleet readiness, situational awareness, emergency management and commercial deployment planning.

Build the software, not merely a proposal describing it. Deliver working frontend and backend applications, persistent databases, functioning ingestion and analysis pipelines, a genuine neural component, deterministic operational rules, scheduling optimisation, tests, documentation, deployment packages and downloadable release artifacts.

The intended users include regulatory specialists, heads of regulatory approvals, safety managers, operational planners, remote pilots, fleet managers, incident coordinators, engineering teams and business development leaders. Support enterprise logistics, distribution, inspection and other legitimate civilian UAS operations without naming or implying affiliation with any particular prospective customer.

Everything authored for the product must be in English: interface, documentation, reports, comments, release notes and model cards. Preserve original source documents in their original languages and clearly identify English translations. Do not alter the legal meaning or status of source material to satisfy the interface language requirement.

2. Non-negotiable constraints

Do not create a static HTML demonstration, a landing page presented as an application, a chat window with decorative dashboards, or disconnected screens containing hard-coded results. A web interface is appropriate only when backed by real application services and persistent workflows.

Do not fabricate flights, customers, authorisations, telemetry, regulations, regulatory interpretations, aircraft performance, commercial results, credentials, integrations, training results or validation evidence. Missing information must remain visibly missing. Empty states must explain what is needed without manufacturing activity.

Do not use slogans, taglines, promotional filler, invented testimonials, customer logos, AI-themed branding, sparkle symbols, ornamental neural-network graphics, stock dashboard illustrations or exaggerated performance claims. Use restrained System Lab typography rather than inventing a logo.

Do not confuse software verification with aviation certification, authority approval or operational acceptance. Autonomous development and release of software do not confer authority to approve real flights, issue regulatory permissions, provide certified separation services or operate an aircraft.

Do not claim that all European law has been collected, every jurisdiction is supported, a system is certified or a model is reliable without evidence matching the exact claim. Coverage must be measurable, versioned and inspectable.

3. Execution protocol

Inspect the actual workspace, repository instructions, available tools, permissions, infrastructure and computing resources before making changes. Preserve unrelated System Lab projects and existing production services. Reuse components only after checking their ownership, licences, architecture and suitability.

Work autonomously on reversible engineering decisions. Research primary sources, implement features, run the application, inspect behaviour, repair failures and continue through release preparation. Do not stop after writing a plan or scaffolding a repository.

Use parallel engineering and adversarial review when supported. Keep separate responsibilities for implementation, security review, domain-rule review and verification, but do not describe multiple model instances as independent professional certification.

Create durable project files: SPECIFICATION.md, AGENTS.md, PLAN.md, STATUS.md, DECISIONS.md, SOURCE_REGISTER.md, DATA_REGISTER.md, THREAT_MODEL.md, SAFETY_BOUNDARY.md and REQUIREMENTS_TRACEABILITY.csv. Preserve this specification as the original acceptance baseline. Plans must implement it rather than quietly redefine it. This persistent specification and milestone approach follows the long-task workflow described in the official Codex guidance. [R5] (OpenAI Developers)

Give each requirement an identifier and connect it to implementation, tests, evidence and release status. Record commands actually executed, outcomes, blockers and decisions. After each milestone, run the relevant validation suite and repair regressions before proceeding.

Use available resources thoroughly, but do not assume unlimited compute, API access, money or unattended execution. Respect budgets, rate limits, permissions and service terms. Do not purchase infrastructure, accept paid subscriptions or incur substantial external charges without an authorised budget. When interrupted, leave a reproducible checkpoint and an exact next-action record.

4. Product boundary and authority model

The default product is an operational management and decision-support platform. It is not an autopilot, a certified Detect and Avoid system, a U-space service provider or an air traffic control system.

Represent at least these decisions separately: regulatory applicability assessment; safety-case review; competent-authority operational authorisation or another applicable legal operating basis; site and airspace permissions; U-space flight authorisation when required; internal dispatch readiness; pilot acknowledgement; actual flight execution.

Do not collapse these into a single green approval badge. A U-space flight authorisation and an operational authorisation from the competent authority are distinct instruments. Preserve their separate issuers, scopes, conditions and evidence. [R2] (EASA)

Use explicit states such as Draft, Missing Evidence, Under Review, Submitted, Approved, Rejected, Expired, Suspended and Superseded, with separate workflow-specific state machines where needed. An internal approval must never be displayed as an authority-issued permission.

Enforce permissions and approval transitions on the server. Safety-significant decisions require an accountable authorised person and, where configured, an independent second reviewer. Agents may prepare recommendations and evidence but cannot grant themselves permissions or approve their own work.

Default external aircraft integrations to read-only telemetry. Do not add take-off, landing, route-upload or flight-termination commands to the ordinary agent toolset. Any future command integration requires a separately engineered and reviewed operational boundary, not a hidden API switch.

5. Technical architecture

Build a maintainable modular system with explicit domain boundaries. Prefer a modular backend and separately deployable workers over unnecessary microservice proliferation.

A suitable default is a typed React and TypeScript operations interface; a Python API backend; PostgreSQL with PostGIS and a supported vector-search extension; object storage for source documents and evidence; a durable workflow engine; an optimisation worker; an inference worker; and an authenticated event stream for live updates. Select maintained implementations after checking their current documentation and compatibility. Record alternatives and decisions rather than selecting tools for novelty.

Separate the regulatory library, authorisation cases, spatial planning, scheduling, telemetry ingestion, incident management and commercial analysis domains. Define versioned APIs and data contracts. Use transactional updates, idempotency keys, bounded retries, durable jobs and an outbox or equivalent consistency mechanism for important events.

Provide a local self-hosted deployment that works without System Lab hosting, plus a documented managed-deployment path. Package services as containers with health checks, pinned dependencies, migrations, configuration validation, backups and restoration procedures. A desktop wrapper is not a substitute for implementing these services.

Core entities must include organisations, users, roles, jurisdictions, sources, document versions, obligations, interpretations, aircraft configurations, sites, routes, operational volumes, missions, resources, personnel qualifications, risk assessments, evidence, permissions, authorisation cases, schedules, telemetry events, alerts, incidents, corrective actions and approval records.

Provide an administrative command-line interface for environment checks, ingestion, verification, training, evaluation, export, backup and restoration. Publish a machine-readable OpenAPI contract. Include a usable local inference path and state its hardware requirements; enable hosted model providers only through explicit configuration and approved data-processing arrangements.

Every consequential result must identify its input snapshot, rule version, source versions, model version where applicable, timestamp and accountable actor.

6. Authoritative regulatory library

Implement a searchable, versioned library of authoritative regulatory and operational material. Begin with EUR-Lex, EASA, relevant national aviation authorities, official aeronautical information providers and other competent public bodies. Use primary sources rather than commercial summaries as the legal foundation.

Seed the source register with the current applicable versions of Regulation (EU) 2018/1139; Regulations (EU) 2019/947 and 2019/945; the U-space framework, including Regulations (EU) 2021/664, 2021/665 and 2021/666; associated AMC and GM; relevant SORA, PDRA, standard-scenario and LUC material; and national procedures, geographical zones and authorisation conditions.

The EASA UAS Easy Access Rules published on 30 June 2026 incorporate SORA 2.5 through ED Decision 2025/018/R. Treat that as a researched starting point, not a permanently current version. Recheck for subsequent changes at implementation and release. Preserve historical methodologies for existing cases rather than mixing editions. [R1] (EASA)

Distinguish binding legislation, amendments, acceptable means of compliance, guidance, standards, national procedures, authority correspondence, operator policies and proposals. For directives, track relevant national transposition rather than assuming identical implementation. Never enforce a consultation document as adopted law.

Assess the applicability of privacy, information-security, cybersecurity, occurrence-reporting, product and AI requirements to the actual product and customer operating model. Include GDPR, relevant Part-IS provisions, the AI Act and other applicable frameworks in this assessment without claiming that every framework applies identically to every operator.

For every source, store issuer, canonical identifier, jurisdiction, language, legal status, publication date, entry-into-force date, applicability dates, retrieval time, version, amendment relationships, licence, checksum and provenance. Preserve article, annex, paragraph, table and page structure.

Prefer official structured XML or HTML. For PDFs, preserve layout and source anchors; use OCR only where necessary and flag uncertain extraction. Parse downloads in an isolated environment. Restrict fetching to approved locations and prevent embedded instructions or malicious documents from obtaining execution privileges.

Maintain a coverage matrix for every supported jurisdiction and topic. Start with a European foundation and deeply validated Luxembourg and Italy packs. Make other country packs installable. Keep UK rules and permissions separate from EU applicability. A listed country is not a validated country.

7. Regulatory question answering and change intelligence

Implement hybrid retrieval combining lexical search, neural embeddings and reranking. Apply organisation permissions, jurisdiction, legal status and relevant dates before retrieval results can influence an answer. Include tables and annexes, not only prose paragraphs.

Answers must state the question, applicable operational context, supporting provisions, conclusions, unresolved uncertainties, missing inputs and required review. Every material regulatory claim needs a resolvable source anchor. Separate quoted source content, machine interpretation and reviewer-approved interpretation.

Support questions about a future operation date and historical questions about the rules that applied when an earlier decision was made. Do not silently answer both using the latest text.

Detect contradictory, superseded and incomplete material. Abstain from unsupported conclusions and explain the missing evidence. Do not express legal confidence as an invented percentage. Treat retrieved documents and user uploads as untrusted data, not instructions to the agent.

Build a change-impact workflow from a source amendment to affected obligations, interpretations, templates, cases, sites, routes, schedules and operating procedures. Generate review tasks with accountable owners. Regulatory changes must not silently overwrite an approved safety case or operational procedure.

Support saved searches, monitored topics and scheduled ingestion. Show last successful checks, upstream failures and coverage gaps. Notification silence must not be interpreted as proof that nothing changed.

8. Genuine neural component and LLM-assisted training

Implement a real, inspectable neural subsystem. Do not label keyword matching, prompt templates or an external chat API as a custom-trained neural network.

Use pretrained neural retrieval as a baseline. Add a compact trainable model for defensible tasks such as document classification, obligation extraction, query routing, evidence relevance or requirement-to-evidence matching. Select the task and architecture through measured experiments. Keep operational constraint enforcement outside the learned model.

Implement an LLM-assisted teacher and student pipeline using real, lawfully usable source passages and, where available, genuine published questions or consented operational queries. The teacher may annotate, classify and extract from these records. It must not invent source facts, approvals, flight histories, test results or operational incidents.

Label teacher-produced annotations as machine-generated derived data, not real-world observations or human-validated ground truth. Store source spans, teacher identity, prompt version, output schema, validation results and review status. Check source licences, model licences and provider terms before training or redistribution.

Validate generated annotations against source text. Quarantine unsupported labels and contradictions. Use qualified human-reviewed examples for safety-significant evaluation where available; do not represent another model’s agreement as expert review.

Prevent leakage by splitting evaluation sets by source family, document version, time and task, not merely random text chunks. Include superseded law, unsupported questions, conflicting jurisdictions, tables, missing evidence and adversarial instructions in evaluation.

Compare the student against lexical, pretrained retrieval and deterministic baselines. Measure extraction accuracy, retrieval quality, citation support, abstention, calibration where meaningful, latency and resource use. Report sample sizes, uncertainty, dataset composition and failure cases.

Deliver training code, configuration, lineage, evaluation results and a versioned artifact for every training run actually completed. Publish a candidate as experimental when it has not earned production promotion. Never manufacture benchmark results or declare training complete when only a script exists.

Do not train operational prediction models without suitable real operational records. Ship those capabilities disabled when evidence is insufficient. Keep current legal truth in the versioned library, not solely in model weights. Require reviewed promotion, rollback and drift monitoring; prohibit uncontrolled online self-modification.

9. Agentic workflow system

Build durable agents for regulatory monitoring, evidence collection, case preparation, site screening, scheduling proposals, incident summarisation and commercial analysis. Use specialised agents only where they improve reliability over a simpler deterministic workflow.

Every action must pass through typed tools with explicit permissions and input validation. Persist workflow state, dependencies, evidence references, retries, deadlines, failures and approval checkpoints. Support cancellation, pause, resume and recovery after worker or model failure.

Separate read-only research, internal draft creation, operational-state changes and external actions. Require explicit scoped approval for authority submissions, external correspondence and safety-significant changes. Pre-authorised internal alerts may execute under a documented notification policy.

Use bounded execution, tool allowlists, egress controls, spending limits and circuit breakers. Prevent agents from modifying their own approval requirements, deleting audit records, broadening credentials or treating instructions found in a regulation as trusted commands.

Show concise action records and decision justifications, not hidden chain-of-thought. The application must remain usable when all generative-model services are unavailable.

10. Authorisation case management

Implement the complete lifecycle from proposed operation and initial applicability assessment through evidence development, internal review, submission, authority questions, revisions, decision recording, operating conditions, renewals and closure.

Represent the ownership boundary between the airspace workstream and the owner of the overall operational authorisation. Coordinate engineering, safety, operations and regulatory contributors without suggesting that completing the airspace section completes the whole application.

Capture the ConOps, aircraft configuration, operating geography, limitations, personnel, procedures, mitigations, evidence and approvals as version-controlled records. Provide requirements matrices, missing-evidence queues, review comments, controlled document releases and professional submission exports.

Maintain separate workflows for applicable authorisation, declaration, PDRA, standard-scenario and LUC routes. Do not force every operation into the same process. Luxembourg’s published SORA application guidance is an example of a national application source that must be reconciled with current requirements rather than copied blindly. [R3] (dac.gouvernement.lu)

Reuse approved evidence and templates only when their assumptions, jurisdiction, aircraft version and operational scope still match. Record why reuse is acceptable. Material changes must trigger impact assessment and the appropriate reapproval workflow.

Track authority correspondence, requests for information, deadlines, dependencies, responsible owners and decision history. Never invent an authority response or label a package submitted without a real receipt or an explicitly recorded manual submission.

11. SORA and Detect and Avoid evidence workbench

Implement version-specific SORA support covering the applicable ground-risk and air-risk steps, strategic mitigations, residual air risk, tactical mitigation requirements, containment, adjacent-area considerations, SAIL and operational safety objectives.

Give the air-risk workstream particular depth: operational environment, airspace structure, traffic evidence, assumptions, exposure, strategic restrictions, tactical mitigation evidence, limitations and traceability to the relevant ConOps.

Implement published calculations and decision tables as reviewable deterministic code with exact source references and regression tests. Do not invent thresholds, interpolate missing regulatory criteria or substitute LLM judgement for an undefined rule. Missing mandatory inputs must produce an incomplete assessment, not a favourable result.

Keep an evidence chain connecting requirements, aircraft configuration, sensor performance, software version, detection and tracking claims, latency, coverage, failure behaviour, test records and reviewer decisions. Separate design claims, simulation results, laboratory evidence and field evidence.

Do not present the platform’s traffic display or proximity alerts as certified Detect and Avoid performance. Do not claim that cooperative surveillance provides complete knowledge of surrounding traffic. Treat unobserved and uncertain traffic as uncertainty, not as an empty sky.

Support evidence exports, test-campaign planning, findings, remediation and configuration-change impact. Require valid rights to any paid technical standards rather than downloading or republishing restricted material without permission.

12. Site assessment and spatial planning

Build a GIS workbench for candidate facilities, launch and recovery locations, delivery areas, routes, operating volumes and relevant contingency areas. Support authoritative geographical zones, airspace structures, restrictions, obstacles, terrain, population datasets and sensitive locations where lawful data is available.

Model geometry in space and time. Preserve coordinate reference systems, vertical references, units, uncertainty and source precision. Handle AGL, AMSL, pressure-based levels and terrain conversions explicitly. Do not perform safety-relevant distance calculations by treating latitude and longitude as a flat metric grid.

Evaluate candidate sites against regulatory feasibility, operating constraints, access permissions, data coverage, ground and air risk evidence, connectivity, weather exposure, emergency arrangements and relevant local requirements.

Produce explainable findings with source-linked limitations and unresolved dependencies. A route generated by the planner is a proposal, not proof of legal or operational feasibility. Display candidate routes separately from approved routes.

13. Authority, ANSP and U-space coordination

Create stakeholder records, engagement plans, meeting notes, actions, owners, deadlines, agreements, responsibilities and controlled correspondence. Include consultant assignments, scope, budget, deliverables and quality review for application peaks.

Implement provider-specific integration adapters from actual documented interfaces. Record jurisdiction, provider coverage, supported services, access requirements, certification evidence where relevant and interface version. Do not invent a universal European authorisation API.

Account for the U-space framework’s network identification, geo-awareness, flight-authorisation and traffic-information services, and additional weather or conformance services where required. Verify current designation and local requirements rather than assuming U-space exists everywhere. [R2] (EASA)

Track the real provider lifecycle for requests, responses, activation, changes, withdrawal and completion. Preserve request IDs, signed or otherwise verifiable responses where available, conditions and timestamps. Map provider states explicitly rather than forcing different providers into misleading equivalence.

Internal conflict checking is advisory and must not impersonate the provider’s authorisation service. National access permissions, operational authorisations and provider approvals remain distinct prerequisites.

14. Flight and resource scheduling

Implement a genuine scheduling engine using constraint programming, mathematical optimisation or another justified method. Do not ask an LLM to improvise an executable flight schedule.

Model aircraft availability and configuration, maintenance, battery condition and charging, launch and recovery capacity, personnel qualifications and duty constraints, approved routes, mission windows, payload, applicable operating limits, weather suitability, airspace conditions, authorisation validity and provider availability.

Distinguish hard legal and safety constraints from soft preferences such as cost, utilisation, throughput, energy use and customer service priorities. Never trade away a hard constraint to improve a commercial objective.

Support recurring operations, rolling replanning, dependency chains, cancellation, resource conflicts, recovery after disruption and manually locked assignments. Explain infeasibility and identify missing inputs or conflicting constraints without inventing a solution.

Use transaction-safe resource reservations and recheck prerequisites immediately before internal dispatch release. Prevent duplicate bookings and stale approvals through version checks and concurrency controls. Distinguish preparation from external activation and actual flight execution.

Preserve UTC timestamps and explicit local time zones. Test daylight-saving transitions, cross-midnight duties and cross-border schedules. Store the exact input snapshot, solver configuration, run status and constraint results for reproducibility.

Use a separately implemented schedule verifier before a proposed schedule can be approved. Report a solver timeout, feasible solution and proven optimum accurately; do not claim optimality merely because the solver returned a schedule.

15. Situational awareness and monitoring

Build an operational console integrating actual mission state, authorised telemetry, aircraft health, route conformance, source freshness, weather, restrictions, provider status, resource readiness and relevant alerts.

Every displayed feed must expose its source, event timestamp, receipt timestamp, last successful update, coverage limitations and operational-use status. Historical replay must be visibly and structurally separated from live operations.

Handle duplicate, delayed, out-of-order, contradictory and missing telemetry. Preserve source precision and report stale tracks. Never smooth missing data into apparently current aircraft positions without a visible prediction label and uncertainty treatment.

Provide configurable, deterministic monitoring for operational-volume deviations, relevant airspace changes, expiring permissions, telemetry loss, degraded services and approved operating-limit exceedances. Thresholds must come from validated operator configuration or applicable evidence, not arbitrary defaults.

Include acknowledged and unacknowledged alerts, ownership, escalation, deduplication and event correlation. Test alert delivery and recovery. Avoid alarm flooding and colour-only status communication.

Keep operational alerts functional without an LLM. Generated summaries are secondary explanations of recorded events and must cite the events they summarise. The interface must not imply complete surveillance coverage or guaranteed collision avoidance.

16. Emergency and incident management

Implement incident detection, triage, command ownership, escalation, task allocation, communications records, evidence preservation, recovery tracking and post-incident review.

Support configurable incident types including lost communications, navigation degradation, unexpected airspace restrictions, severe weather, aircraft faults, battery events, suspected cyber incidents, injury or damage reports, provider outages and fleet-wide operational suspension.

Build emergency checklists from approved operator procedures and aircraft-specific documentation. Do not generate flight-critical emergency instructions from general model knowledge. Where an approved procedure is missing, show that limitation and escalate to the accountable person.

Provide a deterministic incident workspace with an event timeline, affected missions, last known verified state, assigned responders, contact sources, notification status and unresolved actions. Preserve recorded evidence with integrity controls and appropriate access restrictions.

Distinguish an alert sent, a message delivered, an acknowledgement received and an action completed. Do not contact emergency services or external authorities automatically without an explicit authorised process and a supported integration.

Support approved occurrence-reporting workflows, corrective actions, lessons learned and recurrence monitoring. Keep reportability and deadlines jurisdiction-specific and source-backed. Do not assume the same reporting rule applies to every event.

Degraded mode must retain essential contact information, approved procedures and current incident records where lawful and practical, with visible cache age. Data loss must not trigger improvised aircraft commands.

17. Fleet, personnel and operational records

Manage aircraft configuration baselines, registration evidence, maintenance status, defects, serviceability, battery history, payload compatibility and operational restrictions. Link configuration changes to affected authorisations, evidence and schedules.

Manage qualifications, training, role permissions, availability and applicable duty restrictions using real records. Do not invent universal duty-time limits for all UAS personnel. Support approved organisation policies where regulations do not supply a single rule.

Provide preflight and postflight records, discrepancy reporting, shift handovers, operational logs, controlled procedure acknowledgements and audit exports. Support attachments and electronic approvals with honest descriptions of their assurance level.

18. Business development and deployment economics

Implement a commercial planning workspace connected to the same operational and regulatory data, not a separate marketing dashboard.

Track candidate sites and markets, customer requirements, stakeholder dependencies, approval milestones, integration costs, recurring operating costs, evidence reuse, delivery capacity and deployment blockers.

Separate documented facts, customer-provided figures, analyst assumptions and calculated scenarios. Forecasts must be labelled as forecasts. Empty financial inputs must not be replaced with plausible-looking numbers.

Calculate cost per mission or delivery, resource utilisation, contribution estimates and sensitivities only when the necessary inputs exist. Show formulas, units, currencies, dates and uncertainty. Do not fabricate return on investment, demand, addressable-market size or approval timelines.

Support explainable site comparisons and stage-gate decisions. Regulatory feasibility and evidence readiness must remain visible beside commercial attractiveness. A high commercial score cannot override a safety or permission blocker.

Deliver a concise product strategy covering buyer roles, implementation responsibilities, integration partners, measurable pilot outcomes, deployment options and possible service offerings. Ground competitive or market claims in current primary evidence. Keep the downloadable core usable without a compulsory proprietary service.

19. Data connectors and the prohibition on fictitious data

Implement a connector registry with declared capabilities, authentication, licence, permitted purpose, geography, update frequency, freshness expectations, schemas and validation status. Record successful real integration tests separately from contract tests.

Prioritise real regulatory ingestion and authorised operator imports. For operational feeds, evaluate official aeronautical information, national geographical zones, suitable weather sources, U-space providers, customer telemetry, terrain and population data. Do not assume that public accessibility permits commercial redistribution or flight-planning use.

EUROCONTROL states that EAD Basic information must not be used for operational purposes. Enforce that distinction: a research-accessible feed is not automatically an operational data source. Apply the same permitted-purpose review to every provider. [R4] (eurocontrol.int)

When credentials, contracts or lawful access are unavailable, implement and test the adapter boundary but label the integration Not Connected or Not Operationally Validated. Never simulate a successful live connection. Provide controlled manual import where appropriate without misrepresenting its freshness or authority.

Production, training, replay and testing stores must be separated. Artificial inputs may be created only inside clearly isolated software tests, property-based tests or fault-injection harnesses. They must never appear as operational records, customer demonstrations, factual training evidence or measured business results.

Real historical records can support replay only when their provenance, permissions and historical status are preserved. Do not relabel them as current. A pristine installation should contain an empty operational workspace and, where licensed, actual regulatory source material, not a fictional airline.

20. Security, privacy and operational resilience

Implement enterprise authentication, least-privilege roles, tenant isolation, protected service credentials and audited administrative actions. Apply organisation boundaries to documents, embeddings, retrieval, exports, background jobs and caches, not merely to the visible interface.

Protect secrets, minimise personal data, support retention and deletion policies, and document lawful handling of sensitive operational records. Never publish private authority correspondence, customer evidence, access tokens or personal contact details in releases or public model datasets.

Address prompt injection, malicious uploads, SSRF, dependency compromise, insecure deserialisation, unauthorised tool use, retrieval poisoning, cross-tenant leakage and exfiltration. Do not enable remote model code execution by default.

Use tamper-evident audit records with tested verification, rather than claiming an ordinary editable table is immutable. Back up operational data and demonstrate restoration. Test worker crashes, database interruption, expired credentials, stale caches and network partitions.

Provide observability for API errors, workflow delays, ingestion failures, source staleness, solver runs, model failures and alert delivery. Keep personal and secret data out of logs. Define deployment-specific reliability objectives and report measured performance without presenting targets as achieved results.

21. Interface and visual design

Design a professional operational application, not a promotional website. Use compact typography, precise alignment, restrained colours, consistent spacing, clear hierarchy and deliberate information density. Reserve strong colours for meaningful states.

Primary workspaces should cover Operations, Scheduling, Airspace, Authorisations, Safety Evidence, Regulatory Library, Incidents, Fleet and Personnel, Deployment Planning, and Administration. Consolidate navigation where that improves actual workflows.

Use maps, timelines, tables, document readers and contextual panels where they serve the task. Give users direct access to evidence, timestamps and permissions. Do not populate the home screen with meaningless cards, arbitrary counters or decorative charts.

Provide keyboard navigation, accessible contrast, explicit units, readable error messages, responsive layouts and reliable table filtering. Design incident workflows for stressed users and degraded connectivity. Preserve unsaved work and make consequential actions unmistakable.

The assistant should appear as contextual assistance within real workflows, not as the entire product. Verify all visible controls against actual backend behaviour. Do not show enabled buttons for unimplemented or unavailable capabilities.

22. Validation and acceptance evidence

Define acceptance tests before claiming completion. Validate the original requirements rather than only tests written around the implementation that happens to exist.

Run unit, integration, property-based, security, end-to-end, migration, restoration and performance tests. Use independent fixtures and reference calculations for rule engines and scheduling. Exercise failures as thoroughly as successful paths.

Test at minimum: wrong-jurisdiction retrieval; superseded regulations; unsupported regulatory questions; prompt injection in uploaded documents; missing evidence; permission expiry; changed aircraft configuration; stale weather or airspace data; unknown vertical references; duplicate scheduling; concurrent approval edits; solver infeasibility; telemetry loss; provider timeout; incident escalation; model outage; and cross-tenant access attempts.

Demonstrate a complete vertical workflow using real, permissioned inputs wherever external facts are required: ingest a source, preserve a citation, associate a requirement with a real case or user-entered intended operation, identify missing evidence, generate a controlled package, run scheduling checks and preserve the decision trail. Clearly distinguish a user-entered proposed operation from an actual flown mission.

Where real operational records or provider access are missing, validate the software mechanism in an isolated test environment and state the limitation. Do not claim live end-to-end operational acceptance from mocked services, historical replay or automated software tests.

Release evidence must include actual test commands and outputs, versions, coverage of requirements, known defects, connector status, source coverage, model lineage, measured performance, security findings and deployment verification.

Block stable release for unresolved critical security defects, tenant isolation failures, fabricated operational data, untraceable regulatory claims in release examples, approval bypasses, failing core workflows or misleading certification claims. Do not waive a failed gate by renaming it a future improvement.

Use a release-candidate label when important assurance work remains. A working engineering release may be downloadable while real-world operational deployment remains blocked pending data rights, qualified review, acceptance testing and applicable permissions. State those boundaries clearly.

23. Implementation order

Deliver the work in testable increments without reducing the final product to a collection of stubs.

First establish repository governance, architecture, security boundaries, persistent storage, identity, source registers and a real regulatory ingestion pipeline.

Then complete a vertical authorisation workflow with source-grounded retrieval, evidence records, reviewer permissions, controlled exports and auditability.

Next implement spatial planning, version-specific risk support, aircraft and personnel readiness, scheduling and its independent verifier.

Then implement authorised telemetry ingestion, operational monitoring, incidents, degraded-mode behaviour and provider adapters with honest connection status.

After the foundation works, complete the trainable neural subsystem, measured comparisons, model documentation and controlled promotion. Do not postpone the entire neural requirement to a vague roadmap.

Finally complete commercial planning, usability refinement, security hardening, restoration tests, packaging, documentation and release verification. Maintain end-to-end integration throughout rather than leaving integration until the last phase.

24. Required artifacts

Deliver the complete source repository and reproducible installation instructions; container deployment files and dependency lockfiles; database migrations; versioned API documentation and integration contracts; actual regulatory source manifests; functioning workflows; training and inference code; completed experiment artifacts for runs actually executed, with explicit blockers for any required unexecuted experiments; the complete test suite; and reproducible verification commands.

Include an operator handbook, administrator handbook, data-provider setup guide, regulatory coverage statement, model cards, dataset documentation, threat model, safety-boundary statement, backup and recovery runbook, incident-management guide, release notes, known limitations, contributor guide and security-reporting policy.

Provide professional evidence and case exports without fake approval stamps or invented signatures. Include a machine-readable capability matrix identifying Implemented, Verified, Requires External Access, Requires Domain Review and Not Implemented features.

Provide a software bill of materials, third-party notices, checksums and release provenance. Use a permissive licence such as Apache-2.0 for newly created project code where ownership and dependency compatibility permit. Do not relicense existing System Lab assets, third-party documents, model weights or restricted data without rights.

25. Publication on System Lab, GitHub and Hugging Face

Prepare public downloadable releases, not only screenshots or a hosted demonstration. The downloadable package must remain usable without the System Lab website.

The user authorises publication of this new project’s releasable artifacts after the stated engineering gates pass, using existing accessible accounts and approved destinations. Verify account identity, namespace ownership and actual permissions. Do not invent repository URLs, alter unrelated projects or expose an operational customer instance.

On GitHub, publish the source, tagged release, installation instructions, verification evidence, documentation, licence, software bill of materials and downloadable assets. Verify the public release from a clean environment.

On Hugging Face, publish actual redistributable model artifacts and permitted datasets only when they exist and their rights are clear. Include model and dataset cards, lineage, intended uses, limitations and measured evaluations. These are consistent with the Hub’s model-card documentation. [R6] (Hugging Face)

A Hugging Face Space may provide a limited evaluation interface, but it must not be presented as the production operations platform. Use genuine public regulatory material or an empty workspace, never fabricated flights or sensitive customer records. Do not upload an untrained placeholder and describe it as a trained model.

On the existing System Lab site, create a sober project page identifying the software, supported scope, architecture, release status, evidence, limitations, documentation and verified download links. Preserve the site’s established identity and existing content. Do not replace the site with this project.

Separate public documentation hosting from authenticated operational deployment. Scan code, build artifacts, logs, documents and model packages for secrets and restricted material before publication.

When a destination is inaccessible, finish the releasable artifacts and publication workflow, then report the precise access blocker. Distinguish Prepared, Uploaded, Published and Independently Retrieved states. Never claim publication merely because an upload command was written.

26. Final handover

Finish with a factual delivery report identifying what was implemented, how to run it, what was actually tested, which data sources and integrations are active, whether neural training ran, which artifacts were published, and what remains blocked.

Include real artifact paths, repository locations, release versions and verified public links where available. Summarise unresolved operational-acceptance requirements separately from software defects. Do not call the whole system production-ready simply because it builds or passes unit tests.

Begin by inspecting the available environment and establishing the executable project plan. Then implement, run, verify, repair, package and publish within these boundaries. Do not stop at a plan, a mock-up or a description of future software.

27. Primary-source starting points

These sources are starting points, not a claim of complete or permanently current coverage. Recheck the latest applicable material and record the access date during implementation.

[R1] EASA UAS Easy Access Rules and SORA adoption decision

https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-unmanned-aircraft-systems

https://www.easa.europa.eu/en/document-library/agency-decisions/ed-decision-2025018r

[R2] EASA U-space rules and current regulatory register

https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-u-space-regulation-eu-2021664

https://www.easa.europa.eu/en/regulations/u-space

[R3] Luxembourg Directorate of Civil Aviation, SORA application guidance

https://dac.gouvernement.lu/en/drones/drones-let-me-fly/categorie-specifique/sora.html

[R4] EUROCONTROL European AIS Database, access and permitted-use information

https://www.eurocontrol.int/service/european-ais-database

[R5] OpenAI official Codex long-task and execution-plan guidance

https://developers.openai.com/blog/run-long-horizon-tasks-with-codex

https://developers.openai.com/cookbook/articles/codex_exec_plans

[R6] Hugging Face model-card documentation

https://huggingface.co/docs/hub/model-cards

Also verify current applicable legal text directly through EUR-Lex, national authorities and official providers. Source retrieval is not permission to republish restricted content.