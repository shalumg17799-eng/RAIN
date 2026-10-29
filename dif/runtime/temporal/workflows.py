"""Temporal workflow for an agent run (kept minimal: the workflow sandbox re-imports this module).

One workflow per run, one long-running `execute_run` activity per execution segment. The activity runs the
checkpointing engine for the run; if a worker dies the activity is retried elsewhere and resumes from the last
checkpoint. When the engine pauses at an approval gate the activity returns `awaiting_approval` and the workflow waits
for a `decision` signal (sent by the API on approve / reject / cancel, or by a child run that finished), then runs the
engine again. See activities.py for the activity, client and worker factory."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from dif.runtime.temporal.activities import execute_run


@workflow.defn(name="AgentRunWorkflow")
class AgentRunWorkflow:
    def __init__(self):
        self._decisions = 0
        self._seen = 0

    @workflow.signal
    def decision(self, info: dict) -> None:
        self._decisions += 1

    @workflow.run
    async def run(self, rid: str) -> dict:
        while True:
            result = await workflow.execute_activity(
                execute_run, rid,
                start_to_close_timeout=timedelta(hours=12), heartbeat_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=5),
                                         backoff_coefficient=2.0, maximum_interval=timedelta(minutes=5)))
            if result.get("status") != "awaiting_approval":
                return result
            await workflow.wait_condition(lambda: self._decisions > self._seen)
            self._seen = self._decisions
