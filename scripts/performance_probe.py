"""Measure local software paths in an isolated empty workspace, using real source text."""
import json
import tempfile
import time
import statistics
from pathlib import Path
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from airspace.api import create_app
from airspace.storage import Store
from airspace.identity import provision

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    store=Store('sqlite:///'+str(Path(folder)/'probe.db'),b'isolated-performance-probe-key-32bytes')
    store.migrate()
    provision(store,'Isolated software performance probe','probe@test.invalid','regulatory','isolated-probe-passphrase')
    client=TestClient(create_app(store,serve_frontend=False))
    session=client.post('/api/v1/session',json={'email':'probe@test.invalid','password':'isolated-probe-passphrase'}).json()
    headers={'Authorization':'Bearer '+session['token']}
    health=[];lookup=[]
    for _ in range(30):
        start=time.perf_counter();response=client.get('/api/v1/health');health.append(time.perf_counter()-start);assert response.status_code==200
    for _ in range(5):
        start=time.perf_counter();response=client.post('/api/v1/retrieval',headers=headers,json={'question':'operational authorisation','jurisdiction':'LU','operation_date':'2026-10-27'});lookup.append(time.perf_counter()-start);assert response.status_code==200,response.text
    result={'at':datetime.now(timezone.utc).isoformat(),'environment':'Local Windows process / SQLite / isolated empty organisation; real permitted regulatory corpus','health_seconds':{'n':len(health),'median':statistics.median(health),'p95':sorted(health)[int(len(health)*.95)-1]},'lexical_retrieval_seconds':{'n':len(lookup),'median':statistics.median(lookup),'max':max(lookup)},'meaning':'Engineering latency probe, no production capacity or SLO acceptance claim'}
    client.close();store.engine.dispose()
(ROOT/'release-evidence/performance-probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
