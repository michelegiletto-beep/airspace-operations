"""Independently extract and install the generated standalone release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile
import stat
from release_support import archive_workspace, isolated_archive_environment, current_version

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", help="Existing absolute private directory for an isolated verification run")
    args=parser.parse_args()
    ROOT=Path(__file__).resolve().parents[1]
    VERSION=current_version(ROOT)
    archive=ROOT/f'release/System-Lab-Airspace-Operations-{VERSION}.zip'
    with zipfile.ZipFile(archive) as content:
        destination, path_plan=archive_workspace(ROOT, content.namelist(), work_root=args.work_root)
        for entry in content.infolist():
            target=(destination/entry.filename).resolve()
            if not target.is_relative_to(destination) or stat.S_ISLNK(entry.external_attr >> 16):raise ValueError('Unsafe archive path')
        content.extractall(destination)
    project=destination/'airspace-operations'
    provenance=json.loads((project/'RELEASE_PROVENANCE.json').read_text(encoding='utf-8'))
    if provenance['version'] != VERSION:raise ValueError('Archive version mismatch')
    for name, expected in provenance['files'].items():
        source=(project/name).resolve()
        if not source.is_relative_to(project.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            raise ValueError('Archive source manifest mismatch: '+name)
    env=isolated_archive_environment(project, dict(os.environ))
    test_temp=destination/'t'
    test_temp.mkdir(exist_ok=False)
    env.update(TMP=str(test_temp), TEMP=str(test_temp), TMPDIR=str(test_temp))
    start=time.perf_counter()
    installed=subprocess.run(['uv','sync','--frozen','--extra','dev'],cwd=project,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
    python=project/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    env['PYTHONPATH']=str(project/'backend')
    command=[str(python),'-m','airspace.cli','check']
    checked=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30) if installed.returncode==0 else None
    probe='''from airspace.storage import local_store\nfrom airspace.api import create_app\nfrom fastapi.testclient import TestClient\ns=local_store();c=TestClient(create_app(s));r=c.get('/api/v1/health');assert r.status_code==200;assert r.json()['operational_acceptance'] is False;assert c.get('/api/v1/records/case').status_code==401;c.close();s.engine.dispose();print('Empty release database and authenticated API boundary verified')'''
    verification=subprocess.run([str(python),'-c',probe],cwd=project,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30) if installed.returncode==0 else None
    tests=subprocess.run([str(python),'-m','pytest','-q','--basetemp='+str(test_temp/'p')],cwd=project,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240) if installed.returncode==0 else None
    result={'working_paths':path_plan,'test_basetemp':str(test_temp/'p'),'source_manifest_files_verified':len(provenance['files']),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'extracted_into_separate_directory':True,'database_isolation':'Explicit new SQLite database inside extracted project; inherited external database, PostgreSQL-test and OIDC settings removed','installation_command':['uv','sync','--frozen','--extra','dev'],'installation_exit':installed.returncode,'installation_stdout':installed.stdout,'installation_stderr':installed.stderr,'cli_check':{'command':command,'exit_code':checked.returncode,'stdout':checked.stdout,'stderr':checked.stderr} if checked else None,'empty_service_verification':{'exit_code':verification.returncode,'stdout':verification.stdout,'stderr':verification.stderr} if verification else None,'test_suite':{'exit_code':tests.returncode,'stdout':tests.stdout,'stderr':tests.stderr} if tests else None,'elapsed_seconds':time.perf_counter()-start,'success':bool(installed.returncode==0 and checked and checked.returncode==0 and verification and verification.returncode==0 and tests and tests.returncode==0),'postgresql_or_container_verified':False}
    (ROOT/'release-evidence'/('v'+VERSION)/'standalone-archive-verification.json').write_text(json.dumps(dict(version=VERSION,**result),indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'installation_stdout','installation_stderr','cli_check','empty_service_verification'}},indent=2))
    if not result['success']:raise SystemExit(1)


if __name__ == "__main__":
    main()
