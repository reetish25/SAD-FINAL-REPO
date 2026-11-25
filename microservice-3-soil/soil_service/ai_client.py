"""Soil & Nutrient AI client.

When SOIL_AI_URL is set, the worker calls the separate AI service over its private API (ADR-S3).
When it is not set, a built-in model with the same reply format is used, so the service runs alone.
"""
import json
import logging
import urllib.error
import urllib.request

from . import config, rules

log = logging.getLogger("ai")


class SoilAIError(Exception):
    """The AI could not give a usable answer."""


class BuiltinSoilModel:
    model_version = "soil-ai-builtin-1.0"

    def analyze(self, sample_ref, version, values):
        if config.SOIL_AI_FAIL:
            raise SoilAIError("soil AI is unavailable (simulated outage)")
        flags = []
        for nutrient in rules.NUTRIENTS:
            low, high = rules.GOOD[nutrient]
            value = values[nutrient]
            # The model is a little more cautious than the rules near the limits, so the
            # two can disagree. The disagreement is shown, and the rule flag is kept.
            if value < low * 1.05:
                state, score = "DEFICIENT", 0.85
            elif value > high * 0.95:
                state, score = "EXCESS", 0.85
            else:
                state, score = "OK", 0.10
            flags.append({"nutrient": nutrient, "state": state, "score": score})
        return {"modelVersion": self.model_version, "flags": flags}


class HttpSoilAI:
    def analyze(self, sample_ref, version, values):
        payload = {
            "sampleRef": sample_ref, "version": version,
            "nitrogenMgKg": values["nitrogen"], "phosphorusMgKg": values["phosphorus"],
            "potassiumMgKg": values["potassium"], "ph": values["ph"], "moisturePct": values["moisture"],
        }
        req = urllib.request.Request(
            config.SOIL_AI_URL.rstrip("/") + "/internal/soil-analyze",
            data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Client-Id": config.SOIL_AI_CLIENT_ID,
                     "X-Client-Secret": config.SOIL_AI_SECRET},
        )
        try:
            with urllib.request.urlopen(req, timeout=config.AI_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise SoilAIError(f"soil AI call failed: {exc}")
        if not isinstance(data.get("flags"), list) or not data.get("modelVersion"):
            raise SoilAIError("soil AI reply did not match the agreed format")
        return data


def get_client():
    return HttpSoilAI() if config.SOIL_AI_URL else BuiltinSoilModel()
