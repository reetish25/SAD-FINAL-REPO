# Leafline Multi-Microservices Platform Startup Script
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  Leafline Multi-Microservices Platform Startup" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Modes:"
Write-Host "  1. Docker Compose (Default - all 5 services containerized)"
Write-Host "  2. Native Local Processes (Python + Node.js)"
Write-Host ""

$mode = Read-Host "Select mode [1 or 2, default 1]"
if ([string]::IsNullOrWhiteSpace($mode)) { $mode = "1" }

$root = $PSScriptRoot

if ($mode -eq "1") {
    Write-Host "[*] Starting Docker Compose cluster..." -ForegroundColor Cyan
    docker compose up --build
} elseif ($mode -eq "2") {
    Write-Host "[1/5] Starting Plant Health Service on :8000..." -ForegroundColor Cyan
    Start-Process -WorkingDirectory "$root\microservice-1-leafline\backend" -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"

    Write-Host "[2/5] Starting Weather Service on :8001..." -ForegroundColor Cyan
    Start-Process -WorkingDirectory "$root\microservice-2-weather\backend" -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"

    Write-Host "[3/5] Starting Soil Service on :8091..." -ForegroundColor Cyan
    Start-Process -WorkingDirectory "$root\microservice-3-soil" -FilePath "python" -ArgumentList "-m", "soil_service.server"

    Write-Host "[4/5] Starting API Gateway on :8080..." -ForegroundColor Cyan
    Start-Process -WorkingDirectory "$root\api-gateway" -FilePath "python" -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"

    Write-Host "[5/5] Starting Frontend on :5173..." -ForegroundColor Cyan
    Start-Process -WorkingDirectory "$root\frontend" -FilePath "cmd.exe" -ArgumentList "/c", "npm", "run", "dev"

    Write-Host ""
    Write-Host "All Leafline services launched successfully!" -ForegroundColor Green
    Write-Host "Frontend:    http://localhost:5173"
    Write-Host "Gateway:     http://localhost:8080/docs"
    Write-Host "Plant API:   http://localhost:8000/docs"
    Write-Host "Weather API: http://localhost:8001/docs"
    Write-Host "Soil API:    http://localhost:8091/docs"
}
