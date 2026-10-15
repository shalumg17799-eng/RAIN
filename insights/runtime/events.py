"""Per-run event emitter. Sinks are best effort: a failing sink is logged and never fails a run."""

import logging
from collections.abc import Callable, Sequence

from insights.contracts.events import StageEvent
from insights.obs.logging import log_event

_log = logging.getLogger("insights.runtime.events")

EventSink = Callable[[StageEvent], None]


class EventEmitter:
    def __init__(self, sinks: Sequence[EventSink], run_id: str) -> None:
        self._sinks = tuple(sinks)
        self._run_id = run_id

    def emit(self, event: StageEvent) -> None:
        if not isinstance(event, StageEvent):
            raise TypeError("only StageEvent can be emitted")
        for sink in self._sinks:
            try:
                sink(event)
            except Exception as exc:
                log_event(
                    _log,
                    logging.WARNING,
                    "event_sink_failed",
                    run_id=self._run_id,
                    error_type=type(exc).__name__,
                )
