#docker-compose exec backend bash /app/scripts/deployment/init_demo.sh
#!/bin/bash
set -e

trap 'echo "❌ Error occurred. Press Enter to exit."; read' ERR

echo "⏳ Waiting for containers to be healthy... uwu"
docker compose ps

sleep 5

echo "🚀 Running Alembic migrations... uwu"
docker compose exec backend alembic upgrade head

echo "👤 Creating cronjob... uwu"
docker compose exec backend python -m scripts.database.refresh_search_index

echo "👤 Creating testing data... uwu"
docker compose exec backend python -m scripts.database.seed_test_data

echo "🩺 Running health test to check functionality... uwu"
docker compose exec backend pytest app/tests/test_health.py -v

echo " Backend initialization complete uwu"
echo
read -p "Press Enter to exit..."
