#!/bin/bash
set -e

echo "Creating database role and database..."

psql -v ON_ERROR_STOP=1 --username postgres <<-EOF
    DO
    \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'portfolio') THEN
            CREATE DATABASE portfolio OWNER "postgres";
        END IF;
    END
    \$\$
EOF

echo "database created (or already existed)"

