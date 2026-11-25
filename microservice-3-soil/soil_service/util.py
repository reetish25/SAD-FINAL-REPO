import datetime as dt
import secrets


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def iso(moment=None):
    return (moment or utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text):
    return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix):
    return f"{prefix}_{secrets.token_hex(4)}"


def paging(query):
    try:
        page = max(1, int(query.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        size = min(100, max(1, int(query.get("size", 20))))
    except (TypeError, ValueError):
        size = 20
    return page, size
