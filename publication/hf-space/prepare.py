"""Prepare a static, self-contained evidence viewer from actual project records.

Run from the full source checkout after final screenshots have been refreshed.
No model inference, credentials, network requests or operational writes occur.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RELEASE=ROOT/'release-evidence/v0.2.0-rc.1'
MODEL=ROOT/'models/runs/explicit-shall-20261027-4'
IMAGES=['mission-control.jpg','airspace-planning.jpg','fleet-maintenance.jpg','european-coordination.jpg','scheduling.jpg','agent-orchestration.jpg','agent-orchestration-detail.jpg','orchestration-pipeline.svg']


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def checksum(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def duration(start,end):return (datetime.fromisoformat(end.replace('Z','+00:00'))-datetime.fromisoformat(start.replace('Z','+00:00'))).total_seconds()


def main():
    sources={'causal-comparison.json':RELEASE/'causal-comparison.json','actual-ui-workflow.json':RELEASE/'actual-ui-workflow.json',
             'first-causal-run.json':RELEASE/'orchestration-local-20261028T092208Z.json','student-run.json':MODEL/'run.json'}
    for path in list(sources.values())+[ROOT/'publication/media'/name for name in IMAGES]:
        if not path.is_file():raise FileNotFoundError('Required actual evidence or screenshot is missing: '+str(path))
    for folder in ['data','media']:(HERE/folder).mkdir(exist_ok=True)
    for name,path in sources.items():shutil.copyfile(path,HERE/'data'/name)
    for name in IMAGES:shutil.copyfile(ROOT/'publication/media'/name,HERE/'media'/name)
    comparison=read(sources['causal-comparison.json']);actual=read(sources['actual-ui-workflow.json']);first=read(sources['first-causal-run.json']);student=read(sources['student-run.json'])
    workflow=actual['workflow'];data=workflow['data'];trace=data['trace']
    ranked=next(a['payload']['results'] for a in data['artifacts'] if a['tool']=='neural.rerank')
    citations=[{k:r.get(k) for k in ['id','title','text','source_id','source_url','document_version','source_checksum','anchor','legal_status','methodology','valid_from','valid_to']} for r in ranked]
    trials=[]
    for i,t in enumerate(comparison['trials']):
        trial_data=t['workflow']['data']
        trials.append({k:t[k] for k in ['mode','question','source_target','operation_date','seconds','state','target_section_retrieved','citation_count','legal_conclusion_generated','review_gate_preserved']} | {
            'record_order':i+1,'model_calls_with_generation':sum(bool(s.get('model',{}).get('generative_model_used')) for s in trial_data['trace']),
            'completed_tools':[s.get('tool') for s in trial_data['trace'] if s.get('state')=='Completed']})
    dataset={r['id']:r for r in (json.loads(line) for line in (MODEL/'dataset.jsonl').read_text(encoding='utf-8').splitlines())}
    failures=[]
    for failure in student['failure_cases']:
        source=dataset[failure['passage_id']]
        failures.append({**failure,**{k:source[k] for k in ['text','source_id','source_url','document_version','source_checksum','anchor']}})
    owned=read(ROOT/'frontend/public/vendor/systemlab-companion/provenance.json')
    index={'schema_version':'1.0','prepared_at':datetime.now(timezone.utc).isoformat(),'release_state':'Prepared','mode':'Recorded software evidence',
        'live_inference':False,'live_flights':False,'operational_acceptance':False,
        'first_experiment':{'elapsed_seconds':first['elapsed_seconds'],'steps':len(first['workflow']['data']['trace']),'state':first['workflow']['status'],'source':'data/first-causal-run.json'},
        'comparison':{'query_count':comparison['query_count'],'trials':trials,'limitations':comparison['limitations']+['Run order and cache reuse confound timings; no speed benefit is established.'],'source':'data/causal-comparison.json'},
        'ui_workflow':{'id':workflow['id'],'question':workflow['title'],'state':workflow['status'],'request':data['request'],
            'trace_start':trace[0]['started_at'],'trace_end':trace[-1]['finished_at'],'trace_span_seconds':duration(trace[0]['started_at'],trace[-1]['finished_at']),
            'trace':[{k:t.get(k) for k in ['sequence','tool','specialist','state','proposal','model','input_snapshot','started_at','finished_at','artifact_id']} | {'step_seconds':duration(t['started_at'],t['finished_at'])} for t in trace],
            'review_gate':data['review_gate'],'citation_count':len(citations),'citations':citations,'audit_valid':actual['audit']['valid'],'source':'data/actual-ui-workflow.json'},
        'student':{'run_id':student['run_id'],'promotion_status':student['promotion_status'],'task':student['task'],'architecture':student['architecture'],
            'dataset':student['dataset'],'evaluation':student['evaluation'],'failure_cases':failures,'artifact_checksum':student['artifact_checksum'],'training_resources':student['resources'],
            'source':'data/student-run.json','new_weights':False,'new_training':False},
        'owned_presentation':{'owner':owned['owner'],'rights':owned['rights'],'file_count':len(owned['files']),'files':owned['files'],
            'scope':'Application UI presentation only; the static viewer does not execute the reserved renderer.','source_package_version_status':owned['source_package_version_status']},
        'media':IMAGES,'source_attribution':'European Union Aviation Safety Agency, Easy Access Rules; copyright EASA 2003–2026. EU legal documents: copyright European Union 1998–2026. Acknowledged reproduction except where otherwise stated.'}
    (HERE/'data/evidence.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'prepared_at':index['prepared_at'],'source_reports':{name:{'project_path':str(path.relative_to(ROOT)).replace('\\','/'),'sha256':checksum(path),'bytes':path.stat().st_size} for name,path in sources.items()},
              'media':{name:{'sha256':checksum(HERE/'media'/name),'bytes':(HERE/'media'/name).stat().st_size} for name in IMAGES},
              'data_index_sha256':checksum(HERE/'data/evidence.json'),'publication_performed':False,'operational_records_created':False,'model_execution_performed':False}
    (HERE/'data/provenance.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'prepared':str(HERE),'actual_trials':len(trials),'actual_ui_steps':len(trace),'actual_citations':len(citations),'failure_examples':len(failures),'media_files':len(IMAGES),'new_training':False,'published':False}))


if __name__=='__main__':main()
