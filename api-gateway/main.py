import time
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional
import httpx
from fastapi import FastAPI, Request, Response, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from orchestrator import (
    fetch_plant_health,
    fetch_weather_environment,
    fetch_soil_nutrients,
    synthesize_crop_health
)

app = FastAPI(
    title=settings.APP_NAME,
    description="Unified API Gateway, Reverse Proxy and Mode B Cross-Service Orchestrator for the Leafline Sunflower Platform",
    version=settings.VERSION
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System Health"])
@app.get("/api/health", tags=["System Health"])
async def system_health():
    """
    Comprehensive multi-service healthcheck.
    Pings all 3 microservices and reports their operational status and latencies.
    """
    start = time.time()
    services_status = {}
    
    async with httpx.AsyncClient() as client:
        # Check Plant Health
        t0 = time.time()
        try:
            r1 = await client.get(f"{settings.PLANT_SERVICE_URL}/api/health", timeout=2.0)
            services_status["plant_health"] = {
                "status": "UP" if r1.status_code == 200 else "DEGRADED",
                "code": r1.status_code,
                "latency_ms": int((time.time() - t0) * 1000),
                "endpoint": settings.PLANT_SERVICE_URL
            }
        except Exception as e:
            services_status["plant_health"] = {
                "status": "DOWN",
                "latency_ms": int((time.time() - t0) * 1000),
                "error": str(e),
                "endpoint": settings.PLANT_SERVICE_URL
            }

        # Check Weather Service
        t0 = time.time()
        try:
            r2 = await client.get(f"{settings.WEATHER_SERVICE_URL}/api/health", timeout=2.0)
            services_status["weather_environment"] = {
                "status": "UP" if r2.status_code == 200 else "DEGRADED",
                "code": r2.status_code,
                "latency_ms": int((time.time() - t0) * 1000),
                "endpoint": settings.WEATHER_SERVICE_URL
            }
        except Exception as e:
            services_status["weather_environment"] = {
                "status": "DOWN",
                "latency_ms": int((time.time() - t0) * 1000),
                "error": str(e),
                "endpoint": settings.WEATHER_SERVICE_URL
            }

        # Check Soil Service
        t0 = time.time()
        try:
            r3 = await client.get(f"{settings.SOIL_SERVICE_URL}/health", timeout=2.0)
            services_status["soil_nutrient"] = {
                "status": "UP" if r3.status_code == 200 else "DEGRADED",
                "code": r3.status_code,
                "latency_ms": int((time.time() - t0) * 1000),
                "endpoint": settings.SOIL_SERVICE_URL
            }
        except Exception as e:
            services_status["soil_nutrient"] = {
                "status": "DOWN",
                "latency_ms": int((time.time() - t0) * 1000),
                "error": str(e),
                "endpoint": settings.SOIL_SERVICE_URL
            }

    all_up = all(s["status"] == "UP" for s in services_status.values())
    any_up = any(s["status"] == "UP" for s in services_status.values())
    
    return {
        "status": "HEALTHY" if all_up else ("DEGRADED" if any_up else "CRITICAL"),
        "gateway_version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_check_time_ms": int((time.time() - start) * 1000),
        "microservices": services_status
    }


# ==============================================================================
# MODE B: COMBINED CROP-HEALTH ORCHESTRATION ENDPOINT
# ==============================================================================
@app.post("/api/combined/assess", tags=["Combined Orchestration"])
async def combined_crop_health_assessment(
    request: Request,
    image: Optional[UploadFile] = File(None),
    field_id: str = Form("field-demo"),
    plant_label: Optional[str] = Form("Sunflower Field Sector 1"),
    crop_stage: str = Form("flowering"),
    latitude: float = Form(12.9716),
    longitude: float = Form(77.5946),
    pdi: float = Form(15.0)
):
    """
    Mode B Orchestration:
    Coordinates synchronous data retrieval from:
      1. Plant Health microservice (Foliar CNN classification & Grad-CAM severity)
      2. Environment & Weather microservice (Microclimate observation & EDPS pathogen pressure)
      3. Soil & Nutrient microservice (Rhizosphere NPK, pH, moisture, and health status)
    Aggregates the multi-domain signals into a synthesized Sunflower Health Index (SHI).
    Gracefully handles microservice degradation with partial results.
    """
    assessment_id = f"comb-{uuid.uuid4().hex[:10]}"
    timestamp = datetime.now(timezone.utc).isoformat()
    auth_header = request.headers.get("Authorization")

    # Read image bytes if provided
    image_bytes = None
    image_filename = None
    if image:
        image_bytes = await image.read()
        image_filename = image.filename

    async with httpx.AsyncClient() as client:
        # Fan-out concurrent queries across all three independent microservices
        plant_task = fetch_plant_health(
            client=client,
            image_bytes=image_bytes,
            image_filename=image_filename,
            plant_label=plant_label,
            auth_header=auth_header
        )
        weather_task = fetch_weather_environment(
            client=client,
            latitude=latitude,
            longitude=longitude,
            growth_stage=crop_stage,
            pdi=pdi,
            field_id=field_id
        )
        soil_task = fetch_soil_nutrients(
            client=client,
            field_id=field_id,
            auth_header=auth_header
        )

        plant_res, weather_res, soil_res = await asyncio.gather(
            plant_task, weather_task, soil_task
        )

    # Agronomic synthesis across the 3 domains
    synthesis = synthesize_crop_health(plant_res, weather_res, soil_res)

    return {
        "assessment_id": assessment_id,
        "timestamp": timestamp,
        "field_id": field_id,
        "plant_label": plant_label,
        "operating_mode": "MODE_B_COMBINED",
        "composite_health_index": synthesis["composite_health_index"],
        "overall_status": synthesis["overall_status"],
        "summary_verdict": synthesis["summary_verdict"],
        "partial_result": synthesis["partial_result"],
        "warnings": synthesis["warnings"],
        "integrated_recommendations": synthesis["integrated_recommendations"],
        "component_scores": synthesis["component_scores"],
        "services": {
            "plant_health": plant_res,
            "environment_weather": weather_res,
            "soil_nutrient": soil_res
        }
    }


# ==============================================================================
# MODE A: REVERSE PROXY ROUTING TO INDEPENDENT SERVICES
# ==============================================================================
async def _proxy_request(target_base_url: str, path: str, request: Request):
    """Generic high-performance reverse-proxy handler."""
    url = f"{target_base_url}/{path}"
    headers = dict(request.headers)
    # Remove host header to avoid routing mismatch
    headers.pop("host", None)
    
    body = await request.body()
    params = dict(request.query_params)
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                params=params,
                content=body,
                timeout=settings.SERVICE_TIMEOUT_SECONDS * 2
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers)
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Target microservice at '{target_base_url}' is currently unreachable."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Proxy routing error: {str(e)}"
            )

# 1. Reverse proxy to Plant Health (/api/plant/...)
@app.api_route("/api/plant/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_plant(path: str, request: Request):
    return await _proxy_request(f"{settings.PLANT_SERVICE_URL}/api", path, request)

# 2. Reverse proxy to Weather (/api/weather/...)
@app.api_route("/api/weather/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_weather(path: str, request: Request):
    return await _proxy_request(f"{settings.WEATHER_SERVICE_URL}/api", path, request)

# 3. Reverse proxy to Soil (/api/soil/...)
@app.api_route("/api/soil/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_soil(path: str, request: Request):
    return await _proxy_request(settings.SOIL_SERVICE_URL, path, request)

# 4. Reverse proxy for uploaded images / overlays from Plant Health
@app.api_route("/uploads/{path:path}", methods=["GET"])
async def proxy_uploads(path: str, request: Request):
    return await _proxy_request(f"{settings.PLANT_SERVICE_URL}/uploads", path, request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
