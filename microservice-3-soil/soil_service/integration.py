"""Connecting to the other Leafline microservices.

Two directions are supported and both use REST/JSON over HTTP:

* INBOUND: another service calls this one with its client ID and secret, in the headers
  X-Client-Id and X-Client-Secret. The client must be listed in config.SERVICE_CLIENTS and
  may use only the scopes listed for it. Example: AI Analytics reads GET /soil-health.

* OUTBOUND: this service calls another service. Configure it in PEER_SERVICES (see config.py),
  then use call_peer(). Nothing else needs to change in this service.

Services never read each other's databases. Asynchronous events are not used in this version.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from . import config
from .errors import ApiError


def _headers(peer):
    return {"Accept": "application/json", "X-Client-Id": peer.get("client_id", config.SERVICE_NAME),
            "X-Client-Secret": peer.get("secret", "")}


def call_peer(name, path, params=None, timeout=5):
    peer = config.PEER_SERVICES.get(name)
    if not peer:
        raise ApiError(404, "UNKNOWN_PEER", f"No peer service named {name} is configured.")
    url = peer["url"].rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers(peer))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise ApiError(502, "PEER_ERROR", f"{name} replied with status {exc.code}.")
    except (urllib.error.URLError, OSError, ValueError):
        raise ApiError(503, "PEER_UNAVAILABLE", f"{name} is not reachable right now.")


def peer_status():
    result = {}
    for name, peer in config.PEER_SERVICES.items():
        try:
            req = urllib.request.Request(peer["url"].rstrip("/") + "/health", headers=_headers(peer))
            with urllib.request.urlopen(req, timeout=2) as resp:
                result[name] = {"url": peer["url"], "reachable": resp.status == 200}
        except Exception as exc:  # any failure simply means "not reachable"
            result[name] = {"url": peer["url"], "reachable": False, "error": str(exc)[:120]}
    return {"peers": result, "configured": len(config.PEER_SERVICES)}
