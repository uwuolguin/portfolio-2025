#!/bin/bash
set -e

echo "Starting PostgreSQL SSL bootstrap (config only)..."

CERT_DIR="/var/lib/postgresql/certs"
CERT_FILE="$CERT_DIR/server.crt"
KEY_FILE="$CERT_DIR/server.key"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "ERROR: SSL certificates not found"
    echo "Expected:"
    echo "  - $CERT_FILE"
    echo "  - $KEY_FILE"
    exit 1
fi

echo "SSL certificates found (read-only volume)"

CUSTOM_CONF="$PGDATA/postgresql.ssl.conf"

if [ ! -f "$CUSTOM_CONF" ]; then
    cat > "$CUSTOM_CONF" <<EOF
ssl = on
ssl_cert_file = '$CERT_FILE'
ssl_key_file  = '$KEY_FILE'
ssl_min_protocol_version = 'TLSv1.2'
EOF
    chown postgres:postgres "$CUSTOM_CONF"
fi

if ! grep -q "include.*postgresql.ssl.conf" "$PGDATA/postgresql.conf"; then
    echo "include = 'postgresql.ssl.conf'" >> "$PGDATA/postgresql.conf"
fi

CUSTOM_HBA="$PGDATA/pg_hba.ssl.conf"

if [ ! -f "$CUSTOM_HBA" ]; then
    cat > "$CUSTOM_HBA" <<EOF
# Local connections
local   all   all                         scram-sha-256

# SSL-only TCP connections
hostssl all   all   0.0.0.0/0             scram-sha-256
hostssl all   all   ::/0                  scram-sha-256
EOF
    chown postgres:postgres "$CUSTOM_HBA"
fi

if [ ! -L "$PGDATA/pg_hba.conf" ]; then
    rm -f "$PGDATA/pg_hba.conf"
    ln -s "$CUSTOM_HBA" "$PGDATA/pg_hba.conf"
fi

echo "PostgreSQL SSL bootstrap completed"
