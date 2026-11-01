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
HEAD = "e690dc6b5f8ef26f700188300475b668dae2500e"
HOST = "https://magic51-system-lab-airspace-evaluation.static.hf.space"
manifest_path = ROOT / "publication/releases/0.3.2-rc.1/huggingface/manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
targets = [row for row in manifest["files"] if row["repo_type"] == "space" and row["target"] != "README.md"]
prior = json.loads((ROOT / "publication/releases/0.3.1-rc.1/huggingface/manifest.json").read_text(encoding="utf-8"))
targets += [row for row in prior["files"] if row["repo_type"] == "space" and row["target"] in {"NOTICE.md", "styles.css", "media/application-tasks.png"}]
assert len(targets) == 5 and len({row["target"] for row in targets}) == 5
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

# These are the five exact hosting nodes observed on this published Space.
# No authored text, scripts, styles, links or other nodes are discarded.
HF_SCRIPT = b'<script>window.huggingface={variables:{"SPACE_CREATOR_USER_ID":"646c7a3534ba36a75db6c398"}};</script>'
HF_META = b'<meta property="og:title" content="System Lab Airspace Evaluation"><meta property="og:image" content="https://cdn-thumbnails.huggingface.co/social-thumbnails/spaces/Magic51/system-lab-airspace-evaluation.png"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="https://cdn-thumbnails.huggingface.co/social-thumbnails/spaces/Magic51/system-lab-airspace-evaluation.png">'
def authored_html(data):
    assert data.count(HF_SCRIPT) == 1 and data.count(HF_META) == 1
    assert data.count(b"<head>" + HF_SCRIPT) == 1
    assert data.count(HF_META + b"</head>") == 1
    return data.replace(b"<head>" + HF_SCRIPT, b"<head>", 1).replace(HF_META + b"</head>", b"</head>", 1)

report = {"started_at": datetime.now(timezone.utc).isoformat(), "head": HEAD, "host": HOST, "scope": "Anonymous exact live-host assets and all authored HTML bytes after exactly verified hosting additions versus the reviewed manifest; not browser interaction, inference, operator data or operational acceptance.", "cookies_credentials_environment_proxies": False, "remote_mutations": False, "files": []}
try:
    metadata_url = "https://huggingface.co/api/spaces/Magic51/system-lab-airspace-evaluation"
    metadata, _ = fetch(metadata_url)
    info = json.loads(metadata)
    assert info["sha"] == HEAD and info["sdk"] == "static"
    assert info["runtime"]["stage"] == "RUNNING" and info["host"] == HOST
    net.ALLOWED_HOSTS = net.ALLOWED_HOSTS | {urlsplit(HOST).hostname}
    report["metadata"] = {"url": metadata_url, "sha256": sha(metadata), "sha": info["sha"], "sdk": info["sdk"], "runtime_stage": info["runtime"]["stage"], "host": info["host"]}
    rendered_readme, readme_request = fetch(HOST + "/README.md")
    assert readme_request["content_type"].startswith("text/html")
    report["provider_rendered_metadata_route"] = {"path": "README.md", "bytes": len(rendered_readme), "sha256": sha(rendered_readme), "exact_raw_markdown_match_claimed": False, "scope": "The host renders the metadata README as HTML. Its immutable repository Markdown was separately retrieved exactly; it is not a referenced application resource and is excluded from raw live-file comparison.", **readme_request}

    def check(row):
        data, request = fetch(HOST + "/" + row["target"])
        authored = authored_html(data) if row["target"] == "index.html" else data
        assert len(authored) == row["bytes"] and sha(authored) == row["sha256"], row["target"] + " authored bytes differ from exact source"
        return {"path": row["target"], "bytes": len(data), "sha256": sha(data), "exact_raw_manifest_match": data == authored, "authored_bytes": len(authored), "authored_sha256": sha(authored), "exact_authored_manifest_match": True, **request}
    with ThreadPoolExecutor(max_workers=4) as pool:
        report["files"] = list(pool.map(check, targets))
    root, request = fetch(HOST + "/")
    index = next(row for row in targets if row["target"] == "index.html")
    authored_root = authored_html(root)
    assert len(authored_root) == index["bytes"] and sha(authored_root) == index["sha256"]
    report["root_index"] = {"path": "/", "bytes": len(root), "sha256": sha(root), "exact_raw_manifest_match": False, "authored_bytes": len(authored_root), "authored_sha256": sha(authored_root), "exact_authored_manifest_match": True, **request}
    report["verified_hosting_additions"] = {"inline_script_nodes": 1, "inline_script_sha256": sha(HF_SCRIPT), "exact_meta_nodes": 4, "meta_bytes_sha256": sha(HF_META), "added_bytes": len(HF_SCRIPT) + len(HF_META), "positions": ["immediately after head start", "immediately before head end"], "all_remaining_authored_bytes_exact": True}
    mutations = [root.replace(b"</head>", b"<script>alert(1)</script></head>", 1), root.replace(b"styles.css", b"evil.css", 1), root.replace(b"0.3.2-rc.1", b"9.9.9-rc.1", 1), root.replace(HF_SCRIPT, HF_SCRIPT + HF_SCRIPT, 1)]
    rejected = 0
    for altered in mutations:
        try:
            result = authored_html(altered)
            assert result == authored_root
        except AssertionError:
            rejected += 1
    assert rejected == 4
    report["negative_comparisons"] = {"count": rejected, "rejects": ["additional script", "changed stylesheet", "changed authored copy", "duplicate hosting script"]}

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
    html.feed(authored_root.decode("utf-8"))
    assert set(html.images) == {"media/application-tasks.png", "media/operations-permissions-mobile.jpg"}
    assert html.styles == ["styles.css"] and not html.scripts and not html.forms
    report["authored_resource_references"] = {"images": html.images, "stylesheets": html.styles, "scripts": html.scripts, "forms": html.forms}
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
