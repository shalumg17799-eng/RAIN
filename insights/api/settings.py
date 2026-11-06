"""Server settings from the environment (and `.env`). Nothing here holds a secret value."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from insights.cli import repo_root
from insights.gateway.config import GatewayConfig


@dataclass(frozen=True)
class ServerSettings:
    apps_dir: Path
    agents_dir: Path
    skills_dir: Path
    keys_file: Path | None
    audit_file: Path | None
    otel_exporter: str
    gateway: GatewayConfig
    host: str
    port: int
    environ: Mapping[str, str]

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "ServerSettings":
        root = repo_root()

        def path(name: str, default: Path | None) -> Path | None:
            value = environ.get(name, "").strip()
            return Path(value) if value else default

        exporter = environ.get("INSIGHTS_OTEL_EXPORTER", "none").strip().lower() or "none"
        if exporter not in ("none", "console"):
            raise ValueError("INSIGHTS_OTEL_EXPORTER must be none or console")
        return cls(
            apps_dir=path("INSIGHTS_APPS_DIR", root / "apps") or root / "apps",
            agents_dir=path("INSIGHTS_AGENTS_DIR", root / "agents") or root / "agents",
            skills_dir=path("INSIGHTS_SKILLS_DIR", root / "skills") or root / "skills",
            keys_file=path("INSIGHTS_API_KEYS_FILE", None),
            audit_file=path("INSIGHTS_AUDIT_FILE", None),
            otel_exporter=exporter,
            gateway=GatewayConfig.from_env(environ),
            host=environ.get("INSIGHTS_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=int(environ.get("INSIGHTS_PORT", "8080") or 8080),
            environ=dict(environ),
        )
