"""Run executors. The engine (Runtime.execute) is the same everywhere; the executor decides where it runs.

LocalExecutor    - in-process thread pool: dev, tests, single-node. Runs are lost on restart (recover_orphans re-enqueues).
TemporalExecutor - durable: each run is a Temporal workflow (dif/runtime/temporal) executed by `python -m dif.worker`
                   workers; survives worker restarts, waits for approval signals, visible in the Temporal UI."""
import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from dif.config import settings

log = logging.getLogger("dif.executor")


class LocalExecutor:
    kind = "local"

    def __init__(self, workers=4):
        self.pool = ThreadPoolExecutor(workers, thread_name_prefix="dif-run")
        self.runtime = None

    def bind(self, runtime):
        self.runtime = runtime

    def _run(self, rid):
        try:
            self.runtime.execute(rid)
        except Exception:  # the engine records failures itself; this only guards the pool thread
            log.exception("run %s crashed", rid)

    def submit(self, rid):
        self.pool.submit(self._run, rid)

    resume = submit

    def notify(self, rid):  # cancel of a waiting run: nothing is blocked in local mode
        pass

    def depth(self):
        return self.pool._work_queue.qsize()

    def healthy(self):
        return True

    def describe(self, rid):
        return {"executor": "local"}


class TemporalExecutor:
    """Sync facade over the async Temporal client: one background event loop thread, one connection."""
    kind = "temporal"
    WORKFLOW_ID = "dif-run-{rid}"

    def __init__(self, address=None, namespace=None, task_queue=None, tls=None, api_key=None):
        self.address = address or settings.temporal_address
        self.namespace = namespace or settings.temporal_namespace
        self.task_queue = task_queue or settings.temporal_task_queue
        self.tls = settings.temporal_tls if tls is None else tls
        self.api_key = api_key if api_key is not None else settings.temporal_api_key
        self.runtime, self._client = None, None
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True, name="dif-temporal").start()

    def bind(self, runtime):
        self.runtime = runtime

    def _call(self, coro, timeout=60):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _get_client(self):
        if self._client is None:
            from temporalio.client import Client
            kw = {"namespace": self.namespace}
            if self.tls:
                kw["tls"] = True
            if self.api_key:
                kw["api_key"] = self.api_key
            self._client = await Client.connect(self.address, **kw)
        return self._client

    def wid(self, rid):
        return self.WORKFLOW_ID.format(rid=rid)

    async def _start(self, rid):
        from dif.runtime.temporal.workflows import AgentRunWorkflow
        client = await self._get_client()
        return await client.start_workflow(AgentRunWorkflow.run, rid, id=self.wid(rid), task_queue=self.task_queue)

    async def _running(self, rid):
        from temporalio.client import WorkflowExecutionStatus
        from temporalio.service import RPCError
        client = await self._get_client()
        try:
            desc = await client.get_workflow_handle(self.wid(rid)).describe()
        except RPCError:
            return False
        return desc.status == WorkflowExecutionStatus.RUNNING

    async def _signal(self, rid, info):
        client = await self._get_client()
        await client.get_workflow_handle(self.wid(rid)).signal("decision", info)

    async def _resume(self, rid):
        if await self._running(rid):  # workflow is waiting on a decision (approval or child result): wake it
            await self._signal(rid, {"kind": "resume"})
        else:  # failed/cancelled run resumed by a user: start a fresh workflow for the same run id
            await self._start(rid)

    def submit(self, rid):
        self._call(self._start(rid))

    def resume(self, rid):
        self._call(self._resume(rid))

    def notify(self, rid):
        """Cancellation of a waiting run: wake the workflow so it observes the cancelled status and ends."""
        try:
            if self._call(self._running(rid)):
                self._call(self._signal(rid, {"kind": "cancel"}))
        except Exception:
            log.warning("could not notify workflow for run %s", rid, exc_info=True)

    def wait(self, rid, timeout=3600):
        """Block until the workflow finishes or pauses (used for wait=true in temporal mode)."""
        async def _wait():
            client = await self._get_client()
            return await client.get_workflow_handle(self.wid(rid)).result()
        return self._call(_wait(), timeout)

    def depth(self):
        return 0

    def healthy(self):
        try:
            self._call(self._get_client(), timeout=10)
            return True
        except Exception as e:
            log.warning("temporal unreachable: %s", e)
            return False

    def describe(self, rid):
        try:
            async def _d():
                client = await self._get_client()
                d = await client.get_workflow_handle(self.wid(rid)).describe()
                return {"executor": "temporal", "workflow_id": self.wid(rid), "status": d.status.name if d.status else None}
            return self._call(_d(), timeout=10)
        except Exception as e:
            return {"executor": "temporal", "workflow_id": self.wid(rid), "error": str(e)}


def make_executor(kind=None):
    kind = kind or settings.orchestrator
    if kind == "temporal":
        return TemporalExecutor()
    if kind == "local":
        return LocalExecutor(settings.local_workers)
    raise ValueError(f"DIF_ORCHESTRATOR must be local or temporal, not {kind!r}")
