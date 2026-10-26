"""
Alembic runs this file for every migration command.
It connects to the same database the app uses (data/engine.py)
and compares it against the tables in data/orm_models.py
when autogenerating a revision.

render_as_batch is on because SQLite can't ALTER most columns,
batch mode recreates the table and copies the rows over instead.

Helpful reference:
https://alembic.sqlalchemy.org/en/latest/autogenerate.html
https://alembic.sqlalchemy.org/en/latest/batch.html
"""

from logging.config import fileConfig

from alembic import context

from receipt_manager.data.engine import engine
from receipt_manager.data.orm_models import Base, UTCDateTime

config = context.config

# only set up logging when run from the alembic cli,
# migrate.py builds its Config without an ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


# UTCDateTime only changes the values in Python, the column is a plain DateTime.
# Writing it out as sa.DateTime keeps old migration files from importing orm_models.py,
# which would break them if the class ever gets renamed or moved.
def render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


# writes the SQL to stdout instead of running it (alembic upgrade head --sql)
def run_migrations_offline() -> None:
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # tests can hand over their own connection through config.attributes
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return

    with engine.connect() as connection:
        _run(connection)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
