"""Measure source-title target retrieval on real, preserved regulatory sections.

This is an engineering proxy benchmark using actual section titles and exact
structural targets. It is not a legal question-answering or operational trial.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from airspace.regulatory import retrieve
from airspace.neural import LocalEncoder, LocalReranker, ScopedCachedEncoder


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    p.add_argument('--output',type=Path,default=ROOT/'release-evidence'/'retrieval-evaluation.json')
    args=p.parse_args()
    corpus_path=ROOT/'sources'/'corpus.json'
    rows=json.loads(corpus_path.read_text(encoding='utf-8'))
    snippets=['competency of remote pilots','Application for an operational authorisation','Duration and validity of an operational authorisation','Network identification service','Geo-awareness service','UAS flight authorisation service','Traffic information service','Authorised representatives']
    targets=[]
    for snippet in snippets:
        sample=next(r for r in rows if r['legal_status']=='binding_legislation' and snippet.lower() in r['title'].lower())
        targets.append({'query':sample['title'],'source_id':sample['source_id'],'section_id':sample['anchor'].split(':')[0]})
    load_start=time.perf_counter()
    encoder=ScopedCachedEncoder(LocalEncoder(ROOT/'models'/'pretrained'/'encoder',args.device),'public-regulatory-evaluation')
    reranker=LocalReranker(ROOT/'models'/'pretrained'/'reranker',args.device)
    load_seconds=time.perf_counter()-load_start
    trials=[]
    day=datetime.now(timezone.utc).date().isoformat()
    for target in targets:
        for mode,kwargs in [('lexical',{}),('pretrained_hybrid',{'encoder':encoder}),('hybrid_reranked',{'encoder':encoder,'reranker':reranker})]:
            begin=time.perf_counter()
            output=retrieve(rows,target['query'],'LU',day,limit=5,**kwargs)
            rank=next((i+1 for i,r in enumerate(output['results']) if r['source_id']==target['source_id'] and r['anchor'].split(':')[0]==target['section_id']),None)
            trials.append({**target,'mode':mode,'reciprocal_rank_at_5':1/rank if rank else 0.,'target_found_at_5':bool(rank),'seconds':time.perf_counter()-begin,'source_anchors':[r['anchor'] for r in output['results']],'engine':output['engine'],'failures':output['failures']})
        print(json.dumps({'completed_query':target['query']}),flush=True)
    result={'created_at':datetime.now(timezone.utc).isoformat(),'benchmark':'Exact official section-title retrieval proxy; not natural-language legal-answer evaluation','query_count':len(targets),'corpus_passages':len(rows),'corpus_checksum':hashlib.sha256(corpus_path.read_bytes()).hexdigest(),'device':args.device,'model_load_seconds':load_seconds,'human_reviewed_legal_queries':0,'runs':trials,'summary':{}}
    for mode in ['lexical','pretrained_hybrid','hybrid_reranked']:
        batch=[t for t in trials if t['mode']==mode]
        result['summary'][mode]={'target_recall_at_5':sum(t['target_found_at_5'] for t in batch)/len(batch),'mean_reciprocal_rank_at_5':sum(t['reciprocal_rank_at_5'] for t in batch)/len(batch),'total_seconds':sum(t['seconds'] for t in batch)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['summary']),flush=True)


if __name__=='__main__':
    main()
