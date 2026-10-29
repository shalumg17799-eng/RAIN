"""Temporal worker: `python -m dif.worker` (DIF_ORCHESTRATOR=temporal). Run N replicas to scale. Polls the task queue
for agent-run workflows, executes the engine inside activities, and shuts down gracefully on SIGTERM (in-flight
activities finish; Temporal re-dispatches anything else). Exposes Prometheus metrics on DIF_WORKER_METRICS_PORT."""
import asyncio
import logging
import os
import signal

from prometheus_client import start_http_server

from dif import telemetry
from dif.config import settings

log = logging.getLogger("dif.worker")


async def main():
    from dif.runtime.temporal.activities import connect_client, get_runtime, make_worker
    rt = get_runtime()
    client = await connect_client()
    worker = make_worker(client)
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker started: queue %s at %s, %d skills, %d agents, concurrency %d", settings.temporal_task_queue,
             settings.temporal_address, len(rt.skills.list()), len(rt.agents.list()), settings.worker_concurrency)
    run_task = asyncio.create_task(worker.run())
    await stop.wait()
    log.info("signal received; draining in-flight activities")
    await worker.shutdown()
    await run_task
    log.info("worker stopped")


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    telemetry.setup("dif-worker")
    if settings.orchestrator != "temporal":
        raise SystemExit("the worker needs DIF_ORCHESTRATOR=temporal (local mode executes runs inside the api process)")
    start_http_server(int(os.getenv("DIF_WORKER_METRICS_PORT", "9100")))
    asyncio.run(main())
