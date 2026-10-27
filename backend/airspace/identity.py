"""Local identity and optional explicitly configured OIDC validation."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from .storage import users, sessions, organisations, identifier, now

ROLES = {"administrator", "regulatory", "reviewer", "planner", "pilot", "fleet_manager", "incident_coordinator", "analyst", "viewer"}


def password_hash(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
    return f"scrypt${salt.hex()}${digest}"


def check_password(password, encoded):
    try:
        method, salt, digest = encoded.split("$")
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return method == "scrypt" and hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def provision(store, organisation, email, role, password, organisation_id=None):
    if role not in ROLES:
        raise ValueError("Unknown role")
    tenant = organisation_id or identifier()
    user_id = identifier()
    with store.engine.begin() as conn:
        if not conn.execute(select(organisations).where(organisations.c.id == tenant)).first():
            conn.execute(organisations.insert().values(id=tenant, name=organisation, audit_seq=0))
        conn.execute(users.insert().values(id=user_id, organisation_id=tenant, email=email.lower(), role=role, password_hash=password_hash(password), disabled=0))
        store.append_audit(conn, tenant, "local-administrator", "identity.provision", {"user_id": user_id, "role": role})
    return {"id": user_id, "organisation_id": tenant, "email": email.lower(), "role": role}


def login(store, email, password):
    with store.engine.begin() as conn:
        row = conn.execute(select(users).where(users.c.email == email.lower(), users.c.disabled == 0)).mappings().first()
        encoded = row["password_hash"] if row else "scrypt$00000000000000000000000000000000$" + "0" * 128
        valid = check_password(password, encoded)
        if not row or not valid:
            raise HTTPException(401, "Invalid credentials")
        token = secrets.token_urlsafe(48)
        expiry = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
        conn.execute(sessions.insert().values(digest=hashlib.sha256(token.encode()).hexdigest(), user_id=row["id"], expires_at=expiry))
        store.append_audit(conn, row["organisation_id"], row["id"], "identity.login", {})
    return {"token": token, "expires_at": expiry, "user": public_user(row)}


def public_user(row):
    return {k: row[k] for k in ("id", "organisation_id", "email", "role")}


def authenticate(store, token):
    if not token:
        raise HTTPException(401, "Authentication required")
    with store.engine.connect() as conn:
        row = conn.execute(select(users).join(sessions, sessions.c.user_id == users.c.id).where(sessions.c.digest == hashlib.sha256(token.encode()).hexdigest(), sessions.c.expires_at > now(), users.c.disabled == 0)).mappings().first()
    if row:
        return public_user(row)
    issuer = os.environ.get("AIRSPACE_OIDC_ISSUER")
    if issuer:
        import jwt
        # URL comes only from administrator configuration, never a token-controlled jku.
        jwks = os.environ["AIRSPACE_OIDC_JWKS_URL"]
        audience = os.environ["AIRSPACE_OIDC_AUDIENCE"]
        if not issuer.startswith("https://") or not jwks.startswith("https://"):
            raise HTTPException(503, "OIDC requires HTTPS configuration")
        try:
            key = jwt.PyJWKClient(jwks).get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=audience, issuer=issuer, options={"require": ["exp", "iss", "aud", "sub"]})
            mapping = os.environ.get("AIRSPACE_OIDC_SUBJECTS", "{}")
            import json
            user_id = json.loads(mapping).get(claims["sub"])
            with store.engine.connect() as conn:
                row = conn.execute(select(users).where(users.c.id == user_id, users.c.disabled == 0)).mappings().first()
            if row:
                return public_user(row)
        except Exception:
            pass
    raise HTTPException(401, "Expired or invalid session")


def require_role(user, allowed):
    if user["role"] not in allowed:
        raise HTTPException(403, "This role cannot perform this action")
