# Regulatory ingestion administration

Run commands from the product directory using its Python environment:

```powershell
python scripts/ingest_regulatory.py --source lu-dac-sora
python scripts/import_easa_xml.py
python scripts/import_easa_xml.py --url https://www.easa.europa.eu/en/downloads/139565/en --source-id easa-uspace-xml-2024 --edition "May 2024"
```

The catalogue is `sources/catalogue.json`; coverage and permitted use are in `sources/coverage.json` and `sources/rights-review.json`. Each snapshot has original downloaded bytes, checksum, retrieval time, edition and structured passages. Preserve originals unchanged. New source versions create separate content-addressed directories. Ingestion does not supersede reviewed case evidence automatically. `change_impact` creates owner-assigned review tasks for dependent records and leaves approved decisions unchanged.

Only exact registered official HTTPS hosts are accepted. DNS results must all be public, and the TLS connection pins the validated address while verifying the hostname. Redirects, userinfo, alternate ports, proxy environment settings, compressed HTTP responses and oversized documents are rejected. Fetches have a 25-second connection timeout and a 25 MiB limit. EASA XML archives accept one bounded XML payload and reject DTDs and entities. Source text does not gain execution or tool privileges.

HTML/XML parsing uses non-executing standard parsers. Generic document parsing runs in an isolated Python process with a timeout and bounded output. Process isolation on Windows is not an operating-system sandbox. Managed production deployments must additionally run parsers as non-root workers with no network, read-only source mounts, restricted system calls and memory/CPU limits. PDF and arbitrary archive ingestion are rejected pending a reviewed format-specific parser. No OCR quality is claimed.

The separate EASA import preserves machine-readable source metadata, paragraph ordering and table cell boundaries. Equal text in distinct paragraphs or rows is retained because different locations may carry different legal meaning. Regression tests cover short numeric rows and historical methodology boundaries. The source XML retains row/column spans and page-layout information; flattened table rows alone must not be used to derive an unimplemented decision table.

No national snapshot is automatically cleared for release or training. Source availability is separate from reuse rights and operational suitability. Newly authored code's Apache licence does not relicense source documents. EASA's acknowledged-reproduction policy was retrieved from [its copyright notice](https://www.easa.europa.eu/en/copyright-disclaimer); document-specific restrictions still prevail. Do not redistribute logos, illustrations, private correspondence or restricted standards.

Install a reviewed source pack by placing its manifest and preserved snapshots under `sources/`, rerunning citation resolution checks, and setting only applicability intervals supported by primary evidence and an accountable review. A listed jurisdiction without these steps remains unvalidated. A source amendment must create a review task for affected cases, evidence, sites, routes and procedures before any controlled record is revised.

The durable `regulatory_monitor` worker accepts `{"source_id": "registered-catalogue-id"}` and an optional previous SHA-256 digest. It obtains the URL and metadata from the server catalogue; payload-supplied URLs and additional arguments are rejected. It actually downloads and parses HTML or the reviewed EASA XML archive formats. Outputs are stored under `AIRSPACE_RUNTIME/sources/<organisation>/` with tenant-scoped passages, unchanged original bytes, version manifests, append-only check reports and a current monitor-state record. It never updates the shared public corpus. An upstream failure marks the job Failed while retaining its result and the earlier successful check time. A byte change requests dependency review; it does not automatically declare a legal amendment or overwrite an approved case.
