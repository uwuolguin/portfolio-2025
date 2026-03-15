#!/bin/bash
set -e

echo "Creating databases..."

psql -v ON_ERROR_STOP=1 --username postgres <<-EOF
    DO
    \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'portfolio') THEN
            CREATE DATABASE portfolio OWNER "postgres";
        END IF;
        IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal') THEN
            CREATE DATABASE temporal OWNER "postgres";
        END IF;
        IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal_visibility') THEN
            CREATE DATABASE temporal_visibility OWNER "postgres";
        END IF;
    END
    \$\$
EOF

echo "Databases created (or already existed)"