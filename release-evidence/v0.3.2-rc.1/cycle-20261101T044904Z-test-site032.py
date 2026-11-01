"""Isolated identity/HTML negative controls. No network or publication actions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import urllib.request

import pytest

SPEC = importlib.util.spec_from_file_location("independent_site032", Path(__file__).with_name("cycle-20261101T044904Z-verify-site032.py"))
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)
CURRENT, PRIOR = "a" * 64, "b" * 64
OLD = "4a004e21dd04633e82c330f191745ad9b31bd65d8424183d0b66cfd00243763e"


def page():
    text = ('<html><head><link rel="stylesheet" href="/assets/isolated.css"></head><body>'
            'System Lab Airspace Operations 0.3.2-rc.1 0.3.1-rc.1 '
            'original specification is not fully accepted animated fallback reduced-motion '
            + CURRENT + PRIOR + OLD
            + '<section id="release-0-3-2" data-state="Published"></section>'
            + '<section id="release-0-3-1" data-state="Published"></section>')
    for version in ("0.1.0-rc.1", "0.2.0-rc.1", "0.3.0-rc.1", "0.3.1-rc.1"):
        text += f'<a href="https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v{version}">History</a>'
    for version in ("0.3.0-rc.1", "0.3.1-rc.1", "0.3.2-rc.1"):
        text += f'<a href="/airspace-operations/releases/{version}/System-Lab-Airspace-Operations-{version}.zip">ZIP</a>'
    for path in sorted(s.history.CURRENT_CAPTURE_PATHS | {s.PHONE_PATH}):
        text += f'<a href="{path}">Capture</a>'
        if path != '/airspace-operations/media/0.3.1-rc.1/companion-tasks.png':
            text += f'<img src="{path}">'
    text += ''.join(f'<a href="{path}">Historical capture</a>' for path in sorted(s.history.HISTORICAL_IMAGES))
    return (text + '</body></html>').encode()


def checks(actual=None):
    source = page()
    return s.semantic_checks({'path': '/projects/airspace-operations', '_source': source}, source if actual is None else actual, CURRENT, PRIOR)


def test_current_and_both_historical_candidate_assertions_all_pass():
    result = checks()
    assert all(result.values())
    assert result['history031_two_current_displayed_images']
    assert result['history031_all_three_current_capture_links']
    assert result['history030_archive_digest_visible']


@pytest.mark.parametrize('extra', [b'<script>unreviewed()</script>', b'<style>body{display:none}</style>', b'<script src="/extra.js"></script>'])
def test_extra_active_content_is_not_hidden_by_version_specific_checks(extra):
    result = checks(page().replace(b'</body>', extra + b'</body>'))
    assert not result['source_scripts_styles_match']
    assert not result['authored_html_matches_source_after_observed_hosting_injection']


@pytest.mark.parametrize('path,key', [
    (s.PHONE_PATH, 'current032_phone_displayed'),
    ('/airspace-operations/media/0.3.1-rc.1/application-tasks.png', 'history031_two_current_displayed_images'),
])
def test_current_or_preserved_capture_cannot_be_replaced_by_only_a_link(path, key):
    result = checks(page().replace(f'<img src="{path}">'.encode(), b''))
    assert not result[key] and not result['source_images_equal']


@pytest.mark.parametrize('removed,key', [
    (CURRENT, 'current032_archive_digest_visible'),
    (PRIOR, 'history031_verified_archive_digest'),
    (OLD, 'history030_archive_digest_visible'),
    ('id="release-0-3-2" data-state="Published"', 'published032_section'),
])
def test_current_and_historical_digest_or_status_cannot_disappear(removed, key):
    assert not checks(page().replace(removed.encode(), b'Changed isolated fixture'))[key]


@pytest.fixture
def receipts(tmp_path, monkeypatch):
    evidence, source = tmp_path / 'evidence', tmp_path / 'source'
    evidence.mkdir()
    monkeypatch.setattr(s, 'EVIDENCE', evidence)
    assets = []
    for name in sorted(s.ASSET_NAMES):
        data = ('Isolated software identity fixture: ' + name).encode()
        path = source / f'public/airspace-operations/releases/{s.VERSION}' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        assets.append({'name': name, 'bytes': len(data), 'sha256': s.v.digest(data), 'status': 200, 'github_digest_matches': True})
    # Arbitrary identity bytes are confined to this test. Actual image decoding
    # and provenance belong to the independently retrieved upstream media proof.
    data = b'Isolated software media identity fixture only'
    path = source / 'public' / s.PHONE_PATH.lstrip('/')
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    downloads = {'version': s.VERSION, 'state': 'Independently Retrieved', 'source_commit': s.SOURCE, 'assets': assets}
    media = {'state': 'Independently Retrieved', 'source_commit': s.SOURCE, 'media': [{'path': f'publication/media/{s.VERSION}/{s.PHONE_NAME}', 'encoding': 'JPEG', 'bytes': len(data), 'sha256': s.v.digest(data), 'status': 200, 'container_validated': True, 'matches_public_source_and_exact_archive': True}]}
    def save():
        for name, value in [('public-downloads', downloads), ('public-media', media)]:
            (evidence / f'{s.STAMP}-{name}.json').write_text(json.dumps(value), encoding='utf-8')
    save()
    return source, downloads, media, save


def test_targets_bind_all_nine_assets_and_the_phone_identity(receipts):
    source, downloads, media, save = receipts
    targets, checksum = s.verified_current_targets(source)
    assert len(targets) == len({row['url'] for row in targets}) == 10
    assert checksum == next(row['sha256'] for row in downloads['assets'] if row['name'].endswith('.zip'))


@pytest.mark.parametrize('which', ['downloads', 'media'])
def test_wrong_source_or_unpublished_receipt_is_not_accepted(receipts, which):
    source, downloads, media, save = receipts
    row = downloads if which == 'downloads' else media
    for field, value in [('source_commit', 'f' * 40), ('state', 'Prepared')]:
        original = row[field]
        row[field] = value
        save()
        with pytest.raises(ValueError, match='independently retrieved'):
            s.verified_current_targets(source)
        row[field] = original


@pytest.mark.parametrize('change', ['duplicate', 'status', 'github_digest', 'bytes', 'oversize'])
def test_unverified_or_changed_release_asset_is_rejected(receipts, change):
    source, downloads, media, save = receipts
    if change == 'duplicate':
        downloads['assets'][0] = downloads['assets'][1].copy()
    elif change == 'status':
        downloads['assets'][0]['status'] = 503
    elif change == 'github_digest':
        downloads['assets'][0]['github_digest_matches'] = False
    elif change == 'bytes':
        downloads['assets'][0]['sha256'] = 'c' * 64
    else:
        downloads['assets'][0]['bytes'] = s.v.legacy.MAX_RESPONSE_BYTES + 1
    save()
    with pytest.raises(ValueError):
        s.verified_current_targets(source)


@pytest.mark.parametrize('change', ['name', 'encoding', 'identity', 'extra', 'status', 'container', 'provenance'])
def test_wrong_phone_capture_or_extra_media_is_not_accepted(receipts, change):
    source, downloads, media, save = receipts
    if change == 'name':
        media['media'][0]['path'] = 'publication/media/other.jpg'
    elif change == 'encoding':
        media['media'][0]['encoding'] = 'PNG'
    elif change == 'identity':
        media['media'][0]['sha256'] = 'd' * 64
    elif change == 'extra':
        media['media'].append(media['media'][0].copy())
    elif change == 'status':
        media['media'][0]['status'] = 503
    elif change == 'container':
        media['media'][0]['container_validated'] = False
    else:
        media['media'][0]['matches_public_source_and_exact_archive'] = False
    save()
    with pytest.raises(ValueError):
        s.verified_current_targets(source)


def test_import_has_no_argument_parsing_workers_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Import must not execute verification')
    monkeypatch.setattr(argparse.ArgumentParser, 'parse_args', forbidden)
    monkeypatch.setattr(ThreadPoolExecutor, '__init__', forbidden)
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', forbidden)
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    assert callable(module.main)


def test_existing_output_fails_before_source_or_network_work(tmp_path, monkeypatch):
    monkeypatch.setattr(s, 'ROOT', tmp_path)
    path = tmp_path / 'existing.json'
    path.write_text('Retain prior evidence')
    monkeypatch.setattr(s.v, 'assert_deployment_source', lambda *args: pytest.fail('Existing output must fail first'))
    with pytest.raises(SystemExit):
        s.main(['--version-number', '99', '--source-commit', 'a' * 40, '--deployment-id', 'appgdep_isolated', '--output', str(path)])
    assert path.read_text() == 'Retain prior evidence'


def test_outside_output_and_late_creation_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(s, 'ROOT', tmp_path / 'project')
    with pytest.raises(ValueError, match='inside this project'):
        s.fresh_output(str(tmp_path / 'outside.json'))
    s.ROOT.mkdir()
    path = s.fresh_output('new.json')
    path.write_text('Created after path validation')
    with pytest.raises(FileExistsError):
        s.write_report(path, {'must_not_replace': True})
    assert path.read_text() == 'Created after path validation'


@pytest.mark.parametrize('base_count,prior_count,current_count,duplicate', [
    (36, 12, 10, False), (37, 11, 10, False),
    (37, 12, 9, False), (37, 12, 10, True),
])
def test_resource_counts_and_distinctness_fail_before_network(
    tmp_path, monkeypatch, base_count, prior_count, current_count, duplicate
):
    monkeypatch.setattr(s, 'ROOT', tmp_path)
    monkeypatch.setattr(s.v, 'assert_deployment_source', lambda *args: 'a' * 40)
    targets = lambda prefix, count: [{'url': f'https://example.invalid/{prefix}/{number}'} for number in range(count)]
    base, prior, current = targets('base', base_count), targets('prior', prior_count), targets('current', current_count)
    if duplicate:
        current[0] = base[0].copy()
    monkeypatch.setattr(s.v, 'build_targets', lambda *args: base)
    monkeypatch.setattr(s.history, 'verified_new_targets', lambda *args: (prior, PRIOR))
    monkeypatch.setattr(s, 'verified_current_targets', lambda *args: (current, CURRENT))
    monkeypatch.setattr(ThreadPoolExecutor, '__init__', lambda *args, **kwargs: pytest.fail('Bad resource sets must fail before network workers'))
    with pytest.raises(SystemExit):
        s.main(['--version-number', '99', '--source-commit', 'a' * 40,
                '--deployment-id', 'appgdep_isolated', '--output', str(tmp_path / 'new.json')])
    assert not (tmp_path / 'new.json').exists()
