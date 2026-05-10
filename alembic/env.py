"""Alembic environment.

Resolves the database URL from STORYMASTER_DB_URL / STORYMASTER_DB_PATH the same
way the application does, so `alembic upgrade head` always targets the same
database the API server uses.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from storymaster.model.database.schema.base import BaseTable
from storymaster.sync_server.config import config as app_config

# Import the schema so all tables register on BaseTable.metadata.
import storymaster.model.database.schema.base  # noqa: F401

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

if not alembic_config.get_main_option("sqlalchemy.url"):
    alembic_config.set_main_option("sqlalchemy.url", app_config.get_database_url())

target_metadata = BaseTable.metadata


def _is_sqlite() -> bool:
    return alembic_config.get_main_option("sqlalchemy.url", "").startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(
        url=alembic_config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
