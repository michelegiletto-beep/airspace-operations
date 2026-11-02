## Current development checkpoint, 2 November 2026

Published and installed software remains 0.3.3-rc.1. Development source 0.3.4 is independently retrieved at `ea47156010c4c7ec0806a546ac0ee93ab507a361` on `codex/airspace-draft-boundaries-034`. Its Linux suite passed 561 tests with 20 skipped, PostgreSQL passed 19 tests, and the interface passed 180 tests with a successful build. Both full Windows attempts remain failed; the latest records 547 passed, 6 failures, 7 errors and 21 skipped. Native browser URL verification stopped, so no new screenshot, archive installation or release is claimed. Read `improvement/cycles/2026-11-02T011950Z-draft-boundaries.json` for exact evidence and the next bounded action. The separate engineering checkout is `F:/SystemLabAirspaceOperationsEngineering/candidate-0.3.4`. The original specification and operational acceptance remain incomplete. Earlier checkpoint sections are historical.

# System Lab Airspace Operations

This checkout contains development candidate **0.3.3-rc.1**. It addresses recovery from a failed saved-task request and keeps failed, loading and confirmed empty states distinct. The read-only request hook is being hardened against outdated responses from a previous request context. Its own source, interface, installation and publication gates remain under verification. No 0.3.3 download or completed validation is claimed here. The current published software remains 0.3.2-rc.1. [Candidate notes](publication/releases/0.3.3-rc.1/release-notes.md) and [publication status](publication/status.json) identify the current scope.

Version [0.3.2-rc.1](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.2-rc.1) is a published engineering candidate. It explains mission-proposal role permissions, integrates bounded publication-media checks and pins PyPDF 6.21.4 after three upstream denial-of-service advisories. Source and exact-archive suites each passed 542 tests with 20 skipped; 132 interface tests and 19 PostgreSQL checks passed with actual containers, a running worker and restoration. All nine release assets were independently retrieved. The earlier local 541 passed/21 skipped result is separate. [Release evidence](release-evidence/v0.3.2-rc.1/) and [publication status](publication/status.json) record exact scopes. The original specification remains incomplete; stable release and operational acceptance remain false.

Previous candidate [0.3.1-rc.1](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.1-rc.1) is a published engineering candidate. Its exact archive passed 479 tests with 20 skipped; the interface passed 123 tests. Release-source container, worker, PostgreSQL and restoration checks succeeded. All nine public assets were anonymously retrieved and digest-matched. This increment improves task readability, the visible version and mobile panel fit. See [known limitations](docs/known-limitations.md), including the frozen mobile image filename mismatch. Full original acceptance and operational acceptance remain incomplete.

Software for planning and reviewing civilian drone operations. It keeps intended missions, aircraft, personnel, permissions, evidence and tasks in one application. The interface uses persistent Python services and a database. A new installation contains no fictional flights or customer records.

Previous published version [0.3.0-rc.1](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.0-rc.1) is a published engineering candidate. The exact ZIP passed a clean installation and 407 software tests, with 20 skipped. All 19 PostgreSQL checks, actual containers, a running worker, backup/restoration and 107 interface tests passed separately. All nine release assets were anonymously downloaded and matched their published SHA-256 digests. The [previous 0.2 candidate](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.2.0-rc.1) and [first 0.1 candidate](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.1.0-rc.1) remain available with unchanged tags and bytes.

## Start with a task

Record the operation you intend to carry out. Add the real aircraft, people, location and supporting documents as they become available. The application identifies missing information and keeps draft work separate from reviewed evidence and permissions.

This revision implements a persistent local-model conversation, saved personal tasks and previews of internal draft actions that require your confirmation. The local model selects guidance and source, step and action identities; displayed guidance comes from a controlled registry and recorded state. Its owned companion animates during normal use, with an animated fallback and a restrained reactive background. Pause and reduced-motion settings take precedence. Actual browser, animated fallback, pause and current mobile task evidence are retained under release-evidence/v0.3.0-rc.1/.

![Historical 0.3.1 desktop application with its contextual companion](publication/media/0.3.1-rc.1/application-tasks.png)

![Actual 0.3.2 mobile Operations role guidance](publication/media/0.3.2-rc.1/operations-permissions-mobile.jpg)

The desktop capture records historical 0.3.1; the mobile capture records 0.3.2. Both come from isolated software review and show no customer operation or flown mission.

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

Use Python 3.13 and uv. Building the interface from source also needs Node 22.12 or newer and npm. The [downloadable archive](https://github.com/michelegiletto-beep/airspace-operations/releases/download/v0.3.2-rc.1/System-Lab-Airspace-Operations-0.3.2-rc.1.zip) includes the built interface. It contains 13,796,258 bytes and has SHA-256 `1634b9b7e36bd2b80b179a4e0429da7f0c9165434747fc9a62f03ede78cc772e`. Read the [schema 3 upgrade instructions](docs/upgrading-to-0.3.md) before updating an existing installation.

```powershell
uv sync --frozen --extra dev
.venv/Scripts/python.exe scripts/prepare_corpus.py
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

[Run 40803017486](https://github.com/michelegiletto-beep/airspace-operations/actions/runs/40803017486) verified frozen source `331b6e220fec5254c4c2f167cab3ad86d8905456`. The source suite and exact-archive installation each passed 407 tests, with 20 skipped. The 19 PostgreSQL checks passed in their separate container environment, including concurrent access and workflow isolation; running-worker and backup/restoration checks also passed. The interface suite passed 107 tests and its production build completed. The [release assets](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.0-rc.1) include the exact installation receipt, current CI record, provenance, release gates, checksums and SBOM. [Independent download evidence](release-evidence/v0.3.0-rc.1/cycle-20261030-public-downloads.json) records all nine public asset hashes. Earlier 0.2 evidence stays labelled with that release.

Recorded 29 October browser verification used one local Qwen generation and one durable reservation, followed by explicit personal-task confirmation and database/audit checks. Actual mobile and desktop layouts, animation, animated fallback and pause checks are preserved with their source identities. No new student training is claimed.

The [System Lab project page](https://giletto-systems-lab.michele-giletto.chatgpt.site/projects/airspace-operations) is published at version 98, source `7e96d2431d993a6acef01d8ea37dfa6fce40a80c`. All 49 checked resources passed independent retrieval, including 46 exact assets and 3 authored pages. The [model card](https://huggingface.co/Magic51/system-lab-airspace-shall-router), [dataset card](https://huggingface.co/datasets/Magic51/system-lab-airspace-source-annotations) and [recorded evaluation Space](https://huggingface.co/spaces/Magic51/system-lab-airspace-evaluation) now present 0.3.1 evidence and actual screenshots. All ten reviewed presentation files match their manifests; original weights, dataset rows and historical evidence are unchanged. The static Space runs no model. [Publication status](publication/status.json) and the [Hub publication record](docs/huggingface-publication.md) identify exact revisions and verification boundaries.

The experimental literal-language student and its source annotation dataset are unchanged. Its 81.82% agreement on 77 unreviewed machine labels remains below the deterministic literal-word baseline's 100%. It is not promoted, and it does not establish legal correctness. No new training, operational prediction or benchmark improvement is claimed.

The regulatory corpus preserves 9,833 actual EASA passages with editions, checksums and anchors. It does not establish complete current European law. Luxembourg and Italy still need qualified reconciliation. Other country entries are registered geography, and UK applicability remains separate. Original source languages and legal meaning are preserved. See the [source register](SOURCE_REGISTER.md).

No accepted live telemetry, weather, airspace or contracted U-space feed is implied by installation. Missing information remains missing. See [capabilities](capabilities.json), [known limitations](docs/known-limitations.md), [safety boundary](SAFETY_BOUNDARY.md), [recovery instructions](docs/recovery-runbook.md) and [original requirement traceability](REQUIREMENTS_TRACEABILITY.csv).

This is an engineering candidate. It is not certified separation, Detect and Avoid, air traffic control or a flight approval. Adopting organisations must establish lawful data access, real records, approved procedures, competent review, national applicability and permissions, and their own acceptance evidence.

New application code uses Apache-2.0. Existing System Lab artwork and presentation files retain reserved rights; regulatory documents, third-party models and dependencies keep their own terms. Private records, credentials and cached foundation-model weights are excluded from public releases.


## Upgrade compatibility

Version 0.3 uses schema marker 3 because older applications do not protect actor-private companion records. Stop every old API, worker and scheduled client before upgrading; mixed-version rolling deployment is unsafe. Follow [the upgrade procedure](docs/upgrading-to-0.3.md). Never remove marker 3 to force an older version to start.
