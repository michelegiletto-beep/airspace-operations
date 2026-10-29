"""Check prepared copy and local artifacts without publishing or claiming browser QA."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from package_release import SECRET_PATTERNS


class Document(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.ids, self.links, self.visible = [], [], []
        self.hidden = 0
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "style", "head"}: self.hidden += 1
        if "id" in attributes: self.ids.append(attributes["id"])
        if tag in {"a", "link"} and attributes.get("href"): self.links.append(attributes["href"])

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"}: self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden: self.visible.append(data)


def main():
    status = json.loads((HERE / "status.json").read_text(encoding="utf-8"))
    assert status["release"] == "0.3.0-rc.1" and status["states_reached"] == ["Prepared"]
    assert status["publication_performed"] is False and status["public_download"] is None and status["archive_sha256"] is None
    pages = []
    for relative in ("site-project.html", "hf-space/index.html"):
        path = HERE / relative
        document = Document(path.read_text(encoding="utf-8"))
        assert len(document.ids) == len(set(document.ids)), "Duplicate element ID"
        for link in document.links:
            if link.startswith("#"): assert link[1:] in document.ids
            elif not link.startswith(("https://", "/", "data:,")): assert (path.parent / link).is_file()
            assert "/releases/tag/v0.3" not in link and "Operations-0.3" not in link, "Unverified new download must not be enabled"
        visible = " ".join(document.visible)
        assert "Prepared" in visible
        assert not re.search(r"\b0[1-9]\s*[/·—]", visible), "Decorative section numbering"
        pages.append({"path": relative, "ids": len(document.ids), "links": len(document.links), "result": "Parsed; local references checked"})
    authored = [HERE / name for name in ("github-readme.md", "hf-model-card.md", "hf-dataset-card.md", "site-project.html", "hf-space/index.html")]
    for path in authored:
        content = path.read_bytes()
        assert not any(pattern.search(content) for pattern in SECRET_PATTERNS), "Potential credential pattern in prepared copy"
        text = content.decode("utf-8")
        assert "Prepared" in text
        for phrase in ("One operational context. Bounded specialist work.", "Choose the work. Keep the evidence.", "Review remains accountable."):
            assert phrase not in text, "Observed slogan retained in new publication copy"
    student = ROOT / "models/runs/explicit-shall-20261027-4/student.safetensors"
    assert hashlib.sha256(student.read_bytes()).hexdigest() == "ff96770308c96b9d96c5f8f6535576e9d791834f76291bf08fce99dcf34d6e6c"
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "release": "0.3.0-rc.1", "state": "Prepared",
        "pages": pages, "authored_documents_checked": len(authored), "student_original_digest_matches": True,
        "credential_patterns_found": [], "new_download_links_enabled": False,
        "browser_verified": False, "application_verification_reported": {"backend_passed": 360, "postgresql_skipped_locally": 19, "frontend_passed": 107}, "model_execution_reported": "Actual local replies and confirmed personal task; no new student training", "source_ci_status": "In Progress", "publication_performed": False,
        "capture_references": [{"path": str(Path("publication/media/v0.3") / name), "available_locally": (ROOT / "publication/media/v0.3" / name).is_file()} for name in ("desktop-companion.jpg", "mobile-companion.jpg")],
        "limit": "Local copy/structure checks supplement actual application/browser, legal, rights and publication review; they do not prove universal stylistic compliance"}
    (HERE / "preparation-checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
