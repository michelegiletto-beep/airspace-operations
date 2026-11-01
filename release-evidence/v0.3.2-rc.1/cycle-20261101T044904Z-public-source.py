"""Independently retrieve the exact pushed 0.3.2 source. No upload or authentication."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import base64
import hashlib
import importlib.util
import json
import re
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".json")
if OUT.exists():
    raise SystemExit("Refusing to overwrite a prior source receipt")
SOURCE = "2ebb8b20e515d9863a69b072bd963890e219e050"
PARENT = "a604443d12563e5468943309d3047d98345457fc"
REPO = "michelegiletto-beep/airspace-operations"
API = "https://api.github.com/repos/" + REPO
payload_path = ROOT / "runtime/publication/github-032-source-20261101T044904Z.json"
payload = json.loads(payload_path.read_text(encoding="utf-8"))
assert set(payload) == {"files", "deletions"} and len(payload["files"]) == 64 and len(payload["deletions"]) == 2
spec = importlib.util.spec_from_file_location("anonymous_source_boundary", ROOT / "scripts/verify_publication_v2.py")
net = importlib.util.module_from_spec(spec)
spec.loader.exec_module(net)
net.ALLOWED_HOSTS = net.ALLOWED_HOSTS | {"api.github.com", "raw.githubusercontent.com"}
sys.path.insert(0, str(ROOT / "scripts"))
from package_release import SECRET_PATTERNS
from publication_media import _jpeg
sha = lambda value: hashlib.sha256(value).hexdigest()

def fetch(url, bound=4 * 1024 * 1024):
    net.validate_url(url)
    redirect = net.RestrictedRedirects(time.monotonic() + 90)
    with net.anonymous_opener(redirect).open(net.anonymous_request(url), timeout=15) as response:
        assert response.status == 200
        data = response.read(bound + 1)
        assert len(data) <= bound
        return data, {"status": response.status, "final_url": net.safe_url(response.url), "redirect_hosts": redirect.redirect_hosts}

report = {"started_at": datetime.now(timezone.utc).isoformat(), "source_commit": SOURCE, "parent_commit": PARENT, "branch": "release/0.3.2-rc.1", "anonymous_requests": True, "cookies_credentials_environment_proxies": False, "remote_mutations": False, "scope": "Actual public source/tree identities, version locks, selected JPEG container and supported secret-pattern checks. No CI, release asset, installation or operational acceptance is inferred.", "expected_public_payload_sha256": sha(payload_path.read_bytes())}
try:
    commit = json.loads(fetch(API + "/git/commits/" + SOURCE)[0])
    assert commit["sha"] == SOURCE and [row["sha"] for row in commit["parents"]] == [PARENT]
    branch = json.loads(fetch(API + "/git/ref/heads/release/0.3.2-rc.1")[0])
    assert branch["object"]["sha"] == SOURCE
    trees = {}
    for revision in [PARENT, SOURCE]:
        tree = json.loads(fetch(API + "/git/trees/" + revision + "?recursive=1")[0])
        assert tree["truncated"] is False
        trees[revision] = {row["path"]: row for row in tree["tree"] if row["type"] == "blob"}
    previous, current = trees[PARENT], trees[SOURCE]
    expected_paths = {row["path"] for row in payload["files"]}
    deletions = {row["path"] for row in payload["deletions"]}
    assert len(expected_paths) == 64 and len(deletions) == 2
    assert {path for path in current if path not in previous or current[path]["sha"] != previous[path]["sha"]} == expected_paths
    assert set(previous) - set(current) == deletions
    assert all(path in previous and path not in current for path in deletions)
    denied_components = {"runtime", "work", ".git", ".venv", "node_modules", "private", "secrets", "keys"}
    private_paths = [path for path in current if any(part in denied_components for part in PurePosixPath(path).parts) or PurePosixPath(path).suffix.lower() in {".db", ".sqlite", ".sqlite3", ".key", ".pem", ".p12", ".pfx"}]
    assert not private_paths
    actual_contents = {}

    def retrieve(row):
        path = row["path"]
        assert not PurePosixPath(path).is_absolute() and ".." not in PurePosixPath(path).parts and "\\" not in path
        assert row["encoding"] == "base64"
        expected = base64.b64decode(row["content"], validate=True)
        assert len(expected) == row["bytes"] and sha(expected) == row["sha256"]
        url = "https://raw.githubusercontent.com/" + REPO + "/" + SOURCE + "/" + quote(path, safe="/")
        data, request = fetch(url)
        assert data == expected
        blob = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        assert blob == row["git_blob"] == current[path]["sha"] and current[path]["mode"] == "100644"
        assert not any(pattern.search(data) for pattern in SECRET_PATTERNS)
        actual_contents[path] = data
        return {"path": path, "bytes": len(data), "sha256": sha(data), "git_blob": blob, "exact_expected_public_source": True, **request}
    with ThreadPoolExecutor(max_workers=4) as pool:
        report["files"] = list(pool.map(retrieve, payload["files"]))
    package = json.loads(actual_contents["frontend/package.json"])
    package_lock = json.loads(actual_contents["frontend/package-lock.json"])
    project = tomllib.loads(actual_contents["pyproject.toml"].decode("utf-8"))
    uv = tomllib.loads(actual_contents["uv.lock"].decode("utf-8"))
    assert package["version"] == package_lock["version"] == package_lock["packages"][""]["version"] == "0.3.2-rc.1"
    assert project["project"]["version"] == "0.3.2rc1"
    assert re.search(rb'__version__\s*=\s*[\'"]0\.3\.2-rc\.1[\'"]', actual_contents["backend/airspace/__init__.py"])
    assert any(row["name"] == project["project"]["name"] and row["version"] == "0.3.2rc1" for row in uv["package"])
    assert any(row["name"] == "pypdf" and row["version"] == "6.21.4" for row in uv["package"])
    manifest = json.loads(actual_contents["publication/releases/0.3.2-rc.1/manifest.json"])
    assert manifest["version"] == "0.3.2-rc.1"
    assert manifest["screenshot_path"] == "publication/media/0.3.2-rc.1/operations-permissions-mobile.jpg"
    screenshot = actual_contents[manifest["screenshot_path"]]
    assert len(screenshot) == 35517 and screenshot.startswith(b"\xff\xd8\xff") and screenshot.endswith(b"\xff\xd9")
    _jpeg(screenshot)
    baseline, _ = fetch("https://raw.githubusercontent.com/" + REPO + "/" + SOURCE + "/SPECIFICATION.md")
    assert sha(baseline) == "43755041cbfa555158b51979de4c726bf52f7e82dc113e840c1488d974ba9b30"
    report.update({"state": "Independently Retrieved", "source_tree": commit["tree"]["sha"], "exact_changed_files": 64, "deleted_old_frontend_bundles_absent": sorted(deletions), "only_expected_file_changes": True, "supported_secret_pattern_matches": 0, "private_tree_paths": [], "version_locks_consistent": True, "pypdf_lock_version": "6.21.4", "original_baseline_sha256": sha(baseline), "selected_capture": {"path": manifest["screenshot_path"], "bytes": len(screenshot), "sha256": sha(screenshot), "encoding": "JPEG", "container_validated": True, "visual_review_not_repeated": True}, "success": True})
    try:
        runs = json.loads(fetch(API + "/actions/runs?head_sha=" + SOURCE + "&per_page=5")[0])
        report["ci_snapshot"] = [{key: row.get(key) for key in ["id", "head_sha", "head_branch", "status", "conclusion", "html_url", "created_at", "updated_at"]} for row in runs["workflow_runs"]]
    except Exception as error:
        report["ci_metadata_limit"] = {"type": type(error).__name__, "success_inferred": False}
except Exception as error:
    report["success"] = False
    report["error"] = {"type": type(error).__name__, "message": str(error)[:250]}
report["completed_at"] = datetime.now(timezone.utc).isoformat()
with OUT.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")
print(json.dumps({"receipt": str(OUT), "success": report["success"], "exact_files": report.get("exact_changed_files"), "ci": report.get("ci_snapshot"), "error": report.get("error")}))
raise SystemExit(0 if report["success"] else 1)
