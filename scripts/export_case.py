"""Export a private controlled case using an existing authenticated session."""
import argparse
import os
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case-id',required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--base-url',default='http://127.0.0.1:8787')
parser.add_argument('--format',choices=['json','html'],default='json')
args=parser.parse_args()
target=urlsplit(args.base_url)
if target.scheme!='https' and not (target.scheme=='http' and target.hostname in {'127.0.0.1','localhost','::1'}):
    parser.error('Use HTTPS outside the local host')
if not all(c.isalnum() or c=='-' for c in args.case_id): parser.error('Invalid case ID')
if args.output.exists(): parser.error('Output already exists')
token=os.environ.get('AIRSPACE_SESSION_TOKEN')
if not token: parser.error('Set AIRSPACE_SESSION_TOKEN privately; do not put tokens on command lines')
request=urllib.request.Request(args.base_url.rstrip('/')+'/api/v1/records/case/'+args.case_id+'/export?format='+args.format,headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(request,timeout=30) as response:
    data=response.read(10_000_001)
if len(data)>10_000_000: raise ValueError('Export exceeds CLI limit')
args.output.parent.mkdir(parents=True,exist_ok=True)
with args.output.open('xb') as file: file.write(data)
print('Controlled private export written:',args.output)
