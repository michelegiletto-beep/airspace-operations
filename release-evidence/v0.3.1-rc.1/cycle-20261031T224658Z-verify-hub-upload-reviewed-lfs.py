"""Verify a reviewed Hub presentation commit anonymously. Never uploads."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import argparse
import hashlib
import importlib.util
import json
import re
import time

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--type", choices=["model", "dataset", "space"], required=True)
parser.add_argument("--head", required=True)
parser.add_argument("--parent", required=True)
args = parser.parse_args()
assert re.fullmatch(r"[0-9a-f]{40}", args.head)
assert re.fullmatch(r"[0-9a-f]{40}", args.parent)
OUT = Path(__file__).with_name("cycle-20261031T224658Z-hub-" + args.type + "-" + args.head[:8] + "-reviewed-lfs.json")
if OUT.exists():
    raise SystemExit("Refusing to overwrite an earlier receipt")
manifest_path = ROOT / "publication/releases/0.3.1-rc.1/huggingface/manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
targets = [row for row in manifest["files"] if row["repo_type"] == args.type]
assert targets and len({row["repo_id"] for row in targets}) == 1
repo = targets[0]["repo_id"]
api_kind = {"model": "models", "dataset": "datasets", "space": "spaces"}[args.type]
repo_prefix = {"model": "", "dataset": "datasets/", "space": "spaces/"}[args.type]
repo_url = "https://huggingface.co/" + repo_prefix + repo
api_url = "https://huggingface.co/api/" + api_kind + "/" + repo
spec = importlib.util.spec_from_file_location("anonymous_hub_boundary", ROOT / "scripts/verify_publication_v2.py")
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
        return data, {"status": response.status, "final_url": net.safe_url(response.url), "redirect_hosts": redirect.redirect_hosts}

report = {"started_at": datetime.now(timezone.utc).isoformat(), "repo_type": args.type, "repository": repo, "url": repo_url, "head": args.head, "expected_parent": args.parent, "authenticated_read": False, "cookies_credentials_environment_proxies": False, "remote_mutations": False, "scope": "Exact changed presentation files, current public head, displayed direct parent, and all unlisted prior repository file identities/bytes. No new training, inference or operational acceptance."}
try:
    metadata = json.loads(fetch(api_url + "/revision/" + args.head + "?blobs=true")[0])
    previous = json.loads(fetch(api_url + "/revision/" + args.parent + "?blobs=true")[0])
    current = json.loads(fetch(api_url)[0])
    assert metadata["sha"] == current["sha"] == args.head
    assert previous["sha"] == args.parent
    if args.type == "space":
        assert metadata["sdk"] == "static"
    commit_page, commit_request = fetch(repo_url + "/commit/" + args.head)
    html = commit_page.decode("utf-8")
    parent_block = re.search(r"<span[^>]*>\s*1\s+Parent\(s\):</span>(.*?)</div>", html, re.S)
    assert parent_block
    parent_links = re.findall(r'href="([^"]+)"', parent_block[1])
    assert parent_links == ["/" + repo_prefix + repo + "/commit/" + args.parent]
    report["direct_parent"] = {"verified": True, "parent": args.parent, "source_url": repo_url + "/commit/" + args.head, "parent_links": parent_links, "commit_page_sha256": sha(commit_page), **commit_request}
    old = {row["rfilename"]: row for row in previous["siblings"]}
    new = {row["rfilename"]: row for row in metadata["siblings"]}
    target_paths = {row["target"] for row in targets}
    assert set(new) == set(old) | target_paths
    actual_changes = {path for path in set(old) | set(new) if old.get(path) != new.get(path)}
    provider_paths = {".gitattributes"} if ".gitattributes" in actual_changes else set()
    assert actual_changes <= target_paths | provider_paths
    if provider_paths:
        old_attributes, _ = fetch(repo_url + "/resolve/" + args.parent + "/.gitattributes")
        new_attributes, attributes_request = fetch(repo_url + "/resolve/" + args.head + "/.gitattributes")
        assert new_attributes.startswith(old_attributes) and old_attributes.endswith(b"\n")
        added = new_attributes[len(old_attributes):].splitlines(keepends=True)
        expected = {path.encode("utf-8") + b" filter=lfs diff=lfs merge=lfs -text\n" for path in target_paths if "lfs" in new[path] and (path not in old or "lfs" not in old[path])}
        assert added and len(added) == len(set(added)) and set(added) == expected
        report["provider_generated_metadata_exception"] = {"path": ".gitattributes", "old_bytes": len(old_attributes), "new_bytes": len(new_attributes), "old_sha256": sha(old_attributes), "new_sha256": sha(new_attributes), "old_bytes_retained_as_exact_prefix": True, "exact_added_lines": [line.decode("utf-8").rstrip("\n") for line in added], "only_exact_LFS_rules_for_reviewed_new_files": True, **attributes_request}
    assert all(old[path] == new[path] for path in set(old) - target_paths - provider_paths)
    report["only_reviewed_targets_and_exact_provider_LFS_entries_changed"] = True
    report["actual_changed_paths"] = sorted(actual_changes)
    report["manifest_sha256"] = sha(manifest_path.read_bytes())

    def check_target(row):
        url = repo_url + "/resolve/" + args.head + "/" + quote(row["target"], safe="/")
        data, request = fetch(url)
        assert len(data) == row["bytes"] and sha(data) == row["sha256"]
        assert data == (ROOT / row["source"]).read_bytes()
        return {"target": row["target"], "source": row["source"], "url": url, "bytes": len(data), "sha256": sha(data), "matches_reviewed_manifest_and_local_source": True, **request}
    with ThreadPoolExecutor(max_workers=4) as pool:
        report["changed_files"] = list(pool.map(check_target, targets))

    def check_preserved(path):
        old_url = repo_url + "/resolve/" + args.parent + "/" + quote(path, safe="/")
        new_url = repo_url + "/resolve/" + args.head + "/" + quote(path, safe="/")
        old_data, _ = fetch(old_url)
        data, request = fetch(new_url)
        assert data == old_data
        assert len(data) == new[path]["size"]
        if "lfs" in new[path]:
            assert sha(data) == new[path]["lfs"]["sha256"]
        else:
            blob = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
            assert blob == new[path]["blobId"]
        return {"path": path, "bytes": len(data), "sha256": sha(data), "blob_identity_and_actual_bytes_unchanged": True, "source_url": new_url, **request}
    with ThreadPoolExecutor(max_workers=4) as pool:
        report["unlisted_prior_files"] = list(pool.map(check_preserved, sorted(set(old) - target_paths - provider_paths)))
    report["state"] = "Independently Retrieved"
    report["success"] = True
except Exception as error:
    report["success"] = False
    report["error"] = {"type": type(error).__name__, "message": str(error)[:250]}
report["completed_at"] = datetime.now(timezone.utc).isoformat()
with OUT.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")
print(json.dumps({"receipt": str(OUT), "success": report["success"], "reviewed_files": len(report.get("changed_files", [])), "preserved_unlisted_files": len(report.get("unlisted_prior_files", [])), "error": report.get("error")}))
raise SystemExit(0 if report["success"] else 1)
