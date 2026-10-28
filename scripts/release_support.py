"""Version and isolation boundaries shared by local release tools."""
from __future__ import annotations

import json
from pathlib import Path
import re


def current_version(root: Path) -> str:
    match = re.search(r'__version__\s*=\s*"([^"]+)"', (root / "backend/airspace/__init__.py").read_text(encoding="utf-8"))
    if not match or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-rc\.[0-9]+)?", match[1]):
        raise ValueError("A supported explicit release version is required")
    return match[1]


def assert_release_writable(root: Path, version: str) -> None:
    """Publication receipts protect a version even after the active ledger moves."""
    publication = root / "publication"
    paths = {publication / "status.json", *publication.glob("history/*.json"),
             *publication.glob("v*/status.json")}
    for path in sorted(paths):
        if not path.is_file():
            continue
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("release") != version:
            continue
        if set(receipt.get("states_reached", [])) & {"Published", "Independently Retrieved"}:
            raise SystemExit("Published release bytes and metadata are frozen; choose a new software version")


def isolated_archive_environment(project: Path, inherited: dict[str, str]) -> dict[str, str]:
    """Never let a standalone verification use an operator's database or identity."""
    environment = dict(inherited)
    for key in list(environment):
        if key.startswith("AIRSPACE_OIDC_") or key in {
            "AIRSPACE_DATABASE_URL", "AIRSPACE_TEST_POSTGRES_URL", "AIRSPACE_AUDIT_KEY",
            "AIRSPACE_AGENT_MODEL_DIR", "AIRSPACE_MODEL_DIR", "AIRSPACE_INFERENCE_TOKEN",
            "AIRSPACE_INITIAL_PASSWORD",
        }:
            environment.pop(key)
    project = project.resolve()
    runtime = project / "runtime/isolated-release-check"
    environment.update(
        UV_PROJECT_ENVIRONMENT=str(project / ".venv"),
        AIRSPACE_RUNTIME=str(runtime),
        AIRSPACE_DATABASE_URL="sqlite:///" + (runtime / "airspace.db").as_posix(),
        AIRSPACE_AUDIT_KEY="isolated-archive-verification-key-do-not-use",
        AIRSPACE_REQUIRE_TWO_REVIEWERS="false",
        PYTHONPATH=str(project / "backend"),
    )
    return environment


def github_payload_directory(root: Path, version: str, *, legacy: bool = False) -> Path:
    base = root / "runtime/publication/github"
    return base if legacy else base / ("v" + version)


def public_improvement_files(root: Path) -> set[str]:
    """Future cycle contents stay private unless deliberately listed for release."""
    folder = root / "improvement"
    manifest = folder / "publication-manifest.json"
    if not manifest.is_file():
        return set()
    value = json.loads(manifest.read_text(encoding="utf-8"))
    result = {"improvement/publication-manifest.json"}
    for entry in value.get("public_files", []):
        if not isinstance(entry, str):
            raise ValueError("Improvement publication paths must be relative strings")
        relative = Path(entry)
        target = (folder / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(folder.resolve()) or any(part.lower() in {"private", "secrets", "keys", "runtime"} for part in relative.parts) or relative.suffix.lower() not in {".json", ".md", ".csv", ".txt"}:
            raise ValueError("Improvement publication manifest includes a private or unsafe path")
        if not target.is_file():
            raise ValueError("Reviewed improvement publication file is missing")
        result.add("improvement/" + relative.as_posix())
    return result
