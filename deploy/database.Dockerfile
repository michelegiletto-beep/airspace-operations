FROM pgvector/pgvector:0.8.1-pg17-bookworm@sha256:3e8b3adfd27b5707128f60956f62a793c3c9326ea8cfaf0eab7adccb5d700b21
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-17-postgis-3 postgresql-17-postgis-3-scripts && rm -rf /var/lib/apt/lists/*
COPY migrations/002_extensions.sql /docker-entrypoint-initdb.d/002_extensions.sql
COPY --chmod=0755 deploy/010_application_role.sh /docker-entrypoint-initdb.d/010_application_role.sh
