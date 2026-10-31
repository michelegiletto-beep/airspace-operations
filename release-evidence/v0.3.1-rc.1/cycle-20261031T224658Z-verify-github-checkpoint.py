"""Anonymous immutable-source verification; explicit append-only result path."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.commit):
        parser.error('An actual immutable commit is required')
    output = (ROOT / args.output).resolve()
    manifest = (ROOT / args.manifest).resolve()
    if not output.is_relative_to(ROOT) or output.exists() or not manifest.is_relative_to(ROOT):
        parser.error('Use a new output path and a project-local manifest')
    raw = manifest.read_bytes()
    rows = json.loads(raw)['files']
    rows.append({'path':manifest.relative_to(ROOT).as_posix(),'bytes':len(raw),
                 'sha256':hashlib.sha256(raw).hexdigest(),
                 'git_blob':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
    assert len({r['path'] for r in rows}) == len(rows)
    for row in rows:
        path = Path(row['path'])
        assert not path.is_absolute() and '..' not in path.parts and '\\' not in row['path']
    def retrieve(row):
        url = 'https://raw.githubusercontent.com/michelegiletto-beep/airspace-operations/' + args.commit + '/' + row['path']
        result = {'path':row['path'],'url':url,'exact':False}
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=30) as response:
                content = response.read(2_000_001)
                assert len(content) <= 2_000_000 and response.geturl() == url
                result.update(status=response.status,bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),
                              git_blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest())
            result['exact'] = result['status'] == 200 and all(result[k] == row[k] for k in ('bytes','sha256','git_blob'))
        except Exception as exc:
            result['error'] = str(exc)
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(retrieve, rows))
    report = {'checked_at':datetime.now(timezone.utc).isoformat(),'commit':args.commit,
              'manifest':manifest.relative_to(ROOT).as_posix(),'authenticated':False,'environment_proxies':False,
              'files':results,'expected':len(rows),'exact':sum(r['exact'] for r in results),
              'success':all(r['exact'] for r in results),'new_release':False,'remote_mutations':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('commit','expected','exact','success')}))
    return 0 if report['success'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
