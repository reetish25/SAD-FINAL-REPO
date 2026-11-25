# Leafline — AI-Powered Sunflower Health Monitoring Platform

Leafline is an enterprise Software Architecture and Design (SAD) agricultural diagnosis and disease surveillance platform designed for sunflower growers, agronomists, and agricultural researchers. It integrates three independent microservices through a unified API Gateway and responsive React frontend, operating in two distinct architectural modes.

---

## 1. System Architecture & Operating Modes

The platform supports two core operating modes:

### Mode A: Independent Operation
Each microservice functions autonomously with its own database, business logic, and dedicated REST API:
- **Microservice 1: Plant Health (`:8000`)**: Deep-learning foliar disease classification (MobileNetV2, EfficientNetB0, Xception), Grad-CAM lesion segmentation, canopy severity ratio, and versioned pesticide protocols. Owns SQLite database `leafline.db`.
- **Microservice 2: Environment & Weather (`:8001`)**: Live atmospheric observation via Open-Meteo, 7-day canopy forecasts, IoT sensor telemetry, and the Alternaria leaf blight Epidemiological Disease Pressure Score (EDPS). Owns SQLite database `environment_weather.db`.
- **Microservice 3: Soil & Nutrient (`:8091`)**: Laboratory soil test ingestion (NPK, pH, moisture, EC, OM), pure agronomic boundary validation, append-only SQLite triggers, and GOOD / FAIR / POOR soil health rating. Owns SQLite database `soil.db`.

### Mode B: Combined Cross-Service Operation
- **API Gateway & Orchestrator (`:8080`)**: Receives multi-domain requests (`POST /api/combined/assess`), concurrently queries Plant Health, Weather, and Soil microservices via async HTTP fan-out, synthesizes a holistic **Sunflower Health Index (SHI, 0–100%)**, correlates cross-domain risks (e.g., foliar lesions amplified by microclimate humidity), and returns consolidated action plans with service provenance metadata. Gracefully handles partial failures with degraded responses.
- **Common Frontend (`:5173`)**: Single unified web portal built in React 18, Vite, and Tailwind CSS. Features role-based access control (Grower, Agronomist, Operator, Admin), an Architecture Overview Hub, dedicated views for all three microservices, and an interactive Mode B Combined Assessment dashboard.

---

## 2. Directory Layout

```
SAD-FINAL/
├── api-gateway/                      # FastAPI Reverse Proxy & Mode B Orchestrator (:8080)
│   ├── config.py                     # Service URLs and timeout configurations
│   ├── main.py                       # Routing and proxy endpoints
│   ├── orchestrator.py               # Cross-service fan-out & agronomic synthesis
│   ├── requirements.txt              # FastAPI, httpx, uvicorn, pydantic
│   ├── Dockerfile                    # Containerization specification
│   └── tests/                        # Gateway and fallback degradation tests
├── frontend/                         # Unified React 18 + Vite + Tailwind Frontend (:5173)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── HubOverview.jsx       # Platform Hub & live service status
│   │   │   ├── UserPipeline.jsx      # Plant Health 5-step diagnostic workflow
│   │   │   ├── WeatherDashboard.jsx  # Weather, forecast & EDPS risk view
│   │   │   ├── SoilDashboard.jsx     # Soil NPK test & health rating view
│   │   │   ├── CombinedDashboard.jsx # Mode B cross-service assessment view
│   │   │   └── admin/                # Platform management console
│   ├── Dockerfile & nginx.conf       # Multi-stage production container build
│   └── package.json
├── microservice-1-leafline/          # Plant Health Microservice (:8000)
│   └── backend/
│       ├── app/                      # FastAPI routes, PyTorch inference, models, auth
│       ├── models/                   # Registered PyTorch weights (MobileNetV2, EfficientNetB0, Xception)
│       ├── tests/                    # Inference contract and REST API tests
│       └── Dockerfile                # PyTorch CPU containerization
├── microservice-2-weather/           # Environment & Weather Microservice (:8001)
│   └── backend/
│       ├── app/                      # Weather routers, Alternaria engine, APScheduler
│       ├── tests/                    # Unit, assessment, and endpoint tests
│       └── Dockerfile                # FastAPI containerization
├── microservice-3-soil/              # Soil & Nutrient Microservice (:8091)
│   ├── soil_service/                 # Pure Python stdlib HTTP service & rules engine
│   ├── static/                       # Independent static web interface
│   ├── tests/                        # Agronomic rule boundary & validation tests
│   └── Dockerfile                    # Lightweight Python slim containerization
├── tests/                            # Platform-wide E2E Cross-Service Integration Tests
├── documentation/                    # Architecture reports, test evidence, specifications
├── .github/workflows/
│   ├── ci.yml                        # Automated CI workflow (lint, test, build)
│   └── docker-publish.yml            # Automated Docker Hub build and publish
├── docker-compose.yml                # Multi-service local container orchestrator
└── run_all_tests.py                  # Automated test runner across all 6 test suites
```

---

## 3. Quick Start & Execution

### Running Automated Test Suite
Execute all 6 test suites (59 test assertions) with a single command:
```bash
python run_all_tests.py
```
This generates the full execution report at `documentation/TEST_REPORT.md`.

### Running Locally with Docker Compose
Start the complete 5-container cluster (Plant Health, Weather, Soil, API Gateway, and Common Frontend):
```bash
docker compose up --build
```
Once started, access the services:
- **Common Frontend Portal:** [http://localhost:5173](http://localhost:5173)
- **API Gateway & Swagger Docs:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **Plant Health Independent API:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Weather Service Independent API:** [http://localhost:8001/docs](http://localhost:8001/docs)
- **Soil Service Independent Web App:** [http://localhost:8091](http://localhost:8091)

---

## 4. Git Branching Strategy & CI/CD Pipeline

The repository follows a Gitflow-inspired branching model:
- `main`: Production release branch. Protected. Triggers Docker image build and publishing to Docker Hub.
- `development`: Active integration branch. Receives merged feature branches.
- `feature/*`: Task-specific feature branches (e.g. `feature/microservices-integration`).

### GitHub Actions Workflows
- **`ci.yml`**: Triggers on push and pull requests to `main` and `development`. Executes Flake8 static analysis, Soil Service unit tests, Weather Service tests, Plant Health inference and API tests, API Gateway resilience tests, and Common Frontend build validation.
- **`docker-publish.yml`**: Builds production container images for all three microservices, the API gateway, and frontend, tagging each with immutable commit SHA, `latest`, and semver release tags. Pushes to Docker Hub when `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets are configured.

---

## 5. Security & Credentials
- All secrets, database connection strings, and tokens are injected via environment variables.
- Sensitive files (`.env`, `*.db`, `venv/`, `node_modules/`, `*.pt`) are strictly excluded via `.gitignore` and `.dockerignore`.
- Cross-service database access is strictly forbidden; services interact exclusively through documented REST contracts.
