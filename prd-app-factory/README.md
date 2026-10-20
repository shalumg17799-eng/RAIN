# PRD-to-App Factory

Five Claude agents that turn a product requirements document (plus data, if you have it) into a
verified, governed data-and-AI application and deploy it to Azure Container Apps.

This folder is self-contained: the agents, their skills and tools, the governed AI layer the
generated apps use, the runtime app, deployment templates, local infrastructure, tests and an
example PRD. Nothing in it is specific to one app: everything app-specific is written into an
**App Pack** (`apppacks/<app_id>/`).

## The agents

| # | Agent | Stages | Produces |
|---|---|---|---|
| 1 | Requirements | PRD ingest, data contract | `manifest.yaml` (personas, every KPI and signal figure), `data_contract.yaml` |
| 2 | Data | profile or generate, load, data quality, recalibrate | `data/vN/` versions in schema `app_<id>`, `reports/dq.json` |
| 3 | Knowledge & AI | metric layer, ontology and graph, governed profile | `metrics.yaml`, `insights/<id>/` (glossary, joins, examples, `app.yaml`), Postgres roles and row-level security |
| 4 | App builder | UI configuration, preview | `ui.json`, `reports/preview.json` |
| 5 | QA & release | conformance, security, smoke test, findings, deploy | `reports/conformance.md`, `security.json`, `smoke.json`, `findings.json`, `deploy/`, `release.md` |

A **coordinator** (plain code, not a model) runs them in order and stops at three human gates:

```
requirements -> gate A -> data -> gate B -> knowledge -> app -> verify -> gate C -> release
                           ^------- loop: figures that do not match ------'
```

If verification finds PRD figures the data cannot reproduce, the coordinator sends them back to
agent 2 (recalibrate the data as a new version) or agent 3 (fix a metric definition), at most
`--max-loops` times, then stops at gate C either way.

Each agent is Claude (`FACTORY_MODEL`, default `claude-opus-5-5`) with a role prompt, its skills
(`factory/skills/*/SKILL.md`) and only the tools its stages need. Every tool input is validated
against its schema; agents only get read-only SQL (loading and governance are deterministic code);
only agent 5 can deploy, and only after gate C.

## Layout

```
factory/                 the factory
  agents.py              the five agents (role, skills, tool allowlist)
  coordinator.py         workflow, gates, failure routing, retry
  workqueue.py           one queue per agent (local folders, or Azure Storage queues) and the workers
  portal/                web portal: start runs, follow stages, read outputs, approve gates, retry
  runtime.py             Claude tool-use loop
  tools/                 the agents' tools (requirements, data, knowledge, appbuilder, release)
  skills/                SKILL.md instructions, incl. raide-profiling and raide-dq
  runtime_app/           the generic app every App Pack runs on (FastAPI + one page)
  deploy_templates/      Dockerfile, main.bicep, deploy.ps1 for Azure Container Apps
  conformance.py         PRD figure checks shared by agents 3 and 5
  provision.py           load an App Pack into a database (used by the Azure provisioning job)
insights/, agents/, skills/   the governed AI layer used by generated apps (natural-language
                              questions -> safe SQL under each persona's own database role)
infra/                   Azure deployment of the factory itself (portal + five agent jobs)
examples/rain/           example PRD and data (rural health, 5 personas)
apppacks/                generated apps (one folder each)
tests/                   offline and database tests
docker-compose.yml       local PostgreSQL and Neo4j
```

## Set up

Requires Python 3.11+, Docker, and an Anthropic API key.

```powershell
./setup.ps1            # or ./setup.sh: venv, requirements, .env from .env.example, docker compose up
# then put ANTHROPIC_API_KEY in .env
.venv\Scripts\python -m pytest
```

To use an existing PostgreSQL or Neo4j instead of the compose services, point `PG_*` and `NEO4J_*`
in `.env` at them; the PostgreSQL user needs CREATEDB and CREATEROLE.

## Run

### Portal (recommended)

```powershell
.venv\Scripts\python -m factory portal          # http://127.0.0.1:8090
```

Upload a PRD (and CSVs or a zip), then follow the run: each stage's status and summary, every output
(manifest, contract, metrics, reports), the gate to approve (approvals are recorded with your name),
and a Retry button when a stage is blocked. Locally the five agents run as background workers inside
the portal process; on Azure each is its own job.

### Command line

```powershell
.venv\Scripts\python -m factory run --app rain_demo --prd examples\rain\RAIN_Prototype_Spec_v1.docx --data examples\rain\data
.venv\Scripts\python -m factory status  --app rain_demo
.venv\Scripts\python -m factory approve --app rain_demo --gate A     # after reviewing; then:
.venv\Scripts\python -m factory resume  --app rain_demo
.venv\Scripts\python -m factory serve   --app rain_demo              # http://127.0.0.1:8080
```

- `--auto-approve` approves gates A and B for unattended runs. Gate C always needs a person.
- A stage that fails (an agent error, an API limit) is recorded as blocked with the reason, never
  lost: fix the cause, then `python -m factory retry --app <id>` and `resume`.
- `python -m factory worker --agent <name> [--loop]` processes that agent's queue (what each Azure
  job runs).
- Without `--data`, agent 2 generates synthetic data shaped to the PRD.
- PRDs can be `.docx`, `.md` or `.txt`.
- Every agent run is logged to `apppacks/<id>/logs/` (each tool call, input and result) and its
  handoff to `apppacks/<id>/handoffs/`; token usage per stage is in `run.json`.

## The generated app

One generic service and page serves every App Pack:

- KPI tiles and signal cards per persona, each computed live from the metric layer (tiles show
  `live`, or `static` for a fixed PRD value with no data behind it);
- a question box answered by the governed AI layer under the persona's own PostgreSQL role and
  row-level security.

Locally the persona is chosen on the page. Deployed with sign-in (`ENTRA_CLIENT_ID`), the app uses
Container Apps' built-in Entra ID authentication and shows each user only the personas their Entra
groups allow (`apppacks/<id>/access.yaml`, persona -> group ids).

## Deploy to Azure

Agent 5 writes `apppacks/<id>/deploy/` (Dockerfile, `main.bicep`, `deploy.ps1`). With the Azure CLI
signed in and the `AZURE_*`, `PG_ADMIN_PASSWORD` and `ANTHROPIC_API_KEY` variables set, approving
gate C lets agent 5 deploy, or run `apppacks/<id>/deploy/deploy.ps1` from this folder yourself. It
builds the image in Azure Container Registry, then deploys PostgreSQL Flexible Server, the Container
Apps environment, the app, and a provisioning job (`python -m factory provision --app <id>`) that
loads the data and applies roles and row-level security. The Bicep template has not yet been run
against a live subscription.

## Deploy the factory itself to Azure

`infra/` deploys the build plane: the portal (Container App, optional Entra sign-in), the five
agents as event-driven Container Apps Jobs (each with its own managed identity and its own
Storage queue; one execution per stage), an Azure Files share mounted at `/app/apppacks`, and a
PostgreSQL Flexible Server for staging. Only the release agent's identity can deploy (Contributor
on the resource group, AcrPush); its image adds the Azure CLI.

```powershell
$env:AZURE_SUBSCRIPTION_ID='...'; $env:AZURE_LOCATION='westus3'; $env:AZURE_RESOURCE_GROUP='rg-prd-factory'
$env:AZURE_ACR_NAME='prdfactoryacr1'; $env:PG_ADMIN_PASSWORD='...'; $env:ANTHROPIC_API_KEY='...'
./infra/deploy.ps1          # builds both images in ACR, deploys infra/main.bicep, prints the portal URL
```

`infra/main.bicep` and the release image have not yet been run against a live subscription.

## Third-party pieces

- `insights/`, `agents/`, `skills/`: the governed intelligence layer, vendored with two changes for
  this project: retrieval keeps every table a matched glossary term needs, and the unused generic
  bootstrap entry point was removed.
- `factory/skills/raide-profiling`, `raide-dq`: RAIDE data-engineering skills, copied unchanged.
