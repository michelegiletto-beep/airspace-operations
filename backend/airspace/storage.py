"""Transactional tenant storage and tamper-evident audit records."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (JSON, Column, ForeignKey, Integer, MetaData, String, Table, inspect,
                        Text, UniqueConstraint, create_engine, event, select, update)

metadata = MetaData()
organisations = Table("organisations", metadata, Column("id", String, primary_key=True), Column("name", String, nullable=False), Column("audit_seq", Integer, nullable=False, default=0))
users = Table("users", metadata, Column("id", String, primary_key=True), Column("organisation_id", ForeignKey("organisations.id"), nullable=False), Column("email", String, unique=True, nullable=False), Column("role", String, nullable=False), Column("password_hash", String, nullable=False), Column("disabled", Integer, nullable=False, default=0))
sessions = Table("sessions", metadata, Column("digest", String, primary_key=True), Column("user_id", ForeignKey("users.id"), nullable=False), Column("expires_at", String, nullable=False))
records = Table("records", metadata, Column("id", String, primary_key=True), Column("organisation_id", ForeignKey("organisations.id"), nullable=False, index=True), Column("kind", String, nullable=False, index=True), Column("title", String, nullable=False), Column("status", String, nullable=False), Column("data", JSON, nullable=False), Column("version", Integer, nullable=False), Column("created_by", String, nullable=False), Column("created_at", String, nullable=False), Column("updated_at", String, nullable=False))
versions = Table("record_versions", metadata, Column("id", String, primary_key=True), Column("organisation_id", String, nullable=False), Column("record_id", ForeignKey("records.id"), nullable=False), Column("version", Integer, nullable=False), Column("snapshot", JSON, nullable=False), UniqueConstraint("record_id", "version"))
audit = Table("audit", metadata, Column("id", String, primary_key=True), Column("organisation_id", ForeignKey("organisations.id"), nullable=False), Column("sequence", Integer, nullable=False), Column("actor_id", String, nullable=False), Column("action", String, nullable=False), Column("at", String, nullable=False), Column("payload", JSON, nullable=False), Column("previous_hash", String, nullable=False), Column("hash", String, nullable=False), UniqueConstraint("organisation_id", "sequence"))
outbox = Table("outbox", metadata, Column("id", String, primary_key=True), Column("organisation_id", String, nullable=False, index=True), Column("at", String, nullable=False), Column("topic", String, nullable=False), Column("payload", JSON, nullable=False), Column("delivered_at", String))
jobs = Table("jobs", metadata, Column("id", String, primary_key=True), Column("organisation_id", String, nullable=False), Column("kind", String, nullable=False), Column("actor_id", String, nullable=False), Column("state", String, nullable=False), Column("payload", JSON, nullable=False), Column("result", JSON), Column("attempts", Integer, nullable=False), Column("lease_until", String), Column("deadline", String), Column("error", String), Column("version", Integer, nullable=False), Column("created_at", String, nullable=False))
idempotency = Table("idempotency", metadata, Column("organisation_id", String, primary_key=True), Column("key", String, primary_key=True), Column("request_hash", String, nullable=False), Column("response", JSON, nullable=False))
schema_versions = Table("schema_versions", metadata, Column("version", Integer, primary_key=True), Column("applied_at", String, nullable=False))
reservations = Table("resource_reservations", metadata, Column("id", String, primary_key=True), Column("organisation_id", ForeignKey("organisations.id"), nullable=False), Column("schedule_id", ForeignKey("records.id"), nullable=False), Column("mission_id", String, nullable=False), Column("resource_kind", String, nullable=False), Column("resource_id", String, nullable=False), Column("start", String, nullable=False), Column("end", String, nullable=False), Column("state", String, nullable=False), UniqueConstraint("schedule_id", "mission_id", "resource_kind", "resource_id"))
sharing_agreements = Table("sharing_agreements", metadata,
    Column("id", String, primary_key=True),
    Column("owner_organisation_id", ForeignKey("organisations.id"), nullable=False, index=True),
    Column("operator_organisation_id", ForeignKey("organisations.id"), nullable=False, index=True),
    Column("aircraft_id", ForeignKey("records.id"), nullable=False),
    Column("version", Integer, nullable=False), Column("state", String, nullable=False),
    Column("terms", JSON, nullable=False), Column("offer_actor_id", String, nullable=False),
    Column("accepted_actor_id", String), Column("created_at", String, nullable=False), Column("updated_at", String, nullable=False))
resource_locks = Table("resource_locks", metadata,
    Column("resource_key", String, primary_key=True), Column("generation", Integer, nullable=False, default=0))
fleet_reservations = Table("fleet_reservations", metadata,
    Column("id", String, primary_key=True),
    Column("owner_organisation_id", ForeignKey("organisations.id"), nullable=False, index=True),
    Column("operator_organisation_id", ForeignKey("organisations.id"), nullable=False, index=True),
    Column("aircraft_id", ForeignKey("records.id"), nullable=False),
    Column("agreement_id", ForeignKey("sharing_agreements.id")),
    Column("schedule_id", ForeignKey("records.id"), nullable=False), Column("mission_id", String, nullable=False),
    Column("owner_record_version", Integer), Column("flight_seconds", Integer),
    Column("start", String, nullable=False), Column("end", String, nullable=False), Column("state", String, nullable=False),
    UniqueConstraint("schedule_id", "mission_id", "aircraft_id"))
CURRENT_SCHEMA_VERSION = 2


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier() -> str:
    return str(uuid4())


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Store:
    def __init__(self, url: str, audit_key: bytes):
        if len(audit_key) < 32:
            raise ValueError("Audit key must contain at least 32 bytes")
        self.key = audit_key
        self.url = url
        kwargs = {"connect_args": {"check_same_thread": False, "timeout": 20}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        self.engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def sqlite_config(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=WAL")

    def migrate(self):
        if inspect(self.engine).has_table("schema_versions"):
            with self.engine.connect() as conn:
                existing = set(conn.execute(select(schema_versions.c.version)).scalars())
                if any(version > CURRENT_SCHEMA_VERSION for version in existing):
                    raise ValueError("Database schema is newer than this software; use the matching release")
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            applied = set(conn.execute(select(schema_versions.c.version)).scalars())
            if any(version > CURRENT_SCHEMA_VERSION for version in applied):
                raise ValueError("Database schema is newer than this software; use the matching release")
            if 1 not in applied:
                conn.execute(schema_versions.insert().values(version=1, applied_at=now()))
            if 2 not in applied:
                conn.execute(schema_versions.insert().values(version=2, applied_at=now()))

    def append_audit(self, conn, tenant, actor, action, payload):
        # This atomic tenant-row update serialises chain writers on PostgreSQL and SQLite.
        sequence = conn.execute(update(organisations).where(organisations.c.id == tenant).values(audit_seq=organisations.c.audit_seq + 1).returning(organisations.c.audit_seq)).scalar_one()
        previous = conn.execute(select(audit.c.hash).where(audit.c.organisation_id == tenant, audit.c.sequence == sequence - 1)).scalar_one_or_none() or "0" * 64
        row = dict(id=identifier(), organisation_id=tenant, sequence=sequence, actor_id=actor, action=action, at=now(), payload=payload, previous_hash=previous)
        row["hash"] = hmac.new(self.key, canonical(row).encode(), hashlib.sha256).hexdigest()
        conn.execute(audit.insert().values(**row))
        conn.execute(outbox.insert().values(id=identifier(), organisation_id=tenant, at=row["at"], topic=action, payload={"audit_id": row["id"], "sequence": sequence}))
        return row

    def verify_audit(self, tenant):
        with self.engine.connect() as conn:
            rows = conn.execute(select(audit).where(audit.c.organisation_id == tenant).order_by(audit.c.sequence)).mappings().all()
            expected_count = conn.execute(select(organisations.c.audit_seq).where(organisations.c.id == tenant)).scalar_one()
        previous = "0" * 64
        for sequence, item in enumerate(rows, 1):
            row = dict(item)
            claimed = row.pop("hash")
            actual = hmac.new(self.key, canonical(row).encode(), hashlib.sha256).hexdigest()
            if row["sequence"] != sequence or row["previous_hash"] != previous or not hmac.compare_digest(actual, claimed):
                return {"valid": False, "failed_sequence": sequence}
            previous = claimed
        return {"valid": len(rows) == expected_count, "count": len(rows), "head": previous, "external_checkpoint_required": True}

    def snapshot(self, conn, row):
        conn.execute(versions.insert().values(id=identifier(), organisation_id=row["organisation_id"], record_id=row["id"], version=row["version"], snapshot=row))


def local_store() -> Store:
    runtime = Path(os.environ.get("AIRSPACE_RUNTIME", "runtime"))
    runtime.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("AIRSPACE_AUDIT_KEY")
    if key:
        material = key.encode()
    else:
        key_path = runtime / "audit.key"
        if not key_path.exists():
            # Exclusive create avoids silently changing an existing deployment key.
            with key_path.open("xb") as file:
                file.write(secrets.token_bytes(48))
            try:
                key_path.chmod(0o600)
            except OSError:
                pass
        material = key_path.read_bytes()
    return Store(os.environ.get("AIRSPACE_DATABASE_URL", f"sqlite:///{(runtime / 'airspace.db').as_posix()}"), material)
