"""Independently retrieve the public documentation page and frozen release asset."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://giletto-systems-lab.michele-giletto.chatgpt.site"
NAME = "System-Lab-Airspace-Operations-0.1.0-rc.1.zip"
EXPECTED = "a114fa757fe60c9ded044092fac986ce3558cc5ddc5f0c3bd924e9de2caa9d87"


def retrieve(path):
    response = httpx.get(BASE + path, timeout=90, follow_redirects=True)
    response.raise_for_status()
    return response


def main():
    paths = ["/", "/projects/airspace-operations.html", "/airspace-operations/" + NAME]
    with ThreadPoolExecutor(max_workers=3) as pool:
        home, page, archive = list(pool.map(retrieve, paths))
    digest = hashlib.sha256(archive.content).hexdigest()
    assert digest == EXPECTED, "Published archive differs from frozen candidate"
    assert "projects/airspace-operations.html" in home.text, "Home page link missing"
    assert "System Lab Airspace Operations" in page.text, "Project page missing"
    assert "github.com/michelegiletto-beep/airspace-operations" in page.text
    assert "huggingface.co/Magic51/system-lab-airspace-shall-router" in page.text
    assert "huggingface.co/datasets/Magic51/system-lab-airspace-source-annotations" in page.text
    result = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "state": "Independently Retrieved",
        "authenticated_read": False,
        "site_url": BASE,
        "page_url": str(page.url),
        "page_status": page.status_code,
        "home_link_verified": True,
        "release_links_verified": True,
        "download_url": str(archive.url),
        "bytes": len(archive.content),
        "sha256": digest,
        "matches_frozen_release": True,
        "site_source_commit": "bb9ffcd968917e28ab085bcf098abeb417fa8147",
        "version_number": 94,
        "version_id": "appgprj_6a8fdd39ede88191898e6f386864c331~appgver_9c84a6f5f2088191a6ae7ac5f3bea44f",
        "deployment_id": "appgdep_6ae0f566f8608191a87ff00bb5b9f5eb",
        "deployment_status": "succeeded",
        "operational_instance_published": False,
    }
    output = ROOT / "release-evidence/system-lab-public-verification.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
