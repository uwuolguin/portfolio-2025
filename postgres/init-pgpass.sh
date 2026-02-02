#!/bin/bash
set -e
# Exit immediately if any command fails

# Resolve the home directory of the OS user "postgres"
# (usually /var/lib/postgresql or /var/lib/pgsql depending on distro)
POSTGRES_HOME=$(eval echo ~postgres)

# Create (or overwrite) the .pgpass file in postgres' home directory
# .pgpass stores credentials for passwordless connections
cat > "$POSTGRES_HOME/.pgpass" <<EOF
localhost:5432:*:postgres:${POSTGRES_PASSWORD}
127.0.0.1:5432:*:postgres:${POSTGRES_PASSWORD}
EOF

# Explanation of .pgpass format (colon-separated):
# hostname:port:database:username:password
#
# - hostname: localhost or 127.0.0.1
# - port: 5432 (default PostgreSQL port)
# - database: * (any database)
# - username: postgres
# - password: value from $POSTGRES_PASSWORD env var

# PostgreSQL requires .pgpass to have strict permissions
# Otherwise it will be ignored
chmod 600 "$POSTGRES_HOME/.pgpass"

# Ensure the file is owned by the postgres OS user
chown postgres:postgres "$POSTGRES_HOME/.pgpass"
