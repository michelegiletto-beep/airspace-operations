#!/bin/sh
# Database bootstrap only. The ordinary application never receives this role.
set -eu
: "${AIRSPACE_DB_APP_PASSWORD:?A private application database password is required}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
  --set="app_password=$AIRSPACE_DB_APP_PASSWORD" --set="database_name=$POSTGRES_DB" <<'SQL'
CREATE ROLE airspace LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'app_password';
GRANT CONNECT ON DATABASE :"database_name" TO airspace;
GRANT USAGE, CREATE ON SCHEMA public TO airspace;
SQL
