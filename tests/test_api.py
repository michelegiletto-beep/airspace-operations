import json
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, update
from airspace.storage import audit, records
from airspace.worker import run_once


def test_identity_tenant_isolation_idempotency_and_audit(environment):
    store, client, author, reviewer, other, headers = environment
    first, second = headers(author['email']), headers(other['email'])
    assert client.get('/api/v1/records/case').status_code == 401
    payload = {'title':'Isolated proposed operation', 'data':{'jurisdiction':'LU'}}
    h = {**first,'Idempotency-Key':'test-key'}
    response = client.post('/api/v1/records/case',json=payload,headers=h)
    assert response.status_code == 201, response.text
    item = response.json()
    assert client.post('/api/v1/records/case',json=payload,headers=h).json()['id'] == item['id']
    assert client.post('/api/v1/records/case',json={'title':'different'},headers=h).status_code == 409
    assert client.get('/api/v1/records/case',headers=second).json()['items'] == []
    for suffix in ['', '/history', '/export']:
        assert client.get('/api/v1/records/case/'+item['id']+suffix,headers=second).status_code == 404
    assert client.put('/api/v1/records/case/'+item['id'],headers=second,json={'expected_version':1,'title':'attack'}).status_code == 404
    assert store.verify_audit(author['organisation_id'])['valid']
    with store.engine.begin() as conn:
        conn.execute(update(audit).where(audit.c.organisation_id==author['organisation_id'],audit.c.sequence==1).values(action='tampered'))
    assert not store.verify_audit(author['organisation_id'])['valid']


def test_vertical_case_evidence_review_and_export(environment):
    store, client, author, reviewer, other, headers = environment
    h = headers(author['email']); rh = headers(reviewer['email'])
    evidence = client.post('/api/v1/records/evidence',headers=h,json={'title':'Isolated test source reference','data':{'provenance':'Test harness only','checksum':'0'*64,'evidence_type':'Software test'}}).json()
    data = {'jurisdiction':'LU','legal_route':'specific','conops':'User-entered proposed operation in isolated test','owner':author['id'],'aircraft_configuration_id':'test-only-configuration','evidence_ids':[evidence['id']],'reviewer_ids':[reviewer['id']]}
    case = client.post('/api/v1/records/case',headers=h,json={'title':'Test proposed operation','data':data}).json()
    url = '/api/v1/records/case/'+case['id']
    review = client.post(url+'/transition',headers=h,json={'state':'Under Review','expected_version':1,'reason':'Test completeness review'})
    assert review.status_code == 200, review.text
    assert client.post(url+'/transition',headers=h,json={'state':'Approved','expected_version':2,'reason':'Self approval attempted','evidence_ids':[evidence['id']]}).status_code == 403
    approved = client.post(url+'/transition',headers=rh,json={'state':'Approved','expected_version':2,'reason':'Isolated software verification only','evidence_ids':[evidence['id']]})
    assert approved.status_code == 200, approved.text
    assert approved.json()['status'] == 'Approved'
    submitted = client.post(url+'/transition',headers=h,json={'state':'Submitted','expected_version':3,'reason':'No receipt supplied'})
    assert submitted.status_code == 422
    package = client.get(url+'/export',headers=h)
    assert package.status_code == 200
    assert package.json()['case']['version'] == 3
    assert 'No submission' in package.json()['authority_status']
    assert store.verify_audit(author['organisation_id'])['valid']


def test_missing_evidence_and_concurrent_edits(environment):
    _,client,author,reviewer,_,headers=environment
    h=headers(author['email'])
    case=client.post('/api/v1/records/case',headers=h,json={'title':'Incomplete isolated case'}).json()
    url='/api/v1/records/case/'+case['id']
    assert client.post(url+'/transition',headers=h,json={'state':'Under Review','expected_version':1,'reason':'Missing evidence test'}).status_code==422
    def edit(title):
        return client.put(url,headers=h,json={'expected_version':1,'title':title}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(edit,['Edit one','Edit two']))
    assert sorted(results)==[200,409]
    assert client.put(url,headers=h,json={'expected_version':2,'data':{'_approvals':[{'actor_id':author['id']}]}}).status_code==422


def test_worker_pause_recovery_and_model_independence(environment):
    store,client,author,_,other,headers=environment
    h=headers(author['email']); oh=headers(other['email'])
    created=client.post('/api/v1/jobs',headers=h,json={'kind':'case_preparation'}).json()
    assert client.post('/api/v1/jobs',headers=h,json={'kind':'aircraft.takeoff'}).status_code==422
    assert client.post('/api/v1/jobs/'+created['id']+'/pause',headers=oh).status_code==409
    assert client.post('/api/v1/jobs/'+created['id']+'/pause',headers=h).status_code==200
    assert run_once(store) is None
    client.post('/api/v1/jobs/'+created['id']+'/resume',headers=h)
    assert run_once(store)['state']=='Completed'
    result=client.get('/api/v1/jobs',headers=h).json()['items'][0]
    assert result['result']['cases']==[]
    assert client.get('/api/v1/jobs',headers=oh).json()['items']==[]


def test_permission_external_evidence_and_no_privilege_elevation(environment):
    _,client,author,reviewer,_,headers=environment
    h=headers(author['email'])
    assert client.post('/api/v1/records/approval',headers=h,json={'title':'Fake approval'}).status_code==403
    assert client.post('/api/v1/records/telemetry',headers=h,json={'title':'Fake live telemetry'}).status_code==403
    assert client.post('/api/v1/records/case',headers=h,json={'title':'Cross tenant reviewer','data':{'reviewer_ids':['unknown']}}).status_code==422
    assert client.post('/api/v1/records/case',headers=h,json={'title':'Unknown evidence','data':{'evidence_ids':['unknown']}}).status_code==422


def test_backup_restore_integrity(environment,tmp_path):
    import sqlite3
    from airspace.storage import Store
    store,_,author,_,_,_=environment
    target=tmp_path/'backup.db'
    with store.engine.connect() as conn:
        with sqlite3.connect(target) as destination:
            conn.connection.driver_connection.backup(destination)
    restored=Store(f'sqlite:///{target}',store.key)
    assert restored.verify_audit(author['organisation_id'])==store.verify_audit(author['organisation_id'])
    with sqlite3.connect(target) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
