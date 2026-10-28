"""Run real local LLM/neural orchestration on genuine public source passages."""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from airspace.storage import Store
from airspace.identity import provision
from airspace.orchestration import WorkflowRepository, advance_workflow, default_services


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runtime = ROOT / "runtime" / "orchestration-evaluation" / run_id
    runtime.mkdir(parents=True, exist_ok=False)
    os.environ["AIRSPACE_RUNTIME"] = str(runtime)
    os.environ["AIRSPACE_AGENT_MODEL_DIR"] = str(ROOT / "models/pretrained/controller")
    import secrets
    store = Store("sqlite:///" + (runtime / "verification.db").as_posix(), secrets.token_bytes(48))
    store.migrate()
    actor = provision(store, "Isolated software verification", "research@verification.invalid", "regulatory", secrets.token_urlsafe(32))
    request = {"task_kind": "regulatory_research", "objective": "Find the provisions on operational authorisation and U-space flight authorisation; collect supporting source passages for independent review.",
               "jurisdiction": "EU", "operation_date": "2026-10-27", "include_experimental_student": True,
               "controller_mode": "local_causal", "budget": {"max_steps": 8, "max_model_calls": 8, "max_wall_seconds": 1800, "model_timeout_seconds": 120, "tool_timeout_seconds": 180, "max_retries": 1}}
    repository = WorkflowRepository(store)
    row = repository.create(request, actor)
    services = default_services()
    started = time.perf_counter()
    steps = []
    for _ in range(10):
        step_start = time.perf_counter()
        row = advance_workflow(store, row["id"], actor, row["version"], services)
        steps.append({"state": row["status"], "version": row["version"], "elapsed_seconds": round(time.perf_counter() - step_start, 3)})
        print(json.dumps(steps[-1]), flush=True)
        if row["status"] in {"Needs Review", "Cancelled", "Failed", "Blocked", "Reconciliation Required"}:
            break
    evidence = {"run_id": run_id, "kind": "Actual local generative-model and neural execution on genuine public source material", "operational_acceptance": False,
                "records_scope": "Isolated software-verification identity; no aircraft, missions, customers, approvals or telemetry created", "request": request,
                "elapsed_seconds": round(time.perf_counter()-started, 3), "steps": steps, "workflow": row,
                "audit_verification": store.verify_audit(actor["organisation_id"])}
    output = ROOT / "release-evidence/v0.2.0-rc.1"
    output.mkdir(parents=True, exist_ok=True)
    path = output / ("orchestration-local-" + run_id + ".json")
    path.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(path.relative_to(ROOT)), "final_state": row["status"], "seconds": evidence["elapsed_seconds"]}), flush=True)
    store.engine.dispose()
    return 0 if row["status"] == "Needs Review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
