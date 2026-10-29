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
from release_support import assert_release_writable, current_version, public_improvement_files

ROOT=Path(__file__).resolve().parents[1]
VERSION=current_version(ROOT)
EXCLUDED={'.git','.venv','node_modules','__pycache__','.pytest_cache','.hypothesis','runtime','release','work','local-research','snapshots','.cache'}
SECRET_PATTERNS=[re.compile(rb'\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}\b'),re.compile(rb'\bhf_[A-Za-z0-9]{30,}\b'),re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}\b'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]


def source_files():
    improvement_files = public_improvement_files(ROOT)
    top_extensions={'.md','.toml','.lock','.txt','.yaml','.csv','.json','.cff'}
    candidates=[]
    for directory,subdirectories,filenames in os.walk(ROOT):
        subdirectories[:]=[name for name in subdirectories if name not in EXCLUDED and not name.endswith('.egg-info')]
        candidates.extend(Path(directory)/name for name in filenames)
    for file in candidates:
        rel=file.relative_to(ROOT)
        if any(part in EXCLUDED or part.endswith('.egg-info') for part in rel.parts): continue
        if file.name=='.env' or file.suffix in {'.db','.pyc','.sqlite','.log'}: continue
        if rel.parts[0]=='improvement' and rel.as_posix() not in improvement_files: continue
        if rel.parts[:2]==('models','pretrained'):
            if file.name not in {'provenance.json','LICENSE','LICENSE.txt','README.md'}: continue
        if rel.parts[0]=='sources' and not (file.suffix in {'.json','.md'}): continue
        if len(rel.parts)==1 and not (file.suffix in top_extensions or file.name in {'LICENSE','NOTICE','Dockerfile','.env.example','.gitignore','.dockerignore','.gitattributes'}): continue
        if rel.parts[0] in {'.github','LICENSES','work','deploy','backend','frontend','tests','scripts','docs','sources','models','release-evidence','migrations','publication','improvement'} or len(rel.parts)==1:
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
    core_purls={item['purl'] for item in components}
    optional_pins=[]
    for profile in ('requirements-neural.lock.txt','requirements-publication.lock.txt'):
        optional_pins.extend((name,version,profile) for name,version in re.findall(r'^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+\-]+)', (ROOT/profile).read_text(), re.MULTILINE))
    for name,version,profile in optional_pins:
        purl=f'pkg:pypi/{name}@{version}'
        if purl in core_purls: continue
        try:
            meta=importlib.metadata.metadata(name)
            licence=meta.get('License-Expression') or meta.get('License') or 'NOASSERTION'
            if len(licence)>100: licence='See upstream package licence text'
        except importlib.metadata.PackageNotFoundError: licence='NOASSERTION (optional locked dependency, not installed)'
        components.append({'type':'library','name':name,'version':version,'purl':purl,'scope':'optional','properties':[{'name':'installation-profile','value':profile+'; explicitly installed, not bundled wheels'},{'name':'upstream-licence-metadata','value':licence}]})
        core_purls.add(purl)
        notices.append(f'| Optional Python ({profile}) | {name} | {version} | {licence.replace(chr(10)," ").replace("|","/")} |')
    for provenance in sorted((ROOT/'models/pretrained').glob('*/provenance.json')):
        model=json.loads(provenance.read_text(encoding='utf-8'))
        repository=model.get('repository') or model['model_id']
        components.append({'type':'machine-learning-model','name':repository,'version':model['revision'],'scope':'optional','licenses':[{'license':{'id':'Apache-2.0'}}],'externalReferences':[{'type':'model-card','url':f'https://huggingface.co/{repository}/tree/{model["revision"]}'}],'properties':[{'name':'distribution','value':'Pretrained weights excluded; explicit pinned download only'},{'name':'provenance','value':provenance.relative_to(ROOT).as_posix()}]})
        notices.append(f'| Optional pretrained model | {repository} | {model["revision"]} | Apache-2.0; upstream terms and provenance apply; weights excluded |')
    student=ROOT/'models/runs/explicit-shall-20261027-4/student.safetensors'
    components.append({'type':'machine-learning-model','name':'System Lab experimental literal-language routing student','version':'explicit-shall-20261027-4','scope':'optional','hashes':[{'alg':'SHA-256','content':hashlib.sha256(student.read_bytes()).hexdigest()}],'licenses':[{'license':{'id':'Apache-2.0'}}],'modelCard':{'considerations':{'technicalLimitations':['Machine-generated unreviewed labels; inferior to deterministic literal-word baseline; experimental and not promoted','No legal, flight approval or operational prediction authority']}},'properties':[{'name':'lineage','value':'models/runs/explicit-shall-20261027-4/run.json; docs/model-card.md'}]})
    lock=json.loads((ROOT/'frontend/package-lock.json').read_text())
    for path,item in lock['packages'].items():
        if not path: continue
        name=path.split('node_modules/')[-1];version=item.get('version','unknown');licence=item.get('license','NOASSERTION')
        components.append({'type':'library','name':name,'version':version,'purl':f'pkg:npm/{name}@{version}','scope':'optional' if item.get('dev') else 'required','properties':[{'name':'upstream-licence-metadata','value':str(licence)}]})
        notices.append(f'| npm | {name} | {version} | {licence} |')
    owned=ROOT/'frontend/public/vendor/systemlab-companion'
    for relative in ('mascot-renderer.mjs','motion-core.mjs','catalog.mjs','assets/originals/mascotte_01_indaco.png','assets/originals/mascotte_06_coral_compact.png'):
        path=owned/relative
        components.append({'type':'file','name':'System Lab companion presentation runtime / '+relative,
            'hashes':[{'alg':'SHA-256','content':hashlib.sha256(path.read_bytes()).hexdigest()}],
            'licenses':[{'license':{'name':'LicenseRef-SystemLab-Assets — all rights reserved; see LICENSES/LicenseRef-SystemLab-Assets.txt'}}],
            'properties':[{'name':'ownership','value':'Existing System Lab owned presentation asset; not relicensed under Apache-2.0'},
                          {'name':'distribution-scope','value':'Presentation only; no broker, account, trading or aircraft command integration'}]})
    notices.append('| System Lab | Existing companion renderer and character assets | SHA-256 in SBOM; frontend/public/vendor/systemlab-companion/provenance.json; frontend/verification/0.2.0-rc.1/owned-runtime-assets.json | All rights reserved; LICENSES/LicenseRef-SystemLab-Assets.txt |')
    sbom={'bomFormat':'CycloneDX','specVersion':'1.6','version':1,'metadata':{'timestamp':datetime.now(timezone.utc).isoformat(),'component':{'type':'application','name':'System Lab Airspace Operations','version':VERSION}},'components':components}
    (ROOT/'SBOM.cdx.json').write_text(json.dumps(sbom,indent=2),encoding='utf-8')
    (ROOT/'THIRD_PARTY_NOTICES.md').write_text('# Third-party notices\n\nDependency metadata is recorded below; original licences remain controlling. Python dependencies are installed from the hash-locked requirements. The frontend bundle includes production npm code. Dev tools are identified in the SBOM. No source document or pretrained weight is relicensed by the project code licence. Models and legal extracts have separate provenance and rights records. NOASSERTION requires deployment licence review before redistribution of those third-party packages themselves.\n\n| Ecosystem | Component | Version | Upstream licence metadata |\n|---|---|---|---|\n'+'\n'.join(notices)+'\n',encoding='utf-8')


def main():
    # Refuse before build_metadata or any other release output can change.
    assert_release_writable(ROOT, VERSION)
    gate=json.loads((ROOT/'release-evidence'/('v'+VERSION)/'release-gates.json').read_text())
    if not gate.get('engineering_checks_passed'): raise SystemExit('Engineering gates have not passed; packaging blocked')
    if gate.get('version') != VERSION: raise SystemExit('Release gates belong to another software version')
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
