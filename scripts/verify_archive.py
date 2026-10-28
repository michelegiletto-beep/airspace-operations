"""Independently extract and install the generated standalone release."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import zipfile
import re

ROOT=Path(__file__).resolve().parents[1]
VERSION=re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT/'backend/airspace/__init__.py').read_text()).group(1)
archive=ROOT/f'release/System-Lab-Airspace-Operations-{VERSION}.zip'
base=ROOT/'runtime/archive-verification';base.mkdir(parents=True,exist_ok=True)
destination=Path(tempfile.mkdtemp(prefix='candidate-',dir=base)).resolve()
with zipfile.ZipFile(archive) as content:
    for entry in content.infolist():
        target=(destination/entry.filename).resolve()
        if not target.is_relative_to(destination):raise ValueError('Unsafe archive path')
    content.extractall(destination)
project=destination/'airspace-operations'
env=dict(os.environ,UV_PROJECT_ENVIRONMENT=str(project/'.venv'),AIRSPACE_RUNTIME=str(project/'runtime/isolated-release-check'))
start=time.perf_counter()
installed=subprocess.run(['uv','sync','--frozen','--extra','dev'],cwd=project,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
python=project/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
env['PYTHONPATH']=str(project/'backend')
command=[str(python),'-m','airspace.cli','check']
checked=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30) if installed.returncode==0 else None
probe='''from airspace.storage import local_store\nfrom airspace.api import create_app\nfrom fastapi.testclient import TestClient\ns=local_store();c=TestClient(create_app(s));r=c.get('/api/v1/health');assert r.status_code==200;assert r.json()['operational_acceptance'] is False;assert c.get('/api/v1/records/case').status_code==401;c.close();s.engine.dispose();print('Empty release database and authenticated API boundary verified')'''
verification=subprocess.run([str(python),'-c',probe],cwd=project,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30) if installed.returncode==0 else None
tests=subprocess.run([str(python),'-m','pytest','-q'],cwd=project,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240) if installed.returncode==0 else None
result={'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'extracted_into_separate_directory':True,'installation_command':['uv','sync','--frozen','--extra','dev'],'installation_exit':installed.returncode,'installation_stdout':installed.stdout,'installation_stderr':installed.stderr,'cli_check':{'command':command,'exit_code':checked.returncode,'stdout':checked.stdout,'stderr':checked.stderr} if checked else None,'empty_service_verification':{'exit_code':verification.returncode,'stdout':verification.stdout,'stderr':verification.stderr} if verification else None,'test_suite':{'exit_code':tests.returncode,'stdout':tests.stdout,'stderr':tests.stderr} if tests else None,'elapsed_seconds':time.perf_counter()-start,'success':bool(installed.returncode==0 and checked and checked.returncode==0 and verification and verification.returncode==0 and tests and tests.returncode==0),'postgresql_or_container_verified':False}
(ROOT/'release-evidence'/VERSION/'standalone-archive-verification.json').write_text(json.dumps(dict(version=VERSION,**result),indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in {'installation_stdout','installation_stderr','cli_check','empty_service_verification'}},indent=2))
if not result['success']:raise SystemExit(1)
