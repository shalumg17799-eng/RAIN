from prometheus_client import Counter, Gauge, Histogram

RUNS = Counter("dif_agent_runs_total", "Agent runs", ["agent", "status"])
STEP_SECONDS = Histogram("dif_skill_seconds", "Skill execution time", ["skill"])
STEP_ERRORS = Counter("dif_skill_errors_total", "Skill failures", ["skill"])
STEP_RETRIES = Counter("dif_step_retries_total", "Step retries", ["skill"])
ACTIVE = Gauge("dif_active_runs", "Runs currently executing")
QUEUE_DEPTH = Gauge("dif_queue_depth", "Runs waiting for an executor slot")
