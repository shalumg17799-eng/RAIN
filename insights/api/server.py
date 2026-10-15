"""Start the HTTP server: `python -m insights.cli run [--host H] [--port P]`.

Refuses to start (exit code 2) when the API keys file is missing or empty, when an app profile or
agent is invalid, or when the gateway is misconfigured. There is no open mode.
"""

import sys

from insights.api.auth import StartupError
from insights.api.settings import ServerSettings
from insights.catalog.snapshot import CatalogError
from insights.cli import repo_root
from insights.config import environment
from insights.gateway.config import ConfigError


def serve(host: str | None = None, port: int | None = None) -> int:
    try:
        settings = ServerSettings.from_env(environment(repo_root() / ".env"))
    except (ConfigError, ValueError) as exc:
        sys.stderr.write(f"refusing to start: {exc}\n")
        return 2
    try:
        from insights.api.app import create_app

        app = create_app(settings)
    except (StartupError, ConfigError, CatalogError) as exc:
        sys.stderr.write(f"refusing to start: {exc}\n")
        return 2
    import uvicorn

    uvicorn.run(app, host=host or settings.host, port=port or settings.port, log_level="info")
    return 0
