"""Expand the release's permitted source corpus without network access."""
import gzip
import json
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=root/'sources/corpus.json.gz';target=root/'sources/corpus.json'
if not target.exists():
    if not source.is_file(): raise SystemExit('No packaged corpus found; run the registered ingestion workflow')
    with gzip.open(source,'rb') as stream:data=stream.read(50_000_001)
    if len(data)>50_000_000: raise SystemExit('Corpus exceeds bounded expansion size')
    value=json.loads(data)
    if not isinstance(value,list): raise SystemExit('Unexpected corpus schema')
    with target.open('xb') as file:file.write(data)
    print('Expanded actual permitted regulatory passages:',len(value))
else: print('Source corpus already available')
experiments=root/'models/experiment-artifacts.zip'
if experiments.is_file():
    with zipfile.ZipFile(experiments) as archive:
        if sum(entry.file_size for entry in archive.infolist())>20_000_000:
            raise SystemExit('Experiment archive exceeds expansion limit')
        destination=(root/'models').resolve()
        for entry in archive.infolist():
            target=(destination/entry.filename).resolve()
            if not target.is_relative_to(destination) or not entry.filename.startswith('runs/'):
                raise SystemExit('Unsafe experiment artifact path')
        for entry in archive.infolist():
            target=destination/entry.filename
            if not target.exists() and not entry.is_dir():
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as output:output.write(archive.read(entry))
    print('Preserved experimental lineage is available')
