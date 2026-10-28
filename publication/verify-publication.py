"""Verify local publication records, links and image bytes without external actions."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import xml.etree.ElementTree as ET

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPACE = HERE / "hf-space"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.ids: list[str] = []
        self.references: list[str] = []
        self.idrefs: list[str] = []
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if data.get("id"):
            self.ids.append(data["id"])
        for attr in ("src", "href"):
            if data.get(attr):
                self.references.append(data[attr])
        for attr in ("aria-labelledby", "aria-controls", "for"):
            if data.get(attr):
                self.idrefs.extend(data[attr].split())


def verify_page(path: Path, static: bool) -> dict:
    page = Page(path.read_text(encoding="utf-8"))
    assert len(page.ids) == len(set(page.ids)), f"Duplicate HTML ID: {path}"
    assert all(ref in page.ids for ref in page.idrefs), f"Unresolved ID reference: {path}"
    resolved = []
    for ref in page.references:
        parsed = urlsplit(ref)
        if parsed.scheme or parsed.netloc:
            continue
        if ref.startswith("#"):
            assert ref[1:] in page.ids, f"Missing anchor: {ref}"
            continue
        value = unquote(parsed.path)
        if not value:
            continue
        if static:
            target = (SPACE / value).resolve()
            assert target.is_relative_to(SPACE.resolve()), ref
        elif value.startswith("/airspace-operations/media/"):
            target = HERE / "media" / value.rsplit("/", 1)[1]
        elif value == "/assets/airspace-project.css":
            target = HERE / "site-project.css"
        elif value == "/assets/lab.css":
            target = ROOT.parents[1] / "public/assets/lab.css"
        else:
            # Existing-site navigation/release routes are verified by the release owner.
            continue
        assert target.is_file(), f"Missing local resource: {ref} => {target}"
        resolved.append(ref)
    return {"unique_ids": len(page.ids), "id_references": len(page.idrefs), "resolved_local_resources": resolved}


def main() -> None:
    evidence = json.loads((SPACE / "data/evidence.json").read_text(encoding="utf-8"))
    provenance = json.loads((SPACE / "data/provenance.json").read_text(encoding="utf-8"))
    assert evidence["release_state"] == "Prepared"
    assert evidence["live_inference"] is evidence["live_flights"] is evidence["operational_acceptance"] is False
    assert len(evidence["comparison"]["trials"]) == 4
    assert evidence["comparison"]["query_count"] == 2
    assert all(t["state"] == "Needs Review" and t["review_gate_preserved"] and not t["legal_conclusion_generated"] for t in evidence["comparison"]["trials"])
    assert len(evidence["ui_workflow"]["trace"]) == 5
    assert len(evidence["ui_workflow"]["citations"]) == 12
    assert evidence["ui_workflow"]["review_gate"]["approval_granted"] is False
    assert evidence["student"]["new_training"] is evidence["student"]["new_weights"] is False
    assert evidence["student"]["dataset"]["human_reviewed_rows"] == 0
    assert len(evidence["student"]["failure_cases"]) == 14
    assert evidence["owned_presentation"]["file_count"] == 5
    assert provenance["data_index_sha256"] == sha(SPACE / "data/evidence.json")
    for name, report in provenance["source_reports"].items():
        assert sha(SPACE / "data" / name) == report["sha256"] == sha(ROOT / report["project_path"])
    media = {}
    for name, record in provenance["media"].items():
        path = SPACE / "media" / name
        assert sha(path) == record["sha256"] == sha(HERE / "media" / name)
        if name.endswith(".svg"):
            ET.parse(path)
            media[name] = {"state": "Present; SVG XML parsed", **record}
        else:
            with Image.open(path) as image:
                image.load()
                media[name] = {"state": "Present; decoded", "pixels": image.size, **record}
    student = ROOT / "models/runs/explicit-shall-20261027-4/student.safetensors"
    assert sha(student) == "ff96770308c96b9d96c5f8f6535576e9d791834f76291bf08fce99dcf34d6e6c"
    assert not list(SPACE.rglob("*.safetensors")) and not list(SPACE.rglob("*.mjs"))
    readme = (SPACE / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("---\n") and "sdk: static\n" in readme and "app_file: index.html\n" in readme
    secret_findings = []
    for path in SPACE.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".html", ".js", ".md", ".py", ".css"}:
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?:hf_[A-Za-z0-9]{24,}|sk-proj-[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)", text):
                secret_findings.append(str(path.relative_to(HERE)))
    assert not secret_findings, secret_findings
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(), "release_state": "Prepared",
        "native_publication_performed": False, "browser_rendering_verified": False,
        "checks": {"site": verify_page(HERE / "site-project.html", False), "static_space": verify_page(SPACE / "index.html", True),
                   "raw_report_copies": len(provenance["source_reports"]), "media_copies": len(media),
                   "unchanged_student_sha256": sha(student), "official_static_metadata": True,
                   "new_weights_or_renderer_bundled": False, "credential_patterns_found": secret_findings},
        "media": media, "pending_root_assets": [],
        "notes": ["Local checks do not prove browser rendering, clean installation or public publication.",
                  "Rerun prepare.py and both publication checks after the release owner refreshes screenshots."]}
    (HERE / "authoring-qa-v2.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "raw_reports": 4, "media": len(media), "trials": 4, "ui_steps": 5, "citations": 12, "failure_cases": 14, "published": False}))


if __name__ == "__main__":
    main()
