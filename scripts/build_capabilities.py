"""Maintain explicit capability and paragraph-level acceptance status."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
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
add('Fleet, personnel, qualifications and controlled procedures','Implemented','api.py;frontend','tests/test_api.py;frontend/verification','Generic versioned records; detailed battery charging/maintenance campaigns incomplete')
add('CP-SAT scheduling and separately implemented verifier','Verified','scheduler.py','tests/test_scheduler.py','No full recurrence/charging model; timeout and optimum reported distinctly')
add('Transactional schedule reservation and cancellation','Verified','planning.py','tests/test_planning.py','SQLite concurrency tested; PostgreSQL must be separately verified')
add('Internal dispatch release and actual flight execution','Not Implemented','assess_dispatch is advisory only','tests/test_operations.py','Reservation does not grant release; aircraft command capability absent by design')
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
(ROOT/'capabilities.json').write_text(json.dumps({'schema_version':'1.0','release':'0.1.0-rc.1','stable_release':False,'features':items},indent=2),encoding='utf-8')

mapping={1:('README.md;capabilities.json','release-evidence/release-gates.json'),2:('SAFETY_BOUNDARY.md;api.py','tests/test_api.py'),3:('AGENTS.md;PLAN.md;STATUS.md','release-evidence/commands.jsonl'),4:('workflows.py;planning.py','tests/test_security_workflows.py'),5:('api.py;storage.py;compose.yaml','tests/test_api.py'),6:('regulatory.py;sources/catalogue.json','tests/test_regulatory.py'),7:('regulatory.py;neural.py','tests/test_regulatory.py'),8:('neural.py;scripts/train_neural.py','models/runs;release-evidence/neural-cpu-verification.json'),9:('worker.py','tests/test_security_review.py'),10:('api.py;workflows.py;evidence.py','tests/test_api.py'),11:('operations.py','tests/test_operations.py'),12:('operations.py;frontend','tests/test_operations.py'),13:('connector registry;permission records','docs/data-provider-setup.md'),14:('scheduler.py;planning.py','tests/test_scheduler.py;tests/test_planning.py'),15:('monitoring.py;operations.py','tests/test_operations.py'),16:('monitoring.py;operations.py','tests/test_operations.py'),17:('versioned aircraft/personnel/qualification records','frontend/verification'),18:('operations.py;commercial records','tests/test_operations.py'),19:('connector registry;source ingestion','SOURCE_REGISTER.md'),20:('identity.py;storage.py;THREAT_MODEL.md','tests/test_security_review.py'),21:('frontend/src','frontend/verification'),22:('tests;scripts/verify_release.py','release-evidence'),23:('PLAN.md;STATUS.md','release-evidence/commands.jsonl'),24:('README.md;docs;scripts/package_release.py','release-evidence/release-gates.json'),25:('publication workflow','publication/status.json'),26:('STATUS.md;RELEASE_NOTES.md','release-evidence'),27:('SOURCE_REGISTER.md','sources/checks')}
path=ROOT/'REQUIREMENTS_TRACEABILITY.csv'
with path.open(newline='',encoding='utf-8') as file: reader=csv.DictReader(file);fields=reader.fieldnames;rows=list(reader)
for row in rows:
    section=int(row['section']);impl,evidence=mapping.get(section,('',''))
    row.update(implementation=impl,tests_evidence=evidence,release_status='Partial — Requires Acceptance Review',limitations='Paragraph remains original acceptance baseline. See capabilities.json for precise implemented, verified, external-access and unimplemented scope; no full-paragraph acceptance inferred from partial tests.')
with path.open('w',newline='',encoding='utf-8') as file: writer=csv.DictWriter(file,fields);writer.writeheader();writer.writerows(rows)
print(json.dumps({'capabilities':len(items),'baseline_requirements':len(rows),'full_acceptance_claimed':False}))
