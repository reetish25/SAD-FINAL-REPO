"""Who may see what. Every read goes through these checks (section 2.2 of the specification).

A caller is either a person ({"kind": "user", ...}) or a service ({"kind": "service", ...}).
"""
from . import db

ADMIN = "ADMIN"
OPERATOR = "FIELD_OPERATOR"
AGRONOMIST = "AGRONOMIST"
RESEARCHER = "RESEARCHER"
FARMER = "FARMER"
FIELD_ROLES = (OPERATOR, AGRONOMIST, FARMER)


def assigned_fields(user_id):
    rows = db.rows("SELECT field_id FROM account_links WHERE user_id = ? AND revoked_at IS NULL", (user_id,))
    return [r["field_id"] for r in rows]


def can_read_field(caller, field_id, scope):
    """Health and measurement reads: a service with the scope, or an assigned person."""
    if caller["kind"] == "service":
        return scope in caller["scopes"]
    return caller["role"] in FIELD_ROLES and field_id in assigned_fields(caller["id"])


def can_read_sample(caller, sample):
    """One sample: the owner (operator), an assigned agronomist, or a service with the scope."""
    if caller["kind"] == "service":
        return "soil-measurement-read" in caller["scopes"]
    if caller["role"] == OPERATOR:
        return sample["owner_user_id"] == caller["id"]
    if caller["role"] == AGRONOMIST:
        return sample["field_id"] in assigned_fields(caller["id"])
    return False
