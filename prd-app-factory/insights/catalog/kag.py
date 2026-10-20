"""The KAG seam (knowledge graph) and the probe-and-fall-back logic. No KAG exists yet.

The router only sets a PREFERENCE (`kag` or `bypass`); predicting whether the graph can answer is as
hard as asking it. So the sliver step probes: use the KAG when preferred and available, and fall
back to the bypass retrieval when it is down, errors, or covers too little. The path actually
used is always recorded. Today the only implementation is `StubKag`, which reports itself
unavailable, so every run takes the bypass path and says why. Neo4j, parameterized Cypher and
ontology retrieval are out of scope until the Knowledge Factory delivers (report 5.2, M5).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol

from insights.catalog.retrieval import RetrievalResult
from insights.catalog.text import content_tokens
from insights.contracts.enums import PathName
from insights.contracts.principal import Principal
from insights.contracts.request import AskContext
from insights.contracts.state import SliverJoin

KAG_MIN_COVERAGE = 0.6
"""Below this share of the question's concepts, a KAG answer is not trusted and bypass is used."""


class Kag(Protocol):
    def available(self) -> bool: ...

    def retrieve(
        self, question: str, principal: Principal, context: AskContext | None, *, widen: int = 0
    ) -> RetrievalResult: ...

    def joins_for(self, tables: Sequence[str], principal: Principal) -> tuple[SliverJoin, ...]: ...


class StubKag:
    """Reports itself unavailable. The seam exists; the graph does not."""

    def available(self) -> bool:
        return False

    def retrieve(
        self, question: str, principal: Principal, context: AskContext | None, *, widen: int = 0
    ) -> RetrievalResult:
        raise NotImplementedError("the KAG is not built yet")

    def joins_for(self, tables: Sequence[str], principal: Principal) -> tuple[SliverJoin, ...]:
        return ()


class StubKagProvider:
    def for_app(self, app: Any) -> Kag:
        return StubKag()


@dataclass(frozen=True)
class SliverChoice:
    result: RetrievalResult
    path_used: PathName
    notes: tuple[str, ...]


def _table_of(ref: str) -> str:
    return ref.split(".")[0]


def _merge(
    bypass: RetrievalResult, kag: RetrievalResult, client: Kag, principal: Principal, question: str
) -> RetrievalResult:
    """HYBRID: the KAG ADDS to the bypass result -- entitled tables, concept definitions and 1-hop
    REFERENCES joins -- rather than replacing it. Both inputs were entitlement-filtered already, so
    the union stays within the caller's entitlements; `joins_for` only connects tables we kept.
    """
    tables = list(bypass.tables)
    have = {t.name for t in tables}
    for t in kag.tables:
        if t.name not in have:
            tables.append(t)
            have.add(t.name)
    glossary = list(bypass.glossary_terms)
    seen = {g.term for g in glossary}
    for g in kag.glossary_terms:
        if g.term not in seen:
            glossary.append(g)
            seen.add(g.term)
    joins: dict[tuple[str, str], SliverJoin] = {}
    for j in (*bypass.joins, *kag.joins, *client.joins_for(sorted(have), principal)):
        if _table_of(j.left) in have and _table_of(j.right) in have:
            joins[(j.left, j.right)] = j
    provenance = {p.table: p for p in bypass.provenance}
    for p in kag.provenance:
        provenance.setdefault(p.table, p)
    concepts = set(content_tokens(question))
    unmatched = tuple(sorted(set(bypass.unmatched) & set(kag.unmatched)))
    coverage = (
        round((len(concepts) - len(unmatched)) / len(concepts), 4) if concepts else bypass.coverage
    )
    return replace(
        bypass,
        tables=tuple(sorted(tables, key=lambda t: t.name)),
        joins=tuple(joins.values()),
        glossary_terms=tuple(glossary),
        coverage=coverage,
        unmatched=unmatched,
        path_used=PathName.KAG,
        provenance=tuple(provenance.values()),
        notes=(*bypass.notes, "kag:hybrid"),
    )


def retrieve_with_fallback(
    preference: PathName,
    kag: Kag,
    bypass: Callable[[], RetrievalResult],
    question: str,
    principal: Principal,
    context: AskContext | None,
    *,
    widen: int = 0,
    min_coverage: float = KAG_MIN_COVERAGE,
    cypher: Callable[[], RetrievalResult] | None = None,
) -> SliverChoice:
    """HYBRID KAG: when the graph is preferred, available and covers enough of the question, merge
    its tables, definitions and joins into the bypass result; otherwise use bypass. Never raises.

    `cypher`, when given, is the model-written Cypher attempt (DIF-34): it is tried first and, if it
    raises (no model, a rejected query, a graph error) or returns too little, the deterministic KAG
    retrieval is used. Either way entitlement filtering has already run inside the KAG.
    """
    notes: list[str] = []
    bypass_result = bypass()
    if preference is PathName.KAG:
        try:
            if not kag.available():
                notes.append("kag_unavailable")
            else:
                kagres = None
                if cypher is not None:
                    try:
                        kagres = cypher()
                    except Exception:
                        kagres = None  # fall through to the deterministic retrieval
                if kagres is None:
                    kagres = kag.retrieve(question, principal, context, widen=widen)
                if kagres.tables and kagres.coverage >= min_coverage:
                    merged = _merge(bypass_result, kagres, kag, principal, question)
                    return SliverChoice(merged, PathName.KAG, (*notes, "kag:hybrid"))
                notes.append("kag_low_coverage")
        except Exception:
            notes.append("kag_error")
    return SliverChoice(
        replace(bypass_result, path_used=PathName.BYPASS, notes=(*bypass_result.notes, *notes)),
        PathName.BYPASS,
        tuple(notes),
    )
