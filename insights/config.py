"""Configuration helpers: read `.env`, resolve secrets by reference.

Nothing here mutates `os.environ`. A secret reference (`{env: NAME}` in an app profile) resolves
to a value only when a connection is made; a missing one is reported by name, never by value.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from insights.contracts.common import SecretRef


class SecretMissingError(LookupError):
    """A secret reference points at an environment variable that is not set."""


def load_dotenv(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines. Comments and blank lines are skipped; quotes are stripped."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def environment(dotenv_path: Path | None = None) -> dict[str, str]:
    """The process environment, with values from `.env` filling gaps. The real environment wins."""
    merged = load_dotenv(dotenv_path) if dotenv_path else {}
    merged.update(os.environ)
    return merged


def resolve_secret(ref: SecretRef, environ: Mapping[str, str]) -> str:
    value = environ.get(ref.env)
    if not value:
        raise SecretMissingError(f"environment variable {ref.env} is not set")
    return value
