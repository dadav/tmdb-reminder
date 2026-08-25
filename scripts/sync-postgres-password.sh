#!/bin/sh

set -eu

# The official Postgres image applies POSTGRES_PASSWORD only when initializing a
# new data directory. Reconcile the persisted role on later Compose starts so a
# password change in .env does not require deleting the database volume.
psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 \
    --set=role_name="$POSTGRES_USER" \
    --set=role_password="$POSTGRES_PASSWORD" <<'SQL'
SELECT format('ALTER ROLE %I PASSWORD %L', :'role_name', :'role_password') \gexec
SQL
