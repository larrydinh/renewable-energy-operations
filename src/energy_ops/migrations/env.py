"""Migrations run through energy-ops init-db using an explicit connection."""

from alembic import context

connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=None)
with context.begin_transaction():
    context.run_migrations()
