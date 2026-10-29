# RAIN Intelligence Layer Setup & Smart Bootstrap Guide
**Tailored Specifically for the RAIN Application Repository**

---

## 1. The One-Command Smart Bootstrap (Run This First!)

You already copied `insights/`, `agents/`, and `skills/` to your project root. 
You **do not** need to manually create `apps/rain/`, write schemas, or generate keys. 

Simply run this single smart bootstrap command from your project root:

```bash
python -m insights.bootstrap --app rain
```

### What this automatically does in seconds:
1. **Connects to your local PostgreSQL**: Introspects your 17 PRD tables and 103 fields.
2. **Generates the Catalog Snapshot**: Auto-creates `apps/rain/catalog/snapshot.json` with deterministic content hashing.
3. **Connects to Neo4j KAG (`rain-neo4j-graph`)**: Extracts Concepts, Definitions, and Foreign Key Relationships.
4. **Builds Glossary & Joins**: Auto-creates `apps/rain/glossary.yaml` and `apps/rain/join_hints.yaml`.
5. **Configures the App Profile**: Auto-creates `apps/rain/app.yaml` with entitlements for your 5 personas (`executive`, `risk_officer`, `branch_manager`, `loan_officer`, `analyst`).
6. **Generates Persona Keys**: Auto-creates `apps/keys.local.yaml` with ready-to-use keys for all 5 personas.

---

## 2. Environment Configuration (`.env`)

Ensure your `.env` in the root has your database and Neo4j credentials:

```dotenv
# ==============================================================================
# 1. POSTGRESQL (RAIN Relational Database)
# ==============================================================================
INSIGHTS_PG_HOST=127.0.0.1
INSIGHTS_PG_PORT=5432
RAIN_PG_DB=rain_db
INSIGHTS_PG_ADMIN_USER=postgres
INSIGHTS_PG_ADMIN_PASSWORD=your_postgres_password
RAIN_PG_USER=postgres
RAIN_PG_PASSWORD=your_postgres_password

# ==============================================================================
# 2. NEO4J KNOWLEDGE GRAPH (rain-neo4j-graph)
# ==============================================================================
INSIGHTS_KAG_URI=bolt://127.0.0.1:7687
INSIGHTS_KAG_USER=neo4j
INSIGHTS_KAG_PASSWORD=your_neo4j_password
INSIGHTS_KAG_DATABASE=neo4j

# ==============================================================================
# 3. LLM GATEWAY (OpenAI / Ollama / Local / LiteLLM)
# ==============================================================================
INSIGHTS_LLM_PROVIDER=openai_compat
INSIGHTS_LLM_BASE_URL=http://localhost:11434/v1
INSIGHTS_LLM_MODEL=llama3.1
INSIGHTS_LLM_API_KEY=ollama

# ==============================================================================
# 4. SERVER CONFIGURATION
# ==============================================================================
INSIGHTS_API_KEYS_FILE=apps/keys.local.yaml
INSIGHTS_ROOT=.
```

---

## 3. Verify Connections

Run the diagnostic script to confirm everything is communicating:

```bash
python scripts/verify_rain_connections.py --app rain
```
*(Or simply let `python -m insights.bootstrap --app rain` perform the checks for you).*

---

## 4. Mounting in RAIN's FastAPI Backend (`rain-api/main.py`)

Because `insights` is located directly at your project root, you can mount the ready-to-use RAIN adapter router into your existing FastAPI app with just two lines.

In `rain-api/main.py` (or your FastAPI app entry point):

```python
from fastapi import FastAPI
from insights.api.rain_adapter import get_rain_router

app = FastAPI(title="RAIN API")

# Mount the Governed Intelligence Layer
app.include_router(get_rain_router(), prefix="/api/v2")
```

### Why this adapter is smart:
- **Compatible with RAIN's existing body format**: Directly accepts `{"persona": "executive", "query": "what is our total loan portfolio volume?"}`.
- **Server-Side Identity**: It maps the requested `persona` to an internal `Principal` with role-based entitlements.
- **Full Governance**: Runs the 7-stage pipeline (`skill-router` -> `schema-sliver` -> `query-generator` -> `governed-executor` -> `result-assessor` -> `answer-composer`).
- **Rows Delivered to Frontend**: The pipeline protects data from LLMs internally ("rows by reference"), but provides the structured rows in the final JSON response so React can render tables and KPI charts.

---

## 5. React Frontend Integration (`frontend/`)

In your React frontend:
1. Make a POST request to `/api/v2/ask`:
```typescript
const response = await fetch('/api/v2/ask', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: userQuery,
    persona: activePersona, // e.g. "executive", "loan_officer"
    market: "finance",
    product: "rain"
  })
});
const result = await response.json();
```

2. **Handling Fallback Data**:
```typescript
if (result.status === 'abstained' || result.confidence?.score < 0.65) {
  // Render existing static fallback data with a non-blocking indicator
  return <FallbackCard data={staticData} message={result.reason?.message} />;
}
// Render live governed SQL results
return <LiveKPICard data={result.data} />;
```

---

## 6. End-to-End Test Commands

### Test 1: Neo4j KAG Metadata Query (Zero SQL, instant graph lookup)
```bash
curl -X POST http://127.0.0.1:8000/api/v2/ask \
  -H "Content-Type: application/json" \
  -d '{"persona": "executive", "query": "what does portfolio volume mean?"}'
```

### Test 2: Governed SQL Data Query (Postgres live execution)
```bash
curl -X POST http://127.0.0.1:8000/api/v2/ask \
  -H "Content-Type: application/json" \
  -d '{"persona": "executive", "query": "what is our total loan portfolio volume this quarter?"}'
```

### Test 3: Unverified DB Values / Graceful Fallback
```bash
curl -X POST http://127.0.0.1:8000/api/v2/ask \
  -H "Content-Type: application/json" \
  -d '{"persona": "risk_officer", "query": "show unverified third-party credit scores"}'
```
*(Returns `status: "abstained"`, triggering the static fallback gracefully without crashing).*
