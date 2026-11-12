FROM postgres:17.12-bookworm@sha256:40865bc877a289da75963d97d72b59633f639fc5af7a4e856bfa3714cae5b536
# Keep server and rebuilt extensions in the same reviewed PostgreSQL ABI set.
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-17=17.12-1.pgdg12+1 \
    postgresql-client-17=17.12-1.pgdg12+1 \
    postgresql-17-pgvector=0.8.7-1.pgdg12+2 \
    postgresql-17-postgis-3=3.7.0+dfsg-1.pgdg12+2 \
    postgresql-17-postgis-3-scripts=3.7.0+dfsg-1.pgdg12+2 \
    && rm -rf /var/lib/apt/lists/*
COPY migrations/002_extensions.sql /docker-entrypoint-initdb.d/002_extensions.sql
COPY --chmod=0755 deploy/010_application_role.sh /docker-entrypoint-initdb.d/010_application_role.sh
COPY --chmod=0755 deploy/database-health.sh /usr/local/bin/airspace-database-health
