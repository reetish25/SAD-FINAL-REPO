import io
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add api-gateway directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app
from orchestrator import synthesize_crop_health

client = TestClient(app)

def test_gateway_health():
    """Verify gateway healthcheck responds."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "microservices" in data
    assert "plant_health" in data["microservices"]
    assert "weather_environment" in data["microservices"]
    assert "soil_nutrient" in data["microservices"]

def test_synthesis_full_success():
    """Test agronomic synthesis when all 3 microservices succeed."""
    plant_res = {
        "status": "SUCCESS",
        "latency_ms": 110,
        "data": {
            "predicted_class": "MR",
            "healthy_pct": 82.5,
            "severity_pct": 17.5,
            "recommendation": {
                "active_ingredient": "Mancozeb 75% WP",
                "dosage": "2.0 g/L water"
            }
        }
    }
    weather_res = {
        "status": "SUCCESS",
        "latency_ms": 65,
        "data": {
            "temperature_c": 27.2,
            "humidity_pct": 68.0,
            "disease_risk": {
                "edps_score": 25.0,
                "risk_category": "LOW",
                "advisory": "Favorable dry microclimate; low risk of rapid lesion spread."
            }
        }
    }
    soil_res = {
        "status": "SUCCESS",
        "latency_ms": 32,
        "data": {
            "health_status": "GOOD",
            "deficiencies": []
        }
    }

    result = synthesize_crop_health(plant_res, weather_res, soil_res)

    assert result["partial_result"] is False
    assert result["composite_health_index"] > 75.0
    assert result["overall_status"] in ["OPTIMAL_HEALTH", "MODERATE_VIGOR"]
    assert len(result["integrated_recommendations"]) >= 2
    assert len(result["warnings"]) == 0

def test_synthesis_partial_soil_failure():
    """Test synthesis when Soil service is unavailable (graceful degradation)."""
    plant_res = {
        "status": "SUCCESS",
        "latency_ms": 110,
        "data": {
            "predicted_class": "MS",
            "healthy_pct": 62.0,
            "severity_pct": 38.0
        }
    }
    weather_res = {
        "status": "SUCCESS",
        "latency_ms": 70,
        "data": {
            "disease_risk": {
                "edps_score": 55.0,
                "risk_category": "HIGH",
                "advisory": "High humidity forecast."
            }
        }
    }
    soil_res = {
        "status": "UNAVAILABLE",
        "latency_ms": 5000,
        "error": "Connection timed out"
    }

    result = synthesize_crop_health(plant_res, weather_res, soil_res)

    # Must flag partial result but succeed in providing synthesis
    assert result["partial_result"] is True
    assert "Soil rhizosphere nutrient data unavailable." in result["warnings"]
    assert result["composite_health_index"] > 0
    assert result["component_scores"]["canopy_foliar_score"] == 62.0
    assert result["component_scores"]["soil_rhizosphere_score"] is None

def test_synthesis_critical_cross_domain_rule():
    """Test synergistic warning when foliar infection meets severe weather risk."""
    plant_res = {
        "status": "SUCCESS",
        "data": {
            "predicted_class": "S",
            "healthy_pct": 40.0,
            "severity_pct": 60.0
        }
    }
    weather_res = {
        "status": "SUCCESS",
        "data": {
            "disease_risk": {
                "edps_score": 75.0, # High pressure -> weather score = 25.0 (< 50)
                "advisory": "Severe rain and leaf wetness."
            }
        }
    }
    soil_res = {"status": "SUCCESS", "data": {"health_status": "FAIR"}}

    result = synthesize_crop_health(plant_res, weather_res, soil_res)

    assert result["overall_status"] in ["ELEVATED_RISK", "CRITICAL_ACTION_REQUIRED"]
    # Verify the high urgency cross-domain warning was inserted
    has_synergistic = any(
        "Critical Synergistic Warning" in rec.get("category", "")
        for rec in result["integrated_recommendations"]
    )
    assert has_synergistic is True
