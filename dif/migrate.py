"""`python -m dif.migrate` - apply DB migrations (Alembic). Safe to run from many replicas at once: on PostgreSQL a
session advisory lock serialises them. Run it as a one-shot job/init step before starting api/worker."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from dif.config import ROOT, settings


def upgrade(url: str | None = None):
    url = url or settings.database_url
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(ROOT) / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    eng = create_engine(url)
    with eng.connect() as conn:
        if eng.dialect.name == "postgresql":
            conn.execute(text("select pg_advisory_lock(727274)"))
        try:
            command.upgrade(cfg, "head")
        finally:
            if eng.dialect.name == "postgresql":
                conn.execute(text("select pg_advisory_unlock(727274)"))
                conn.commit()


if __name__ == "__main__":
    upgrade()
    print("migrations applied")
