"""Verify the deployed Airspace 0.3 dossier and preserved releases anonymously.

Run only after a successful deployment. Binary identity comes from frozen public
receipts and the selected clean deployed Site checkout. Three HTML pages compare
text, exact link/image sets, script/style elements and authored HTML bytes after
removal of one exact observed hosting script. A repeated hosting-only comparison
is retained. No credentials, proxies, uploads or model calls are used.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://giletto-systems-lab.michele-giletto.chatgpt.site'
PROJECT = 'appgprj_6a8fdd39ede88191898e6f386864c331'
EVIDENCE = ROOT / 'release-evidence/v0.3.0-rc.1'
LEGACY_SPEC = importlib.util.spec_from_file_location('airspace_v2_public_verifier', ROOT / 'scripts/verify_publication_v2.py')
legacy = importlib.util.module_from_spec(LEGACY_SPEC)
LEGACY_SPEC.loader.exec_module(legacy)

# Exact script body observed on the three deployed public pages on30October2026.
# Only validated per-request r/t values may differ; this is not a script allowlist.
OBSERVED_CF_SCRIPT = b'''(function(){function c(){var b=a.contentDocument||(a.contentWindow&&a.contentWindow.document);if(b){var d=b.createElement('script');d.innerHTML="window.__CF$cv$params={r:'REQUEST_ID',t:'TIMESTAMP'};var l=window.parent.location,o;try{o=new URL(l.origin).origin}catch(e){try{o=new URL(new URL(l.href).origin).origin}catch(e){o=''}}var u='/cdn-cgi/challenge-platform/scripts/jsd/main.js?ray=REQUEST_ID',a=document.createElement('script');a.src=o?new URL(u,o).href:u;document.getElementsByTagName('head')[0].appendChild(a);";b.getElementsByTagName('head')[0].appendChild(d)}}if(document.body){var a=document.createElement('iframe');a.height=1;a.width=1;a.style.position='absolute';a.style.top=0;a.style.left=0;a.style.border='none';a.style.visibility='hidden';document.body.appendChild(a);if('loading'!==document.readyState)c();else if(window.addEventListener)document.addEventListener('DOMContentLoaded',c);else{var e=document.onreadystatechange||function(){};document.onreadystatechange=function(b){e(b);'loading'!==document.readyState&&(document.onreadystatechange=e,c())}}}})();'''
CF_SCRIPT_ELEMENT = re.compile(rb'<script>(\(function\(\)\{function c\(\).*?)</script>', re.DOTALL)


class ActiveContentHTML(HTMLParser):
    """Compare script/style attributes, order and exact contents without execution."""
    def __init__(self, content: bytes):
        super().__init__(convert_charrefs=False)
        self.elements = []
        self.active = None
        self.feed(content.decode('utf-8', errors='strict'))

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.active = {'tag': tag, 'attrs': attrs, 'text': ''}

    def handle_data(self, data):
        if self.active is not None:
            self.active['text'] += data

    def handle_endtag(self, tag):
        if self.active is not None and tag == self.active['tag']:
            self.elements.append(self.active)
            self.active = None


def remove_observed_hosting_injection(content: bytes) -> bytes:
    matches = [match for match in CF_SCRIPT_ELEMENT.finditer(content)
               if normalise_hosting_parameters(match[1]) == OBSERVED_CF_SCRIPT]
    if len(matches) != 1:
        return content
    match = matches[0]
    return content[:match.start()] + content[match.end():]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_deployment_source(source: Path, source_commit: str) -> str:
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=source, text=True, capture_output=True, check=True, timeout=20).stdout.strip()
    if head != source_commit:
        raise ValueError('Current Site source does not match the successful deployment source')
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all', '--', 'public', '.openai/hosting.json'], cwd=source, text=True, capture_output=True, check=True, timeout=20).stdout
    if dirty.strip():
        raise ValueError('Public Site source changed after the deployed source commit; preserve those changes and verify the matching deployment')
    return head


def source_path(source: Path, url_path: str) -> Path:
    if not isinstance(url_path, str) or not url_path.startswith('/') or '\\' in url_path or any(part in {'.', '..'} for part in url_path.split('/')) or '?' in url_path or '#' in url_path:
        raise ValueError('Invalid fixed Site resource path')
    relative = 'index.html' if url_path == '/' else url_path.lstrip('/')
    if url_path in {'/projects/airspace-operations', '/projects/multiagentic-systems'}:
        relative += '.html'
    public = (source / 'public').resolve()
    path = (public / relative).resolve()
    if not path.is_relative_to(public) or not path.is_file():
        raise ValueError('Expected resource is absent or outside the public source')
    return path


def exact_target(path: str, size: int, sha: str) -> dict:
    if type(size) is not int or not 0 < size <= legacy.MAX_RESPONSE_BYTES or not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('Expected public digest or byte limit is invalid')
    legacy.validate_url(SITE + path, resolve=False)
    return {'destination': 'site', 'path': path, 'url': SITE + path,
            'expected_bytes': size, 'expected_sha256': sha, 'verification_mode': 'exact'}


def build_targets(source: Path) -> list[dict]:
    source = source.resolve()
    if not source.is_relative_to((ROOT / 'work').resolve()):
        raise ValueError('Site source must be an opened checkout inside this project work directory')
    binding = json.loads((source / '.openai/hosting.json').read_text())
    if binding.get('project_id') != PROJECT:
        raise ValueError('Site checkout is bound to a different project')
    previous = json.loads((ROOT / 'release-evidence/v0.2.0-rc.1/system-lab-public-verification.json').read_text())
    current = json.loads((EVIDENCE / 'cycle-20261030-public-downloads.json').read_text())
    if previous.get('state') != 'Independently Retrieved' or current.get('state') != 'Independently Retrieved':
        raise ValueError('Frozen publication receipts are required')
    targets = []
    pages = {'/': 'index.html', '/projects/airspace-operations': 'projects/airspace-operations.html', '/projects/multiagentic-systems': 'projects/multiagentic-systems.html'}
    for path in pages:
        data = source_path(source, path).read_bytes()
        if len(data) > legacy.MAX_HTML_BYTES:
            raise ValueError('Source HTML exceeds the semantic inspection bound')
        targets.append({'destination': 'site', 'path': path, 'url': SITE + path, 'expected_bytes': len(data), 'expected_sha256': digest(data), 'verification_mode': 'semantic', '_source': data})
    for row in previous['checks']:
        if row['path'] in pages or row['path'] == '/assets/airspace-project.css':
            continue
        path = source_path(source, row['path'])
        if digest(path.read_bytes()) != row['sha256'] or path.stat().st_size != row['bytes']:
            raise ValueError('A frozen historical Site resource changed in the checkout')
        targets.append(exact_target(row['path'], row['bytes'], row['sha256']))
    if len(current['assets']) != 9 or current.get('source_commit') != '331b6e220fec5254c4c2f167cab3ad86d8905456':
        raise ValueError('Current release receipt identity changed')
    for row in current['assets']:
        if Path(row['name']).name != row['name'] or '\\' in row['name']:
            raise ValueError('Invalid candidate asset name')
        path = '/airspace-operations/releases/0.3.0-rc.1/' + row['name']
        content = source_path(source, path).read_bytes()
        if len(content) != row['bytes'] or digest(content) != row['sha256']:
            raise ValueError('Site candidate bytes differ from independently downloaded release')
        targets.append(exact_target(path, row['bytes'], row['sha256']))
    media = json.loads((EVIDENCE / 'cycle-20261030-public-media.json').read_text())
    if media.get('state') != 'Independently Retrieved' or len(media['media']) != 2:
        raise ValueError('Verified current capture receipt is required')
    for row in media['media']:
        path = '/airspace-operations/media/v0.3/' + Path(row['path']).name
        data = source_path(source, path).read_bytes()
        if len(data) != row['bytes'] or digest(data) != row['sha256']:
            raise ValueError('Site capture differs from independently retrieved media')
        targets.append(exact_target(path, row['bytes'], row['sha256']))
    css_path = '/assets/airspace-project.css'
    css = source_path(source, css_path).read_bytes()
    targets.append(exact_target(css_path, len(css), digest(css)))
    if len(targets) != 37 or len({row['url'] for row in targets}) != 37:
        raise ValueError('Expected exactly 37 distinct publication resources')
    return targets


def visible(page) -> str:
    return ' '.join(' '.join(page.text).split())


def semantic_checks(target: dict, content: bytes) -> dict:
    reference = legacy.PresentationHTML(target['_source'])
    page = legacy.PresentationHTML(content)
    authored = visible(page)
    without_hosting = remove_observed_hosting_injection(content)
    checks = {
        'visible_text_matches_source': authored == visible(reference),
        'source_links_equal': reference.links == page.links,
        'source_images_equal': reference.images == page.images,
        'source_scripts_styles_match': ActiveContentHTML(without_hosting).elements == ActiveContentHTML(target['_source']).elements,
        'authored_html_matches_source_after_observed_hosting_injection': without_hosting == target['_source'],
    }
    if target['path'] == '/projects/airspace-operations':
        expected_zip = '/airspace-operations/releases/0.3.0-rc.1/System-Lab-Airspace-Operations-0.3.0-rc.1.zip'
        checks.update({'product_title': 'System Lab Airspace Operations' in authored, 'published_candidate_visible': '0.3.0-rc.1 Published' in authored,
                       'verified_archive_digest': '4a004e21dd04633e82c330f191745ad9b31bd65d8424183d0b66cfd00243763e' in authored,
                       'candidate_download_link': expected_zip in page.links,
                       'two_actual_captures': all('/airspace-operations/media/v0.3/' + name in page.images for name in ['desktop-companion.jpg', 'mobile-companion.jpg']),
                       'frozen_current_document_links': all('/blob/main/' not in link and '/tree/main/' not in link for link in page.links),
                       'original_acceptance_limit': 'original specification is not fully accepted' in authored,
                       'animation_accessibility': 'animated fallback' in authored and 'reduced-motion' in authored,
                       'historical_release_links': all('https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v' + version in page.links for version in ['0.1.0-rc.1', '0.2.0-rc.1'])})
    else:
        checks['existing_airspace_link'] = bool({'/projects/airspace-operations', '/projects/airspace-operations.html'} & page.links)
        if target['path'] == '/projects/multiagentic-systems':
            checks['existing_interval_relationship'] = 'Interval' in authored
    return checks


def normalise_hosting_parameters(content: bytes) -> bytes:
    # The new observed Cloudflare injection repeats its request r value inside
    # one fixed challenge-script literal. Do not normalise arbitrary URL queries,
    # other script content or a ray value inconsistent with the params record.
    params = list(legacy.CF_PARAMETERS.finditer(content))
    if len(params) != 1 or not re.fullmatch(rb"[0-9a-f]{16}", params[0][2]):
        return content
    try:
        timestamp = base64.b64decode(params[0][4], validate=True)
    except (ValueError, binascii.Error):
        return content
    if not re.fullmatch(rb'[0-9]{9,12}', timestamp):
        return content
    prefix = b"var u='/cdn-cgi/challenge-platform/scripts/jsd/main.js?ray="
    suffix = b"',a=document.createElement('script');"
    literal = prefix + params[0][2] + suffix
    if content.count(literal) == 1:
        content = content.replace(literal, prefix + b"REQUEST_ID" + suffix)
    return legacy.normalise_hosting_parameters(content)


def retrieve(target: dict) -> dict:
    if target['verification_mode'] == 'exact':
        return legacy.retrieve(target)
    started = time.monotonic()
    clean_target = {key: value for key, value in target.items() if key != '_source'}
    result = {**clean_target, 'verified': False, 'authenticated_read': False}
    try:
        first, first_redirects = legacy.repeat_html_sample(target['url'], started + legacy.REQUEST_BUDGET_SECONDS)
        second, second_redirects = legacy.repeat_html_sample(target['url'], started + legacy.REQUEST_BUDGET_SECONDS)
        checks = semantic_checks(target, first)
        repeated = semantic_checks(target, second)
        normalised_equal = normalise_hosting_parameters(first) == normalise_hosting_parameters(second)
        result.update({'status': 200, 'bytes': len(first), 'sha256': digest(first), 'length_matches': len(first) == target['expected_bytes'], 'sha256_matches': digest(first) == target['expected_sha256'],
                       'semantic_assertions': checks, 'repeat_semantic_assertions': repeated, 'repeated_normalised_content_equal': normalised_equal,
                       'normalisation_scope': 'A unique16hexadecimal Cloudflare r, strict-base64 decimal timestamp and its matching fixed challenge-script ray literal only. Source HTML bytes and script/style elements are also compared after removal of at most one exact observed Cloudflare script. Authored text, URLs and other active content remain compared. Raw response hashes remain distinct.',
                       'second_sample_sha256': digest(second), 'redirect_hosts': first_redirects.redirect_hosts + second_redirects.redirect_hosts})
        result['verified'] = all(checks.values()) and all(repeated.values()) and normalised_equal
    except HTTPError as exc:
        result.update({'status': exc.code, 'error': 'HTTPError: ' + str(exc.code)})
    except URLError as exc:
        result['error'] = 'URLError: ' + type(exc.reason).__name__
    except (OSError, ValueError, TimeoutError) as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc).split('https://', 1)[0][:240]
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-source', default='work/site-publishing')
    parser.add_argument('--version-number', type=int, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--deployment-id', required=True)
    parser.add_argument('--output', default='runtime/site-publication-recheck-v3.json')
    args = parser.parse_args()
    if args.version_number <= 95 or not re.fullmatch('[0-9a-f]{40}', args.source_commit) or not re.fullmatch('appgdep_[A-Za-z0-9_]+', args.deployment_id):
        parser.error('The actual successful new deployment identity is required')
    source = (ROOT / args.site_source).resolve()
    output = legacy.output_path(args.output)
    try:
        head = assert_deployment_source(source, args.source_commit)
    except ValueError as exc:
        parser.error(str(exc))
    targets = build_targets(source)
    started = time.monotonic()
    report = {'release': '0.3.0-rc.1', 'checked_at': datetime.now(timezone.utc).isoformat(), 'source_commit': head, 'version_number': args.version_number, 'deployment_id': args.deployment_id,
              'deployment_identity_scope': 'Successful deployment identity supplied by the owner workflow; content is independently checked by anonymous HTTP reads.',
              'authenticated_read': False, 'remote_mutations_performed': False, 'environment_proxies_used': False,
              'limits': {'workers': 4, 'max_response_bytes': legacy.MAX_RESPONSE_BYTES, 'per_resource_seconds': legacy.REQUEST_BUDGET_SECONDS, 'allowed_hosts': sorted(legacy.ALLOWED_HOSTS)}}
    with ThreadPoolExecutor(max_workers=4) as pool:
        report['checks'] = list(pool.map(retrieve, targets))
    report['summary'] = {'expected': 37, 'http_200': sum(row.get('status') == 200 for row in report['checks']),
                         'verified': sum(row['verified'] for row in report['checks']),
                         'exact': sum(row['verified'] and row['verification_mode'] == 'exact' for row in report['checks']),
                         'semantic': sum(row['verified'] and row['verification_mode'] == 'semantic' for row in report['checks'])}
    report['success'] = all(row['verified'] for row in report['checks'])
    report['state'] = 'Independently Retrieved' if report['success'] else 'Verification failed'
    report['elapsed_seconds'] = round(time.monotonic() - started, 3)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'state': report['state'], 'summary': report['summary'], 'output': str(output.relative_to(ROOT))}, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
