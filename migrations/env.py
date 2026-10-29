from alembic import context
from sqlalchemy import create_engine

from dif.config import settings

url = context.config.get_main_option("sqlalchemy.url") or settings.database_url
if context.is_offline_mode():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as conn:
        context.configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()
