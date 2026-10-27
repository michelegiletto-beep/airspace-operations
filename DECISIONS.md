# Architecture decisions

- D001: separate product directory; existing portfolio repository has unrelated uncommitted work. No reuse or relicensing of existing assets.
- D002: Python FastAPI modular API, SQLAlchemy transactional persistence, React/TypeScript interface and separately runnable durable worker. SQLAlchemy 2.0 maintenance series selected for known compatibility after reading current official documentation (2026-10-27). Database-backed leased jobs and transactional outbox avoid a mandatory external orchestration service in a self-hosted installation.
- D003: PostgreSQL deployment target with PostGIS and pgvector extensions; SQLite local portability/testing profile. Spatial safety checks use geodesic calculations, not flat latitude/longitude. Do not claim SQLite validates PostgreSQL concurrency or extensions.
- D004: local password identity uses scrypt and short-lived opaque hashed sessions. CLI provisions users and roles; no self-service elevation. Enterprise OIDC is a separate configuration path requiring issuer/audience verification and explicit existing-user mapping.
- D005: documents retain provenance and original language. Retrieval is evidence lookup; unsupported legal conclusions abstain. No external generative API dependency in essential workflows.
- D006: all operational workspaces start empty. Test fixtures are isolated from production stores. Restricted provider access remains Not Connected; no synthetic connection success.
- D007: engineering release candidate only until source coverage, domain review, security and deployment gates are satisfied. Model promotion requires a named reviewer and cannot follow automatically from training metrics.

Documentation consulted: https://fastapi.tiangolo.com/deployment/docker/ ; https://docs.sqlalchemy.org/en/20/intro.html ; https://www.postgresql.org/docs/current/release-18.html ; https://github.com/pgvector/pgvector ; official Codex execution-plan guidance referenced in the baseline. Access date 2026-10-27.
