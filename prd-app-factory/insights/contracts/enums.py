"""Closed sets used across the contracts."""

from enum import StrEnum


class Status(StrEnum):
    """Response status. Exactly six (design report 4.4)."""

    ANSWERED = "answered"
    ABSTAINED = "abstained"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"
    DENIED = "denied"
    FAILED = "failed"


class ExecutionFailure(StrEnum):
    """Typed failures from the governed executor. Never retried by the refine loop."""

    POLICY_DENIED = "policy_denied"
    ACCESS_DENIED = "access_denied"
    TIMEOUT = "timeout"
    ERROR = "error"


class ExecutionStatus(StrEnum):
    OK = "ok"
    POLICY_DENIED = "policy_denied"
    ACCESS_DENIED = "access_denied"
    TIMEOUT = "timeout"
    ERROR = "error"


class RunFailureReason(StrEnum):
    """Why the engine ended a run as failed (as opposed to a product status from a skill)."""

    DEADLINE = "deadline"
    TOKEN_BUDGET = "token_budget"  # noqa: S105 - not a credential
    SKILL_ERROR = "skill_error"
    REF_ERROR = "ref_error"
    UNMAPPED_LABEL = "unmapped_label"
    ROWS_IN_STATE = "rows_in_state"
    RECURSION_LIMIT = "recursion_limit"
    INVALID_INPUT = "invalid_input"
    INTERNAL = "internal"


class Intent(StrEnum):
    """Day-one intents plus `metadata_question` (answered from the KAG/catalog, no SQL)."""

    DATA_QUERY = "data_query"
    METADATA_QUESTION = "metadata_question"
    OUT_OF_SCOPE = "out_of_scope"
    NEEDS_CLARIFICATION = "needs_clarification"


class PathName(StrEnum):
    KAG = "kag"
    BYPASS = "bypass"


class RouterLayer(StrEnum):
    RULES = "rules"
    EMBEDDING = "embedding"
    LLM = "llm"
    FALLBACK = "fallback"


class AssessorLabel(StrEnum):
    ANSWER = "answer"
    REFINE_SLIVER = "refine_sliver"
    REFINE_QUERY = "refine_query"
    ESCALATE = "escalate"


class ColumnRole(StrEnum):
    DIMENSION = "dimension"
    MEASURE = "measure"
    TIME = "time"


class Purpose(StrEnum):
    """Gateway purposes. Skills name a purpose, never a model or provider."""

    ROUTE = "route"
    RESOLVE = "resolve"
    CONCEPTS = "concepts"
    CYPHER = "cypher"
    SQL = "sql"
    JUDGE = "judge"
    NARRATE = "narrate"


class IdentityMode(StrEnum):
    """Layer 3 identity modes (design report 5.4)."""

    PER_USER = "per_user"
    SERVICE_PRINCIPAL_WITH_VIEWS = "service_principal_with_views"
    SERVICE_PRINCIPAL_WITH_PREDICATES = "service_principal_with_predicates"


class Dialect(StrEnum):
    POSTGRES = "postgres"
    DATABRICKS = "databricks"


class MaskKind(StrEnum):
    REDACT = "redact"
    HASH = "hash"
    LAST4 = "last4"
    NULL = "null"


class EventType(StrEnum):
    """SSE stage events. Never carry rows."""

    STAGE_STARTED = "stage_started"
    STAGE_FINISHED = "stage_finished"
    REFINE = "refine"
    PROGRESS = "progress"
    RUN_FINISHED = "run_finished"


class AuditEventType(StrEnum):
    RUN_STARTED = "run_started"
    STEP_FINISHED = "step_finished"
    POLICY_DECISION = "policy_decision"
    EXECUTION = "execution"
    RUN_FINISHED = "run_finished"


class PolicyLayer(StrEnum):
    L1 = "l1"
    L2 = "l2"
    L3 = "l3"


class PolicyDecisionKind(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
