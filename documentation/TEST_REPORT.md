# Leafline Platform — Automated Test Execution Report

- **Execution Timestamp:** 2026-11-24T15:44:53.095269+00:00
- **Environment:** Windows / Python 3.14 / PyTorch 2.13 CPU / FastAPI / SQLite
- **Total Suites:** 6
- **Suites Passed:** 6
- **Suites Failed:** 0
- **Success Rate:** 100.0%

## Test Suite Breakdown

| # | Component / Suite | Scope | Status | Duration |
|---|---|---|---|---|
| 1 | Soil & Nutrient Service: Unit & Business Rules (NS-BR-01..08) | Unit / Business Rules | ✅ PASS | 0.15s |
| 2 | Plant Health Service: PyTorch ML Inference & Severity (MobileNetV2, EfficientNetB0, Xception) | ML Inference / Grad-CAM | ✅ PASS | 11.02s |
| 3 | Plant Health Service: REST API, Auth, Pesticide Versioning & Scans | REST API / Auth / SQLite | ✅ PASS | 14.36s |
| 4 | Environment & Weather Service: Open-Meteo, EDPS Alternaria Risk & Sensors | Atmospheric & Epidemiological | ✅ PASS | 10.02s |
| 5 | API Gateway & Orchestrator: Reverse Proxy Routing, Mode B Synthesis & Degradation | Gateway / Mode B Orchestrator | ✅ PASS | 8.54s |
| 6 | Platform E2E Integration: Cross-Domain Synergy, Partial Failures & Rule Validation | E2E Cross-Service Integration | ✅ PASS | 2.05s |

## Detailed Execution Logs

### 1. Soil & Nutrient Service: Unit & Business Rules (NS-BR-01..08)

```
No stdout
```

### 2. Plant Health Service: PyTorch ML Inference & Severity (MobileNetV2, EfficientNetB0, Xception)

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\kulka\OneDrive\Desktop\SAD-FINAL
plugins: anyio-4.13.0, Faker-40.37.0, hydra-core-1.3.4, langsmith-0.14.1
collecting ... collected 4 items

microservice-1-leafline/backend/tests/test_inference.py::test_inference_predict_contract PASSED [ 25%]
microservice-1-leafline/backend/tests/test_inference.py::test_inference_stability PASSED [ 50%]
microservice-1-leafline/backend/tests/test_inference.py::test_severity_segmentation_contract PASSED [ 75%]
microservice-1-leafline/backend/tests/test_inference.py::test_project_risk_contract PASSED [100%]

============================== warnings summary ===============================
microservice-1-leafline/backend/tests/test_inference.py::test_project_risk_contract
  C:\Users\kulka\OneDrive\Desktop\SAD-FINAL\microservice-1-leafline\backend\app\inference.py:441: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 4 passed, 1 warning in 8.28s =========================

```

### 3. Plant Health Service: REST API, Auth, Pesticide Versioning & Scans

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\kulka\OneDrive\Desktop\SAD-FINAL
plugins: anyio-4.13.0, Faker-40.37.0, hydra-core-1.3.4, langsmith-0.14.1
collecting ... collected 9 items

microservice-1-leafline/backend/tests/test_api.py::test_health_endpoint PASSED [ 11%]
microservice-1-leafline/backend/tests/test_api.py::test_login_flow PASSED [ 22%]
microservice-1-leafline/backend/tests/test_api.py::test_generic_login_errors PASSED [ 33%]
microservice-1-leafline/backend/tests/test_api.py::test_scan_submission_and_flow PASSED [ 44%]
microservice-1-leafline/backend/tests/test_api.py::test_versioned_pesticide_table PASSED [ 55%]
microservice-1-leafline/backend/tests/test_api.py::test_admin_user_provisioning_and_forced_password_change PASSED [ 66%]
microservice-1-leafline/backend/tests/test_api.py::test_deactivate_instead_of_delete PASSED [ 77%]
microservice-1-leafline/backend/tests/test_api.py::test_forgot_and_reset_password_flow PASSED [ 88%]
microservice-1-leafline/backend/tests/test_api.py::test_audit_logs_and_csv_exports PASSED [100%]

============================== warnings summary ===============================
microservice-1-leafline\backend\app\main.py:40
  C:\Users\kulka\OneDrive\Desktop\SAD-FINAL\microservice-1-leafline\backend\app\main.py:40: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

..\..\..\AppData\Roaming\Python\Python314\site-packages\fastapi\applications.py:4681
  C:\Users\kulka\AppData\Roaming\Python\Python314\site-packages\fastapi\applications.py:4681: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about
```

### 4. Environment & Weather Service: Open-Meteo, EDPS Alternaria Risk & Sensors

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\kulka\OneDrive\Desktop\SAD-FINAL
plugins: anyio-4.13.0, Faker-40.37.0, hydra-core-1.3.4, langsmith-0.14.1
collecting ... collected 19 items

microservice-2-weather/backend/tests/test_alternaria_engine.py::test_calculate_complete_day PASSED [  5%]
microservice-2-weather/backend/tests/test_alternaria_engine.py::test_missing_input_is_incomplete PASSED [ 10%]
microservice-2-weather/backend/tests/test_assessment.py::test_assessment_after_sensor_reading PASSED [ 15%]
microservice-2-weather/backend/tests/test_service.py::test_health PASSED [ 21%]
microservice-2-weather/backend/tests/test_service.py::test_local_dev_token PASSED [ 26%]
microservice-2-weather/backend/tests/test_service.py::test_weather_current_persists PASSED [ 31%]
microservice-2-weather/backend/tests/test_service.py::test_forecast PASSED [ 36%]
microservice-2-weather/backend/tests/test_service.py::test_sensor_registration_and_ingestion PASSED [ 42%]
microservice-2-weather/backend/tests/test_service.py::test_operator_scope PASSED [ 47%]
microservice-2-weather/backend/tests/test_service.py::test_missing_weather_token PASSED [ 52%]
microservice-2-weather/backend/tests/test_service.py::test_user_registration_and_login PASSED [ 57%]
microservice-2-weather/backend/tests/test_service.py::test_organization_approval_workflow PASSED [ 63%]
microservice-2-weather/backend/tests/test_service.py::test_organization_rejected_workflow PASSED [ 68%]
microservice-2-weather/backend/tests/test_service.py::test_pdf_report_generation PASSED [ 73%]
microservice-2-weather/backend/tests/test_weather.py::test_weather_health_endpoints PASSED [ 78%]
microservice-2-weather/backend/tests/test_weather.py::test_dev_token_issuance PASSED [ 84%]
microservice-2-weather/backend/tests/test_weather.py::test_growth_stages_endpoint PASSED [ 8
```

### 5. API Gateway & Orchestrator: Reverse Proxy Routing, Mode B Synthesis & Degradation

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\kulka\OneDrive\Desktop\SAD-FINAL
plugins: anyio-4.13.0, Faker-40.37.0, hydra-core-1.3.4, langsmith-0.14.1
collecting ... collected 4 items

api-gateway/tests/test_gateway.py::test_gateway_health PASSED            [ 25%]
api-gateway/tests/test_gateway.py::test_synthesis_full_success PASSED    [ 50%]
api-gateway/tests/test_gateway.py::test_synthesis_partial_soil_failure PASSED [ 75%]
api-gateway/tests/test_gateway.py::test_synthesis_critical_cross_domain_rule PASSED [100%]

============================== 4 passed in 6.68s ==============================

```

### 6. Platform E2E Integration: Cross-Domain Synergy, Partial Failures & Rule Validation

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\kulka\OneDrive\Desktop\SAD-FINAL
plugins: anyio-4.13.0, Faker-40.37.0, hydra-core-1.3.4, langsmith-0.14.1
collecting ... collected 5 items

tests/test_e2e_integration.py::test_e2e_mode_b_full_orchestration PASSED [ 20%]
tests/test_e2e_integration.py::test_e2e_mode_b_graceful_degradation_weather_down PASSED [ 40%]
tests/test_e2e_integration.py::test_soil_rules_boundary_enforcement PASSED [ 60%]
tests/test_e2e_integration.py::test_soil_health_classification_logic PASSED [ 80%]
tests/test_e2e_integration.py::test_cross_domain_synergy_high_risk_rule PASSED [100%]

============================== 5 passed in 0.21s ==============================

```

