"""Anonymously recheck the frozen 0.2 public publication manifests using stdlib only.

This reads historical evidence without changing it. A new result is written under
runtime by default. No credentials, cookies, environmental proxies, uploads,
model execution or operational services are used.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import socket
import ssl
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import (
    HTTPSHandler,
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "release-evidence/v0.2.0-rc.1"
SITE = "https://giletto-systems-lab.michele-giletto.chatgpt.site"
GITHUB_REPOSITORY = "https://github.com/michelegiletto-beep/airspace-operations"
HF_REPOSITORY = "https://huggingface.co/spaces/Magic51/system-lab-airspace-evaluation"
REPORTS = {
    "github": ("github-public-verification.json", "assets", 9),
    "site": ("system-lab-public-verification.json", "checks", 26),
    "hf": ("hf-space-final-public-verification.json", "files", 21),
}
ALLOWED_HOSTS = frozenset({
    "github.com",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.hf.co",
    "cas-bridge.xethub.hf.co",
    "us.aws.cdn.hf.co",
    "giletto-systems-lab.michele-giletto.chatgpt.site",
})
SOCKET_TIMEOUT_SECONDS = 15
REQUEST_BUDGET_SECONDS = 90
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_HTML_BYTES = 512 * 1024
MAX_REDIRECTS = 5
WORKERS = 4
CHUNK_BYTES = 64 * 1024
SEMANTIC_SITE_PATHS = frozenset({"/", "/projects/airspace-operations", "/projects/multiagentic-systems"})
CF_PARAMETERS = re.compile(rb"(window\.__CF\$cv\$params\s*=\s*\{\s*r:\s*')([^']{1,128})('\s*,\s*t:\s*')([^']{1,128})('\s*\})")


class PresentationHTML(HTMLParser):
    """Read bounded public markup without evaluating scripts or loading resources."""
    def __init__(self, content: bytes):
        super().__init__(convert_charrefs=True)
        self.links: set[str] = set()
        self.images: set[str] = set()
        self.text: list[str] = []
        self.hidden_element_depth = 0
        self.feed(content.decode("utf-8", errors="strict"))

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"script", "style"}:
            self.hidden_element_depth += 1
        if tag == "a" and values.get("href"):
            self.links.add(values["href"])
        if tag == "img" and values.get("src"):
            self.images.add(values["src"])

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden_element_depth = max(0, self.hidden_element_depth - 1)

    def handle_data(self, data):
        if not self.hidden_element_depth:
            self.text.append(data)


def normalise_hosting_parameters(content: bytes) -> bytes:
    # Only the observed Cloudflare request ID/timestamp are normalised. This is
    # for two-response diagnosis, never a claim to match the original raw hash.
    return CF_PARAMETERS.sub(lambda match: match[1] + b"REQUEST_ID" + match[3] + b"TIMESTAMP" + match[5], content)


def semantic_assertions(target: dict, content: bytes) -> dict:
    page = PresentationHTML(content)
    visible = " ".join(" ".join(page.text).split())
    link = "/projects/airspace-operations"
    has_link = link in page.links or link + ".html" in page.links
    if target["path"] == "/":
        return {"airspace_catalogue_link": has_link}
    if target["path"] == "/projects/multiagentic-systems":
        return {"airspace_programme_link": has_link, "existing_interval_material_preserved": "interval" in visible.casefold()}
    expected = target["semantic_expectations"]
    raw = content.decode("utf-8")
    return {
        "product_title": "System Lab Airspace Operations" in visible,
        "release_version_visible": "0.2.0-rc.1" in visible,
        "exact_candidate_download_link": expected["zip_path"] in page.links,
        "exact_candidate_sha256_visible": expected["zip_sha256"] in visible,
        "actual_mission_control_image": "/airspace-operations/media/mission-control.jpg" in page.images,
        "six_recorded_workspace_references": all(name in raw for name in expected["workspace_images"]),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_url(url: str, *, resolve: bool = True) -> str:
    """Admit only fixed public HTTPS hosts, including every redirect destination."""
    if not isinstance(url, str) or len(url) > 16384 or any(ord(c) < 33 for c in url):
        raise ValueError("Invalid public URL")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.fragment
    ):
        raise ValueError("URL is outside the fixed anonymous HTTPS allowlist")
    if resolve:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Allowlisted hostname did not resolve exclusively to public addresses")
    return url


def safe_url(url: str) -> str:
    """Do not persist temporary CDN signatures or other redirected query values."""
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


class RestrictedRedirects(HTTPRedirectHandler):
    def __init__(self, deadline: float):
        self.deadline = deadline
        self.redirect_hosts: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Public retrieval exceeded its request budget")
        if len(self.redirect_hosts) >= MAX_REDIRECTS:
            raise ValueError("Public retrieval exceeded the redirect limit")
        validate_url(newurl)
        self.redirect_hosts.append(urlsplit(newurl).hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def expected_record(destination: str, row: dict, report: dict) -> dict:
    expected_bytes = row.get("bytes")
    expected_sha = row.get("sha256")
    if expected_bytes is not None and (
        type(expected_bytes) is not int or not 0 <= expected_bytes <= MAX_RESPONSE_BYTES
    ):
        raise ValueError("Manifest byte length is outside the bounded download limit")
    if expected_sha is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ValueError("Manifest SHA-256 is invalid")
    if destination == "github":
        name = row["name"]
        if not isinstance(name, str) or PurePosixPath(name).name != name or "\\" in name:
            raise ValueError("Invalid GitHub asset name")
        url = row["url"]
        expected_url = GITHUB_REPOSITORY + "/releases/download/v0.2.0-rc.1/" + quote(name, safe="")
        if url != expected_url:
            raise ValueError("GitHub asset is outside the exact published release")
    elif destination == "site":
        url = row["url"]
        parsed = urlsplit(url)
        if parsed.scheme + "://" + parsed.netloc != SITE or parsed.query or parsed.fragment:
            raise ValueError("Site resource is outside the published System Lab site")
        name = parsed.path
    else:
        name = row["path"]
        if (
            not isinstance(name, str) or not name or "\\" in name
            or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
        ):
            raise ValueError("Invalid pinned Hugging Face file path")
        revision = report["revision"]
        if report["url"] != HF_REPOSITORY or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("Invalid pinned Hugging Face Space identity")
        url = HF_REPOSITORY + "/resolve/" + revision + "/" + quote(name, safe="/")
    validate_url(url, resolve=False)
    record = {
        "destination": destination, "path": name, "url": url,
        "expected_bytes": expected_bytes, "expected_sha256": expected_sha,
        "verification_mode": "semantic" if destination == "site" and name in SEMANTIC_SITE_PATHS else "exact",
    }
    if destination == "site" and name == "/projects/airspace-operations":
        zip_path = "/airspace-operations/System-Lab-Airspace-Operations-0.2.0-rc.1.zip"
        zip_rows = [item for item in report["checks"] if item.get("path") == zip_path]
        if len(zip_rows) != 1 or not re.fullmatch(r"[0-9a-f]{64}", zip_rows[0].get("sha256", "")):
            raise ValueError("Site report does not identify the exact candidate ZIP digest")
        record["semantic_expectations"] = {
            "zip_path": zip_path, "zip_sha256": zip_rows[0]["sha256"],
            "workspace_images": ["mission-control.jpg", "airspace-planning.jpg", "fleet-maintenance.jpg", "european-coordination.jpg", "scheduling.jpg", "agent-orchestration.jpg"],
        }
    return record


def load_targets(destinations: list[str]) -> tuple[list[dict], list[dict]]:
    targets, manifests = [], []
    for destination in destinations:
        filename, field, expected_count = REPORTS[destination]
        path = EVIDENCE / filename
        content = path.read_bytes()
        report = json.loads(content)
        rows = report[field]
        if report.get("state") != "Independently Retrieved" or len(rows) != expected_count:
            raise ValueError(f"Unexpected final publication report identity/count: {filename}")
        items = [expected_record(destination, row, report) for row in rows]
        if len({item["url"] for item in items}) != len(items):
            raise ValueError(f"Duplicate publication targets in {filename}")
        targets.extend(items)
        manifests.append({
            "destination": destination, "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": hashlib.sha256(content).hexdigest(), "expected_resources": expected_count,
            "publication_checked_at": report.get("checked_at"),
            "revision": report.get("revision"), "source_commit": report.get("source_commit"),
        })
    return targets, manifests


def anonymous_opener(redirects: RestrictedRedirects):
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), redirects)


def anonymous_request(url: str) -> Request:
    return Request(url, method="GET", headers={
        "User-Agent": "System-Lab-Publication-Verifier/0.2", "Accept-Encoding": "identity",
    })


def repeat_html_sample(url: str, deadline: float) -> tuple[bytes, RestrictedRedirects]:
    validate_url(url)
    redirects = RestrictedRedirects(deadline)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Public retrieval exceeded its request budget")
    with anonymous_opener(redirects).open(anonymous_request(url), timeout=min(SOCKET_TIMEOUT_SECONDS, remaining)) as response:
        if response.status != 200:
            raise ValueError("Repeated public HTML sample did not return HTTP 200")
        content = bytearray()
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError("Public retrieval exceeded its request budget")
            chunk = response.read(CHUNK_BYTES)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_HTML_BYTES:
                raise ValueError("HTML exceeds the bounded semantic inspection limit")
    return bytes(content), redirects


def retrieve(target: dict) -> dict:
    started = time.monotonic()
    deadline = started + REQUEST_BUDGET_SECONDS
    redirects = RestrictedRedirects(deadline)
    result = {**target, "verified": False, "authenticated_read": False}
    try:
        validate_url(target["url"])
        # No environment proxy, cookie jar, .netrc reader or auth handler is installed.
        opener = anonymous_opener(redirects)
        request = anonymous_request(target["url"])
        with opener.open(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
            result["status"] = response.status
            result["final_url"] = safe_url(response.url)
            result["content_type"] = response.headers.get("Content-Type")
            if response.status != 200:
                raise ValueError("Public asset did not return HTTP 200")
            announced = response.headers.get("Content-Length")
            if announced is not None and int(announced) > MAX_RESPONSE_BYTES:
                raise ValueError("Public response exceeds the bounded download limit")
            digest, count, captured = hashlib.sha256(), 0, bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Public retrieval exceeded its request budget")
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                count += len(chunk)
                if count > MAX_RESPONSE_BYTES:
                    raise ValueError("Public response exceeds the bounded download limit")
                digest.update(chunk)
                if target["verification_mode"] == "semantic":
                    captured.extend(chunk)
                    if count > MAX_HTML_BYTES:
                        raise ValueError("HTML exceeds the bounded semantic inspection limit")
        result["bytes"] = count
        result["sha256"] = digest.hexdigest()
        result["length_matches"] = count == target["expected_bytes"] if target["expected_bytes"] is not None else None
        result["sha256_matches"] = digest.hexdigest() == target["expected_sha256"] if target["expected_sha256"] is not None else None
        if target["verification_mode"] == "semantic":
            first, second = bytes(captured), None
            second, second_redirects = repeat_html_sample(target["url"], deadline)
            checks = semantic_assertions(target, first)
            repeated_checks = semantic_assertions(target, second)
            first_normalised, second_normalised = normalise_hosting_parameters(first), normalise_hosting_parameters(second)
            result["semantic_assertions"] = checks
            result["repeat_semantic_assertions"] = repeated_checks
            result["hosting_difference"] = {
                "first_sample_sha256": result["sha256"], "second_sample_sha256": hashlib.sha256(second).hexdigest(),
                "second_sample_bytes": len(second), "raw_samples_equal": first == second,
                "first_cloudflare_parameter_blocks": len(CF_PARAMETERS.findall(first)),
                "second_cloudflare_parameter_blocks": len(CF_PARAMETERS.findall(second)),
                "normalised_samples_equal": first_normalised == second_normalised,
                "first_normalised_sha256": hashlib.sha256(first_normalised).hexdigest(),
                "second_normalised_sha256": hashlib.sha256(second_normalised).hexdigest(),
                "normalisation_scope": "Only observed window.__CF$cv$params r/t values; no authored text or links removed",
                "second_redirect_hosts": second_redirects.redirect_hosts,
            }
            result["verified"] = all(checks.values()) and all(repeated_checks.values()) and first_normalised == second_normalised
            result["verification_note"] = "Explicit semantic mode for the three originally semantic HTML checks; raw expected length/digest comparisons remain reported and are not claimed to match"
            if not result["verified"]:
                result["error"] = "HTML semantic assertions failed or repeated content differs beyond recognised hosting parameters"
        else:
            comparisons = [result[key] for key in ("length_matches", "sha256_matches") if result[key] is not None]
            result["verified"] = bool(comparisons) and all(comparisons)
            if not comparisons:
                result["error"] = "No expected length or digest: availability is insufficient to verify identity"
            elif not result["verified"]:
                result["error"] = "Public content differs from the final recorded publication"
    except HTTPError as exc:
        result["status"] = exc.code
        result["error"] = f"HTTPError: {exc.code}"
    except URLError as exc:
        result["error"] = "URLError: " + type(exc.reason).__name__
    except (OSError, ValueError, TimeoutError) as exc:
        # Avoid logging redirected signed URLs or raw response/error bodies.
        result["error"] = type(exc).__name__ + ": " + str(exc).split("https://", 1)[0][:240]
    finally:
        result["redirect_hosts"] = redirects.redirect_hosts
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def output_path(value: str) -> Path:
    supplied = Path(value).expanduser()
    output = (supplied if supplied.is_absolute() else ROOT / supplied).resolve()
    runtime = (ROOT / "runtime").resolve()
    if output.exists() and (not output.is_file() or not output.is_relative_to(runtime)):
        raise ValueError("Refusing to overwrite existing files outside the mutable runtime directory")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", choices=("all", "github", "site", "hf"), default="all")
    parser.add_argument("--output", default="runtime/publication-recheck-v2.json", help="New result file; existing historical files cannot be overwritten")
    args = parser.parse_args()
    try:
        output = output_path(args.output)
    except ValueError as exc:
        parser.error(str(exc))
    destinations = list(REPORTS) if args.destination == "all" else [args.destination]
    started, timestamp = time.monotonic(), utc_now()
    report = {
        "schema_version": "1.0", "release": "0.2.0-rc.1", "started_at": timestamp,
        "requested_destination": args.destination, "authenticated_read": False,
        "remote_mutations_performed": False, "historical_evidence_modified": False,
        "verification_scope": "All binary/static assets are checked exactly. Only the three explicitly designated Site HTML pages use bounded semantic assertions and two-sample hosting-parameter diagnosis; their raw hash comparisons remain visible.",
        "limits": {"socket_timeout_seconds": SOCKET_TIMEOUT_SECONDS, "per_resource_budget_seconds": REQUEST_BUDGET_SECONDS,
                   "budget_note": "Monotonic checks between redirects and reads; a blocking socket operation is additionally bounded by its socket timeout. DNS uses the operating system resolver.",
                   "max_response_bytes": MAX_RESPONSE_BYTES, "max_semantic_html_bytes": MAX_HTML_BYTES,
                   "max_redirects": MAX_REDIRECTS, "workers": WORKERS,
                   "allowed_hosts": sorted(ALLOWED_HOSTS), "environment_proxies_used": False},
        "source_reports": [], "resources": [], "summary": {}, "success": False,
    }
    try:
        targets, report["source_reports"] = load_targets(destinations)
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            report["resources"] = list(pool.map(retrieve, targets))
        for destination in destinations:
            rows = [item for item in report["resources"] if item["destination"] == destination]
            report["summary"][destination] = {
                "expected": REPORTS[destination][2], "attempted": len(rows),
                "http_200": sum(item.get("status") == 200 for item in rows),
                "verified": sum(item["verified"] for item in rows),
                "failed": sum(not item["verified"] for item in rows),
                "exact_verified": sum(item["verified"] and item["verification_mode"] == "exact" for item in rows),
                "semantic_verified": sum(item["verified"] and item["verification_mode"] == "semantic" for item in rows),
                "raw_sha256_mismatches": sum(item.get("sha256_matches") is False for item in rows),
            }
        report["success"] = all(item["verified"] for item in report["resources"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc)[:300]
    report["finished_at"] = utc_now()
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, prefix=".publication-recheck-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2)
            stream.write("\n")
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"success": report["success"], "summary": report["summary"],
                      "elapsed_seconds": report["elapsed_seconds"], "output": str(output), "error": report.get("error")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
