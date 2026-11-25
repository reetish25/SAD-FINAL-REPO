"""HTTP routes. Each route maps one web address to one business function.

Access is checked here (who is calling) and again in the business modules (what they may see).
"""
import hmac
import re
from datetime import date

from . import access, admin, auth, config, db, history, integration, samples, security, soil_health
from .errors import ApiError
from .util import utcnow

P = "/api/v1/soil"
ROUTES = []


class Request:
    def __init__(self, method, path, query, body, headers, request_id):
        self.method = method
        self.path = path
        self.query = query
        self.body = body
        self.headers = headers
        self.request_id = request_id

    def json(self):
        if self.body is None:
            return {}
        if not isinstance(self.body, dict):
            raise ApiError(400, "BAD_REQUEST", "Send a JSON object.")
        return self.body


class Route:
    def __init__(self, method, template, handler, summary, access_rule):
        self.method = method
        self.template = template
        self.handler = handler
        self.summary = summary
        self.access_rule = access_rule
        self.regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template) + "$")


def route(method, template, summary, access_rule):
    def wrap(fn):
        ROUTES.append(Route(method, template, fn, summary, access_rule))
        return fn
    return wrap


# ---------- who is calling ----------

def user_caller(req, roles=None):
    header = req.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError(401, "NOT_LOGGED_IN", "Log in to continue.")
    try:
        claims = security.read_access_token(header[7:].strip())
    except security.TokenExpired:
        raise ApiError(401, "PASS_EXPIRED", "Pass expired, refresh it.")
    except security.TokenInvalid:
        raise ApiError(401, "NOT_LOGGED_IN", "Log in to continue.")
    user = db.row("SELECT id, role, status FROM users WHERE id = ?", (claims.get("sub"),))
    if not user or user["status"] != auth.ACTIVE or not user["role"]:
        raise ApiError(401, "NOT_LOGGED_IN", "Log in to continue.")
    if roles and user["role"] not in roles:
        raise ApiError(403, "NOT_ALLOWED", "Your role cannot do this.")
    return {"kind": "user", "id": user["id"], "role": user["role"], "scopes": frozenset()}


def service_caller(req, scope):
    client_id = req.headers.get("x-client-id", "")
    client = config.SERVICE_CLIENTS.get(client_id)
    given = req.headers.get("x-client-secret", "")
    if not client or not hmac.compare_digest(client["secret"], given):
        raise ApiError(401, "SERVICE_AUTH_FAILED", "Service credentials are missing or wrong.")
    if scope not in client["scopes"]:
        raise ApiError(403, "SCOPE_DENIED", f"{client_id} may not call this endpoint.")
    return {"kind": "service", "id": client_id, "role": "SERVICE", "scopes": client["scopes"]}


def read_caller(req, scope, roles=None):
    if req.headers.get("x-client-id"):
        return service_caller(req, scope)
    return user_caller(req, roles)


# ---------- authentication ----------

@route("POST", P + "/auth/register", "Register a new account (pending verification)", "public")
def _register(req):
    return 202, auth.register(req.json())


@route("GET", P + "/auth/verify", "Verify email with the link token", "public")
def _verify(req):
    return 200, auth.verify(req.query.get("token"))


@route("POST", P + "/auth/login", "Log in: returns an access pass (30 min) and a refresh pass (7 days)", "public")
def _login(req):
    return 200, auth.login(req.json())


@route("POST", P + "/auth/refresh", "Exchange a refresh pass for a new pair (rotation)", "public")
def _refresh(req):
    return 200, auth.refresh(req.json().get("refreshToken"))


@route("POST", P + "/auth/logout", "Cancel the refresh pass", "public")
def _logout(req):
    return 200, auth.logout(req.json().get("refreshToken"))


@route("POST", P + "/auth/password-reset", "Email a password reset link", "public")
def _reset_request(req):
    return 202, auth.request_reset(req.json())


@route("POST", P + "/auth/password-reset/confirm", "Set a new password with the reset link", "public")
def _reset_confirm(req):
    return 200, auth.confirm_reset(req.json())


@route("GET", P + "/auth/me", "Your account, role and assigned fields", "user")
def _me(req):
    return 200, auth.me(user_caller(req))


# ---------- Module 1: soil data ----------

@route("POST", P + "/soil-measurements", "Submit one soil sample for an assigned field (Field Operator)", "user")
def _submit(req):
    return 202, samples.submit(user_caller(req, [access.OPERATOR]), req.json())


@route("GET", P + "/soil-measurements", "List the samples you may see", "user")
def _list(req):
    return 200, samples.list_samples(user_caller(req), req.query)


@route("GET", P + "/soil-measurements/{sample_id}", "Read one sample (owner, assigned agronomist or service)", "user or service")
def _read(req, sample_id):
    return 200, samples.read(read_caller(req, "soil-measurement-read"), sample_id, req.query.get("version"))


@route("POST", P + "/soil-measurements/{sample_id}/corrections", "Correct your own sample within 7 days (new version)", "user")
def _correct(req, sample_id):
    return 202, samples.correct(user_caller(req, [access.OPERATOR]), sample_id, req.json())


@route("POST", P + "/soil-measurements/{sample_id}/reanalyse", "Analyse again a sample whose analysis failed", "user")
def _reanalyse(req, sample_id):
    return 202, samples.reanalyse(user_caller(req, [access.OPERATOR]), sample_id)


@route("GET", P + "/soil-data", "Measurement values for a field (AI Analytics, Plant Health, assigned people)", "user or service")
def _soil_data(req):
    return 200, samples.soil_data(read_caller(req, "soil-data", roles=(access.AGRONOMIST, access.FARMER)), req.query)


@route("GET", P + "/fields", "Fields you are assigned to", "user")
def _fields(req):
    caller = user_caller(req, access.FIELD_ROLES)
    return 200, samples.my_fields(caller)


# ---------- Modules 4 and 5: health and flags ----------

@route("GET", P + "/soil-health", "Health (GOOD/FAIR/POOR) and nutrient flags for a field", "user or service")
def _health(req):
    caller = read_caller(req, "soil-health", roles=access.FIELD_ROLES)
    return 200, soil_health.get(caller, req.query)


# ---------- Module 6: history ----------

@route("GET", P + "/soil-history", "Field history; anonymous for researchers", "user or service")
def _history(req):
    caller = read_caller(req, "soil-history", roles=(access.OPERATOR, access.AGRONOMIST, access.FARMER,
                                                      access.RESEARCHER))
    return 200, history.get(caller, req.query)


# ---------- administration ----------

@route("GET", P + "/admin/accounts", "All accounts (optionally by status)", "admin")
def _accounts(req):
    user_caller(req, [access.ADMIN])
    return 200, admin.list_accounts(req.query.get("status"))


@route("POST", P + "/admin/accounts/{user_id}/approve", "Approve a registration and set its role", "admin")
def _approve(req, user_id):
    return 200, admin.approve(user_caller(req, [access.ADMIN]), user_id, req.json().get("role"))


@route("POST", P + "/admin/accounts/{user_id}/reject", "Reject a registration", "admin")
def _reject(req, user_id):
    return 200, admin.reject(user_caller(req, [access.ADMIN]), user_id)


@route("POST", P + "/admin/accounts/{user_id}/revoke-sessions", "Cancel every session of a person now", "admin")
def _revoke(req, user_id):
    return 200, admin.revoke_sessions(user_caller(req, [access.ADMIN]), user_id)


@route("POST", P + "/admin/assignments", "Assign a person to a field (logged, with reason)", "admin")
def _assign(req):
    return 200, admin.assign(user_caller(req, [access.ADMIN]), req.json())


@route("POST", P + "/admin/assignments/remove", "Remove a person's field assignment (logged)", "admin")
def _unassign(req):
    return 200, admin.unassign(user_caller(req, [access.ADMIN]), req.json())


@route("GET", P + "/admin/fields", "List fields", "admin")
def _fields_list(req):
    user_caller(req, [access.ADMIN])
    return 200, admin.list_fields()


@route("POST", P + "/admin/fields", "Create a field", "admin")
def _fields_create(req):
    return 201, admin.create_field(user_caller(req, [access.ADMIN]), req.json())


@route("POST", P + "/admin/admins", "Create another administrator (shows the second-factor secret once)", "admin")
def _create_admin(req):
    return 201, admin.create_admin(user_caller(req, [access.ADMIN]), req.json())


@route("GET", P + "/admin/audit-log", "Activity log (no measurement values)", "admin")
def _audit(req):
    user_caller(req, [access.ADMIN])
    return 200, admin.audit_log(req.query)


@route("GET", P + "/integration/peers", "Other services this one is connected to, and whether they answer", "admin")
def _peers(req):
    user_caller(req, [access.ADMIN])
    return 200, integration.peer_status()


# ---------- system ----------

def _health_payload():
    return {"status": "ok", "service": config.SERVICE_NAME, "version": config.SERVICE_VERSION,
            "database": "ok" if db.ping() else "down", "time": utcnow().isoformat() + "Z"}


@route("GET", "/health", "Liveness check for the load balancer", "public")
def _liveness(req):
    return 200, _health_payload()


@route("GET", P + "/health", "Liveness check (same as /health)", "public")
def _liveness_api(req):
    return 200, _health_payload()


@route("GET", P + "/dev/outbox", "Development mail outbox (verification and reset links)", "public in dev only")
def _outbox(req):
    if not config.DEV_MODE:
        raise ApiError(404, "NOT_FOUND", "Not available.")
    return 200, admin.outbox()


@route("GET", P + "/openapi.json", "Description of every address in this service", "public")
def _openapi(req):
    paths = {}
    for r in ROUTES:
        paths.setdefault(r.template, {})[r.method.lower()] = {
            "summary": r.summary, "x-access": r.access_rule,
            "responses": {"200": {"description": "OK"}, "401": {"description": "Not logged in"},
                          "403": {"description": "Not allowed"}, "404": {"description": "Not found"}},
        }
    return 200, {"openapi": "3.0.3",
                 "info": {"title": "Nutrient & Soil Service", "version": config.SERVICE_VERSION,
                          "description": f"Generated {date.today().isoformat()}"},
                 "paths": paths}


# ---------- dispatch ----------

def dispatch(req):
    matched_path = False
    for r in ROUTES:
        m = r.regex.match(req.path)
        if not m:
            continue
        matched_path = True
        if r.method != req.method:
            continue
        return r.handler(req, **m.groupdict())
    if matched_path:
        raise ApiError(405, "METHOD_NOT_ALLOWED", "This address does not accept that method.")
    raise ApiError(404, "NOT_FOUND", "No such address in this service.")
