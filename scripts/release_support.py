"""Version and isolation boundaries shared by local release tools."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys
import tempfile


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
        if key.startswith("AIRSPACE_") or key in {
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


def archive_workspace(root: Path, members: list[str], *, work_root: str | None = None,
                      platform: str | None = None) -> tuple[Path, dict]:
    """Choose one isolated workspace; never alter OS settings or remove old runs."""
    platform = sys.platform if platform is None else platform
    windows = platform == "win32"
    if platform not in {"win32", "linux", "darwin"}:
        raise ValueError("Unsupported archive verification platform")
    for name in members:
        if (not name or "\\" in name or ":" in name or PurePosixPath(name).is_absolute()
                or PureWindowsPath(name).is_absolute() or ".." in PurePosixPath(name).parts):
            raise ValueError("Unsafe archive member path")
    if work_root is not None:
        if not work_root.strip() or "\x00" in work_root:
            raise ValueError("Work root must be an existing absolute private directory")
        given = Path(work_root)
        if not given.is_absolute() or (windows and (not PureWindowsPath(work_root).is_absolute()
                or PureWindowsPath(work_root).drive.startswith("\\"))):
            raise ValueError("Work root must be an absolute local directory")
    else:
        given = Path(tempfile.gettempdir()) if windows else root / "runtime/archive-verification"
    for parent in (given, *given.parents):
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Work root must not traverse symlinks or junctions")
    if work_root is None and not windows:
        given.mkdir(parents=True, exist_ok=True)
    base = given.resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Work root must be a directory")

    def budget(destination: Path) -> dict:
        paths = [destination / name for name in members]
        # Include conservative installed-package and pytest/runtime suffix budgets.
        paths.extend([destination / ("v" * 160), destination / ("t" * 200)])
        maximum = max(len(str(path).encode("utf-16-le")) // 2 + 1 for path in paths)
        if windows and maximum > 260:
            raise ValueError("Windows archive path budget exceeds 260 UTF-16 units; choose a shorter --work-root")
        return {"maximum_utf16_units_including_terminator": maximum,
                "windows_legacy_budget": 260, "package_suffix_budget": 160,
                "test_suffix_budget": 200, "scope": "Preflight layout budgets; actual full installation and tests still required"}

    budget(base / "av-xxxxxxxx")
    destination = Path(tempfile.mkdtemp(prefix="av-", dir=base)).resolve(strict=True)
    return destination, {"work_root": str(base), "destination": str(destination),
                         "selection": "explicit" if work_root is not None else "OS temporary directory" if windows else "project runtime",
                         **budget(destination)}


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
