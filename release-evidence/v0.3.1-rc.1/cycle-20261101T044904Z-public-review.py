"""Read-only anonymous publication recheck, 31 October 2026 22:46 cycle. Never uploads or replaces artifacts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import gzip
import hashlib
import importlib.util
import io
import json
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".json")
if OUT.exists():
    raise SystemExit("Refusing to overwrite an earlier dated receipt")
spec = importlib.util.spec_from_file_location("publication_network_boundary", ROOT / "scripts/verify_publication_v2.py")
net = importlib.util.module_from_spec(spec)
spec.loader.exec_module(net)
net.ALLOWED_HOSTS = net.ALLOWED_HOSTS | {"api.github.com", "raw.githubusercontent.com"}
sha = lambda data: hashlib.sha256(data).hexdigest()
report = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "scope": "Fresh anonymous HTTP retrieval and exact byte comparison; no new installation, model run, domain review or operational acceptance.",
    "anonymous_requests": True,
    "cookies_credentials_environment_proxies": False,
    "remote_mutations": False,
    "frozen_files_modified": False,
    "errors": [],
}

def fetch(url, bound=16 * 1024 * 1024):
    net.validate_url(url)
    redirect = net.RestrictedRedirects(time.monotonic() + 90)
    with net.anonymous_opener(redirect).open(net.anonymous_request(url), timeout=15) as response:
        if response.status != 200:
            raise ValueError("Expected public HTTP 200")
        data = response.read(bound + 1)
        if len(data) > bound:
            raise ValueError("Response exceeds fixed bound")
        return data, {"status": response.status, "final_url": net.safe_url(response.url), "redirect_hosts": redirect.redirect_hosts}

def run_section(name, operation):
    try:
        report[name] = operation()
    except Exception as error:
        report["errors"].append({"section": name, "type": type(error).__name__, "message": str(error)[:300]})

def github():
    repo = "michelegiletto-beep/airspace-operations"
    source = "433e89a66038ee7f7c34cb443c03eeafdee92f36"
    base = f"https://api.github.com/repos/{repo}"
    release = json.loads(fetch(base + "/releases/tags/v0.3.1-rc.1")[0])
    tag = json.loads(fetch(base + "/git/ref/tags/v0.3.1-rc.1")[0])
    assert release["id"] == 429437042 and release["draft"] is False and release["prerelease"] is True
    assert release["target_commitish"] == tag["object"]["sha"] == source
    prior = json.loads((ROOT / "release-evidence/v0.3.1-rc.1/cycle-20261030T195233Z-public-downloads.json").read_text(encoding="utf-8"))
    expected = {row["name"]: row for row in prior["assets"]}
    assert len(expected) == 9 and {row["name"] for row in release["assets"]} == set(expected)
    downloaded = {}
    def check_asset(row):
        old = expected[row["name"]]
        assert PurePosixPath(row["name"]).name == row["name"]
        assert row["browser_download_url"] == old["url"]
        data, request = fetch(old["url"])
        digest = sha(data)
        assert row["id"] == old["id"]
        assert len(data) == row["size"] == old["bytes"]
        assert digest == old["sha256"] and row["digest"] == "sha256:" + digest
        downloaded[row["name"]] = data
        return {"name": row["name"], "id": row["id"], "url": old["url"], "bytes": len(data), "sha256": digest, "matches_prior_receipt_and_current_github_digest": True, **request}
    with ThreadPoolExecutor(max_workers=4) as pool:
        assets = list(pool.map(check_asset, release["assets"]))
    archive = downloaded["System-Lab-Airspace-Operations-0.3.1-rc.1.zip"]
    provenance = json.loads(downloaded["RELEASE_PROVENANCE.json"])
    ci = json.loads(downloaded["ci-verification.json"])
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        assert zipped.testzip() is None
        names = zipped.namelist()
        assert len(names) == len(set(names)) == 638
        assert all(name.startswith("airspace-operations/") and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names)
        members = {name.removeprefix("airspace-operations/"): zipped.read(name) for name in names}
        assert set(members) == set(provenance["files"]) | {"RELEASE_PROVENANCE.json"}
        assert len(provenance["files"]) == 637
        assert all(sha(members[name]) == digest for name, digest in provenance["files"].items())
        assert len(ci["local_software_input_hashes"]) == 200
        assert all(sha(members[name]) == digest for name, digest in ci["local_software_input_hashes"].items())
        assert provenance["source_commit"] == ci["commit"] == source
        assert sha(members["SPECIFICATION.md"]) == "43755041cbfa555158b51979de4c726bf52f7e82dc113e840c1488d974ba9b30"
        mobile = members["publication/media/0.3.1-rc.1/companion-tasks-mobile.png"]
        assert mobile.startswith(b"\xff\xd8\xff")
        assert sha(mobile) == "e2fa3b2d733158e93cfe9e7f0e78497fd8c033f0143b5e96dfe9a50daa691b4c"
    return {"release_url": release["html_url"], "source_commit": source, "tag_unchanged": True, "prerelease": True, "assets": assets, "archive_members": 638, "exact_manifest_hashes": 637, "exact_ci_source_hashes": 200, "known_mobile_filename_encoding_mismatch_preserved": True}

def current_main():
    url = "https://api.github.com/repos/michelegiletto-beep/airspace-operations/git/ref/heads/main"
    data, request = fetch(url)
    ref = json.loads(data)
    assert ref["object"]["sha"].startswith("a604")
    return {"url": url, "commit": ref["object"]["sha"], "matches_expected_checkpoint_prefix": True, **request}

def huggingface():
    heads = {"model": "a6a24fc396ce7e86eb9f9c096231f0378e355ef7", "dataset": "88c470dd521d63a90a6361e762e73167823317a1", "space": "7aae1c50c4a7556d3f067bcf8992cf8219fa51cf"}
    reports = []
    for kind, head in heads.items():
        prior_path = ROOT / "release-evidence/v0.3.1-rc.1" / ("cycle-20261031T224658Z-hub-" + kind + "-" + head[:8] + "-reviewed-lfs.json")
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        api_kind = {"model": "models", "dataset": "datasets", "space": "spaces"}[kind]
        metadata_url = "https://huggingface.co/api/" + api_kind + "/" + prior["repository"]
        metadata = json.loads(fetch(metadata_url)[0])
        assert metadata["sha"] == head
        if kind == "space":
            assert metadata["sdk"] == "static" and metadata["runtime"]["stage"] == "RUNNING"
        resources = [{"path": row["target"], "url": row["url"], "bytes": row["bytes"], "sha256": row["sha256"]} for row in prior["changed_files"]]
        resources += [{"path": row["path"], "url": row["source_url"], "bytes": row["bytes"], "sha256": row["sha256"]} for row in prior["unlisted_prior_files"]]
        generated = prior.get("provider_generated_metadata_exception")
        if generated:
            resources.append({"path": ".gitattributes", "url": prior["url"] + "/resolve/" + head + "/.gitattributes", "bytes": generated["new_bytes"], "sha256": generated["new_sha256"]})
        def check(row):
            data, request = fetch(row["url"])
            assert len(data) == row["bytes"] and sha(data) == row["sha256"]
            return {**row, "exact_prior_publication_match": True, **request}
        with ThreadPoolExecutor(max_workers=4) as pool:
            checked = list(pool.map(check, resources))
        reports.append({"repo_type": kind, "repository": prior["repository"], "current_head": head, "metadata_url": metadata_url, "resources": checked, "prior_publication_receipt": str(prior_path.relative_to(ROOT))})
    return {"repositories": reports, "total_exact_files": sum(len(row["resources"]) for row in reports), "weights_data_and_code_unchanged": True, "new_model_calls": 0, "new_uploads": False}

run_section("current_main", current_main)
run_section("github", github)
run_section("huggingface", huggingface)
report["completed_at"] = datetime.now(timezone.utc).isoformat()
report["success"] = not report["errors"]
with OUT.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")
print(json.dumps({"receipt": str(OUT), "success": report["success"], "sections": list(report), "errors": report["errors"]}))
raise SystemExit(0 if report["success"] else 1)
