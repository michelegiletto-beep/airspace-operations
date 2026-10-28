# Publication preparation for 0.3

Status: Prepared. No upload, deployment, new release or independent retrieval has been performed by this preparation work.

This directory implements the publication part of SPECIFICATION_V3_ADDENDUM.md. It preserves the existing System Lab identity, published 0.1 and 0.2 releases, model weights, dataset rows and reserved artwork. The current product implementation and its tests are owned by the application engineers.

The new copy describes tasks in ordinary English. It removes slogans, ornamental section numbers, hashtag labels and decorative slash or dash pairs. Actual version numbers, source anchors, dates, units, URLs, model identifiers, code, legal terms and Markdown structure retain their meaning. A phrase scan is a bounded aid; rendered review remains necessary.

## Files

| File | Intended destination |
| --- | --- |
| github-readme.md | Repository README after the new source has been verified |
| site-project.html and site-project.css | Only the existing Airspace Operations project page and its stylesheet |
| hf-model-card.md | Existing experimental student repository; weights unchanged |
| hf-dataset-card.md | Existing source annotation dataset; records unchanged |
| hf-space | Existing static evidence Space; no live model service implied |
| ablation-inventory.json | Concrete observed copy and proposed treatment |
| public-source-audit.json | Actual public source reads and failures |
| status.json | Prepared destination states and missing evidence |

## Release sequence

| Acceptance requirement | Owner and required evidence |
| --- | --- |
| ASO3-001 and ASO3-002 | Copy inventory plus rendered review; preserve legal text and technical references |
| ASO3-003 through ASO3-008 | Application engineers: actual model, persistence, action confirmation, guidance, animation and accessibility journeys |
| ASO3-009 and ASO3-010 | Release owner: exact new source, gates, installable archive, rights, SBOM, publication and independent retrieval |
| ASO3-011 | Release owner: existing automation receipt, public prompt and actual cycle checkpoints |
| ASO3-012 | All contributors: no email, people contact, paid services or operational external actions |

The release owner first verifies the application journeys, actual local model response, private conversation/task persistence, action preview and confirmation, stale input rejection, animation and fallback, reduced motion, background readability and browser errors. It then runs current software checks, rights checks, credential scans, dependency checks and actual container/database verification for the new source identity. Earlier release results remain historical evidence.

After source freeze, the owner creates the new candidate package, SBOM, checksums and provenance. It installs that exact archive in a separate directory and verifies an empty authenticated workspace. The new archive must not inherit an operator database, PostgreSQL test URL or enterprise identity configuration. The current script enforces an isolated SQLite verification profile.

Only after those gates pass does the owner create a distinct tag/release, upload the approved artifacts, retrieve them independently and verify bytes and links. The System Lab update uses the existing Site identity and official Site workflow. The owner updates the model/dataset presentation without changing existing artifacts, and updates the evidence Space with genuine 0.3 records and screenshots. A failed or unavailable destination keeps its own honest state.

Until these steps finish, these sources display Prepared, link only the existing verified 0.2 download, and contain no invented 0.3 screenshots, model runs, performance figures or release URLs. The owner must replace preparation statements only with observed results, then rerun copy, link, rights and retrieval checks. Do not copy an earlier CI success into the new candidate's verification record.

## Handoff

The GitHub payload tool defaults to `runtime/publication/github/v<actual-version>/`. Its inventory contains the exact `output_directory`, `inventory_path`, `batch_paths` and `large_path`; consumers must use those entries rather than globbing all historical payloads. Existing count fields remain available. `--legacy-output` explicitly restores the old unversioned output location for an older consumer.

Published receipts in the active ledger, publication history and versioned publication directories protect old versions before metadata or archive writes. No package has been built as part of this preparation.

The recurring engineering prompt and automation receipt are development governance. They do not schedule aircraft operations. Only files listed in improvement/publication-manifest.json enter the release; future unreviewed cycles remain excluded.
