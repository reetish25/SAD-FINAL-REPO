"""Activity log. One line per action. Measurement values are never written here."""
from . import db
from .util import iso


def write(actor_id, actor_role, action, target_id=None, outcome="OK"):
    db.run(
        "INSERT INTO audit_log (actor_user_id, actor_role, action, target_id, outcome, occurred_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (actor_id, actor_role, action, target_id, outcome, iso()),
    )
