"""Temporal activity, client and worker factory for agent runs (the workflow itself is in workflows.py).

Design (MVP-1): one workflow per run, one long-running activity per execution segment. The activity runs the
checkpointing engine (Runtime.execute) for the run; the engine persists every step, so if a worker dies the activity
is retried on another worker and resumes from the last checkpoint. When the engine pauses at an approval gate the
activity returns `awaiting_approval` and the workflow waits for a `decision` signal (sent by the API on approve /
reject / cancel, or by a child run that finished), then runs the engine again. Per-step retry/timeout policies are
applied by the engine; parallel groups run on the engine's thread pool inside the activity. A later refinement can
split steps into separate activities and sub-agents into child workflows without changing agent YAML."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio import activity

log = logging.getLogger("dif.temporal")
_runtime = None
_runtime_lock = threading.Lock()


def set_runtime(rt):
    global _runtime
    _runtime = rt


def get_runtime():
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            from dif.runtime.factory import build_runtime
            _runtime = build_runtime("temporal")
    return _runtime


@activity.defn(name="execute_run")
def execute_run(rid: str) -> dict:
    """Runs the engine for one run until it finishes or pauses. Heartbeats the current step so a dead worker is
    detected and the activity retried elsewhere."""
    rt = get_runtime()
    current = {"step": None}
    rt.progress = lambda run_id, step: current.__setitem__("step", step) if run_id == rid else None
    pool = ThreadPoolExecutor(1, thread_name_prefix="dif-activity")
    fut = pool.submit(rt.execute, rid)
    pool.shutdown(wait=False)
    while True:
        try:
            run = fut.result(timeout=10)
            break
        except TimeoutError:
            activity.heartbeat(current["step"])
    activity.heartbeat(current["step"])
    return {"id": rid, "status": (run or {}).get("status"), "error": (run or {}).get("error")}


async def connect_client():
    from temporalio.client import Client

    from dif.config import settings
    kw = {"namespace": settings.temporal_namespace}
    if settings.temporal_tls:
        kw["tls"] = True
    if settings.temporal_api_key:
        kw["api_key"] = settings.temporal_api_key
    for attempt in range(30):  # the server may still be starting (compose / container apps)
        try:
            return await Client.connect(settings.temporal_address, **kw)
        except Exception as e:  # noqa: BLE001
            log.warning("temporal not reachable at %s (%s); retrying", settings.temporal_address, e)
            time.sleep(min(2 * (attempt + 1), 20))
    raise RuntimeError(f"cannot connect to Temporal at {settings.temporal_address}")


def make_worker(client, task_queue=None, concurrency=None):
    from temporalio.worker import Worker

    from dif.config import settings
    n = concurrency or settings.worker_concurrency
    from dif.runtime.temporal.workflows import AgentRunWorkflow
    return Worker(client, task_queue=task_queue or settings.temporal_task_queue, workflows=[AgentRunWorkflow],
                  activities=[execute_run], activity_executor=ThreadPoolExecutor(n, thread_name_prefix="dif-act"),
                  max_concurrent_activities=n)
