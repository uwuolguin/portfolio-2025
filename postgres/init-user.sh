#!/bin/bash
set -e

echo "Creating database role and database..."

psql -v ON_ERROR_STOP=1 --username postgres <<-EOF
    DO
    \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'user') THEN
            CREATE ROLE "user"
            WITH LOGIN SUPERUSER PASSWORD 'pass';
        ELSE
            ALTER ROLE "user" WITH SUPERUSER;
        END IF;

        IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'portfolio') THEN
            CREATE DATABASE portfolio OWNER "user";
        END IF;
    END
    \$\$
EOF

echo "User and database created (or already existed)"

