"""The KAG retrieval path: a READ-ONLY client over the external Neo4j knowledge graph.

The graph (database `nfcukag`, loaded by the owner from the provided ontology) holds Concepts
(business terms with synonyms and definitions), Entities (tables), Attributes (columns) and the
MAPS_TO / HAS_ATTRIBUTE / REFERENCES edges. `Neo4jKag.retrieve` matches the question's words to
concepts, follows MAPS_TO to tables, and builds a sliver -- exactly the shape the bypass path
returns, so `retrieve_with_fallback` treats them the same.

Three rules hold here:
- READ ONLY. Every query runs with READ routing; the client never writes, and never loads data.
- ENTITLEMENT FIRST. Tables are filtered to the caller's role in the app profile. The graph's own
  `personas` links are hints for the Data Factory, never the access authority.
- Never raise to the caller. `available()` and `retrieve` fail soft so probe-and-fall-back can pick
  the bypass path; connection problems degrade to "KAG unavailable", not a crashed run.

Neo4j is reached through a `GraphReader` seam, so the retrieval and entitlement logic is unit-tested
against an in-memory fake graph with no network; the real reader is covered by a credentials-gated
integration test.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, SecretStr

from insights.catalog.entitlements import allowed_objects, effective_role, role_tables
from insights.catalog.retrieval import RetrievalResult
from insights.catalog.text import content_tokens, stems
from insights.contracts.enums import PathName
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile
from insights.contracts.request import AskContext
from insights.contracts.response import Provenance
from insights.contracts.state import GlossaryTerm, SliverColumn, SliverJoin, SliverTable

CATALOG_VERSION = "nfcukag"
MAX_SYNONYM_WORDS = 6
CYPHER_LIMIT_CAP = 200
"""Hard row cap enforced on any model-written Cypher before it runs."""
"""A matched phrase of more than this many words is ignored: it is a sentence, not a term."""


# ---- the graph, read through a seam ----------------------------------------------------------


@dataclass(frozen=True)
class ConceptRow:
    name: str
    synonyms: tuple[str, ...]
    definition: str
    tables: tuple[str, ...]
    """Bare table names this concept MAPS_TO."""


@dataclass(frozen=True)
class ColumnRow:
    table: str
    name: str
    type: str
    position: int
    primary_key: bool


@dataclass(frozen=True)
class JoinRow:
    left_table: str
    left_column: str
    right_table: str
    right_column: str


class GraphReader(Protocol):
    def ping(self) -> bool: ...

    def concepts(self) -> list[ConceptRow]: ...

    def columns(self, tables: Sequence[str]) -> list[ColumnRow]: ...

    def joins(self, tables: Sequence[str]) -> list[JoinRow]: ...

    def entity_tables(self) -> list[str]: ...

    def labels(self) -> list[str]: ...

    def rel_types(self) -> list[str]: ...

    def node_properties(self, label: str) -> list[str]: ...

    def run_read(self, cypher: str, limit: int) -> list[Mapping[str, Any]]: ...


# ---- configuration ---------------------------------------------------------------------------


class KagConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    uri: str | None = None
    user: str | None = None
    password: SecretStr | None = None
    database: str = "nfcukag"

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> KagConfig:
        def get(name: str) -> str | None:
            value = environ.get(f"INSIGHTS_KAG_{name}", "").strip()
            return value or None

        return cls(
            uri=get("URI"),
            user=get("USER"),
            password=SecretStr(get("PASSWORD")) if get("PASSWORD") else None,
            database=get("DATABASE") or "nfcukag",
        )

    @property
    def configured(self) -> bool:
        return bool(self.uri)


# ---- the KAG ---------------------------------------------------------------------------------


class Neo4jKag:
    """One app's view of the graph. Bound to the app so retrieval can enforce entitlements."""

    def __init__(self, reader: GraphReader, app: AppProfile, *, partial_match: bool = True) -> None:
        self._reader = reader
        self._app = app
        self._partial = partial_match

    def available(self) -> bool:
        try:
            return self._reader.ping()
        except Exception:
            return False

    def retrieve(
        self,
        question: str,
        principal: Principal,
        context: AskContext | None,
        *,
        widen: int = 0,
    ) -> RetrievalResult:
        role = effective_role(principal, self._app)
        concepts_in_q = list(dict.fromkeys(content_tokens(question)))
        if role is None or not concepts_in_q:
            return self._empty(concepts_in_q)
        matched = self._match_concepts(question)
        # ENTITLEMENT FIRST: keep only tables this role may see (profile, not the graph's personas)
        entitled = set(role_tables(self._app, role))
        wanted = sorted({t for _, ts in matched for t in ts} & entitled)
        if not wanted:
            return self._empty(concepts_in_q)
        return self._assemble(wanted, matched, question, principal, ("kag:neo4j",))

    def _match_concepts(self, question: str) -> list[tuple[ConceptRow, set[str]]]:
        """Concepts whose name or a synonym appears in the question, with the tables they map to."""
        q_stems = set(stems(question))
        matched: list[tuple[ConceptRow, set[str]]] = []
        for c in self._reader.concepts():
            hit_tables: set[str] = set()
            for phrase in (c.name, *c.synonyms):
                ps = set(stems(phrase))
                if not ps or len(ps) > MAX_SYNONYM_WORDS:
                    continue
                full = ps <= q_stems
                # partial: at least half of a multi-word phrase's words appear (e.g. "service
                # level" on "service"); single-word phrases still need the full (exact) match.
                partial = self._partial and len(ps) >= 2 and len(ps & q_stems) / len(ps) >= 0.5
                if full or partial:
                    hit_tables.update(c.tables)
            if hit_tables:
                matched.append((c, hit_tables))
        return matched

    def _assemble(
        self,
        wanted: Sequence[str],
        matched: list[tuple[ConceptRow, set[str]]],
        question: str,
        principal: Principal,
        notes: tuple[str, ...],
    ) -> RetrievalResult:
        tables = self._build_tables(wanted, principal)
        kept = {t.name for t in tables}
        joins = self._build_joins(kept)
        glossary_terms = tuple(
            GlossaryTerm(
                term=c.name,
                definition=c.definition or c.name,
                maps_to=tuple(sorted(set(ts) & kept)),
            )
            for c, ts in matched
            if set(ts) & kept
        )
        coverage, unmatched = self._coverage(question, matched, kept)
        return RetrievalResult(
            tables=tables,
            joins=joins,
            glossary_terms=glossary_terms,
            coverage=coverage,
            unmatched=unmatched,
            catalog_version=CATALOG_VERSION,
            notes=notes,
            path_used=PathName.KAG,
            provenance=tuple(
                Provenance(table=t.name, source=self._app.datasources[0].id) for t in tables
            ),
        )

    # ---- the LLM-driven Cypher path (DIF-34) -------------------------------------------------

    def schema_summary(self) -> str:
        """A compact graph schema for the Cypher prompt: node labels with property names, and
        relationship types. It NEVER includes Attribute.sample_values (or any cell value)."""
        labels = self._reader.labels()
        rels = self._reader.rel_types()
        lines = ["Node labels and their properties (names only):"]
        for label in labels:
            names = [p for p in self._reader.node_properties(label) if p != "sample_values"]
            lines.append(f"  (:{label}) {{{', '.join(names)}}}")
        lines.append("Relationship types: " + ", ".join(rels))
        lines.append(
            "Entities carry `table` (the table name) and `schema`; Concepts carry `name`, "
            "`synonyms`, `definition`; (Concept)-[:MAPS_TO]->(Entity); (Entity)-[:HAS_ATTRIBUTE]->"
            "(Attribute); (Entity)-[:REFERENCES]->(Entity)."
        )
        return "\n".join(lines)

    def retrieve_via_cypher(
        self, cypher: str, principal: Principal, question: str
    ) -> RetrievalResult:
        """Run a MODEL-WRITTEN read-only Cypher query after the mandatory guard, map the tables
        it returns to a sliver, and entitlement-filter. Raises CypherRejected / an error on any
        problem so the caller falls back to the deterministic path. Entitlement filtering runs
        here too."""
        from insights.catalog.cypher_guard import guard_cypher

        safe = guard_cypher(
            cypher,
            allowed_labels=set(self._reader.labels()),
            allowed_rels=set(self._reader.rel_types()),
            limit_cap=CYPHER_LIMIT_CAP,
        )
        rows = self._reader.run_read(safe, CYPHER_LIMIT_CAP)
        known = set(self._reader.entity_tables())
        found = {v for row in rows for v in row.values() if isinstance(v, str) and v in known}
        role = effective_role(principal, self._app)
        if role is None:
            return self._empty(list(dict.fromkeys(content_tokens(question))))
        wanted = sorted(found & set(role_tables(self._app, role)))
        if not wanted:
            return self._empty(list(dict.fromkeys(content_tokens(question))))
        # the tables come from the Cypher output; concept matching only supplies glossary terms
        # and coverage, and _assemble keeps a term only when its tables survive entitlement.
        matched = self._match_concepts(question)
        return self._assemble(wanted, matched, question, principal, ("kag:cypher",))

    # ---- building the sliver, entitlement-filtered -------------------------------------------

    def _build_tables(self, wanted: Sequence[str], principal: Principal) -> tuple[SliverTable, ...]:
        source = self._app.datasources[0].id
        rows = self._reader.columns(wanted)
        by_table: dict[str, list[ColumnRow]] = {}
        for r in rows:
            by_table.setdefault(r.table, []).append(r)
        candidates = [
            SliverTable(
                source_id=source,
                name=table,
                columns=tuple(
                    SliverColumn(name=c.name, type=c.type)
                    for c in sorted(cols, key=lambda c: c.position)
                ),
            )
            for table, cols in by_table.items()
        ]
        # second entitlement pass, now at column granularity (masks/column lists apply)
        allowed = allowed_objects(candidates, self._app, principal)
        out = []
        for table in candidates:
            cols = allowed.columns_of(table.name)
            if not cols:
                continue
            out.append(
                SliverTable(
                    source_id=source,
                    name=table.name,
                    columns=tuple(c for c in table.columns if c.name.lower() in cols),
                )
            )
        return tuple(sorted(out, key=lambda t: t.name))

    def joins_for(self, tables: Sequence[str], principal: Principal) -> tuple[SliverJoin, ...]:
        """1-hop REFERENCES joins among the given tables, entitlement-checked. Used by the hybrid
        merge to connect bypass tables to KAG-added tables. Read-only."""
        role = effective_role(principal, self._app)
        if role is None:
            return ()
        entitled = set(role_tables(self._app, role))
        names = [t for t in tables if t in entitled]
        return self._build_joins(set(names)) if names else ()

    def _build_joins(self, kept: set[str]) -> tuple[SliverJoin, ...]:
        joins = []
        seen = set()
        for j in self._reader.joins(sorted(kept)):
            if j.left_table in kept and j.right_table in kept:
                left = f"{j.left_table}.{j.left_column}"
                right = f"{j.right_table}.{j.right_column}"
                key = tuple(sorted((left, right)))
                if key not in seen:
                    seen.add(key)
                    joins.append(SliverJoin(left=left, right=right, kind="declared"))
        return tuple(sorted(joins, key=lambda j: (j.left, j.right)))

    def _coverage(
        self,
        question: str,
        matched: list[tuple[ConceptRow, set[str]]],
        kept: set[str],
    ) -> tuple[float, tuple[str, ...]]:
        concepts = list(dict.fromkeys(content_tokens(question)))
        if not concepts:
            return 0.0, ()
        covered_stems: set[str] = set()
        for c, ts in matched:
            if not set(ts) & kept:
                continue
            for phrase in (c.name, *c.synonyms):
                covered_stems.update(stems(phrase))
        hit = [tok for tok in concepts if tok in covered_stems]
        unmatched = tuple(tok for tok in concepts if tok not in covered_stems)
        return round(len(hit) / len(concepts), 4), unmatched

    def _empty(self, concepts: list[str]) -> RetrievalResult:
        return RetrievalResult(
            tables=(),
            joins=(),
            glossary_terms=(),
            coverage=0.0,
            unmatched=tuple(concepts),
            catalog_version=CATALOG_VERSION,
            notes=("kag:no_match",),
            path_used=PathName.KAG,
        )


# ---- providers -------------------------------------------------------------------------------


class Neo4jGraphReader:
    """The real reader. All queries are READ-routed; nothing here writes or loads."""

    def __init__(self, driver: Any, database: str) -> None:
        self._driver = driver
        self._database = database

    def _read(self, query: str, **params: Any) -> list[Any]:
        records, _, _ = self._driver.execute_query(
            query, parameters_=params, database_=self._database, routing_="r"
        )
        return records

    def ping(self) -> bool:
        self._read("RETURN 1 AS ok")
        return True

    def concepts(self) -> list[ConceptRow]:
        rows = self._read(
            "MATCH (c:Concept)-[:MAPS_TO]->(e:Entity) "
            "RETURN c.name AS name, c.synonyms AS synonyms, c.definition AS definition, "
            "collect(DISTINCT e.table) AS tables"
        )
        return [
            ConceptRow(
                name=r["name"],
                synonyms=tuple(r["synonyms"] or ()),
                definition=r["definition"] or "",
                tables=tuple(r["tables"] or ()),
            )
            for r in rows
        ]

    def columns(self, tables: Sequence[str]) -> list[ColumnRow]:
        rows = self._read(
            "MATCH (e:Entity)-[:HAS_ATTRIBUTE]->(a:Attribute) WHERE e.table IN $tables "
            "RETURN e.table AS table, a.name AS name, a.type AS type, "
            "coalesce(a.position, 0) AS position, coalesce(a.is_primary_key, false) AS pk",
            tables=list(tables),
        )
        return [
            ColumnRow(
                table=r["table"],
                name=r["name"],
                type=str(r["type"] or "unknown"),
                position=int(r["position"]),
                primary_key=bool(r["pk"]),
            )
            for r in rows
        ]

    def joins(self, tables: Sequence[str]) -> list[JoinRow]:
        rows = self._read(
            "MATCH (a:Entity)-[r:REFERENCES]->(b:Entity) "
            "WHERE a.table IN $tables AND b.table IN $tables "
            "RETURN a.table AS lt, r.from_column AS lc, b.table AS rt, r.to_column AS rc",
            tables=list(tables),
        )
        return [
            JoinRow(r["lt"], str(r["lc"]), r["rt"], str(r["rc"]))
            for r in rows
            if r["lc"] and r["rc"]
        ]

    def entity_tables(self) -> list[str]:
        return [r["t"] for r in self._read("MATCH (e:Entity) RETURN e.table AS t")]

    def labels(self) -> list[str]:
        rows = self._read("CALL db.labels() YIELD label RETURN label ORDER BY label")
        return [r["label"] for r in rows]

    def rel_types(self) -> list[str]:
        rows = self._read(
            "CALL db.relationshipTypes() YIELD relationshipType AS t RETURN t ORDER BY t"
        )
        return [r["t"] for r in rows]

    def node_properties(self, label: str) -> list[str]:
        # label comes from labels() (the graph's own set), not from user input
        rows = self._read(f"MATCH (n:{label}) WITH keys(n) AS ks UNWIND ks AS k RETURN DISTINCT k")
        return sorted(r["k"] for r in rows)

    def run_read(self, cypher: str, limit: int) -> list[Mapping[str, Any]]:
        # the query has already passed guard_cypher; READ routing, configured database only
        records = self._driver.execute_query(cypher, database_=self._database, routing_="r")[0]
        return [dict(r) for r in records[:limit]]


class Neo4jKagProvider:
    """Builds a `Neo4jKag` per app over one shared, lazily-opened, read-only driver."""

    def __init__(self, config: KagConfig) -> None:
        self._config = config
        self._driver: Any | None = None

    def _reader(self) -> Neo4jGraphReader:
        if self._driver is None:
            import neo4j

            self._driver = neo4j.GraphDatabase.driver(
                self._config.uri,
                auth=(self._config.user or "", self._config.password.get_secret_value())
                if self._config.password
                else None,
                connection_timeout=5,
                connection_acquisition_timeout=5,
            )
        return Neo4jGraphReader(self._driver, self._config.database)

    def for_app(self, app: AppProfile) -> Neo4jKag:
        return Neo4jKag(self._reader(), app)

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None


def build_kag_provider(config: KagConfig) -> Any:
    """A configured Neo4j provider, or the stub (reports unavailable) when no URI is set."""
    from insights.catalog.kag import StubKagProvider

    return Neo4jKagProvider(config) if config.configured else StubKagProvider()
