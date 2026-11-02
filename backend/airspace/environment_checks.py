"""Read-only installation diagnostics; path budgets do not establish usable storage."""
from __future__ import annotations

import sys
from pathlib import Path


REGISTRY_KEY = r"SYSTEM\CurrentControlSet\Control\FileSystem"


def _read_windows_long_paths() -> bool | None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY, 0, winreg.KEY_READ) as key:
        value, kind = winreg.QueryValueEx(key, "LongPathsEnabled")
    if kind != winreg.REG_DWORD or type(value) is not int or value not in (0, 1):
        return None
    return value == 1


def storage_path_diagnostics(runtime: str | Path, *, platform: str | None = None) -> dict:
    """Inspect configuration and explicit layout examples without touching storage."""
    platform = sys.platform if platform is None else platform
    applicable = platform == "win32"
    enabled = None
    if applicable:
        try:
            enabled = _read_windows_long_paths()
        except (ImportError, OSError):
            pass
    state = "Not Applicable" if not applicable else "Enabled" if enabled is True else "Disabled" if enabled is False else "Unknown"
    root = str(Path(runtime).resolve())
    characters = lambda value: len(value.encode("utf-16-le")) // 2
    prefix_characters = characters(root.rstrip("\\/"))
    layouts = []
    for name, components in (
        ("evidence_blob", [("objects", 7), ("tenant UUID", 36), ("SHA-256 filename", 64)]),
        ("source_snapshot_temporary_file", [("sources", 7), ("tenant UUID", 36), ("maximum accepted source identifier", 100), ("SHA-256 directory", 64), ("original.bin.tmp- plus 16 hexadecimal characters", 33)]),
    ):
        suffix = sum(length for _, length in components) + len(components)
        total = prefix_characters + suffix
        layouts.append({"name": name, "component_assumptions": [{"name": label, "characters": length} for label, length in components], "separators": len(components), "additional_characters": suffix, "total_characters": total, "legacy_limit_reached": total >= 260})
    reaches_limit = any(row["legacy_limit_reached"] for row in layouts)
    if not applicable:
        assessment = "Not Applicable"
    elif enabled is True:
        assessment = "Windows configuration enabled; process and storage support unverified"
    elif reaches_limit:
        assessment = "Representative layout reaches the legacy Windows path limit"
    elif enabled is False:
        assessment = "Representative layouts are below the legacy Windows path limit"
    else:
        assessment = "Windows long-path configuration is unknown"
    return {
        "windows_long_paths": {"applicable": applicable, "registry_enabled": enabled, "registry_status": state, "registry_scope": "Machine configuration only; process manifest and filesystem support are not verified"},
        "length_unit": "UTF-16 code units (Windows characters)", "runtime_characters": characters(root),
        "legacy_limit_characters_including_terminator": 260, "representative_layouts": layouts,
        "assessment": assessment, "io_verified": False, "configuration_only": True,
        "scope": "Explicit path-layout examples, not a complete storage budget or proof that a directory exists, permits access, or supports writes. Other output roots, identifiers, temporary files and tools can require longer paths.",
        "guidance": "Choose a shorter private AIRSPACE_RUNTIME and a short isolated test temporary directory when needed. Back up and restore existing data and its audit key before relocating it. See docs/administrator-handbook.md. This command does not change Windows settings or perform a storage write test.",
    }
