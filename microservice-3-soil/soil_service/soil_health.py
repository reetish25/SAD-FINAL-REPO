"""Modules 4 and 5: overall soil health and nutrient deficiency or excess flags."""
from datetime import date

from . import access, audit, db, samples
from .errors import ApiError

def _date(value):
    if not value:
        return date.today().isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ApiError(400, "BAD_DATE", "date must look like YYYY-MM-DD.")

def get(caller, query):
    field_id = query.get("fieldId")
    if not field_id:
        raise ApiError(400, "MISSING_FIELD", "fieldId is required.")
    if not access.can_read_field(caller, field_id, "soil-health"):
        audit.write(caller["id"], caller["role"], "read-health", field_id, "DENIED")
        raise ApiError(404, "NOT_FOUND", "Field not found.")
    on_date = _date(query.get("date"))
    candidates = db.rows(
        f"SELECT s.* FROM soil_samples s WHERE {samples.LATEST} AND s.field_id = ? AND s.sample_date <= ? "
        "ORDER BY s.sample_date DESC, s.created_at DESC LIMIT 20",
        (field_id, on_date),
    )
    for s in candidates:
        h = samples.health_row(s["sample_id"], s["version"])
        if not h:
            continue
        flags = samples.flags_for(s["sample_id"], s["version"])
        audit.write(caller["id"], caller["role"], "read-health", field_id, "OK")
        return {
            "fieldId": field_id, "sampleId": s["sample_id"], "version": s["version"],
            "sampleDate": s["sample_date"], "healthStatus": h["health_status"], "flags": flags,
            "deficiencies": [{"nutrient": f["measurement"], "state": f["state"], "severity": f["severity"]}
                             for f in flags if f["state"] in ("DEFICIENT", "EXCESS")],
            "aiView": h["ai_view"], "ruleVersion": h["rule_version"], "modelVersion": h["model_version"],
            "analysedAt": h["analysed_at"],
        }
    raise ApiError(404, "NO_RESULT", "No analysed sample for this field yet.")
