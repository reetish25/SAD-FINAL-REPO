"""Settings for the Nutrient & Soil service. Every value can be changed with an environment variable."""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env(name, default):
    return os.environ.get(name, default)


def _bool(name, default):
    return _env(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


SERVICE_NAME = "nutrient-soil-service"
SERVICE_VERSION = "1.0.0"

HOST = _env("HOST", "0.0.0.0")
PORT = int(_env("PORT", "8091"))
PUBLIC_BASE_URL = _env("PUBLIC_BASE_URL", f"http://localhost:{PORT}")
DB_PATH = _env("DB_PATH", os.path.join(BASE_DIR, "data", "soil.db"))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Security
JWT_SECRET = _env("JWT_SECRET", "dev-only-secret-change-me-before-production")
ACCESS_TTL = 30 * 60              # access pass: 30 minutes
REFRESH_TTL = 7 * 24 * 3600       # refresh pass: 7 days
VERIFY_TTL = 24 * 3600            # email verification link: 24 hours
RESET_TTL = 30 * 60               # password reset link: 30 minutes
LOCK_FAILURES = 5                 # failed logins ...
LOCK_WINDOW = 15 * 60             # ... within 15 minutes ...
LOCK_DURATION = 15 * 60           # ... lock the account for 15 minutes
PASSWORD_ITERATIONS = int(_env("PASSWORD_ITERATIONS", "200000"))

# Business limits
SUBMIT_LIMIT_PER_HOUR = 100
CORRECTION_WINDOW = 7 * 24 * 3600
AI_MAX_ATTEMPTS = 3
AI_RETRY_DELAYS = (5, 20, 60)     # seconds to wait after attempt 1, 2 (and 3)
AI_TIMEOUT = 30

# Soil & Nutrient AI. Empty URL = use the built-in model with the same contract.
SOIL_AI_URL = _env("SOIL_AI_URL", "")
SOIL_AI_CLIENT_ID = _env("SOIL_AI_CLIENT_ID", SERVICE_NAME)
SOIL_AI_SECRET = _env("SOIL_AI_SECRET", "soil-ai-dev-secret")
SOIL_AI_FAIL = _bool("SOIL_AI_FAIL", False)  # switch on to simulate the AI being down

# Running and first-run setup
DEV_MODE = _bool("DEV_MODE", True)            # shows the mail outbox and console links
SEED_DEMO = _bool("SEED_DEMO", True)          # creates demo fields and accounts on first run
RUN_WORKER_IN_API = _bool("RUN_WORKER_IN_API", True)
ADMIN_EMAIL = _env("ADMIN_EMAIL", "admin@soil.local")
ADMIN_PASSWORD = _env("ADMIN_PASSWORD", "Admin-Change-Me-2026")
ADMIN_TOTP_SECRET = _env("ADMIN_TOTP_SECRET", "")

# Services allowed to call THIS service (read-only, listed scopes only).
SERVICE_CLIENTS = {
    "ai-analytics": {
        "secret": _env("AI_ANALYTICS_SECRET", "ai-analytics-dev-secret"),
        "scopes": {"soil-data", "soil-health", "soil-history", "soil-measurement-read"},
    },
    "plant-health": {
        "secret": _env("PLANT_HEALTH_SECRET", "plant-health-dev-secret"),
        "scopes": {"soil-data", "soil-health"},
    },
}

# Services THIS service can call. Filled in when the other microservices are deployed.
# Example (set in the environment as one line of JSON):
# {"ai-analytics": {"url": "http://ai-analytics:8095", "client_id": "nutrient-soil-service", "secret": "..."}}
PEER_SERVICES = json.loads(_env("PEER_SERVICES", "{}"))
