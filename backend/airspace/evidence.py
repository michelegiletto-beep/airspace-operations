"""Content-addressed tenant evidence and escaped controlled reports."""
import base64
import binascii
import hashlib
import html
import io
import json
import os
import zipfile
from pathlib import Path
from fastapi import Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from .identity import require_role
from .storage import records, now


class Attachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_name: str = Field(min_length=1, max_length=200)
    media_type: str
    content_base64: str = Field(max_length=1_500_000)
    expected_version: int = Field(ge=1)


def blob_path(tenant, checksum):
    # Both values are server-issued identifiers, never source-supplied paths.
    if not all(c in "0123456789abcdef" for c in checksum) or len(checksum) != 64:
        raise ValueError("Invalid content digest")
    if "/" in tenant or "\\" in tenant or ".." in tenant:
        raise ValueError("Invalid tenant identifier")
    return Path(os.getenv("AIRSPACE_RUNTIME", "runtime")) / "objects" / tenant / checksum


def report_html(package):
    escape = lambda value: html.escape(str(value), quote=True)
    case = package["case"]
    rows = "".join(f"<tr><td>{escape(e['title'])}</td><td>{escape(e['version'])}</td><td>{escape(e['data'].get('evidence_type','Not recorded'))}</td><td><code>{escape(e['data'].get('checksum','Missing'))}</code></td><td>{escape(e['data'].get('provenance','Missing'))}</td></tr>" for e in package["evidence"])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>{escape(case['title'])}</title><style>body{{font:14px system-ui;max-width:1100px;margin:40px auto;color:#152331}}h1{{font-size:26px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #c8cfd5;padding:8px;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.boundary{{border:1px solid #9c7738;padding:15px}}code{{overflow-wrap:anywhere}}</style><header>SYSTEM LAB · AIRSPACE OPERATIONS</header><h1>{escape(case['title'])}</h1><p>Controlled case record · Revision {escape(case['version'])} · {escape(case['status'])}</p><p class="boundary">Internal evidence package. No submission, signature, authority authorisation or operational acceptance is implied.</p><dl><dt>Generated UTC</dt><dd>{escape(package['generated_at'])}</dd><dt>Accountable exporting actor</dt><dd>{escape(package['accountable_actor'])}</dd><dt>Input digest</dt><dd><code>{escape(package['sha256'])}</code></dd></dl><h2>Proposed operation and evidence context</h2><pre>{escape(json.dumps(case['data'],indent=2))}</pre><h2>Evidence register</h2><table><thead><tr><th>Evidence</th><th>Revision</th><th>Type</th><th>Digest</th><th>Provenance</th></tr></thead><tbody>{rows}</tbody></table><h2>Unresolved requirements</h2><pre>{escape(json.dumps(package['missing_inputs'],indent=2))}</pre><footer>Software {escape(package['software_version'])} · Rule {escape(package['rule_version'])}</footer></html>'''


def install_evidence_routes(app, store, current):
    from .api import row_get, lock_tenant

    @app.put("/api/v1/evidence/{item_id}/content")
    def upload(item_id: str, payload: Attachment, user=Depends(current)):
        require_role(user, {"regulatory", "fleet_manager", "planner"})
        if payload.media_type not in {"application/pdf", "application/xml", "text/plain", "text/html", "application/json", "text/csv"}:
            raise HTTPException(422, "Evidence format is not permitted")
        if Path(payload.original_name).name != payload.original_name or any(x in payload.original_name for x in ("/", "\\", "\x00", "\r", "\n")):
            raise HTTPException(422, "Use a plain attachment filename")
        try:
            content = base64.b64decode(payload.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(422, "Attachment must be valid base64")
        if not content or len(content) > 1_000_000:
            raise HTTPException(413, "Local evidence upload supports files up to 1 MB")
        digest = hashlib.sha256(content).hexdigest()
        target = blob_path(user["organisation_id"], digest)
        with store.engine.begin() as conn:
            lock_tenant(conn, user["organisation_id"])
            row = row_get(conn, user["organisation_id"], "evidence", item_id)
            if row["version"] != payload.expected_version or row["status"] not in {"Draft", "Missing Evidence"}:
                raise HTTPException(409, "Create an editable revision before attaching evidence")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                try:
                    with target.open("xb") as output:
                        output.write(content)
                except FileExistsError:
                    pass
            row.update(data={**{k:v for k,v in row["data"].items() if not k.startswith("_")}, "checksum": digest, "attachment": {"original_name": payload.original_name, "media_type": payload.media_type, "bytes": len(content), "sha256": digest}, "_prepared_by": user["id"]}, status="Draft", version=row["version"] + 1, updated_at=now())
            changed = conn.execute(update(records).where(records.c.id == item_id, records.c.organisation_id == user["organisation_id"], records.c.version == payload.expected_version).values(**row))
            if changed.rowcount != 1:
                raise HTTPException(409, "Concurrent attachment rejected")
            store.snapshot(conn, row)
            store.append_audit(conn, user["organisation_id"], user["id"], "evidence.attached", {"record_id": item_id, "sha256": digest, "version": row["version"], "bytes": len(content)})
        return row

    @app.get("/api/v1/evidence/{item_id}/content")
    def download(item_id: str, user=Depends(current)):
        with store.engine.connect() as conn:
            row = row_get(conn, user["organisation_id"], "evidence", item_id)
        attachment = row["data"].get("attachment")
        if not attachment:
            raise HTTPException(404, "No attachment recorded")
        path = blob_path(user["organisation_id"], attachment["sha256"])
        if not path.is_file():
            raise HTTPException(503, "Evidence object is unavailable; restore from backup")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != attachment["sha256"]:
            raise HTTPException(409, "Evidence integrity check failed")
        return Response(data, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="evidence-{item_id}.bin"'})
