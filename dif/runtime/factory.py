"""Builds a Runtime from settings (shared by the API, the Temporal worker and tests)."""
from dif.artifacts.store import ArtifactStore
from dif.config import settings
from dif.runtime.agents import AgentRegistry
from dif.runtime.engine import Runtime
from dif.runtime.executors import make_executor
from dif.runtime.store import Store
from dif.skills.registry import SkillRegistry


def build_runtime(executor_kind=None, store=None, executor=None) -> Runtime:
    store = store or Store(settings.database_url)
    return Runtime(store, SkillRegistry(settings.skills_dirs), AgentRegistry(settings.agents_dir, store, settings.contracts_dir),
                   executor if executor is not None else make_executor(executor_kind),
                   ArtifactStore(settings.artifact_store), settings.contracts_dir)
