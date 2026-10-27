-- PostgreSQL deployment bootstrap; executed by the database administrator.
-- These extensions are deployment capabilities. Current spatial calculations
-- use PROJ and current retrieval uses filtered local vectors; no query claims
-- to use a database vector index until that path has verification evidence.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
