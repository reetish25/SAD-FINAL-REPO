"""First-run setup. Safe to run every time: it only creates what is missing."""
import logging

from . import access, auth, config, db, security
from .util import iso

log = logging.getLogger("seed")

DEMO_FIELDS = [
    ("fld_0412", "Sunrise Farm", "Region North", "FLD-N01"),
    ("fld_0587", "Riverbend Plot", "Region South", "FLD-S02"),
    ("fld_0931", "Hillside Plot", "Region East", "FLD-E03"),
]
DEMO_USERS = [
    ("operator@soil.local", "Olivia Operator", access.OPERATOR, ["fld_0412"]),
    ("agronomist@soil.local", "Anil Agronomist", access.AGRONOMIST, ["fld_0412", "fld_0587", "fld_0931"]),
    ("farmer@soil.local", "Farah Farmer", access.FARMER, ["fld_0587"]),
    ("researcher@soil.local", "Riya Researcher", access.RESEARCHER, []),
]
DEMO_PASSWORD = "Demo-Password-2026"


def run():
    with db.tx():
        if not db.row("SELECT id FROM fields LIMIT 1"):
            for field_id, farm, region, code in DEMO_FIELDS:
                db.run("INSERT INTO fields (id, farm_name, region, anon_code, created_at) VALUES (?, ?, ?, ?, ?)",
                       (field_id, farm, region, code, iso()))

    if not db.row("SELECT id FROM users WHERE role = ?", (access.ADMIN,)):
        secret = config.ADMIN_TOTP_SECRET or security.new_totp_secret()
        auth.create_account(config.ADMIN_EMAIL, "Platform Administrator", "Leafline", access.ADMIN,
                            access.ADMIN, auth.ACTIVE, config.ADMIN_PASSWORD, secret)
        log.warning("Administrator %s created. Authenticator secret (keep it safe): %s",
                    config.ADMIN_EMAIL, secret)

    if config.SEED_DEMO:
        created = []
        for email, name, role, fields in DEMO_USERS:
            if db.row("SELECT id FROM users WHERE email = ?", (email,)):
                continue
            uid = auth.create_account(email, name, "Demo organisation", role, role, auth.ACTIVE, DEMO_PASSWORD)
            for field_id in fields:
                db.run("INSERT INTO account_links (user_id, field_id, granted_by, reason, granted_at) "
                       "VALUES (?, ?, 'seed', 'demo data', ?)", (uid, field_id, iso()))
            created.append(email)
        if created:
            log.warning("Demo accounts created (password %s): %s", DEMO_PASSWORD, ", ".join(created))
