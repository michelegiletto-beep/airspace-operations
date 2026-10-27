"""Build a sanitised standalone engineering archive, SBOM and checksums."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tomllib
import zipfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0-rc.1'
EXCLUDED={'.git','.venv','node_modules','__pycache__','.pytest_cache','.hypothesis','runtime','release','work','local-research','snapshots','.cache'}
SECRET_PATTERNS=[re.compile(rb'\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}\b'),re.compile(rb'\bhf_[A-Za-z0-9]{30,}\b'),re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}\b'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]


def source_files():
    top_extensions={'.md','.toml','.lock','.txt','.yaml','.csv','.json','.cff'}
    candidates=[]
    for directory,subdirectories,filenames in os.walk(ROOT):
        subdirectories[:]=[name for name in subdirectories if name not in EXCLUDED]
        candidates.extend(Path(directory)/name for name in filenames)
    for file in candidates:
        rel=file.relative_to(ROOT)
        if any(part in EXCLUDED for part in rel.parts): continue
        if file.name=='.env' or file.suffix in {'.db','.pyc','.sqlite','.log'}: continue
        if rel.parts[:2]==('models','pretrained'):
            if file.name not in {'provenance.json','LICENSE','LICENSE.txt','README.md'}: continue
        if rel.parts[0]=='sources' and not (file.suffix in {'.json','.md'}): continue
        if len(rel.parts)==1 and not (file.suffix in top_extensions or file.name in {'LICENSE','NOTICE','Dockerfile','.env.example','.gitignore','.dockerignore'}): continue
        if rel.parts[0] in {'work','deploy','backend','frontend','tests','scripts','docs','sources','models','release-evidence','migrations','publication'} or len(rel.parts)==1:
            if file.name.endswith('.tsbuildinfo'): continue
            yield file,rel


def build_metadata():
    components=[];notices=[]
    for item in tomllib.loads((ROOT/'uv.lock').read_text())['package']:
        name,version=item['name'],item['version']
        if name=='system-lab-airspace-operations': continue
        try:
            meta=importlib.metadata.metadata(name)
            licence=meta.get('License-Expression') or meta.get('License') or 'NOASSERTION'
            if len(licence)>100: licence='See upstream package licence text'
        except importlib.metadata.PackageNotFoundError: licence='NOASSERTION (locked dependency, not installed in build environment)'
        components.append({'type':'library','name':name,'version':version,'purl':f'pkg:pypi/{name}@{version}','properties':[{'name':'upstream-licence-metadata','value':licence}]})
        notices.append(f'| Python | {name} | {version} | {licence.replace(chr(10)," ").replace("|","/")} |')
    lock=json.loads((ROOT/'frontend/package-lock.json').read_text())
    for path,item in lock['packages'].items():
        if not path: continue
        name=path.split('node_modules/')[-1];version=item.get('version','unknown');licence=item.get('license','NOASSERTION')
        components.append({'type':'library','name':name,'version':version,'purl':f'pkg:npm/{name}@{version}','scope':'optional' if item.get('dev') else 'required','properties':[{'name':'upstream-licence-metadata','value':str(licence)}]})
        notices.append(f'| npm | {name} | {version} | {licence} |')
    sbom={'bomFormat':'CycloneDX','specVersion':'1.6','version':1,'metadata':{'timestamp':datetime.now(timezone.utc).isoformat(),'component':{'type':'application','name':'System Lab Airspace Operations','version':VERSION}},'components':components}
    (ROOT/'SBOM.cdx.json').write_text(json.dumps(sbom,indent=2),encoding='utf-8')
    (ROOT/'THIRD_PARTY_NOTICES.md').write_text('# Third-party notices\n\nDependency metadata is recorded below; original licences remain controlling. Python dependencies are installed from the hash-locked requirements. The frontend bundle includes production npm code. Dev tools are identified in the SBOM. No source document or pretrained weight is relicensed by the project code licence. Models and legal extracts have separate provenance and rights records. NOASSERTION requires deployment licence review before redistribution of those third-party packages themselves.\n\n| Ecosystem | Component | Version | Upstream licence metadata |\n|---|---|---|---|\n'+'\n'.join(notices)+'\n',encoding='utf-8')


def main():
    gate=json.loads((ROOT/'release-evidence/release-gates.json').read_text())
    if not gate.get('engineering_checks_passed'): raise SystemExit('Engineering gates have not passed; packaging blocked')
    if not (ROOT/'frontend/dist/index.html').exists(): raise SystemExit('Build the interface first')
    build_metadata()
    output=ROOT/'release';output.mkdir(exist_ok=True)
    package=output/f'System-Lab-Airspace-Operations-{VERSION}.zip'
    files=list(source_files());failures=[];manifest={}
    for source,rel in files:
        data=source.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS): failures.append(rel.as_posix())
        manifest[rel.as_posix()]=hashlib.sha256(data).hexdigest()
    if failures: raise SystemExit('Potential secret patterns block packaging: '+','.join(failures))
    provenance={'version':VERSION,'source_commit':os.getenv('AIRSPACE_SOURCE_COMMIT'),'built_at':datetime.now(timezone.utc).isoformat(),'python':sys.version.split()[0],'platform':platform.platform(),'baseline_sha256':manifest['SPECIFICATION.md'],'files':manifest,'gates':gate,'scope':'Engineering candidate; stable and operational deployment blocked as documented','excluded':'Private runtime, keys, databases, customer evidence, original snapshots with uncleared rights, cached base-model weights, unrelated projects'}
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for source,rel in files: archive.write(source,'airspace-operations/'+rel.as_posix())
        archive.writestr('airspace-operations/RELEASE_PROVENANCE.json',json.dumps(provenance,indent=2))
    (output/'RELEASE_PROVENANCE.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    digest=hashlib.sha256(package.read_bytes()).hexdigest()
    (output/'SHA256SUMS.txt').write_text(f'{digest}  {package.name}\n',encoding='utf-8')
    result={'path':str(package),'bytes':package.stat().st_size,'sha256':digest,'file_count':len(files),'secret_pattern_scan':'No matched credential patterns; bounded heuristic, not a full secret-security proof','publication_status':'Prepared'}
    (output/'package-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
