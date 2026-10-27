"""Verify local CPU inference against actual, source-linked held-out passages."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import importlib.metadata

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from airspace.neural import ExperimentalStudent,LocalEncoder


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',default='explicit-shall-20261027-4')
    p.add_argument('--output',type=Path,default=ROOT/'release-evidence'/'neural-cpu-verification.json')
    args=p.parse_args()
    folder=ROOT/'models'/'runs'/args.run
    manifest=json.loads((folder/'run.json').read_text())
    actual=hashlib.sha256((folder/'student.safetensors').read_bytes()).hexdigest()
    if actual!=manifest['artifact_checksum']:
        raise ValueError('Student artifact checksum mismatch')
    records=[json.loads(line) for line in (folder/'dataset.jsonl').read_text().splitlines()]
    records=[r for r in records if r['split']=='test' and r['annotation']['status']!='Quarantined'][:8]
    started=time.perf_counter()
    encoder=LocalEncoder(ROOT/'models'/'pretrained'/'encoder',device='cpu')
    student=ExperimentalStudent(folder,encoder)
    load=time.perf_counter()-started
    started=time.perf_counter()
    predictions=student.classify([r['text'] for r in records])
    latency=time.perf_counter()-started
    result={'created_at':datetime.now(timezone.utc).isoformat(),'device':'cpu','samples':len(records),'model_load_seconds':load,'batch_inference_seconds':latency,'artifact_checksum':actual,'model_version':student.version,'inference_environment':{name:importlib.metadata.version(name) for name in ['torch','transformers','huggingface-hub','tokenizers','safetensors','numpy']},'historical_training_environment':manifest['resources'],'historical_training_manifest_checksum':hashlib.sha256((folder/'run.json').read_bytes()).hexdigest(),'training_rerun':False,'predictions':[{'passage_id':r['id'],'source_anchor':r['anchor'],**prediction} for r,prediction in zip(records,predictions)],'status':'CPU inference executed; experimental routing only; no operational or legal decision validation'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='predictions'}),flush=True)


if __name__=='__main__':main()
