"""API-key auth. DIF_API_KEYS="key:name:role[:enterprise],..." (role = user|approver|admin). Unset => open mode (local
dev only). Keys are accepted as `X-API-Key: <key>` or `Authorization: Bearer <key>`.

A key with an enterprise only sees that enterprise's runs and artifacts and creates runs for it; a key without one is
platform-wide (sees everything, creates runs with enterprise_id = null unless the request names one)."""
import logging
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from dif.config import settings

log = logging.getLogger("dif.auth")
_header = APIKeyHeader(name="X-API-Key", auto_error=False)
ROLES = ("user", "approver", "admin")


def _keys():
    out = {}
    for item in filter(None, (x.strip() for x in settings.api_keys.split(","))):
        parts = item.split(":")
        k, name = parts[0], parts[1] if len(parts) > 1 else "user"
        role = parts[2] if len(parts) > 2 and parts[2] else "user"
        ent = parts[3] if len(parts) > 3 and parts[3] else None
        if role not in ROLES:
            log.warning("API key for %s has unknown role %r; treating as user", name, role)
            role = "user"
        out[k] = {"name": name, "role": role, "enterprise": ent}
    return out


def warn_if_open():
    if not _keys():
        log.warning("DIF_API_KEYS is not set: authentication is DISABLED. Do not expose this instance.")


def current_user(request: Request, key: str | None = Depends(_header)):
    keys = _keys()
    if not keys:
        return {"name": "anonymous", "role": "admin", "enterprise": None}
    auth = request.headers.get("authorization", "")
    key = key or (auth[7:] if auth.lower().startswith("bearer ") else None)
    for k, u in keys.items():
        if key and secrets.compare_digest(k, key):
            return u
    raise HTTPException(401, "missing or invalid API key", headers={"WWW-Authenticate": "ApiKey"})


def admin_user(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "admin role required")
    return user


def approver_user(user=Depends(current_user)):
    if user["role"] not in ("approver", "admin"):
        raise HTTPException(403, "approver or admin role required")
    return user
