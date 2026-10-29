"""Configuration-driven settings. Swap env vars to move OSS -> Azure (see docs/azure-migration.md)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _dirs(env, default):
    raw = os.getenv(env)
    return [Path(p) for p in raw.split(os.pathsep) if p] if raw else default


class Settings:
    database_url = os.getenv("DIF_DATABASE_URL", f"sqlite:///{ROOT}/dif.db")
    skills_dir = Path(os.getenv("DIF_SKILLS_DIR", ROOT / "dif-skills"))  # "skills/" belongs to the RAIN insights packs in this repo
    # Layered skill directories: later directories override earlier ones for the same skill name/version (and
    # enterprise-specific overrides live under enterprises/<id>/skills). DIF_SKILLS_DIRS is os.pathsep separated.
    skills_dirs = _dirs("DIF_SKILLS_DIRS", [skills_dir, ROOT / "skills-factory", *sorted(ROOT.glob("enterprises/*/skills"))])
    agents_dir = Path(os.getenv("DIF_AGENTS_DIR", ROOT / "agents"))
    contracts_dir = Path(os.getenv("DIF_CONTRACTS_DIR", ROOT / "contracts"))
    platform_dir = Path(os.getenv("DIF_PLATFORM_DIR", ROOT / "platform"))   # governed platform assets (upper ontology)
    schema_catalog_dir = Path(os.getenv("DIF_SCHEMA_CATALOG", ROOT / "samples" / "schemas"))
    artifact_store = os.getenv("DIF_ARTIFACT_STORE", f"file://{ROOT}/.data/artifacts")  # fsspec url: file://, az://, s3://, gs://
    llm_provider = os.getenv("DIF_LLM_PROVIDER", "none")  # none | ollama | azure_openai
    orchestrator = os.getenv("DIF_ORCHESTRATOR", "local")  # local (in-process threads) | temporal (durable workflows)
    local_workers = int(os.getenv("DIF_LOCAL_WORKERS", "4"))
    temporal_address = os.getenv("DIF_TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = os.getenv("DIF_TEMPORAL_NAMESPACE", "default")
    temporal_task_queue = os.getenv("DIF_TEMPORAL_TASK_QUEUE", "dif-runs")
    temporal_tls = os.getenv("DIF_TEMPORAL_TLS", "false").lower() in ("1", "true", "yes")
    temporal_api_key = os.getenv("DIF_TEMPORAL_API_KEY", "")  # Temporal Cloud
    worker_concurrency = int(os.getenv("DIF_WORKER_CONCURRENCY", "4"))
    api_keys = os.getenv("DIF_API_KEYS", "")  # "key:name:role[:enterprise],..."; role user|approver|admin; empty => auth disabled (dev only)
    stale_seconds = int(os.getenv("DIF_STALE_SECONDS", "300"))
    neo4j_uri = os.getenv("DIF_NEO4J_URI", "")
    neo4j_user = os.getenv("DIF_NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("DIF_NEO4J_PASSWORD", "")
    log_level = os.getenv("DIF_LOG_LEVEL", "INFO")


settings = Settings()
