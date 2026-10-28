"""Verify a real pg_dump/pg_restore round trip in disposable CI databases."""
import json
import os
import sys
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from airspace.storage import Store, organisations
from airspace.identity import provision

KEY = b"isolated-recovery-verification-key-only"
NAME = "Isolated pg_dump restoration verification"
url = make_url(os.environ["AIRSPACE_TEST_POSTGRES_URL"])
if sys.argv[1] == "verify":
    url = url.set(database="airspace_restoration")
store = Store(url.render_as_string(hide_password=False), KEY)
store.migrate()
if sys.argv[1] == "seed":
    actor = provision(store, NAME, "restore-check@test.invalid", "regulatory", "isolated-restore-password")
    with store.engine.begin() as conn:
        store.append_audit(conn, actor["organisation_id"], actor["id"], "recovery.marker", {"kind": "Isolated software verification; no operational activity"})
    print("Created isolated recovery marker")
else:
    with store.engine.connect() as conn:
        tenant = conn.execute(select(organisations.c.id).where(organisations.c.name == NAME)).scalar_one()
    result = store.verify_audit(tenant)
    assert result["valid"] and result["count"] == 2, result
    print(json.dumps({"postgresql_restoration_verified": True, "audit_count": result["count"], "audit_valid": True, "operational_acceptance": False}))
store.engine.dispose()
