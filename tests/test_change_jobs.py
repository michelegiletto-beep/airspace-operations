from sqlalchemy import select
from airspace.storage import records
from airspace.worker import run_once


def test_source_change_creates_transitive_owned_review_tasks_without_overwrite(environment,monkeypatch):
    store,client,author,_,_,headers=environment
    h=headers(author['email'])
    requirement=client.post('/api/v1/records/requirement',headers=h,json={'title':'Isolated source requirement','data':{'source_ids':['easa-ear-uas-2026'],'owner':author['id']}}).json()
    case=client.post('/api/v1/records/case',headers=h,json={'title':'Isolated impacted case','data':{'requirement_ids':[requirement['id']],'owner':author['id']}}).json()
    def changed(*args,**kwargs):
        return {'success':True,'content_changed':True,'previous_checksum':'1'*64,'current_checksum':'2'*64,'operational_validation':False}
    monkeypatch.setattr('airspace.regulatory.monitor_registered_source',changed)
    queued=client.post('/api/v1/jobs',headers=h,json={'kind':'regulatory_monitor','payload':{'source_id':'easa-ear-uas-2026'}}).json()
    assert run_once(store)['state']=='Completed'
    tasks=client.get('/api/v1/records/review_task',headers=h).json()['items']
    assert {r['data']['affected_record_id'] for r in tasks}=={case['id'],requirement['id']}
    assert all(r['data']['owner']==author['id'] for r in tasks)
    unchanged=client.get('/api/v1/records/case/'+case['id'],headers=h).json()
    assert unchanged['version']==1 and unchanged['status']=='Draft'
