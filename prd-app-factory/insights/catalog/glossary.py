"""The glossary (business terms and metric definitions), table tags and join hints.

Both files are curated by a data steward. Nothing in them is trusted blindly: they are validated
against the catalog snapshot at load time, and their text is later treated as untrusted input when
it reaches a prompt (design report 5.2).
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from insights.catalog.snapshot import CatalogError, CatalogSnapshot
from insights.contracts.common import Contract, SqlIdentifier
from insights.yamlio import load_yaml


class TableTags(Contract):
    """Which domains, products and markets a table is relevant to. A missing key means all."""

    domain: tuple[str, ...] = ()
    product: tuple[str, ...] = ()
    market: tuple[str, ...] = ()


class GlossaryEntry(Contract):
    term: str = Field(min_length=2, max_length=80)
    kind: Literal["metric", "dimension", "term"] = "term"
    synonyms: tuple[str, ...] = ()
    definition: str = Field(min_length=3, max_length=600)
    maps_to: tuple[SqlIdentifier, ...] = ()
    """`table` or `table.column` the term refers to."""
    expression: str | None = Field(default=None, max_length=600)
    """For a metric: the SQL expression that defines it, shown to the query generator."""

    def phrases(self) -> tuple[str, ...]:
        return (self.term, *self.synonyms)


class Glossary(Contract):
    version: int = 1
    tables: dict[SqlIdentifier, TableTags] = Field(default_factory=dict)
    terms: tuple[GlossaryEntry, ...] = ()

    @model_validator(mode="after")
    def _terms_are_unique(self) -> "Glossary":
        seen: set[str] = set()
        for entry in self.terms:
            for phrase in entry.phrases():
                key = phrase.lower()
                if key in seen:
                    raise ValueError(f"the phrase {phrase!r} is used by more than one term")
                seen.add(key)
        return self


class JoinHint(Contract):
    left: SqlIdentifier
    """`table.column`."""
    right: SqlIdentifier
    note: str = ""


class JoinHints(Contract):
    version: int = 1
    joins: tuple[JoinHint, ...] = ()


def _load(path: Path, model: type, what: str):
    try:
        raw = load_yaml(path.read_text(encoding="utf-8")) or {}
        return model.model_validate(raw)
    except OSError as exc:
        raise CatalogError(f"cannot read the {what} {path}: {exc}") from exc
    except (ValidationError, ValueError, TypeError) as exc:
        raise CatalogError(f"invalid {what} {path}: {exc}") from exc


def load_glossary(path: Path) -> Glossary:
    return _load(path, Glossary, "glossary")


def load_join_hints(path: Path) -> JoinHints:
    return _load(path, JoinHints, "join hints")


def _exists(snapshot: CatalogSnapshot, ref: str) -> bool:
    table, _, column = ref.partition(".")
    found = snapshot.table(table)
    return found is not None and (not column or found.column(column) is not None)


def problems_against(snapshot: CatalogSnapshot, glossary: Glossary, hints: JoinHints) -> list[str]:
    """Everything in the curated files that points at something the catalog does not have."""
    problems: list[str] = []
    for table in glossary.tables:
        if snapshot.table(table) is None:
            problems.append(f"glossary tags name an unknown table: {table}")
    for entry in glossary.terms:
        problems += [
            f"glossary term {entry.term!r} maps to unknown {ref}"
            for ref in entry.maps_to
            if not _exists(snapshot, ref)
        ]
    for hint in hints.joins:
        for ref in (hint.left, hint.right):
            if "." not in ref or not _exists(snapshot, ref):
                problems.append(f"join hint names an unknown column: {ref}")
    return problems


def all_phrases(entries: Iterable[GlossaryEntry]) -> dict[str, GlossaryEntry]:
    return {phrase.lower(): entry for entry in entries for phrase in entry.phrases()}
