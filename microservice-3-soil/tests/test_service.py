"""End-to-end tests over real HTTP. The server runs in a thread with a temporary database."""
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

TMP = tempfile.mkdtemp(prefix="soil-test-")
os.environ.update({
    "DB_PATH": os.path.join(TMP, "soil.db"),
    "PASSWORD_ITERATIONS": "1000",
    "PORT": "0",
    "RUN_WORKER_IN_API": "false",
    "SEED_DEMO": "true",
    "DEV_MODE": "true",
})

from soil_service import ai_client, admin, analysis, config, db, security, seed  # noqa: E402
from soil_service.server import make_server  # noqa: E402

config.AI_RETRY_DELAYS = (0, 0, 0)
DEMO_PW = seed.DEMO_PASSWORD


class Api:
    def __init__(self, base):
        self.base = base

    def call(self, method, path, body=None, token=None, headers=None):
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = "Bearer " + token
        h.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def login(self, email, password, code=None):
        body = {"email": email, "password": password}
        if code:
            body["totpCode"] = code
        return self.call("POST", "/auth/login", body)


def submission(**overrides):
    body = {"fieldId": "fld_0412", "sampleDate": "2026-10-20", "depthCm": 20, "nitrogenMgKg": 28,
            "phosphorusMgKg": 22, "potassiumMgKg": 180, "ph": 6.8, "moisturePct": 31}
    body.update(overrides)
    return body


def drain_worker():
    """Run the background worker until the queue is empty (what the worker thread does forever)."""
    while True:
        job = analysis.claim_next("test-worker")
        if job is None:
            return
        analysis.process(job)


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_schema()
        seed.run()
        cls.server = make_server()
        port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.api = Api(f"http://127.0.0.1:{port}/api/v1/soil")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)

    def operator(self):
        status, body = self.api.login("operator@soil.local", DEMO_PW)
        self.assertEqual(status, 200, body)
        return body["accessToken"]

    # ----- health and access to the web app -----

    def test_health_and_web_app(self):
        status, body = self.api.call("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        req = urllib.request.urlopen(self.api.base.replace("/api/v1/soil", "/"))
        self.assertIn(b"Nutrient", req.read())

    def test_static_path_traversal_is_refused(self):
        try:
            urllib.request.urlopen(self.api.base.replace("/api/v1/soil", "/../config.py"))
            self.fail("should not serve files outside static/")
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (400, 404))

    # ----- sign-in rules -----

    def test_unknown_email_and_wrong_password_look_the_same(self):
        s1, b1 = self.api.login("nobody@soil.local", "Whatever-1234")
        s2, b2 = self.api.login("operator@soil.local", "Wrong-Password-1")
        self.assertEqual((s1, b1["error"]["message"]), (s2, b2["error"]["message"]))

    def test_registration_then_verification_then_approval(self):
        email = "new.agronomist@example.org"
        status, body = self.api.call("POST", "/auth/register", {
            "fullName": "Neha Rao", "email": email, "organisation": "Example Farms",
            "requestedRole": "AGRONOMIST", "password": "Long-Secure-Pass-9"})
        self.assertEqual(status, 202)
        # Same reply for an email that is already registered (no account discovery).
        status2, body2 = self.api.call("POST", "/auth/register", {
            "fullName": "Neha Rao", "email": email, "organisation": "Example Farms",
            "requestedRole": "AGRONOMIST", "password": "Long-Secure-Pass-9"})
        self.assertEqual(body, body2)

        self.assertEqual(self.api.login(email, "Long-Secure-Pass-9")[0], 403)  # not verified yet

        outbox = self.api.call("GET", "/dev/outbox", token=self.operator())[1]["items"]
        link = next(m["body"] for m in outbox if m["to"] == email)
        token = link.split("token=")[1]
        self.assertEqual(self.api.call("GET", "/auth/verify?token=" + token)[0], 200)
        self.assertEqual(self.api.call("GET", "/auth/verify?token=" + token)[0], 400)  # works once

        status, body = self.api.login(email, "Long-Secure-Pass-9")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "AWAITING_APPROVAL")

        pending = self.api.call("GET", "/admin/accounts?status=PENDING_APPROVAL", token=self._admin_token())[1]
        uid = next(i["id"] for i in pending["items"] if i["email"] == email)
        self.assertEqual(self.api.call("POST", f"/admin/accounts/{uid}/approve", {}, self._admin_token())[0], 200)
        self.assertEqual(self.api.login(email, "Long-Secure-Pass-9")[0], 200)

    def test_weak_password_is_refused(self):
        status, body = self.api.call("POST", "/auth/register", {
            "fullName": "Weak Pass", "email": "weak@example.org", "organisation": "Example",
            "requestedRole": "FARMER", "password": "short1"})
        self.assertEqual(status, 422)

    def test_admin_cannot_be_self_registered(self):
        status, _ = self.api.call("POST", "/auth/register", {
            "fullName": "Sneaky", "email": "sneaky@example.org", "organisation": "Example",
            "requestedRole": "ADMIN", "password": "Long-Secure-Pass-9"})
        self.assertEqual(status, 400)

    def test_five_failures_lock_the_account(self):
        email = "agronomist@soil.local"
        seen = []
        for _ in range(5):
            seen.append(self.api.login(email, "Wrong-Password-1")[0])
        self.assertEqual(seen[-1], 423)
        status, body = self.api.login(email, DEMO_PW)
        self.assertEqual(status, 423)
        self.assertIn("minutes", body["error"]["message"])
        # release the lock for later tests
        db.run("UPDATE users SET locked_until = NULL, failed_count = 0 WHERE email = ?", (email,))

    def test_admin_needs_second_factor(self):
        admin_row = db.row("SELECT totp_secret FROM users WHERE role = 'ADMIN' LIMIT 1")
        status, body = self.api.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD)
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "SECOND_FACTOR")
        code = security.totp_code(admin_row["totp_secret"], int(__import__("time").time() // 30))
        self.assertEqual(self.api.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD, code)[0], 200)

    def _admin_token(self):
        admin_row = db.row("SELECT totp_secret FROM users WHERE role = 'ADMIN' LIMIT 1")
        code = security.totp_code(admin_row["totp_secret"], int(__import__("time").time() // 30))
        return self.api.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD, code)[1]["accessToken"]

    def test_refresh_rotates_and_reuse_cancels_the_session(self):
        _, first = self.api.login("farmer@soil.local", DEMO_PW)
        old_refresh = first["refreshToken"]
        status, second = self.api.call("POST", "/auth/refresh", {"refreshToken": old_refresh})
        self.assertEqual(status, 200)
        self.assertEqual(self.api.call("POST", "/auth/refresh", {"refreshToken": old_refresh})[0], 401)
        # the newer pass from the same session is cancelled too
        self.assertEqual(self.api.call("POST", "/auth/refresh", {"refreshToken": second["refreshToken"]})[0], 401)

    def test_expired_pass_says_refresh_it(self):
        _, body = self.api.login("farmer@soil.local", DEMO_PW)
        import time
        claims = security.read_access_token(body["accessToken"])
        real_now = time.time
        try:
            time.time = lambda: real_now() + 3 * 3600
            status, err = self.api.call("GET", "/auth/me", token=body["accessToken"])
        finally:
            time.time = real_now
        self.assertEqual(status, 401)
        self.assertEqual(err["error"]["code"], "PASS_EXPIRED")
        self.assertTrue(claims["sub"])

    # ----- Module 1: submission, rules and correction -----

    def test_submit_then_worker_then_health(self):
        token = self.operator()
        status, body = self.api.call("POST", "/soil-measurements", submission(), token)
        self.assertEqual(status, 202, body)
        self.assertEqual(body["state"], "RECEIVED")
        sid = body["sampleId"]
        drain_worker()
        status, sample = self.api.call("GET", f"/soil-measurements/{sid}", token=token)
        self.assertEqual(sample["state"], "READY")
        self.assertIsNotNone(sample["health"])
        self.assertTrue(sample["canCorrect"])
        status, health = self.api.call("GET", "/soil-health?fieldId=fld_0412&date=2026-12-31", token=token)
        self.assertEqual(status, 200)
        self.assertIn(health["healthStatus"], ("GOOD", "FAIR", "POOR"))
        self.assertEqual(len(health["flags"]), 5)

    def test_out_of_range_refused_and_nothing_saved(self):
        token = self.operator()
        before = db.row("SELECT COUNT(*) AS n FROM soil_samples")["n"]
        status, body = self.api.call("POST", "/soil-measurements", submission(ph=15, sampleDate="2026-10-01"), token)
        self.assertEqual(status, 422)
        self.assertEqual(db.row("SELECT COUNT(*) AS n FROM soil_samples")["n"], before)

    def test_unit_mismatch_refused(self):
        token = self.operator()
        status, body = self.api.call("POST", "/soil-measurements",
                                     submission(sampleDate="2026-10-02", units={"nitrogen": "ppm"}), token)
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "UNIT_MISMATCH")

    def test_duplicate_refused(self):
        token = self.operator()
        self.api.call("POST", "/soil-measurements", submission(sampleDate="2026-10-03", depthCm=30), token)
        status, body = self.api.call("POST", "/soil-measurements", submission(sampleDate="2026-10-03", depthCm=30), token)
        self.assertEqual(status, 409)

    def test_unassigned_field_refused(self):
        status, body = self.api.call("POST", "/soil-measurements", submission(fieldId="fld_0931",
                                     sampleDate="2026-10-04"), self.operator())
        self.assertEqual(status, 403)

    def test_correction_creates_a_new_version_and_keeps_the_old(self):
        token = self.operator()
        status, body = self.api.call("POST", "/soil-measurements", submission(sampleDate="2026-10-05", depthCm=40), token)
        sid = body["sampleId"]
        drain_worker()
        status, corr = self.api.call("POST", f"/soil-measurements/{sid}/corrections", {"nitrogenMgKg": 33}, token)
        self.assertEqual(status, 202, corr)
        self.assertEqual(corr["version"], 2)
        drain_worker()
        _, latest = self.api.call("GET", f"/soil-measurements/{sid}", token=token)
        self.assertEqual(latest["values"]["nitrogen"], 33.0)
        self.assertEqual([v["version"] for v in latest["versions"]], [1, 2])
        _, old = self.api.call("GET", f"/soil-measurements/{sid}?version=1", token=token)
        self.assertEqual(old["values"]["nitrogen"], 28.0)

    def test_samples_cannot_be_overwritten_in_the_database(self):
        row = db.row("SELECT sample_id FROM soil_samples LIMIT 1")
        with self.assertRaises(Exception):
            db.run("UPDATE soil_samples SET nitrogen_mg_kg = 1 WHERE sample_id = ?", (row["sample_id"],))

    def test_worker_failure_shows_rule_flags_and_pending_ai_view(self):
        token = self.operator()
        _, body = self.api.call("POST", "/soil-measurements", submission(sampleDate="2026-10-06", depthCm=50), token)
        sid = body["sampleId"]
        config.SOIL_AI_FAIL = True
        try:
            drain_worker()
        finally:
            config.SOIL_AI_FAIL = False
        _, sample = self.api.call("GET", f"/soil-measurements/{sid}", token=token)
        self.assertEqual(sample["state"], "ANALYSIS_FAILED")
        self.assertEqual(sample["health"]["aiView"], "PENDING")
        self.assertEqual(len(sample["flags"]), 5)
        status, _ = self.api.call("POST", f"/soil-measurements/{sid}/reanalyse", {}, token)
        self.assertEqual(status, 202)
        drain_worker()
        _, sample = self.api.call("GET", f"/soil-measurements/{sid}", token=token)
        self.assertEqual(sample["state"], "READY")

    # ----- access rules -----

    def test_unassigned_person_gets_not_found_for_health(self):
        token = self.api.login("researcher@soil.local", DEMO_PW)[1]["accessToken"]
        status, _ = self.api.call("GET", "/soil-health?fieldId=fld_0412", token=token)
        self.assertEqual(status, 403)  # researchers have no field role at all

    def test_researcher_history_is_anonymous(self):
        token = self.api.login("researcher@soil.local", DEMO_PW)[1]["accessToken"]
        status, body = self.api.call("GET", "/soil-history", token=token)
        self.assertEqual(status, 200)
        self.assertTrue(body["anonymous"])
        for item in body["items"]:
            self.assertIn("fieldCode", item)
            self.assertNotIn("sampleId", item)
            self.assertNotIn("fieldName", item)
            self.assertNotIn("fieldId", item)

    def test_operator_cannot_read_history_of_other_fields(self):
        token = self.operator()
        status, _ = self.api.call("GET", "/soil-history?fieldId=fld_0931", token=token)
        self.assertEqual(status, 404)

    def test_operator_cannot_see_other_operators_samples(self):
        token = self.operator()
        status, _ = self.api.call("GET", "/soil-measurements?fieldId=fld_0412", token=token)
        self.assertEqual(status, 200)

    def test_researcher_cannot_submit(self):
        token = self.api.login("researcher@soil.local", DEMO_PW)[1]["accessToken"]
        status, _ = self.api.call("POST", "/soil-measurements", submission(sampleDate="2026-10-07"), token)
        self.assertEqual(status, 403)

    def test_nobody_can_raise_their_own_role_and_admin_actions_are_logged(self):
        admin_token = self._admin_token()
        me = self.api.call("GET", "/auth/me", token=admin_token)[1]["user"]
        status, body = self.api.call("POST", f"/admin/accounts/{me['id']}/approve", {"role": "AGRONOMIST"}, admin_token)
        self.assertEqual(status, 403)
        status, log = self.api.call("GET", "/admin/audit-log", token=admin_token)
        self.assertEqual(status, 200)
        self.assertTrue(any(i["action"] for i in log["items"]))

    def test_service_credentials_limit_scope(self):
        status, _ = self.api.call("GET", "/soil-health?fieldId=fld_0412&date=2026-12-31",
                                  headers={"X-Client-Id": "ai-analytics", "X-Client-Secret": "ai-analytics-dev-secret"})
        self.assertEqual(status, 200)
        status, _ = self.api.call("GET", "/soil-data?fieldId=fld_0412",
                                  headers={"X-Client-Id": "plant-health", "X-Client-Secret": "plant-health-dev-secret"})
        self.assertEqual(status, 200)
        status, _ = self.api.call("GET", "/soil-history",
                                  headers={"X-Client-Id": "plant-health", "X-Client-Secret": "plant-health-dev-secret"})
        self.assertEqual(status, 403)
        status, _ = self.api.call("GET", "/soil-health?fieldId=fld_0412",
                                  headers={"X-Client-Id": "ai-analytics", "X-Client-Secret": "wrong"})
        self.assertEqual(status, 401)

    def test_no_measurement_values_in_audit_log(self):
        rows = db.rows("SELECT * FROM audit_log")
        for r in rows:
            self.assertNotIn("nitrogen", json.dumps(r).lower())

    def test_audit_log_is_append_only(self):
        with self.assertRaises(Exception):
            db.run("DELETE FROM audit_log")


if __name__ == "__main__":
    unittest.main()
