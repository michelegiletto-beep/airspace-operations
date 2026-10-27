"""Download and parse EASA's official eRules XML archive without executing it.

Retains exact source metadata and local snapshot anchors. Legal material, AMC
and guidance remain separate. An eRules consolidation is not an authentic OJ
publication; date-specific applicability still requires regulatory review.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import subprocess
import os
import tempfile
from contextlib import contextmanager
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from airspace.regulatory import safe_fetch, utc_now

ER = "{http://www.easa.europa.eu/erules-export}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ATTRIBUTION = "Source: European Union Aviation Safety Agency, Easy Access Rules. Copyright EASA 2003-2026. EU legal documents: copyright European Union 1998-2026."


def atomic_json(path: Path, value):
    temporary=path.with_name(path.name+".tmp-"+os.urandom(8).hex())
    try:
        with temporary.open("x",encoding="utf-8") as file:
            json.dump(value,file,indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def corpus_lock(folder: Path):
    """OS-released file lock prevents lost corpus-index updates after crashes."""
    with (folder/".corpus.lock").open("a+b") as lock:
        lock.seek(0,2)
        if lock.tell()==0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name=="nt":
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name=="nt":
                msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


def parse_archive(data: bytes, source_id: str, url: str, edition: str) -> tuple[list[dict], dict]:
    with ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or not entries[0].filename.lower().endswith(".xml"):
            raise ValueError("Only a single reviewed XML payload is accepted")
        item = entries[0]
        if item.file_size > 25 * 1024 * 1024 or item.compress_size < 1 or item.file_size / item.compress_size > 100:
            raise ValueError("Archive exceeds extraction bounds")
        xml = archive.read(item)
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("DTD and XML entities are prohibited")
    root = ET.fromstring(xml)
    metadata = {t.get("sdt-id"): t.attrib for t in root.iter(ER + "topic")}
    digest = hashlib.sha256(data).hexdigest()
    xml_digest = hashlib.sha256(xml).hexdigest()
    result, seen = [], set()
    today = datetime.now(timezone.utc).date()
    for section in root.iter(W + "sdt"):
        properties = section.find(W + "sdtPr")
        ident = properties.find(W + "id") if properties is not None else None
        meta = metadata.get(ident.get(W + "val")) if ident is not None else None
        if not meta:
            continue
        content_type = meta.get("TypeOfContent", "")
        status = "binding_legislation" if content_type.startswith(("IR ", "DR ")) else "amc" if content_type.startswith("AMC") else "guidance" if content_type.startswith("GM") else None
        if not status:
            continue
        source_family = "eu-2021-664" if "uspace" in source_id else "eu-2019-945" if content_type.startswith("DR ") else "eu-2019-947"
        content = section.find(W + "sdtContent")
        if content is None:
            continue
        structures = []
        for child in content:
            if child.tag == W + "p":
                structures.append(("paragraph", child))
            elif child.tag == W + "tbl":
                structures.extend(("table_row", row) for row in child.iter(W + "tr"))
        for index, (kind, element) in enumerate(structures):
            if kind == "table_row":
                text = " | ".join("".join(t.text or "" for t in cell.iter(W + "t")) for cell in element.findall(W + "tc"))
            else:
                text = "".join(t.text or "" for t in element.iter(W + "t"))
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue
            # Equal text in different rows/paragraphs is still a distinct source
            # location. Never remove repeated table values or threshold rows.
            key = (source_family, meta.get("ERulesId"), index, text)
            if key in seen:
                continue
            seen.add(key)
            ident = f"{meta['ERulesId']}:b{index+1:04d}"
            result.append({"id": f"{source_id}:{digest[:12]}:{ident}", "source_id": source_id,
                           "source_family": source_family, "document_version": edition, "source_checksum": digest,
                           "xml_checksum": xml_digest, "anchor": ident, "anchor_kind": "local_eRules_section_and_block",
                           "source_url": url, "title": meta.get("source-title", ""), "text": text, "structure": kind,
                           "jurisdiction": "EU", "language": "en", "legal_status": status, "organisation_id": None,
                           "valid_from": today.isoformat(), "valid_to": (today + timedelta(days=1)).isoformat(),
                           "temporal_status": "snapshot_only", "retrieved_at": utc_now(),
                           "methodology": ("SORA 2.0" if "AMC1bis Article 11" in (meta.get("source-title", "") + meta.get("ParentIR", ""))
                                           else "SORA 2.5" if "AMC1 Article 11 Rules for conducting an operational risk assessment" in (meta.get("source-title", "") + meta.get("ParentIR", ""))
                                           else None),
                           "upstream_metadata": meta, "attribution": ATTRIBUTION,
                           "extraction_warning": "Consolidated reference text. Local anchor resolves in preserved XML; article applicability metadata may contain several dates. No earlier or future temporal applicability is inferred.",
                           "licence": {"status": "Reproduction authorised with source acknowledgement, except otherwise stated", "url": "https://www.easa.europa.eu/en/copyright-disclaimer", "redistribution": "cleared_text_only", "attribution": ATTRIBUTION}})
    manifest = {"id": source_id, "source_url": url, "edition": edition, "retrieved_at": utc_now(), "archive_checksum": digest,
                "xml_checksum": xml_digest, "archive_bytes": len(data), "xml_bytes": len(xml), "passage_count": len(result),
                "status": "Retrieved and parsed; requires domain and source-currentness review", "attribution": ATTRIBUTION,
                "rights_evidence": "https://www.easa.europa.eu/en/copyright-disclaimer", "parser": "stdlib XML; DTD/entity rejection; archive bounds; no code execution",
                "temporal_scope": "Retrieval date snapshot only; not an assertion of historical or future applicability",
                "amendment_relationships": sorted({p['upstream_metadata'].get('RegulatorySource', '') for p in result})}
    return result, manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="https://www.easa.europa.eu/en/downloads/137111/en")
    p.add_argument("--source-id", default="easa-uas-xml-2026")
    p.add_argument("--edition", default="June 2026")
    p.add_argument("--parse-file",type=Path,help=argparse.SUPPRESS)
    p.add_argument("--report-file",type=Path,help=argparse.SUPPRESS)
    args = p.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}",args.source_id):
        raise ValueError("Unsafe source identifier")
    if args.parse_file:
        if not args.report_file or args.parse_file.stat().st_size>25*1024*1024:
            raise ValueError("Parser input/output contract is invalid")
        rows,manifest=parse_archive(args.parse_file.read_bytes(),args.source_id,args.url,args.edition)
        args.report_file.write_text(json.dumps({"rows":rows,"manifest":manifest}),encoding="utf-8")
        return
    data, headers = safe_fetch(args.url)
    downloaded_at=utc_now()
    # Separate non-executing parser process. Containers additionally enforce
    # network/CPU/memory restrictions; process isolation is not an OS sandbox.
    with tempfile.TemporaryDirectory(prefix="airspace-regulatory-parser-") as temporary:
        raw=Path(temporary)/"source.zip"
        report=Path(temporary)/"parsed.json"
        raw.write_bytes(data)
        process=subprocess.run([sys.executable,"-I",str(Path(__file__).resolve()),"--parse-file",str(raw),"--report-file",str(report),"--url",args.url,"--source-id",args.source_id,"--edition",args.edition],capture_output=True,timeout=45,env={"PATH":os.environ.get("PATH",""),"SYSTEMROOT":os.environ.get("SYSTEMROOT","")})
        if process.returncode or not report.exists() or report.stat().st_size>70*1024*1024:
            raise ValueError("Isolated eRules parser rejected the document")
        parsed=json.loads(report.read_text(encoding="utf-8"))
        rows,manifest=parsed["rows"],parsed["manifest"]
    manifest["parsed_at"]=manifest["retrieved_at"]
    manifest["retrieved_at"]=downloaded_at
    snapshot_day=datetime.fromisoformat(downloaded_at).date()
    for row in rows:
        row["parsed_at"]=row["retrieved_at"]
        row["retrieved_at"]=downloaded_at
        row["valid_from"]=snapshot_day.isoformat()
        row["valid_to"]=(snapshot_day+timedelta(days=1)).isoformat()
    folder = ROOT / "sources" / "snapshots" / args.source_id / manifest["archive_checksum"]
    folder.mkdir(parents=True, exist_ok=True)
    existing_manifest=folder/"manifest.json"
    if existing_manifest.exists():
        old=json.loads(existing_manifest.read_text(encoding="utf-8"))
        manifest["first_retrieved_at"]=old.get("first_retrieved_at",old.get("retrieved_at"))
    else:
        manifest["first_retrieved_at"]=manifest["retrieved_at"]
    manifest["last_successful_check"]=manifest["retrieved_at"]
    (folder / "original.zip").write_bytes(data)
    atomic_json(folder/"passages.json",rows)
    atomic_json(folder/"manifest.json",manifest)
    corpus_path = ROOT / "sources" / "corpus.json"
    with corpus_lock(corpus_path.parent):
        existing = json.loads(corpus_path.read_text(encoding="utf-8")) if corpus_path.exists() else []
        atomic_json(corpus_path,[r for r in existing if r["source_id"] != args.source_id] + rows)
    checks=ROOT/"sources"/"checks"
    checks.mkdir(exist_ok=True)
    stamp=manifest["retrieved_at"].replace(":","-")
    (checks/(args.source_id+"-"+stamp+".json")).write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
