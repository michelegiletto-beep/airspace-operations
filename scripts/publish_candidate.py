"""Plan a candidate release; mutations require --publish inside the gated CI job."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

from release_support import current_version, assert_release_writable

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "michelegiletto-beep/airspace-operations"
BASELINE = "43755041cbfa555158b51979de4c726bf52f7e82dc113e840c1488d974ba9b30"
REQUIRED_CHECKS = {"python_tests", "frontend_tests", "frontend_build", "frontend_dependency_audit", "python_dependency_audit", "optional_neural_dependency_audit", "baseline_integrity"}


def validate_context(root, environment, head):
    version = current_version(root)
    if (environment.get("CI") != "true" or environment.get("GITHUB_ACTIONS") != "true"
            or environment.get("GITHUB_EVENT_NAME") != "push"
            or environment.get("GITHUB_REPOSITORY") != REPOSITORY
            or environment.get("GITHUB_SERVER_URL") != "https://github.com"
            or environment.get("GITHUB_API_URL") != "https://api.github.com"
            or environment.get("GH_HOST", "github.com") != "github.com"
            or environment.get("GH_TOKEN")
            or not environment.get("GITHUB_RUN_ID", "").isdigit()
            or environment.get("GITHUB_REF") != "refs/heads/release/" + version
            or environment.get("AIRSPACE_ENGINEERING_RESULT") != "success"):
        raise ValueError("Publication requires the exact repository, release branch and successful engineering dependency in GitHub Actions")
    sha = environment.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or head != sha:
        raise ValueError("The checked-out source is not the exact GitHub event commit")
    if "-rc." not in version:
        raise ValueError("This workflow publishes engineering candidates only")
    assert_release_writable(root, version)
    return {"version": version, "repository": REPOSITORY, "sha": sha, "tag": "v" + version, "run_id": environment.get("GITHUB_RUN_ID")}


def safe_path(root, relative):
    if not isinstance(relative, str) or "\\" in relative:
        raise ValueError("Unsafe release manifest path")
    path = PurePosixPath(relative)
    target = (root / relative).resolve()
    if (path.is_absolute() or ".." in path.parts or not target.is_relative_to(root.resolve())
            or any(part in {"runtime", ".git", "private", "secrets", "keys", "snapshots", "local-research"} for part in path.parts)
            or any(part.startswith(".env") and part != ".env.example" for part in path.parts)
            or path.suffix.lower() in {".key", ".db", ".sqlite", ".sqlite3", ".pem", ".p12", ".pfx", ".log"}):
        raise ValueError("Unsafe release manifest path")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("Symlinks cannot supply release assets")
    return target


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_artifacts(root, context):
    from package_release import SECRET_PATTERNS
    version = context["version"]
    evidence = root / "release-evidence" / ("v" + version)
    gate = json.loads((evidence / "release-gates.json").read_text())
    if (gate.get("version") != version or gate.get("engineering_checks_passed") is not True
            or gate.get("stable_release_allowed") is not False or gate.get("operational_acceptance") is not False
            or gate.get("external_ci", {}).get("verified") is not True
            or not REQUIRED_CHECKS <= gate.get("checks", {}).keys()
            or not all(gate["checks"][name] is True for name in REQUIRED_CHECKS)):
        raise ValueError("Current dependency, verification and partial-baseline gates are required")
    archive = root / "release" / f"System-Lab-Airspace-Operations-{version}.zip"
    provenance = json.loads((root / "release/RELEASE_PROVENANCE.json").read_text())
    if provenance.get("version") != version or provenance.get("source_commit") != context["sha"] or provenance.get("baseline_sha256") != BASELINE:
        raise ValueError("Release provenance does not identify this source commit and acceptance baseline")
    manifest = provenance["files"]
    ci = json.loads((evidence / "ci-verification.json").read_text())
    if (ci.get("conclusion") != "success" or ci.get("commit") != context["sha"]
            or str(ci.get("run_id")) != str(context.get("run_id")) or not ci.get("local_software_input_hashes")):
        raise ValueError("Successful current-run CI provenance is required")
    for relative, checksum in ci["local_software_input_hashes"].items():
        source = safe_path(root, relative)
        if not source.is_file() or digest(source) != checksum or manifest.get(relative) != checksum:
            raise ValueError("Controlled source differs from the verified engineering commit")
    with zipfile.ZipFile(archive) as content:
        expected = {"airspace-operations/" + name for name in manifest} | {"airspace-operations/RELEASE_PROVENANCE.json"}
        if len(content.namelist()) != len(expected) or set(content.namelist()) != expected:
            raise ValueError("Archive members differ from the source manifest")
        if sum(item.file_size for item in content.infolist()) > 250_000_000:
            raise ValueError("Candidate archive exceeds its bounded verification size")
        for relative, checksum in manifest.items():
            safe_path(root, relative)
            data = content.read("airspace-operations/" + relative)
            if hashlib.sha256(data).hexdigest() != checksum or any(pattern.search(data) for pattern in SECRET_PATTERNS):
                raise ValueError("Archive checksum or secret-pattern verification failed")
        if json.loads(content.read("airspace-operations/RELEASE_PROVENANCE.json")) != provenance:
            raise ValueError("Archive and asset provenance differ")
        if hashlib.sha256(content.read("airspace-operations/SPECIFICATION.md")).hexdigest() != BASELINE:
            raise ValueError("The original acceptance baseline changed")
    restored = json.loads((evidence / "standalone-archive-verification.json").read_text())
    if restored.get("version") != version or restored.get("success") is not True or restored.get("archive_sha256") != digest(archive):
        raise ValueError("A successful clean install of these exact archive bytes is required")
    sbom = json.loads((root / "SBOM.cdx.json").read_text())
    if sbom.get("bomFormat") != "CycloneDX" or sbom["metadata"]["component"]["version"] != version:
        raise ValueError("Current software bill of materials is required")
    vendor = root / "frontend/public/vendor/systemlab-companion"
    rights = json.loads((vendor / "provenance.json").read_text())
    if not rights.get("authorization") or not rights.get("rights") or not (root / "LICENSES/LicenseRef-SystemLab-Assets.txt").is_file():
        raise ValueError("Owned-asset rights and reserved-rights notice are required")
    for item in rights["files"]:
        if digest(safe_path(root, "frontend/public/vendor/systemlab-companion/" + item["file"])) != item["sha256"]:
            raise ValueError("Owned asset bytes changed from their rights provenance")
    assets = [archive, root / "release/RELEASE_PROVENANCE.json", root / "release/SHA256SUMS.txt", root / "SBOM.cdx.json", root / "THIRD_PARTY_NOTICES.md", root / "LICENSE", evidence / "release-gates.json", evidence / "standalone-archive-verification.json", evidence / "ci-verification.json"]
    for asset in assets:
        safe_path(root, asset.relative_to(root).as_posix())
        if not asset.is_file() or any(pattern.search(asset.read_bytes()) for pattern in SECRET_PATTERNS):
            raise ValueError("Release asset is missing or contains a secret pattern")
        relative = asset.relative_to(root).as_posix()
        # This receipt is necessarily produced after packaging and binds the
        # exact archive digest above. Every other attached input is immutable.
        post_package_receipt = evidence / "standalone-archive-verification.json"
        if asset != post_package_receipt and relative in manifest and digest(asset) != manifest[relative]:
            raise ValueError("Release asset changed after archive creation")
    if provenance.get("gates") != gate:
        raise ValueError("Packaged and attached verification gates differ")
    if (root / "release/SHA256SUMS.txt").read_text().strip() != digest(archive) + "  " + archive.name:
        raise ValueError("Candidate checksum asset differs from the archive")
    return assets


def gh(arguments, *, capture=True):
    environment = dict(os.environ, GH_HOST="github.com")
    environment.pop("GH_TOKEN", None)
    result = subprocess.run(["gh", *arguments], env=environment, text=True, capture_output=capture, check=False, timeout=180)
    if result.returncode:
        raise RuntimeError("GitHub CLI operation failed; no retry or overwrite was attempted")
    return result.stdout if capture else ""


def record_engineering(root, context, environment):
    run_id = environment.get("GITHUB_RUN_ID", "")
    if not run_id.isdigit():
        raise ValueError("A current workflow run ID is required")
    result = json.loads(gh(["api", f"repos/{REPOSITORY}/actions/runs/{run_id}/jobs", "--paginate", "--slurp"]))
    jobs = [job for page in result for job in page["jobs"]]
    matches = [job for job in jobs if job["name"] == "containers-postgresql" and job["conclusion"] == "success" and job.get("head_sha") == context["sha"]]
    required = {"Full software suite", "Build actual application and spatial database containers", "Start and verify container health", "Actual running container worker and authenticated API", "PostgreSQL extensions, concurrency and workflow isolation", "Actual PostgreSQL backup and restoration"}
    if len(matches) != 1 or not required <= {step["name"] for step in matches[0]["steps"] if step["conclusion"] == "success"}:
        raise ValueError("Actual successful container, PostgreSQL, worker and restoration steps are required")
    from package_release import source_files
    hashes = {relative.as_posix(): digest(path) for path, relative in source_files() if relative.parts[0] in {"backend", "frontend", "tests", "scripts", "deploy", "migrations", ".github"} and not relative.as_posix().startswith("frontend/dist/")}
    evidence = root / "release-evidence" / ("v" + context["version"])
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "ci-verification.json").write_text(json.dumps({"conclusion": "success", "scope": "Successful engineering dependency job in this still-running publication workflow", "run_id": int(run_id), "job_id": matches[0]["id"], "commit": context["sha"], "local_software_input_hashes": hashes, "verified_job_url": matches[0]["html_url"]}, indent=2) + "\n")


def reviewed_publication_material(root, version):
    """Select explicit reviewed public files; new versions never inherit old copy."""
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+", version):
        raise ValueError("An explicit candidate version is required for publication copy")
    if version == "0.3.0-rc.1":
        notes_path = "publication/v0.3/release-notes.md"
        screenshot_path = "publication/media/v0.3/desktop-companion.jpg"
    else:
        manifest_path = safe_path(root, f"publication/releases/{version}/manifest.json")
        if not manifest_path.is_file() or manifest_path.stat().st_size > 16_384:
            raise ValueError("A bounded version-specific reviewed publication manifest is required")

        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate publication manifest keys are not permitted")
                result[key] = value
            return result

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
        if (not isinstance(manifest, dict) or set(manifest) != {"version", "notes_path", "screenshot_path"}
                or manifest["version"] != version):
            raise ValueError("Publication manifest schema or version differs from this candidate")
        notes_path, screenshot_path = manifest["notes_path"], manifest["screenshot_path"]
        for relative in (notes_path, screenshot_path):
            if (not isinstance(relative, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", relative)
                    or PurePosixPath(relative).as_posix() != relative):
                raise ValueError("Publication material paths must be canonical public relative paths")
        notes = PurePosixPath(notes_path)
        image = PurePosixPath(screenshot_path)
        if notes.parent.as_posix() != f"publication/releases/{version}" or notes.suffix != ".md":
            raise ValueError("Reviewed notes must be a Markdown file in this candidate's publication directory")
        from package_release import EXCLUDED
        if (not screenshot_path.startswith("publication/media/") or image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
                or any(part in EXCLUDED or part.endswith(".egg-info") for part in image.parts)):
            raise ValueError("Reviewed screenshot must be a packaged public raster image")
    source = safe_path(root, notes_path)
    image = safe_path(root, screenshot_path)
    if not source.is_file() or not image.is_file():
        raise ValueError("Reviewed release notes and the actual companion screenshot are required")
    return source, image, screenshot_path


def candidate_notes(root, context, assets):
    source, image, screenshot_path = reviewed_publication_material(root, context["version"])
    if not source.is_file() or not image.is_file():
        raise ValueError("Reviewed release notes and the actual companion screenshot are required")
    body = source.read_text(encoding="utf-8")
    first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
    if context["version"] != "0.3.0-rc.1" and first_line not in {"# Release " + context["version"], "# System Lab Airspace Operations " + context["version"]}:
        raise ValueError("Reviewed release notes must identify this exact candidate version in their heading")
    if re.search(r"(?im)^\s*(?:publication|release|status)(?: status)?\s*:\s*(?:prepared|in progress)\b|\b(?:TODO|TBD)\b", body):
        raise ValueError("Release notes still contain preparation placeholders")
    archive = next(asset for asset in assets if asset.name == f"System-Lab-Airspace-Operations-{context['version']}.zip")
    evidence = root / "release-evidence" / ("v" + context["version"])
    gate = json.loads((evidence / "release-gates.json").read_text())
    clean = json.loads((evidence / "standalone-archive-verification.json").read_text())
    output = clean.get("test_suite", {}).get("stdout", "")
    passed = re.search(r"\b([0-9]+) passed\b", output)
    skipped = re.search(r"\b([0-9]+) skipped\b", output)
    summary = (passed[1] + " passed" if passed else "See the attached actual test output") + (", " + skipped[1] + " skipped" if skipped else "")
    return (body.replace("{{SOURCE_COMMIT}}", context["sha"]).rstrip() +
            f"\n\n![Companion workspace](https://raw.githubusercontent.com/{REPOSITORY}/{context['sha']}/{screenshot_path})\n\n" +
            f"Source commit: `{context['sha']}`. Download: `{archive.name}` ({archive.stat().st_size:,} bytes). SHA-256: `{digest(archive)}`.\n\n" +
            f"Engineering checks: {sum(value is True for value in gate['checks'].values())} passed. Clean-install software suite: {summary}. The original acceptance baseline remains partial; stable release and operational acceptance remain false.\n\n" +
            "Previous candidates: " + ", ".join(
                f"[{version}](https://github.com/{REPOSITORY}/releases/tag/v{version})"
                for version in (("0.2.0-rc.1", "0.1.0-rc.1") if context["version"] == "0.3.0-rc.1"
                                else ("0.3.0-rc.1", "0.2.0-rc.1", "0.1.0-rc.1"))) + ".\n")


def publish(root, context, assets, *, release_body=None):
    if release_body is None:
        release_body = candidate_notes(root, context, assets)
    # Empty lists, rather than ignored CLI errors, distinguish absence from an
    # unavailable API. Create-ref is exclusive; no existing tag is reused.
    refs = json.loads(gh(["api", f"repos/{REPOSITORY}/git/matching-refs/tags/{context['tag']}"]))
    releases = json.loads(gh(["api", f"repos/{REPOSITORY}/releases", "--paginate", "--slurp"]))
    if any(item["ref"] == "refs/tags/" + context["tag"] for item in refs) or any(item["tag_name"] == context["tag"] for page in releases for item in page):
        raise ValueError("Existing tags and releases are frozen; choose a new version")
    gh(["api", "--method", "POST", f"repos/{REPOSITORY}/git/refs", "-f", "ref=refs/tags/" + context["tag"], "-f", "sha=" + context["sha"]])
    with tempfile.TemporaryDirectory(prefix="airspace-candidate-") as folder:
        directory = Path(folder)
        notes = directory / "notes.md"
        notes.write_text(release_body, encoding="utf-8")
        gh(["release", "create", context["tag"], "--repo", REPOSITORY, "--verify-tag", "--target", context["sha"], "--prerelease", "--draft", "--title", "System Lab Airspace Operations " + context["version"], "--notes-file", str(notes), *map(str, assets)])
        retrieved = directory / "retrieved"
        gh(["release", "download", context["tag"], "--repo", REPOSITORY, "--dir", str(retrieved)])
        if {item.name for item in retrieved.iterdir()} != {item.name for item in assets} or any(digest(retrieved / item.name) != digest(item) for item in assets):
            raise ValueError("Uploaded draft assets differ; draft and tag retained for investigation")
        gh(["release", "edit", context["tag"], "--repo", REPOSITORY, "--draft=false", "--prerelease", "--latest=false"])
    return {"state": "Published", "url": f"https://github.com/{REPOSITORY}/releases/tag/{context['tag']}", "independent_public_retrieval": "Required separately; authenticated draft retrieval is not anonymous public verification"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--record-engineering", action="store_true")
    args = parser.parse_args()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()
    context = validate_context(ROOT, os.environ, head)
    clean = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "backend", "frontend", "scripts", "tests", "deploy", "migrations", ".github", "publication", ".gitignore", "Dockerfile", "compose.yaml", "pyproject.toml", "uv.lock"], cwd=ROOT, text=True, capture_output=True, check=True)
    if clean.stdout.strip():
        raise ValueError("Controlled application source changed after checkout")
    if args.publish or args.record_engineering:
        if not os.environ.get("GITHUB_TOKEN"):
            raise ValueError("Only the ephemeral repository-scoped CI token is supported")
    if args.record_engineering:
        record_engineering(ROOT, context, os.environ)
    if args.publish:
        assets = validate_artifacts(ROOT, context)
        print(json.dumps(publish(ROOT, context, assets, release_body=candidate_notes(ROOT, context, assets))))
    else:
        print(json.dumps({**context, "state": "Prepared", "publication_performed": False}))


if __name__ == "__main__":
    main()
