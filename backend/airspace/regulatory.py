"""Versioned, source-grounded regulatory ingestion and conservative retrieval.

This module never interprets retrieved text as executable instructions or grants
an operating permission. Parsing runs in a separate, bounded process; the
parsers do not evaluate scripts, XML entities, macros, or document code.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import tempfile
from contextlib import contextmanager
from collections import Counter
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

RULE_VERSION = "regulatory-retrieval-1.0.0"
APPROVED_HOSTS = frozenset({
    "eur-lex.europa.eu", "www.easa.europa.eu", "dac.gouvernement.lu",
    "www.enac.gov.it", "www.eurocontrol.int", "publications.europa.eu",
})
EU_COUNTRIES = frozenset("AT BE BG HR CY CZ DE DK EE ES FI FR GR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split())
ALLOWED_STATUSES = frozenset({"binding_legislation", "amc", "guidance", "national_procedure", "official_information"})
TOKEN = re.compile(r"[a-z0-9]+", re.I)
STOP = frozenset("a an the of and or is are for to in on it what which how can does do i we as be by at this that with from about".split())
MAX_BYTES = 25 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes):
    temporary = path.with_name(path.name + ".tmp-" + os.urandom(8).hex())
    try:
        with temporary.open("xb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_url(url: str, *, resolve: bool = True) -> tuple[str, int, str, str | None]:
    """Reject private endpoints, redirects, userinfo, alternate ports and proxies.

    The returned address is pinned during TLS connection, so a DNS change
    between validation and connection cannot redirect a download to a private IP.
    """
    if any(ord(c) < 33 for c in url) or "\\" in url:
        raise ValueError("URL contains unsafe characters")
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in APPROVED_HOSTS or p.username or p.password:
        raise ValueError("Only registered official HTTPS hosts are permitted")
    if p.port not in (None, 443) or p.fragment:
        raise ValueError("Only HTTPS port 443 and fragment-free download URLs are permitted")
    path = p.path or "/"
    if p.query:
        path += "?" + p.query
    address = None
    if resolve:
        addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("DNS resolved to a non-public address")
        address = addresses[0][4][0]
    return p.hostname, 443, path, address


class _PinnedTLS(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, timeout: int):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self.public_address = address

    def connect(self):
        raw = socket.create_connection((self.public_address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def safe_fetch(url: str, max_bytes: int = MAX_BYTES) -> tuple[bytes, dict]:
    if not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("Download limit must be between 1 and 25 MiB")
    host, _, path, address = validate_url(url)
    conn = _PinnedTLS(host, address, 25)
    deadline = time.monotonic() + 60
    try:
        conn.request("GET", path, headers={
            "User-Agent": "SystemLabAirspaceOperations/0.1 regulatory-research (bounded downloader)",
            "Accept": "text/html,application/xml,text/xml,application/zip,application/pdf",
            "Accept-Encoding": "identity",
        })
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError(f"Upstream returned HTTP {response.status}; redirects are never followed")
        headers = {k.lower(): v for k, v in response.getheaders()}
        if headers.get("content-encoding", "identity") not in ("identity", ""):
            raise ValueError("Compressed HTTP responses are not accepted")
        length = headers.get("content-length")
        if length and int(length) > max_bytes:
            raise ValueError("Document exceeds download limit")
        chunks, total = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("Document download exceeded the 60-second total budget")
            if conn.sock:
                conn.sock.settimeout(min(25,remaining))
            chunk = response.read1(min(65536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Document exceeds download limit")
        data = b"".join(chunks)
        if not data:
            raise ValueError("Upstream returned an empty document")
        if b"verify that you're not a robot" in data.lower() or b"captcha" in data.lower()[:10000]:
            raise ValueError("Upstream returned a challenge page, not a regulatory document")
        return data, headers
    finally:
        conn.close()


class _Blocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.active, self.parts = [], None, []
        self.stack, self.ignore, self.heading = [], 0, ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append((tag, attrs.get("id")))
        if tag in {"script", "style", "noscript", "nav", "footer", "header", "form"}:
            self.ignore += 1
        if not self.ignore and tag in {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            if self.active:
                self._finish()
            self.active = (tag, next((a for _, a in reversed(self.stack) if a), None))
            self.parts = []
        if tag in {"td", "th"} and self.active:
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if self.active and self.active[0] == tag:
            self._finish()
        if tag in {"script", "style", "noscript", "nav", "footer", "header", "form"}:
            self.ignore = max(0, self.ignore - 1)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        if self.active and not self.ignore:
            self.parts.append(data)

    def _finish(self):
        text = re.sub(r"\s+", " ", "".join(self.parts)).strip(" |")
        tag, anchor = self.active
        if tag.startswith("h"):
            self.heading = text
        if len(text) >= 12:
            self.blocks.append({"text": text, "html_id": anchor, "heading": self.heading, "kind": "table_row" if tag == "tr" else tag})
        self.active, self.parts = None, []


def extract_document(data: bytes, content_type: str = "text/html") -> list[dict]:
    """Non-executing parser. Keep structural blocks and identifiers, including tables."""
    if len(data) > MAX_BYTES:
        raise ValueError("Document exceeds parser limit")
    if data.startswith(b"%PDF") or "pdf" in content_type or data.startswith(b"PK"):
        raise ValueError("PDF/ZIP requires a reviewed format-specific import; it is not silently flattened")
    text = data.decode("utf-8-sig", errors="strict")
    if "<!ENTITY" in text.upper() or "<!DOCTYPE" in text.upper() and "xml" in content_type:
        raise ValueError("XML DTD and entities are prohibited")
    if "xml" in content_type and "html" not in content_type:
        root = ET.fromstring(text)
        blocks = []
        for node in root.iter():
            tag = node.tag.split("}")[-1].lower()
            if tag in {"p", "paragraph", "row", "tr", "title", "heading"}:
                value = re.sub(r"\s+", " ", " ".join(node.itertext())).strip()
                if len(value) >= 12:
                    blocks.append({"text": value, "html_id": node.get("id"), "heading": "", "kind": tag})
        return blocks
    parser = _Blocks()
    parser.feed(text)
    if parser.active:
        parser._finish()
    return parser.blocks


def isolated_extract(path: Path, content_type: str) -> list[dict]:
    """Bound execution time and output in a fresh isolated Python interpreter.

    This is parser-process isolation, not an OS sandbox. Deployment workers should
    additionally disable network and mount sources read-only, as documented.
    """
    process = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).resolve()), "--parse", str(path.resolve()), content_type],
        capture_output=True, timeout=30, check=False, env={"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")},
    )
    if process.returncode or len(process.stdout) > MAX_BYTES * 2:
        raise ValueError("Isolated parser rejected the document")
    return json.loads(process.stdout)


def ingest_source(entry: dict, storage_dir: str | Path, *, data: bytes | None = None, content_type: str | None = None) -> dict:
    """Create content-addressed raw snapshots and append-only version manifests.

    Optional bytes are for a controlled manual import or an isolated software
    test. Callers must record their provenance; no live connection is implied.
    """
    required = {"id", "url", "issuer", "jurisdiction", "language", "legal_status", "version", "licence"}
    if required - entry.keys():
        raise ValueError("Source metadata is incomplete: " + ", ".join(sorted(required - entry.keys())))
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}", entry["id"]):
        raise ValueError("Unsafe source identifier")
    validate_url(entry["url"], resolve=False)
    headers = {}
    if data is None:
        data, headers = safe_fetch(entry["url"])
        import_mode = "official_https_download"
    else:
        import_mode = "controlled_manual_import"
    digest = sha256(data)
    root = Path(storage_dir).resolve()
    folder = (root / entry["id"] / digest).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("Source storage path escaped the configured root")
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / "original.bin"
    _atomic_write(raw,data)
    mime = content_type or headers.get("content-type", "text/html").split(";")[0]
    blocks = isolated_extract(raw, mime)
    if not blocks:
        raise ValueError("No structured passages extracted; source requires review")
    passages = []
    for i, block in enumerate(blocks):
        anchor = block.get("html_id")
        passage_id = f"{entry['id']}:{digest[:12]}:p{i+1:05d}"
        passages.append({
            **{k: entry.get(k) for k in ("jurisdiction", "language", "legal_status", "valid_from", "valid_to", "organisation_id", "temporal_status", "methodology")},
            "id": passage_id, "source_id": entry["id"], "document_version": entry["version"],
            "source_checksum": digest, "anchor": anchor or f"p{i+1:05d}",
            "source_url": entry["url"] + ("#" + anchor if anchor else ""),
            "anchor_kind": "original_html_id" if anchor else "local_extraction_block",
            "title": block.get("heading") or entry.get("title", entry["id"]), "text": block["text"],
            "structure": block["kind"], "extraction_warning": None if anchor else "No upstream block identifier; resolve by snapshot checksum and local block ID",
            "retrieved_at": utc_now(), "licence": entry["licence"],
        })
    _atomic_write(folder / "passages.json",json.dumps(passages, ensure_ascii=False, indent=2).encode("utf-8"))
    result = {**entry, "checksum": digest, "retrieved_at": utc_now(), "content_type": mime,
              "raw_path": str(raw), "text_path": str(folder / "passages.json"),
              "document_version": entry["version"], "import_mode": import_mode,
              "status": "Ingested — Requires Domain Review", "passage_count": len(passages)}
    _atomic_write(folder / "manifest.json",json.dumps(result, indent=2).encode("utf-8"))
    return {**result, "passages": passages}


def _tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


def filter_passages(passages: list[dict], jurisdiction: str, on_date: str, organisation_id: str | None = None, statuses=None, methodology: str | None = None) -> list[dict]:
    """Apply all tenant, legal-status, jurisdiction and temporal filters before rank."""
    day = date.fromisoformat(on_date)
    if not jurisdiction:
        raise ValueError("Jurisdiction is required")
    allowed = set(statuses or ALLOWED_STATUSES)
    output = []
    for p in passages:
        if p.get("organisation_id") is not None and p.get("organisation_id") != organisation_id:
            continue
        scope = p.get("jurisdiction")
        if scope != jurisdiction and not (scope == "EU" and jurisdiction in EU_COUNTRIES):
            continue
        if p.get("legal_status") not in allowed:
            continue
        if methodology and p.get("methodology") not in (None, methodology):
            continue
        if not p.get("valid_from") or p.get("temporal_status") == "unverified":
            continue
        if date.fromisoformat(p["valid_from"]) > day:
            continue
        if p.get("valid_to") and day >= date.fromisoformat(p["valid_to"]):
            continue
        if p.get("superseded") and not p.get("valid_to"):
            continue
        output.append(p)
    return output


def retrieve(passages: list[dict], query: str, jurisdiction: str, on_date: str, organisation_id: str | None = None, limit: int = 5, *, encoder=None, reranker=None, tenant_id: str | None = None, methodology: str | None = None, accountable_actor: str | None = None) -> dict:
    if not query.strip() or not 1 <= limit <= 20:
        raise ValueError("A question and a result limit of 1–20 are required")
    if organisation_id is None:
        organisation_id = tenant_id
    rows = filter_passages(passages, jurisdiction, on_date, organisation_id, methodology=methodology)
    query_tokens = Counter(_tokens(query))
    lexical = []
    docs = [_tokens(p["text"]) for p in rows]
    n, avg = len(rows), sum(map(len, docs)) / max(1, len(rows))
    dfs = Counter(t for doc in docs for t in set(doc))
    for p, doc in zip(rows, docs):
        counts = Counter(doc)
        score = 0.0
        for token in query_tokens:
            tf = counts[token]
            if tf:
                idf = math.log(1 + (n - dfs[token] + 0.5) / (dfs[token] + 0.5))
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(doc) / max(avg, 1)))
        lexical.append(score)
    semantic, failures = [0.0] * len(rows), []
    engine = "BM25"
    if encoder and rows:
        try:
            vectors = encoder.encode([query] + [p["text"] for p in rows])
            semantic = [float(sum(a * b for a, b in zip(vectors[0], vector))) for vector in vectors[1:]]
            engine += " + pretrained neural embeddings"
        except Exception as exc:
            failures.append("Embedding model unavailable: " + type(exc).__name__)
    lex_order = sorted(range(len(rows)), key=lambda i: lexical[i], reverse=True)
    sem_order = sorted(range(len(rows)), key=lambda i: semantic[i], reverse=True)
    lex_rank, sem_rank = {i: r for r, i in enumerate(lex_order)}, {i: r for r, i in enumerate(sem_order)}
    selected = [i for i in lex_order if lexical[i] > 0]
    if encoder and not failures:
        selected = list(set(selected[:40]) | {i for i in sem_order[:40] if semantic[i] >= 0.25})
    selected.sort(key=lambda i: 1 / (60 + lex_rank[i]) + (1 / (60 + sem_rank[i]) if encoder and not failures else 0), reverse=True)
    rerank_scores = {}
    if reranker and selected:
        try:
            subset = selected[:40]
            scores = reranker.rank(query, [rows[i]["text"] for i in subset])
            rerank_scores = dict(zip(subset, map(float, scores)))
            selected = sorted(subset, key=lambda i: rerank_scores[i], reverse=True)
            engine += " + neural cross-encoder reranking"
        except Exception as exc:
            failures.append("Reranker unavailable: " + type(exc).__name__)
    results = [{**rows[i], "lexical_score": round(lexical[i], 6), "neural_similarity": round(semantic[i], 6) if encoder and not failures else None,
                "reranker_score": rerank_scores.get(i)} for i in selected[:limit]]
    snapshot = sha256(json.dumps({"question":query,"jurisdiction":jurisdiction,"operation_date":on_date,"organisation_id":organisation_id,"methodology":methodology,
                                  "passages":sorted((p["id"], p.get("source_checksum"), sha256(p["text"].encode())) for p in rows)}, sort_keys=True).encode())
    return {"results": results, "abstained": not results, "missing_inputs": [] if rows else ["No date-verified source passages in the permitted jurisdiction and organisation scope"],
            "question": query, "jurisdiction": jurisdiction, "operation_date": on_date, "engine": engine, "failures": failures,
            "provenance": {"input_snapshot": snapshot, "rule_version": RULE_VERSION, "model_version": getattr(encoder, "version", None), "reranker_version": getattr(reranker,"version",None), "timestamp": utc_now(), "accountable_actor":accountable_actor,
                           "source_versions": sorted({(r["source_id"], r["document_version"]) for r in results})}}


def source_answer(passages: list[dict], query: str, jurisdiction: str, on_date: str, organisation_id=None, **kwargs) -> dict:
    result = retrieve(passages, query, jurisdiction, on_date, organisation_id, **kwargs)
    editions = sorted({r["methodology"] for r in result["results"] if r.get("methodology")})
    if len(editions) > 1:
        result["missing_inputs"].append("Choose and review the case's SORA methodology edition; retrieved editions must not be combined")
    return {**result, "answer_status": "Evidence retrieved — interpretation required" if result["results"] else "Abstained — insufficient source evidence",
            "supporting_provisions": [{"quotation": p["text"], "citation": {k: p[k] for k in ("source_id", "document_version", "source_checksum", "anchor", "anchor_kind", "source_url")}} for p in result["results"]],
            "conclusion": None, "machine_interpretation": None, "reviewer_approved_interpretation": None,
            "unresolved_uncertainties": ["Retrieved provisions do not establish applicability to a complete operation. An accountable regulatory reviewer must assess context and coverage."],
            "required_review": True, "methodologies_in_results": editions, "conclusion_abstained": True,
            "operational_context": {"jurisdiction": jurisdiction, "operation_date": on_date, "methodology": kwargs.get("methodology")}}


def change_impact(previous: dict, current: dict, dependencies: list[dict]) -> dict:
    """Produce owner-assigned review tasks; never overwrite approved records."""
    if previous.get("id") != current.get("id"):
        raise ValueError("Only versions of the same source can be compared")
    changed = previous.get("checksum") != current.get("checksum")
    tasks = [{"record_id": d["record_id"], "record_type": d["record_type"], "owner_id": d.get("owner_id"),
              "status": "Missing Owner" if not d.get("owner_id") else "Under Review", "reason": "Source version changed; applicability and evidence require review",
              "previous_checksum": previous.get("checksum"), "current_checksum": current.get("checksum")}
             for d in dependencies if changed and previous["id"] in d.get("source_ids", [])]
    return {"changed": changed, "tasks": tasks, "existing_decisions_modified": False, "rule_version": RULE_VERSION, "timestamp": utc_now()}


@contextmanager
def _monitor_lock(folder: Path):
    """OS releases the lock on worker failure, preserving resumable checks."""
    with (folder/".monitor.lock").open("a+b") as lock:
        lock.seek(0,2)
        if lock.tell()==0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        deadline=time.monotonic()+10
        while True:
            try:
                if os.name=="nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except (OSError,BlockingIOError):
                if time.monotonic()>=deadline:
                    raise TimeoutError("Source check is already running; bounded lock wait expired")
                time.sleep(0.05)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name=="nt":
                msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


def _registered_source(source_id: str) -> dict:
    if not isinstance(source_id,str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}",source_id):
        raise ValueError("A registered source identifier is required")
    catalogue_path=Path(__file__).resolve().parents[2]/"sources"/"catalogue.json"
    catalogue=json.loads(catalogue_path.read_text(encoding="utf-8"))
    matches=[s for s in catalogue["sources"] if s["id"]==source_id]
    if len(matches)!=1:
        raise ValueError("Source identifier is not uniquely registered")
    entry=dict(matches[0])
    validate_url(entry["url"],resolve=False)
    return entry


def _isolated_easa_snapshot(data: bytes, entry: dict, folder: Path, downloaded_at: str) -> dict:
    script=Path(__file__).resolve().parents[2]/"scripts"/"import_easa_xml.py"
    if entry["id"] not in {"easa-uas-xml-2026","easa-uspace-xml-2024"} or not script.is_file():
        raise ValueError("No reviewed archive parser is registered for this source")
    digest=sha256(data)
    snapshot=(folder/digest).resolve()
    if not snapshot.is_relative_to(folder):
        raise ValueError("Archive storage path escaped source scope")
    snapshot.mkdir(parents=True,exist_ok=True)
    raw=snapshot/"original.zip"
    _atomic_write(raw,data)
    with tempfile.TemporaryDirectory(prefix="parser-",dir=folder) as temporary:
        report=Path(temporary)/"result.json"
        parsed=subprocess.run([sys.executable,"-I",str(script),"--parse-file",str(raw),"--report-file",str(report),"--url",entry["url"],"--source-id",entry["id"],"--edition",entry["version"]],capture_output=True,timeout=45,
                              env={"PATH":os.environ.get("PATH",""),"SYSTEMROOT":os.environ.get("SYSTEMROOT","")})
        if parsed.returncode or not report.is_file() or report.stat().st_size>70*1024*1024:
            raise ValueError("Isolated archive parser rejected source; preserved bytes require review")
        output=json.loads(report.read_text(encoding="utf-8"))
    manifest={**entry,**output["manifest"],"checksum":digest,"retrieved_at":downloaded_at,"organisation_id":entry.get("organisation_id"),
              "raw_path":str(raw),"text_path":str(snapshot/"passages.json"),"document_version":entry["version"],
              "import_mode":"official_https_download","status":"Ingested — Requires Domain Review"}
    rows=output["rows"]
    for row in rows:
        row["organisation_id"]=entry.get("organisation_id")
        row["retrieved_at"]=downloaded_at
    _atomic_write(snapshot/"passages.json",json.dumps(rows,indent=2).encode())
    _atomic_write(snapshot/"manifest.json",json.dumps(manifest,indent=2).encode())
    return {**manifest,"passages":rows}


def monitor_registered_source(source_id: str, storage_dir: str | Path, previous_checksum: str | None = None, *, organisation_id: str | None = None) -> dict:
    """Perform one bounded real primary-source check in the supplied store.

    URLs and legal metadata come exclusively from the server catalogue. Worker
    callers supply a tenant-scoped store and organisation ID. The public corpus
    and catalogue are never modified. Success means retrieval and parsing, not
    professional legal review or approval of an existing operational case.
    """
    entry=_registered_source(source_id)
    if previous_checksum is not None and not re.fullmatch(r"[a-f0-9]{64}",previous_checksum):
        raise ValueError("Previous checksum must be a SHA-256 digest")
    entry["organisation_id"]=organisation_id
    root=Path(storage_dir).resolve()
    folder=(root/source_id).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("Source path escaped the configured store")
    folder.mkdir(parents=True,exist_ok=True)
    with _monitor_lock(folder):
        state_path=folder/"monitor-state.json"
        previous=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        baseline=previous_checksum or previous.get("latest_checksum")
        checked_at=utc_now()
        common={"source_id":source_id,"organisation_id":organisation_id,"checked_at":checked_at,
                "rule_version":RULE_VERSION,"registered_version":entry["version"],
                "approved_metadata":{k:entry.get(k) for k in ("id","url","issuer","canonical_identifier","jurisdiction","language","legal_status","version","licence")},
                "previous_checksum":baseline,"last_successful_check":previous.get("last_successful_check"),
                "external_actions":[],"warning":"Notification silence does not establish absence of source changes; content checks do not establish legal applicability"}
        try:
            data,headers=safe_fetch(entry["url"])
            downloaded_at=utc_now()
            mime=headers.get("content-type","text/html").split(";")[0]
            if data.startswith(b"PK") or "zip" in mime:
                snapshot=_isolated_easa_snapshot(data,entry,folder,downloaded_at)
            else:
                snapshot=ingest_source(entry,root,data=data,content_type=mime)
                snapshot["import_mode"]="official_https_download"
                snapshot["retrieved_at"]=downloaded_at
                for row in snapshot["passages"]:
                    row["retrieved_at"]=downloaded_at
                _atomic_write(Path(snapshot["text_path"]),json.dumps(snapshot["passages"],indent=2).encode())
                _atomic_write(Path(snapshot["raw_path"]).parent/"manifest.json",json.dumps({k:v for k,v in snapshot.items() if k!="passages"},indent=2).encode())
            changed=baseline is not None and baseline!=snapshot["checksum"]
            result={**common,"success":True,"state":"Change Requires Review" if changed else "Snapshot Recorded" if baseline is None else "No Content Change",
                    "comparison":"content_changed" if changed else "initial_snapshot" if baseline is None else "unchanged",
                    "current_checksum":snapshot["checksum"],"last_successful_check":downloaded_at,"content_changed":changed,
                    "document_version":snapshot["document_version"],"passage_count":len(snapshot["passages"]),
                    "manifest_path":str(Path(snapshot["raw_path"]).parent/"manifest.json"),"passages_path":snapshot["text_path"],
                    "review_required":True,"dependency_review_required":changed,"existing_decisions_modified":False,
                    "currentness_status":"Registered edition retained; upstream content and applicability require review"}
            updated={"source_id":source_id,"organisation_id":organisation_id,"last_attempt":checked_at,"last_successful_check":downloaded_at,
                     "latest_checksum":snapshot["checksum"],"document_version":snapshot["document_version"],"last_outcome":result["state"],"upstream_error":None,
                     "check_count":previous.get("check_count",0)+1}
        except Exception as error:
            result={**common,"success":False,"state":"Upstream Check Failed","comparison":"unknown","current_checksum":None,
                    "content_changed":None,"dependency_review_required":False,"review_required":True,
                    "upstream_error":type(error).__name__+": "+str(error)[:300],"existing_decisions_modified":False}
            updated={**previous,"source_id":source_id,"organisation_id":organisation_id,"last_attempt":checked_at,"last_outcome":result["state"],
                     "last_successful_check":previous.get("last_successful_check"),"upstream_error":result["upstream_error"],"check_count":previous.get("check_count",0)+1}
        checks=folder/"checks"
        checks.mkdir(exist_ok=True)
        check_id=checked_at.replace(":","-")+"-"+os.urandom(4).hex()
        _atomic_write(checks/(check_id+".json"),json.dumps(result,indent=2).encode())
        _atomic_write(state_path,json.dumps(updated,indent=2).encode())
        return result


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "--parse":
    try:
        print(json.dumps(extract_document(Path(sys.argv[2]).read_bytes(), sys.argv[3]), ensure_ascii=True))
    except Exception:
        sys.exit(2)
