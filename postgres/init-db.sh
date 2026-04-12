#!/bin/bash
set -e

echo "Creating databases..."
# ========================================================
# POSTGRESQL IDEMPOTENT DATABASE CREATION - TECHNICAL EXPLANATION
# ========================================================
#
# PROBLEM:
#   PostgreSQL does NOT support "CREATE DATABASE IF NOT EXISTS".
#   Running CREATE DATABASE on an existing DB causes an error.
#
# SOLUTION:
#   Use a SELECT + \gexec trick (very common in Docker entrypoints,
#   Temporal, Supabase, etc.)
#
# HOW IT WORKS - STEP BY STEP:
#
# 1. Here-document (<<-EOF ... EOF):
#    - <<-EOF  : starts a here-document. The '-' allows stripping leading tabs.
#    - Everything between <<-EOF and the closing EOF is sent as stdin to psql.
#    - Using single quotes 'EOSQL' (or <<- 'EOF') prevents bash variable expansion, everything inside is treated as plain text.
#
# 2. The SELECT query:
#    - Checks pg_database system catalog to see if the DB already exists.
#    - If DB exists     → WHERE condition is FALSE → returns 0 rows
#    - If DB does not exist → WHERE condition is TRUE → returns 1 row
#      containing the text: 'CREATE DATABASE temporal OWNER postgres'
#
# 3. \gexec  ← THIS IS THE BLACK MAGIC
#    - \gexec is a psql meta-command (not SQL).
#    - It takes every value from the last query result and EXECUTES IT as SQL.
#    - If SELECT returned 0 rows → \gexec does nothing.
#    - If SELECT returned 1 row  → \gexec runs: CREATE DATABASE temporal OWNER postgres;
#    - This makes the whole operation idempotent (safe to run multiple times).
#
# 4. -v ON_ERROR_STOP=1
#    - Tells psql to stop immediately if any SQL command fails.
#    - Without it, psql would continue even after errors.
#
# ========================================================
psql -v ON_ERROR_STOP=1 --username postgres <<-EOF
    SELECT 'CREATE DATABASE temporal OWNER postgres'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal')\gexec

    SELECT 'CREATE DATABASE temporal_visibility OWNER postgres'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal_visibility')\gexec
EOF

echo "Databases created (or already existed)"