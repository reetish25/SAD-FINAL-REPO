@echo off
setlocal
echo ========================================================
echo   Leafline AI-Powered Sunflower Health Monitoring Platform
echo   Multi-Microservices Architecture Startup Script
echo ========================================================
echo.
echo Mode:
echo   1. Docker Compose (All 5 services containerized)
echo   2. Native Python/Node Development Services
echo.
set /p choice="Enter choice [1 or 2, default 1]: "
if "%choice%"=="" set choice=1

if "%choice%"=="1" (
    echo.
    echo [*] Launching Docker Compose stack...
    docker compose up --build
    goto end
)

if "%choice%"=="2" (
    echo.
    echo [1/5] Launching Plant Health Service (Port 8000)...
    powershell -NoProfile -Command "Start-Process -WorkingDirectory '%~dp0microservice-1-leafline\backend' -FilePath 'python' -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'"

    echo [2/5] Launching Weather & Environment Service (Port 8001)...
    powershell -NoProfile -Command "Start-Process -WorkingDirectory '%~dp0microservice-2-weather\backend' -FilePath 'python' -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8001'"

    echo [3/5] Launching Soil & Nutrient Service (Port 8091)...
    powershell -NoProfile -Command "Start-Process -WorkingDirectory '%~dp0microservice-3-soil' -FilePath 'python' -ArgumentList '-m', 'soil_service.server'"

    echo [4/5] Launching API Gateway & Mode B Orchestrator (Port 8080)...
    powershell -NoProfile -Command "Start-Process -WorkingDirectory '%~dp0api-gateway' -FilePath 'python' -ArgumentList '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8080'"

    echo [5/5] Launching Common Frontend (Port 5173)...
    powershell -NoProfile -Command "Start-Process -WorkingDirectory '%~dp0frontend' -FilePath 'cmd.exe' -ArgumentList '/c', 'npm', 'run', 'dev'"

    echo.
    echo ========================================================
    echo Leafline services are active:
    echo   - Common Frontend:      http://localhost:5173
    echo   - API Gateway:          http://localhost:8080/docs
    echo   - Plant Health Service: http://localhost:8000/docs
    echo   - Weather Service:      http://localhost:8001/docs
    echo   - Soil & Nutrient:      http://localhost:8091/docs
    echo ========================================================
)

:end
