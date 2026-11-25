# Leafline: AI-Powered Sunflower Health Monitoring Platform
## Software Architecture and Design (SAD) — Defense Presentation Slides
### Engineering Lead: Reetish Kulkarni (`reetish25`)

---

## Slide 1: Title & Executive Overview
- **Project:** Leafline V2 — AI-Powered Sunflower Health Monitoring Platform
- **Domain:** Precision Agronomy & Distributed Computing
- **Architectural Paradigm:** Multi-Microservices Architecture with API Gateway Orchestration
- **Core Problem:** Traditional foliar disease scouting fails because crop epidemics require triangulating plant symptoms with microclimatic risk and soil nutrient balance.
- **Key Accomplishment:** Integrated 3 independent services into 1 cohesive platform supporting dual operating modes (Mode A: Independent; Mode B: Combined Orchestration).
- **Quality Status:** 59/59 Automated Tests Passing (100% Pass Rate). AWS Cloud Deployment Architecture complete and verified (Strictly non-deployed).

---

## Slide 2: The Agricultural Problem & The Disease Triangle
- **Sunflower (*Helianthus annuus*):** Critical global oilseed crop; fungal epidemics cause 20% to 80% yield loss.
- **The Plant Disease Triangle:**
  1. **Host:** Sunflower foliar health, lesion severity, cellular susceptibility.
  2. **Pathogen:** Fungal pathogens (*Alternaria helianthi*, Downy mildew, Rust, Septoria).
  3. **Environment:** Temperature, sustained relative humidity ($\ge 85\%$), leaf wetness duration.
  4. **Rhizosphere (Soil):** Macro-nutrient imbalances (excess nitrogen weakens cell walls; potassium deficiency impairs defense).
- **Why a Monolith or Single Service Fails:**
  - Diagnosing an infected leaf does not predict whether tomorrow's rain will explode the epidemic.
  - Soil testing labs have different operational cadences than automated weather forecasting.
  - Heavy PyTorch computer vision models require isolated compute scaling from lightweight I/O services.

---

## Slide 3: Microservice Decomposition & Bounded Contexts
- **Microservice 1: Plant Health (`:8000`)**
  - PyTorch Deep Learning: MobileNetV2 (~180ms), EfficientNetB0 (~310ms), Xception (~640ms).
  - Explainable AI: Grad-CAM lesion saliency mapping & canopy infection area quantification.
  - Owns `leafline.db` (users, scans, pesticide protocols, feedback).
- **Microservice 2: Weather & Environment (`:8001`)**
  - Open-Meteo external sync & local IoT sensor telemetry ingestion.
  - Alternaria Epidemiology Engine: Daily Severity Values (DSV) & cumulative EDPS scoring.
  - Automated PDF spray advisory reports; owns `environment_weather.db`.
- **Microservice 3: Soil & Nutrient (`:8091`)**
  - Agronomic boundary checks (NS-BR-01..08); N-P-K-pH-OC fertility rating (`GOOD`/`FAIR`/`POOR`).
  - Immutable audit trail via SQLite trigger (`sample_audit_trigger`); owns `soil.db`.
- **API Gateway & Orchestrator (`:8080`)**
  - Mode A reverse proxy routing; Mode B non-blocking async fan-out (`asyncio.gather`).
  - Computes composite **Sunflower Health Index (SHI)** with dynamic degradation re-normalization.
- **Common Frontend (`:5173` / `:80`)**
  - React 18, Vite, Tailwind CSS; unified cluster health monitor and data provenance badges.

---

## Slide 4: Dual Operational Modes (Mode A vs Mode B)
- **Mode A: Independent Service Operation**
  - Complete operational independence.
  - A farmer can run a foliar disease scan on `:8000` without Weather or Soil being online.
  - An agronomist can check 7-day EDPS risk on `:8001` without uploading images.
  - A soil lab technician can record NPK tests on `:8091` without external dependencies.
- **Mode B: Combined Cross-Domain Orchestration**
  - Single composite endpoint `/api/v1/combined/assess` on API Gateway (`:8080`).
  - Concurrent async fan-out to all 3 microservices with a 3.0-second timeout.
  - Evaluates cross-domain risk synergies (e.g., *Alternaria* + High EDPS = Immediate Systemic Fungicide Alert).
  - Graceful degradation: returns partial results and degrades SHI formula if any service fails.

---

## Slide 5: The Sunflower Health Index (SHI) Formula
$$\text{SHI} = 100 - \left( w_{\text{foliar}} \cdot P_{\text{foliar}} + w_{\text{weather}} \cdot P_{\text{weather}} + w_{\text{soil}} \cdot P_{\text{soil}} \right)$$

- **Baseline Normalized Weights:** $w_{\text{foliar}} = 0.50$, $w_{\text{weather}} = 0.25$, $w_{\text{soil}} = 0.25$.
- **Dynamic Re-normalization Under Faults:**
  $$w_i' = \frac{w_i}{\sum_{j \in \text{Active}} w_j}$$
  - If Soil Service is down: $w_{\text{foliar}}' = 0.667$, $w_{\text{weather}}' = 0.333$.
  - Guarantees SHI remains mathematically bounded between $0.0$ and $100.0$.

---

## Slide 6: Database Isolation Architecture
- **Strict Database-per-Service Principle:**
  - `leafline.db`: Owned exclusively by Plant Health.
  - `environment_weather.db`: Owned exclusively by Weather & Environment.
  - `soil.db`: Owned exclusively by Soil & Nutrient.
- **Zero Cross-Service Table Joins or Foreign Keys:**
  - Cross-service data is synthesized ephemerally in the Gateway layer.
  - Prevents tight schema coupling and enables independent database migrations.
- **Data Integrity Feature:**
  - Soil service uses an append-only SQLite trigger (`sample_audit_trigger`) logging changes into `sample_audit_log` to prevent regulatory tampering.

---

## Slide 7: Artificial Intelligence & Agronomic Models
- **Foliar Vision Models:**
  - MobileNetV2 (eval acc ~96.2%, 8.9MB): Lightweight edge deployment.
  - EfficientNetB0 (eval acc ~97.8%, 15.9MB): Balanced compound scaling.
  - Xception (eval acc ~98.4%, 81.6MB): Deep separable cross-channel convolutions.
- **Explainable AI (XAI):**
  - Grad-CAM heatmap overlays visually verify the model focuses on necrotic lesions rather than leaf veins or background soil.
- **Alternaria EDPS Risk Algorithm:**
  - Daily Severity Values (DSV 0-4) calculated from bivariate temperature and hours of $RH \ge 85\%$.
  - 7-day cumulative DSV threshold: $\ge 18$ triggers urgent fungicide alert.

---

## Slide 8: Automated Verification & Test Results
- **Harness:** `run_all_tests.py` executing 6 automated test suites.
- **Results:**
  - Suite 1 (Soil Rules NS-BR-01..08): **18/18 PASS**
  - Suite 2 (Plant Health PyTorch ML Contracts): **4/4 PASS**
  - Suite 3 (Plant Health FastAPI Endpoints): **9/9 PASS**
  - Suite 4 (Weather Microclimate & EDPS): **19/19 PASS**
  - Suite 5 (API Gateway Mode B Synthesis): **4/4 PASS**
  - Suite 6 (Platform E2E Cross-Service Workflows): **5/5 PASS**
  - **TOTAL: 59 Passed, 0 Failed (100% Success Rate)**.
- Zero mocked or fabricated numbers; verified on real local runtimes.

---

## Slide 9: DevOps, Containerization & CI/CD Pipeline
- **Docker Multi-Stage Containerization:**
  - All 5 components containerized (`plant-health`, `weather-service`, `soil-service`, `api-gateway`, `frontend`).
  - Root `docker-compose.yml` validated with isolated bridge network (`leafline-network`), named persistent volumes, and healthchecks.
- **GitHub Actions CI/CD:**
  - `.github/workflows/ci.yml`: Static analysis (`flake8`), parallel service testing, gateway degradation testing, and frontend production build.
  - `.github/workflows/docker-publish.yml`: Multi-stage image building, semantic tagging (`:latest`, `:semver`, `:${{ github.sha }}`), and automated push to Docker Hub using GitHub Secrets.
- **Git Repository Structure:**
  - Base commit `03e8668` preserved from the original AWS-deployed service.
  - Branching model: `main`, `development`, `feature/microservices-integration`.

---

## Slide 10: AWS Cloud Readiness & Defense Conclusion
- **Strict Cloud Boundary:**
  - In strict compliance with guidelines, **AWS deployment remains uncompleted**.
  - No cloud resources were provisioned, billed, or modified.
- **Complete Architecture Specification:**
  - Route 53 + CloudFront CDN + ALB (HTTPS termination & path routing).
  - ECS Fargate private subnets with auto-scaling compute tasks.
  - EFS persistent volume mounts for SQLite databases.
  - S3 encrypted bucket for foliar image uploads.
- **Defense Summary:**
  - Leafline successfully bridges advanced computer vision, meteorological epidemiology, and soil chemistry into an enterprise-ready, fault-tolerant distributed system.
