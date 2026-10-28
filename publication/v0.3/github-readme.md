# System Lab Airspace Operations

Software for planning and reviewing civilian drone operations. It keeps intended missions, aircraft, personnel, permissions, evidence and tasks in one application. The interface uses persistent Python services and a database. A new installation contains no fictional flights or customer records.

Version 0.3.0-rc.1 is Prepared. Its application checks, model interaction, screenshots, exact archive and public download are still being verified. The [published 0.2 candidate](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.2.0-rc.1) remains available and unchanged.

## Start with a task

Record the operation you intend to carry out. Add the real aircraft, people, location and supporting documents as they become available. The application identifies missing information and keeps draft work separate from reviewed evidence and permissions.

This revision is being prepared to offer clearer instructions, a persistent local language-model conversation, saved tasks and a preview of proposed internal actions before you confirm them. Its owned companion is intended to keep moving during ordinary use, with a real animated fallback and a restrained background that responds to interaction. Pause and reduced-motion settings take precedence. These changes require the new revision's execution and browser evidence before release.

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

Use Python 3.13 and uv. Building the interface from source also needs Node 22.12 or newer and npm. The final downloadable archive must include the built interface; no verified 0.3 archive is available at this preparation checkpoint.

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

The new candidate requires its own actual model, browser, software, container and installation results. [Publication status](publication/status.json) and [release evidence](release-evidence/) identify what has actually run. Earlier 0.2 evidence remains labelled with that release, including its container, PostgreSQL and recovery checks. It is not silently reused to certify changed code.

The experimental literal-language student and its source annotation dataset are unchanged. Its 81.82% agreement on 77 unreviewed machine labels remains below the deterministic literal-word baseline's 100%. It is not promoted, and it does not establish legal correctness. No new training, operational prediction or benchmark improvement is claimed.

The regulatory corpus preserves 9,833 actual EASA passages with editions, checksums and anchors. It does not establish complete current European law. Luxembourg and Italy still need qualified reconciliation. Other country entries are registered geography, and UK applicability remains separate. Original source languages and legal meaning are preserved. See the [source register](SOURCE_REGISTER.md).

No accepted live telemetry, weather, airspace or contracted U-space feed is implied by installation. Missing information remains missing. See [capabilities](capabilities.json), [known limitations](docs/known-limitations.md), [safety boundary](SAFETY_BOUNDARY.md), [recovery instructions](docs/recovery-runbook.md) and [original requirement traceability](REQUIREMENTS_TRACEABILITY.csv).

This is an engineering candidate. It is not certified separation, Detect and Avoid, air traffic control or a flight approval. Adopting organisations must establish lawful data access, real records, approved procedures, competent review, national applicability and permissions, and their own acceptance evidence.

New application code uses Apache-2.0. Existing System Lab artwork and presentation files retain reserved rights; regulatory documents, third-party models and dependencies keep their own terms. Private records, credentials and cached foundation-model weights are excluded from public releases.
