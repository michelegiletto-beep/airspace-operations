"""Exercise frozen-release startup rejection using an isolated software fixture.

This is a startup compatibility check, not a fence for already-running old
processes. It never opens an operator database or starts an inference worker.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

from release_support import isolated_archive_environment


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA256 = "a66a23080654a34133b377c47d549fd83a02907ea6b04805ce272f5619c7273f"
LEGACY_SOURCES = {
    "airspace/api.py": "2e3cbe3606d8098c09fefaf335c6533d0b6c34e1b61ad491ccad06eed74a584e",
    "airspace/storage.py": "d8e8c554059f3ffdb5baedde450b23e4922ddac335967641f9858786cc7c6187",
    "airspace/__init__.py": "8bcb029ee684ea91be244362ee78fb6a96d110d96d813548e0f8f76269382116",
}

CURRENT_PROBE = r'''
import json, os
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select
from airspace import __version__
from airspace.api import create_app
from airspace.identity import provision
from airspace.storage import Store, schema_versions, CURRENT_SCHEMA_VERSION

assert CURRENT_SCHEMA_VERSION == 3, "This verification requires the privacy compatibility marker"
store = Store(os.environ["AIRSPACE_DATABASE_URL"], os.environ["AIRSPACE_AUDIT_KEY"].encode())
store.migrate()
store.migrate()
with store.engine.connect() as conn:
    markers = sorted(conn.execute(select(schema_versions.c.version)).scalars())
assert markers == [1, 2, 3]
password = "isolated-compatibility-fixture-password"
owner = provision(store, "Isolated compatibility fixture", "owner@test.invalid", "regulatory", password)
peer = provision(store, "Isolated compatibility fixture", "peer@test.invalid", "viewer", password, owner["organisation_id"])
other = provision(store, "Other isolated compatibility fixture", "other@test.invalid", "viewer", password)
checks = {}
with TestClient(create_app(store, serve_frontend=False)) as client:
    def headers(actor):
        response = client.post("/api/v1/session", json={"email": actor["email"], "password": password})
        assert response.status_code == 200
        return {"Authorization": "Bearer " + response.json()["token"]}
    auth = {name: headers(actor) for name, actor in (("owner", owner), ("peer", peer), ("other_tenant", other))}
    response = client.post("/api/v1/companion/conversations", headers=auth["owner"], json={"workspace": "administration", "title": "Isolated privacy compatibility fixture"})
    assert response.status_code == 201, response.status_code
    conversation = response.json()
    base = "/api/v1/companion/conversations/" + conversation["id"]
    response = client.post(base + "/messages", headers=auth["owner"], json={"message": "Isolated software fixture: verify private notes remain actor scoped.", "expected_version": conversation["version"]})
    assert response.status_code == 202, response.status_code
    pending = response.json()
    assert pending["job"]["kind"] == "companion_reply" and pending["job"]["state"] == "Queued"
    assert pending["reply"] is None
    message_id, job_id = pending["user_message"]["id"], pending["job"]["id"]
    for name, credentials in auth.items():
        history = client.get("/api/v1/records/companion_message/" + message_id + "/history", headers=credentials)
        generic = client.get("/api/v1/records/companion_message/" + message_id, headers=credentials)
        assert history.status_code == 404 and generic.status_code == 404
        visible_jobs = client.get("/api/v1/jobs", headers=credentials)
        assert visible_jobs.status_code == 200
        job_visible = any(item["id"] == job_id for item in visible_jobs.json()["items"])
        detail = client.get(base, headers=credentials)
        assert detail.status_code == (200 if name == "owner" else 404)
        assert job_visible == (name == "owner")
        checks[name] = {"generic_history_status": history.status_code, "generic_record_status": generic.status_code, "private_conversation_status": detail.status_code, "private_job_visible": job_visible}
    owner_detail = client.get(base, headers=auth["owner"]).json()
    assert len(owner_detail["messages"]) == 1 and owner_detail["messages"][0]["data"]["role"] == "user"
    assert owner_detail["active_job"]["id"] == job_id
audits = [store.verify_audit(actor["organisation_id"]) for actor in (owner, other)]
assert all(result["valid"] for result in audits)
store.engine.dispose()
print(json.dumps({"software_version": __version__, "schema_markers": markers, "privacy_checks": checks, "fixture_has_private_user_message_and_queued_job": True, "worker_or_model_started": False, "audit_valid": True, "audit_counts": [item["count"] for item in audits]}))
'''

LEGACY_PROBE = r'''
import hashlib, json, os, re
from pathlib import Path
from sqlalchemy import event
import airspace
import airspace.api as api
import airspace.storage as storage

expected = Path(os.environ["PYTHONPATH"]).resolve() / "airspace"
assert Path(api.__file__).resolve() == expected / "api.py"
assert Path(storage.__file__).resolve() == expected / "storage.py"
assert airspace.__version__ == "0.2.0-rc.1" and storage.CURRENT_SCHEMA_VERSION == 2
store = storage.Store(os.environ["AIRSPACE_DATABASE_URL"], os.environ["AIRSPACE_AUDIT_KEY"].encode())
statements = []
event.listen(store.engine, "before_cursor_execute", lambda conn, cursor, statement, parameters, context, executemany: statements.append(statement))
app_constructed = []
original_fastapi = api.FastAPI
def observed_fastapi(*args, **kwargs):
    app_constructed.append(True)
    return original_fastapi(*args, **kwargs)
api.FastAPI = observed_fastapi
try:
    api.create_app(store, serve_frontend=False)
except ValueError as error:
    assert str(error) == "Database schema is newer than this software; use the matching release", str(error)
    assert not app_constructed, "Old API was constructed before compatibility rejection"
    assert any("schema_versions" in statement for statement in statements)
    forbidden = re.compile(r'\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+["`\[]?(?:records|record_versions|jobs|users|sessions|audit|outbox|organisations)\b', re.I)
    assert not any(forbidden.search(statement) for statement in statements), statements
    print(json.dumps({"software_version": airspace.__version__, "maximum_schema_version": storage.CURRENT_SCHEMA_VERSION, "startup_rejected": True, "exception_type": type(error).__name__, "message": str(error), "api_constructed": False, "domain_queries_executed": False, "observed_sql": statements, "source_sha256": {name: hashlib.sha256((expected / name).read_bytes()).hexdigest() for name in ("api.py", "storage.py", "__init__.py")}}))
else:
    raise AssertionError("Frozen old API accepted a database containing actor-private records")
finally:
    store.engine.dispose()
'''


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_legacy_backend(archive: Path, directory: Path) -> dict:
    if sha256(archive) != ARCHIVE_SHA256:
        raise ValueError("Frozen 0.2 archive checksum does not match the independently retrieved release")
    prefix = "airspace-operations/backend/"
    destination = (directory / "legacy/backend").resolve()
    destination.mkdir(parents=True)
    members = 0
    total = 0
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            if not entry.filename.startswith(prefix) or entry.is_dir():
                continue
            relative = PurePosixPath(entry.filename[len(prefix):])
            target = destination.joinpath(*relative.parts).resolve()
            if relative.is_absolute() or ".." in relative.parts or "\\" in entry.filename or not target.is_relative_to(destination) or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Unsafe frozen backend archive member")
            if entry.file_size > 10_000_000:
                raise ValueError("Frozen backend member exceeds verification size limit")
            total += entry.file_size
            if total > 100_000_000:
                raise ValueError("Frozen backend exceeds verification size limit")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(source.read(entry))
            members += 1
    for name, expected in LEGACY_SOURCES.items():
        if sha256(destination / name) != expected:
            raise ValueError("Frozen release application source checksum mismatch")
    return {"directory": destination, "members": members, "uncompressed_bytes": total}


def database_snapshot(path: Path) -> dict:
    """Read complete logical state without emitting fixture row contents."""
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        schema = connection.execute("SELECT name,type,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        tables = {}
        for name, kind, _ in schema:
            if kind != "table":
                continue
            quoted = '"' + name.replace('"', '""') + '"'
            tables[name] = sorted(json.dumps(row, separators=(",", ":")) for row in connection.execute("SELECT * FROM " + quoted))
    value = {"schema": schema, "tables": tables}
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "table_counts": {name: len(rows) for name, rows in tables.items()}}


def run_probe(name: str, code: str, environment: dict, directory: Path) -> dict:
    path = directory / (name + ".py")
    path.write_text(code, encoding="utf-8")
    command = [sys.executable, str(path)]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=directory, env=environment, text=True, capture_output=True, timeout=120)
    result = {"command": command, "exit_code": completed.returncode, "seconds": round(time.monotonic() - started, 3), "stdout": completed.stdout, "stderr": completed.stderr}
    if completed.returncode:
        raise RuntimeError("Isolated " + name + " failed: " + json.dumps(result))
    result["result"] = json.loads(completed.stdout)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-archive", type=Path, default=ROOT / "release/System-Lab-Airspace-Operations-0.2.0-rc.1.zip")
    args = parser.parse_args()
    report_path = ROOT / "release-evidence/v0.3.0-rc.1/schema-compatibility-verification.json"
    report = {"started_at": timestamp(), "success": False, "scope": "Isolated SQLite software fixture and frozen 0.2 Python application source executed with the current verification dependency runtime. No operational instance, inference, live HTTP service or external provider.", "legacy_archive": str(args.legacy_archive.resolve()), "expected_archive_sha256": ARCHIVE_SHA256, "expected_legacy_source_sha256": LEGACY_SOURCES, "invocation": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]], "prior_finding": "Schema 2 admitted the old server, whose generic organisation-level jobs and history endpoints did not enforce actor-private companion semantics. This check preserves that finding and verifies the schema-3 startup boundary.", "limitations": ["A startup schema marker cannot revoke already-running old APIs, workers, embedded library consumers or database sessions. Stop every old process before migration; mixed-version rolling deployment is unsafe.", "Do not remove schema 3 or downgrade the live database in place. Use compatible software or restore a complete pre-upgrade checkpoint into a separately controlled environment.", "This SQLite run does not establish PostgreSQL deployment acceptance or compatibility with every historical binary."], "external_actions": [], "model_calls": 0, "published": False}
    verification_root = (ROOT / "runtime/verification").resolve()
    verification_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="schema-compatibility-", dir=verification_root)).resolve()
    if not directory.is_relative_to(verification_root):
        raise ValueError("Verification directory escaped its isolated runtime boundary")
    report["isolated_directory"] = str(directory)
    try:
        extracted = extract_legacy_backend(args.legacy_archive.resolve(), directory)
        report["legacy_archive_sha256"] = sha256(args.legacy_archive.resolve())
        report["extracted_backend"] = {key: str(value) if isinstance(value, Path) else value for key, value in extracted.items()}
        environment = isolated_archive_environment(directory, dict(os.environ))
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = str(ROOT / "backend")
        database = directory / "fixture.db"
        environment["AIRSPACE_DATABASE_URL"] = "sqlite:///" + database.as_posix()
        report["environment_isolation"] = {"database": "New verification-only SQLite file", "oidc_environment_removed": not any(key.startswith("AIRSPACE_OIDC_") for key in environment), "inherited_database_url_removed": True, "inherited_model_and_identity_secrets_removed": True, "fixture_audit_key": "Fixed public software-verification key only; no operator key used"}
        report["current_probe"] = run_probe("current_privacy_probe", CURRENT_PROBE, environment, directory)
        before = database_snapshot(database)
        legacy_environment = dict(environment, PYTHONPATH=str(extracted["directory"]))
        report["legacy_probe"] = run_probe("legacy_startup_probe", LEGACY_PROBE, legacy_environment, directory)
        after = database_snapshot(database)
        report["database_before_legacy_startup"] = before
        report["database_after_legacy_startup"] = after
        if before != after:
            raise AssertionError("Rejected legacy startup changed database schema, domain records, audit or version history")
        if report["legacy_probe"]["result"]["source_sha256"] != {Path(name).name: digest for name, digest in LEGACY_SOURCES.items()}:
            raise AssertionError("Executed legacy source hashes changed after extraction")
        report["database_unchanged"] = True
        report["success"] = True
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        report["finished_at"] = timestamp()
        report["verifier_sha256"] = sha256(Path(__file__).resolve())
        report["current_source_sha256"] = {name: sha256(ROOT / name) for name in ("backend/airspace/storage.py", "backend/airspace/api.py", "backend/airspace/assistant.py")}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "report": str(report_path), "database_unchanged": report.get("database_unchanged", False), "failure": report.get("failure")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
