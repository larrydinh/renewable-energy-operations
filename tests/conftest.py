"""Opt-in PostgreSQL integration fixtures, isolated from the application database."""

import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from energy_ops.db import upgrade_database
from energy_ops.smard import REQUIRED_HEADERS


@pytest.fixture(scope="session")
def postgres_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL *_test database")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Integration tests require a separate PostgreSQL database ending in _test")
    engine = create_engine(url, pool_pre_ping=True)
    upgrade_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_engine(postgres_engine):
    with postgres_engine.begin() as conn:
        conn.execute(
            text("""
            TRUNCATE observation_revisions, generation_intervals, import_runs RESTART IDENTITY
        """)
        )
    return postgres_engine


@pytest.fixture
def day_export(tmp_path: Path) -> Path:
    path = tmp_path / "generation.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(REQUIRED_HEADERS)
        for index in range(96):
            start = datetime(2024, 1, 1) + timedelta(minutes=15 * index)
            end = start + timedelta(minutes=15)
            labels = [
                f"Jan {dt.day}, 2024 {dt.hour % 12 or 12}:{dt.minute:02} "
                f"{'PM' if dt.hour >= 12 else 'AM'}"
                for dt in (start, end)
            ]
            writer.writerow([*labels, "1", "2", "3", "4", "0", "-"])
    return path
