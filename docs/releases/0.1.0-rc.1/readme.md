# System Lab Airspace Operations

Installable civilian UAS operational management and decision support. Version **0.1.0-rc.1**, engineering release candidate. It is not an autopilot, certified Detect and Avoid service, authority approval system or U-space provider. The original 170-paragraph acceptance baseline remains in SPECIFICATION.md; incomplete capabilities are visible in capabilities.json and REQUIREMENTS_TRACEABILITY.csv.

The application contains a Python API, persistent transactional records, tenant identity, controlled independent review, version history, tamper-evident audit, evidence objects, primary-source retrieval, deterministic spatial/risk/monitoring/incident/economics tools, OR-Tools scheduling with a separate verifier, leased workers and a React/TypeScript operations interface. No fictional operator, customer, flight, telemetry or authorisation is installed.

## Local installation

Requirements: Python 3.13, Node >=22.12, npm and uv. A 4-core CPU and 8 GB RAM are a practical base configuration; local neural model requirements are documented separately. This repository works without System Lab hosting or a hosted model subscription.

```powershell
uv sync --extra dev
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

Open http://127.0.0.1:8787 . Passwords are entered through an interactive prompt. There is no default account. Provision role-specific colleagues with the returned `--organisation-id`; administrator does not imply reviewer authority. On Linux use `.venv/bin/python` and `export PYTHONPATH=backend`. To use neural inference, follow docs/model-card.md and its pinned model-download instructions; the application remains usable without it.

Run a separately deployable internal worker from the same product directory:

```powershell
$env:PYTHONPATH='backend'
.venv/Scripts/python.exe -m airspace.cli worker
```

API contract: `/api/v1/openapi.json`; interactive documentation: `/api/docs`; detailed calculation schemas: authenticated `/api/v1/contracts`. Every API action except health/sign-in requires authentication. Configuration examples are in .env.example. Python does not automatically read that file: set environment variables in your service manager or shell.

## Verify and package

```powershell
.venv/Scripts/python.exe -m pytest -q
cd frontend
npm test
npm run build
cd ..
.venv/Scripts/python.exe scripts/verify_release.py
.venv/Scripts/python.exe scripts/package_release.py
```

Tests use isolated artificial fixtures; those records never enter the installed workspace. Published evidence records actual commands and outcomes. Read release-evidence before treating a target as verified. Container files are included; if no Docker/PostgreSQL execution evidence exists, their presence is preparation, not deployment verification.

## Deployment and operating boundary

The portability profile uses SQLite with a tenant object store under `runtime/`. The managed/self-hosted container path uses PostgreSQL, PostGIS and pgvector. Run `docker compose build` and `docker compose up -d` only after supplying private environment values as described in docs/administrator-handbook.md. In production terminate TLS, restrict database/worker egress and test identity/backup configuration.

Source coverage is a measured foundation, not all European law. Luxembourg and Italy are registered research packs pending full reconciliation and qualified validation. Full SORA, live provider integrations, production dispatch and real-world operational acceptance have separate gates. Downloadable code, model runs and test success do not confer legal or aviation authority.

Documentation: docs/operator-handbook.md, docs/administrator-handbook.md, docs/data-provider-setup.md, docs/recovery-runbook.md, docs/incident-management.md, docs/product-strategy.md, docs/known-limitations.md, SAFETY_BOUNDARY.md, THREAT_MODEL.md, SOURCE_REGISTER.md and DATA_REGISTER.md. New code is Apache-2.0; source documents, model weights and third-party components retain their own rights.
