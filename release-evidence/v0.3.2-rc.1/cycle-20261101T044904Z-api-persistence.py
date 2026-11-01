"""Independently inspect the actual candidate review snapshot without login or writes."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
import hashlib
import hmac
import json
import sqlite3
import sys

CANDIDATE = Path(__file__).resolve().parents[2]
PRODUCT = CANDIDATE.parent.parent
OUT = Path(__file__).with_suffix(".json")
if OUT.exists():
    raise SystemExit("Refusing to overwrite a prior receipt")
canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
sha = lambda data: hashlib.sha256(data).hexdigest()
report = {"checked_at": datetime.now(timezone.utc).isoformat(), "candidate_version": "0.3.2-rc.1", "scope": "Read-only candidate loopback and two distinct persistent stores. Root's authenticated browser journey is corroborated without a new login or operational API action. No inference or operational acceptance.", "new_authentication": False, "new_model_calls": 0, "task_or_operational_mutations": False, "secrets_or_personal_values_logged": False, "errors": [], "requests": []}

try:
    opener = build_opener(ProxyHandler({}))
    for route in ["/api/v1/health", "/api/v1/me", "/api/v1/companion/tasks"]:
        try:
            with opener.open(Request("http://127.0.0.1:8788" + route, headers={"Accept": "application/json"}), timeout=5) as response:
                status, content = response.status, response.read(16385)
        except HTTPError as error:
            status, content = error.code, error.read(16385)
        assert len(content) <= 16384
        result = {"route": route, "status": status, "response_sha256": sha(content)}
        if route.endswith("health"):
            value = json.loads(content)
            assert status == 200 and value["status"] == "ok" and value["version"] == "0.3.2-rc.1" and value["operational_acceptance"] is False
            result["health"] = value
        else:
            assert status == 401
            result["unauthenticated_access_rejected"] = True
        report["requests"].append(result)
except Exception as error:
    report["errors"].append({"section": "api", "type": type(error).__name__})

def inspect_store(relative):
    folder = PRODUCT / relative
    database = folder / "airspace.db"
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    assert integrity == ["ok"] and not list(connection.execute("PRAGMA foreign_key_check"))
    records = []
    for entry in connection.execute("SELECT * FROM records ORDER BY id"):
        row = dict(entry)
        row["data"] = json.loads(row["data"])
        records.append(row)
    fingerprint = sha(canonical(records).encode("utf-8"))
    assert fingerprint == "c6801f17dcf2fa8f84017bad30a9c7af3db4a0d8b87e4495c96d2180d46eee01"
    assert len(records) == 20 and all(row["kind"].startswith("companion_") for row in records)
    tasks = [{"status": row["status"], "version": row["version"], "sha256": sha(canonical(row).encode("utf-8"))} for row in records if row["kind"] == "companion_task"]
    expected = [{"status": "Open", "version": 1, "sha256": "c0918ab201ddf8786bbb4da0fdc1cedebe4e2db98f9002cbb8c6e6ded7057c16"}, {"status": "Completed", "version": 2, "sha256": "94df8703ff398427bb05d155cddfd44fd00fa70565a7f4f904493649c7e816f8"}]
    assert sorted(tasks, key=lambda row: row["sha256"]) == sorted(expected, key=lambda row: row["sha256"])
    key = (folder / "audit.key").read_bytes()
    audits = []
    for tenant in connection.execute("SELECT id,audit_seq FROM organisations"):
        rows = list(connection.execute("SELECT * FROM audit WHERE organisation_id=? ORDER BY sequence", (tenant["id"],)))
        assert len(rows) == tenant["audit_seq"]
        previous = "0" * 64
        actions = {}
        for sequence, entry in enumerate(rows, 1):
            row = dict(entry)
            claimed = row.pop("hash")
            row["payload"] = json.loads(row["payload"])
            actual = hmac.new(key, canonical(row).encode("utf-8"), hashlib.sha256).hexdigest()
            assert row["sequence"] == sequence and row["previous_hash"] == previous and hmac.compare_digest(actual, claimed)
            previous = claimed
            actions[row["action"]] = actions.get(row["action"], 0) + 1
        audits.append({"valid": True, "count": len(rows), "actions": actions, "external_checkpoint_required": True})
    roles = sorted({row[0] for row in connection.execute("SELECT role FROM users WHERE disabled=0")})
    jobs = {row["state"]: row["count"] for row in connection.execute("SELECT state,COUNT(*) AS count FROM jobs GROUP BY state")}
    connection.close()
    return {"store": relative, "mode": "ro", "query_only": True, "integrity": integrity, "foreign_key_errors": 0, "records": 20, "records_snapshot_sha256": fingerprint, "tasks": tasks, "operational_records": 0, "audit": audits, "jobs": jobs, "existing_actor_roles": roles}

try:
    source = inspect_store("runtime/review-v3")
    candidate = inspect_store("runtime/candidate032-review")
    assert sum(row["count"] for row in source["audit"]) == 46
    assert source["records_snapshot_sha256"] == candidate["records_snapshot_sha256"]
    assert source["tasks"] == candidate["tasks"] and source["existing_actor_roles"] == candidate["existing_actor_roles"]
    report["original_store"] = source
    report["candidate_store"] = candidate
    snapshot = PRODUCT / "runtime/candidate032-review/SNAPSHOT.json"
    report["snapshot_provenance"] = {"distinct_database_files": (PRODUCT / "runtime/review-v3/airspace.db").resolve() != (PRODUCT / "runtime/candidate032-review/airspace.db").resolve(), "provenance_file_present": snapshot.is_file(), "provenance_file_sha256": sha(snapshot.read_bytes()), "audit_key_matches_without_exposing_material": hmac.compare_digest((PRODUCT / "runtime/review-v3/audit.key").read_bytes(), (PRODUCT / "runtime/candidate032-review/audit.key").read_bytes()), "domain_records_match_original": True, "authentication_audit_delta": sum(row["count"] for row in candidate["audit"]) - 46}
except Exception as error:
    report["errors"].append({"section": "persistent_data", "type": type(error).__name__, "message": str(error)[:120]})

sys.path.insert(0, str(CANDIDATE / "backend"))
from airspace.worker_health import check_worker_health
health = check_worker_health(PRODUCT / "runtime/candidate032-review")
report["candidate_worker"] = {key: value for key, value in health.items() if key in {"healthy", "scope", "age_seconds", "reason"}}
if not health["healthy"]:
    report["errors"].append({"section": "worker", "type": "UnhealthyWorker"})
report["success"] = not report["errors"]
with OUT.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")
print(json.dumps(report))
raise SystemExit(0 if report["success"] else 1)
