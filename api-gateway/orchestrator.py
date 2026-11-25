import time
import logging
from typing import Optional, Dict, Any
import httpx
from config import settings

logger = logging.getLogger("orchestrator")

async def fetch_plant_health(
    client: httpx.AsyncClient,
    image_bytes: Optional[bytes] = None,
    image_filename: Optional[str] = None,
    plant_label: Optional[str] = None,
    auth_header: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calls the Plant Health microservice.
    If image_bytes is provided, executes a new diagnostic scan.
    Otherwise fetches latest scan or status.
    """
    start_time = time.time()
    url = f"{settings.PLANT_SERVICE_URL}/api"
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header

    try:
        if image_bytes:
            # Multipart upload to Plant Health /api/scans
            files = {"image": (image_filename or "sunflower_leaf.jpg", image_bytes, "image/jpeg")}
            data = {"plant_label": plant_label or "Field Scan", "forecast_days": "7"}
            resp = await client.post(
                f"{url}/scans",
                files=files,
                data=data,
                headers=headers,
                timeout=settings.SERVICE_TIMEOUT_SECONDS * 2  # PyTorch inference might take slightly longer
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "status": "SUCCESS",
                    "latency_ms": elapsed_ms,
                    "service": "Plant Health Diagnosis",
                    "version": "1.0.0",
                    "data": {
                        "scan_id": data.get("id"),
                        "predicted_class": data.get("predicted_class"),
                        "confidence": data.get("confidence"),
                        "severity_pct": data.get("severity_pct"),
                        "healthy_pct": data.get("healthy_pct"),
                        "model_used": data.get("model_used"),
                        "image_path": data.get("image_path"),
                        "overlay_image_path": data.get("overlay_image_path"),
                        "recommendation": data.get("recommendation"),
                        "probabilities": data.get("probabilities")
                    }
                }
            else:
                return {
                    "status": "ERROR",
                    "latency_ms": elapsed_ms,
                    "service": "Plant Health Diagnosis",
                    "error": f"Plant health returned HTTP {resp.status_code}: {resp.text[:200]}"
                }
        else:
            # No image supplied - probe health and recent status
            resp = await client.get(f"{url}/health", timeout=settings.SERVICE_TIMEOUT_SECONDS)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "SUCCESS",
                "latency_ms": elapsed_ms,
                "service": "Plant Health Diagnosis",
                "version": "1.0.0",
                "data": {
                    "note": "No foliar image provided for diagnosis; service is online and ready.",
                    "status": resp.json() if resp.status_code == 200 else "online"
                }
            }
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Plant health service communication failed: {e}")
        return {
            "status": "UNAVAILABLE",
            "latency_ms": elapsed_ms,
            "service": "Plant Health Diagnosis",
            "error": f"Service connection error: {str(e)}"
        }


async def fetch_weather_environment(
    client: httpx.AsyncClient,
    latitude: float,
    longitude: float,
    growth_stage: str = "flowering",
    pdi: float = 15.0,
    field_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calls the Environment & Weather microservice.
    Retrieves live weather conditions and Alternaria disease epidemiological risk (EDPS).
    """
    start_time = time.time()
    url = f"{settings.WEATHER_SERVICE_URL}/api"

    try:
        # 1. Fetch current weather
        weather_res = await client.get(
            f"{url}/weather/current",
            params={"latitude": latitude, "longitude": longitude},
            timeout=settings.SERVICE_TIMEOUT_SECONDS
        )
        weather_data = weather_res.json() if weather_res.status_code == 200 else {}

        # 2. Fetch Alternaria disease forecast if available
        forecast_payload = {
            "field_id": field_id or "field-demo",
            "latitude": latitude,
            "longitude": longitude,
            "growth_stage": growth_stage,
            "pdi": pdi,
            "forecast_days": 7
        }
        forecast_res = await client.post(
            f"{url}/disease-forecast/calculate",
            json=forecast_payload,
            timeout=settings.SERVICE_TIMEOUT_SECONDS
        )
        forecast_data = forecast_res.json() if forecast_res.status_code == 200 else {}

        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "SUCCESS",
            "latency_ms": elapsed_ms,
            "service": "Environment & Weather Service",
            "version": "2.0.0",
            "data": {
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "temperature_c": weather_data.get("temperature_c", 26.5),
                "humidity_pct": weather_data.get("humidity_pct", 72.0),
                "rainfall_mm": weather_data.get("rainfall_mm", 0.0),
                "wind_speed_kmh": weather_data.get("wind_speed_kmh", 12.0),
                "weather_source": weather_data.get("source", "Open-Meteo"),
                "disease_risk": {
                    "pdi_used": pdi,
                    "growth_stage": growth_stage,
                    "edps_score": forecast_data.get("edps") or forecast_data.get("edps_score") or 35.0,
                    "risk_category": forecast_data.get("risk_category", "MODERATE"),
                    "advisory": forecast_data.get("advisory", "Maintain standard field scouting.")
                }
            }
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Weather service communication failed: {e}")
        return {
            "status": "UNAVAILABLE",
            "latency_ms": elapsed_ms,
            "service": "Environment & Weather Service",
            "error": f"Service connection error: {str(e)}"
        }


async def fetch_soil_nutrients(
    client: httpx.AsyncClient,
    field_id: str = "field-demo",
    auth_header: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calls the Soil & Nutrient microservice.
    Retrieves field soil health classification (GOOD/FAIR/POOR), NPK values, pH, and nutrient flags.
    """
    start_time = time.time()
    url = settings.SOIL_SERVICE_URL
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header

    try:
        # Check health/measurements endpoint
        res = await client.get(
            f"{url}/soil-health",
            params={"field_id": field_id},
            headers=headers,
            timeout=settings.SERVICE_TIMEOUT_SECONDS
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        if res.status_code == 200:
            data = res.json()
            return {
                "status": "SUCCESS",
                "latency_ms": elapsed_ms,
                "service": "Soil & Nutrient Service",
                "version": "1.0.0",
                "data": data
            }
        elif res.status_code == 404:
            # Field not sampled yet, fetch sample fields or return clean status
            return {
                "status": "SUCCESS",
                "latency_ms": elapsed_ms,
                "service": "Soil & Nutrient Service",
                "version": "1.0.0",
                "data": {
                    "field_id": field_id,
                    "health_status": "PENDING_SAMPLE",
                    "note": f"No recent soil test registered for field '{field_id}'. Defaulting to baseline agronomic parameters."
                }
            }
        else:
            return {
                "status": "ERROR",
                "latency_ms": elapsed_ms,
                "service": "Soil & Nutrient Service",
                "error": f"Soil service returned HTTP {res.status_code}: {res.text[:200]}"
            }
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Soil service communication failed: {e}")
        return {
            "status": "UNAVAILABLE",
            "latency_ms": elapsed_ms,
            "service": "Soil & Nutrient Service",
            "error": f"Service connection error: {str(e)}"
        }


def synthesize_crop_health(
    plant_result: Dict[str, Any],
    weather_result: Dict[str, Any],
    soil_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Synthesizes data from Plant Health, Weather, and Soil microservices
    into an integrated Sunflower Health Assessment with composite scoring and action plan.
    Handles partial results gracefully when one or more services are unavailable.
    """
    weights_used = {}
    score_components = []
    recommendations = []
    warnings = []
    
    # 1. Plant Foliar Health Component (Weight 45%)
    plant_score = None
    if plant_result.get("status") == "SUCCESS" and "data" in plant_result:
        data = plant_result["data"]
        healthy_pct = data.get("healthy_pct")
        if healthy_pct is not None:
            plant_score = float(healthy_pct)
        elif data.get("predicted_class"):
            # Estimate from class
            class_scores = {"Immune": 98.0, "Resistant": 90.0, "MR": 75.0, "MS": 55.0, "S": 35.0, "HS": 15.0}
            plant_score = class_scores.get(data.get("predicted_class"), 80.0)
            
        if data.get("recommendation"):
            rec = data["recommendation"]
            recommendations.append({
                "source": "Plant Health",
                "category": "Foliar Treatment",
                "urgency": "High" if plant_score < 60 else "Routine",
                "action": f"Apply {rec.get('active_ingredient', 'fungicide')} at {rec.get('dosage', 'standard dosage')}."
            })
    else:
        warnings.append("Plant foliar diagnosis data unavailable or degraded.")

    # 2. Weather & Epidemiological Risk Component (Weight 30%)
    weather_score = None
    if weather_result.get("status") == "SUCCESS" and "data" in weather_result:
        data = weather_result["data"]
        disease_risk = data.get("disease_risk", {})
        edps = float(disease_risk.get("edps_score", 30.0))
        # High EDPS = high disease pressure = lower health score
        weather_score = max(0.0, min(100.0, 100.0 - edps))
        
        advisory = disease_risk.get("advisory")
        if advisory:
            recommendations.append({
                "source": "Environment & Weather",
                "category": "Epidemiological Advisory",
                "urgency": "High" if edps > 60 else "Moderate",
                "action": advisory
            })
    else:
        warnings.append("Microclimate epidemiological risk data unavailable.")

    # 3. Soil & Rhizosphere Health Component (Weight 25%)
    soil_score = None
    if soil_result.get("status") == "SUCCESS" and "data" in soil_result:
        data = soil_result["data"]
        health_status = data.get("health_status", "FAIR")
        if health_status == "GOOD":
            soil_score = 92.0
        elif health_status == "FAIR":
            soil_score = 70.0
        elif health_status == "POOR":
            soil_score = 40.0
        else:
            soil_score = 75.0  # Baseline when pending sample
            
        deficiencies = data.get("deficiencies", [])
        for d in deficiencies:
            recommendations.append({
                "source": "Soil & Nutrient",
                "category": "Nutrient Correction",
                "urgency": "Moderate",
                "action": f"Correct deficiency in {d.get('nutrient', 'mineral')} (Level: {d.get('value')} {d.get('unit', '')})."
            })
    else:
        warnings.append("Soil rhizosphere nutrient data unavailable.")

    # Calculate dynamically weighted composite score
    active_weights = []
    if plant_score is not None:
        active_weights.append((plant_score, 0.45, "Canopy Foliage"))
    if weather_score is not None:
        active_weights.append((weather_score, 0.30, "Climate & Disease Pressure"))
    if soil_score is not None:
        active_weights.append((soil_score, 0.25, "Soil & Rhizosphere"))

    if active_weights:
        total_weight = sum(w for _, w, _ in active_weights)
        composite_index = sum(s * (w / total_weight) for s, w, _ in active_weights)
        composite_index = round(composite_index, 1)
    else:
        composite_index = 50.0  # Fallback neutral score

    # Classify overall condition
    if composite_index >= 85:
        overall_status = "OPTIMAL_HEALTH"
        summary_verdict = "Sunflower canopy and rhizosphere demonstrate excellent agronomic vigor with low pathogen pressure."
    elif composite_index >= 68:
        overall_status = "MODERATE_VIGOR"
        summary_verdict = "Crop is in fair condition. Monitor foliar symptoms and microclimate moisture closely."
    elif composite_index >= 50:
        overall_status = "ELEVATED_RISK"
        summary_verdict = "Pathogen pressure or nutritional deficiencies detected. Interventions recommended to prevent yield loss."
    else:
        overall_status = "CRITICAL_ACTION_REQUIRED"
        summary_verdict = "Severe disease damage or severe soil/weather stress observed. Immediate agronomic remediation required."

    # Multi-domain cross-correlation insight
    if plant_score is not None and weather_score is not None and plant_score < 70 and weather_score < 50:
        recommendations.insert(0, {
            "source": "Multi-Service Synthesis",
            "category": "Critical Synergistic Warning",
            "urgency": "Urgent",
            "action": "Active foliar infection coincides with high environmental pathogen conduciveness. Schedule fungicide application within 24 hours."
        })

    is_partial = any(res.get("status") != "SUCCESS" for res in (plant_result, weather_result, soil_result))

    return {
        "composite_health_index": composite_index,
        "overall_status": overall_status,
        "summary_verdict": summary_verdict,
        "partial_result": is_partial,
        "warnings": warnings,
        "integrated_recommendations": recommendations,
        "component_scores": {
            "canopy_foliar_score": plant_score,
            "climate_resilience_score": weather_score,
            "soil_rhizosphere_score": soil_score
        }
    }
