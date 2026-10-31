"""Prepare presentation-only Hub files; this script performs no network action."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VERSION = '0.3.1-rc.1'
SOURCE = '433e89a66038ee7f7c34cb443c03eeafdee92f36'
ARCHIVE_SHA = '0917f468624e35c64829f1591d389fadf51f4528f027d7dc614f1c3fb2b7b750'
OLD = ROOT / 'publication/v0.3'


def write(relative, content):
    path = HERE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def main():
    model = (OLD/'hf-model-card.md').read_text(encoding='utf-8')
    model = model.replace('published 0.3 application revision', 'published 0.3.1 application candidate')
    model = model.replace('[0.3 application candidate]', '[0.3.1 application candidate]').replace('v0.3.0-rc.1', 'v0.3.1-rc.1')
    model += '''
## Recorded application context

![Actual companion task panel](media/companion-tasks.png)

This actual 0.3.1 software-review capture shows existing personal engineering tasks. It contains no flown mission or customer activity. The screenshot is recorded evidence, not an interactive assistant or a new training example. No model reply was requested for this capture.

The installed application's owned companion animates during normal motion mode. Its fallback also animates; user pause and reduced-motion preferences take precedence. Conversations and personal tasks are private to the signed-in actor. Typed internal draft actions require explicit confirmation and current server-enforced permissions and input versions. The application uses the shared System Lab agent core through domain-specific tools. This does not grant the student authority to approve its own work.

Candidate 0.3.1 passed 479 source tests and a separate exact-archive installation with 479 passed and 20 skipped. Its interface suite passed 123 tests. Nineteen PostgreSQL tests, actual containers, worker/API completion and restoration are recorded in [CI41118769822](https://github.com/michelegiletto-beep/airspace-operations/actions/runs/41118769822). Those software results are separate from this student's unchanged evaluation. [Inspect frozen source433e89](https://github.com/michelegiletto-beep/airspace-operations/tree/433e89a66038ee7f7c34cb443c03eeafdee92f36).
'''
    write('model/README.md', model)
    dataset = (OLD/'hf-dataset-card.md').read_text(encoding='utf-8')
    dataset = dataset.replace('published 0.3 application revision', 'published 0.3.1 application candidate')
    dataset = dataset.replace('interaction changes in 0.3', 'interaction changes through 0.3.1').replace('v0.3.0-rc.1', 'v0.3.1-rc.1')
    dataset += '\nThe 0.3.1 publication changes only the application presentation. No dataset rows, original checksums, annotations, weights or evaluation results are replaced by this card update. Application screenshots are kept outside the dataset records and do not become factual training evidence.\n'
    write('dataset/README.md', dataset)
    readme = (OLD/'hf-space/README.md').read_text(encoding='utf-8')
    readme = readme.replace('0.3.0-rc.1', VERSION).replace('407 software tests', '479 software tests').replace('107 interface tests', '123 interface tests')
    readme = readme.replace('served from the frozen source commit', 'copied byte-for-byte from the frozen source commit433e89')
    readme += f'\nThe exact ZIP is 12,504,321 bytes, SHA-256 `{ARCHIVE_SHA}`. Current candidate verification is [CI41118769822](https://github.com/michelegiletto-beep/airspace-operations/actions/runs/41118769822). The original mobile capture has JPEG bytes under a `.png` filename in the frozen release; this viewer uses an identical `.jpg` copy and preserves the release unchanged.\n'
    write('space/README.md', readme)
    page = (OLD/'hf-space/index.html').read_text(encoding='utf-8')
    page = page.replace('0.3.0-rc.1', VERSION).replace('11,675,616', '12,504,321').replace('407 software tests', '479 software tests').replace('107 tests', '123 tests')
    page = page.replace('40803017486', '41118769822').replace('4a004e21dd04633e82c330f191745ad9b31bd65d8424183d0b66cfd00243763e', ARCHIVE_SHA)
    page = page.replace('https://raw.githubusercontent.com/michelegiletto-beep/airspace-operations/331b6e220fec5254c4c2f167cab3ad86d8905456/publication/media/v0.3/desktop-companion.jpg', 'media/application-tasks.png')
    page = page.replace('https://raw.githubusercontent.com/michelegiletto-beep/airspace-operations/331b6e220fec5254c4c2f167cab3ad86d8905456/publication/media/v0.3/mobile-companion.jpg', 'media/companion-tasks-mobile.jpg')
    page = page.replace('Mobile companion panel from the same software-review environment.', 'Actual mobile task panel. The frozen capture contains JPEG bytes under a PNG filename; this identical copy uses .jpg. No frozen release file was replaced.')
    page = page.replace('Persistent application and contextual assistance. Software-review workspace; no fictional aircraft or customer activity.', 'Actual 0.3.1 application with existing personal engineering tasks. No operational aircraft, missions or customer activity are populated.')
    page = page.replace('<p>The installed product keeps', '<p><a href="https://github.com/michelegiletto-beep/airspace-operations/tree/'+SOURCE+'">Inspect the exact frozen source and evidence</a>. The screenshot capture requested no new model generation; it is not a training example.</p><p>The installed product keeps')
    page = page.replace('<p><a href="https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.2.0-rc.1">Open the published 0.2 application release</a></p>', '<p>Previous candidates remain available: <a href="https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.0-rc.1">0.3.0</a> and <a href="https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.2.0-rc.1">0.2.0</a>.</p>')
    write('space/index.html', page)
    shutil.copyfile(OLD/'hf-space/styles.css', HERE/'space/styles.css')
    images = [
        ('companion-tasks.png', 'model/media/companion-tasks.png'),
        ('application-tasks.png', 'space/media/application-tasks.png'),
        ('companion-tasks-mobile.png', 'space/media/companion-tasks-mobile.jpg'),
    ]
    for source_name, relative in images:
        target = HERE/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/'publication/media'/VERSION/source_name, target)
    notice = (ROOT/'LICENSES/LicenseRef-SystemLab-Assets.txt').read_text(encoding='utf-8')
    notice += '\nThese presentation captures retain reserved artwork/runtime rights. Newly authored publication prose and static viewer code use the project Apache-2.0 licence; the student, source documents and upstream models retain their separate terms. Screenshots are not dataset records or permission to reuse the companion independently.\n'
    write('model/NOTICE.md', notice)
    # Historical source/evidence files remain in the existing Space. Preserve
    # their complete notice rather than replacing it with an artwork-only one.
    historical_notice = (ROOT/'publication/hf-space/NOTICE.md').read_text(encoding='utf-8')
    write('space/NOTICE.md', historical_notice + '\n' + notice)
    groups = [('model','model','Magic51/system-lab-airspace-shall-router'),
              ('dataset','dataset','Magic51/system-lab-airspace-source-annotations'),
              ('space','space','Magic51/system-lab-airspace-evaluation')]
    files = []
    for folder, kind, repo in groups:
        for path in sorted((HERE/folder).rglob('*')):
            if path.is_file():
                files.append({'source':path.relative_to(ROOT).as_posix(),'repo_type':kind,'repo_id':repo,
                              'target':path.relative_to(HERE/folder).as_posix(),'bytes':path.stat().st_size,
                              'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {'prepared_at':datetime.now(timezone.utc).isoformat(),'state':'Prepared','presentation_only':True,
                'application_version':VERSION,'application_source':SOURCE,'files':files,
                'new_uploads':False,'weights_changed':False,'dataset_records_changed':False,'live_inference':False,
                'publication_blocker':'Existing supported Hugging Face write access is unavailable; browser signed out and configured token absent',
                'publish_procedure':['Recheck existing account Magic51 and exact write permissions using supported authentication',
                                     'Re-read all three remote revisions and reconcile newer edits before any commit',
                                     'Commit only each listed target file to its existing matching repository; preserve all unlisted historical artifacts',
                                     'Do not upload prepare.py, validator, manifest, model weights, dataset rows or private runtime files',
                                     'Retrieve each changed file at its returned immutable revision, compare bytes and hashes, then verify actual static Space rendering',
                                     'Record Uploaded, Published and Independently Retrieved separately; retain rollback revision identifiers'],
                'archive_bytes':12504321,'archive_sha256':ARCHIVE_SHA,'release_ci':41118769822,
                'rights':'Owner-authorised official screenshots retain reserved rights; no source documents or new training artifacts are redistributed'}
    write('manifest.json', json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'state':'Prepared','target_files':len(files),'total_bytes':sum(row['bytes'] for row in files),'network_actions':False}))


if __name__ == '__main__':
    main()
