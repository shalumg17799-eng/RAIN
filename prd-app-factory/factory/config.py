"""Paths and settings shared by the factory. Everything reads the environment,
loaded from this project's .env (copy .env.example); nothing here is specific to one app."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
FACTORY_DIR = ROOT / "factory"
APPPACKS_DIR = ROOT / "apppacks"
SKILLS_DIR = FACTORY_DIR / "skills"

if (ROOT / ".env").is_file():
    load_dotenv(ROOT / ".env")

MODEL = os.environ.get("FACTORY_MODEL", "claude-opus-5-5")
MAX_TOKENS = int(os.environ.get("FACTORY_MAX_TOKENS", "64000"))


def pg_settings(dbname: str | None = None) -> dict:
    """Staging database for generated apps (one schema per app)."""
    return {
        "host": os.environ.get("FACTORY_PG_HOST") or os.environ.get("PG_HOST", "localhost"),
        "port": int(os.environ.get("FACTORY_PG_PORT") or os.environ.get("PG_PORT", "5432")),
        "dbname": dbname or os.environ.get("FACTORY_PG_DB", "factory"),
        "user": os.environ.get("FACTORY_PG_USER") or os.environ["PG_USER"],
        "password": os.environ.get("FACTORY_PG_PASSWORD") or os.environ["PG_PASSWORD"],
    }


def neo4j_settings() -> dict:
    return {
        "uri": os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687"),
        "user": os.environ.get("NEO4J_USER", "neo4j"),
        "password": os.environ.get("NEO4J_PASSWORD", ""),
    }


def schema_for(app_id: str) -> str:
    return f"app_{app_id}"
