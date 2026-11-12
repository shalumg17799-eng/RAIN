"""Build doc/RAIN_v0.4_E2E_Steps_and_Skills.xlsx: the RAIN v0.4 end-to-end steps and the skills behind them."""
import sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import CellIsRule, DataBarRule, FormulaRule
from openpyxl.workbook.properties import CalcProperties
from openpyxl.worksheet.page import PageMargins
from openpyxl.chart.title import Title
from openpyxl.chart.text import RichText, Text
from openpyxl.drawing.text import Paragraph, ParagraphProperties, CharacterProperties, RegularTextRun, Font as DFont

OUT = sys.argv[1]


def chart_title(text):
    cp = CharacterProperties(sz=1100, b=True, solidFill="1F3A5F", latin=DFont(typeface="Arial"))
    return Title(tx=Text(rich=RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), r=[RegularTextRun(rPr=cp, t=text)])])), overlay=False)


def small_text(size=800, bold=False, color="1F2933"):
    cp = CharacterProperties(sz=size, b=bold, solidFill=color, latin=DFont(typeface="Arial"))
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), endParaRPr=cp)])


def value_labels(fmt=None):
    dl = DataLabelList()
    dl.showVal = True
    dl.showCatName = False
    dl.showSerName = False
    dl.showLegendKey = False
    dl.showPercent = False
    dl.position = "outEnd"
    dl.txPr = small_text(800, True)
    if fmt:
        dl.numFmt = fmt
    return dl

# ── palette and styles ───────────────────────────────────────────────────────────────────────────────
NAVY, INK, MUTED, GRID, BAND = "1F3A5F", "1F2933", "5F6B7A", "D5DBE3", "F4F6F9"
STAGE = {  # stage: (strong, tint)
    "Define": ("2E5A88", "DCE7F3"),
    "Build knowledge": ("6A4C93", "E8E1F2"),
    "Build data": ("1B7F79", "D9EFED"),
    "Build app": ("B5651D", "F6E6D8"),
    "Prove & hand over": ("3A7D44", "DFEFE1"),
}
F = "Arial"
thin = Side(style="thin", color=GRID)
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)


def font(size=10, bold=False, color=INK, italic=False):
    return Font(name=F, size=size, bold=bold, color=color, italic=italic)


def fill(rgb):
    return PatternFill("solid", fgColor=rgb)


def put(ws, ref, value, size=10, bold=False, color=INK, italic=False, bg=None, h="left", v="top", wrap=True, border=False, fmt=None):
    c = ws[ref]
    c.value = value
    c.font = font(size, bold, color, italic)
    c.alignment = Alignment(horizontal=h, vertical=v, wrap_text=wrap)
    if bg:
        c.fill = fill(bg)
    if border:
        c.border = BOX
    if fmt:
        c.number_format = fmt
    return c


def title(ws, text, sub, width_cols):
    put(ws, "A1", text, size=16, bold=True, color=NAVY, wrap=False)
    put(ws, "A2", sub, size=10, color=MUTED, wrap=False)
    ws.row_dimensions[1].height = 26


def header(ws, row, labels, widths=None):
    for i, lab in enumerate(labels, start=1):
        c = ws.cell(row=row, column=i, value=lab)
        c.font = font(10, True, "FFFFFF")
        c.fill = fill(NAVY)
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w


def body_row(ws, row, values, bg=None, bold_cols=()):
    for i, val in enumerate(values, start=1):
        c = ws.cell(row=row, column=i, value=val)
        c.font = font(10, i in bold_cols)
        c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        c.border = BOX
        if bg:
            c.fill = fill(bg)


def landscape(ws, fit_width=True):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = fit_width
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5)
    ws.sheet_view.showGridLines = False


# ── content ──────────────────────────────────────────────────────────────────────────────────────────
PHASES = [  # no, name, stage, what comes out, skills / tools
    (1, "PRD & personas", "Define", "v0.2 personas mapped; PRD v0.4 merged: 14 personas, use cases A and B; e2e build prompt written", "Claude skills: docs, docx"),
    (2, "Set up the build folder", "Define", "Worktree RAIN4.0-DIF_BT_integration from commit a513008; inputs copied; LF and disk-space traps fixed", "git worktree"),
    (3, "Factory inputs", "Define", "No-LLM factory extract and planned schema: 53 tables, each with its source", "make_v4_ddl.py"),
    (4, "DIF factory run", "Build knowledge", "dif-build-orchestrator, scenario uc2: package 4.0.0 with 614 nodes and 732 relationships", "11 agents, 24 DIF skills"),
    (5, "KAG publish & refresh", "Build knowledge", "Published with the PRD seed (14 personas), then rebuilt as rain-v4.1.0: 2,603 nodes", "neo4j-publish, neo4j-validate, kag_v4_refresh.py"),
    (6, "Public data", "Build data", "24 public tables for Nevada and Tennessee in public_data, with a manifest; 2 sources blocked", "load_public_data.py"),
    (7, "Synthetic data", "Build data", "59 tables, about 689k rows, seeded and calibrated to the Q3 story; every key checked", "scripts/e2e/synth generator"),
    (8, "Backend API", "Build app", "/api/v4: computed metrics, UI data, chat, 140 queries, write-back flow, proof headers", "FastAPI, build_data_api.py, pytest"),
    (9, "Frontend UI", "Build app", "14 personas, workbenches, patient views on /api/v4; the console shows API calls only", "React + Vite, npm run check"),
    (10, "Run the stack", "Build app", "Compose project rain4: UI 8184, API 8003, Postgres 55436, Neo4j 17477, pgAdmin 5052", "docker compose"),
    (11, "Validate end to end", "Prove & hand over", "Tests, chat, real browser, queries, public data, write-back, KAG, console: see Validation", "playwright-core + Chrome, validators"),
    (12, "Docs & handover", "Prove & hand over", "Query packs and reports, demo queries, backend API list, build log, this workbook", "Claude skill: xlsx"),
]
PH = {p[0]: p for p in PHASES}

# id, step, what we do, input, output, DIF skills, scripts & tools, Claude skill, how we checked, result, status
STEPS = {
    1: [
        ("1.1", "Map the v0.2 personas", "Compare the PRD v0.2 personas with the v0.3 set and list the ones v0.3 left out", "PRD v0.2; Prototype Spec v2 (v0.3)", "Persona gap list", "", "", "", "Reviewed with the user", "6 personas to bring in: Hargrove, Bell, Holloway, Brooks, Okafor, Rosa Martínez", "Done"),
        ("1.2", "Merge into PRD v0.4", "One PRD with every v0.2 and v0.3 persona, keeping both where two share a role", "PRD v0.2, Prototype Spec v2", "PRD v0.4 as a Claude Doc and RAIN_Platform_PRD_v0.4.docx", "", "", "docs, docx", "Reviewed with the user", "14 personas; use cases A and B", "Done"),
        ("1.3", "Write the end-to-end build prompt", "Phases 0 to 8 with the checks each must pass and the traps found in the v0.3 run", "PRD v0.4; the v0.3 run", "doc/prd/RAIN_Platform_PRD_v0.4_e2e_prompt.md", "", "", "", "Used as the checklist in the build log", "9 phases, 6 known traps", "Done"),
    ],
    2: [
        ("2.1", "Commit v0.3 and create the worktree", "Commit the v0.3 work, then add a worktree on its own branch so v0.3 keeps running untouched", "RAIN repo, branch RAIN3.0-DIF_BT_integration", "C:\\Users\\pa613\\RAIN4.0-DIF_BT_integration", "", "git worktree", "", "Separate folder and branch", "Commit a513008 (not pushed)", "Done"),
        ("2.2", "Copy inputs, fix known traps", "Copy the gitignored inputs (.env, keys, initdb, .data/public, store.py); make entrypoint.sh LF; check free space on C:", "v0.3 folder", "A folder that builds", "", ".gitattributes", "", "Backend container starts", "No CRLF crash loop", "Done"),
    ],
    3: [
        ("3.1", "Factory extract", "Write PRD v0.4 in the factory's no-LLM grammar (the factory never reads the docx)", "PRD v0.4", "RAIN_Platform_PRD_v0.4_factory_extract.txt", "Read by prd-intake and the extractors", "", "", "Factory parses it", "Every planned table is mentioned", "Done"),
        ("3.2", "Planned schemas", "One table per planned entity, each with a `-- source:` comment", "PRD v0.4 Section 9", "RAIN_Platform_PRD_v0.4_planned_schemas.sql", "", "make_v4_ddl.py", "", "Reconciliation leaves no table unmapped", "53 tables", "Done"),
    ],
    4: [
        ("4.1", "Intake and metadata", "Parse the requirements, pick the scenario, extract and check the metadata graph", "Extract + planned DDL", "requirements.json; metadata graph", "prd-intake, schema-metadata-extractor, metadata-validator", "factory_v4.py in a helper container (no gates, no LLM)", "", "metadata-validator", "Scenario uc2 (schemas supplied)", "Done"),
        ("4.2", "Domain model and validation gate", "Build and normalise the domain model, then validate it", "Requirements", "domain-model.json; validation report", "domain-model-extractor, domain-model-normalizer, acceptance-check, llm-judge, validation-summary", "factory_v4.py", "", "acceptance-check; llm-judge in heuristic mode", "Gate passed", "Done"),
        ("4.3", "Enrichment", "Map tables to business domains and entities to columns", "Domain model, metadata graph", "domain-catalog.json; semantic-mappings.json", "domain-enricher, semantic-mapper", "factory_v4.py", "", "Confidence and gaps reported", "Every table mapped", "Done"),
        ("4.4", "Data acquisition", "Route the scenario, type the schema, generate sample rows, land, profile and report readiness", "Planned DDL", "data-assets.json; landed CSV + manifest", "scenario-router, provisional-schema-generator, synthetic-data-generator, data-landing, data-profiler, data-readiness-report", "factory_v4.py (10 rows per table, seed 7)", "", "data-readiness-report", "53 tables, readiness synthetic, 0 gaps", "Done"),
        ("4.5", "Ontology", "Build the lower ontology and align its classes to the upper ontology", "Domain model, mappings", "lower-ontology.json; upper-ontology-alignment.json", "lower-ontology-builder, ontology-validator, upper-ontology-aligner", "factory_v4.py", "", "ontology-validator", "53 classes; 26 aligned, 27 without an upper concept (warning)", "Done with gaps"),
        ("4.6", "KAG model, reconcile, package", "Turn the ontology into graph records, precheck them, reconcile with the data, assemble the package", "All factory artifacts", "artifacts/RAIN_Knowledge_Package_v4.0.0 (13 files with SHA-256)", "kag-model-mapper, neo4j-validate, reconciler, package-assembler", "factory_v4.py", "", "Precheck 5/5; reconciliation", "614 nodes, 732 relationships; 53 of 80 concepts reconcile (partial, score 0.662)", "Done with gaps"),
    ],
    5: [
        ("5.1", "Publish release rain-v4.0.0", "Write the graph records into Neo4j database neo4j, then validate the release", "Package 4.0.0", "Release rain-v4.0.0 in Neo4j", "neo4j-publish, neo4j-validate", "publish_v4_kag.py", "", "neo4j-validate", "Published; replaced by 5.3", "Superseded"),
        ("5.2", "Seed the PRD knowledge", "Personas, workbenches and access rules, use cases, contract checkpoint, quality gate, segments", "PRD v0.4", "seeds/rain_v4_prd_seed.py", "", "rain_v4_prd_seed.py", "", "MATCH (p:Persona) returns 14", "139 nodes, 14 personas (kept in 5.3)", "Done"),
        ("5.3", "Rebuild as rain-v4.1.0", "One release with what v0.4 has now; the v1/v2 seed graph and 4.0.0 are deleted", "Factory ontology, PRD seed, live rain_v4 schema, query pack, flows", "Release rain-v4.1.0: 14 personas, 84 tables, 140 queries, metric groups, datasets, flows, sources", "", "kag_v4_refresh.py", "", "RAIN_v4_kag_check.md", "2,603 nodes; 21/21 checks", "Done"),
    ],
    6: [
        ("6.1", "Download public sources", "Nevada and Tennessee: CDC PLACES, CDC/ATSDR SVI, HRSA HPSA and sites, NPPES, RUCC, ZCTA gazetteer, Census ACS 5-year, FORHP rural areas, ZCTA-county, CMS hospitals, CMS POS, HRSA UDS, County Health Rankings 2025, CMS eCQM, OSRM drive times", "Public websites and APIs", ".data/public with MANIFEST.md (URL, release, date, rows)", "", "Download scripts", "", "Manifest per source", "All open sources loaded", "Done"),
        ("6.2", "Load into public_data", "Load every source into Postgres and make it queryable", ".data/public", "24 tables in rain_v4.public_data", "", "load_public_data.py", "", "public_data_v4.py: each table queryable via /api/v4/data and used in the UI or a query", "24/24", "Done"),
        ("6.3", "Blocked sources", "Sources that need an account or a manual download are not faked; visuals read a loaded substitute and say so", "FCC BDC; CMS Geographic Variation", "Substitutes: Census ACS broadband; CMS hospital data", "", "", "", "Listed as open gaps", "FCC needs your account and API token; CMS needs a browser download", "Blocked"),
    ],
    7: [
        ("7.1", "Generate row-level data", "Seeded generator writes every operational record: patients, encounters, claims, claim lines, quality results, readings, campaign, model scores, schedules, reminders", "Planned DDL; scenario file", "59 synthetic tables, about 689k rows (31,600 patients, 95,000 encounters, 150,000 claims, 245,000 claim lines)", "", "scripts/e2e/synth (seed 2026)", "", "Same seed gives the same rows", "Deterministic", "Done"),
        ("7.2", "Calibrate to the Q3 story", "Tune the rows so SQL over them gives back the PRD's numbers", "rain_v4_scenario.json", "9,400 members, $412 vs $386 PMPM, gate 2 of 5, 2,140 low-value services, 312 avoidable ED visits per 1,000", "", "gen_synthetic_v4.py, metrics_roundtrip_v4.py", "", "metrics_roundtrip_v4.py", "324 values equal the scenario; 52 differ, each with its reason", "Done"),
        ("7.3", "Load with integrity", "Create tables in dependency order, derive reference tables from public_data, check every foreign key, grant the app login", "Generated rows", "rain_v4.synthetic loaded", "", "gen_load.py", "", "Foreign key check", "Keys join across tables", "Done"),
    ],
    8: [
        ("8.1", "Compute every number", "Every constant, record and dataset is computed by SQL per request; cached 10 minutes, dropped on any write", "synthetic + public_data", "metrics_v4.py, metrics_personas_v4.py", "", "Python, SQL", "", "Edit a row, the number changes", "No stored figures", "Done"),
        ("8.2", "UI data API", "GET /api/v4/ui/data: persona contracts and copy are templates filled with the computed values", "Computed context; ui_v4.dataset (config)", "ui_data_v4.py, templating_v4.py", "", "FastAPI", "", "test_ui_data_v4.py", "One response for all screens", "Done"),
        ("8.3", "Chat API", "GET /briefing and POST /ask for 14 personas: prepared answers built live, persona queries run live, refusals with a reason", "Contracts, query pack", "ultra_v4_api.py, chat_v4.py", "", "FastAPI", "", "validate_v4.py", "436/436", "Done"),
        ("8.4", "Persona query pack", "5 synthetic + 5 public queries per persona; patients see only their own record, the payer only aggregates", "rain_v4 schemas", "doc/queries/rain_v4_persona_queries.sql (140); persona_queries_v4.py", "", "make_v4_query_pack.py", "", "query_check_v4.py", "559/560", "Done"),
        ("8.5", "Write-back flow", "POST /api/v4/flow/{book, contact, reply, reading, handoff, inbox, signoff, note, reset}, each with an undo log", "User actions", "flow_v4.py; synthetic.flow_event", "", "FastAPI", "", "flow_check_v4.py", "7/7", "Done"),
        ("8.6", "Data API, proof headers, tests", "Generated read-only table API; X-RAIN-* headers on every response; backend tests", "DDL", "data_api_v4.py; tests", "", "build_data_api.py, pytest", "", "pytest in rain4-backend-1", "388/388", "Done"),
    ],
    9: [
        ("9.1", "Personas and workbenches", "14 personas in switcher order (11 operators, 2 patients, the payer); site-scoped workbenches, RHTP reporting, front-desk inbox, pre-visit summary, patient views", "PRD v0.4 Sections 6-7", "Persona folders (manifest + index, scaffold-persona layout)", "", "React, Vite", "", "Browser crawl", "14/14 briefings, 51/51 pages", "Done"),
        ("9.2", "Wire to the backend", "Ultra http mode on /api/v4/ui; boot loader reads /data; actions write through /flow, then re-read", "Backend APIs", "backendData.ts, flowApi.ts, store.ts", "", "TypeScript", "", "No data literals in components", "All screen data from the backend", "Done"),
        ("9.3", "Console shows backend calls only", "One collapsed console entry per API call: method, path, status, time, turn", "", "core/log.ts, core/api/proof.ts", "", "", "", "console_check_v4.mjs", "0 non-API messages", "Done"),
        ("9.4", "npm run check", "Typecheck, unit tests, lint ratchet, catalog, standard audit, registration, build", "", "Frontend build", "", "npm, vitest, eslint", "", "npm run check", "516 tests pass", "Done"),
    ],
    10: [
        ("10.1", "Start compose project rain4", "Always with the port variables, so it never collides with the other RAIN stacks", "docker-compose.yml", "UI 8184, API 8003, Postgres 55436, Neo4j 17477/17690", "", "docker compose", "", "Containers healthy", "Running", "Done"),
        ("10.2", "pgAdmin for rain_v4", "Standalone pgAdmin with the server preconfigured and the query pack in its file storage", "", "pgAdmin on 5052", "", "start_pgadmin_v4.sh", "", "Opens rain_v4", "Running", "Done"),
    ],
    11: [
        ("11.1", "Automated tests", "Backend tests in the container, frontend tests in npm run check", "", "", "", "pytest, vitest", "", "Test runs", "388 + 516 pass", "Done"),
        ("11.2", "Every chat answer", "Every scripted question, chip and follow-up of every persona through POST /api/v4/ui/ask", "", "", "", "validate_v4.py", "", "Expected turn per input", "436/436", "Done"),
        ("11.3", "Real browser pass", "Chrome drives every briefing, chip, sidebar page, patient thread and persona query", "", "Screenshots in artifacts/", "", "crawl_v4.mjs, chat_queries_v4.mjs", "run (earlier session)", "Rendered text and console errors", "14 briefings, 98 chips, 51 pages, 2 threads, 140 queries", "Done"),
        ("11.4", "Per-persona query check", "Each query asked 3 ways in its persona's chat, plus the API; first-person patient phrasing; refusals", "", "RAIN_v4_query_check.md", "", "query_check_v4.py", "", "Turn id and rows per answer", "559/560; phrasing 20/22; refusals 5/5", "Done"),
        ("11.5", "Data-driven proof", "Edit a benchmark row and a claim in Postgres, see the CEO tiles change without a restart, restore", "", "Screenshots before and after", "", "demo_data_driven_v4.py / .mjs", "", "UI shows the edited values", "$412/$386 to $412/$394 and $422/$386, then restored", "Done"),
        ("11.6", "Public data, write-back, KAG", "Every public table usable from the UI; every write-back changes the next read; KAG content checks", "", "Reports in doc/queries", "", "public_data_v4.py, flow_check_v4.py, kag_v4_refresh.py", "", "Scripted checks", "24/24, 7/7, 21/21", "Done"),
        ("11.7", "Console and API usage", "The console shows only API calls; record every backend call of a full browser run", "", "console_check.json, api_usage.json", "", "console_check_v4.mjs, api_usage_v4.mjs", "", "Network and console capture", "33/33 API entries; 175/175 calls returned 200", "Done"),
    ],
    12: [
        ("12.1", "Query docs", "Persona queries, 3 + 3 demo queries per persona, the per-persona query check", "", "RAIN_v4_persona_queries.md/.sql, RAIN_v4_demo_queries.md, RAIN_v4_query_check.md", "", "make_v4_demo_queries.py", "", "", "In doc/queries", "Done"),
        ("12.2", "Proof reports", "Validation, public data in the UI, backend data proof, chat end to end, metrics round trip, flow, KAG", "", "RAIN_v4_*.md in doc/queries", "", "make_v4_docs.py", "", "", "In doc/queries", "Done"),
        ("12.3", "Run docs", "How to run, rebuild and call the stack", "", "DOCKER.md, backend-integration.md, RAIN_v4_backend_apis.md, RAIN_v0.4_build_log.md", "", "", "", "", "In doc/", "Done"),
        ("12.4", "This workbook", "Steps and skills on one page", "This build", "RAIN_v0.4_E2E_Steps_and_Skills.xlsx", "", "openpyxl", "xlsx", "", "In doc/", "Done"),
    ],
}

# DIF factory skills (run in the v0.4 factory, from the package provenance), in pipeline order
DIF = [  # skill, agent, stage, what it does, output in v0.4
    ("prd-intake", "dif-build-orchestrator", "Intake", "Parses the PRD into requirements (use cases, entities, KPIs, policies) and detects the build scenario", "requirements.json; scenario uc2"),
    ("schema-metadata-extractor", "metadata-extraction-agent", "Metadata", "Turns the PRD and schemas into a metadata graph: entities, tables, columns, keys, lineage", "Metadata graph of 53 tables"),
    ("metadata-validator", "metadata-extraction-agent", "Metadata", "Checks the metadata graph for completeness, relationship integrity and lineage", "Issues and a confidence score"),
    ("domain-model-extractor", "domain-modelling-agent", "Domain model", "Drafts the domain model (entities, attributes, keys, relationships, glossary) with evidence", "Draft domain model"),
    ("domain-model-normalizer", "domain-modelling-agent", "Domain model", "Normalises names, de-duplicates and validates relationships", "domain-model.json"),
    ("acceptance-check", "validation-agent", "Validation gate", "Deterministic checks: schema contract, thresholds, required keys, cross references", "Validation checks"),
    ("llm-judge", "validation-agent", "Validation gate", "Scores an artifact against a rubric; heuristic verdict when no LLM is used", "Verdict (heuristic in this run)"),
    ("validation-summary", "validation-agent", "Validation gate", "Merges the checks and the judge into one validation report", "Validation report"),
    ("domain-enricher", "domain-enrichment-agent", "Enrichment", "Maps each table to a business domain and capability", "domain-catalog.json"),
    ("semantic-mapper", "domain-enrichment-agent", "Enrichment", "Maps entities and attributes to tables and columns, with confidence and gaps", "semantic-mappings.json"),
    ("scenario-router", "data-acquisition-agent", "Data acquisition", "Decides the scenario: uc1 no sources, uc2 schema only, uc3 schema through MCP", "uc2"),
    ("provisional-schema-generator", "data-acquisition-agent", "Data acquisition", "Derives typed tables, keys and DDL from the domain model", "Typed schema"),
    ("synthetic-data-generator", "data-acquisition-agent", "Data acquisition", "Generates seeded rows with foreign-key integrity, marked synthetic", "10 sample rows per table (app data: step 7.1)"),
    ("data-landing", "data-acquisition-agent", "Data acquisition", "Lands rows as CSV with a manifest in the artifact store", "landing/rain/<run>/"),
    ("data-profiler", "data-acquisition-agent", "Data acquisition", "Profiles each table: rows, nulls, distinct values, ranges", "Profiles in quality-report.json"),
    ("data-readiness-report", "data-acquisition-agent", "Data acquisition", "One readiness entry per table: landed, schema only or missing", "data-assets.json: 53 tables, 0 gaps"),
    ("lower-ontology-builder", "lower-ontology-agent", "Ontology", "Builds the enterprise ontology: classes, properties, axioms", "lower-ontology.json: 53 classes"),
    ("ontology-validator", "lower-ontology-agent", "Ontology", "Checks classes, provenance, dangling properties, naming, coverage", "Ontology checks"),
    ("upper-ontology-aligner", "upper-ontology-alignment-agent", "Ontology", "Aligns each class to a governed upper-ontology concept", "26 aligned, 27 not (warning)"),
    ("kag-model-mapper", "kag-builder-agent", "KAG", "Maps ontology, mappings and data assets to Neo4j node and relationship records", "614 nodes, 732 relationships"),
    ("neo4j-validate", "kag-builder-agent", "KAG", "Validates a release: orphans, unaligned classes, unmapped tables, provenance", "Precheck 5/5 passed"),
    ("neo4j-publish", "kag-builder-agent", "KAG", "Writes the records to Neo4j idempotently (MERGE by key and release)", "Deferred in the run; published by publish_v4_kag.py"),
    ("reconciler", "reconciliation-agent", "Reconcile & package", "Checks that concepts, mappings, data and KPIs agree; gives a readiness verdict", "53 of 80 concepts; partial (0.662)"),
    ("package-assembler", "package-publisher-agent", "Reconcile & package", "Assembles the versioned knowledge package with checksums", "RAIN_Knowledge_Package_v4.0.0"),
]
STAGE_ORDER = ["Intake", "Metadata", "Domain model", "Validation gate", "Enrichment", "Data acquisition", "Ontology", "KAG", "Reconcile & package"]
STEP_OF = {"Intake": "4.1", "Metadata": "4.1", "Domain model": "4.2", "Validation gate": "4.2", "Enrichment": "4.3",
           "Data acquisition": "4.4", "Ontology": "4.5", "KAG": "4.6", "Reconcile & package": "4.6"}

CLAUDE = [  # skill, used for, when, output
    ("docs", "Write the merged PRD v0.4 as a living document", "2026-11-09", "PRD v0.4 Claude Doc", "1.2"),
    ("docx", "Read the v0.2 / v0.3 PRDs and produce PRD v0.4 as Word", "2026-11-09", "RAIN_Platform_PRD_v0.4.docx", "1.2"),
    ("run", "Launch and drive the running app in a real browser, take screenshots", "2026-11-06", "Browser pass of the running stack", "11.3"),
    ("xlsx", "Workbooks: environment configuration, data acquisition steps and skills, this end-to-end sheet", "2026-10-20, 2026-11-10", "This workbook and two earlier ones", "12.4"),
    ("claude-api", "Build the DIF agents that call Claude", "2026-10-20", "DIF agent code", "4.1-4.6"),
    ("pptx", "Editable project architecture deck", "2026-10-14", "Architecture deck", "Earlier wave"),
    ("pdf", "RHTP deep dive: challenges and how the platform answers them", "2026-10-27", "RHTP PDF", "Earlier wave"),
]

TOOLS = [  # tool, what it does, used in
    ("dif-build-orchestrator", "Runs the whole DIF factory: intake, then the agents as children (human gates auto-approved in this run)", "4.1-4.6"),
    ("build_data_api.py", "Generates the read-only table API from the DDL (rain-api/data_api_v4.py)", "8.6"),
    ("scripts/e2e/synth", "Seeded row-level synthetic data generator and loader (59 tables)", "7.1-7.3"),
    ("metrics_v4.py", "Computes every UI number by SQL per request", "8.1"),
    ("kag_v4_refresh.py", "Rebuilds the KAG as rain-v4.1.0 from what v0.4 has now", "5.3"),
    ("scaffold-persona", "Frontend persona folder layout (manifest + index)", "9.1"),
    ("npm run check", "Typecheck, tests, lint ratchet, catalog, standard audit, build", "9.4"),
    ("playwright-core + Chrome", "Drives the real app for the browser checks", "11.3-11.7"),
    ("docker compose (rain4)", "Runs UI, API, Postgres and Neo4j on their own ports", "10.1"),
    ("pgAdmin / Neo4j Browser", "Query Postgres and the KAG by hand", "10.2, 5.3"),
]

NOT_USED = [
    ("source-discovery, ddl-source-reader, mcp-call", "DIF factory", "Only for uc3 (schemas read from a source system through MCP); v0.4 supplies its schema (uc2)"),
    ("package-store", "DIF factory", "The package was copied to artifacts/ instead of the artifact store"),
    ("platform-kag-seed", "DIF factory", "The KAG was rebuilt by kag_v4_refresh.py (step 5.3)"),
    ("skill-router, schema-sliver, query-generator, governed-executor, result-assessor, answer-composer, synthesizer, metadata-answerer, hitl-reviewer", "Insights layer (skills/insights)", "Serve the legacy /api/v2/ask; v0.4 chat answers are computed by /api/v4"),
    ("requirements-interpreter, persona-question-designer, scenario-designer, entity-model-designer, build-data-map, prd-finalizer, question-registry-reducer, upper-ontology-curator, upper-ontology-reducer", "Data design (skills/data)", "Not part of the v0.4 run"),
]

VALIDATION = [  # area, check, what it proves, script, passed, total, explained, note
    ("Backend", "Backend tests", "Units, APIs and a live Postgres edit", "pytest in rain4-backend-1", 388, 388, 0, ""),
    ("Frontend", "Frontend tests", "Components, contracts and snapshots", "vitest (npm run check)", 516, 516, 0, ""),
    ("Chat API", "Every chat answer", "Every scripted question, chip and follow-up reaches its answer", "validate_v4.py", 436, 436, 0, ""),
    ("Browser", "Briefings", "Each persona's briefing renders", "crawl_v4.mjs", 14, 14, 0, ""),
    ("Browser", "Briefing chips", "Every chip shows the backend's answer", "crawl_v4.mjs", 98, 98, 0, ""),
    ("Browser", "Sidebar pages", "Every page of every persona renders", "crawl_v4.mjs", 51, 51, 0, ""),
    ("Browser", "Patient threads", "Linda's and Rosa's patient views play", "crawl_v4.mjs", 2, 2, 0, ""),
    ("Browser", "Persona queries in chat", "Each query typed in chat renders a live table", "chat_queries_v4.mjs", 140, 140, 0, ""),
    ("Queries", "Queries asked 3 ways + API", "Exact question, id and loose text each run the query", "query_check_v4.py", 559, 560, 1, "CEO-S5 typed loosely gets its prepared answer by design"),
    ("Queries", "Patient phrasing", "First-person questions run the patient's query", "query_check_v4.py", 20, 22, 2, "Two reminders phrasings get the prepared reminders answer, which shows her own rows"),
    ("Queries", "Refusals with a reason", "Another person's query is refused and explained", "query_check_v4.py", 5, 5, 0, ""),
    ("Public data", "Public tables usable", "Each table queryable and used in the UI or a query", "public_data_v4.py", 24, 24, 0, ""),
    ("Data", "Computed values", "SQL over the rows gives back the scenario", "metrics_roundtrip_v4.py", 324, 376, 52, "52 differ by design, each listed with its reason in RAIN_v4_metrics_roundtrip.md"),
    ("Data", "Data-driven proof", "A Postgres edit shows in the UI without a restart", "demo_data_driven_v4.py", 2, 2, 0, "Benchmark edit and claim edit, then restored"),
    ("Write-back", "Flow steps", "Each write changes the next read; reset restores", "flow_check_v4.py", 7, 7, 0, ""),
    ("KAG", "KAG checks", "rain-v4.1.0 holds every persona, table, query and flow", "kag_v4_refresh.py", 21, 21, 0, ""),
    ("Factory", "KAG precheck", "No orphans; tables mapped; provenance present", "neo4j-validate", 5, 5, 0, "Warning: 27 classes without an upper concept"),
    ("Console", "Console entries", "Every console message is a backend API call", "console_check_v4.mjs", 33, 33, 0, ""),
    ("API", "Backend calls in a full run", "Every call the browser made returned 200", "api_usage_v4.mjs", 175, 175, 0, "6 endpoints used"),
]

GAPS = [
    ("Blocked source", "FCC Broadband Data Collection", "Needs your FCC account and API token", "Census ACS household broadband"),
    ("Blocked source", "CMS Medicare Geographic Variation", "data.cms.gov needs a browser download", "CMS hospital data for unplanned visits"),
    ("Knowledge", "Ontology alignment", "27 classes have no upper-ontology concept; reconciliation 53 of 80 (partial)", "Same known gap as v0.3"),
    ("Repo", "Nothing committed", "All v0.4 work is uncommitted on RAIN4.0-DIF_BT_integration", "Commit when you ask; never pushed"),
]

RUNTIME = [  # action, call, module, data, user sees, calls in run
    ("Open the app or switch persona", "GET /api/v4/ui/data", "ui_data_v4 + metrics_v4", "Reads synthetic + public_data; fills ui_v4 templates", "Every number on every screen", "71"),
    ("Persona's Ask AI or AI widget opens", "GET /api/v4/ui/briefing", "ultra_v4_api + chat_v4", "Persona contract, built live", "Greeting, KPIs, chips", "72"),
    ("Click a chip or ask a question", "POST /api/v4/ui/ask", "ultra_v4_api", "Prepared answer built from computed data", "Answer with visuals", "28 ask calls in all"),
    ("Ask one of my queries", "POST /api/v4/ui/ask", "persona_queries_v4", "Runs the pack SQL read-only (15 s limit)", "Live table of rows", "(in the 28)"),
    ("Ask someone else's query", "POST /api/v4/ui/ask", "persona_queries_v4.owner_of", "Nothing read", "Refusal with the reason and my own questions", "(in the 28)"),
    ("Approve, log a call, book, sign off, send a note, BP reading", "POST /api/v4/flow/<action>", "flow_v4", "Writes synthetic rows + flow_event, then the app re-reads /data", "The change on every screen", "2"),
    ("Press Reset", "POST /api/v4/flow/reset", "flow_v4", "Replays the undo log", "Back to the generated morning", "2"),
]

STACK = [
    ("App (UI)", "http://localhost:8184/login/rain/?access=rain@9705", "8184", "Access key in the link", "14 personas; patients at /patient and /patient?patient=rosa"),
    ("Backend API", "http://localhost:8003/docs", "8003", "None", "Swagger for /api/v4/ui, /data, /queries, /flow"),
    ("Postgres", "localhost:55436, database rain_v4", "55436", "See doc/DOCKER.md", "Schemas synthetic, public_data, ui_v4"),
    ("pgAdmin", "http://localhost:5052", "5052", "admin@rain.app / admin", "Server preconfigured; query pack in file storage"),
    ("Neo4j Browser (KAG)", "http://localhost:17477/browser/", "17477 (bolt 17690)", "See doc/DOCKER.md", "Release rain-v4.1.0 in database neo4j"),
]

# ── workbook ─────────────────────────────────────────────────────────────────────────────────────────
wb = openpyxl.Workbook()
wb._named_styles["Normal"].font = Font(name=F, size=10)
wb.calculation = CalcProperties(fullCalcOnLoad=True)

# Steps -------------------------------------------------------------------------------------------------
st = wb.active
st.title = "E2E Steps"
title(st, "End-to-end steps", "Every step of the RAIN v0.4 build, in order, with the skills, scripts and checks behind it. Phase rows are coloured by stage.", 12)
put(st, "A3", "Status: Done · Done with gaps (works, known gap noted) · Superseded (replaced by a later step) · Blocked (needs your action)", size=9, color=MUTED, wrap=False)
HDR = ["#", "Phase", "Step", "What we do", "Input", "Output / artifact", "DIF skills", "Scripts & tools", "Claude skill", "How we checked", "Result", "Status"]
header(st, 5, HDR, [6, 18, 26, 46, 24, 36, 32, 28, 13, 28, 32, 15])
r = 6
step_rows = []
for no, steps in STEPS.items():
    _, name, stage, _, _ = PH[no]
    strong, tint = STAGE[stage]
    st.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(HDR))
    put(st, f"A{r}", f"Phase {no} · {name}   ({stage})", size=11, bold=True, color="FFFFFF", bg=strong, v="center", wrap=False)
    st.row_dimensions[r].height = 22
    r += 1
    for s in steps:
        body_row(st, r, [s[0], name, *s[1:]], bold_cols=(3,))
        st.cell(row=r, column=2).fill = fill(tint)
        st.cell(row=r, column=1).fill = fill(tint)
        step_rows.append(r)
        r += 1
last_step = r - 1
st.freeze_panes = "D6"
rng = f"L6:L{last_step}"
st.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Done"'], fill=fill("DFEFE1"), font=Font(name=F, color="2F6B38", bold=True)))
st.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Done with gaps"'], fill=fill("FFF1D6"), font=Font(name=F, color="8A5A00", bold=True)))
st.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Blocked"'], fill=fill("FBE0DD"), font=Font(name=F, color="A1281D", bold=True)))
st.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Superseded"'], fill=fill("ECEFF3"), font=Font(name=F, color=MUTED, bold=True)))
landscape(st)
st.print_title_rows = "5:5"

# Skills ------------------------------------------------------------------------------------------------
sk = wb.create_sheet("Skills")
title(sk, "Skills we follow", "A: the DIF factory skills that ran for v0.4 (from the package provenance). B: Claude skills used. C: project tools. D: skills available but not used in this run.", 9)
put(sk, "A4", "A. DIF factory skills run in the v0.4 factory (release rain-v4.0.0, package 4.0.0)", size=11, bold=True, color=NAVY, wrap=False)
SKH = ["#", "Skill", "Agent", "Factory stage", "Step", "What it does", "Output in v0.4", "Ran in v0.4", "Evidence"]
header(sk, 5, SKH, [5, 28, 30, 20, 8, 58, 42, 12, 30])
r = 6
for i, (name, agent, stage, what, out) in enumerate(DIF, start=1):
    body_row(sk, r, [i, name, agent, stage, STEP_OF[stage], what, out, "Yes", "Package provenance.json"], bold_cols=(2,))
    sk.cell(row=r, column=8).alignment = Alignment(horizontal="center", vertical="top")
    r += 1
DIF_FIRST, DIF_LAST = 6, r - 1
sk.conditional_formatting.add(f"H{DIF_FIRST}:H{DIF_LAST}", CellIsRule(operator="equal", formula=['"Yes"'], fill=fill("DFEFE1"), font=Font(name=F, color="2F6B38", bold=True)))
# agents count note
put(sk, f"B{r}", "Agents involved", bold=True, color=MUTED)
put(sk, f"C{r}", f'=SUMPRODUCT(1/COUNTIF(C{DIF_FIRST}:C{DIF_LAST},C{DIF_FIRST}:C{DIF_LAST}))', bold=True, fmt="0")
put(sk, f"F{r}", "Distinct agents in column C (dif-build-orchestrator runs the other agents as children: 11 agents in all, per provenance.json).", size=9, color=MUTED, italic=True)
AGENTS_CELL = f"C{r}"
r += 2

put(sk, f"A{r}", "B. Claude skills used to produce the work", size=11, bold=True, color=NAVY, wrap=False)
r += 1
for i, lab in enumerate(["#", "Claude skill", "Used for", "When", "Step", "Output"], start=1):
    c = sk.cell(row=r, column=i, value=lab)
    c.font = font(10, True, "FFFFFF"); c.fill = fill(NAVY); c.border = BOX
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
sk.merge_cells(start_row=r, start_column=6, end_row=r, end_column=7)
r += 1
for i, (name, used, when, out, step) in enumerate(CLAUDE, start=1):
    body_row(sk, r, [i, name, used, when, step, out], bold_cols=(2,))
    sk.merge_cells(start_row=r, start_column=6, end_row=r, end_column=7)
    r += 1
r += 1
put(sk, f"A{r}", "C. Project tools and generators", size=11, bold=True, color=NAVY, wrap=False)
r += 1
for i, lab in enumerate(["#", "Tool", "What it does", "", "Step"], start=1):
    c = sk.cell(row=r, column=i, value=lab or None)
    c.font = font(10, True, "FFFFFF"); c.fill = fill(NAVY); c.border = BOX
sk.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
r += 1
for i, (name, what, step) in enumerate(TOOLS, start=1):
    body_row(sk, r, [i, name, what, None, step], bold_cols=(2,))
    sk.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
    r += 1
r += 1
put(sk, f"A{r}", "D. Available but not used in the v0.4 run", size=11, bold=True, color=NAVY, wrap=False)
r += 1
for i, lab in enumerate(["#", "Skills", "Where they live", "Why not used"], start=1):
    c = sk.cell(row=r, column=i, value=lab)
    c.font = font(10, True, "FFFFFF"); c.fill = fill(NAVY); c.border = BOX
sk.merge_cells(start_row=r, start_column=4, end_row=r, end_column=7)
r += 1
for i, (names, where, why) in enumerate(NOT_USED, start=1):
    body_row(sk, r, [i, names, where, why], bold_cols=())
    sk.merge_cells(start_row=r, start_column=4, end_row=r, end_column=7)
    for col in range(1, 8):
        sk.cell(row=r, column=col).font = font(10, color=MUTED)
        sk.cell(row=r, column=col).border = BOX
    r += 1
sk.freeze_panes = "C6"
landscape(sk)

# Validation --------------------------------------------------------------------------------------------
va = wb.create_sheet("Validation")
title(va, "Validation results", "Latest run of every end-to-end check. Pass rate and Status are formulas: Pass when all pass, Pass (explained) when every miss is an explained exception.", 11)
VH = ["#", "Area", "Check", "What it proves", "Script", "Passed", "Total", "Explained exceptions", "Pass rate", "Status", "Note"]
header(va, 4, VH, [5, 13, 26, 42, 26, 10, 10, 13, 12, 17, 48])
r = 5
for i, (area, check, what, script, ok, tot, exp, note) in enumerate(VALIDATION, start=1):
    body_row(va, r, [i, area, check, what, script, ok, tot, exp, f"=IF(G{r}=0,0,F{r}/G{r})",
                     f'=IF(F{r}=G{r},"Pass",IF(F{r}+H{r}>=G{r},"Pass (explained)","Fail"))', note], bold_cols=(3,))
    for col in (6, 7, 8):
        va.cell(row=r, column=col).number_format = "#,##0"
        va.cell(row=r, column=col).font = font(10, color="0000FF")  # inputs: recorded results
        va.cell(row=r, column=col).alignment = Alignment(horizontal="right", vertical="top")
    va.cell(row=r, column=9).number_format = "0.0%"
    va.cell(row=r, column=9).alignment = Alignment(horizontal="right", vertical="top")
    r += 1
V_FIRST, V_LAST = 5, r - 1
put(va, f"C{r}", "Total", bold=True, border=True)
for col in "FGH":
    put(va, f"{col}{r}", f"=SUM({col}{V_FIRST}:{col}{V_LAST})", bold=True, border=True, fmt="#,##0", h="right")
put(va, f"I{r}", f"=IF(G{r}=0,0,F{r}/G{r})", bold=True, border=True, fmt="0.0%", h="right")
put(va, f"J{r}", f'=COUNTIF(J{V_FIRST}:J{V_LAST},"Pass*")&" of "&COUNTA(C{V_FIRST}:C{V_LAST})&" pass"', bold=True, border=True)
V_TOTAL = r
va.conditional_formatting.add(f"I{V_FIRST}:I{V_LAST}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="3A7D44"))
va.conditional_formatting.add(f"J{V_FIRST}:J{V_LAST}", CellIsRule(operator="equal", formula=['"Pass"'], fill=fill("DFEFE1"), font=Font(name=F, color="2F6B38", bold=True)))
va.conditional_formatting.add(f"J{V_FIRST}:J{V_LAST}", CellIsRule(operator="equal", formula=['"Pass (explained)"'], fill=fill("FFF1D6"), font=Font(name=F, color="8A5A00", bold=True)))
va.conditional_formatting.add(f"J{V_FIRST}:J{V_LAST}", CellIsRule(operator="equal", formula=['"Fail"'], fill=fill("FBE0DD"), font=Font(name=F, color="A1281D", bold=True)))
put(va, f"A{r + 1}", "Blue numbers are the recorded results of each script's last run (source: the script and its report in doc/queries or artifacts/rain-v4-validation).", size=9, color=MUTED, italic=True, wrap=False)
r += 3
put(va, f"A{r}", "Open gaps", size=11, bold=True, color=NAVY, wrap=False)
r += 1
for i, lab in enumerate(["#", "Type", "Gap", "Why", "", "What we use instead"], start=1):
    c = va.cell(row=r, column=i, value=lab or None)
    c.font = font(10, True, "FFFFFF"); c.fill = fill(NAVY); c.border = BOX
va.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
va.merge_cells(start_row=r, start_column=6, end_row=r, end_column=11)
r += 1
G_FIRST = r
for i, (typ, gap, why, instead) in enumerate(GAPS, start=1):
    body_row(va, r, [i, typ, gap, why, None, instead], bold_cols=(3,))
    va.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
    va.merge_cells(start_row=r, start_column=6, end_row=r, end_column=11)
    r += 1
G_LAST = r - 1
va.freeze_panes = "D5"
landscape(va)

# Runtime flow ------------------------------------------------------------------------------------------
rt = wb.create_sheet("Runtime Flow")
title(rt, "What happens at run time", "How a user action travels through the stack. Only Postgres is behind the APIs: no LLM, Neo4j or internet call at run time.", 7)
lanes = [("1  Browser\nReact app on :8184", "2E5A88"), ("2  nginx :8184\nforwards /api and /health", "6A4C93"),
         ("3  FastAPI rain-api :8003\n/api/v4/ui · /queries · /flow · /data", "B5651D"), ("4  Postgres rain_v4 :55436\nsynthetic · public_data · ui_v4", "1B7F79")]
for i, (txt, col) in enumerate(lanes):
    put(rt, f"{'ABCD'[i]}4", txt, size=11, bold=True, color="FFFFFF", bg=col, h="center", v="center")
    put(rt, f"{'ABCD'[i]}5", "➜  then" if i < 3 else "answers flow back the same way", size=9, bold=True, color=col, h="right" if i < 3 else "center", v="top", wrap=False)
rt.row_dimensions[4].height = 54
put(rt, "A6", "Neo4j KAG (:17477) is built offline by kag_v4_refresh.py and browsed by people; the app does not call it.", size=9, color=MUTED, italic=True, wrap=False)
RH = ["User action", "API call", "Backend module", "Reads / writes in rain_v4", "What the user sees", "Calls in the recorded run"]
r = 8
for i, lab in enumerate(RH, start=1):
    c = rt.cell(row=r, column=i, value=lab)
    c.font = font(10, True, "FFFFFF"); c.fill = fill(NAVY); c.border = BOX
    c.alignment = Alignment(wrap_text=True, vertical="center")
rt.row_dimensions[r].height = 30
for col, w in zip("ABCDEF", [34, 30, 30, 40, 34, 18]):
    rt.column_dimensions[col].width = w
r += 1
for row in RUNTIME:
    body_row(rt, r, list(row), bold_cols=(2,))
    rt.cell(row=r, column=2).font = Font(name="Consolas", size=10, bold=True, color=INK)
    r += 1
put(rt, f"A{r + 1}", "Recorded run: scripts/e2e/api_usage_v4.mjs on 2026-11-10, 14 personas, 175 backend calls, all 200 (artifacts/rain-v4-validation/api_usage.json; doc/RAIN_v4_backend_apis.md).", size=9, color=MUTED, italic=True, wrap=False)
landscape(rt)

# Stack -------------------------------------------------------------------------------------------------
sa = wb.create_sheet("Stack & URLs")
title(sa, "Stack and URLs", "Compose project rain4. Start: FRONTEND_PORT=8184 BACKEND_PORT=8003 PG_HOST_PORT=55436 NEO4J_HTTP_PORT=17477 NEO4J_BOLT_PORT=17690 docker compose -p rain4 up -d", 5)
header(sa, 4, ["Service", "URL", "Port", "Login", "What it is for"], [22, 52, 18, 26, 52])
r = 5
for row in STACK:
    body_row(sa, r, list(row), bold_cols=(1,))
    r += 1
landscape(sa)

# Overview (first sheet) --------------------------------------------------------------------------------
ov = wb.create_sheet("Overview", 0)
ov.sheet_view.showGridLines = False
ov.column_dimensions["A"].width = 2
for i in range(6):
    ov.column_dimensions["BDFHJL"[i]].width = 27
    if i < 5:
        ov.column_dimensions["CEGIK"[i]].width = 4
ov.column_dimensions["M"].width = 2
put(ov, "B2", "RAIN v0.4 · End-to-end steps and skills", size=20, bold=True, color=NAVY, wrap=False)
put(ov, "B3", "From the merged PRD to a running, validated stack: 12 phases in 5 stages. Details in E2E Steps, Skills, Validation, Runtime Flow and Stack & URLs.", size=10, color=MUTED, wrap=False)
# stage legend
c = 2
for sname, (strong, tint) in STAGE.items():
    put(ov, f"{'BDFHJ'[list(STAGE).index(sname)]}5", sname, size=9, bold=True, color="FFFFFF", bg=strong, h="center", v="center", wrap=False)
put(ov, "L5", "Stages", size=9, color=MUTED, h="left", v="center", wrap=False)


def phase_row(top, phases):
    """Stage band, header, body and skills rows for up to 6 phases starting at row `top`."""
    for i, no in enumerate(phases):
        col = "BDFHJL"[i]
        _, name, stage, out, tools = PH[no]
        strong, tint = STAGE[stage]
        put(ov, f"{col}{top}", stage, size=8, bold=True, color=strong, h="left", v="bottom", wrap=False)
        put(ov, f"{col}{top + 1}", f"{no}  {name}", size=11, bold=True, color="FFFFFF", bg=strong, h="left", v="center")
        put(ov, f"{col}{top + 2}", out, size=9, color=INK, bg=tint, h="left", v="top")
        put(ov, f"{col}{top + 3}", tools, size=8, color=strong, italic=True, bg=tint, h="left", v="top")
        if i < len(phases) - 1:
            put(ov, f"{'CEGIK'[i]}{top + 2}", "➜", size=16, bold=True, color=MUTED, h="center", v="center", wrap=False)
    ov.row_dimensions[top].height = 14
    ov.row_dimensions[top + 1].height = 30
    ov.row_dimensions[top + 2].height = 66
    ov.row_dimensions[top + 3].height = 30


phase_row(7, [1, 2, 3, 4, 5, 6])
put(ov, "L11", "▼  continues below", size=9, bold=True, color=MUTED, h="right", v="center", wrap=False)
phase_row(12, [7, 8, 9, 10, 11, 12])
put(ov, "B16", "▲ each box: what the phase produced (body) and the skills or tools that did it (italic)", size=8, color=MUTED, italic=True, wrap=False)

# key number tiles
put(ov, "B18", "Key numbers", size=13, bold=True, color=NAVY, wrap=False)
ST = "'E2E Steps'"
tiles = [
    (14, "personas in the UI, chat and KAG", "PRD v0.4; constants.PERSONAS", "0"),
    (f"=COUNTIF(Skills!H{DIF_FIRST}:H{DIF_LAST},\"Yes\")", "DIF factory skills run", "Skills sheet, part A", "0"),
    (59, "synthetic tables", "scripts/e2e/synth", "0"),
    (689000, "synthetic rows (about)", "gen_load.py row counts", '#,##0,"k"'),
    (24, "public data tables (NV, TN)", "public_data_v4.py", "0"),
    (140, "persona queries (5 + 5 each)", "rain_v4_persona_queries.sql", "0"),
    (2603, "KAG nodes in rain-v4.1.0", "kag_v4_refresh.py", "#,##0"),
    (10, "of 22 /api/v4 routes used by the UI", "api_usage_v4.mjs; OpenAPI", "0"),
    (f"=Validation!F{V_FIRST}", "backend tests pass", "Validation sheet", "0"),
    (f"=Validation!F{V_FIRST + 1}", "frontend tests pass", "Validation sheet", "0"),
    (f"=COUNTIF(Validation!J{V_FIRST}:J{V_LAST},\"Pass*\")", f"=\"of \"&COUNTA(Validation!C{V_FIRST}:C{V_LAST})&\" validation checks pass\"", "Validation sheet", "0"),
    (f"=COUNTIF(Validation!B{G_FIRST}:B{G_LAST},\"Blocked source\")", "public sources blocked (your action)", "Validation sheet, open gaps", "0"),
]
for k, (val, label, src, fmt) in enumerate(tiles):
    row0 = 19 if k < 6 else 23
    col = "BDFHJL"[k % 6]
    put(ov, f"{col}{row0}", val, size=22, bold=True, color=NAVY, bg=BAND, h="left", v="center", wrap=False, fmt=fmt)
    put(ov, f"{col}{row0 + 1}", label, size=9, bold=True, color=INK, bg=BAND, h="left", v="top")
    put(ov, f"{col}{row0 + 2}", f"Source: {src}", size=8, color=MUTED, italic=True, bg=BAND, h="left", v="top")
for rr in (19, 23):
    ov.row_dimensions[rr].height = 34
    ov.row_dimensions[rr + 1].height = 26
    ov.row_dimensions[rr + 2].height = 22

# skills-by-stage table (feeds chart 1)
put(ov, "B28", "DIF skills by factory stage", size=13, bold=True, color=NAVY, wrap=False)
put(ov, "B29", "Stage", size=10, bold=True, color="FFFFFF", bg=NAVY, border=True)
put(ov, "D29", "Skills", size=10, bold=True, color="FFFFFF", bg=NAVY, border=True)
for i, sname in enumerate(STAGE_ORDER):
    rr = 30 + i
    put(ov, f"B{rr}", sname, size=10, border=True, wrap=False)
    put(ov, f"D{rr}", f'=COUNTIF(Skills!D{DIF_FIRST}:D{DIF_LAST},B{rr})', size=10, border=True, h="right", fmt="0")
put(ov, f"B{30 + len(STAGE_ORDER)}", "Total", size=10, bold=True, border=True)
put(ov, f"D{30 + len(STAGE_ORDER)}", f"=SUM(D30:D{29 + len(STAGE_ORDER)})", size=10, bold=True, border=True, h="right", fmt="0")

ch1 = BarChart()
ch1.type = "bar"
ch1.style = 10
ch1.title = chart_title("DIF skills run, by factory stage")
ch1.add_data(Reference(ov, min_col=4, min_row=29, max_row=29 + len(STAGE_ORDER)), titles_from_data=True)
ch1.set_categories(Reference(ov, min_col=2, min_row=30, max_row=29 + len(STAGE_ORDER)))
ch1.x_axis.scaling.orientation = "maxMin"
ch1.x_axis.txPr = small_text(800)
ch1.y_axis.txPr = small_text(800)
ch1.y_axis.scaling.min = 0
ch1.y_axis.scaling.max = 7
ch1.y_axis.majorUnit = 1
ch1.y_axis.majorGridlines = None
ch1.x_axis.delete = False
ch1.y_axis.delete = False
ch1.legend = None
ch1.series[0].graphicalProperties.solidFill = "6A4C93"
ch1.series[0].graphicalProperties.line.solidFill = "6A4C93"
ch1.dataLabels = value_labels()
ch1.gapWidth = 50
ch1.height = 8.5
ch1.width = 11.5
ov.add_chart(ch1, "F28")

ch2 = BarChart()
ch2.type = "bar"
ch2.style = 10
ch2.title = chart_title("Validation: pass rate by check")
ch2.add_data(Reference(va, min_col=9, min_row=4, max_row=V_LAST), titles_from_data=True)
ch2.set_categories(Reference(va, min_col=3, min_row=V_FIRST, max_row=V_LAST))
ch2.x_axis.scaling.orientation = "maxMin"
ch2.x_axis.txPr = small_text(750)
ch2.y_axis.txPr = small_text(750)
ch2.y_axis.scaling.min = 0
ch2.y_axis.scaling.max = 1.15
ch2.y_axis.majorUnit = 0.25
ch2.y_axis.number_format = "0%"
ch2.y_axis.majorGridlines = None
ch2.x_axis.delete = False
ch2.y_axis.delete = False
ch2.legend = None
ch2.series[0].graphicalProperties.solidFill = "3A7D44"
ch2.series[0].graphicalProperties.line.solidFill = "3A7D44"
ch2.dataLabels = value_labels("0%")
ch2.gapWidth = 35
ch2.height = 13.5
ch2.width = 13.5
ov.add_chart(ch2, "J28")

put(ov, "B57", "How to read this workbook", size=13, bold=True, color=NAVY, wrap=False)
guide = [
    ("E2E Steps", "Every step by phase: what we did, input, output, DIF skills, scripts, Claude skill, check, result, status."),
    ("Skills", "The 24 DIF factory skills that ran (and their agents), the Claude skills, the project tools, and what was not used."),
    ("Validation", "Each check's latest result with pass rate and status formulas, and the open gaps."),
    ("Runtime Flow", "What each user action calls in the backend and what it reads or writes."),
    ("Stack & URLs", "Where each service runs and how to sign in."),
]
for i, (sheet, text) in enumerate(guide):
    put(ov, f"B{58 + i}", sheet, size=10, bold=True, color=NAVY, wrap=False)
    ov.merge_cells(start_row=58 + i, start_column=4, end_row=58 + i, end_column=12)
    put(ov, f"D{58 + i}", text, size=10, wrap=False)
ov.page_setup.orientation = "landscape"
ov.page_setup.fitToWidth = 1
ov.page_setup.fitToHeight = 0
ov.sheet_properties.pageSetUpPr.fitToPage = True
ov.sheet_properties.tabColor = NAVY
for ws, colr in ((st, "2E5A88"), (sk, "6A4C93"), (va, "3A7D44"), (rt, "B5651D"), (sa, "1B7F79")):
    ws.sheet_properties.tabColor = colr

wb.active = 0
wb.save(OUT)
print("saved", OUT, "| steps", len(step_rows), "| DIF skills", DIF_LAST - DIF_FIRST + 1, "| checks", V_LAST - V_FIRST + 1,
      "| agents cell", AGENTS_CELL, "| V rows", V_FIRST, V_LAST, "| gaps", G_FIRST, G_LAST)
