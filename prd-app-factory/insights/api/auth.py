"""API keys and the server-side Principal. Fail closed: no keys, no server.

Keys live in a file outside version control (`INSIGHTS_API_KEYS_FILE`). The file holds the SHA-256
of each bearer token, never the token, plus the identity the token stands for. A token is matched
by constant-time comparison against every entry. The Principal is built here, on the server; the
request body never carries identity (the contract rejects it).
"""

import hashlib
import hmac
import json
from pathlib import Path
from typing import Annotated

from pydantic import Field, StringConstraints, ValidationError

from insights.contracts.common import Contract, Identifier, Sha256Hex
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile
from insights.yamlio import load_yaml

KeyId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,62}$")]


class StartupError(RuntimeError):
    """The server must not start. The message says why."""


class KeyRecord(Contract):
    id: KeyId
    key_sha256: Sha256Hex
    subject: str = Field(min_length=1, max_length=256)
    tenant: str = Field(min_length=1, max_length=128)
    roles: tuple[Identifier, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)
    apps: tuple[Identifier, ...] = ()
    """Apps this key may call. Empty means any app the server serves."""


class KeysFile(Contract):
    version: int = 1
    keys: tuple[KeyRecord, ...] = ()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ApiKeys:
    def __init__(self, records: tuple[KeyRecord, ...]) -> None:
        if not records:
            raise StartupError(
                "no API keys are configured; the server refuses to start without them "
                "(create one with: python scripts/make_api_key.py)"
            )
        hashes = [r.key_sha256 for r in records]
        if len(set(hashes)) != len(hashes):
            raise StartupError("the API keys file lists the same key twice")
        self._records = records

    @classmethod
    def load(cls, path: Path | None) -> "ApiKeys":
        if path is None:
            raise StartupError("INSIGHTS_API_KEYS_FILE is not set; the server refuses to start")
        try:
            raw = load_yaml(path.read_text(encoding="utf-8")) or {}
            parsed = KeysFile.model_validate(raw)
        except OSError as exc:
            raise StartupError(f"cannot read the API keys file {path}: {exc}") from exc
        except (ValidationError, ValueError, TypeError) as exc:
            raise StartupError(f"invalid API keys file {path}: {exc}") from exc
        return cls(parsed.keys)

    def __len__(self) -> int:
        return len(self._records)

    def authenticate(self, token: str | None) -> KeyRecord | None:
        """The record for a bearer token, or None. Every entry is compared, every time."""
        if not token:
            return None
        digest = hash_token(token)
        found: KeyRecord | None = None
        for record in self._records:
            if hmac.compare_digest(record.key_sha256, digest):
                found = record
        return found


def entitlement_digest(record: KeyRecord, app: AppProfile) -> str:
    """Digest of the entitlements in force for this caller in this app version."""
    material = {
        "app": [app.id, app.version],
        "roles": {r: app.roles[r].model_dump(mode="json") for r in record.roles if r in app.roles},
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def principal_for(record: KeyRecord, app: AppProfile) -> Principal:
    return Principal(
        subject=record.subject,
        tenant=record.tenant,
        roles=record.roles,
        attributes=dict(record.attributes),
        entitlement_digest=entitlement_digest(record, app),
        token_ref=f"key:{record.id}",
    )


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()
