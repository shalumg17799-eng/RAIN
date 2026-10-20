"""Work queues: one per agent. A message is {"app_id", "stage"}.

Two backends behind one interface:
- local  : a folder per agent under apppacks/_queue/ (one JSON file per message), and for the
           portal's local mode a background thread that drains it;
- azure  : Azure Storage queues `factory-<agent>` (FACTORY_QUEUE_CONNECTION), one per agent, which
           the Container Apps Job of that agent scales on (event-driven, one message per execution).
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

from factory.config import APPPACKS_DIR

AGENT_NAMES = ("requirements", "data", "knowledge", "app", "release")


def queue_name(agent: str) -> str:
    return f"factory-{agent}"


class LocalQueue:
    def __init__(self, root: Path | None = None):
        self.root = root or APPPACKS_DIR / "_queue"

    def send(self, agent: str, message: dict) -> None:
        d = self.root / agent
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f".{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(message), encoding="utf-8")
        tmp.rename(d / f"{time.time_ns()}-{uuid.uuid4().hex[:8]}.json")

    def receive(self, agent: str) -> tuple[dict, object] | None:
        d = self.root / agent
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            claimed = f.with_suffix(".claimed")
            try:
                f.rename(claimed)               # atomic claim: two workers never get the same message
            except OSError:
                continue
            return json.loads(claimed.read_text(encoding="utf-8")), claimed
        return None

    def complete(self, agent: str, receipt) -> None:
        Path(receipt).unlink(missing_ok=True)


class AzureQueue:
    def __init__(self, connection: str):
        from azure.storage.queue import QueueServiceClient
        self.service = QueueServiceClient.from_connection_string(connection)

    def _client(self, agent: str):
        client = self.service.get_queue_client(queue_name(agent))
        try:
            client.create_queue()
        except Exception:  # already exists
            pass
        return client

    def send(self, agent: str, message: dict) -> None:
        self._client(agent).send_message(json.dumps(message))

    def receive(self, agent: str):
        # Visibility timeout longer than an agent run, so a crashed job's message reappears for a retry.
        for msg in self._client(agent).receive_messages(messages_per_page=1, visibility_timeout=3 * 3600):
            return json.loads(msg.content), msg
        return None

    def complete(self, agent: str, receipt) -> None:
        self._client(agent).delete_message(receipt)


def get_queue():
    conn = os.environ.get("FACTORY_QUEUE_CONNECTION", "").strip()
    return AzureQueue(conn) if conn else LocalQueue()


def enqueue(app_id: str, stage: str) -> None:
    from factory.coordinator import STAGE_AGENT
    get_queue().send(STAGE_AGENT[stage], {"app_id": app_id, "stage": stage, "sent_at": time.time()})


def work_once(agent: str) -> dict | None:
    """Take one message for this agent, run its stage, then dispatch whatever comes next."""
    from factory import coordinator
    q = get_queue()
    got = q.receive(agent)
    if got is None:
        return None
    message, receipt = got
    try:
        handoff = coordinator.run_stage(message["app_id"], message["stage"])
        coordinator.advance(message["app_id"], dispatch=enqueue)
    finally:
        q.complete(agent, receipt)   # a crash inside run_stage is recorded as "blocked", not retried forever
    return {"message": message, "status": handoff.get("status", handoff.get("skipped"))}


class LocalWorkers:
    """Portal local mode: one daemon thread per agent draining the local queue."""

    def __init__(self, poll_seconds: float = 2.0):
        self.poll = poll_seconds
        self.stop = threading.Event()
        self.threads = [threading.Thread(target=self._loop, args=(a,), daemon=True, name=f"agent-{a}")
                        for a in AGENT_NAMES]

    def start(self) -> "LocalWorkers":
        for t in self.threads:
            t.start()
        return self

    def _loop(self, agent: str) -> None:
        while not self.stop.is_set():
            try:
                if work_once(agent) is None:
                    self.stop.wait(self.poll)
            except Exception as exc:  # keep the worker alive; the run itself records the failure
                print(f"[worker {agent}] {type(exc).__name__}: {exc}")
                self.stop.wait(self.poll)
