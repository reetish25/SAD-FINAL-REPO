"""Security helpers using only the Python standard library.

- Passwords: PBKDF2-SHA256 with a random salt (never stored in plain text).
- Access passes: HS256-signed tokens (the same format as a JWT).
- Admin second factor: TOTP codes (RFC 6238), compatible with common authenticator apps.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import struct
import time

from . import config

# A small built-in list. A real deployment should check a full breached-password list.
LEAKED = {
    "password1234", "password12345", "123456789012", "qwertyuiop123",
    "letmein12345", "welcome12345", "leafline2026", "soil-soil-2026",
}


class TokenInvalid(Exception):
    pass


class TokenExpired(Exception):
    pass


# ---------- passwords ----------

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, config.PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${config.PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


def password_problem(password):
    """Return a message if the password breaks the policy, otherwise None."""
    if len(password or "") < 12:
        return "Password must have at least 12 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must include letters and numbers."
    if password.lower() in LEAKED:
        return "This password appears on a list of leaked passwords. Choose another."
    return None


# ---------- tokens ----------

def sha256_hex(text):
    return hashlib.sha256(text.encode()).hexdigest()


def random_token():
    return secrets.token_urlsafe(32)


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(signing_input):
    digest = hmac.new(config.JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    return _b64(digest)


def issue_access_token(claims):
    now = int(time.time())
    body = {**claims, "typ": "access", "iat": now, "exp": now + config.ACCESS_TTL, "jti": secrets.token_hex(8)}
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    return f"{head}.{payload}.{_sign(head + '.' + payload)}"


def read_access_token(token):
    try:
        head, payload, signature = token.split(".")
    except ValueError:
        raise TokenInvalid()
    if not hmac.compare_digest(_sign(f"{head}.{payload}"), signature):
        raise TokenInvalid()
    try:
        body = json.loads(_unb64(payload))
    except ValueError:
        raise TokenInvalid()
    if body.get("typ") != "access":
        raise TokenInvalid()
    if body.get("exp", 0) < time.time():
        raise TokenExpired()
    return body


# ---------- admin second factor (TOTP) ----------

def new_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp_code(secret, counter):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1000000:06d}"


def totp_valid(secret, code, window=1):
    if not secret or not code:
        return False
    counter = int(time.time() // 30)
    code = str(code).strip()
    return any(hmac.compare_digest(totp_code(secret, counter + d), code) for d in range(-window, window + 1))
