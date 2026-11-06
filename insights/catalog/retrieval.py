"""Schema retrieval, "bypass" path: from a question to the few tables that matter.

Order of work (design report 5.2):
  1. ENTITLEMENT FILTER FIRST. Everything below sees only tables and columns the caller's role may
     query. Index statistics and embeddings are built from those alone, so a table the caller may
     not see cannot influence a ranking, a score or a coverage number, let alone appear in output.
  2. Narrow by the request's market, product and domain, using the glossary's table tags.
  3. Rank tables: BM25 over names, comments and glossary phrases, blended with an embedding
     similarity (pluggable; a deterministic fake in tests), plus a boost for matched glossary terms.
  4. Join expansion: connect the chosen tables over declared foreign keys and curated join hints,
     within a hop limit, adding only the bridge tables needed.
  5. Columns, joins, glossary terms and a coverage score: the share of the question's concepts the
     sliver can speak to.
"""

import threading
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from insights.catalog.bm25 import BM25Index
from insights.catalog.catalog import Catalog
from insights.catalog.embedding import Embedder, HashingEmbedder, cosine
from insights.catalog.entitlements import (
    AllowedObjects,
    allowed_objects,
    default_schema_of,
    effective_role,
    normalize_table,
)
from insights.catalog.glossary import GlossaryEntry
from insights.catalog.snapshot import CatalogTable
from insights.catalog.text import content_tokens, stems
from insights.contracts.enums import PathName
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile
from insights.contracts.request import AskContext
from insights.contracts.response import Provenance
from insights.contracts.state import (
    GlossaryTerm,
    Sliver,
    SliverColumn,
    SliverJoin,
    SliverTable,
)

ALPHA = 0.6
"""Weight of BM25 against embedding similarity in the table ranking."""
GLOSSARY_BOOST = 0.5
MIN_RELATIVE_SCORE = 0.25


@dataclass(frozen=True)
class RetrievalResult:
    tables: tuple[SliverTable, ...]
    joins: tuple[SliverJoin, ...]
    glossary_terms: tuple[GlossaryTerm, ...]
    coverage: float
    unmatched: tuple[str, ...]
    """Concepts in the question the sliver cannot speak to (stemmed). Drives the critique."""
    catalog_version: str
    notes: tuple[str, ...] = ()
    path_used: PathName = PathName.BYPASS
    provenance: tuple[Provenance, ...] = field(default=())

    def to_sliver(self) -> Sliver:
        return Sliver(
            tables=self.tables,
            joins=self.joins,
            glossary_terms=self.glossary_terms,
            coverage=self.coverage,
            path_used=self.path_used,
            catalog_version=self.catalog_version,
            provenance=self.provenance,
        )


@dataclass
class _RoleView:
    """Everything one role may see, indexed. Built once per role and reused."""

    allowed: AllowedObjects
    tables: dict[str, CatalogTable]
    """Entitled tables with only their entitled columns."""
    terms: list[GlossaryEntry]
    """Glossary entries that still refer to something visible."""
    visible_refs: dict[str, tuple[str, ...]]
    """Per term: the `table` / `table.column` references that remain visible."""
    bm25: BM25Index
    vectors: dict[str, list[float]]
    vocabulary: dict[str, set[str]]
    """Per table: every stem a question concept can match."""


class BypassRetriever:
    def __init__(
        self,
        catalog: Catalog,
        app: AppProfile,
        embedder: Embedder | None = None,
        *,
        top_k: int = 3,
        hop_limit: int = 2,
        max_tables: int = 6,
        max_columns: int = 30,
    ) -> None:
        self._catalog = catalog
        self._app = app
        self._embedder = embedder or HashingEmbedder()
        self._top_k, self._hops, self._max_tables, self._max_columns = (
            top_k,
            hop_limit,
            max_tables,
            max_columns,
        )
        self._views: dict[str, _RoleView] = {}
        self._lock = threading.Lock()

    # ---- the entitled view ----------------------------------------------------------------------

    def _view(self, principal: Principal) -> _RoleView | None:
        role = effective_role(principal, self._app)
        if role is None:
            return None
        with self._lock:
            if role not in self._views:
                self._views[role] = self._build_view(principal)
            return self._views[role]

    def _build_view(self, principal: Principal) -> _RoleView:
        snapshot = self._catalog.snapshot
        sliver_like = [
            SliverTable(
                source_id=snapshot.source_id,
                name=t.name,
                columns=tuple(SliverColumn(name=c.name, type=c.type) for c in t.columns),
            )
            for t in snapshot.tables
        ]
        allowed = allowed_objects(sliver_like, self._app, principal)
        schema = default_schema_of(self._app)
        tables: dict[str, CatalogTable] = {}
        for table in snapshot.tables:
            # allowed tables and columns are keyed by their normalized (lowercased) names,
            # while the snapshot keeps the database's own casing (e.g. "PregnancyEpisode")
            columns = allowed.columns_of(normalize_table(table.name, schema))
            if columns:
                kept = tuple(c for c in table.columns if c.name.lower() in columns)
                tables[table.name] = table.model_copy(
                    update={
                        "columns": kept,
                        "freshness": {c: v for c, v in table.freshness.items() if c in columns},
                        "foreign_keys": tuple(
                            fk for fk in table.foreign_keys if all(c in columns for c in fk.columns)
                        ),
                    }
                )

        terms: list[GlossaryEntry] = []
        visible_refs: dict[str, tuple[str, ...]] = {}
        for entry in self._catalog.glossary.terms:
            refs = tuple(ref for ref in entry.maps_to if self._ref_visible(ref, tables))
            if entry.maps_to and not refs:
                continue  # it points only at things this role cannot see: it does not exist here
            terms.append(entry)
            visible_refs[entry.term] = refs

        phrases: dict[str, list[str]] = {name: [] for name in tables}
        for entry in terms:
            for ref in visible_refs[entry.term]:
                phrases[ref.partition(".")[0]].extend(entry.phrases())

        documents: dict[str, list[str]] = {}
        texts: dict[str, str] = {}
        vocabulary: dict[str, set[str]] = {}
        for name, table in tables.items():
            parts = [name, name, table.description]
            for column in table.columns:
                parts += [column.name, column.description]
            parts += phrases[name]
            text = " ".join(p for p in parts if p)
            texts[name] = text
            documents[name] = stems(text)
            vocabulary[name] = set(documents[name])
        names = list(tables)
        vectors = (
            dict(zip(names, self._embedder.embed([texts[n] for n in names]), strict=True))
            if names
            else {}
        )
        return _RoleView(
            allowed, tables, terms, visible_refs, BM25Index(documents), vectors, vocabulary
        )

    @staticmethod
    def _ref_visible(ref: str, tables: dict[str, CatalogTable]) -> bool:
        table, _, column = ref.partition(".")
        found = tables.get(table)
        return found is not None and (not column or found.column(column) is not None)

    def vocabulary(self, principal: Principal) -> frozenset[str]:
        """Every stem a question can match for this caller (entitled names, comments, glossary)."""
        view = self._view(principal)
        if view is None:
            return frozenset()
        words: set[str] = set()
        for table_words in view.vocabulary.values():
            words |= table_words
        return frozenset(words)

    # ---- retrieval ------------------------------------------------------------------------------

    def retrieve(
        self,
        question: str,
        principal: Principal,
        context: AskContext | None = None,
        *,
        widen: int = 0,
    ) -> RetrievalResult:
        view = self._view(principal)
        version = self._catalog.version
        if view is None or not view.tables:
            return RetrievalResult(
                (), (), (), 0.0, tuple(content_tokens(question)), version, ("no_access",)
            )

        notes: list[str] = []
        q_stems = stems(question)
        matched_terms = self._match_terms(q_stems, view)

        candidates = self._narrow(view, context, notes)
        scores = self._rank(question, q_stems, view, candidates, matched_terms)
        best = max(scores.values(), default=0.0)
        seeds = [
            name
            for name, score in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
            if score > 0 and score >= best * MIN_RELATIVE_SCORE
        ][: self._top_k + 2 * widen]

        graph = self._graph(view)
        included = self._connect(seeds, graph, self._hops + widen)
        if widen:
            for seed in list(included):
                for neighbour in sorted(graph.get(seed, ())):
                    included.setdefault(neighbour, None)
        order = sorted(included, key=lambda n: (-scores.get(n, 0.0), n))
        order = order[: self._max_tables + widen]

        tables = tuple(
            self._sliver_table(view, name, q_stems, matched_terms, scores) for name in order
        )
        joins = self._joins(view, set(order))
        glossary_terms = tuple(
            GlossaryTerm(
                term=entry.term,
                definition=entry.definition
                + (f" Defined as: {entry.expression}" if entry.expression else ""),
                maps_to=tuple(
                    r for r in view.visible_refs[entry.term] if r.partition(".")[0] in order
                ),
            )
            for entry in matched_terms
            if any(r.partition(".")[0] in order for r in view.visible_refs[entry.term])
            or not view.visible_refs[entry.term]
        )
        coverage, unmatched = self._coverage(question, view, order, matched_terms)
        return RetrievalResult(
            tables=tables,
            joins=joins,
            glossary_terms=glossary_terms,
            coverage=coverage,
            unmatched=unmatched,
            catalog_version=version,
            notes=tuple(notes),
            provenance=tuple(
                Provenance(
                    table=name,
                    source=self._catalog.snapshot.source_id,
                    freshness=view.tables[name].latest(),
                )
                for name in order
            ),
        )

    # ---- steps ----------------------------------------------------------------------------------

    @staticmethod
    def _match_terms(q_stems: list[str], view: _RoleView) -> list[GlossaryEntry]:
        matched = []
        for entry in view.terms:
            for phrase in entry.phrases():
                words = stems(phrase)
                n = len(words)
                if n and any(q_stems[i : i + n] == words for i in range(len(q_stems) - n + 1)):
                    matched.append(entry)
                    break
        return matched

    def _narrow(self, view: _RoleView, context: AskContext | None, notes: list[str]) -> set[str]:
        names = set(view.tables)
        if context is None:
            return names
        tags = self._catalog.glossary.tables
        keep = set(names)
        for dimension in ("market", "product", "domain"):
            requested = getattr(context, dimension)
            if not requested:
                continue
            wanted = set(stems(requested))
            for name in list(keep):
                declared = getattr(tags.get(name), dimension, ()) if name in tags else ()
                if declared and not any(set(stems(tag)) & wanted for tag in declared):
                    keep.discard(name)
        if not keep:
            notes.append("narrowing_skipped")  # relevance only, not security: do not return nothing
            return names
        if keep != names:
            notes.append("narrowed_by_context")
        return keep

    def _rank(
        self,
        question: str,
        q_stems: list[str],
        view: _RoleView,
        candidates: set[str],
        matched_terms: list[GlossaryEntry],
    ) -> dict[str, float]:
        bm25 = {k: v for k, v in view.bm25.score(q_stems).items() if k in candidates}
        top_bm25 = max(bm25.values(), default=0.0) or 1.0
        query_vector = self._embedder.embed([question])[0]
        cos = {k: max(0.0, cosine(query_vector, view.vectors[k])) for k in candidates}
        top_cos = max(cos.values(), default=0.0) or 1.0
        boosted: dict[str, float] = {}
        for entry in matched_terms:
            for ref in view.visible_refs[entry.term]:
                name = ref.partition(".")[0]
                boosted[name] = min(1.0, boosted.get(name, 0.0) + GLOSSARY_BOOST)
        return {
            name: ALPHA * (bm25.get(name, 0.0) / top_bm25)
            + (1 - ALPHA) * (cos[name] / top_cos)
            + boosted.get(name, 0.0)
            for name in candidates
            if bm25.get(name, 0.0) > 0 or boosted.get(name, 0.0) > 0
        }

    def _graph(self, view: _RoleView) -> dict[str, set[str]]:
        """Undirected join graph over entitled tables: declared foreign keys plus join hints."""
        graph: dict[str, set[str]] = {name: set() for name in view.tables}

        def link(a: str, b: str) -> None:
            if a in graph and b in graph and a != b:
                graph[a].add(b)
                graph[b].add(a)

        for table in view.tables.values():
            for fk in table.foreign_keys:
                link(table.name, fk.ref_table)
        for hint in self._catalog.hints.joins:
            left, right = hint.left.partition(".")[0], hint.right.partition(".")[0]
            if self._ref_visible(hint.left, view.tables) and self._ref_visible(
                hint.right, view.tables
            ):
                link(left, right)
        return graph

    @staticmethod
    def _connect(
        seeds: Sequence[str], graph: dict[str, set[str]], hop_limit: int
    ) -> dict[str, None]:
        """Chosen tables plus the bridge tables that join them, within `hop_limit` edges."""
        included: dict[str, None] = {}
        for seed in seeds:
            if not included:
                included[seed] = None
                continue
            path = BypassRetriever._shortest_path(seed, set(included), graph, hop_limit)
            for node in path:
                included.setdefault(node, None)
            included.setdefault(seed, None)
        return included

    @staticmethod
    def _shortest_path(
        start: str, targets: set[str], graph: dict[str, set[str]], hop_limit: int
    ) -> list[str]:
        if start in targets:
            return []
        queue = deque([(start, [start])])
        seen = {start}
        while queue:
            node, path = queue.popleft()
            if len(path) - 1 >= hop_limit:
                continue
            for neighbour in sorted(graph.get(node, ())):
                if neighbour in seen:
                    continue
                if neighbour in targets:
                    return path
                seen.add(neighbour)
                queue.append((neighbour, [*path, neighbour]))
        return []

    def _joins(self, view: _RoleView, names: set[str]) -> tuple[SliverJoin, ...]:
        joins: dict[tuple[str, str], SliverJoin] = {}
        for name in sorted(names):
            for fk in view.tables[name].foreign_keys:
                if fk.ref_table in names:
                    for col, ref_col in zip(fk.columns, fk.ref_columns, strict=True):
                        left, right = f"{name}.{col}", f"{fk.ref_table}.{ref_col}"
                        joins[(left, right)] = SliverJoin(left=left, right=right, kind="declared")
        for hint in self._catalog.hints.joins:
            lt, rt = hint.left.partition(".")[0], hint.right.partition(".")[0]
            if (
                lt in names
                and rt in names
                and self._ref_visible(hint.left, view.tables)
                and (self._ref_visible(hint.right, view.tables))
            ):
                joins.setdefault(
                    (hint.left, hint.right),
                    SliverJoin(left=hint.left, right=hint.right, kind="hint"),
                )
        return tuple(joins.values())

    def _sliver_table(
        self,
        view: _RoleView,
        name: str,
        q_stems: list[str],
        matched_terms: list[GlossaryEntry],
        scores: dict[str, float],
    ) -> SliverTable:
        table = view.tables[name]
        columns = list(table.columns)
        if len(columns) > self._max_columns:
            wanted = set(q_stems)
            for entry in matched_terms:
                for ref in view.visible_refs[entry.term]:
                    if ref.startswith(f"{name}."):
                        wanted.update(stems(ref.partition(".")[2]))
            keys = {c.name for c in columns if c.primary_key} | {
                c for fk in table.foreign_keys for c in fk.columns
            }

            def relevance(column) -> int:
                hit = set(stems(f"{column.name} {column.description}")) & wanted
                return (2 if column.name in keys else 0) + len(hit)

            ranked = sorted(columns, key=lambda c: (-relevance(c), columns.index(c)))
            keep = {c.name for c in ranked[: self._max_columns]}
            columns = [c for c in columns if c.name in keep]
        kept = {c.name for c in columns}
        return SliverTable(
            source_id=self._catalog.snapshot.source_id,
            name=name,
            description=table.description,
            columns=tuple(
                SliverColumn(name=c.name, type=c.type, description=c.description) for c in columns
            ),
            score=round(scores.get(name, 0.0), 4),
            freshness={c: v for c, v in table.freshness.items() if c in kept},
        )

    @staticmethod
    def _coverage(
        question: str, view: _RoleView, names: list[str], matched_terms: list[GlossaryEntry]
    ) -> tuple[float, tuple[str, ...]]:
        concepts = list(dict.fromkeys(content_tokens(question)))
        if not concepts:
            return 0.0, ()
        vocabulary: set[str] = set()
        for name in names:
            vocabulary |= view.vocabulary[name]
        for entry in matched_terms:
            if any(r.partition(".")[0] in names for r in view.visible_refs[entry.term]):
                for phrase in entry.phrases():
                    vocabulary.update(stems(phrase))
        unmatched = tuple(c for c in concepts if c not in vocabulary)
        return round(1 - len(unmatched) / len(concepts), 4), unmatched
