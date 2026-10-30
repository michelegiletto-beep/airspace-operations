from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,time
root=Path.cwd();spec=importlib.util.spec_from_file_location('v',root/'scripts/verify_publication_v2.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);v.ALLOWED_HOSTS=v.ALLOWED_HOSTS|{'raw.githubusercontent.com'}
commit='331b6e220fec5254c4c2f167cab3ad86d8905456';p=json.loads((root/'release/0.3.0-rc.1/RELEASE_PROVENANCE.json').read_bytes());rows=[]
for path in ['publication/media/v0.3/desktop-companion.jpg','publication/media/v0.3/mobile-companion.jpg']:
 url='https://raw.githubusercontent.com/michelegiletto-beep/airspace-operations/'+commit+'/'+path
 v.validate_url(url);redirects=v.RestrictedRedirects(time.monotonic()+90)
 with v.anonymous_opener(redirects).open(v.anonymous_request(url),timeout=15) as r:
  assert r.status==200;data=r.read(2000001);assert len(data)<=2000000
  digest=hashlib.sha256(data).hexdigest();assert digest==p['files'][path] and data==(root/path).read_bytes()
  rows.append({'url':url,'path':path,'status':r.status,'bytes':len(data),'sha256':digest,'matches_released_provenance':True,'matches_local_capture':True,'authenticated_read':False})
report={'checked_at':datetime.now(timezone.utc).isoformat(),'source_commit':commit,'state':'Independently Retrieved','media':rows}
(root/'release-evidence/v0.3.0-rc.1/cycle-20261030-public-media.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
