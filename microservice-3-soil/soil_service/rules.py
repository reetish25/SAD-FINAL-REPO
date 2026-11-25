"""Business rules for soil data.

Pure functions only: no database and no web code. That makes them easy to test
and keeps the range and unit rules in one place, so they cannot be skipped.
"""
import datetime as dt

from .errors import ApiError

MEASUREMENTS = ("nitrogen", "phosphorus", "potassium", "ph", "moisture")
NUTRIENTS = ("nitrogen", "phosphorus", "potassium")
LABELS = {"nitrogen": "Nitrogen", "phosphorus": "Phosphorus", "potassium": "Potassium",
          "ph": "pH", "moisture": "Moisture"}
UNITS = {"nitrogen": "mg/kg", "phosphorus": "mg/kg", "potassium": "mg/kg", "ph": None, "moisture": "percent"}

# Possible range: outside it a value is refused (422).  (NS-BR-02)
POSSIBLE = {"nitrogen": (0, 1000), "phosphorus": (0, 1000), "potassium": (0, 1500),
            "ph": (0.0, 14.0), "moisture": (0, 100)}
# Good range for sunflower: outside it a value is saved and flagged.  (NS-BR-03, section 7.2 - to be signed off)
GOOD = {"nitrogen": (20, 40), "phosphorus": (15, 30), "potassium": (120, 250),
        "ph": (6.0, 7.5), "moisture": (15, 45)}
DEPTH = (0, 100)
MAX_AGE_YEARS = 5
RULE_VERSION = "soil-rules-1.0"
HEALTH_VERSION = "soil-health-1.0"

NUTRIENT_STATE = {"LOW": "DEFICIENT", "HIGH": "EXCESS", "OK": "OK"}
_UNIT_ALIASES = {"": None, "none": None, "%": "percent"}


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check_value(name, value):
    """Return the value as a float, or raise 422 when it is outside its possible range."""
    label = LABELS[name]
    if not _is_number(value):
        raise ApiError(400, "BAD_VALUE", f"{label} must be a number.")
    low, high = POSSIBLE[name]
    if not low <= value <= high:
        raise ApiError(422, "OUT_OF_RANGE", f"{label} must be between {low} and {high}.")
    if name == "ph" and abs(value * 10 - round(value * 10)) > 1e-6:
        raise ApiError(422, "OUT_OF_RANGE", "pH must have one decimal place.")
    return float(value)


def check_depth(value):
    if not _is_number(value):
        raise ApiError(400, "BAD_VALUE", "Depth must be a number.")
    low, high = DEPTH
    if not low <= value <= high:
        raise ApiError(422, "OUT_OF_RANGE", "Depth must be between 0 and 100 cm.")
    return float(value)


def check_units(units):
    """Units are fixed. A different unit is refused, never converted silently (NS-BR-04)."""
    if units is None:
        return
    if not isinstance(units, dict):
        raise ApiError(400, "BAD_UNITS", "units must be an object such as {\"nitrogen\": \"mg/kg\"}.")
    for key, given in units.items():
        if key not in UNITS:
            raise ApiError(400, "UNKNOWN_MEASUREMENT", f"Unknown measurement: {key}.")
        norm = given.strip().lower() if isinstance(given, str) else given
        norm = _UNIT_ALIASES.get(norm, norm)
        expected = UNITS[key]
        if norm != expected:
            shown = expected or "no unit"
            raise ApiError(422, "UNIT_MISMATCH",
                           f"{LABELS[key]} must be given in {shown}. Units are never converted.")


def check_sample_date(text, today=None):
    """The date cannot be in the future or more than 5 years old (NS-BR-07)."""
    try:
        day = dt.date.fromisoformat(str(text))
    except ValueError:
        raise ApiError(400, "BAD_DATE", "Sample date must look like YYYY-MM-DD.")
    today = today or dt.date.today()
    if day > today:
        raise ApiError(422, "FUTURE_DATE", "Sample date cannot be in the future.")
    if day < today.replace(year=today.year - MAX_AGE_YEARS):
        raise ApiError(422, "OLD_DATE", "Sample date cannot be more than 5 years old.")
    return day.isoformat()


def flag_level(name, value):
    low, high = GOOD[name]
    if value < low:
        return "LOW"
    if value > high:
        return "HIGH"
    return "OK"


def severity(name, value, level):
    """slight within 10 % of the limit, moderate from 10 to 25 %, severe beyond 25 %."""
    if level == "OK":
        return None
    low, high = GOOD[name]
    limit = low if level == "LOW" else high
    gap_pct = abs(value - limit) * 100 / limit
    if gap_pct <= 10 + 1e-9:
        return "slight"
    if gap_pct <= 25 + 1e-9:
        return "moderate"
    return "severe"


def nutrient_state(name, level):
    """Nutrients read DEFICIENT / OK / EXCESS. pH and moisture keep LOW / OK / HIGH."""
    return NUTRIENT_STATE[level] if name in NUTRIENTS else level


def rule_flags(values):
    """Flag every measurement with its level and severity."""
    result = {}
    for name in MEASUREMENTS:
        level = flag_level(name, values[name])
        result[name] = {"level": level, "severity": severity(name, values[name], level)}
    return result


def health_status(flags):
    """GOOD: all in range. FAIR: one outside and none severe. POOR: two or more outside, or any severe."""
    outside = [f for f in flags if f["level"] != "OK"]
    if not outside:
        return "GOOD"
    if len(outside) >= 2 or any(f["severity"] == "severe" for f in outside):
        return "POOR"
    return "FAIR"
