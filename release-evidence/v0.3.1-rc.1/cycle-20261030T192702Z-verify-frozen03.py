from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib, importlib.util, json, pathlib, time
root=pathlib.Path.cwd()
spec=importlib.util.spec_from_file_location('prior_verifier',root/'scripts/verify_publication_v2.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
v.ALLOWED_HOSTS=v.ALLOWED_HOSTS|{'api.github.com','raw.githubusercontent.com'}
folder=root/'release/0.3.0-rc.1';folder.mkdir(parents=True,exist_ok=True)
def fetch(url,bound):
    v.validate_url(url)
    redirects=v.RestrictedRedirects(time.monotonic()+90)
    with v.anonymous_opener(redirects).open(v.anonymous_request(url),timeout=15) as r:
        if r.status!=200:raise ValueError('Expected HTTP200')
        data=r.read(bound+1)
        if len(data)>bound:raise ValueError('Response exceeds bound')
        return data,{'status':r.status,'final_url':v.safe_url(r.url),'redirect_hosts':redirects.redirect_hosts,'authenticated_read':False}
url='https://api.github.com/repos/michelegiletto-beep/airspace-operations/releases/tags/v0.3.0-rc.1'
release=json.loads(fetch(url,500000)[0]);assert not release['draft'] and release['prerelease'] and len(release['assets'])==9
assert release['target_commitish']=='331b6e220fec5254c4c2f167cab3ad86d8905456'
ref=json.loads(fetch('https://api.github.com/repos/michelegiletto-beep/airspace-operations/git/ref/tags/v0.3.0-rc.1',50000)[0]);assert ref['object']['sha']==release['target_commitish']
def asset(row):
    name=row['name'];assert pathlib.PurePosixPath(name).name==name and '\\' not in name
    expected='https://github.com/michelegiletto-beep/airspace-operations/releases/download/v0.3.0-rc.1/'+name
    assert row['browser_download_url']==expected
    data,request=fetch(expected,16*1024*1024)
    sha=hashlib.sha256(data).hexdigest();assert len(data)==row['size'] and 'sha256:'+sha==row['digest']
    path=folder/name
    if path.exists():assert path.read_bytes()==data,'Existing frozen asset differs'
    else:raise ValueError('The frozen local asset must already exist; this verification never repairs frozen files')
    return {'name':name,'id':row['id'],'url':expected,'bytes':len(data),'sha256':sha,'github_digest_matches':True,**request}
with ThreadPoolExecutor(max_workers=4) as p: assets=list(p.map(asset,release['assets']))
report={'checked_at':datetime.now(timezone.utc).isoformat(),'release_id':release['id'],'url':release['html_url'],'tag':release['tag_name'],'source_commit':ref['object']['sha'],'published_at':release['published_at'],'state':'Independently Retrieved','anonymous_requests':True,'credentials_cookies_environment_proxies':False,'assets':assets}
evidence=root/'release-evidence/v0.3.1-rc.1';evidence.mkdir(exist_ok=True)
(evidence/'cycle-20261030T192702Z-github-frozen03.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
