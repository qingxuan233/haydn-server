"""Read-only client for the on-device Android Bridge (loopback HTTPS + token + pinned cert)."""
import json
import ssl
import threading
import time
import urllib.request

CERT = "/root/server/etc/bridge.crt"
TOKEN_FILE = "/root/server/etc/bridge.token"
BASE = "https://127.0.0.1:3099"
CACHE_TTL = 10.0

_lock = threading.Lock()
_cache = {"at": 0.0, "data": None, "error": None, "last_seen": None}


def _token():
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _ctx():
    try:
        return ssl.create_default_context(cafile=CERT)
    except Exception:
        return None


def _get(path, timeout=2.0):
    token = _token()
    if not token:
        raise RuntimeError("bridge token missing")
    ctx = _ctx()
    if ctx is None:
        raise RuntimeError("bridge cert missing")
    req = urllib.request.Request(
        BASE + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def health(timeout=2.0):
    """True if /v1/health succeeds (no token required)."""
    try:
        ctx = _ctx()
        if ctx is None:
            return False
        with urllib.request.urlopen(BASE + "/v1/health", timeout=timeout, context=ctx) as resp:
            return resp.status == 200
    except Exception:
        return False


def status(force=False):
    """Return a small dict with bridge status or None; failures are cached briefly."""
    now = time.time()
    with _lock:
        if not force and _cache["data"] is not None and now - _cache["at"] < CACHE_TTL:
            cached = dict(_cache["data"])
            cached["age_s"] = round(now - _cache["at"], 1)
            return cached
        try:
            payload = _get("/v1/status")
            data = {
                "ok": True,
                "source": "bridge",
                "data": payload,
                "age_s": 0.0,
                "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "error": None,
            }
            _cache.update({"at": now, "data": data, "error": None, "last_seen": data["last_seen"]})
            return dict(data)
        except Exception as exc:
            _cache.update({"at": now, "data": None, "error": str(exc)})
            return None


def snapshot():
    """For API use: returns dict with ok/source/data/age_s/version/last_seen."""
    data = status(force=False)
    if data is None:
        return {
            "ok": False,
            "source": "termux",
            "data": None,
            "last_seen": _cache.get("last_seen"),
            "error": _cache.get("error"),
            "age_s": None,
        }
    payload = data.get("data") or {}
    return {
        "ok": True,
        "source": "bridge",
        "data": payload,
        "last_seen": data.get("last_seen"),
        "error": None,
        "age_s": 0.0,
        "version": payload.get("version"),
    }
