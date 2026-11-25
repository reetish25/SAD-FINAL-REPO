# Nutrient & Soil Service

Service 2 of 4 in the **Leafline** sunflower health platform. It keeps soil test results for each field, checks that every value is possible, stores it safely, works out how healthy the soil is, and flags nutrients that are too low or too high. It has its **own business rules, its own database and its own web app**, and it talks to other services only through its REST API.

It follows the *Nutrient & Soil Service* specification (v1.0, 26 October 2026).

---

## 1. Run it (no installation needed)

You need Python 3.10 or newer. The service uses only the standard library.

```bash
cd nutrient-soil-service
python3 -m soil_service
```

Then open **http://localhost:8091** in a browser.

On first run the service creates its database (`data/soil.db`), three demo fields and these accounts:

| Account | Password | What it can do |
|---|---|---|
| `operator@soil.local` | `Demo-Password-2026` | Field Operator: submit and correct samples on *Sunrise Farm* |
| `agronomist@soil.local` | `Demo-Password-2026` | Agronomist: read health, flags and history for all three fields |
| `farmer@soil.local` | `Demo-Password-2026` | Farmer: read health and history for *Riverbend Plot* |
| `researcher@soil.local` | `Demo-Password-2026` | Researcher: anonymous history only |
| `admin@soil.local` | `Admin-Change-Me-2026` + authenticator code | Administrator: approvals, field assignments, activity log |

The administrator's **authenticator secret** is printed in the console the first time the service starts. Add it to an authenticator app (Google Authenticator, Authy, etc.) to get the 6-digit code that the admin login asks for.

Set `SEED_DEMO=false` and change `ADMIN_PASSWORD` before using the service for anything real.

### Demo flow (about 2 minutes)
1. Log in as **operator@soil.local** and submit a sample for *Sunrise Farm*. You get a sample page that refreshes while the analysis runs.
2. Log in as **agronomist@soil.local** and open *Health* for the field: GOOD/FAIR/POOR, with the nutrients that are too low or too high.
3. Log in as **researcher@soil.local** and open the anonymous history: field codes and regions only.
4. Register a new account from the login page. Open **Mail (dev)** to find the verification link, then approve the account as the administrator.

### Using Docker
```bash
cp .env.example .env          # then change the secrets
docker compose up --build     # api on :8091, worker in its own container
```

### Tests
```bash
python3 -m unittest discover -s tests -t . -v
```
45 tests: the business rules at every boundary in the specification, and end-to-end tests over real HTTP (sign-in and lock-out, verification and approval, submission and rejection, the worker, corrections as new versions, the AI-outage path, anonymous research history, and service credentials).

---

## 2. Project layout

```
nutrient-soil-service/
├── soil_service/            the service (Python)
│   ├── api.py               HTTP routes: one address -> one business function, with access checks
│   ├── server.py            HTTP server, security headers, static web app
│   ├── auth.py              Module: accounts and sessions (register, verify, login, lock, refresh, reset)
│   ├── samples.py           Module 1: Soil Data Management (submit, correct as versions, read, list)
│   ├── rules.py             Pure business rules: ranges, units, flags, severity, health score
│   ├── soil_health.py       Modules 4 and 5: health result and nutrient deficiency/excess
│   ├── history.py           Module 6: Soil History with the anonymiser
│   ├── admin.py             Administration: approvals, assignments, fields, activity log
│   ├── analysis.py          Background worker: lock, rules, AI call with retries, save results
│   ├── ai_client.py         Soil & Nutrient AI client (separate service, or built-in model)
│   ├── access.py            Who may read which sample, field or history
│   ├── integration.py       Calls to and from other microservices
│   ├── db.py / seed.py      Own database (SQLite), append-only protection, first-run setup
│   ├── security.py          Password hashing, signed access passes, one-time codes
│   └── config.py            All settings (environment variables)
├── static/                  Web app: index.html, css/style.css, js/app.js
├── tests/                   Unit tests (rules) and end-to-end tests (HTTP)
├── Dockerfile, docker-compose.yml, .env.example, .github/workflows/ci.yml
```

Each module keeps the three layers from the specification: **API** (the routes in `api.py`) → **business rules** (`rules.py`, and the module services) → **data access** (`db.py`). Only `db.py` talks to the database.

---

## 3. What the service does, mapped to the specification

| Specification | Where it is |
|---|---|
| NS-FR-01 to 04 collect and store NPK, pH, moisture | `POST /soil-measurements` → `samples.submit` |
| NS-FR-05 soil health GOOD/FAIR/POOR (section 7.3) | `rules.health_status`, `GET /soil-health` |
| NS-FR-06/07 deficiency and excess with severity (10 % / 25 %) | `rules.severity`, `soil_health.get` |
| NS-FR-08 history, never lost | `GET /soil-history`; samples are append-only |
| NS-FR-09 authorised services and users only, 404 otherwise | `access.py`, service credentials in `api.py` |
| NS-BR-01 never overwritten; correction = new version | `POST /soil-measurements/{id}/corrections`; SQLite triggers refuse updates to values |
| NS-BR-02 out of possible range → 422, nothing saved | `rules.check_value` |
| NS-BR-03 in possible range but outside good range → saved and flagged | `rules.rule_flags` |
| NS-BR-04 fixed units, never converted | `rules.check_units` |
| NS-BR-06 anonymous history | `history.py` (made-up field code, region only) |
| NS-BR-07 date not future, not older than 5 years | `rules.check_sample_date` |
| NS-BR-08 one current sample per field, date and depth | duplicate check → 409 |
| NS-AUTH-02 to 12 accounts and sessions | `auth.py` (see section 5 for limits) |
| Sample states RECEIVED → ANALYSING → READY / ANALYSIS_FAILED | `analysis.py`, `samples.py` |
| QA-S1 AI down: sample saved, rule flags shown, AI view pending | `analysis._finish` with `ai_view = PENDING` |
| Rate limit 100 submissions per person per hour → 429 | `samples.submit` |
| Activity log without measurement values, append-only | `audit.py`, SQLite trigger on `audit_log` |
| Ports and health check (section 12) | `GET /health`; port 8091 by default |

---

## 4. The API

All addresses start with **`/api/v1/soil`**. Replies are JSON. A full machine-readable description is at `GET /api/v1/soil/openapi.json`. Log in first and send the access pass as `Authorization: Bearer <token>`.

| Method and address | Who | Purpose |
|---|---|---|
| `POST /auth/register`, `GET /auth/verify?token=`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` | anyone / logged-in | accounts and sessions |
| `POST /auth/password-reset`, `POST /auth/password-reset/confirm` | anyone | reset a forgotten password |
| `GET /auth/me`, `GET /fields` | logged-in | own account and assigned fields |
| `POST /soil-measurements` | Field Operator (assigned field) | submit one sample → `202` |
| `GET /soil-measurements?fieldId=` | assigned people | list samples |
| `GET /soil-measurements/{id}` | owner, assigned agronomist, service | one sample with values, flags, health and versions |
| `POST /soil-measurements/{id}/corrections` | owner, within 7 days | correction as a new version → `202` |
| `POST /soil-measurements/{id}/reanalyse` | owner, if analysis failed | analyse again |
| `GET /soil-health?fieldId=&date=` | assigned people, Farmer (own fields), services | health and flags |
| `GET /soil-data?fieldId=&from=&to=` | services, assigned agronomist/farmer | READY measurement values |
| `GET /soil-history?fieldId=&region=&from=&to=` | assigned people; researchers (anonymous) ; services | history |
| `/admin/...` | Administrator | accounts, approvals, assignments, fields, admins, audit log |
| `GET /integration/peers` | Administrator | which connected services answer |
| `GET /health` | anyone | liveness for the load balancer |

**Example: submit a sample**
```bash
curl -X POST localhost:8091/api/v1/soil/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"operator@soil.local","password":"Demo-Password-2026"}'
# copy accessToken, then:
curl -X POST localhost:8091/api/v1/soil/soil-measurements \
  -H "Authorization: Bearer <accessToken>" -H 'Content-Type: application/json' \
  -d '{"fieldId":"fld_0412","sampleDate":"2026-10-20","depthCm":20,"nitrogenMgKg":28,
       "phosphorusMgKg":22,"potassiumMgKg":180,"ph":6.8,"moisturePct":31}'
```

---

## 5. Honest limits of this version

This is a complete, working implementation for the course. Some parts are simplified on purpose, and you should say so in the report:

- **Identity** runs inside this service. In the full platform it belongs to Identity & Access at the API Gateway (the specification's design). The rules (verification, approval, 5-failure lock, 30-minute passes, rotating 7-day refresh pass, reuse cancels the session, reset cancels sessions, no self-promotion) are all implemented here.
- **Email** is written to the outbox and the console, not sent. In production, replace `auth._send_mail` with an SMTP call.
- **Passwords** are checked against a small built-in list of leaked passwords. A real deployment should use a full breached-password list.
- **Administrator second factor** is a TOTP code (RFC 6238). Other users have no second factor, as the specification allows for the proposed design.
- **Storage** is SQLite, one file. It is fine for one copy of the service. Several copies behind a load balancer need PostgreSQL (see the specification's ADR and section 12).
- **Measurement values** sit in one table row per version, not in a separate measurement table. Each version is still immutable (triggers).
- **Good ranges** (section 7.2) are the specification's starting values. An agronomist must sign them off (decision D-S3).
- **Not included:** bulk import (D-S5), data export (D-S6), the 200-operator load test, the event bus (the specification says everything goes through the API), and the full CI/CD stages for staging and production.
- The **AI** is a built-in model with the agreed request and reply format. Set `SOIL_AI_URL` to use the separate Soil & Nutrient AI service instead.

---

## 6. Connecting the other microservices

The service is built so the other services can connect without any change to its code.

**The other services call us.** Each service that calls this one gets a client ID and secret, listed in `config.SERVICE_CLIENTS`:

```python
"ai-analytics": {"secret": "...", "scopes": {"soil-data", "soil-health", "soil-history", "soil-measurement-read"}},
```

It then sends these headers on every call:
```
X-Client-Id: ai-analytics
X-Client-Secret: <secret>
```
Each call is checked against the listed scopes. For example, AI Analytics can read `GET /soil-health` and `GET /soil-data`, but not submit samples. Set the real secrets with environment variables (`AI_ANALYTICS_SECRET`, `PLANT_HEALTH_SECRET`) and rotate them every 90 days.

**We call them.** Describe the other service in `PEER_SERVICES` (one line of JSON in the environment):

```bash
PEER_SERVICES='{"ai-analytics": {"url": "http://ai-analytics:8095", "client_id": "nutrient-soil-service", "secret": "..."}}'
```

Then, in any module:
```python
from soil_service import integration
integration.call_peer("ai-analytics", "/api/v1/analytics/health")
```
`GET /api/v1/soil/integration/peers` (administrator) shows whether each configured service answers.

**Adding a new service later** takes three steps: add its client to `SERVICE_CLIENTS` (what it may read), add it to `PEER_SERVICES` (where we call it), and add tests for the agreed format in `tests/test_service.py`. Nothing else in this service changes.

**Plant Health and AI Analytics** read our data through the endpoints above. The data format is the contract; changing a field name requires agreement from all four team members (specification section 17.10).

---

## 7. Operations

- **Health:** `GET /health` returns `ok` when the database answers.
- **Logs:** one line per request with the request ID. Measurement values are never logged.
- **Worker:** runs inside the API process by default. For separate scaling use `RUN_WORKER_IN_API=false` and `python -m soil_service worker` (this is what `docker-compose.yml` does).
- **Backups:** copy `data/soil.db` while the service is stopped, or use SQLite's `.backup` command.
- **Security headers:** strict content security policy, no framing, no caching of API replies.
