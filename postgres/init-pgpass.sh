#!/bin/bash
set -e

POSTGRES_HOME=$(eval echo ~postgres)

cat > "$POSTGRES_HOME/.pgpass" <<EOF
localhost:5432:*:postgres:${POSTGRES_PASSWORD}
127.0.0.1:5432:*:postgres:${POSTGRES_PASSWORD}
EOF

chmod 600 "$POSTGRES_HOME/.pgpass"
chown postgres:postgres "$POSTGRES_HOME/.pgpass"