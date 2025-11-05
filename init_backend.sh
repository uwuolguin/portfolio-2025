#!/bin/bash or git bash
set -e

echo "⏳ Waiting for containers to be healthy... uwu"
docker compose ps

sleep 5

echo "🚀 Running Alembic migrations... uwu"
docker compose exec backend alembic upgrade head

echo "👤 Creating admin user...uwu"
docker compose exec backend python -m app.services.testing_setup_users_data

echo "✅ Backend initialization complete uwu"
