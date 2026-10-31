"""Isolated negative controls for0.3.1 publication verification; no network."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import urllib.request

import pytest

SPEC = importlib.util.spec_from_file_location("site_public_031", Path(__file__).resolve().parents[1] / "scripts/verify_site_031.py")
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)
ARCHIVE = "a" * 64


def page(images=None, historical=True, detail_link=True):
    images = v.DISPLAYED_CURRENT_IMAGES if images is None else images
    content = ('<html><body>System Lab Airspace Operations0.3.1-rc.1 Published '
               'original specification is not fully accepted animated fallback reduced-motion ' + ARCHIVE +
               '<section id="release-0-3-1" data-state="Published"></section>' +
               f'<a href="/airspace-operations/releases/{v.VERSION}/System-Lab-Airspace-Operations-{v.VERSION}.zip">Download</a>')
    for version in ("0.1.0-rc.1", "0.2.0-rc.1", "0.3.0-rc.1"):
        content += '<a href="https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v' + version + '">History</a>'
    content += ''.join('<a href="' + image + '"><img src="' + image + '"></a>' for image in sorted(images))
    if detail_link:
        content += f'<a href="/airspace-operations/media/{v.VERSION}/companion-tasks.png">Task detail capture</a>'
    if historical:
        content += ''.join('<a href="' + image + '">Historical capture</a>' for image in sorted(v.HISTORICAL_IMAGES))
    return (content + '</body></html>').encode()


def checks(source, actual=None):
    return v.semantic_checks({'path': '/projects/airspace-operations', '_source': source}, source if actual is None else actual, ARCHIVE)


def test_current_images_and_real_historical_links_pass():
    result = checks(page())
    assert all(result.values())
    assert result['two_current_displayed_images']
    assert result['all_three_current_capture_links']
    assert result['source_historical03_image_links_preserved']
    assert 'two_actual_captures' not in result


@pytest.mark.parametrize('missing', sorted(v.DISPLAYED_CURRENT_IMAGES))
def test_every_current_image_is_required_even_if_replaced_with_link(missing):
    source = page()
    actual = source.replace(('<img src="' + missing + '">').encode(), ('<a href="' + missing + '">Capture</a>').encode())
    result = checks(source, actual)
    assert not result['two_current_displayed_images']
    assert not result['source_images_equal']


def test_old_images_alone_cannot_satisfy_current_capture_requirement():
    result = checks(page(images=v.HISTORICAL_IMAGES))
    assert not result['two_current_displayed_images']
    assert result['source_images_equal']


def test_current_images_as_links_cannot_satisfy_capture_requirement():
    source = page(images=[])
    source = source.replace(b'</body>', ''.join('<a href="' + image + '">Capture</a>' for image in v.CURRENT_CAPTURE_PATHS).encode() + b'</body>')
    assert not checks(source)['two_current_displayed_images']


def test_task_detail_capture_link_is_required_separately_from_two_displayed_images():
    result = checks(page(detail_link=False))
    assert result['two_current_displayed_images']
    assert not result['all_three_current_capture_links']


def test_historical_links_are_checked_only_when_the_source_contains_them():
    source = page(historical=False)
    assert 'source_historical03_image_links_preserved' not in checks(source)
    source = page()
    missing = next(iter(v.HISTORICAL_IMAGES))
    actual = source.replace(('<a href="' + missing + '">Historical capture</a>').encode(), b'')
    assert not checks(source, actual)['source_historical03_image_links_preserved']


@pytest.mark.parametrize('extra', [b'<style>body{display:none}</style>', b'<script>steal()</script>', b'<script src="/unreviewed.js"></script>'])
def test_unrelated_style_and_script_changes_remain_rejected(extra):
    source = page()
    result = checks(source, source.replace(b'</body>', extra + b'</body>'))
    assert not result['source_scripts_styles_match']
    assert not result['authored_html_matches_source_after_observed_hosting_injection']


def test_existing_output_is_rejected_before_any_source_or_network_work(tmp_path, monkeypatch):
    monkeypatch.setattr(v, 'ROOT', tmp_path)
    output = tmp_path / 'existing.json'
    output.write_text('Preserve original evidence')
    def forbidden(*args):
        pytest.fail('Existing output must fail before source validation or network access')
    monkeypatch.setattr(v.v, 'assert_deployment_source', forbidden)
    with pytest.raises(SystemExit):
        v.main(['--version-number', '98', '--source-commit', 'b' * 40, '--deployment-id', 'appgdep_test', '--output', str(output)])
    assert output.read_text() == 'Preserve original evidence'


def test_output_is_explicit_and_exclusive_creation_protects_races(tmp_path, monkeypatch):
    monkeypatch.setattr(v, 'ROOT', tmp_path)
    with pytest.raises(SystemExit):
        v.main(['--version-number', '98', '--source-commit', 'b' * 40, '--deployment-id', 'appgdep_test'])
    output = v.fresh_output_path('new.json')
    output.write_text('Created after initial path check')
    with pytest.raises(FileExistsError):
        v.write_report(output, {'not_written': True})
    assert output.read_text() == 'Created after initial path check'


def test_import_does_not_parse_arguments_start_workers_or_access_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Import must only define the read-only verifier')
    monkeypatch.setattr(argparse.ArgumentParser, 'parse_args', forbidden)
    monkeypatch.setattr(ThreadPoolExecutor, '__init__', forbidden)
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', forbidden)
    imported = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(imported)
    assert callable(imported.main)


@pytest.fixture
def receipts(tmp_path, monkeypatch):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    monkeypatch.setattr(v, 'EVIDENCE', evidence)
    source = tmp_path / 'source'
    assets, captures = [], []
    names = [f'System-Lab-Airspace-Operations-{v.VERSION}.zip'] + [f'asset{number}.txt' for number in range(8)]
    for name in names:
        data = ('Isolated permitted software fixture ' + name).encode()
        path = source / f'public/airspace-operations/releases/{v.VERSION}' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        assets.append({'name': name, 'bytes': len(data), 'sha256': v.v.digest(data)})
    for public_path in sorted(v.CURRENT_CAPTURE_PATHS):
        data = ('Isolated capture identity fixture ' + public_path).encode()
        path = source / 'public' / public_path.lstrip('/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        original = path.name.replace('companion-tasks-mobile.jpg', 'companion-tasks-mobile.png')
        captures.append({'path': 'publication/media/' + original, 'bytes': len(data), 'sha256': v.v.digest(data)})
    downloads = {'state': 'Independently Retrieved', 'source_commit': v.SOURCE, 'assets': assets}
    media = {'state': 'Independently Retrieved', 'source_commit': v.SOURCE, 'media': captures}
    def save():
        (evidence / (v.STAMP + '-public-downloads.json')).write_text(json.dumps(downloads), encoding='utf-8')
        (evidence / (v.STAMP + '-public-media.json')).write_text(json.dumps(media), encoding='utf-8')
    save()
    return source, downloads, media, save


def test_verified_targets_bind_all_twelve_local_asset_identities(receipts):
    source, downloads, media, save = receipts
    targets, archive = v.verified_new_targets(source)
    assert len(targets) == 12
    assert archive == downloads['assets'][0]['sha256']
    assert {row['path'] for row in targets if '/media/' in row['path']} == v.CURRENT_CAPTURE_PATHS


@pytest.mark.parametrize('receipt', ['downloads', 'media'])
def test_wrong_frozen_source_identity_is_rejected(receipts, receipt):
    source, downloads, media, save = receipts
    (downloads if receipt == 'downloads' else media)['source_commit'] = 'f' * 40
    save()
    with pytest.raises(ValueError, match='receipts are required'):
        v.verified_new_targets(source)


@pytest.mark.parametrize('kind', ['asset', 'capture'])
def test_changed_local_asset_or_capture_bytes_are_rejected(receipts, kind):
    source, downloads, media, save = receipts
    relative = (f'public/airspace-operations/releases/{v.VERSION}/' + downloads['assets'][0]['name'] if kind == 'asset'
                else 'public' + sorted(v.CURRENT_CAPTURE_PATHS)[0])
    (source / relative).write_bytes(b'Altered isolated software fixture')
    with pytest.raises(ValueError, match='differs from frozen public'):
        v.verified_new_targets(source)


def test_duplicate_capture_rows_do_not_satisfy_three_capture_requirement(receipts):
    source, downloads, media, save = receipts
    media['media'][1] = media['media'][0].copy()
    save()
    with pytest.raises(ValueError, match='three distinct current captures'):
        v.verified_new_targets(source)


def test_unrelated_capture_name_is_not_admitted_by_three_row_count(receipts):
    source, downloads, media, save = receipts
    media['media'][0]['path'] = 'publication/media/unrelated.png'
    save()
    with pytest.raises(ValueError, match='three current captures'):
        v.verified_new_targets(source)
