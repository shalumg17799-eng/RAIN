# PRD Artifact Pipeline

Run from the repository root:

```powershell
python -m insights.prd.pipeline --input "doc/RAIN_Prototype_Spec_v1.docx" --output "artifacts/rain-prd"
```

The command uses the configured `INSIGHTS_LLM_PROVIDER` and `INSIGHTS_LLM_MODEL` from the root `.env` or `rain-api/.env`. It sends the PRD text and schema headers to that provider. Do not run it on confidential documents unless that transfer is approved.

The pipeline writes a requirements IR, persona question registry, entity model, lower ontology, upper ontology, and table/column and ontology audits. It preserves the existing ontology only when `--existing-upper` points to an exported JSON snapshot. It never writes to Neo4j, executes generated scenario SQL, or creates application source code.

Scenario design is skipped unless `--scenario-db-state` is provided with a generated database-state description. Never point that option at production row data.

The RAIN PRD and existing schemas can be compared without a model call using the helpers in `insights.prd.pipeline`; a full pipeline run makes one model call for each design stage.