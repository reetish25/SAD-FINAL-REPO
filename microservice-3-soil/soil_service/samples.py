"""Module 1: Soil Data Management.

Receives a sample, checks it, saves it with state RECEIVED and queues the analysis.
A correction never overwrites: it adds a new version that points to the one it replaces (NS-BR-01).
"""
from datetime import timedelta

from . import access, audit, config, db, rules
from .errors import ApiError
from .util import iso, new_id, paging, parse_iso, utcnow

COLUMN = {"nitrogen": "nitrogen_mg_kg", "phosphorus": "phosphorus_mg_kg", "potassium": "potassium_mg_kg",
          "ph": "ph", "moisture": "moisture_pct"}
BODY_KEY = {"nitrogen": "nitrogenMgKg", "phosphorus": "phosphorusMgKg", "potassium": "potassiumMgKg",
            "ph": "ph", "moisture": "moisturePct"}
REQUIRED = ("fieldId", "sampleDate", "depthCm", *BODY_KEY.values())
IN_FLIGHT = ("RECEIVED", "ANALYSING")
DONE_STATES = ("READY", "ANALYSIS_FAILED")
# "the latest version of each sample" - used by every read so old versions stay hidden from lists
LATEST = "s.version = (SELECT MAX(t.version) FROM soil_samples t WHERE t.sample_id = s.sample_id)"


def latest(sample_id):
    return db.row(f"SELECT * FROM soil_samples s WHERE {LATEST} AND s.sample_id = ?", (sample_id,))


def specific(sample_id, version):
    return db.row("SELECT * FROM soil_samples WHERE sample_id = ? AND version = ?", (sample_id, version))


def _values(row):
    return {m: row[COLUMN[m]] for m in rules.MEASUREMENTS}


def _parse_submission(body):
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Send a JSON object.")
    missing = [key for key in REQUIRED if body.get(key) in (None, "")]
    if missing:
        raise ApiError(400, "MISSING_FIELDS", "Missing: " + ", ".join(missing) + ".")
    lab = body.get("labReference")
    if lab not in (None, "") and (not isinstance(lab, str) or len(lab) > 40):
        raise ApiError(400, "BAD_LAB_REFERENCE", "Lab reference can be up to 40 characters.")
    return body


def _insert_version(c, sample_id, version, supersedes, field_id, owner_id, sample_date, depth, lab, values, now):
    c.execute(
        "INSERT INTO soil_samples (sample_id, version, supersedes_version, field_id, owner_user_id, sample_date, "
        "depth_cm, nitrogen_mg_kg, phosphorus_mg_kg, potassium_mg_kg, ph, moisture_pct, lab_reference, state, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sample_id, version, supersedes, field_id, owner_id, sample_date, depth,
         values["nitrogen"], values["phosphorus"], values["potassium"], values["ph"], values["moisture"],
         lab, "RECEIVED", now),
    )
    c.execute("INSERT INTO analysis_jobs (sample_id, version, job_status, attempts, next_run_at, created_at) "
              "VALUES (?, ?, 'QUEUED', 0, ?, ?)", (sample_id, version, now, now))


def _window_open(first_row):
    return utcnow() <= parse_iso(first_row["created_at"]) + timedelta(seconds=config.CORRECTION_WINDOW)


def submit(caller, body):
    body = _parse_submission(body)
    field_id = str(body["fieldId"])
    if not db.row("SELECT id FROM fields WHERE id = ?", (field_id,)):
        raise ApiError(404, "FIELD_NOT_FOUND", "Field not found.")
    if field_id not in access.assigned_fields(caller["id"]):
        audit.write(caller["id"], caller["role"], "submit-sample", field_id, "DENIED")
        raise ApiError(403, "NOT_ASSIGNED", "You are not assigned to this field.")
    hour_ago = iso(utcnow() - timedelta(hours=1))
    recent = db.row("SELECT COUNT(*) AS n FROM soil_samples WHERE owner_user_id = ? AND version = 1 "
                    "AND created_at > ?", (caller["id"], hour_ago))["n"]
    if recent >= config.SUBMIT_LIMIT_PER_HOUR:
        raise ApiError(429, "RATE_LIMITED", "Submission limit reached. Try again later.")

    rules.check_units(body.get("units"))
    values = {m: rules.check_value(m, body[BODY_KEY[m]]) for m in rules.MEASUREMENTS}
    depth = rules.check_depth(body["depthCm"])
    sample_date = rules.check_sample_date(body["sampleDate"])
    if db.row(f"SELECT s.sample_id FROM soil_samples s WHERE {LATEST} AND s.field_id = ? "
              "AND s.sample_date = ? AND s.depth_cm = ?", (field_id, sample_date, depth)):
        raise ApiError(409, "DUPLICATE_SAMPLE", "A sample for this field, date and depth already exists.")

    sample_id = new_id("smp")
    lab = body.get("labReference") or None
    with db.tx() as c:
        _insert_version(c, sample_id, 1, None, field_id, caller["id"], sample_date, depth, lab, values, iso())
        audit.write(caller["id"], caller["role"], "submit-sample", sample_id, "OK")
    return {"sampleId": sample_id, "version": 1, "state": "RECEIVED",
            "message": "Saved. Analysis is running in the background."}


def correct(caller, sample_id, body):
    body = body if isinstance(body, dict) else {}
    current = latest(sample_id)
    if not current or not access.can_read_sample(caller, current):
        raise ApiError(404, "NOT_FOUND", "Sample not found.")
    if current["owner_user_id"] != caller["id"]:
        raise ApiError(403, "NOT_OWNER", "Only the person who submitted this sample can correct it.")
    if not _window_open(specific(sample_id, 1)):
        raise ApiError(409, "WINDOW_CLOSED", "The 7-day correction window has closed.")
    if current["state"] in IN_FLIGHT:
        raise ApiError(409, "ANALYSIS_IN_PROGRESS", "Wait until the current analysis has finished.")

    rules.check_units(body.get("units"))
    values = _values(current)
    changed = False
    for m in rules.MEASUREMENTS:
        if body.get(BODY_KEY[m]) not in (None, ""):
            values[m] = rules.check_value(m, body[BODY_KEY[m]])
            changed = True
    if not changed:
        raise ApiError(400, "NO_CHANGES", "Send at least one changed value.")
    lab = current["lab_reference"]
    if body.get("labReference") not in (None, ""):
        lab = str(body["labReference"])[:40]

    version = current["version"] + 1
    with db.tx() as c:
        _insert_version(c, sample_id, version, current["version"], current["field_id"], caller["id"],
                        current["sample_date"], current["depth_cm"], lab, values, iso())
        audit.write(caller["id"], caller["role"], "correct-sample", sample_id, "OK")
    return {"sampleId": sample_id, "version": version, "supersedesVersion": current["version"], "state": "RECEIVED"}


def reanalyse(caller, sample_id):
    current = latest(sample_id)
    if not current or current["owner_user_id"] != caller["id"]:
        raise ApiError(404, "NOT_FOUND", "Sample not found.")
    if current["state"] != "ANALYSIS_FAILED":
        raise ApiError(409, "NOT_FAILED", "Only a sample whose analysis failed can be analysed again.")
    now = iso()
    with db.tx() as c:
        c.execute("UPDATE soil_samples SET state = 'ANALYSING' WHERE sample_id = ? AND version = ?",
                  (sample_id, current["version"]))
        c.execute("INSERT INTO analysis_jobs (sample_id, version, job_status, attempts, next_run_at, created_at) "
                  "VALUES (?, ?, 'QUEUED', 0, ?, ?)", (sample_id, current["version"], now, now))
        audit.write(caller["id"], caller["role"], "reanalyse-sample", sample_id, "OK")
    return {"sampleId": sample_id, "version": current["version"], "state": "ANALYSING"}


# ---------- reading ----------

def flags_for(sample_id, version):
    order = {m: i for i, m in enumerate(rules.MEASUREMENTS)}
    rows = db.rows("SELECT * FROM soil_flags WHERE sample_id = ? AND version = ?", (sample_id, version))
    out = []
    for r in sorted(rows, key=lambda r: order[r["measurement"]]):
        m = r["measurement"]
        out.append({
            "measurement": m, "level": r["level"], "state": rules.nutrient_state(m, r["level"]),
            "severity": r["severity"], "source": r["source"], "aiLevel": r["ai_level"],
            "aiScore": r["ai_score"], "disagreement": bool(r["disagreement"]), "modelVersion": r["model_version"],
        })
    return out


def health_row(sample_id, version):
    """The newest health result for a version (rows are kept, never replaced)."""
    return db.row("SELECT * FROM health_results WHERE sample_id = ? AND version = ? ORDER BY id DESC LIMIT 1",
                  (sample_id, version))


def _health_view(h):
    return {"healthStatus": h["health_status"], "ruleVersion": h["rule_version"],
            "modelVersion": h["model_version"], "aiView": h["ai_view"], "analysedAt": h["analysed_at"]}


def sample_view(row):
    out = {
        "sampleId": row["sample_id"], "version": row["version"], "supersedesVersion": row["supersedes_version"],
        "fieldId": row["field_id"], "sampleDate": row["sample_date"], "depthCm": row["depth_cm"],
        "labReference": row["lab_reference"], "state": row["state"], "createdAt": row["created_at"],
        "values": _values(row), "units": rules.UNITS,
    }
    if row["state"] in DONE_STATES:
        out["flags"] = flags_for(row["sample_id"], row["version"])
        h = health_row(row["sample_id"], row["version"])
        out["health"] = _health_view(h) if h else None
    out["versions"] = [
        {"version": v["version"], "state": v["state"], "createdAt": v["created_at"],
         "supersedesVersion": v["supersedes_version"]}
        for v in db.rows("SELECT version, state, created_at, supersedes_version FROM soil_samples "
                         "WHERE sample_id = ? ORDER BY version", (row["sample_id"],))
    ]
    return out


def read(caller, sample_id, version=None):
    try:
        row = specific(sample_id, int(version)) if version else latest(sample_id)
    except ValueError:
        raise ApiError(400, "BAD_VERSION", "Version must be a number.")
    if not row or not access.can_read_sample(caller, row):
        audit.write(caller["id"], caller["role"], "read-sample", sample_id, "DENIED")
        raise ApiError(404, "NOT_FOUND", "Sample not found.")
    audit.write(caller["id"], caller["role"], "read-sample", sample_id, "OK")
    view = sample_view(row)
    if caller["kind"] == "user" and caller["role"] == access.OPERATOR and row["owner_user_id"] == caller["id"]:
        current = latest(sample_id)
        first = specific(sample_id, 1)
        view["canCorrect"] = (current["version"] == row["version"] and current["state"] in DONE_STATES
                              and _window_open(first))
        view["canReanalyse"] = current["state"] == "ANALYSIS_FAILED" and current["version"] == row["version"]
    return view


def _summary(r):
    return {"sampleId": r["sample_id"], "version": r["version"], "fieldId": r["field_id"],
            "sampleDate": r["sample_date"], "depthCm": r["depth_cm"], "state": r["state"],
            "createdAt": r["created_at"]}


def list_samples(caller, query):
    page, size = paging(query)
    assigned = access.assigned_fields(caller["id"])
    if not assigned:
        return {"items": [], "page": page, "size": size}
    where = [f"s.field_id IN ({','.join('?' * len(assigned))})"]
    args = list(assigned)
    if caller["role"] == access.OPERATOR:
        where.append("s.owner_user_id = ?")
        args.append(caller["id"])
    if query.get("fieldId"):
        where.append("s.field_id = ?")
        args.append(query["fieldId"])
    sql = (f"SELECT s.* FROM soil_samples s WHERE {LATEST} AND " + " AND ".join(where)
           + " ORDER BY s.sample_date DESC, s.created_at DESC LIMIT ? OFFSET ?")
    rows = db.rows(sql, (*args, size, (page - 1) * size))
    return {"items": [_summary(r) for r in rows], "page": page, "size": size}


def my_fields(caller):
    rows = db.rows(
        "SELECT f.id, f.farm_name, f.region, f.anon_code FROM account_links l JOIN fields f ON f.id = l.field_id "
        "WHERE l.user_id = ? AND l.revoked_at IS NULL ORDER BY f.id", (caller["id"],))
    return {"items": [{"fieldId": r["id"], "farmName": r["farm_name"], "region": r["region"],
                       "fieldCode": r["anon_code"]} for r in rows]}


def soil_data(caller, query):
    """Measurement values for a field, for AI Analytics and Plant Health (or an assigned agronomist)."""
    field_id = query.get("fieldId")
    if not field_id:
        raise ApiError(400, "MISSING_FIELD", "fieldId is required.")
    if not access.can_read_field(caller, field_id, "soil-data"):
        raise ApiError(404, "NOT_FOUND", "Field not found.")
    page, size = paging(query)
    where, args = ["s.field_id = ?", "s.state = 'READY'"], [field_id]
    if query.get("from"):
        where.append("s.sample_date >= ?")
        args.append(query["from"])
    if query.get("to"):
        where.append("s.sample_date <= ?")
        args.append(query["to"])
    rows = db.rows(f"SELECT s.* FROM soil_samples s WHERE {LATEST} AND " + " AND ".join(where)
                   + " ORDER BY s.sample_date DESC LIMIT ? OFFSET ?", (*args, size, (page - 1) * size))
    items = [{"sampleId": r["sample_id"], "version": r["version"], "sampleDate": r["sample_date"],
              "depthCm": r["depth_cm"], "values": _values(r)} for r in rows]
    return {"fieldId": field_id, "items": items, "page": page, "size": size}
