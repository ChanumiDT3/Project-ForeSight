"""Migration runner using deployment-supplied SQLite configuration."""
import os
from alembic import context
from app.models import Base
from app.settings import load_environment
from app.storage import make_engine

# Real environment variables win; otherwise backend/.env (or .env.example) is used.
load_environment()
url = os.environ.get("FORESIGHT_DATABASE_URL")
if not url:
    raise RuntimeError("Request FORESIGHT_DATABASE_URL before running migrations")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
