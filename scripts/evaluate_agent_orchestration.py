"""Actual local agent/source-research comparison in an isolated database.

Questions are developer-authored regulatory research requests anchored to real
source sections, not consented operator queries or records of flown missions.
No emails, provider submissions, bookings or aircraft operations are performed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from airspace.storage import Store
from airspace.identity import provision
from airspace.orchestration import WorkflowRepository,advance_workflow,default_services


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['local_causal','native','both'],default='both')
    parser.add_argument('--query-count',type=int,choices=[1,2,3],default=2)
    parser.add_argument('--include-experimental-student',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'release-evidence'/'causal-orchestration-comparison.json')
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Output exists; choose a fresh evidence path to preserve the previous run')
    corpus_file=ROOT/'sources/corpus.json'
    corpus=json.loads(corpus_file.read_text(encoding='utf-8'))
    queries=[('UAS flight authorisation service','What source provisions describe the U-space UAS flight authorisation service?'),
             ('Cross-border operations','Which recorded Article 13 provisions concern cross-border UAS operations?'),
             ('Duration and validity of an operational authorisation','Which source provisions describe duration and validity of an operational authorisation?')][:args.query_count]
    trials=[];services=default_services()
    with tempfile.TemporaryDirectory(prefix='airspace-agent-software-verification-') as temporary:
        store=Store('sqlite:///'+str(Path(temporary)/'verification.db'),secrets.token_bytes(32));store.migrate()
        actor=provision(store,'Isolated agent software verification','research@test.invalid','regulatory',secrets.token_urlsafe(32))
        repository=WorkflowRepository(store)
        for snippet,question in queries:
            source=next(p for p in corpus if p['legal_status']=='binding_legislation' and snippet.lower() in p['title'].lower())
            target=source['anchor'].split(':')[0]
            for mode in (['native','local_causal'] if args.mode=='both' else [args.mode]):
                row=repository.create({'task_kind':'regulatory_research','objective':question,'jurisdiction':'LU','operation_date':source['valid_from'],
                                       'include_experimental_student':args.include_experimental_student,'controller_mode':mode,
                                       'budget':{'max_steps':8,'max_model_calls':10,'max_wall_seconds':1800,'model_timeout_seconds':180,'tool_timeout_seconds':300,'max_retries':1}},actor)
                start=time.perf_counter()
                while row['status'] in {'Queued','Running'}:
                    row=advance_workflow(store,row['id'],actor,row['version'],services)
                    print(json.dumps({'mode':mode,'question':question,'status':row['status'],'completed_tools':[a['tool'] for a in row['data']['artifacts']]}),flush=True)
                package=next((a['payload'] for a in row['data']['artifacts'] if a['tool']=='artifact.assemble'),{})
                citations=package.get('supporting_provisions',[])
                trials.append({'mode':mode,'question':question,'source_target':target,'operation_date':source['valid_from'],'seconds':time.perf_counter()-start,
                               'state':row['status'],'target_section_retrieved':any(c['anchor'].split(':')[0]==target for c in citations),
                               'citation_count':len(citations),'legal_conclusion_generated':package.get('conclusion') is not None,
                               'review_gate_preserved':row['data']['review_gate']['required'] and not row['data']['review_gate']['approval_granted'],
                               'workflow':row})
        audit=store.verify_audit(actor['organisation_id']);store.engine.dispose()
    result={'created_at':datetime.now(timezone.utc).isoformat(),'benchmark':'Developer-authored source-section research requests; isolated software verification, not legal or operational acceptance',
            'source_corpus_checksum':hashlib.sha256(corpus_file.read_bytes()).hexdigest(),'query_count':len(queries),'actual_model_inference_requested':args.mode!='native',
            'operational_records_created':False,'external_actions':[],'audit_verification':audit,'trials':trials,
            'limitations':['Tiny source-title-grounded research sample; not representative operator queries','Target-section matching does not establish legal-answer correctness','No comparative benefit is assumed; model failures and latency are retained','Experimental student remains unpromoted regardless of orchestration success']}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(args.output),'trials':len(trials),'states':[t['state'] for t in trials],'audit_valid':audit['valid']}),flush=True)


if __name__=='__main__':main()
