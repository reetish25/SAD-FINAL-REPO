import os
import sys
import io
import time
from pathlib import Path
from PIL import Image
import pytest

# Add project paths to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "api-gateway"))
sys.path.insert(0, str(ROOT_DIR / "microservice-1-leafline" / "backend"))
sys.path.insert(0, str(ROOT_DIR / "microservice-2-weather" / "backend"))
sys.path.insert(0, str(ROOT_DIR / "microservice-3-soil"))

from orchestrator import synthesize_crop_health
from soil_service import rules as soil_rules
from soil_service.errors import ApiError

def make_test_image_bytes():
    buf = io.BytesIO()
    img = Image.new("RGB", (224, 224), (60, 140, 50))
    img.save(buf, format="JPEG")
    return buf.getvalue()

# ==============================================================================
# 1. CROSS-SERVICE INTEGRATION TESTS (MODE B COMBINED OPERATION)
# ==============================================================================

def test_e2e_mode_b_full_orchestration():
    """
    Simulates complete Mode B pipeline across Canopy, Microclimate and Rhizosphere:
    Verifies that multi-service data is correctly weighted and integrated.
    """
    plant_data = {
        "status": "SUCCESS",
        "latency_ms": 120,
        "service": "Plant Health Diagnosis",
        "data": {
            "predicted_class": "MR",
            "confidence": 0.89,
            "healthy_pct": 78.5,
            "severity_pct": 21.5,
            "recommendation": {
                "active_ingredient": "Mancozeb 75% WP",
                "dosage": "2.0 - 2.5 g/L"
            }
        }
    }

    weather_data = {
        "status": "SUCCESS",
        "latency_ms": 45,
        "service": "Environment & Weather Service",
        "data": {
            "temperature_c": 27.5,
            "humidity_pct": 74.0,
            "disease_risk": {
                "edps_score": 38.0,
                "risk_category": "MODERATE",
                "advisory": "Moderate Alternaria risk. Monitor lower canopy foliage."
            }
        }
    }

    soil_data = {
        "status": "SUCCESS",
        "latency_ms": 28,
        "service": "Soil & Nutrient Service",
        "data": {
            "health_status": "GOOD",
            "deficiencies": []
        }
    }

    synthesis = synthesize_crop_health(plant_data, weather_data, soil_data)

    assert synthesis["partial_result"] is False
    assert synthesis["overall_status"] in ["OPTIMAL_HEALTH", "MODERATE_VIGOR"]
    assert synthesis["composite_health_index"] >= 70.0
    assert len(synthesis["integrated_recommendations"]) >= 2
    assert len(synthesis["warnings"]) == 0

def test_e2e_mode_b_graceful_degradation_weather_down():
    """
    Verifies Mode B resilience when Weather service is offline:
    Platform must continue operating, compute composite score from available services,
    and flag partial_result = True with user warning.
    """
    plant_data = {
        "status": "SUCCESS",
        "latency_ms": 115,
        "data": {
            "predicted_class": "Resistant",
            "healthy_pct": 92.0,
            "severity_pct": 8.0
        }
    }

    weather_data = {
        "status": "UNAVAILABLE",
        "latency_ms": 5000,
        "error": "Connection timed out"
    }

    soil_data = {
        "status": "SUCCESS",
        "latency_ms": 30,
        "data": {
            "health_status": "FAIR",
            "deficiencies": [
                {"nutrient": "Potassium", "value": 110.0, "unit": "mg/kg"}
            ]
        }
    }

    synthesis = synthesize_crop_health(plant_data, weather_data, soil_data)

    assert synthesis["partial_result"] is True
    assert "Microclimate epidemiological risk data unavailable." in synthesis["warnings"]
    assert synthesis["composite_health_index"] > 75.0
    assert synthesis["component_scores"]["canopy_foliar_score"] == 92.0
    assert synthesis["component_scores"]["climate_resilience_score"] is None
    assert synthesis["component_scores"]["soil_rhizosphere_score"] == 70.0

# ==============================================================================
# 2. BUSINESS RULES & DATA INTEGRITY TESTS
# ==============================================================================

def test_soil_rules_boundary_enforcement():
    """
    Verifies pure agronomic rules in Soil service:
    Boundary checks refuse out-of-range values without corrupting database state.
    """
    # Valid pH within possible range (3.5 - 9.5) returns the float value
    val = soil_rules.check_value("ph", 6.8)
    assert val == 6.8

    # Out of possible range pH (e.g. -1.0 or 15.0) must raise ApiError(422)
    with pytest.raises(ApiError) as exc_info:
        soil_rules.check_value("ph", -1.0)
    assert exc_info.value.status == 422

    with pytest.raises(ApiError) as exc_info2:
        soil_rules.check_value("ph", 15.0)
    assert exc_info2.value.status == 422

def test_soil_health_classification_logic():
    """
    Verifies Soil health status mapping:
    All in range -> GOOD
    One non-severe flag -> FAIR
    One severe flag or two+ flags -> POOR
    """
    # All in range
    assert soil_rules.health_status([]) == "GOOD"
    assert soil_rules.health_status([{"level": "OK", "severity": "none"}]) == "GOOD"

    # One non-severe flag -> FAIR
    assert soil_rules.health_status([{"level": "LOW", "severity": "mild"}]) == "FAIR"

    # One severe flag -> POOR
    assert soil_rules.health_status([{"level": "VERY_LOW", "severity": "severe"}]) == "POOR"

    # Two non-severe flags -> POOR
    assert soil_rules.health_status([
        {"level": "LOW", "severity": "mild"},
        {"level": "HIGH", "severity": "moderate"}
    ]) == "POOR"

def test_cross_domain_synergy_high_risk_rule():
    """
    Verifies multi-domain agronomic rule:
    When canopy has severe foliar infection AND weather has high disease pressure (EDPS > 60),
    an Urgent Synergistic Warning must be generated.
    """
    plant_data = {
        "status": "SUCCESS",
        "data": {
            "predicted_class": "HS",
            "healthy_pct": 20.0,
            "severity_pct": 80.0
        }
    }
    weather_data = {
        "status": "SUCCESS",
        "data": {
            "disease_risk": {
                "edps_score": 82.0,
                "advisory": "High humidity and continuous leaf wetness."
            }
        }
    }
    soil_data = {
        "status": "SUCCESS",
        "data": {
            "health_status": "POOR",
            "deficiencies": [{"nutrient": "Potassium", "value": 85.0}]
        }
    }

    synthesis = synthesize_crop_health(plant_data, weather_data, soil_data)

    assert synthesis["overall_status"] == "CRITICAL_ACTION_REQUIRED"
    assert synthesis["composite_health_index"] < 40.0
    urgent_recs = [r for r in synthesis["integrated_recommendations"] if r.get("urgency") == "Urgent"]
    assert len(urgent_recs) >= 1
    assert "Synergistic" in urgent_recs[0]["category"]
