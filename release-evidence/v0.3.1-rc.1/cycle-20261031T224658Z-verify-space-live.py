"""Anonymous exact static-Space deployment verification. Never uploads."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import importlib.util
import json
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".json")
if OUT.exists():
    raise SystemExit("Refusing to overwrite an earlier live receipt")
HEAD = "7aae1c50c4a7556d3f067bcf8992cf8219fa51cf"
HOST = "https://magic51-system-lab-airspace-evaluation.static.hf.space"
manifest_path = ROOT / "publication/releases/0.3.1-rc.1/huggingface/manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
targets = [row for row in manifest["files"] if row["repo_type"] == "space"]
assert len(targets) == 6
spec = importlib.util.spec_from_file_location("anonymous_space_boundary", ROOT / "scripts/verify_publication_v2.py")
net = importlib.util.module_from_spec(spec)
spec.loader.exec_module(net)
sha = lambda data: hashlib.sha256(data).hexdigest()

def fetch(url, bound=4 * 1024 * 1024):
    net.validate_url(url)
    redirect = net.RestrictedRedirects(time.monotonic() + 90)
    with net.anonymous_opener(redirect).open(net.anonymous_request(url), timeout=15) as response:
        assert response.status == 200
        data = response.read(bound + 1)
        assert len(data) <= bound
        return data, {"status": response.status, "content_type": response.headers.get("Content-Type"), "final_url": net.safe_url(response.url), "redirect_hosts": redirect.redirect_hosts}

report = {"started_at": datetime.now(timezone.utc).isoformat(), "head": HEAD, "host": HOST, "scope": "Anonymous exact live-host HTML and assets versus the reviewed manifest; not browser interaction, inference, operator data or operational acceptance.", "cookies_credentials_environment_proxies": False, "remote_mutations": False, "files": []}
try:
    metadata_url = "https://huggingface.co/api/spaces/Magic51/system-lab-airspace-evaluation"
    metadata, _ = fetch(metadata_url)
    info = json.loads(metadata)
    assert info["sha"] == HEAD and info["sdk"] == "static"
    assert info["runtime"]["stage"] == "RUNNING" and info["host"] == HOST
    net.ALLOWED_HOSTS = net.ALLOWED_HOSTS | {urlsplit(HOST).hostname}
    report["metadata"] = {"url": metadata_url, "sha256": sha(metadata), "sha": info["sha"], "sdk": info["sdk"], "runtime_stage": info["runtime"]["stage"], "host": info["host"]}

    def check(row):
        data, request = fetch(HOST + "/" + row["target"])
        assert len(data) == row["bytes"] and sha(data) == row["sha256"], row["target"] + " differs from exact source"
        return {"path": row["target"], "bytes": len(data), "sha256": sha(data), "exact_reviewed_manifest_match": True, **request}
    with ThreadPoolExecutor(max_workers=4) as pool:
        report["files"] = list(pool.map(check, targets))
    root, request = fetch(HOST + "/")
    index = next(row for row in targets if row["target"] == "index.html")
    assert len(root) == index["bytes"] and sha(root) == index["sha256"]
    report["root_index"] = {"path": "/", "bytes": len(root), "sha256": sha(root), "exact_reviewed_index_match": True, **request}

    class Structure(HTMLParser):
        def __init__(self):
            super().__init__()
            self.images, self.styles, self.scripts, self.forms = [], [], [], []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "img": self.images.append(attrs.get("src"))
            if tag == "link" and attrs.get("rel") == "stylesheet": self.styles.append(attrs.get("href"))
            if tag == "script": self.scripts.append(attrs.get("src"))
            if tag == "form": self.forms.append(attrs.get("action"))
    html = Structure()
    html.feed(root.decode("utf-8"))
    assert set(html.images) == {"media/application-tasks.png", "media/companion-tasks-mobile.jpg"}
    assert html.styles == ["styles.css"] and not html.scripts and not html.forms
    report["actual_loaded_resource_references"] = {"images": html.images, "stylesheets": html.styles, "scripts": html.scripts, "forms": html.forms}
    report["success"] = True
    report["state"] = "Independently Retrieved"
except Exception as error:
    report["success"] = False
    report["error"] = {"type": type(error).__name__, "message": str(error)[:250]}
report["completed_at"] = datetime.now(timezone.utc).isoformat()
with OUT.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")
print(json.dumps({"receipt": str(OUT), "success": report["success"], "exact_live_files": len(report["files"]), "error": report.get("error")}))
raise SystemExit(0 if report["success"] else 1)
