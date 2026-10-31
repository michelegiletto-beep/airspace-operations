"""Read-only prepared Site review. No remote requests, Git writes or deployment."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'work/site-publishing'
EXPECTED = 'a7c4da5fdfca2ef040b92b4d3cdbddb6aeae995d'
BASE = '309b6fac69cfbe51278da6d116545cf2916251b7'
STAMP = 'cycle-20261031T224658Z'
def git(*arguments):
    return subprocess.run(['git', *arguments], cwd=SITE, check=True, capture_output=True, timeout=30).stdout
def digest(data):
    return hashlib.sha256(data).hexdigest()
def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

assert git('rev-parse', 'HEAD').decode().strip() == EXPECTED
assert not git('status', '--porcelain').strip()
changes = [row.split('\t', 1) for row in git('diff', '--name-status', BASE+'..HEAD').decode().splitlines()]
allowed_existing = {'public/projects/airspace-operations.html', 'templates/airspace-operations.html', 'tests/airspace-operations.test.mjs'}
assert len(changes) == 15
assert all(path in allowed_existing or path.startswith('public/airspace-operations/media/0.3.1-rc.1/') or path.startswith('public/airspace-operations/releases/0.3.1-rc.1/') for state,path in changes)
assert sum(state == 'A' for state,path in changes) == 12
assert all(state == 'M' and path in allowed_existing for state,path in changes if state != 'A')

spec = importlib.util.spec_from_file_location('review_site_v3', ROOT/'scripts/verify_publication_v3.py')
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)
old_targets = verification.build_targets(SITE)
assert len(old_targets) == 37
historical_exact = [row for row in old_targets if row['verification_mode']=='exact']
assert len(historical_exact) == 34
assert all(len(verification.source_path(SITE,row['path']).read_bytes())==row['expected_bytes'] and digest(verification.source_path(SITE,row['path']).read_bytes())==row['expected_sha256'] for row in historical_exact)

evidence = ROOT / 'release-evidence/v0.3.1-rc.1'
downloads = read_json(evidence/'cycle-20261030T195233Z-public-downloads.json')
assert downloads['state']=='Independently Retrieved' and downloads['source_commit']=='433e89a66038ee7f7c34cb443c03eeafdee92f36' and len(downloads['assets'])==9
new_assets = []
for row in downloads['assets']:
    path = SITE/'public/airspace-operations/releases/0.3.1-rc.1'/row['name']
    data = path.read_bytes()
    assert len(data)==row['bytes'] and digest(data)==row['sha256']
    assert data==(ROOT/'release/0.3.1-rc.1'/row['name']).read_bytes()
    new_assets.append({'path':path.relative_to(SITE).as_posix(),'bytes':len(data),'sha256':digest(data)})
media = read_json(evidence/'cycle-20261030T195233Z-public-media.json')
new_media = []
for row in media['media']:
    name = Path(row['path']).name
    if name=='companion-tasks-mobile.png':
        name='companion-tasks-mobile.jpg'
    path = SITE/'public/airspace-operations/media/0.3.1-rc.1'/name
    data = path.read_bytes()
    assert len(data)==row['bytes'] and digest(data)==row['sha256']
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        detected, pixels = image.format, list(image.size)
    assert detected==('JPEG' if path.suffix=='.jpg' else 'PNG') and pixels==row['pixels']
    new_media.append({'path':path.relative_to(SITE).as_posix(),'bytes':len(data),'sha256':digest(data),'detected_format':detected,'pixels':pixels})

secret_patterns = [re.compile(rb'\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}\b'),re.compile(rb'\bhf_[A-Za-z0-9]{30,}\b'),re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}\b'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(rb'Authorization:\s*Bearer\s+[A-Za-z0-9_.-]{20,}',re.I)]
secret_findings = []
for state,relative in changes:
    data = (SITE/relative).read_bytes()
    if any(pattern.search(data) for pattern in secret_patterns):
        secret_findings.append(relative)
private_paths=[]
archive=next(row for row in new_assets if row['path'].endswith('.zip'))
with zipfile.ZipFile(SITE/archive['path']) as bundle:
    members=bundle.infolist()
    for member in members:
        if member.is_dir():
            continue
        parts=Path(member.filename).parts
        if any(part in {'runtime','private','secrets','snapshots','local-research','.git','.venv','node_modules'} for part in parts) or Path(member.filename).suffix.lower() in {'.key','.sqlite','.db','.pem','.p12','.pfx'}:
            private_paths.append(member.filename)
        data=bundle.read(member)
        if any(pattern.search(data) for pattern in secret_patterns):
            secret_findings.append('archive/'+member.filename)
assert not private_paths and not secret_findings
page=(SITE/'public/projects/airspace-operations.html').read_text(encoding='utf-8')
assert page==(SITE/'templates/airspace-operations.html').read_text(encoding='utf-8')
assert '<script' not in page.lower() and '<form' not in page.lower() and 'mailto:' not in page.lower()
assert 'original specification is not fully accepted' in page and 'no accepted live telemetry' in page
assert 'The platform is not certified' in page and 'currently presents the 0.2 record' in page
assert 'existing personal engineering tasks in a software review workspace' in page and 'Mission records remain empty' in page
assert 'file contains valid JPEG bytes' in page
assert '0.3.1-rc.1 Published' in page and '479 passed, 20 skipped' in page and '123 passed' in page
assert not re.search(r'(?i)one operational context|choose the work|keep the evidence|unlock your|seamless|game.chang|delve|cutting.edge|revolutioniz|#AI', page)
assert git('rev-parse','HEAD').decode().strip()==EXPECTED
assert not git('status','--porcelain').strip()
report={'at':datetime.now(timezone.utc).isoformat(),'reviewer':'/root/guard_final_review','review_kind':'Read-only engineering source, asset, copy and private-material review; no professional aviation certification',
        'state':'Prepared source review passed; no deployment or anonymous public Site retrieval claimed',
        'site_source_commit':EXPECTED,'prior_site_source_commit':BASE,'worktree_clean':True,'changed_paths':changes,'unrelated_tracked_source_unchanged':True,
        'historical_targets_checked':37,'historical_exact_assets':34,'new_assets':new_assets,'new_media':new_media,
        'new_archive_members':len(members),'secret_findings':secret_findings,'private_archive_paths':private_paths,
        'copy_review':'Functional headings and task descriptions, no detected slogans or decorative labels in authored project copy. Candidate, historical model results, source-coverage limits and separate operational acceptance remain explicit.',
        'visual_media_review':['Actual mobileJPEG decoded and visually inspected; task states/empty mission context retained','Actual desktopPNG decoded and visually inspected; private header cropped, empty mission/site workspace retained','All3media match previously independently retrieved frozen source digests'],
        'scoped_test':{'command':'node --test tests/airspace-operations.test.mjs','cwd':'work/site-publishing','passed':5,'failed':0,'duration_ms':850.4014,'exit_code':0},
        'blocking_findings':[],'source_files_edited':False,'git_mutations':False,'remote_requests':False,'model_calls':0,
        'next_action':'Root must finish the official source helper push/package and native save/deploy, then anonymously verify49resources against the exact successful deployment identity and inspect the public page. Preserve all frozen releases.'}
output=evidence/(STAMP+'-site-source-review.json')
output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':report['state'],'historical_exact':34,'new_assets':len(new_assets),'new_media':len(new_media),'secret_findings':0,'private_paths':0,'source_commit':EXPECTED,'output':str(output.relative_to(ROOT))}))
