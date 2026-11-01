"""Anonymously verify the additive 0.3.2 Site only after actual publication.

Expected bytes come from independently retrieved release/media receipts, never
from planned values. The frozen 0.3/0.3.1 helpers and hosting comparator are not
edited. This verifier does not upload, authenticate or overwrite prior evidence.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.3.2-rc.1"
SOURCE = "2ebb8b20e515d9863a69b072bd963890e219e050"
STAMP = "cycle-20261101T044904Z"
EVIDENCE = ROOT / "release-evidence" / ("v" + VERSION)
PHONE_NAME = "operations-permissions-mobile.jpg"
PHONE_PATH = f"/airspace-operations/media/{VERSION}/{PHONE_NAME}"
ASSET_NAMES = frozenset({
    f"System-Lab-Airspace-Operations-{VERSION}.zip", "ci-verification.json",
    "LICENSE", "release-gates.json", "RELEASE_PROVENANCE.json", "SBOM.cdx.json",
    "SHA256SUMS.txt", "standalone-archive-verification.json", "THIRD_PARTY_NOTICES.md",
})
SPEC = importlib.util.spec_from_file_location("site031_history_boundary", ROOT / "scripts/verify_site_031.py")
history = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(history)
v = history.v


def receipt(name: str) -> dict:
    value = json.loads((EVIDENCE / (STAMP + "-" + name + ".json")).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("state") != "Independently Retrieved" or value.get("source_commit") != SOURCE:
        raise ValueError("Actual independently retrieved 0.3.2 receipt and frozen source are required")
    return value


def exact_local_target(source: Path, path: str, row: dict) -> dict:
    size, checksum = row.get("bytes"), row.get("sha256")
    if (type(size) is not int or not 0 < size <= v.legacy.MAX_RESPONSE_BYTES
            or not isinstance(checksum, str) or not re.fullmatch("[0-9a-f]{64}", checksum)):
        raise ValueError("An actual bounded byte count and SHA-256 identity are required")
    local = v.source_path(source, path)
    if local.stat().st_size != size:
        raise ValueError("Site bytes differ from the independently retrieved 0.3.2 receipt")
    with local.open("rb") as stream:
        data = stream.read(size + 1)
    if len(data) != size or v.digest(data) != checksum:
        raise ValueError("Site bytes differ from the independently retrieved 0.3.2 receipt")
    return v.exact_target(path, size, checksum)


def verified_current_targets(source: Path):
    downloads = receipt("public-downloads")
    media = receipt("public-media")
    rows = downloads.get("assets")
    if downloads.get("version") != VERSION or not isinstance(rows, list) or len(rows) != 9:
        raise ValueError("Exactly nine actual 0.3.2 release assets are required")
    if any(not isinstance(row, dict) or not isinstance(row.get("name"), str) for row in rows):
        raise ValueError("Invalid release asset rows")
    if {row["name"] for row in rows} != ASSET_NAMES:
        raise ValueError("Nine distinct expected 0.3.2 release asset names are required")
    targets = []
    for row in rows:
        if row.get("status") != 200 or row.get("github_digest_matches") is not True:
            raise ValueError("Actual HTTP 200 release assets with matching published digests are required")
        path = f"/airspace-operations/releases/{VERSION}/" + row["name"]
        targets.append(exact_local_target(source, path, row))
    captures = media.get("media")
    if not isinstance(captures, list) or len(captures) != 1:
        raise ValueError("Exactly one independently retrieved 0.3.2 phone capture is required")
    phone = captures[0]
    if (not isinstance(phone, dict) or phone.get("path") != f"publication/media/{VERSION}/{PHONE_NAME}"
            or phone.get("encoding") != "JPEG" or phone.get("status") != 200
            or phone.get("container_validated") is not True
            or phone.get("matches_public_source_and_exact_archive") is not True):
        raise ValueError("The actual correctly named 0.3.2 JPEG phone capture is required")
    targets.append(exact_local_target(source, PHONE_PATH, phone))
    archive = next(row["sha256"] for row in rows if row["name"].endswith(".zip"))
    return targets, archive


def semantic_checks(target: dict, content: bytes, current_sha: str, prior_sha: str) -> dict:
    checks = history.semantic_checks(target, content, prior_sha)
    if target["path"] == "/projects/airspace-operations":
        # Retain every 0.3.1 assertion while adding a separately identified current
        # candidate. No authored-content or hosting exception is relaxed.
        for key in ("published_candidate_visible", "candidate_download_link", "verified_archive_digest",
                    "two_current_displayed_images", "all_three_current_capture_links"):
            checks["history031_" + key] = checks.pop(key)
        page = v.legacy.PresentationHTML(content)
        authored = v.visible(page)
        checks.update({
            "published032_section": b'id="release-0-3-2" data-state="Published"' in content,
            "current032_tag_visible": VERSION in authored,
            "current032_archive_digest_visible": current_sha in authored,
            "current032_download_link": f"/airspace-operations/releases/{VERSION}/System-Lab-Airspace-Operations-{VERSION}.zip" in page.links,
            "current032_phone_displayed": PHONE_PATH in page.images,
            "current032_phone_link": PHONE_PATH in page.links,
            "history031_release_link": "https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.1-rc.1" in page.links,
            "history030_download_link": "/airspace-operations/releases/0.3.0-rc.1/System-Lab-Airspace-Operations-0.3.0-rc.1.zip" in page.links,
            "history030_archive_digest_visible": "4a004e21dd04633e82c330f191745ad9b31bd65d8424183d0b66cfd00243763e" in authored,
        })
    return checks


def fresh_output(value: str) -> Path:
    path = Path(value).expanduser()
    path = path if path.is_absolute() else ROOT / path
    if path.exists() or path.is_symlink():
        raise ValueError("Existing evidence cannot be overwritten; choose a new output path")
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT) or resolved.suffix != ".json" or resolved.exists():
        raise ValueError("A new JSON output path inside this project is required")
    return resolved


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-source", default="work/site-publishing")
    parser.add_argument("--version-number", required=True, type=int)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if (args.version_number <= 98 or not re.fullmatch("[0-9a-f]{40}", args.source_commit)
            or not re.fullmatch("appgdep_[A-Za-z0-9_]+", args.deployment_id)):
        parser.error("The actual successful new Site deployment identity is required")
    try:
        output = fresh_output(args.output)
        source = (ROOT / args.site_source).resolve()
        head = v.assert_deployment_source(source, args.source_commit)
        targets = v.build_targets(source)
        if len(targets) != 37:
            raise ValueError("Exactly 37 original publication resources are required")
        prior, prior_sha = history.verified_new_targets(source)
        targets += prior
        if len(targets) != 49 or len({row["url"] for row in targets}) != 49:
            raise ValueError("Exactly 49 preserved 0.3.1 and older resources are required")
        current, current_sha = verified_current_targets(source)
        targets += current
        if len(targets) != 59 or len({row["url"] for row in targets}) != 59:
            raise ValueError("Exactly 59 distinct current and historical resources are required")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    started = time.monotonic()
    original = v.semantic_checks
    v.semantic_checks = lambda target, content: semantic_checks(target, content, current_sha, prior_sha)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            checks = list(pool.map(v.retrieve, targets))
    finally:
        v.semantic_checks = original
    summary = {"expected": 59, "http_200": sum(row.get("status") == 200 for row in checks),
               "verified": sum(row["verified"] for row in checks),
               "exact": sum(row["verified"] and row["verification_mode"] == "exact" for row in checks),
               "authored_html": sum(row["verified"] and row["verification_mode"] == "semantic" for row in checks)}
    success = summary["verified"] == 59
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "version": VERSION,
              "release_source_commit": SOURCE, "site_source_commit": head,
              "version_number": args.version_number, "deployment_id": args.deployment_id,
              "summary": summary, "checks": checks, "success": success,
              "state": "Independently Retrieved" if success else "Verification failed",
              "authenticated_read": False, "environment_proxies_used": False,
              "remote_mutations_performed": False, "elapsed_seconds": round(time.monotonic() - started, 3),
              "scope": "All 49 previously verified resources plus nine actual 0.3.2 release assets and one actual JPEG capture. All 56 binary assets require exact bytes; all three authored pages retain the unchanged hardened source/text/link/image/script/style comparator and exact pinned hosting exception. Current 0.3.2 and separate 0.3.1/0.3 history assertions are enforced."}
    write_report(output, report)
    print(json.dumps({"state": report["state"], "summary": summary, "output": str(output.relative_to(ROOT))}), flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
