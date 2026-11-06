"""Loads each app's catalog and retriever once and shares them (read-only) across requests.

`DirectoryCatalogs` is the `Services.catalogs` implementation: it reads `apps/<app id>/` under a
configured apps folder. Entries are keyed by app id and version, so a new profile version loads
fresh files. Nothing here is per-request or per-principal; the entitlement filter happens inside
the retriever, per role.
"""

import threading
from dataclasses import dataclass
from pathlib import Path

from insights.catalog.catalog import Catalog
from insights.catalog.embedding import Embedder
from insights.catalog.retrieval import BypassRetriever
from insights.contracts.profile import AppProfile


@dataclass(frozen=True)
class AppCatalog:
    catalog: Catalog
    retriever: BypassRetriever


class DirectoryCatalogs:
    def __init__(self, apps_dir: Path, embedder: Embedder | None = None) -> None:
        self._apps_dir = apps_dir
        self._embedder = embedder
        self._loaded: dict[tuple[str, str], AppCatalog] = {}
        self._lock = threading.Lock()

    def for_app(self, app: AppProfile) -> AppCatalog:
        key = (app.id, app.version)
        with self._lock:
            if key not in self._loaded:
                catalog = Catalog.load(self._apps_dir / app.id, app)
                self._loaded[key] = AppCatalog(
                    catalog, BypassRetriever(catalog, app, self._embedder)
                )
            return self._loaded[key]
