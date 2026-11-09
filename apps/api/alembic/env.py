"""Alembic environment.

The database URL comes from application settings (``OSCAR_DATABASE_URL``) rather
than alembic.ini, so migrations and the app can never point at different databases.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from oscar_api.config import get_settings

# Imported for their side effect of registering tables on Base.metadata, so
# `alembic revision --autogenerate` can see them. Migrations in this repo are
# still hand-reviewed (docs/04 §9) -- autogenerate is a starting point, not
# the source of truth.
from oscar_api.core import models as _core_models  # noqa: F401
from oscar_api.db import Base
from oscar_api.modules.applications import models as _applications_models  # noqa: F401
from oscar_api.modules.career import models as _career_models  # noqa: F401
from oscar_api.modules.cv import models as _cv_models  # noqa: F401
from oscar_api.modules.jobs import models as _jobs_models  # noqa: F401
from oscar_api.modules.settings import models as _settings_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

# Empty at M0; populated as models land in M1+.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
