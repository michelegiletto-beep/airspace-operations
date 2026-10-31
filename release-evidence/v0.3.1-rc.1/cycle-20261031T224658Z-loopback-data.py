"""Read-only current development health, SQLite and audit verification. No login."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import hashlib
import hmac
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".json")
if OUT.exists():
    raise SystemExit("Refusing to overwrite a dated receipt")
runtime = ROOT / "runtime/review-v3"
sha = lambda data: hashlib.sha256(data).hexdigest()
canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
report = {
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "scope": "Current read-only loopback health and anonymous access boundary plus independent mode=ro SQLite integrity, record snapshot and HMAC audit checks. No authenticated browser-to-API task journey is claimed.",
    "new_sessions_or_authentication": False,
    "task_operational_or_job_mutations": False,
    "new_model_calls": 0,
    "secrets_or_personal_values_logged": False,
    "requests": [],
    "errors": [],
}
opener = build_opener(ProxyHandler({}))
for route in ["/api/v1/health", "/api/v1/me", "/api/v1/companion/tasks"]:
    try:
        try:
            with opener.open(Request("http://127.0.0.1:8787" + route, headers={"Accept": "application/json"}), timeout=5) as response:
                status, data = response.status, response.read(16385)
        except HTTPError as error:
            status, data = error.code, error.read(16385)
        assert len(data) <= 16384
        parsed = json.loads(data)
        result = {"route": route, "status": status, "response_sha256": sha(data)}
        if route.endswith("health"):
            assert status == 200 and parsed["status"] == "ok" and parsed["version"] == "0.3.1-rc.1"
            assert parsed["operational_acceptance"] is False
            result["health"] = parsed
        else:
            assert status == 401
            result["unauthenticated_access_rejected"] = True
        report["requests"].append(result)
    except Exception as error:
        report["errors"].append({"route": route, "type": type(error).__name__})

try:
    connection = sqlite3.connect((runtime / "airspace.db").resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    assert integrity == ["ok"]
    foreign_key_errors = list(connection.execute("PRAGMA foreign_key_check"))
    assert not foreign_key_errors

    def snapshot():
        result = []
        for row in connection.execute("SELECT * FROM records ORDER BY id"):
            item = dict(row)
            item["data"] = json.loads(item["data"])
            result.append(item)
        return result

    records = snapshot()
    fingerprint = sha(canonical(records).encode("utf-8"))
    previous = json.loads((ROOT / "release-evidence/v0.3.1-rc.1/cycle-20261031-recovery-api-data.json").read_text(encoding="utf-8"))
    assert len(records) == previous["records_count"] == 20
    assert fingerprint == previous["records_snapshot_sha256"]
    tasks = [row for row in records if row["kind"] == "companion_task"]
    assert len(tasks) == 2
    task_states = [{"status": row["status"], "version": row["version"], "sha256": sha(canonical(row).encode("utf-8"))} for row in tasks]
    assert sorted(task_states, key=lambda row: row["sha256"]) == sorted(previous["task_states"], key=lambda row: row["sha256"])
    assert all(row["kind"].startswith("companion_") for row in records)

    key = (runtime / "audit.key").read_bytes()
    assert len(key) >= 32
    audits = []
    for tenant in connection.execute("SELECT id,audit_seq FROM organisations"):
        previous_hash = "0" * 64
        rows = list(connection.execute("SELECT * FROM audit WHERE organisation_id=? ORDER BY sequence", (tenant["id"],)))
        assert len(rows) == tenant["audit_seq"]
        for sequence, entry in enumerate(rows, 1):
            row = dict(entry)
            claimed = row.pop("hash")
            row["payload"] = json.loads(row["payload"])
            actual = hmac.new(key, canonical(row).encode("utf-8"), hashlib.sha256).hexdigest()
            assert row["sequence"] == sequence and row["previous_hash"] == previous_hash
            assert hmac.compare_digest(actual, claimed)
            previous_hash = claimed
        audits.append({"valid": True, "count": len(rows), "external_checkpoint_required": True})
    job_counts = {row["state"]: row["count"] for row in connection.execute("SELECT state,COUNT(*) AS count FROM jobs GROUP BY state")}
    assert sha(canonical(snapshot()).encode("utf-8")) == fingerprint
    report["database"] = {"mode": "ro", "query_only": True, "integrity": integrity, "foreign_key_errors": 0, "records": len(records), "records_snapshot_sha256": fingerprint, "matches_prior_recovery_snapshot": True, "tasks": task_states, "operational_records": 0, "audit": audits, "jobs": job_counts, "record_snapshot_stable_during_checks": True}
    connection.close()
except Exception as error:
    report["errors"].append({"section": "database", "type": type(error).__name__, "message": str(error)[:100]})

sys.path.insert(0, str(ROOT / "backend"))
from airspace.worker_health import check_worker_health
worker = check_worker_health(runtime)
report["worker"] = {key: value for key, value in worker.items() if key in {"healthy", "scope", "age_seconds", "error", "reason"}}
report["success"] = not report["errors"]
with OUT.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")
print(json.dumps(report))
raise SystemExit(0 if report["success"] else 1)
