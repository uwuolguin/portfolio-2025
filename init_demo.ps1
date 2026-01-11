#Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#.\init_demo.ps1
$ErrorActionPreference = "Stop"

Write-Host "Waiting for containers to be healthy..."
docker compose ps

Start-Sleep -Seconds 5

Write-Host "Running Alembic migrations..."
docker compose exec -T backend alembic upgrade head

Write-Host "Creating testing data..."
docker compose exec -T backend python -m scripts.database.seed_test_data

Write-Host "Running tests to check functionality..."
docker compose exec backend pytest app/tests/ -v

Write-Host "Backend initialization complete"