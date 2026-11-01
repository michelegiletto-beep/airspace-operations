"""Verify the actual public 0.3.2 release without uploading or replacing assets."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import hashlib
import importlib.util
import io
import json
import re
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.3.2-rc.1"
SOURCE = "2ebb8b20e515d9863a69b072bd963890e219e050"
REPO = "michelegiletto-beep/airspace-operations"
EVIDENCE = ROOT / "release-evidence/v0.3.2-rc.1"
STAMP = "cycle-20261101T105140Z"
FOLDER = ROOT / "release/0.3.2-rc.1"
spec = importlib.util.spec_from_file_location("anonymous_release_boundary", ROOT / "scripts/verify_publication_v2.py")
net = importlib.util.module_from_spec(spec)
spec.loader.exec_module(net)
net.ALLOWED_HOSTS = net.ALLOWED_HOSTS | {"api.github.com", "raw.githubusercontent.com"}
sys.path.insert(0, str(ROOT / "scripts"))
from package_release import SECRET_PATTERNS
from publication_media import _jpeg
sha = lambda data: hashlib.sha256(data).hexdigest()

def fetch(url, bound=32 * 1024 * 1024):
    net.validate_url(url)
    redirect = net.RestrictedRedirects(time.monotonic() + 90)
    with net.anonymous_opener(redirect).open(net.anonymous_request(url), timeout=15) as response:
        assert response.status == 200
        data = response.read(bound + 1)
        assert len(data) <= bound
        return data, {"status": response.status, "final_url": net.safe_url(response.url), "redirect_hosts": redirect.redirect_hosts, "authenticated_read": False}

def save(name, value):
    path = EVIDENCE / (STAMP + "-" + name + ".json")
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")

release = json.loads(fetch("https://api.github.com/repos/" + REPO + "/releases/tags/v" + VERSION)[0])
assert release["draft"] is False and release["prerelease"] is True and release["target_commitish"] == SOURCE
ref = json.loads(fetch("https://api.github.com/repos/" + REPO + "/git/ref/tags/v" + VERSION)[0])
assert ref["object"]["sha"] == SOURCE
expected = {"System-Lab-Airspace-Operations-" + VERSION + ".zip", "RELEASE_PROVENANCE.json", "SHA256SUMS.txt", "SBOM.cdx.json", "THIRD_PARTY_NOTICES.md", "LICENSE", "release-gates.json", "standalone-archive-verification.json", "ci-verification.json"}
assert len(release["assets"]) == 9 and {row["name"] for row in release["assets"]} == expected
downloaded = {}

def retrieve(row):
    name = row["name"]
    assert PurePosixPath(name).name == name and "\\" not in name
    url = "https://github.com/" + REPO + "/releases/download/v" + VERSION + "/" + name
    assert row["browser_download_url"] == url
    data, request = fetch(url)
    digest = sha(data)
    assert len(data) == row["size"] and row["digest"] == "sha256:" + digest
    downloaded[name] = data
    return {"name": name, "id": row["id"], "url": url, "bytes": len(data), "sha256": digest, "github_digest_matches": True, **request}

with ThreadPoolExecutor(max_workers=4) as pool:
    assets = list(pool.map(retrieve, release["assets"]))
FOLDER.mkdir(parents=True, exist_ok=True)
for name, data in downloaded.items():
    path = FOLDER / name
    if path.exists():
        assert path.read_bytes() == data, "Never replace existing released bytes"
    else:
        with path.open("xb") as stream:
            stream.write(data)
save("public-downloads", {"checked_at": datetime.now(timezone.utc).isoformat(), "version": VERSION, "release_id": release["id"], "published_at": release["published_at"], "source_commit": SOURCE, "state": "Independently Retrieved", "anonymous_requests": True, "cookies_credentials_environment_proxies": False, "assets": assets})
archive_name = "System-Lab-Airspace-Operations-" + VERSION + ".zip"
archive = downloaded[archive_name]
archive_sha = sha(archive)
assert downloaded["SHA256SUMS.txt"].decode("utf-8").strip() == archive_sha + "  " + archive_name
provenance = json.loads(downloaded["RELEASE_PROVENANCE.json"])
gate = json.loads(downloaded["release-gates.json"])
ci = json.loads(downloaded["ci-verification.json"])
clean = json.loads(downloaded["standalone-archive-verification.json"])
assert provenance["version"] == gate["version"] == clean["version"] == VERSION
assert provenance["source_commit"] == ci["commit"] == SOURCE
assert provenance["gates"] == gate and gate["engineering_checks_passed"] and all(gate["checks"].values())
assert gate["stable_release_allowed"] is False and gate["operational_acceptance"] is False
assert gate["external_ci"]["verified"] is True and ci["conclusion"] == "success"
assert ci["run_id"] == gate["external_ci"]["run_id"] == 41275818880
assert clean["success"] and clean["installation_exit"] == clean["test_suite"]["exit_code"] == 0 and clean["archive_sha256"] == archive_sha
with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
    assert zipped.testzip() is None
    names = zipped.namelist()
    assert len(names) == len(set(names))
    assert sum(row.file_size for row in zipped.infolist()) <= 250000000
    assert all((row.external_attr >> 16) & 0o170000 != 0o120000 for row in zipped.infolist())
    assert all(name.startswith("airspace-operations/") and not name.endswith("/") and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names)
    members = {name.removeprefix("airspace-operations/"): zipped.read(name) for name in names}
assert set(members) == set(provenance["files"]) | {"RELEASE_PROVENANCE.json"}
assert all(sha(members[path]) == digest for path, digest in provenance["files"].items())
assert all(sha(members[path]) == digest for path, digest in ci["local_software_input_hashes"].items())
assert members["RELEASE_PROVENANCE.json"] == downloaded["RELEASE_PROVENANCE.json"]
baseline = sha(members["SPECIFICATION.md"])
assert baseline == provenance["baseline_sha256"] == "43755041cbfa555158b51979de4c726bf52f7e82dc113e840c1488d974ba9b30"
for path, data in members.items():
    assert not any(part in {"runtime", "work", ".git", ".venv", "node_modules", "private", "secrets", "keys"} for part in PurePosixPath(path).parts)
    assert PurePosixPath(path).suffix.lower() not in {".db", ".sqlite", ".sqlite3", ".key", ".pem", ".p12", ".pfx"}
    assert not any(pattern.search(data) for pattern in SECRET_PATTERNS)
for name in ["LICENSE", "SBOM.cdx.json", "THIRD_PARTY_NOTICES.md"]:
    assert members[name] == downloaded[name]
rights_prefix = "frontend/public/vendor/systemlab-companion/"
rights = json.loads(members[rights_prefix + "provenance.json"])
assert rights["authorization"] and rights["rights"] and len(rights["files"]) == 5
assert members["LICENSES/LicenseRef-SystemLab-Assets.txt"]
assert all(sha(members[rights_prefix + row["file"]]) == row["sha256"] for row in rights["files"])
manifest = json.loads(members["publication/releases/0.3.2-rc.1/manifest.json"])
image_path = manifest["screenshot_path"]
assert image_path == "publication/media/0.3.2-rc.1/operations-permissions-mobile.jpg"
image = members[image_path]
assert len(image) == 35517 and sha(image) == "a82143bb86ed1baebff2f0518d27bb2ae826332a0b378c24786d342ab912b581"
_jpeg(image)
public_image, image_request = fetch("https://raw.githubusercontent.com/" + REPO + "/" + SOURCE + "/" + image_path)
assert public_image == image
save("public-media", {"checked_at": datetime.now(timezone.utc).isoformat(), "version": VERSION, "source_commit": SOURCE, "state": "Independently Retrieved", "media": [{"path": image_path, "bytes": len(image), "sha256": sha(image), "encoding": "JPEG", "container_validated": True, "matches_public_source_and_exact_archive": True, **image_request}]})
student_matches = [path for path in members if path.endswith("student.safetensors")]
assert student_matches and all(sha(members[path]) == "ff96770308c96b9d96c5f8f6535576e9d791834f76291bf08fce99dcf34d6e6c" for path in student_matches)
save("archive-integrity", {"checked_at": datetime.now(timezone.utc).isoformat(), "version": VERSION, "source_commit": SOURCE, "archive_bytes": len(archive), "archive_sha256": archive_sha, "zip_crc_valid": True, "archive_member_count": len(members), "manifest_hashed_files": len(provenance["files"]), "all_manifest_digests_match": True, "ci_source_hash_count": len(ci["local_software_input_hashes"]), "ci_source_hashes_match_archive": True, "baseline_integrity": True, "private_paths_or_supported_secret_patterns_found": 0, "owned_resources_verified": 5, "unchanged_student_artifact_paths": student_matches, "clean_install_receipt_binds_exact_archive": True, "recorded_exact_archive_suite": re.findall(r"\d+ passed, \d+ skipped[^\n]*", clean["test_suite"]["stdout"]), "stable_release_allowed": False, "operational_acceptance": False, "scope": "Anonymous exact bytes and actual CI/install receipts. No new local installation or operational acceptance claimed."})
import importlib.metadata
import jsonschema
from urllib.parse import urlsplit
SCHEMA_REVISION = "e833d732337dd33aceb45ff1991f896796f1e5e7"
SCHEMA_DIGESTS = {"bom-1.6.schema.json": "18f57f7482593bad9f21b4feed09084640cbeff419d62ad5090c5ceccca5b37d", "spdx.schema.json": "c41917196639055e9f9670811bac23ef777732144f3ff5a2f39686f61580dbe6"}
schemas = {}
def official_schema(url):
    parsed = urlsplit(url)
    assert parsed.hostname == "cyclonedx.org" and parsed.path.startswith("/schema/")
    name = Path(parsed.path).name
    assert name in SCHEMA_DIGESTS and parsed.path == "/schema/" + name
    actual_url = "https://raw.githubusercontent.com/CycloneDX/specification/" + SCHEMA_REVISION + "/schema/" + name
    data, _ = fetch(actual_url, 2 * 1024 * 1024)
    assert sha(data) == SCHEMA_DIGESTS[name]
    schemas[actual_url] = sha(data)
    return json.loads(data)
schema = official_schema("https://cyclonedx.org/schema/bom-1.6.schema.json")
sbom = json.loads(downloaded["SBOM.cdx.json"])
resolver = jsonschema.RefResolver.from_schema(schema, handlers={"http": official_schema, "https": official_schema})
jsonschema.Draft7Validator(schema, resolver=resolver).validate(sbom)
assert sbom["metadata"]["component"]["version"] == VERSION
save("sbom-validation", {"checked_at": datetime.now(timezone.utc).isoformat(), "valid": True, "artifact": "release/" + VERSION + "/SBOM.cdx.json", "sbom_sha256": sha(downloaded["SBOM.cdx.json"]), "components": len(sbom["components"]), "validator": "jsonschema " + importlib.metadata.version("jsonschema"), "official_schema_revision": SCHEMA_REVISION, "official_schema_sha256": schemas, "scope": "Formal exact downloaded CycloneDX1.6 validation, not licence clearance or vulnerability assessment"})
print(json.dumps({"success": True, "version": VERSION, "source_commit": SOURCE, "release_id": release["id"], "assets": 9, "archive_bytes": len(archive), "archive_sha256": archive_sha, "manifest_files": len(provenance["files"]), "ci_source_hashes": len(ci["local_software_input_hashes"]), "media": 1}), flush=True)
