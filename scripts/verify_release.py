"""Execute reproducible verification and preserve actual command outputs."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import re
from datetime import datetime, timezone
from release_support import current_version

ROOT=Path(__file__).resolve().parents[1]
VERSION=current_version(ROOT)
EVIDENCE=ROOT/'release-evidence'/('v'+VERSION)


def execute(name,command,cwd=ROOT,timeout=300):
    started=datetime.now(timezone.utc).isoformat(); clock=time.perf_counter()
    env=dict(os.environ,PYTHONPATH=str(ROOT/'backend'),PYTHONIOENCODING='utf-8')
    try:
        completed=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        code,stdout,stderr=completed.returncode,completed.stdout,completed.stderr
    except subprocess.TimeoutExpired as error:
        code,stdout,stderr=124,str(error.stdout or ''),str(error.stderr or '')+'\nVerification timeout'
    record={'name':name,'command':command,'cwd':'.' if cwd==ROOT else str(cwd.relative_to(ROOT)),'started_at':started,'elapsed_seconds':round(time.perf_counter()-clock,3),'exit_code':code,'stdout':stdout,'stderr':stderr}
    (EVIDENCE/(name+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
    with (EVIDENCE/'commands.jsonl').open('a',encoding='utf-8') as out: out.write(json.dumps(record)+'\n')
    print(json.dumps({'check':name,'exit_code':code,'seconds':record['elapsed_seconds']}),flush=True)
    return code==0


def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    npm='npm.cmd' if os.name=='nt' else 'npm'
    checks={}
    checks['python_tests']=execute('python-tests',[sys.executable,'-m','pytest','-q',f'--junitxml={EVIDENCE}/pytest.xml','--cov=airspace','--cov=systemlab_agentic',f'--cov-report=json:{EVIDENCE}/coverage.json','--cov-report=term'])
    checks['frontend_tests']=execute('frontend-tests',[npm,'test'],ROOT/'frontend')
    checks['frontend_build']=execute('frontend-build',[npm,'run','build'],ROOT/'frontend')
    checks['frontend_dependency_audit']=execute('frontend-dependency-audit',[npm,'audit','--json'],ROOT/'frontend')
    checks['python_dependency_audit']=execute('python-dependency-audit',[sys.executable,'-m','pip_audit','--no-deps','--disable-pip','-r','requirements.lock.txt','--format=json'],timeout=300)
    checks['optional_neural_dependency_audit']=execute('optional-neural-dependency-audit',[sys.executable,'-m','pip_audit','--no-deps','--disable-pip','-r','requirements-neural.lock.txt','--format=json'],timeout=300)
    checks['baseline_integrity']=hashlib.sha256((ROOT/'SPECIFICATION.md').read_bytes()).hexdigest()=='43755041cbfa555158b51979de4c726bf52f7e82dc113e840c1488d974ba9b30'
    result=release_result(checks)
    (EVIDENCE/'release-gates.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if all(checks.values()) else 1


def release_result(checks):
    ci_path=EVIDENCE/'ci-verification.json'
    ci=json.loads(ci_path.read_text(encoding='utf-8')) if ci_path.exists() else None
    ci_matches=bool(ci and ci.get('conclusion')=='success' and ci.get('local_software_input_hashes'))
    if ci_matches:
        ci_matches=all((ROOT/path).is_file() and hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in ci['local_software_input_hashes'].items())
    unverified=['Qualified Luxembourg/Italy pack validation','Full methodology and operational data acceptance','Live provider and enterprise identity integration','Complete baseline feature/assurance acceptance','Production-scale resilience and deployment-specific security acceptance']
    if not ci_matches:
        unverified[:0]=['PostgreSQL/PostGIS/pgvector deployment and concurrency','Docker build and health checks']
    return {'version':VERSION,'at':datetime.now(timezone.utc).isoformat(),'checks':checks,'engineering_checks_passed':all(checks.values()),'stable_release_allowed':False,'operational_acceptance':False,'external_ci':{'verified':ci_matches,'evidence':'ci-verification.json' if ci else None,'run_id':ci.get('run_id') if ci else None,'commit':ci.get('commit') if ci else None,'scope':'Actual isolated container/PostgreSQL/worker/restoration run; local input hashes must remain identical'},'unverified_gates':unverified}


if __name__=='__main__': raise SystemExit(main())
