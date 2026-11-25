"""Accounts and sessions (section 3 of the specification).

In the full platform these rules belong to Identity & Access at the API Gateway. They live here so
that the service runs on its own with no other service required. The rules are the same either way.

Functions that must save a result even when they refuse a request (for example, a failed login
counts towards the lock) return an error dictionary instead of raising inside the transaction.
"""
import logging
import math
import re
from datetime import timedelta

from . import access, audit, config, db, security
from .errors import ApiError
from .util import iso, new_id, parse_iso, utcnow

log = logging.getLogger("auth")

ACTIVE = "ACTIVE"
PENDING_VERIFICATION = "PENDING_VERIFICATION"
PENDING_APPROVAL = "PENDING_APPROVAL"
REJECTED = "REJECTED"
REQUESTABLE = (access.OPERATOR, access.AGRONOMIST, access.RESEARCHER, access.FARMER)
NEEDS_APPROVAL = (access.OPERATOR, access.AGRONOMIST, access.RESEARCHER)
GENERIC_REGISTER = "If this email can be used, a verification link has been sent."
GENERIC_RESET = "If the email is registered, a reset link has been sent."
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DUMMY_HASH = security.hash_password("timing-equaliser")


def _err(status, code, message):
    return {"status": status, "code": code, "message": message}


def _bad_credentials():
    return _err(401, "BAD_CREDENTIALS", "Email or password is wrong.")


def _email(value):
    return str(value or "").strip().lower()


def _checked_email(value):
    email = _email(value)
    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise ApiError(400, "BAD_EMAIL", "Enter a valid email address.")
    return email


def _text(body, key, low, high, required=True):
    value = body.get(key)
    value = value.strip() if isinstance(value, str) else ""
    if not value and not required:
        return None
    if not low <= len(value) <= high:
        raise ApiError(400, "BAD_FIELD", f"{key} must be {low} to {high} characters.")
    return value


def public_user(row):
    return {
        "id": row["id"], "email": row["email"], "fullName": row["full_name"],
        "organisation": row["organisation"], "role": row["role"],
        "requestedRole": row["requested_role"], "status": row["status"],
    }


# ---------- email tokens and mail ----------

def _issue_token(user_id, purpose, ttl):
    raw = security.random_token()
    db.run(
        "INSERT INTO email_tokens (token_hash, user_id, purpose, expires_at) VALUES (?, ?, ?, ?)",
        (security.sha256_hex(raw), user_id, purpose, iso(utcnow() + timedelta(seconds=ttl))),
    )
    return raw


def _consume_token(raw, purpose):
    row = db.row("SELECT * FROM email_tokens WHERE token_hash = ? AND purpose = ?",
                 (security.sha256_hex(str(raw or "")), purpose))
    if not row or row["used_at"]:
        raise ApiError(400, "LINK_INVALID", "This link is not valid. Request a new one.")
    if parse_iso(row["expires_at"]) < utcnow():
        raise ApiError(400, "LINK_EXPIRED", "This link has expired. Request a new one.")
    db.run("UPDATE email_tokens SET used_at = ? WHERE token_hash = ?", (iso(), row["token_hash"]))
    return row["user_id"]


def _send_mail(to_email, subject, text):
    """Stands in for an email server. Messages are kept in the outbox; in development they are also logged."""
    db.run("INSERT INTO outbox (to_email, subject, body, created_at) VALUES (?, ?, ?, ?)",
           (to_email, subject, text, iso()))
    if config.DEV_MODE:
        log.info("DEV MAIL to %s: %s -> %s", to_email, subject, text)


# ---------- accounts ----------

def create_account(email, full_name, organisation, requested_role, role, status, password, totp_secret=None):
    uid = new_id("usr")
    db.run(
        "INSERT INTO users (id, email, full_name, phone, organisation, requested_role, role, status, "
        "password_hash, totp_secret, created_at) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)",
        (uid, email, full_name, organisation, requested_role, role, status,
         security.hash_password(password), totp_secret, iso()),
    )
    return uid


def register(body):
    full_name = _text(body, "fullName", 2, 120)
    organisation = _text(body, "organisation", 2, 120)
    phone = _text(body, "phone", 0, 30, required=False)
    email = _checked_email(body.get("email"))
    role = body.get("requestedRole")
    if role not in REQUESTABLE:
        raise ApiError(400, "BAD_ROLE", "Request one of: " + ", ".join(REQUESTABLE)
                       + ". Administrators are created by an administrator.")
    problem = security.password_problem(body.get("password") or "")
    if problem:
        raise ApiError(422, "WEAK_PASSWORD", problem)
    with db.tx():
        if db.row("SELECT id FROM users WHERE email = ?", (email,)):
            # Same reply as a new email, so the service does not reveal which emails exist (NS-AUTH-04).
            return {"message": GENERIC_REGISTER}
        uid = new_id("usr")
        db.run(
            "INSERT INTO users (id, email, full_name, phone, organisation, requested_role, role, status, "
            "password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",
            (uid, email, full_name, phone, organisation, role, PENDING_VERIFICATION,
             security.hash_password(body["password"]), iso()),
        )
        token = _issue_token(uid, "verify", config.VERIFY_TTL)
        _send_mail(email, "Verify your Nutrient & Soil account",
                   f"Open this link within 24 hours: {config.PUBLIC_BASE_URL}/#/verify?token={token}")
        audit.write(uid, role, "register", uid, "OK")
    return {"message": GENERIC_REGISTER}


def verify(raw_token):
    with db.tx():
        uid = _consume_token(raw_token, "verify")
        user = db.row("SELECT * FROM users WHERE id = ?", (uid,))
        if user["status"] != PENDING_VERIFICATION:
            raise ApiError(400, "LINK_INVALID", "This link is not valid. Request a new one.")
        if user["requested_role"] in NEEDS_APPROVAL:
            status, role = PENDING_APPROVAL, None
            message = "Email verified. An administrator will approve your account before you can see data."
        else:
            status, role = ACTIVE, user["requested_role"]
            message = "Email verified. You can log in now."
        db.run("UPDATE users SET status = ?, role = ? WHERE id = ?", (status, role, uid))
        audit.write(uid, role, "verify-email", uid, "OK")
    return {"status": status, "message": message}


# ---------- login ----------

def login(body):
    email = _email(body.get("email"))
    password = str(body.get("password") or "")
    code = str(body.get("totpCode") or "")
    with db.tx():
        result = _check_login(email, password, code)
    if "error" in result:
        raise ApiError(**result["error"])
    return result["ok"]


def _locked_error(until_iso, now):
    minutes = max(1, math.ceil((parse_iso(until_iso) - now).total_seconds() / 60))
    return _err(423, "ACCOUNT_LOCKED", f"Account locked. Try again in {minutes} minutes.")


def _record_failure(user, now):
    first = parse_iso(user["first_failure_at"]) if user["first_failure_at"] else None
    if first is None or now - first > timedelta(seconds=config.LOCK_WINDOW):
        first, count = now, 1
    else:
        count = user["failed_count"] + 1
    locked_until = None
    if count >= config.LOCK_FAILURES:
        locked_until = now + timedelta(seconds=config.LOCK_DURATION)
        count, first = 0, None
    db.run("UPDATE users SET failed_count = ?, first_failure_at = ?, locked_until = ? WHERE id = ?",
           (count, iso(first) if first else None, iso(locked_until) if locked_until else None, user["id"]))
    return iso(locked_until) if locked_until else None


def _check_login(email, password, code):
    user = db.row("SELECT * FROM users WHERE email = ?", (email,))
    if not user:
        security.verify_password(password, DUMMY_HASH)  # same work as a real check
        return {"error": _bad_credentials()}
    if user["status"] == PENDING_VERIFICATION:
        return {"error": _err(403, "NOT_VERIFIED", "Verify your email before logging in.")}
    if user["status"] == PENDING_APPROVAL:
        return {"error": _err(403, "AWAITING_APPROVAL", "Your account is waiting for approval.")}
    if user["status"] != ACTIVE or not user["role"]:
        return {"error": _err(403, "NOT_ALLOWED", "This account cannot log in.")}
    now = utcnow()
    if user["locked_until"] and parse_iso(user["locked_until"]) > now:
        return {"error": _locked_error(user["locked_until"], now)}

    password_ok = security.verify_password(password, user["password_hash"])
    second_factor_ok = True
    if password_ok and user["role"] == access.ADMIN:
        second_factor_ok = security.totp_valid(user["totp_secret"], code)
    if not (password_ok and second_factor_ok):
        locked = _record_failure(user, now)
        audit.write(user["id"], user["role"], "login-failed", user["id"], "DENIED")
        if locked:
            return {"error": _locked_error(locked, now)}
        if password_ok:
            return {"error": _err(401, "SECOND_FACTOR", "Authenticator code is wrong or missing.")}
        return {"error": _bad_credentials()}

    db.run("UPDATE users SET failed_count = 0, first_failure_at = NULL, locked_until = NULL WHERE id = ?",
           (user["id"],))
    audit.write(user["id"], user["role"], "login", user["id"], "OK")
    return {"ok": {**_new_session(user), "user": public_user(user)}}


# ---------- sessions: access pass (30 min) and refresh pass (7 days, rotated) ----------

def _new_session(user, family=None):
    raw = security.random_token()
    family = family or new_id("fam")
    db.run(
        "INSERT INTO refresh_tokens (token_hash, user_id, family_id, expires_at) VALUES (?, ?, ?, ?)",
        (security.sha256_hex(raw), user["id"], family, iso(utcnow() + timedelta(seconds=config.REFRESH_TTL))),
    )
    access_token = security.issue_access_token({"sub": user["id"], "role": user["role"]})
    return {"accessToken": access_token, "refreshToken": raw, "expiresIn": config.ACCESS_TTL,
            "tokenType": "Bearer"}


def refresh(raw_token):
    with db.tx():
        result = _rotate(raw_token)
    if "error" in result:
        raise ApiError(**result["error"])
    return result["ok"]


def _rotate(raw_token):
    row = db.row("SELECT * FROM refresh_tokens WHERE token_hash = ?", (security.sha256_hex(str(raw_token or "")),))
    if not row:
        return {"error": _err(401, "SESSION_UNKNOWN", "Session not recognised. Log in again.")}
    if row["used_at"]:
        # A used refresh pass was presented again: someone may have copied it. Cancel the whole session.
        db.run("UPDATE refresh_tokens SET revoked_at = ? WHERE family_id = ? AND revoked_at IS NULL",
               (iso(), row["family_id"]))
        audit.write(row["user_id"], None, "refresh-reuse", row["user_id"], "DENIED")
        return {"error": _err(401, "SESSION_CANCELLED", "Session cancelled for your safety. Log in again.")}
    if row["revoked_at"]:
        return {"error": _err(401, "SESSION_CANCELLED", "Session cancelled. Log in again.")}
    if parse_iso(row["expires_at"]) < utcnow():
        return {"error": _err(401, "SESSION_EXPIRED", "Session expired. Log in again.")}
    user = db.row("SELECT * FROM users WHERE id = ?", (row["user_id"],))
    if not user or user["status"] != ACTIVE or not user["role"]:
        return {"error": _err(401, "SESSION_CANCELLED", "Session cancelled. Log in again.")}
    db.run("UPDATE refresh_tokens SET used_at = ? WHERE token_hash = ?", (iso(), row["token_hash"]))
    return {"ok": _new_session(user, family=row["family_id"])}


def logout(raw_token):
    with db.tx():
        row = db.row("SELECT * FROM refresh_tokens WHERE token_hash = ?", (security.sha256_hex(str(raw_token or "")),))
        if row:
            db.run("UPDATE refresh_tokens SET revoked_at = ? WHERE family_id = ? AND revoked_at IS NULL",
                   (iso(), row["family_id"]))
            audit.write(row["user_id"], None, "logout", row["user_id"], "OK")
    return {"message": "Logged out."}


# ---------- password reset ----------

def request_reset(body):
    email = _email(body.get("email"))
    with db.tx():
        user = db.row("SELECT * FROM users WHERE email = ?", (email,)) if email else None
        if user and user["status"] != PENDING_VERIFICATION:
            token = _issue_token(user["id"], "reset", config.RESET_TTL)
            _send_mail(email, "Reset your Nutrient & Soil password",
                       f"Open this link within 30 minutes: {config.PUBLIC_BASE_URL}/#/reset?token={token}")
            audit.write(user["id"], user["role"], "password-reset-request", user["id"], "OK")
    return {"message": GENERIC_RESET}


def confirm_reset(body):
    problem = security.password_problem(body.get("newPassword") or "")
    if problem:
        raise ApiError(422, "WEAK_PASSWORD", problem)
    with db.tx():
        uid = _consume_token(body.get("token"), "reset")
        db.run("UPDATE users SET password_hash = ?, failed_count = 0, first_failure_at = NULL, locked_until = NULL "
               "WHERE id = ?", (security.hash_password(body["newPassword"]), uid))
        db.run("UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (iso(), uid))
        audit.write(uid, None, "password-reset", uid, "OK")
    return {"message": "Password changed. Log in again on your devices."}


def me(caller):
    user = db.row("SELECT * FROM users WHERE id = ?", (caller["id"],))
    fields = db.rows(
        "SELECT f.id, f.farm_name, f.region, f.anon_code FROM account_links l "
        "JOIN fields f ON f.id = l.field_id WHERE l.user_id = ? AND l.revoked_at IS NULL ORDER BY f.id",
        (caller["id"],),
    )
    return {"user": public_user(user), "fields": [
        {"fieldId": f["id"], "farmName": f["farm_name"], "region": f["region"], "fieldCode": f["anon_code"]}
        for f in fields]}
