# System Lab Airspace Operations — delivery handover

**Release: 0.1.0-rc.1, engineering release candidate.** The software is downloadable and locally installable. The original master specification is **not fully implemented or accepted**; stable release and real-world operational deployment remain blocked by the gaps below. Software tests, internal reviews and published artifacts do not confer aviation certification, regulatory permission or operational acceptance.

## Published artifacts and release identity

| Artifact | Verified location and state |
| --- | --- |
| Source repository | [GitHub source](https://github.com/michelegiletto-beep/airspace-operations), publicly accessible and independently cloned. |
| Candidate release | [v0.1.0-rc.1](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.1.0-rc.1), published as a prerelease and independently retrieved. |
| Installable package | [System-Lab-Airspace-Operations-0.1.0-rc.1.zip](https://github.com/michelegiletto-beep/airspace-operations/releases/download/v0.1.0-rc.1/System-Lab-Airspace-Operations-0.1.0-rc.1.zip), 2,090,705 bytes; public download matches the prepared archive. |
| Neural artifact | [Magic51/system-lab-airspace-shall-router](https://huggingface.co/Magic51/system-lab-airspace-shall-router), actual trained safetensors, loader, lineage and model card; independently retrieved with matching weight digest. |
| Machine-derived dataset | [Magic51/system-lab-airspace-source-annotations](https://huggingface.co/datasets/Magic51/system-lab-airspace-source-annotations), permitted source-linked annotations and dataset card; independently retrieved and matched to the actual experiment. |
| System Lab project page | [Published project page](https://giletto-systems-lab.michele-giletto.chatgpt.site/projects/airspace-operations), site version 94; independently retrieved with HTTP 200, homepage link and release links verified. The [site-hosted ZIP](https://giletto-systems-lab.michele-giletto.chatgpt.site/airspace-operations/System-Lab-Airspace-Operations-0.1.0-rc.1.zip) matches the frozen GitHub release byte count and digest. |

Frozen source tag: `v0.1.0-rc.1`, commit `921996c4db20c449b21dcd03bd21f438911eed62`.

ZIP SHA-256:

```text
a114fa757fe60c9ded044092fac986ce3558cc5ddc5f0c3bd924e9de2caa9d87
```

Release assets also include `SHA256SUMS.txt`, `SBOM.cdx.json`, `RELEASE_PROVENANCE.json` and `release-gates.json`. These handover notes are subsequent delivery documentation; the published archive and source tag retain the identity above. The local product source directory is `products/airspace-operations/`. The frozen ZIP lacks the requested named `SOURCE_REGISTER.md` summary; the [source register](SOURCE_REGISTER.md) is supplied on `main` as documented in [release errata](RELEASE_ERRATA.md). Private runtime stores, evidence objects, credentials and uncleared national-source originals are excluded from public packages. Newly authored code uses Apache-2.0; third-party documents, components and models retain their own rights and notices.

The additive System Lab site deployment succeeded from source commit `bb9ffcd968917e28ab085bcf098abeb417fa8147`. It publishes project documentation and download assets; no operational tenant instance was published. All configured publication destinations reached **Independently Retrieved** with no publication access blocker remaining. Final destination records are in [publication/status.json](publication/status.json), with website evidence in [system-lab-public-verification.json](release-evidence/system-lab-public-verification.json).

## What works

The application provides a typed React operations interface, authenticated Python API, persistent SQLite portability profile, tenant-scoped objects and records, revision history, independent reviewer permissions, optional second-review policy, controlled JSON/HTML case exports, integrity-checked attachments, tamper-evident audit verification and separately runnable bounded workers. The ten workspaces cover the requested operational domains. A pristine installation has an empty operational organisation; it contains no fictional flights, customers, approvals or live feeds.

Implemented decision-support mechanisms include source ingestion and anchored retrieval; requirements, evidence and authorisation records; SORA edition/evidence compatibility and a limited source-bound calculation subset; geodesic candidate-site screening; aircraft and personnel records; CP-SAT scheduling with a separate verifier; transactional internal reservations and cancellation; read-only authorised manual telemetry imports; distinct live/replay modes; deterministic alert acknowledgement and approved-procedure incident workspaces; degraded incident snapshot export; and explicit-input deployment economics. Reservations and advisory dispatch checks do not release a flight, activate a provider or operate an aircraft. External submissions and correspondence have no execution tool.

Detailed implementation and acceptance states are in [capabilities.json](capabilities.json), [REQUIREMENTS_TRACEABILITY.csv](REQUIREMENTS_TRACEABILITY.csv) and [known limitations](docs/known-limitations.md). The immutable acceptance baseline remains [SPECIFICATION.md](SPECIFICATION.md).

## Installation and first use

Use Python 3.13, Node.js 22.12 or later, npm and uv. A 4-core CPU and 8 GB RAM are practical base allowances. From a newly extracted product directory on Windows:

```powershell
uv sync --frozen --extra dev
python scripts/prepare_corpus.py
cd frontend
npm ci
npm run build
cd ..
$env:PYTHONPATH='backend'
.venv/Scripts/python.exe -m airspace.cli check
.venv/Scripts/python.exe -m airspace.cli user-add --organisation 'Your organisation' --email 'you@example.org' --role administrator
.venv/Scripts/python.exe -m airspace.cli serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`. Password entry is interactive; there is no default account. Repeat `user-add` with the returned `--organisation-id` for the required regulatory, reviewer, planner, pilot and other roles. Administrator access does not imply operational authorship or reviewer authority. On Linux use `.venv/bin/python` and `export PYTHONPATH=backend`.

Run `.venv/Scripts/python.exe -m airspace.cli worker` in a separate process from the product directory. API documentation is `/api/docs`, OpenAPI is `/api/v1/openapi.json`, and authenticated detailed engine schemas are `/api/v1/contracts`. Set service environment variables explicitly; Python does not automatically load `.env.example`.

The core runs without System Lab hosting or hosted model services. Optional pinned local retrieval/inference setup is in [model administration](docs/model-administration.md); CPU inference was executed. Allow about 2 GB additional RAM for retrieval models and at least 4 GB for teacher work, plus application resources. The experimental student is not automatically promoted. Containers, PostgreSQL/PostGIS/pgvector configuration and migrations are provided, but their deployment was not executed in this environment.

## Evidence actually obtained

| Verification | Observed result |
| --- | --- |
| Local Python suite | 137 passed; recorded statement coverage approximately 75%. Captured runs retain resource/dependency warnings. |
| Frontend suite and build | 27 tests passed in seven suites; strict TypeScript and production build passed. |
| Exact published ZIP, separate clean directory | Frozen dependency installation succeeded; empty authenticated service boundary verified; **136 passed, 1 skipped, 0 failed**. The skipped test needs an original licensed upstream XML ZIP excluded from the package; actual upstream ZIP/parser checks are recorded separately. |
| Public source clone | Independently cloned, installed and tested: 136 passed, 1 skipped; subsequent release-source metadata validation recorded. |
| Security and resilience | Tested tenant isolation, reviewer independence, controlled metadata, evidence integrity, transactional rollback, concurrency/reservations, worker recovery, telemetry/replay boundaries and SQLite restoration. Current core, frontend and optional neural dependency scans reported no known advisories in their recorded scans. |
| Small local latency probe | 30 health requests: median 5.82 ms, p95 6.75 ms; five lexical retrieval queries: median 0.912 s. These empty-organisation engineering measurements establish no production capacity or availability objective. |

Commands and outputs are preserved in [release-evidence](release-evidence/), including `final-python-tests.txt`, `frontend-tests.json`, `standalone-archive-verification.json`, public retrieval reports, source/parser checks and dependency scans. Reproduce the software suites with `.venv/Scripts/python.exe -m pytest -q`, then `npm test` and `npm run build` inside `frontend/`. No mocked operational feed is represented as a successful live integration.

## Sources and neural work

The installed public research corpus contains **9,833 actual English EASA passages**, extracted from the June 2026 UAS and May 2024 U-space structured archives, preserving section, table/paragraph, block and checksum provenance. Fresh monitor checks ran for the EASA UAS publication page and U-space XML archive. Recorded direct EUR-Lex attempts for 2019/947, 2019/945 and 2021/664 returned challenge/HTTP 202 responses and were rejected; a registered identifier does not establish that it was individually fetched. Amendment/currentness reconciliation remains incomplete. Luxembourg DAC and Italian ENAC pages were retrieved in their original languages; both national packs require qualified validation, and their redistribution/training rights are not assumed. UK applicability remains separate; no validated UK pack is delivered. Temporal retrieval is restricted to reviewed snapshot dates and abstains for unsupported historical/future applicability. See the [source register](SOURCE_REGISTER.md), [regulatory coverage](docs/regulatory-coverage.md), the [machine-readable catalogue](sources/catalogue.json) and `sources/coverage.json`.

Neural training **actually ran**: run `explicit-shall-20261027-4` produced a 12,386-parameter student over a frozen pretrained encoder. Its narrow task is literal English `shall`-language routing, not legal obligation inference. The teacher annotated 288 real passages; 42 were quarantined and 246 remained unreviewed machine annotations. Whole-source-family splits were used. Held-out agreement was **81.82% on 77 machine labels**, versus **100% for the deterministic literal-word baseline**. The candidate is **Experimental — Not promoted** and demonstrates no production advantage over that baseline. Three earlier semantic-teacher attempts failed and retain their blocked lineage. No operational prediction model was trained. CPU inference was separately executed after dependency upgrades; training metrics retain the original environment. Read the [model card](docs/model-card.md) and [dataset card](docs/dataset-card.md).

## Remaining engineering work and operational acceptance

**Software feature and assurance gaps:** actual PostgreSQL/PostGIS/pgvector and Docker build/concurrency/recovery verification; complete SORA ground/air-risk derivation and OSO/DAA assurance; deeper route/GIS planning; complete recurrence/charging optimisation; detailed fleet campaigns; route-specific submission packages; automatic retention/erasure; interactive offline operation; full occurrence-reporting rules; enterprise identity acceptance; and representative production-scale failure, security and performance assurance. Generic PDF ingestion is unavailable. The full original specification remains open, and stable release is blocked rather than waived.

**Operational acceptance and access requirements:** qualified national/source review; lawful authoritative airspace, weather, terrain, population and geozone access; provider-specific U-space interfaces/contracts/credentials; real operator aircraft, personnel and operational records; approved procedures and monitoring thresholds; security/privacy applicability and retention decisions; deployment-specific restoration/identity tests; and all applicable operating bases and permissions. No accepted live operational feed, enterprise identity provider, U-space provider or customer aircraft is connected. EAD Basic remains research-only. The product neither submits an authorisation nor controls an aircraft.

For administration, follow [administrator handbook](docs/administrator-handbook.md) and [recovery runbook](docs/recovery-runbook.md). Back up the database, complete object store and original audit key; the database alone does not contain attachment bytes. For adoption, follow [operator handbook](docs/operator-handbook.md), [data-provider setup](docs/data-provider-setup.md), [incident management](docs/incident-management.md), [THREAT_MODEL.md](THREAT_MODEL.md) and [SAFETY_BOUNDARY.md](SAFETY_BOUNDARY.md). Further engineering work should advance the original traceability matrix without changing this candidate's frozen release identity.
