"""Exact-match response cache. Never shared across principals; never holds a prompt with rows.

The key covers everything that can change an answer: the app and its version, who is asking
(subject, tenant and entitlement digest, so even identical entitlements do not share), the
purpose, model, sampling settings, the full prompt and the response schema. A call whose
prompt carries result rows is no-store: the gateway neither reads nor writes the cache for it.
"""

import hashlib
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Sequence
from typing import Any

from insights.contracts.enums import Purpose
from insights.contracts.gateway import CompletionResult, Message
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile


def cache_key(
    *,
    app: AppProfile,
    principal: Principal,
    purpose: Purpose,
    model: str,
    temperature: float,
    max_tokens: int,
    messages: Sequence[Message],
    response_schema: dict[str, Any] | None,
) -> str:
    material = {
        "app": [app.id, app.version],
        "principal": [principal.subject, principal.tenant, principal.entitlement_digest],
        "purpose": purpose.value,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [[m.role, m.content] for m in messages],
        "schema": response_schema,
    }
    canonical = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class InMemoryExactCache:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        ttl_seconds: float = 600.0,
        max_entries: int = 1000,
    ) -> None:
        self._clock = clock
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: OrderedDict[str, tuple[float, CompletionResult]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> CompletionResult | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry[0] <= self._clock():
                del self._entries[key]
                return None
            return entry[1]

    def put(self, key: str, result: CompletionResult) -> None:
        with self._lock:
            self._entries[key] = (self._clock() + self._ttl, result)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
