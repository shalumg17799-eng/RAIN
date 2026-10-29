"""Per-step execution policy: retries with backoff, non-retryable errors, timeout.

YAML (step level, or agent-level `defaults:` applied to every step):
    retry: {attempts: 3, backoff: {initial: 2, factor: 2, max: 60}, non_retryable: [SkillError]}
    timeout: 600
The same policy maps to Temporal activity options (`to_temporal`) so the YAML is executor-independent."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field

log = logging.getLogger("dif.policy")


class StepTimeout(Exception):
    pass


@dataclass
class StepPolicy:
    attempts: int = 1
    initial: float = 1.0
    factor: float = 2.0
    max_interval: float = 60.0
    non_retryable: tuple = field(default_factory=tuple)
    timeout: float | None = None

    def sleep_for(self, attempt: int) -> float:
        return min(self.initial * (self.factor ** (attempt - 1)), self.max_interval)

    def is_retryable(self, exc: Exception) -> bool:
        if getattr(exc, "retryable", True) is False:
            return False
        return not any(c.__name__ in self.non_retryable for c in type(exc).__mro__)

    def to_temporal(self):
        """Temporal activity options with the same meaning (used when DIF_ORCHESTRATOR=temporal runs steps as activities)."""
        from datetime import timedelta

        from temporalio.common import RetryPolicy
        return {"retry_policy": RetryPolicy(maximum_attempts=self.attempts, initial_interval=timedelta(seconds=self.initial),
                                            backoff_coefficient=self.factor, maximum_interval=timedelta(seconds=self.max_interval),
                                            non_retryable_error_types=list(self.non_retryable)),
                "start_to_close_timeout": timedelta(seconds=self.timeout) if self.timeout else None}


def validate_policy(step: dict, where: str):
    r = step.get("retry")
    if r is not None:
        if not isinstance(r, dict) or int(r.get("attempts", 1)) < 1:
            raise ValueError(f"{where}: retry.attempts must be >= 1")
        b = r.get("backoff", {})
        if not isinstance(b, dict) or any(float(b.get(k, 1)) <= 0 for k in ("initial", "factor", "max")):
            raise ValueError(f"{where}: retry.backoff values must be > 0")
        if not isinstance(r.get("non_retryable", []), list):
            raise ValueError(f"{where}: retry.non_retryable must be a list of exception class names")
    t = step.get("timeout")
    if t is not None and float(t) <= 0:
        raise ValueError(f"{where}: timeout must be > 0 seconds")


def policy_from_step(step: dict, defaults: dict | None = None) -> StepPolicy:
    d = defaults or {}
    r = {**d.get("retry", {}), **(step.get("retry") or {})}
    b = {**d.get("retry", {}).get("backoff", {}), **(step.get("retry") or {}).get("backoff", {})}
    timeout = step.get("timeout", d.get("timeout"))
    return StepPolicy(attempts=int(r.get("attempts", 1)), initial=float(b.get("initial", 1)), factor=float(b.get("factor", 2)),
                      max_interval=float(b.get("max", 60)), non_retryable=tuple(r.get("non_retryable", [])),
                      timeout=float(timeout) if timeout else None)


def _sleep(seconds):  # module-level so tests can stub the backoff without touching time.sleep globally
    time.sleep(seconds)


def run_with_policy(policy: StepPolicy, fn, on_retry=None, should_stop=None, sleep=None):
    """Run fn() under the policy. A timed-out attempt cannot be killed in-process (skills must be idempotent); its
    thread is abandoned and the step is retried or failed."""
    last = None
    for attempt in range(1, policy.attempts + 1):
        try:
            if policy.timeout:
                pool = ThreadPoolExecutor(1, thread_name_prefix="dif-step")
                fut = pool.submit(fn)
                pool.shutdown(wait=False)
                try:
                    return fut.result(timeout=policy.timeout)
                except FutureTimeout:
                    raise StepTimeout(f"step timed out after {policy.timeout:g}s (attempt {attempt})")
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt >= policy.attempts or not policy.is_retryable(e) or (should_stop and should_stop()):
                raise
            wait = policy.sleep_for(attempt)
            if on_retry:
                on_retry(attempt, e, wait)
            log.warning("attempt %d failed (%s); retrying in %.1fs", attempt, e, wait)
            (sleep or _sleep)(wait)
    raise last  # pragma: no cover


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def run_lock(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())
