"""Database configuration and versioned schema upgrades."""

import os
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine


@lru_cache
def get_engine() -> Engine:
    load_dotenv(Path.cwd() / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured; see .env.example")
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def upgrade_database(engine: Engine) -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
