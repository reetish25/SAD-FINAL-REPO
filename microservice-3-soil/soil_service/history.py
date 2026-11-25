"""Module 6: Soil History.

Assigned people see their fields. Researchers see anonymous rows only: a made-up field code and a
region, never a farm name, a person or an exact location (NS-BR-06).
"""
import re

from . import access, audit, db, samples
from .errors import ApiError
from .util import paging

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get(caller, query):
    page, size = paging(query)
    field_id = query.get("fieldId")
    region = query.get("region")
    service = caller["kind"] == "service"
    anonymous = caller.get("role") == access.RESEARCHER
    where, args = [], []
    assigned = []
    if not service and not anonymous:
        assigned = access.assigned_fields(caller["id"])
        if not assigned:
            return {"items": [], "page": page, "size": size, "anonymous": False}
        where.append(f"s.field_id IN ({','.join('?' * len(assigned))})")
        args += assigned
    if field_id:
        if not service and not anonymous and field_id not in assigned:
            raise ApiError(404, "NOT_FOUND", "Field not found.")
        where.append("s.field_id = ?")
        args.append(field_id)
    if region:
        where.append("f.region = ?")
        args.append(region)
    for key, op in (("from", ">="), ("to", "<=")):
        if query.get(key):
            if not DATE.match(query[key]):
                raise ApiError(400, "BAD_DATE", f"{key} must look like YYYY-MM-DD.")
            where.append(f"s.sample_date {op} ?")
            args.append(query[key])

    clause = " AND ".join(["s.state = 'READY'", samples.LATEST] + where)
    rows = db.rows(
        "SELECT s.*, f.region, f.anon_code, f.farm_name FROM soil_samples s JOIN fields f ON f.id = s.field_id "
        f"WHERE {clause} ORDER BY s.sample_date DESC, s.sample_id LIMIT ? OFFSET ?",
        (*args, size, (page - 1) * size),
    )
    items = []
    for r in rows:
        h = samples.health_row(r["sample_id"], r["version"])
        health = h["health_status"] if h else None
        flagged = [f["measurement"] for f in samples.flags_for(r["sample_id"], r["version"]) if f["level"] != "OK"]
        if anonymous:
            items.append({"fieldCode": r["anon_code"], "region": r["region"], "sampleDate": r["sample_date"],
                          "depthCm": r["depth_cm"], "version": r["version"], "healthStatus": health,
                          "outOfRange": flagged})
        else:
            items.append({"sampleId": r["sample_id"], "fieldId": r["field_id"], "fieldName": r["farm_name"],
                          "region": r["region"], "sampleDate": r["sample_date"], "depthCm": r["depth_cm"],
                          "version": r["version"], "healthStatus": health, "outOfRange": flagged})
    audit.write(caller["id"], caller.get("role"), "read-history", field_id or region or "all",
                "OK")
    return {"items": items, "page": page, "size": size, "anonymous": anonymous}
