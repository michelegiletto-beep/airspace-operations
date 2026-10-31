"""Verify the additive0.3.1 Site publication anonymously without overwriting evidence.

The existing hardened comparator remains unchanged. Site98 displays two current
screenshots and links all three captures, including a separate task-detail image.
Historical image links are checked when present in source.
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

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.1-rc.1"
SOURCE = "433e89a66038ee7f7c34cb443c03eeafdee92f36"
STAMP = "cycle-20261030T195233Z"
EVIDENCE = ROOT / f"release-evidence/v{VERSION}"
SPEC = importlib.util.spec_from_file_location("hardened_site03", ROOT / "scripts/verify_publication_v3.py")
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)
ORIGINAL_SEMANTIC_CHECKS = v.semantic_checks
CURRENT_CAPTURE_PATHS = frozenset(f"/airspace-operations/media/{VERSION}/" + name for name in (
    "companion-tasks.png", "companion-tasks-mobile.jpg", "application-tasks.png"))
DISPLAYED_CURRENT_IMAGES = frozenset(f"/airspace-operations/media/{VERSION}/" + name for name in (
    "companion-tasks-mobile.jpg", "application-tasks.png"))
HISTORICAL_IMAGES = frozenset("/airspace-operations/media/v0.3/" + name for name in (
    "desktop-companion.jpg", "mobile-companion.jpg"))


def verified_new_targets(source: Path):
    downloads = json.loads((EVIDENCE / (STAMP + "-public-downloads.json")).read_text(encoding="utf-8"))
    media = json.loads((EVIDENCE / (STAMP + "-public-media.json")).read_text(encoding="utf-8"))
    if (downloads.get("state") != "Independently Retrieved" or downloads.get("source_commit") != SOURCE
            or len(downloads.get("assets", [])) != 9 or media.get("state") != "Independently Retrieved"
            or media.get("source_commit") != SOURCE or len(media.get("media", [])) != 3):
        raise ValueError("Frozen independently retrieved0.3.1 asset and media receipts are required")
    result = []
    for row in downloads["assets"]:
        if Path(row["name"]).name != row["name"] or "\\" in row["name"]:
            raise ValueError("Invalid frozen candidate asset name")
        path = f"/airspace-operations/releases/{VERSION}/" + row["name"]
        data = v.source_path(source, path).read_bytes()
        if len(data) != row["bytes"] or v.digest(data) != row["sha256"]:
            raise ValueError("Site candidate asset differs from frozen public receipt")
        result.append(v.exact_target(path, row["bytes"], row["sha256"]))
    media_paths = set()
    for row in media["media"]:
        name = Path(row["path"]).name
        if name == "companion-tasks-mobile.png":
            name = "companion-tasks-mobile.jpg"
        path = f"/airspace-operations/media/{VERSION}/" + name
        if path not in CURRENT_CAPTURE_PATHS:
            raise ValueError("Frozen media receipt must identify the three current captures")
        media_paths.add(path)
        data = v.source_path(source, path).read_bytes()
        if len(data) != row["bytes"] or v.digest(data) != row["sha256"]:
            raise ValueError("Site capture differs from frozen public media receipt")
        result.append(v.exact_target(path, row["bytes"], row["sha256"]))
    if media_paths != CURRENT_CAPTURE_PATHS:
        raise ValueError("Frozen media receipt must identify three distinct current captures")
    archives = [a["sha256"] for a in downloads["assets"] if a["name"] == f"System-Lab-Airspace-Operations-{VERSION}.zip"]
    if len(archives) != 1:
        raise ValueError("Exactly one frozen candidate archive identity is required")
    return result, archives[0]


def semantic_checks(target: dict, content: bytes, archive_sha: str) -> dict:
    checks = ORIGINAL_SEMANTIC_CHECKS(target, content)
    if target["path"] == "/projects/airspace-operations":
        page = v.legacy.PresentationHTML(content)
        reference = v.legacy.PresentationHTML(target["_source"])
        authored = v.visible(page)
        # This is the sole retired version-specific assertion. Exact source,
        # visible text, links, images, markup, styles and scripts stay compared.
        checks.pop("two_actual_captures")
        checks["published_candidate_visible"] = VERSION in authored and b'id="release-0-3-1" data-state="Published"' in content
        checks["candidate_download_link"] = f"/airspace-operations/releases/{VERSION}/System-Lab-Airspace-Operations-{VERSION}.zip" in page.links
        checks["verified_archive_digest"] = archive_sha in authored
        checks["two_current_displayed_images"] = DISPLAYED_CURRENT_IMAGES <= page.images
        checks["all_three_current_capture_links"] = CURRENT_CAPTURE_PATHS <= page.links
        historical_links = HISTORICAL_IMAGES & reference.links
        if historical_links:
            checks["source_historical03_image_links_preserved"] = historical_links <= page.links
        checks["historical03_release_link"] = "https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.0-rc.1" in page.links
    return checks


def fresh_output_path(value: str) -> Path:
    supplied = Path(value).expanduser()
    original = supplied if supplied.is_absolute() else ROOT / supplied
    if original.exists() or original.is_symlink():
        raise ValueError("A new output path is required; existing evidence is never overwritten")
    output = original.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise ValueError("A new output path inside this project is required")
    return output


def write_report(output: Path, report: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also rejects a file created after the initial check.
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-source", default="work/site-publishing")
    parser.add_argument("--version-number", type=int, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--output", required=True, help="New project-local result file; never overwrites any existing file")
    args = parser.parse_args(argv)
    if (args.version_number <= 97 or not re.fullmatch("[0-9a-f]{40}", args.source_commit)
            or not re.fullmatch("appgdep_[A-Za-z0-9_]+", args.deployment_id)):
        parser.error("The actual successful new deployment identity is required")
    try:
        output = fresh_output_path(args.output)
        source = (ROOT / args.site_source).resolve()
        head = v.assert_deployment_source(source, args.source_commit)
        targets = v.build_targets(source)
        if len(targets) != 37:
            raise ValueError("Exactly37 prior publication resources are required")
        new, archive_sha = verified_new_targets(source)
        targets += new
        if len(targets) != 49 or len({t["url"] for t in targets}) != 49:
            raise ValueError("Exactly49 distinct publication resources are required")
    except ValueError as exc:
        parser.error(str(exc))
    started = time.monotonic()
    previous_checks = v.semantic_checks
    v.semantic_checks = lambda target, content: semantic_checks(target, content, archive_sha)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(v.retrieve, targets))
    finally:
        v.semantic_checks = previous_checks
    summary = {"expected": 49, "http_200": sum(r.get("status") == 200 for r in results),
               "verified": sum(r["verified"] for r in results),
               "exact": sum(r["verified"] and r["verification_mode"] == "exact" for r in results),
               "authored_html": sum(r["verified"] and r["verification_mode"] == "semantic" for r in results)}
    success = summary["verified"] == 49
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "version": VERSION,
              "version_number": args.version_number, "source_commit": head, "deployment_id": args.deployment_id,
              "summary": summary, "checks": results, "state": "Independently Retrieved" if success else "Verification failed",
              "success": success, "authenticated_read": False, "environment_proxies_used": False,
              "remote_mutations_performed": False, "elapsed_seconds": round(time.monotonic() - started, 3),
              "scope": "Original37 resources plus9 candidate assets and3 actual raster captures. All46 binary assets require exact identity;3 authored HTML pages retain the unchanged hardened source/text/link/image/script/style/hosting comparator. Site98 displays2 current captures as images and links all3 captures, including a task-detail capture offered as a link. Historical image links are preserved when present in source."}
    write_report(output, report)
    print(json.dumps({"state": report["state"], "summary": summary, "output": str(output.relative_to(ROOT))}), flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
