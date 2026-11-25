"""Background worker (Module 2 and 5 analysis, Module 4 health).

Steps for each queued job:
1. claim it with a lock (two workers never take the same job);
2. run the rule flags (no AI needed);
3. ask the Soil & Nutrient AI, retrying up to 3 times with a wait between tries;
4. save flags, severity and health together, then set the sample to READY,
   or to ANALYSIS_FAILED with the rule flags still shown and the AI view marked PENDING.
"""
import logging
import os
import threading
import time
from datetime import timedelta

from . import ai_client, audit, config, db, rules, samples
from .util import iso, utcnow

log = logging.getLogger("worker")
NUTRIENT_LEVEL = {"DEFICIENT": "LOW", "EXCESS": "HIGH", "OK": "OK"}
LOCK_MINUTES = 5


def claim_next(worker_id):
    now = iso()
    with db.tx():
        job = db.row(
            "SELECT * FROM analysis_jobs WHERE (job_status = 'QUEUED' AND (next_run_at IS NULL OR next_run_at <= ?)) "
            "OR (job_status = 'RUNNING' AND locked_until < ?) ORDER BY id LIMIT 1",
            (now, now),
        )
        if not job:
            return None
        cur = db.run(
            "UPDATE analysis_jobs SET job_status = 'RUNNING', locked_by = ?, locked_until = ? "
            "WHERE id = ? AND (job_status = 'QUEUED' OR locked_until < ?)",
            (worker_id, iso(utcnow() + timedelta(minutes=LOCK_MINUTES)), job["id"], now),
        )
        if cur.rowcount != 1:
            return None
        db.run("UPDATE soil_samples SET state = 'ANALYSING' WHERE sample_id = ? AND version = ?",
               (job["sample_id"], job["version"]))
        return job


def _reschedule(job, attempt, delay, error):
    with db.tx():
        db.run(
            "UPDATE analysis_jobs SET job_status = 'QUEUED', attempts = ?, locked_by = NULL, locked_until = NULL, "
            "next_run_at = ?, last_error = ? WHERE id = ?",
            (attempt, iso(utcnow() + timedelta(seconds=delay)), error[:200], job["id"]),
        )


def process(job):
    sample = db.row("SELECT * FROM soil_samples WHERE sample_id = ? AND version = ?",
                    (job["sample_id"], job["version"]))
    values = {m: sample[samples.COLUMN[m]] for m in rules.MEASUREMENTS}
    rule = rules.rule_flags(values)
    attempt = job["attempts"] + 1
    try:
        ai = ai_client.get_client().analyze(job["sample_id"], job["version"], values)
    except ai_client.SoilAIError as exc:
        if attempt < config.AI_MAX_ATTEMPTS:
            _reschedule(job, attempt, config.AI_RETRY_DELAYS[attempt - 1], str(exc))
        else:
            _finish(job, rule, None, attempt, str(exc))
        return
    _finish(job, rule, ai, attempt, None)


def _finish(job, rule, ai, attempt, failure):
    ai_map = {f["nutrient"]: f for f in ai["flags"]} if ai else {}
    model = ai["modelVersion"] if ai else None
    ok = failure is None
    sid, ver = job["sample_id"], job["version"]
    with db.tx():
        for m in rules.MEASUREMENTS:
            r = rule[m]
            ai_level = score = None
            if m in ai_map:
                ai_level = NUTRIENT_LEVEL.get(ai_map[m].get("state"))
                score = ai_map[m].get("score")
            # The rule flag is kept when the AI disagrees; the disagreement is recorded.
            disagreement = 1 if ai_level and ai_level != r["level"] else 0
            db.run(
                "INSERT OR REPLACE INTO soil_flags (sample_id, version, measurement, level, severity, source, "
                "ai_level, ai_score, model_version, disagreement) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, ver, m, r["level"], r["severity"], "RULE+AI" if ai_level else "RULE",
                 ai_level, score, model, disagreement),
            )
        health = rules.health_status([{"level": v["level"], "severity": v["severity"]} for v in rule.values()])
        db.run(
            "INSERT INTO health_results (sample_id, version, health_status, rule_version, model_version, ai_view, "
            "analysed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, ver, health, rules.HEALTH_VERSION, model, "READY" if ok else "PENDING", iso()),
        )
        db.run("UPDATE soil_samples SET state = ? WHERE sample_id = ? AND version = ?",
               ("READY" if ok else "ANALYSIS_FAILED", sid, ver))
        db.run("UPDATE analysis_jobs SET job_status = ?, attempts = ?, locked_by = NULL, locked_until = NULL, "
               "last_error = ? WHERE id = ?", ("DONE" if ok else "FAILED", attempt, failure, job["id"]))
        audit.write("worker", "SERVICE", "analyse-sample", sid, "OK" if ok else "FAILED")
    if not ok:
        log.error("analysis failed for %s v%s after %s tries: %s", sid, ver, attempt, failure)


def run_worker(stop=None, poll_seconds=1.0):
    worker_id = f"worker-{os.getpid()}-{threading.get_ident()}"
    log.info("worker %s started", worker_id)
    while not (stop and stop.is_set()):
        try:
            job = claim_next(worker_id)
        except Exception:
            log.exception("could not claim a job")
            time.sleep(poll_seconds)
            continue
        if job is None:
            time.sleep(poll_seconds)
            continue
        try:
            process(job)
        except Exception:
            log.exception("job %s failed unexpectedly; it will be retried", job["id"])
            _reschedule(job, job["attempts"] + 1, 5, "unexpected error")
