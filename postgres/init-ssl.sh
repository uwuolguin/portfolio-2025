#!/bin/bash
# =============================================================================
# PostgreSQL SSL Bootstrap - Config Only
#
# WHY TWO DIFFERENT APPROACHES FOR THE TWO CONFIG FILES:
#
# postgresql.conf — supports native includes via the "include" directive.
#   This means we can leave the original file untouched and just append
#   a single line that tells PostgreSQL to also load our ssl config file.
#   Our custom file (postgresql.ssl.conf) only contains ssl-related settings,
#   keeping concerns separated and making the original conf easy to diff/audit.
#   If the include line already exists, we skip it — making this idempotent.
#
# pg_hba.conf — does NOT support includes. It is read top-to-bottom as a single
#   flat file with no way to compose from multiple sources. This means we cannot
#   "append" to it safely — order matters (first match wins), and appending ssl
#   rules after a catch-all "host all all 0.0.0.0/0" would make them unreachable.
#   So instead, we write our complete authoritative version (pg_hba.ssl.conf)
#   and replace pg_hba.conf entirely with a symlink pointing to it.
#   The symlink approach (vs. overwriting) makes it explicit that this file is
#   managed — ls -la will show exactly where it points, and it survives
#   scenarios where PostgreSQL or init scripts try to recreate the original.
#
# ENCRYPTION POLICY:
#   Both encrypted and unencrypted TCP connections are accepted.
#   Encryption is enforced at the application layer — the backend connects
#   with sslmode=require, while Temporal connects without SSL by design.
#   All traffic is internal to the Kubernetes cluster network (10.42.x.x).
# =============================================================================
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
local   all             all                         scram-sha-256
host    all             all   127.0.0.1/32          scram-sha-256
host    all             all   ::1/128               scram-sha-256
# Both encrypted and unencrypted TCP connections are accepted.
# Encryption is enforced at the application layer — the backend connects
# with sslmode=require, while Temporal connects without SSL by design.
# All traffic is internal to the Kubernetes cluster network (10.42.x.x).
host    all             all   0.0.0.0/0             scram-sha-256
host    all             all   ::/0                  scram-sha-256
hostssl all             all   0.0.0.0/0             scram-sha-256
hostssl all             all   ::/0                  scram-sha-256
# Replication — SSL required
hostssl replication     all   0.0.0.0/0             scram-sha-256
hostssl replication     all   ::/0                  scram-sha-256
EOF
    chown postgres:postgres "$CUSTOM_HBA"
fi

if [ ! -L "$PGDATA/pg_hba.conf" ]; then
    rm -f "$PGDATA/pg_hba.conf"
    ln -s "$CUSTOM_HBA" "$PGDATA/pg_hba.conf"
fi

echo "PostgreSQL SSL bootstrap completed"