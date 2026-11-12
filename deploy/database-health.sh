#!/bin/sh
# Read-only application readiness: incomplete bootstrap must remain unhealthy.
set -eu
: "${AIRSPACE_DB_APP_PASSWORD:?Application database password is required}"
: "${POSTGRES_DB:?Application database name is required}"
case "$POSTGRES_DB" in
    *[!A-Za-z0-9_-]*|'') exit 1 ;;
esac
result=$(
    PGPASSWORD="$AIRSPACE_DB_APP_PASSWORD" PGCONNECT_TIMEOUT=3 \
    PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=1000 -c lock_timeout=500 -c search_path=pg_catalog,public' \
    psql -X --no-password --host=127.0.0.1 --port=5432 --username=airspace \
        --dbname="$POSTGRES_DB" --set=ON_ERROR_STOP=1 --tuples-only --no-align <<'SQL'
SELECT current_user = 'airspace'
   AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
   AND NOT rolreplication AND NOT rolbypassrls
   AND has_database_privilege(current_user, current_database(), 'CONNECT')
   AND has_schema_privilege(current_user, 'public', 'USAGE')
   AND has_schema_privilege(current_user, 'public', 'CREATE')
   AND public.postgis_lib_version() <> ''
   AND public.vector_dims('[0]'::public.vector) = 1
FROM pg_catalog.pg_roles WHERE rolname = current_user;
SQL
)
# A successfully executed SELECT false is still a failed readiness check.
[ "$result" = 't' ]
