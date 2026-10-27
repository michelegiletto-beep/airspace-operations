"""Create identity-only isolated browser test realm. Never seed operational data."""
import os
os.environ["AIRSPACE_RUNTIME"] = "runtime/browser-test"
from airspace.storage import local_store, users
from airspace.identity import provision
from sqlalchemy import select

store = local_store()
store.migrate()
with store.engine.connect() as connection:
    exists = connection.execute(select(users)).first()
if not exists:
    author = provision(store, "Isolated browser verification", "browser@test.invalid", "regulatory", "isolated-browser-only-passphrase")
    provision(store, "Isolated browser verification", "reviewer@test.invalid", "reviewer", "isolated-browser-only-passphrase", author["organisation_id"])
print("Identity-only isolated browser realm is ready; no operational records were created")
