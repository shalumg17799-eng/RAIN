# RAIN Intelligence Layer Integration Specification
**Tailored for the RAIN Application Repository (`rain-api`)**

---

## 1. Executive Summary & Application Context

### 1.1 Architecture & Current State of RAIN
The target application, **RAIN**, is a decision-intelligence platform running locally with the following components:
- **Repository Layout**:
  - `insights/`: The core intelligence engine (contracts, policy, catalog, runtime, datasources, gateway).
  - `agents/`: Declarative LangGraph YAML pipelines (`insights-agent.yaml`).
  - `skills/`: The 7 pipeline skills (`skill-router`, `metadata-answerer`, `schema-sliver`, `query-generator`, `governed-executor`, `result-assessor`, `answer-composer`).
  - `rain-api/`: Existing FastAPI backend application.
  - `rain-neo4j-graph/`: Local Neo4j Knowledge Graph (KAG) with 11 ontology mappings, Concepts, Entities, and Attributes.
  - `frontend/`: React application with 5 personas, 6 operational screens, and live/fallback UI states.
- **Relational Store**: PostgreSQL with 17 PRD tables and 103 fields. Some database values remain unverified.
- **Operational Challenge**: Where live queries are unavailable, RAIN currently returns static/fallback data.

### 1.2 Mission Objective
Activate the governed intelligence layer to replace static/fallback queries with live, governed SQL execution, instant Neo4j KAG metadata lookups, and bounded agentic refinement.

---

## 2. Smart Bootstrap: Automated Setup

Rather than manually authoring configuration files, run the automated bootstrap command from the project root:

```bash
python -m insights.bootstrap --app rain
```

This single command automatically:
1. **Introspects PostgreSQL**: Discovers all 17 PRD tables and 103 columns.
2. **Generates Catalog Snapshot**: Writes `apps/rain/catalog/snapshot.json` with SHA-256 version hashing.
3. **Inspects Neo4j KAG (`rain-neo4j-graph`)**: Reads Concept nodes and REFERENCES edges.
4. **Builds Domain Files**: Creates `apps/rain/glossary.yaml` and `apps/rain/join_hints.yaml`.
5. **Configures App Profile**: Creates `apps/rain/app.yaml` with the 5 personas and table-level entitlements.
6. **Generates Keys**: Creates `apps/keys.local.yaml` with pre-computed SHA-256 key hashes.

---

## 3. Core Architectural Non-Negotiables

1. **LLM Never Touches Raw Data Directly**:
   - The LLM never sees database credentials.
   - The LLM never executes SQL.
   - The LLM has zero arbitrary system tools.
   - The LLM **never sees raw result rows** by default (rows travel strictly by reference; state, SSE streams, and audit logs store only `row_count` and `result_ref`).
2. **Dual-Layer Governance (Fail-Closed)**:
   - **L1 AST Policy**: `sqlglot` parses generated SQL, permits only single `SELECT`/`CTE` queries, rejects DDL/DML, enforces `LIMIT`, and confirms that all tables and columns exist in the caller's authorized schema sliver.
   - **L3 Platform Enforcement**: PostgreSQL executes under `SET LOCAL ROLE <persona>` inside a read-only transaction with a statement timeout and row cap.
3. **Server-Side Identity**:
   - `Principal` and `AppProfile` are constructed on the server.
   - The RAIN FastAPI adapter (`insights.api.rain_adapter`) safely maps the client's requested persona to the internal server-side `Principal`.
4. **Declarative LangGraph Pipeline**:
   - Orchestrated via `agents/insights-agent.yaml`.
   - The YAML maps closed-set decision labels to steps. It contains no Python logic.
   - Bounded refinement: `max_refines: 2`, with explicit recursion limits.
5. **Deterministic Abstention for Unverified Data**:
   - If a query hits unverified data fields or unmapped tables with low confidence, the pipeline returns `status: "abstained"` with `reason.code: "data_unverified"`.
   - The React frontend receives this status and displays the verified static benchmark fallback with an explanation banner.

---

## 4. The 7-Stage Intelligence Pipeline

```
[User / React Frontend]
       │
       ▼ (POST /api/v2/ask {query, persona})
[FastAPI rain_adapter] ──► Validates Persona ──► Constructs Principal
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INSIGHTS AGENT RUNTIME                                │
│                                                                                 │
│  [Stage 4: skill-router]                                                        │
│     ├── Access Pre-Check & Input Screening                                      │
│     ├── "metadata_question" ──► [metadata-answerer (Neo4j)]                     │
│     │                                       │                                   │
│     └── "data_query" ──┐                    ▼                                   │
│                        │              [answer-composer] ──► Return to Client    │
│  [Stage 5: schema-sliver] ◄────┘                                                │
│     ├── Entitlement Filtering (Persona-permitted tables only)                   │
│     └── Narrow Schema Sliver (Tables, Columns, Joins, Terms)                    │
│                        │                                                        │
│                        ▼                                                        │
│  [Stage 6: query-generator] (sqlglot AST validation)                            │
│     └── PostgreSQL SELECT generation + Dialect AST check                        │
│                        │                                                        │
│                        ▼                                                        │
│  [Stage 7: governed-executor] (NO LLM)                                          │
│     ├── L1 sqlglot AST Policy Check                                             │
│     ├── L2 EXPLAIN Dry-Run Cost Check                                           │
│     ├── L3 Read-only Tx with `SET LOCAL ROLE <persona>`                         │
│     └── L4 Structured Audit Log (Rows kept by reference)                        │
│                        │                                                        │
│                        ▼                                                        │
│  [Stage 8: result-assessor] (Quality & Sanity Evaluation)                        │
│     └── Labels: "answer" | "refine_query" | "refine_sliver" | "escalate"        │
│                        │                                                        │
│                        ▼                                                        │
│  [Stage 9: answer-composer]                                                     │
│     └── Produces final AskResponse (Status, Data, Confidence, Provenance)       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Integration Blueprint for RAIN

### 5.1 Backend Integration (`rain-api/main.py`)
In RAIN's existing FastAPI backend, mount the adapter router:

```python
from fastapi import FastAPI
from insights.api.rain_adapter import get_rain_router

app = FastAPI(title="RAIN API")

# Mounts POST /api/v2/ask and GET /api/v2/health
app.include_router(get_rain_router(), prefix="/api/v2")
```

### 5.2 React Frontend Integration (`frontend/`)
Connect RAIN's chat and KPI widgets to the new endpoint:

```typescript
// Query the Governed Intelligence Layer
async function queryRainInsights(query: string, persona: string) {
  const response = await fetch('/api/v2/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: query,
      persona: persona, // "executive", "risk_officer", "branch_manager", "loan_officer", "analyst"
      market: "finance",
      product: "rain"
    })
  });
  const result = await response.json();

  if (result.status === 'abstained' || result.confidence?.score < 0.65) {
    // Graceful fallback: render static benchmark data
    return { isFallback: true, data: staticFallbackData, reason: result.reason?.message };
  }

  // Live governed data
  return { isFallback: false, data: result.data, sql: result.query?.sql };
}
```

---

## 6. Verification Checklist

To confirm complete, operational integration:
1. Run `python -m insights.bootstrap --app rain` and verify all 5 steps succeed.
2. Send a metadata question:
   `POST /api/v2/ask` with `{"persona": "executive", "query": "what does portfolio volume mean?"}`.
   Verify response is `status: "answered"` from Neo4j without SQL generation.
3. Send a live data question:
   `POST /api/v2/ask` with `{"persona": "executive", "query": "what is our total loan portfolio volume this quarter?"}`.
   Verify response is `status: "answered"` with live PostgreSQL data.
4. Verify persona access control:
   Query a restricted table as `branch_manager` and verify `row_filter` enforcement or `status: "denied"`.
