#!/bin/bash
set -e

echo "Creating databases..."

psql -v ON_ERROR_STOP=1 --username postgres <<-EOF
    SELECT 'CREATE DATABASE temporal OWNER postgres'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal')\gexec

    SELECT 'CREATE DATABASE temporal_visibility OWNER postgres'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal_visibility')\gexec
EOF

echo "Databases created (or already existed)"