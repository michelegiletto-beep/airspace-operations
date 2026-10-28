# Architecture decisions

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
