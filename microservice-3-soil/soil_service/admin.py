"""Administrator functions: approvals, field assignments and the activity log.
An administrator can assign people to fields but can never change measurements (section 2.3)."""
import secrets

from . import access, audit, auth, db, security
from .errors import ApiError
from .util import iso, paging


def _account(user_id):
    user = db.row("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise ApiError(404, "NOT_FOUND", "Account not found.")
    return user


def list_accounts(status=None):
    if status and status != "ALL":
        users = db.rows("SELECT * FROM users WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        users = db.rows("SELECT * FROM users ORDER BY created_at DESC")
    items = []
    for u in users:
        fields = db.rows("SELECT field_id FROM account_links WHERE user_id = ? AND revoked_at IS NULL", (u["id"],))
        item = auth.public_user(u)
        item["fields"] = [f["field_id"] for f in fields]
        items.append(item)
    return {"items": items}


def approve(actor, user_id, role):
    target = _account(user_id)
    if target["id"] == actor["id"]:
        raise ApiError(403, "SELF_CHANGE", "No one can change their own role or status.")
    if target["status"] != auth.PENDING_APPROVAL:
        raise ApiError(409, "NOT_PENDING", "This account is not waiting for approval.")
    role = role or target["requested_role"]
    if role not in auth.NEEDS_APPROVAL:
        raise ApiError(400, "BAD_ROLE", "Approve as Field Operator, Agronomist or Researcher.")
    with db.tx():
        db.run("UPDATE users SET status = ?, role = ? WHERE id = ?", (auth.ACTIVE, role, user_id))
        audit.write(actor["id"], actor["role"], "approve-account", user_id, "OK")
    return {"message": f"Approved as {role}."}


def reject(actor, user_id):
    target = _account(user_id)
    if target["id"] == actor["id"]:
        raise ApiError(403, "SELF_CHANGE", "No one can change their own role or status.")
    with db.tx():
        db.run("UPDATE users SET status = ? WHERE id = ?", (auth.REJECTED, user_id))
        db.run("UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (iso(), user_id))
        audit.write(actor["id"], actor["role"], "reject-account", user_id, "OK")
    return {"message": "Account rejected."}


def revoke_sessions(actor, user_id):
    _account(user_id)
    with db.tx():
        db.run("UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (iso(), user_id))
        audit.write(actor["id"], actor["role"], "revoke-sessions", user_id, "OK")
    return {"message": "All sessions for this person are cancelled."}


def _reason(body):
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 3:
        raise ApiError(400, "REASON_REQUIRED", "Give a short reason for this change.")
    return reason


def assign(actor, body):
    user = _account(str(body.get("userId") or ""))
    field_id = str(body.get("fieldId") or "")
    reason = _reason(body)
    if user["status"] != auth.ACTIVE or user["role"] not in access.FIELD_ROLES:
        raise ApiError(409, "NOT_ELIGIBLE", "Only approved Field Operators, Agronomists and Farmers can be assigned.")
    if not db.row("SELECT id FROM fields WHERE id = ?", (field_id,)):
        raise ApiError(404, "FIELD_NOT_FOUND", "Field not found.")
    if field_id in access.assigned_fields(user["id"]):
        raise ApiError(409, "ALREADY_ASSIGNED", "This person already has this field.")
    with db.tx():
        db.run("INSERT INTO account_links (user_id, field_id, granted_by, reason, granted_at) VALUES (?, ?, ?, ?, ?)",
               (user["id"], field_id, actor["id"], reason, iso()))
        audit.write(actor["id"], actor["role"], "assign-field", f"{user['id']}:{field_id}", "OK")
    return {"message": "Field assigned."}


def unassign(actor, body):
    user = _account(str(body.get("userId") or ""))
    field_id = str(body.get("fieldId") or "")
    reason = _reason(body)
    with db.tx():
        cur = db.run("UPDATE account_links SET revoked_at = ?, reason = ? WHERE user_id = ? AND field_id = ? "
                     "AND revoked_at IS NULL", (iso(), reason, user["id"], field_id))
        if cur.rowcount == 0:
            raise ApiError(404, "NOT_FOUND", "No active assignment for that person and field.")
        audit.write(actor["id"], actor["role"], "unassign-field", f"{user['id']}:{field_id}", "OK")
    return {"message": "Assignment removed."}


def list_fields():
    rows = db.rows("SELECT * FROM fields ORDER BY id")
    return {"items": [{"fieldId": r["id"], "farmName": r["farm_name"], "region": r["region"],
                       "fieldCode": r["anon_code"]} for r in rows]}


def create_field(actor, body):
    farm = str(body.get("farmName") or "").strip()
    region = str(body.get("region") or "").strip()
    if not 2 <= len(farm) <= 120 or not 2 <= len(region) <= 60:
        raise ApiError(400, "BAD_FIELD", "Farm name (2 to 120 characters) and region (2 to 60) are required.")
    field_id = "fld_" + secrets.token_hex(4)
    code = "FLD-" + secrets.token_hex(2).upper()
    with db.tx():
        db.run("INSERT INTO fields (id, farm_name, region, anon_code, created_at) VALUES (?, ?, ?, ?, ?)",
               (field_id, farm, region, code, iso()))
        audit.write(actor["id"], actor["role"], "create-field", field_id, "OK")
    return {"fieldId": field_id, "fieldCode": code}


def create_admin(actor, body):
    email = auth._email(body.get("email"))
    full_name = str(body.get("fullName") or "").strip()
    if not email or not full_name:
        raise ApiError(400, "BAD_FIELD", "Email and full name are required.")
    problem = security.password_problem(body.get("password") or "")
    if problem:
        raise ApiError(422, "WEAK_PASSWORD", problem)
    if db.row("SELECT id FROM users WHERE email = ?", (email,)):
        raise ApiError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    secret = security.new_totp_secret()
    with db.tx():
        uid = auth.create_account(email, full_name, "Leafline", access.ADMIN, access.ADMIN, auth.ACTIVE,
                                  body["password"], secret)
        audit.write(actor["id"], actor["role"], "create-admin", uid, "OK")
    return {"id": uid, "email": email,
            "totpSecret": secret,
            "message": "Add this secret to an authenticator app now. It is shown only once."}


def audit_log(query):
    page, size = paging(query)
    rows = db.rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?", (size, (page - 1) * size))
    return {"items": [{"id": r["id"], "actorId": r["actor_user_id"], "actorRole": r["actor_role"],
                       "action": r["action"], "target": r["target_id"], "outcome": r["outcome"],
                       "at": r["occurred_at"]} for r in rows], "page": page, "size": size}


def outbox(limit=50):
    rows = db.rows("SELECT * FROM outbox ORDER BY id DESC LIMIT ?", (limit,))
    return {"items": [{"to": r["to_email"], "subject": r["subject"], "body": r["body"], "at": r["created_at"]}
                      for r in rows]}
