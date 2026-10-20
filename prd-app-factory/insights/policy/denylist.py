"""Per-dialect denylist, loaded from `policy/denylists/<dialect>.yaml`."""

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from insights.yamlio import load_yaml

DENYLIST_DIR = Path(__file__).resolve().parent / "denylists"


class DenylistError(ValueError):
    """The denylist file is missing or invalid. Policy cannot run without it (fail closed)."""


class _File(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dialect: str
    version: int
    functions: tuple[str, ...]
    allow_anonymous_functions: tuple[str, ...] = ()
    allow_table_functions: tuple[str, ...] = ()
    bare_identifiers: tuple[str, ...] = ()
    schemas: tuple[str, ...]
    schema_prefixes: tuple[str, ...] = ()
    nodes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Denylist:
    dialect: str
    version: int
    functions: tuple[str, ...]
    allow_anonymous_functions: frozenset[str]
    allow_table_functions: frozenset[str]
    bare_identifiers: frozenset[str]
    schemas: frozenset[str]
    schema_prefixes: tuple[str, ...]
    nodes: frozenset[str]

    def function_denied(self, name: str) -> str | None:
        """The glob that refuses this function name, or None."""
        lowered = name.lower()
        return next((p for p in self.functions if fnmatchcase(lowered, p.lower())), None)

    def table_function_allowed(self, *names: str) -> bool:
        return any(n.lower() in self.allow_table_functions for n in names)

    def anonymous_function_allowed(self, name: str) -> bool:
        return name.lower() in self.allow_anonymous_functions

    def schema_denied(self, name: str) -> bool:
        lowered = name.lower()
        return lowered in self.schemas or lowered.startswith(self.schema_prefixes)


def load_denylist(dialect: str, directory: Path = DENYLIST_DIR) -> Denylist:
    path = directory / f"{dialect}.yaml"
    try:
        raw = load_yaml(path.read_text(encoding="utf-8"))
        data = _File.model_validate(raw)
    except (OSError, ValidationError, TypeError) as exc:
        raise DenylistError(f"denylist for {dialect!r} is missing or invalid: {path.name}") from exc
    if data.dialect != dialect:
        raise DenylistError(f"{path.name} is for dialect {data.dialect!r}, not {dialect!r}")
    return Denylist(
        dialect=data.dialect,
        version=data.version,
        functions=data.functions,
        allow_anonymous_functions=frozenset(f.lower() for f in data.allow_anonymous_functions),
        allow_table_functions=frozenset(f.lower() for f in data.allow_table_functions),
        bare_identifiers=frozenset(b.lower() for b in data.bare_identifiers),
        schemas=frozenset(s.lower() for s in data.schemas),
        schema_prefixes=tuple(p.lower() for p in data.schema_prefixes),
        nodes=frozenset(data.nodes),
    )
