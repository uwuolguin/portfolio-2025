#Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#.\init_demo.ps1
$ErrorActionPreference = "Stop"

Write-Host "⏳ Waiting for containers to be healthy... uwu"
docker compose ps

Start-Sleep -Seconds 5

Write-Host "🚀 Running Alembic migrations... uwu"
docker compose exec backend alembic upgrade head

Write-Host "📅 Creating cronjob... uwu"
docker compose exec backend python -m scripts.database.refresh_search_index

Write-Host "🧪 Creating testing data... uwu"
docker compose exec backend python -m scripts.database.seed_test_data

Write-Host "🔬 Running health test to check functionality... uwu"
docker compose exec backend pytest app/tests/test_health.py -v

Write-Host "✅ Backend initialization complete uwu"