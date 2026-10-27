# Regulatory source records

`catalogue.json` is a researched source register, not a claim of complete legal coverage. `coverage.json` reports gaps. `snapshots/` contains original downloaded bytes, version metadata and source-anchored extraction. Downloads that fail, return a challenge page or require rights review are recorded as failures. A catalogue entry alone is not an ingested or operationally validated source.

Run `python scripts/ingest_regulatory.py --source eu-2019-947` to retrieve a registered source. Exact official HTTPS hosts are allowlisted. Redirects, private IPs, alternate ports, overlarge files and executable document features are rejected. PDF/ZIP import is deliberately separate from HTML ingestion. Follow redirects only after reviewing the destination and registering its exact official URL.

Original authority text retains its original language. No machine translation is described as authoritative English. National source applicability and SORA edition transitions require qualified review. The UK has a separate jurisdiction and receives no EU source matches.

Do not redistribute source snapshots merely because they were downloadable. Each record includes rights status. Release packaging must include only cleared source snapshots and manifests; sources with unconfirmed rights remain local and are excluded. Newly authored code's Apache licence does not relicense these documents.
