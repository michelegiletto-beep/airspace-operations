"""Verify only local presentation material; no Hub publication or inference."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from package_release import SECRET_PATTERNS
from publication_media import validate_raster_encoding


class Document(HTMLParser):
    def __init__(self, content):
        super().__init__(); self.ids=[]; self.links=[]; self.images=[]; self.tags=[]; self.feed(content)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs); self.tags.append(tag)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag in {'a','link'} and attrs.get('href'):self.links.append(attrs['href'])
        if tag=='img':
            assert attrs.get('alt'), 'Images require descriptive alternatives'
            self.images.append(attrs['src'])


def main():
    manifest=json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['state']=='Prepared' and manifest['new_uploads'] is False
    assert manifest['presentation_only'] and not manifest['weights_changed'] and not manifest['dataset_records_changed']
    assert manifest['application_source']=='433e89a66038ee7f7c34cb443c03eeafdee92f36'
    assert len(manifest['files'])==10 and len({(row['repo_type'],row['target']) for row in manifest['files']})==10
    checked=[]
    for row in manifest['files']:
        path=ROOT/row['source']; data=path.read_bytes()
        assert path.is_relative_to(HERE) and path.is_file() and not path.is_symlink()
        assert path.stat().st_size==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        assert not any(pattern.search(data) for pattern in SECRET_PATTERNS)
        if path.suffix in {'.md','.html','.css'}:
            text=data.decode('utf-8')
            assert '\ufffd' not in text
            assert not any(phrase in text for phrase in ('One operational context. Bounded specialist work.','Choose the work. Keep the evidence.','Review remains accountable.','static-image fallback'))
            assert '/blob/main/' not in text and '/tree/main/' not in text
        else:
            encoding=validate_raster_encoding(path)
            checked.append({'source':row['source'],'encoding':encoding,'sha256':row['sha256']})
    page=(HERE/'space/index.html').read_text(encoding='utf-8')
    document=Document(page)
    assert len(document.ids)==len(set(document.ids))
    assert not set(document.tags)&{'script','iframe','form','input','button'}
    for link in document.links:
        if link.startswith('#'):assert link[1:] in document.ids
        elif not link.startswith('https://'):assert (HERE/'space'/link).is_file()
    for image in document.images:assert (HERE/'space'/image).is_file()
    assert '509' not in page and all(value in page for value in ('479','123','19','20 skipped','41118769822','12,504,321',manifest['archive_sha256']))
    assert '0.3.1-rc.1' in page and len(document.images)==2
    model=(HERE/'model/README.md').read_text(encoding='utf-8')
    dataset=(HERE/'dataset/README.md').read_text(encoding='utf-8')
    assert 'animated fallback' in (HERE/'space/README.md').read_text(encoding='utf-8')
    assert 'fallback also animates' in model
    historical_notice=(ROOT/'publication/hf-space/NOTICE.md').read_text(encoding='utf-8')
    assert (HERE/'space/NOTICE.md').read_text(encoding='utf-8').startswith(historical_notice)
    for card in (model,dataset):
        assert '81.82%' in card and '77' in card and '100%' in card.replace('100.00%','100%')
        assert '0.3.1' in card and 'unreviewed' in card
    originals={'model/media/companion-tasks.png':'companion-tasks.png',
               'space/media/application-tasks.png':'application-tasks.png',
               'space/media/companion-tasks-mobile.jpg':'companion-tasks-mobile.png'}
    for relative,source in originals.items():
        assert (HERE/relative).read_bytes()==(ROOT/'publication/media/0.3.1-rc.1'/source).read_bytes()
    student=ROOT/'models/runs/explicit-shall-20261027-4/student.safetensors'
    assert student.stat().st_size==49824 and hashlib.sha256(student.read_bytes()).hexdigest()=='ff96770308c96b9d96c5f8f6535576e9d791834f76291bf08fce99dcf34d6e6c'
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'state':'Prepared; local structural, copy, rights-boundary and hash checks passed',
            'application_version':'0.3.1-rc.1','application_source':manifest['application_source'],'target_files':10,
            'secret_patterns_found':0,'images':checked,'local_space_references_valid':True,'active_or_operational_controls':False,
            'student_bytes_unchanged':True,'weights_or_dataset_rows_in_upload_list':False,
            'new_model_calls':0,'new_training_runs':0,'new_uploads':False,'authentication_attempts':False,
            'rights_notice_in_model_and_space':True,'existing_space_source_and_historical_notice_preserved':True,
            'review_repair':'Read-only engineering copy review identified that an artwork-only Space NOTICE would drop existing EASA/EU attribution; the complete historical notice is now retained before the added asset terms',
            'raw_legal_documents_redistributed':False,
            'browser_verified':False,'release_verification':{'source_tests':479,'exact_archive_tests':479,'skipped':20,'frontend_tests':123,'postgresql_tests':19,'ci':41118769822},
            'limitations':['Static Space browser rendering and independent retrieval remain pending a real upload to the existing account',
                           'Container checks do not decode pixel data or prove whole-product copy completeness',
                           'The frozen mobile JPEG/PNG filename mismatch remains; this presentation uses an identical.jpg copy'],
            'manifest_sha256':hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest(),
            'command':'.venv/Scripts/python.exe -B publication/releases/0.3.1-rc.1/huggingface/verify_preparation.py'}
    (HERE/'preparation-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (ROOT/'release-evidence/v0.3.1-rc.1/cycle-20261031-hub-preparation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'state':report['state'],'target_files':10,'images':len(checked),'student_unchanged':True,'new_uploads':False}))


if __name__=='__main__':main()
