"""Administrative commands. Credentials are supplied interactively or by environment."""
import argparse
import getpass
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from .storage import local_store, Store, metadata, now, organisations, CURRENT_SCHEMA_VERSION


def main():
    parser = argparse.ArgumentParser(prog="airspace", description="System Lab Airspace Operations administration")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("migrate")
    provisioner = sub.add_parser("user-add")
    provisioner.add_argument("--organisation", required=True)
    provisioner.add_argument("--organisation-id")
    provisioner.add_argument("--email", required=True)
    provisioner.add_argument("--role", required=True)
    server = sub.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8787)
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--organisation-id", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--input", required=True)
    restore.add_argument("--target", required=True, help="New SQLite path; existing targets are refused")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--source-id", required=True)
    ingest.add_argument("--output", default="runtime/sources/public")
    sub.add_parser("openapi")
    inference = sub.add_parser("inference-serve")
    inference.add_argument("--host", default="127.0.0.1")
    inference.add_argument("--port", type=int, default=8789)
    for command in ("train", "evaluate", "export"):
        forwarded = sub.add_parser(command)
        forwarded.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "restore":
        target = Path(args.target).resolve()
        source = Path(args.input).resolve()
        if target.exists() or source == target:
            parser.error("Restoration requires a new target file")
        with sqlite3.connect(source.as_posix()) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                parser.error("Backup integrity failed")
            target.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(target.as_posix()) as destination:
                conn.backup(destination)
        print(json.dumps({"restored": str(target), "audit_key_required": True, "at": now()}))
        return
    store = local_store()
    store.migrate()
    if args.command == "migrate":
        print(json.dumps({"schema_version": CURRENT_SCHEMA_VERSION, "status": "Applied"}))
    elif args.command == "check":
        print(json.dumps({"python": sys.version.split()[0], "database_profile": "SQLite portability" if store.url.startswith("sqlite") else "PostgreSQL", "schema_version": CURRENT_SCHEMA_VERSION, "docker": bool(shutil.which("docker")), "pg_dump": bool(shutil.which("pg_dump")), "runtime": str(Path(os.getenv("AIRSPACE_RUNTIME", "runtime")).resolve()), "operational_acceptance": False}, indent=2))
    elif args.command == "user-add":
        from .identity import provision
        password = os.environ.get("AIRSPACE_INITIAL_PASSWORD") or getpass.getpass("New password (at least 12 characters): ")
        result = provision(store, args.organisation, args.email, args.role, password, args.organisation_id)
        print(json.dumps(result, indent=2))
    elif args.command == "serve":
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(store), host=args.host, port=args.port, access_log=False)
    elif args.command == "worker":
        from .worker import run_once
        while True:
            result = run_once(store)
            if result:
                print(json.dumps(result), flush=True)
            if args.once:
                break
            time.sleep(2)
    elif args.command == "verify":
        result = store.verify_audit(args.organisation_id)
        print(json.dumps(result, indent=2))
        if not result["valid"]:
            raise SystemExit(1)
    elif args.command == "backup":
        target = Path(args.output).resolve()
        if target.exists():
            parser.error("Backup target already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not store.url.startswith("sqlite"):
            parser.error("Use pg_dump --format=custom for PostgreSQL; see recovery runbook")
        with store.engine.connect() as connection:
            raw = connection.connection.driver_connection
            with sqlite3.connect(target.as_posix()) as destination:
                raw.backup(destination)
        print(json.dumps({"backup": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "at": now(), "audit_key_included": False}))
    elif args.command == "ingest":
        from .regulatory import monitor_registered_source
        root = Path(__file__).resolve().parents[2]
        catalogue = json.loads((root / "sources/catalogue.json").read_text())
        entry = next((s for s in catalogue["sources"] if s["id"] == args.source_id), None)
        if not entry:
            parser.error("Source is not in the approved catalogue")
        result = monitor_registered_source(args.source_id, Path(args.output))
        print(json.dumps({k: v for k, v in result.items() if k != "passages"}, indent=2))
        if not result.get("success"):
            raise SystemExit(1)
    elif args.command == "openapi":
        from .api import create_app
        print(json.dumps(create_app(store, serve_frontend=False).openapi(), indent=2))
    elif args.command == "inference-serve":
        import uvicorn
        from .inference import create_inference_app
        uvicorn.run(create_inference_app(store), host=args.host, port=args.port, access_log=False)
    elif args.command in {"train", "evaluate", "export"}:
        import subprocess
        root = Path(__file__).resolve().parents[2]
        script = {"train": "train_neural.py", "evaluate": "evaluate_retrieval.py", "export": "export_case.py"}[args.command]
        arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        raise SystemExit(subprocess.call([sys.executable, str(root / "scripts" / script), *arguments]))


if __name__ == "__main__":
    main()
