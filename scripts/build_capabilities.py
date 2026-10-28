"""Maintain explicit capability and paragraph-level acceptance status."""
import csv
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION=re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT/'backend/airspace/__init__.py').read_text()).group(1)
items=[]
def add(name,status,implementation,evidence,limitation=''):
    items.append(dict(capability=name,status=status,implementation=implementation,evidence=evidence,limitation=limitation))

add('Tenant identity, role enforcement and isolation','Verified','identity.py;api.py','tests/test_api.py;tests/test_security_workflows.py','SQLite software tests; live enterprise OIDC requires acceptance')
add('Independent review and configured second reviewer','Verified','workflows.py;api.py','tests/test_security_workflows.py;tests/test_security_review.py','Internal electronic approval; no qualified signature claim')
add('Controlled records, version history and case exports','Verified','api.py;evidence.py','tests/test_api.py;tests/test_security_workflows.py','Full route-specific authority package templates remain incomplete')
add('Content-addressed evidence attachment integrity','Verified','evidence.py','tests/test_security_review.py','1MB per upload; object-store backup is separate')
add('HMAC audit chain and SQLite restoration','Verified','storage.py;cli.py','tests/test_api.py','Requires private key and off-host checkpoint; not immutable storage')
add('PostgreSQL/PostGIS/pgvector deployment','Implemented','compose.yaml;deploy/database.Dockerfile;migrations','SQL dialect generation only','Docker/PostgreSQL unavailable here; extensions and production queries not executed')
add('Primary-source downloads and structured ingestion','Verified','regulatory.py;scripts/import_easa_xml.py','release-evidence/isolated-source-parser.json;sources/checks','Direct EUR-Lex requests blocked; no complete legal coverage')
add('EU regulatory foundation currentness reconciliation','Requires Domain Review','sources/catalogue.json;sources/corpus.json','SOURCE_REGISTER.md;docs/regulatory-coverage.md','9,833 extracted passages; snapshot-only temporal coverage')
add('Luxembourg deeply validated country pack','Requires Domain Review','sources/catalogue.json','sources/coverage.json','Published DAC material retrieved; current SORA and national reconciliation incomplete')
add('Italy deeply validated country pack','Requires Domain Review','sources/catalogue.json','sources/coverage.json','ENAC material retrieved; national procedures/geozones/conditions not fully validated')
add('Filtered lexical, pretrained embedding and reranked retrieval','Verified','regulatory.py;neural.py','tests/test_regulatory.py;release-evidence/retrieval-evaluation.json','Eight real title-target proxy queries; no legal-QA accuracy claim')
add('Historical and future legal applicability conclusions','Not Implemented','regulatory.py date filters abstain','tests/test_regulatory.py','Verified historical/applicability corpus absent; fail closed')
add('Source-grounded autonomous regulatory interpretation','Not Implemented','source_answer returns quotations and review requirement','tests/test_regulatory.py','No unsupported conclusions or invented legal confidence')
add('Change-impact task preparation','Verified','regulatory.change_impact;api controlled revisions','tests/test_regulatory.py','Full transitive dependency graph and scheduled monitoring assurance incomplete')
add('Durable bounded internal job execution','Verified','worker.py;api.py','tests/test_api.py;tests/test_security_review.py','External submissions and correspondence have no execution tool')
add('SORA2.0/2.5 evidence compatibility workbench','Verified','operations.py','tests/test_operations.py','Full SORA risk classification/compliance remains incomplete')
add('Published SORA2.5 SAIL/TMPR/adjacent-area subset calculations','Verified','operations.py','tests/test_operations.py;docs/domain-rules.md','Exact source anchors; requires qualified methodology applicability/domain review')
add('Complete SORA methodology and DAA assurance acceptance','Requires Domain Review','operations.py;versioned evidence records','SAFETY_BOUNDARY.md','No complete GRC/ARC/SAIL determination or certified DAA claim')
add('Geodesic candidate-site screening and vertical references','Verified','operations.py','tests/test_operations.py','No authoritative basemap, full route generation or obstacle-clearance acceptance')
add('Fleet, personnel, qualifications and controlled procedures','Implemented','api.py;frontend','tests/test_api.py;frontend/verification','Detailed aircraft-specific maintenance and qualified work-order release added in 0.2; full charging/recurrence and real operator acceptance remain incomplete')
add('CP-SAT scheduling and separately implemented verifier','Verified','scheduler.py','tests/test_scheduler.py','No full recurrence/charging model; timeout and optimum reported distinctly')
add('Transactional schedule reservation and cancellation','Verified','planning.py','tests/test_planning.py','SQLite concurrency tested; PostgreSQL must be separately verified')
add('Accountable internal dispatch release and pilot acknowledgement','Verified','backend/airspace/dispatch.py;coordination_api.py','tests/test_dispatch.py;tests/test_postgres_coordination.py','Provider activation and actual execution remain separate and not performed; no aircraft command integration')
add('Read-only authorised telemetry import and deterministic freshness','Implemented','monitoring.py;operations.py','tests/test_operations.py','Manual import boundary; no accepted live vendor feed; integration persistence checks pending')
add('Alerts, accountable acknowledgement and event integrity','Implemented','monitoring.py','tests/test_operations.py;frontend/verification','External alert delivery/escalation transport not connected')
add('Incident record, approved checklist and degraded export','Implemented','monitoring.py;operations.py;frontend','tests/test_operations.py;frontend/verification','Interactive offline mode and jurisdiction reporting automation incomplete')
add('Provider-specific U-space network interfaces','Requires External Access','connector registry;permission contracts','docs/data-provider-setup.md','No documented contracted provider or credentials supplied; no live network adapter claimed')
add('Weather, terrain, population and operational aeronautical feeds','Requires External Access','connector and manual-import boundaries','docs/data-provider-setup.md','Permitted purpose and operational acceptance required; EAD Basic research-only')
add('Local trainable neural student and completed lineage','Verified','neural.py;models/runs/explicit-shall-20261027-4','release-evidence/neural-cpu-verification.json;docs/model-card.md','Literal shall-language routing; inferior to deterministic baseline, experimental and not promoted')
add('Human-validated neural/legal evaluation and time-version holdout','Requires Domain Review','training split/evaluation code','docs/dataset-card.md','No human-labelled ground truth; one snapshot per source family; semantic teachers failed')
add('Operational prediction model','Not Implemented','Disabled','docs/model-card.md','No suitable real operational records; not trained')
add('Connected deployment economics and formulas','Verified','operations.py;commercial records;frontend','tests/test_operations.py;frontend/verification','Conditional forecasts only; no demand/ROI/approval-time evidence inferred')
add('Enterprise privacy/retention automation and compliance assessment','Requires Domain Review','docs/legal-applicability.md;THREAT_MODEL.md','docs/administrator-handbook.md','Automatic erasure/retention not implemented; actual deployment applicability requires counsel')
add('Accessible authenticated operations interface','Verified','frontend/src','frontend/verification','Browser verification scope recorded separately; no blanket accessibility certification')
add('Container build, restoration and resilience at production scale','Requires External Access','Dockerfile;compose.yaml;recovery runbook','release-evidence/release-gates.json','No Docker/PostgreSQL runtime here; no measured production SLO or external pentest')
add('Public downloadable release','Implemented','scripts/package_release.py;publication workflow','release/package-result.json','Publication state recorded separately; no invented URLs')
add('Complete original master specification acceptance','Not Implemented','SPECIFICATION.md;REQUIREMENTS_TRACEABILITY.csv','release-evidence/release-gates.json','Candidate is substantial engineering implementation; baseline remains unmet in documented areas')
add('Local generative LLM orchestration of actual specialist tools','Verified','backend/airspace/orchestration.py;worker.py','release-evidence/v0.2.0-rc.1/actual-ui-workflow.json;causal-comparison.json;tests/test_orchestration.py','Two source-title proxy questions; no legal-QA quality or speed advantage established; independent review required')
add('Reusable domain-neutral multiagentic core','Verified','backend/systemlab_agentic;airspace/orchestration.py','tests/test_orchestration.py;docs/multiagentic-contract-mapping.md','Fresh shared implementation aligned with the in-house programme; no transferred domain qualification')
add('Pause, resume, cancellation and revocation-safe model workflow','Verified','backend/airspace/orchestration.py;coordination_api.py;worker.py','tests/test_revision_integration.py;tests/test_orchestration.py','Cooperative inference cancellation; process isolation/hard preemption remains deployment work')
add('Owned animated companion presentation runtime','Verified','frontend/public/vendor/systemlab-companion;frontend/src','frontend/verification/0.2.0-rc.1;publication/media','Existing five byte-identical presentation files; reserved rights; WebGL activation, reduced motion and static fallback are separate from inference')
add('Aircraft-specific maintenance, completion evidence and independent release','Verified','backend/airspace/fleet.py;coordination_api.py','tests/test_fleet.py;tests/test_revision_integration.py','Intervals and limitations come from actual operator/aircraft evidence; no universal defaults')
add('Constrained maintenance scheduler and separate verifier','Verified','backend/airspace/fleet.py','tests/test_fleet.py','Requires real technician/facility/task inputs; proposed plan is not a serviceability release')
add('European country segments, handovers and Article 13 instrument distinctions','Verified','backend/airspace/europe.py;tests/references/article13-2026.json','tests/test_europe.py;docs/fleet-and-cross-border.md','50 geographical registrations are not 50 validated legal packs; STS/LUC documented host provision differs from operational-authorisation confirmation')
add('Bilateral aircraft sharing and physical global reservation ledger','Verified','backend/airspace/sharing.py;planning.py;storage.py','tests/test_sharing.py;tests/test_postgres_coordination.py','Consent is not transfer of operational permission; PostgreSQL concurrency result is recorded separately')
(ROOT/'capabilities.json').write_text(json.dumps({'schema_version':'1.0','release':VERSION,'stable_release':False,'features':items},indent=2),encoding='utf-8')

mapping={1:('README.md;capabilities.json','release-evidence/release-gates.json'),2:('SAFETY_BOUNDARY.md;api.py','tests/test_api.py'),3:('AGENTS.md;PLAN.md;STATUS.md','release-evidence/commands.jsonl'),4:('workflows.py;planning.py','tests/test_security_workflows.py'),5:('api.py;storage.py;compose.yaml','tests/test_api.py'),6:('regulatory.py;sources/catalogue.json','tests/test_regulatory.py'),7:('regulatory.py;neural.py','tests/test_regulatory.py'),8:('neural.py;scripts/train_neural.py','models/runs;release-evidence/neural-cpu-verification.json'),9:('worker.py','tests/test_security_review.py'),10:('api.py;workflows.py;evidence.py','tests/test_api.py'),11:('operations.py','tests/test_operations.py'),12:('operations.py;frontend','tests/test_operations.py'),13:('connector registry;permission records','docs/data-provider-setup.md'),14:('scheduler.py;planning.py','tests/test_scheduler.py;tests/test_planning.py'),15:('monitoring.py;operations.py','tests/test_operations.py'),16:('monitoring.py;operations.py','tests/test_operations.py'),17:('versioned aircraft/personnel/qualification records','frontend/verification'),18:('operations.py;commercial records','tests/test_operations.py'),19:('connector registry;source ingestion','SOURCE_REGISTER.md'),20:('identity.py;storage.py;THREAT_MODEL.md','tests/test_security_review.py'),21:('frontend/src','frontend/verification'),22:('tests;scripts/verify_release.py','release-evidence'),23:('PLAN.md;STATUS.md','release-evidence/commands.jsonl'),24:('README.md;docs;scripts/package_release.py','release-evidence/release-gates.json'),25:('publication workflow','publication/status.json'),26:('STATUS.md;RELEASE_NOTES.md','release-evidence'),27:('SOURCE_REGISTER.md','sources/checks')}
mapping[9]=('backend/systemlab_agentic;backend/airspace/orchestration.py;worker.py','tests/test_orchestration.py;tests/test_orchestration.py;release-evidence/v0.2.0-rc.1/actual-ui-workflow.json')
mapping[14]=('backend/airspace/scheduler.py;planning.py;fleet.py;dispatch.py','tests/test_scheduler.py;tests/test_planning.py;tests/test_dispatch.py;tests/test_fleet.py')
mapping[17]=('backend/airspace/fleet.py;sharing.py;coordination_api.py;frontend/src','tests/test_fleet.py;tests/test_sharing.py;frontend/verification/0.2.0-rc.1')
path=ROOT/'REQUIREMENTS_TRACEABILITY.csv'
with path.open(newline='',encoding='utf-8') as file: reader=csv.DictReader(file);fields=reader.fieldnames;rows=list(reader)
for row in rows:
    
    if not row['requirement_id'].startswith('ASO-'): continue
    section=int(row['section']);impl,evidence=mapping.get(section,('',''))
    row.update(implementation=impl,tests_evidence=evidence,release_status='Partial â€” Requires Acceptance Review',limitations='Paragraph remains original acceptance baseline. See capabilities.json for precise implemented, verified, external-access and unimplemented scope; no full-paragraph acceptance inferred from partial tests.')
# The addendum has its own IDs and never replaces the 170 original paragraphs.
revision_map={
1:('docs/revision-review.md;SPECIFICATION_V2_ADDENDUM.md','REQUIREMENTS_TRACEABILITY.csv'),
2:('backend/airspace/orchestration.py;backend/airspace/neural.py','release-evidence/v0.2.0-rc.1/actual-ui-workflow.json;release-evidence/v0.2.0-rc.1/causal-comparison.json'),
3:('backend/systemlab_agentic;docs/multiagentic-contract-mapping.md','tests/test_orchestration.py'),
4:('backend/airspace/worker.py;backend/airspace/orchestration.py','tests/test_orchestration.py;tests/test_revision_integration.py'),
5:('frontend/src;frontend/public/vendor/systemlab-companion','frontend/verification/0.2.0-rc.1;publication/media'),
6:('backend/airspace/europe.py','tests/test_europe.py;tests/references/article13-2026.json'),
7:('backend/airspace/sharing.py;backend/airspace/planning.py','tests/test_sharing.py;tests/test_postgres_coordination.py'),
8:('backend/airspace/fleet.py','tests/test_fleet.py;tests/test_maintenance_workflow.py'),
9:('backend/airspace/planning.py;backend/airspace/scheduler.py;backend/airspace/dispatch.py','tests/test_planning.py;tests/test_dispatch.py'),
10:('backend/airspace/dispatch.py;backend/airspace/coordination_api.py','tests/test_dispatch.py'),
11:('frontend/src;docs/operator-handbook.md','frontend/verification/0.2.0-rc.1;publication/media'),
12:('publication/site-project.html;publication/site-project.css','publication/status.json'),
13:('publication/github-readme-v2.md;publication/HFmodel-card-v2.md;publication/HFdataset-card-v2.md','publication/status.json'),
14:('.github/workflows/engineering.yml;deploy;compose.yaml','release-evidence/v0.2.0-rc.1;tests/test_postgres_integration.py;tests/test_postgres_coordination.py'),
15:('scripts/package_release.py;scripts/verify_archive.py','publication/status.json;release-evidence/v0.2.0-rc.1'),
16:('SPECIFICATION_V2_ADDENDUM.md;docs/agent-contracts.md','No correspondence adapter or outbound communication action')}
rows=[row for row in rows if not row['requirement_id'].startswith('ASO2-')]
for line in (ROOT/'SPECIFICATION_V2_ADDENDUM.md').read_text(encoding='utf-8').splitlines():
    if not line.startswith('| ASO2-'): continue
    cells=[x.strip() for x in line.strip('|').split('|')]
    number=int(cells[0].split('-')[1]);impl,evidence=revision_map[number]
    rows.append(dict(requirement_id=cells[0],section='Revision 2',baseline_text=cells[1],implementation=impl,tests_evidence=evidence,release_status='Implemented - verification and publication states recorded separately',limitations='See versioned evidence and publication/status.json; no full original-baseline or operational acceptance inferred.'))
with path.open('w',newline='',encoding='utf-8') as file: writer=csv.DictWriter(file,fields);writer.writeheader();writer.writerows(rows)
print(json.dumps({'capabilities':len(items),'baseline_requirements':sum(x['requirement_id'].startswith('ASO-') for x in rows),'revision_requirements':sum(x['requirement_id'].startswith('ASO2-') for x in rows),'full_acceptance_claimed':False}))
