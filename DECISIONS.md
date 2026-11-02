## Windows installation diagnostics, 2 November 2026

Expose configuration and representative path limits without changing registry values, relocating records or weakening failed gates. Environment checks must not create a database or key. Report supported schema separately from an inspected database. Keep the original deep-path failures and same-case reproduction alongside the passing short-path suite. New screenshots use actual browser pixels and exclude the account header; rejected captures stay private.

# Architecture decisions

31 October 2026: use a standard-library container-format guard for future candidate screenshots, alongside separate browser decoding, visual review and rights checks. Validate the selected screenshot and the candidate media namespace; bound bytes, total entries, depth and raster count. An independent review identified the need for the total-entry and depth bounds, which were added and tested. The verified development source is c6839aeda8276685ea55bae724d90669ae2e9bcd; it does not amend frozen release0.3.1.

31 October 2026: preserve private SQLite/WAL/key files before recovering a full-volume startup failure. Broad recursive environment cleanup was automatically rejected; narrower housekeeping removed only one disposable bytecode cache and one superseded temporary Site archive. Keep packaging blocked until sufficient working storage exists, even though API/data/audit recovery succeeded. Retain clean prepared Site sourcea7c4da5 against verified remote309b6fa and use ordinary concurrency-safe source publication when work resumes. No forced history change, new Site deployment, model execution or operational acceptance follows from these checks.

- D001: separate product directory; existing portfolio repository has unrelated uncommitted work. No reuse or relicensing of existing assets.
- D002: Python FastAPI modular API, SQLAlchemy transactional persistence, React/TypeScript interface and separately runnable durable worker. SQLAlchemy 2.0 maintenance series selected for known compatibility after reading current official documentation (2026-10-27). Database-backed leased jobs and transactional outbox avoid a mandatory external orchestration service in a self-hosted installation.
- D003: PostgreSQL deployment target with PostGIS and pgvector extensions; SQLite local portability/testing profile. Spatial safety checks use geodesic calculations, not flat latitude/longitude. Do not claim SQLite validates PostgreSQL concurrency or extensions.
- D004: local password identity uses scrypt and short-lived opaque hashed sessions. CLI provisions users and roles; no self-service elevation. Enterprise OIDC is a separate configuration path requiring issuer/audience verification and explicit existing-user mapping.
- D005: documents retain provenance and original language. Retrieval is evidence lookup; unsupported legal conclusions abstain. No external generative API dependency in essential workflows.
- D006: all operational workspaces start empty. Test fixtures are isolated from production stores. Restricted provider access remains Not Connected; no synthetic connection success.
- D007: engineering release candidate only until source coverage, domain review, security and deployment gates are satisfied. Model promotion requires a named reviewer and cannot follow automatically from training metrics.

Documentation consulted: https://fastapi.tiangolo.com/deployment/docker/ ; https://docs.sqlalchemy.org/en/20/intro.html ; https://www.postgresql.org/docs/current/release-18.html ; https://github.com/pgvector/pgvector ; official Codex execution-plan guidance referenced in the baseline. Access date 2026-10-27.


## 28 October 2026 — publication verification profile

Core runtime remains frozen. Added a separate hash-locked publication-only profile and complete optional neural/model SBOM entries. The first publication-dependency scan found64 Pillow12.2.0 advisories; the historical failed report remains preserved. Upgraded the explicit publication environment to Pillow13.0.0, rescanned all6 pinned packages (zero known vulnerabilities) and revalidated actual image bytes. The canonical CycloneDX schema endpoint returned HTTP403; validation uses the same official specification repository at pinned1.6.2 commit e833d732337dd33aceb45ff1991f896796f1e5e7. All240 SBOM components validated against its official schema and SPDX list. This is format validation, not a legal clearance. A shell-wrapped long document write was rejected by automatic approval review with no detailed reason; the handover was completed through an explicit file patch. No permission expansion or external correspondence was used.


29 October2026: candidate publication is being moved into a separate repository-scoped GitHub Actions job after real container/PostgreSQL verification. The local connector lacks release/asset methods and the noninteractive Git credential helper has no credential; no new personal token was created. The publisher must fail closed on identity/source/gates/existing tags, preserve failures as drafts, validate exact assets and keep anonymous retrieval separate. Official GitHub CLI create/upload documentation and GITHUB_TOKEN authentication guidance were read on29October2026. The official actions/setup-node v6 ref resolved to249970729cb0ef3589644e2896645e5dc5ba9c38; the release job provisions the supported Node22line and records its actual version. This does not broaden any product agent permission.


## 0.3.1 companion presentation and release selection

Compare complete task titles and descriptions with whitespace normalisation only; preserve distinct text and the underlying records. Do not use fuzzy deletion for legal or safety guidance. The current contract has no versioned guidance-equivalence metadata, so semantic overlap remains explicit. Use the package version as the UI version source. Size the fixed companion against the layout viewport rather than scrollbar-inclusive `100vw`; actual mobile bounds are checked in the browser. New candidate publication requires a strict version-specific notes and screenshot manifest, rather than inheriting 0.3 materials. Original artwork, model weights, operational rules and schema marker 3 remain unchanged.


## 2 November 2026 development checkpoint

Use a separate owned F volume checkout after the C volume reached zero free bytes; retain all original releases, runtime data and models. A rejected cache deletion is not retried through another mechanism. Current publication aliases are derived from matching saved/deployed/public receipts. Development 0.3.4 stays unreleased until native browser verification and the remaining release gates pass.
