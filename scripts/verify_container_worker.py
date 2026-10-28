"""Observe the separately running CI worker through the actual HTTP API."""
import json
import os
import time
import urllib.request

BASE = "http://127.0.0.1:8787/api/v1"


def request(path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=body, headers=headers), timeout=10) as response:
        return json.load(response)


session = request("/session", {"email": "container-worker@test.invalid", "password": os.environ["AIRSPACE_INITIAL_PASSWORD"]})
token = session["token"]
created = request("/jobs", {"kind": "case_preparation", "payload": {}}, token)
deadline = time.monotonic() + 45
while time.monotonic() < deadline:
    items = request("/jobs", token=token)["items"]
    job = next(item for item in items if item["id"] == created["id"])
    if job["state"] in {"Completed", "Failed", "Expired", "Cancelled"}:
        break
    time.sleep(0.5)
else:
    raise SystemExit("The actual container worker did not complete the isolated job within 45 seconds")
assert job["state"] == "Completed", {"state": job["state"], "error": job.get("error")}
assert job["result"] == {"cases": [], "external_actions": []}, "The verification tenant must remain operationally empty"
audit = request("/audit", token=token)
assert audit["verification"]["valid"]
assert any(item["action"] == "job.finished" and item["payload"]["job_id"] == job["id"] and item["payload"]["state"] == "Completed" for item in audit["items"])
print(json.dumps({"actual_running_container_worker_completed_job": True, "result": job["result"], "audit_valid": True, "operational_acceptance": False}))
