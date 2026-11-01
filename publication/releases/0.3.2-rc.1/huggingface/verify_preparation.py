"""Read-only validation of the prepared presentation pack; no remote actions."""
from __future__ import annotations

from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys

PACK = Path(__file__).resolve().parent
ROOT = PACK.parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from publication_media import validate_raster_encoding
from package_release import SECRET_PATTERNS


def require(condition, message):
    if not condition:
        raise ValueError(message)


class References(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.local = set()
        self.scripts = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.scripts += tag == "script"
        for name, value in attrs:
            if name in {"src", "href"} and value and not value.startswith(("https://", "#")):
                self.local.add(value)


def validate():
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["application_version"] == "0.3.2-rc.1", "Wrong candidate version")
    require(manifest["application_source"] == "2ebb8b20e515d9863a69b072bd963890e219e050", "Wrong frozen candidate source")
    require(manifest["ready_for_upload"] is True, "Current release evidence must be finalized before upload")
    require(manifest["archive_bytes"] == 13796258 and manifest["archive_sha256"] == "1634b9b7e36bd2b80b179a4e0429da7f0c9165434747fc9a62f03ede78cc772e", "Current release identity differs")
    proofs = {name: json.loads((ROOT / relative).read_text(encoding="utf-8")) for name, relative in manifest["release_evidence"].items()}
    downloads, integrity, media = proofs["public-downloads"], proofs["archive-integrity"], proofs["public-media"]
    require(downloads["state"] == "Independently Retrieved" and downloads["source_commit"] == manifest["application_source"] and len(downloads["assets"]) == 9, "Nine actual release downloads are required")
    require(all(row["status"] == 200 and row["github_digest_matches"] is True for row in downloads["assets"]), "Public release download verification failed")
    archive = next(row for row in downloads["assets"] if row["name"] == "System-Lab-Airspace-Operations-0.3.2-rc.1.zip")
    require(archive["bytes"] == manifest["archive_bytes"] and archive["sha256"] == manifest["archive_sha256"], "Published archive differs")
    require(all(integrity[key] is True for key in ("all_manifest_digests_match", "ci_source_hashes_match_archive", "zip_crc_valid", "clean_install_receipt_binds_exact_archive")), "Archive integrity gate failed")
    require(media["state"] == "Independently Retrieved" and media["source_commit"] == manifest["application_source"] and len(media["media"]) == 1 and media["media"][0]["encoding"] == "JPEG" and media["media"][0]["status"] == 200, "Actual public JPEG proof is required")
    require(not manifest["weights_changed"] and not manifest["dataset_records_changed"] and not manifest["live_inference"], "Presentation-only boundary changed")
    expected = {("model", "README.md"), ("model", "media/operations-permissions-mobile.jpg"),
                ("dataset", "README.md"), ("space", "README.md"), ("space", "index.html"),
                ("space", "media/operations-permissions-mobile.jpg")}
    require({(row["repo_type"], row["target"]) for row in manifest["files"]} == expected and len(manifest["files"]) == 6,
            "Prepared upload list differs from the six reviewed targets")
    repos = {"model": "Magic51/system-lab-airspace-shall-router",
             "dataset": "Magic51/system-lab-airspace-source-annotations",
             "space": "Magic51/system-lab-airspace-evaluation"}
    for row in manifest["files"]:
        require(row["repo_id"] == repos[row["repo_type"]], "Prepared destination repository differs")
        source = (ROOT / row["source"]).resolve()
        require(source.is_relative_to(PACK) and source.is_file(), "Unsafe or absent prepared source")
        data = source.read_bytes()
        require(len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"], "Prepared target digest changed")
    old = ROOT / "publication/releases/0.3.1-rc.1/huggingface"
    for relative in ("model/NOTICE.md", "space/NOTICE.md", "model/media/companion-tasks.png",
                     "space/media/application-tasks.png", "space/media/companion-tasks-mobile.jpg", "space/styles.css"):
        require((PACK / relative).read_bytes() == (old / relative).read_bytes(), "Existing rights notice or historical media/style changed")
    phone = ROOT / manifest["new_capture"]["source"]
    for kind in ("model", "space"):
        actual = PACK / kind / "media/operations-permissions-mobile.jpg"
        require(actual.read_bytes() == phone.read_bytes(), "New screenshot differs from actual frozen candidate capture")
        require(validate_raster_encoding(actual) == "JPEG", "New mobile capture encoding differs")
    for path in PACK.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        require(not any(pattern.search(data) for pattern in SECRET_PATTERNS), "Supported secret pattern found")
        require(path.suffix.lower() not in {".db", ".sqlite", ".key", ".safetensors", ".bin"}, "Unapproved artifact in presentation pack")
        if path.suffix.lower() in {".md", ".html", ".css"}:
            text = data.decode("utf-8")
            require(not re.search(r"\b(?:TODO|TBD)\b|\{\{[^}]+\}\}", text), "Preparation contains a placeholder")
    html = References((PACK / "space/index.html").read_text(encoding="utf-8"))
    require(html.scripts == 0, "Static presentation unexpectedly includes script execution")
    for relative in html.local:
        target = (PACK / "space" / relative).resolve()
        require(target.is_relative_to(PACK / "space") and target.is_file(), "Static viewer local reference is absent or unsafe")
    for kind in ("model", "dataset", "space"):
        text = (PACK / kind / "README.md").read_text(encoding="utf-8")
        for relative in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if relative.startswith(("https://", "#")):
                continue
            local = (PACK / kind / relative).resolve()
            require(local.is_relative_to(PACK / kind) and local.is_file(), "Card local reference is absent or unsafe")
        require("0.3.2" in text and "published" in text and "unchanged" in text, "Card candidate or artifact boundary missing")
        require("GHSA-5849-834g-hvw5" in text and "GHSA-mfr5-77xh-9j7h" in text and "GHSA-cggf-277g-3q54" in text,
                "Official security references missing")
    return {"state": "Ready for scoped upload; no Hub upload performed", "targets": 6,
            "target_bytes": sum(row["bytes"] for row in manifest["files"]), "rights_notices_exact": 2,
            "new_capture_copies_exact": 2, "new_capture_encoding": "JPEG", "local_html_references": len(html.local),
            "supported_secret_patterns_found": 0, "remote_actions": False, "new_model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
