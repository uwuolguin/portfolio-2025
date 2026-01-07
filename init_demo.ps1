# Save this as init_demo.ps1 with UTF-8 encoding (no BOM)
$ErrorActionPreference = "Stop"

Write-Host "Waiting for containers to be healthy..."
docker compose ps

Start-Sleep -Seconds 5

Write-Host "Running Alembic migrations..."
docker compose exec -T backend alembic upgrade head

Write-Host "Creating cronjob..."
docker compose exec -T backend python -m scripts.database.refresh_search_index

Write-Host "Creating testing data..."
docker compose exec -T backend python -m scripts.database.seed_test_data

Write-Host "Running health test to check functionality..."
docker compose exec -T backend pytest app/tests/test_health.py -v

Write-Host "Backend initialization complete"