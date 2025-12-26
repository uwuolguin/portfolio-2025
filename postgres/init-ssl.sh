#!/bin/bash
set -e

echo "Starting PostgreSQL SSL bootstrap..."

SSL_DIR="$PGDATA/ssl"

if [ ! -f "$SSL_DIR/server.crt" ]; then
    echo "Generating SSL certificates..."
    mkdir -p "$SSL_DIR"
    openssl req -new -x509 -days 3650 -nodes \
        -out "$SSL_DIR/server.crt" \
        -keyout "$SSL_DIR/server.key" \
        -subj "/CN=postgres"

    chown postgres:postgres "$SSL_DIR/server.crt" "$SSL_DIR/server.key"
    chmod 600 "$SSL_DIR/server.key"
    chmod 644 "$SSL_DIR/server.crt"
    echo "SSL certificates created"
else
    echo "SSL certificates already exist, skipping generation"
fi

CUSTOM_CONF="$PGDATA/postgresql.ssl.conf"

if [ ! -f "$CUSTOM_CONF" ]; then
    echo "Creating SSL file configuration..."
    cat > "$CUSTOM_CONF" <<EOF
ssl_cert_file = 'ssl/server.crt'
ssl_key_file  = 'ssl/server.key'
ssl_min_protocol_version = 'TLSv1.2'
EOF
    chown postgres:postgres "$CUSTOM_CONF"
    echo "SSL file configuration created"
fi

if ! grep -q "include.*postgresql.ssl.conf" "$PGDATA/postgresql.conf"; then
    echo "include = 'postgresql.ssl.conf'" >> "$PGDATA/postgresql.conf"
    echo "SSL config included in postgresql.conf"
fi

CUSTOM_HBA="$PGDATA/pg_hba.ssl.conf"

if [ ! -f "$CUSTOM_HBA" ]; then
    echo "Creating authentication configuration..."
    cat > "$CUSTOM_HBA" <<EOF
# Local connections
local   all   all                         scram-sha-256

# Non-SSL TCP allowed (PoC / STARTTLS-style)
host    all   all   0.0.0.0/0             scram-sha-256
host    all   all   ::/0                  scram-sha-256

# SSL connections
hostssl all   all   0.0.0.0/0             scram-sha-256
hostssl all   all   ::/0                  scram-sha-256
EOF
    chown postgres:postgres "$CUSTOM_HBA"
    echo "Authentication configuration created"
fi

if [ ! -L "$PGDATA/pg_hba.conf" ]; then
    rm -f "$PGDATA/pg_hba.conf"
    ln -s "$CUSTOM_HBA" "$PGDATA/pg_hba.conf"
    echo "pg_hba.conf linked"
fi

echo "PostgreSQL SSL bootstrap completed"
