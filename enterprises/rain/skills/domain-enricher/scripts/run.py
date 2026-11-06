"""Rain override of domain-enricher: shared scoring, Rain taxonomy by default (see SKILL.md)."""
import importlib.util
from pathlib import Path

import yaml

from dif.config import settings

ENTERPRISE_DIR = Path(__file__).resolve().parents[3]           # enterprises/rain
TAXONOMY_FILE = ENTERPRISE_DIR / "config" / "taxonomy.yaml"
SHARED_SCRIPT = settings.skills_dir / "domain-enricher" / "scripts" / "run.py"


def _shared():
    spec = importlib.util.spec_from_file_location("skill_domain_enricher__shared_for_rain", SHARED_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SHARED = _shared()


def load_rain_taxonomy():
    if not TAXONOMY_FILE.exists():
        raise ValueError(f"Rain taxonomy missing: {TAXONOMY_FILE}")
    return yaml.safe_load(TAXONOMY_FILE.read_text())


def run(inp, ctx):
    taxonomy = inp.get("taxonomy") or load_rain_taxonomy()
    return _SHARED.run({**inp, "taxonomy": taxonomy}, ctx)
