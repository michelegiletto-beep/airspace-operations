# System Lab Airspace Operations

Software for planning and reviewing civilian drone operations. It keeps intended missions, aircraft, personnel, permissions, evidence and tasks in one application. The interface uses persistent Python services and a database. A new installation contains no fictional flights or customer records.

Version [0.3.0-rc.1](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.0-rc.1) is a published engineering candidate. Its exact ZIP passed a clean installation and 407 software tests, with 20 skipped. Nineteen PostgreSQL checks, actual containers, a running worker, restoration and 107 interface tests passed separately. All nine public release assets were independently retrieved and SHA-256 matched. Actual local-model replies, an explicitly confirmed personal task and API-restart persistence are recorded. The [published 0.2 candidate](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.2.0-rc.1) remains available and unchanged.

## Start with a task

Record the operation you intend to carry out. Add the real aircraft, people, location and supporting documents as they become available. The application identifies missing information and keeps draft work separate from reviewed evidence and permissions.

This revision provides a persistent local language-model conversation, saved personal tasks and previews of proposed internal drafts before confirmation. The owned companion animates during ordinary use, with an animated fallback and a restrained background responding to interaction. Pause and reduced-motion settings take precedence. Conversations and personal tasks are private to their author; confirmed cases and agent workflows are visible to the organisation.

![Desktop application with contextual companion](publication/media/v0.3/desktop-companion.jpg)

![Mobile application with contextual companion](publication/media/v0.3/mobile-companion.jpg)

These captures come from an isolated software-review workspace. They do not show a customer operation or a flown mission.

The companion does not issue a permission or approve its own work. Animation does not prove that a model has finished or that a flight is ready. A missing local model must remain visibly unavailable. All real workspaces remain usable when language-model generation is unavailable.

## What the application records

| Area | Work |
| --- | --- |
| Missions | Intended operation, resources, current status and missing information |
| Authorisations | Source documents, requirements, review comments and separate permission records |
| Airspace | Proposed sites and routes, coordinate and height references, and data limitations |
| Aircraft and personnel | Configuration, maintenance evidence, qualifications and availability |
| Planning | Resource proposals, independent schedule checks and reservations |
| Country coordination | The countries along a route, applicable instruments and handovers |
| Tasks and assistance | Saved work, explanations and proposed internal drafts requiring confirmation |
| Incidents | Recorded events, approved procedures, accountable actions and evidence |

Internal review, authority permission, U-space permission, pilot acknowledgement and actual flight execution remain separate records. The software does not command aircraft or activate provider services.

## Install on your computer or server

Use Python 3.13 and uv. Building the interface from source also needs Node 22.12 or newer and npm. The [downloadable archive](https://github.com/michelegiletto-beep/airspace-operations/releases/download/v0.3.0-rc.1/System-Lab-Airspace-Operations-0.3.0-rc.1.zip) includes the built interface. Its 11,675,616 bytes have SHA-256 `4a004e21dd04633e82c330f191745ad9b31bd65d8424183d0b66cfd00243763e`. Read the [schema 3 upgrade instructions](docs/upgrading-to-0.3.md) before updating an existing installation.

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

Open `http://127.0.0.1:8787`. Enter a password when prompted. There is no default account. Add colleagues under the returned organisation ID with the roles they need. An administrator is not automatically a reviewer. Linux uses `.venv/bin/python` and its corresponding shell environment syntax.

Run the background worker separately:

```powershell
$env:PYTHONPATH='backend'
.venv/Scripts/python.exe -m airspace.cli worker
```

Local model files are an explicit optional installation:

```powershell
uv pip install --python .venv/Scripts/python.exe --require-hashes -r requirements-neural.lock.txt
.venv/Scripts/python.exe scripts/prepare_neural.py --component encoder --component reranker
.venv/Scripts/python.exe scripts/prepare_controller.py
```

The pinned Qwen3-1.7B files occupy approximately 4.08 GB before runtime overhead. Allow additional memory for model loading, retrieval and services. Earlier CPU timings describe their recorded machine; they are not a guaranteed performance target. Read the [model setup guide](docs/model-administration.md) and [administrator handbook](docs/administrator-handbook.md) before loading private operational material.

## Evidence and limitations

[Run 40803017486](https://github.com/michelegiletto-beep/airspace-operations/actions/runs/40803017486) verified frozen source `331b6e220fec5254c4c2f167cab3ad86d8905456`. The source suite and exact-archive installation each passed 407 tests, with 20 skipped; all 19 PostgreSQL checks passed in their separate deployment environment. Actual container, running-worker and backup/restoration checks passed. The interface suite passed 107 tests and its production build completed. [Release assets](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.0-rc.1) include the exact installation receipt, CI record, provenance, release gates, checksums and SBOM. Earlier 0.2 evidence remains labelled with that release.

The experimental literal-language student and its source annotation dataset are unchanged. Its 81.82% agreement on 77 unreviewed machine labels remains below the deterministic literal-word baseline's 100%. It is not promoted, and it does not establish legal correctness. No new training, operational prediction or benchmark improvement is claimed.

The regulatory corpus preserves 9,833 actual EASA passages with editions, checksums and anchors. It does not establish complete current European law. Luxembourg and Italy still need qualified reconciliation. Other country entries are registered geography, and UK applicability remains separate. Original source languages and legal meaning are preserved. See the [source register](SOURCE_REGISTER.md).

No accepted live telemetry, weather, airspace or contracted U-space feed is implied by installation. Missing information remains missing. See [capabilities](capabilities.json), [known limitations](docs/known-limitations.md), [safety boundary](SAFETY_BOUNDARY.md), [recovery instructions](docs/recovery-runbook.md) and [original requirement traceability](REQUIREMENTS_TRACEABILITY.csv).

This is an engineering candidate. It is not certified separation, Detect and Avoid, air traffic control or a flight approval. Adopting organisations must establish lawful data access, real records, approved procedures, competent review, national applicability and permissions, and their own acceptance evidence.

New application code uses Apache-2.0. Existing System Lab artwork and presentation files retain reserved rights; regulatory documents, third-party models and dependencies keep their own terms. Private records, credentials and cached foundation-model weights are excluded from public releases.
