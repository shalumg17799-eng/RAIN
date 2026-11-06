"""Load an app's catalog (snapshot, glossary, join hints), cross-checked with the profile."""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from insights.catalog.examples import ReviewedExample, load_examples
from insights.catalog.glossary import (
    Glossary,
    JoinHints,
    load_glossary,
    load_join_hints,
    problems_against,
)
from insights.catalog.snapshot import CatalogError, CatalogSnapshot, load_snapshot
from insights.catalog.text import stems
from insights.contracts.profile import AppProfile


@dataclass(frozen=True)
class Catalog:
    snapshot: CatalogSnapshot
    glossary: Glossary
    hints: JoinHints
    examples: tuple[ReviewedExample, ...] = ()

    @classmethod
    def load(cls, app_dir: Path, app: AppProfile) -> "Catalog":
        """Read the three files named by the profile. Any inconsistency is an error, all listed."""
        snapshot = load_snapshot(app_dir / app.catalog.path)
        glossary = load_glossary(app_dir / app.glossary_path)
        hints = (
            load_join_hints(app_dir / app.join_hints_path) if app.join_hints_path else JoinHints()
        )
        problems = problems_against(snapshot, glossary, hints)
        if snapshot.dialect is not app.dialect:
            problems.append(
                f"snapshot dialect {snapshot.dialect.value} differs from the app's "
                f"{app.dialect.value}"
            )
        if snapshot.source_id not in {s.id for s in app.datasources}:
            problems.append(
                f"snapshot source {snapshot.source_id!r} is not a data source of the app"
            )
        if problems:
            raise CatalogError("; ".join(problems))
        examples = load_examples(app_dir / app.examples_path, snapshot) if app.examples_path else ()
        return cls(snapshot, glossary, hints, examples)

    @property
    def version(self) -> str:
        return self.snapshot.version

    @cached_property
    def vocabulary(self) -> frozenset[str]:
        """Every stem the whole catalog can speak to, across all roles.

        For intent classification only (is this a data question?), so that the router answers
        the same way for every caller and a status never reveals what a role may not see.
        Retrieval itself uses the entitled, per-role vocabulary, never this one.
        """
        words: set[str] = set()
        for table in self.snapshot.tables:
            words.update(stems(f"{table.name} {table.description}"))
            for column in table.columns:
                words.update(stems(f"{column.name} {column.description}"))
        for entry in self.glossary.terms:
            for phrase in entry.phrases():
                words.update(stems(phrase))
        return frozenset(words)
