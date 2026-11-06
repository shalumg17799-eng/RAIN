"""Everything one run needs, handed to the compiled graph at invoke time.

The compiled graph is shared by every request and every principal, so nothing per-request may be
captured in it. It arrives through `config["configurable"]["scope"]` instead.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from insights.contracts.enums import AuditEventType
from insights.contracts.events import AuditEvent
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile
from insights.runtime.events import EventEmitter
from insights.runtime.limits import EffectiveLimits
from insights.skills_core.protocols import (
    AuditSink,
    Deadline,
    Gateway,
    ResultStore,
    Services,
    UsageMeter,
)
from insights.skills_core.registry import SkillRegistry


@dataclass(frozen=True)
class RunScope:
    run_id: str
    trace_id: str
    thread_id: str
    registry: SkillRegistry
    gateway: Gateway
    audit: AuditSink
    results: ResultStore
    meter: UsageMeter
    deadline: Deadline
    emitter: EventEmitter
    principal: Principal
    app: AppProfile
    limits: EffectiveLimits
    clock: Callable[[], float]
    now: Callable[[], datetime]
    services: Services

    def audit_event(self, type: AuditEventType, **fields: object) -> AuditEvent:
        """An audit event carrying the common identity fields. Hashes and counts only."""
        return AuditEvent(
            event_id=uuid.uuid4().hex,
            type=type,
            ts=self.now(),
            run_id=self.run_id,
            trace_id=self.trace_id,
            principal_subject=self.principal.subject,
            principal_tenant=self.principal.tenant,
            app_id=self.app.id,
            app_version=self.app.version,
            **fields,  # type: ignore[arg-type]
        )
