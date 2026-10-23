"""Real PostgreSQL checks for publication, revisions and rollback."""

import csv
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from energy_ops.ingestion import import_file
from energy_ops.time_normalization import TimeNormalizationError

pytestmark = pytest.mark.integration


def load(engine, path, **kwargs):
    return import_file(
        engine, path, start_date=date(2024, 1, 1), end_date=date(2024, 1, 2), **kwargs
    )


def change_first_value(path, value):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    rows[1][2] = value
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle, delimiter=";").writerows(rows)


def test_import_and_rerun_are_idempotent(db_engine, day_export):
    first = load(db_engine, day_export)
    second = load(db_engine, day_export)
    assert first["inserted"] == 576
    assert second["status"] == "no_change"
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM generation_intervals")).scalar_one() == 576
        assert conn.execute(text("SELECT count(*) FROM observation_revisions")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM import_runs")).scalar_one() == 2
        assert (
            conn.execute(
                text("""
            SELECT count(*) FROM generation_intervals WHERE energy_mwh IS NULL
        """)
            ).scalar_one()
            == 96
        )


def test_conflicting_snapshot_requires_explicit_approval(db_engine, day_export):
    load(db_engine, day_export)
    change_first_value(day_export, "9")
    with pytest.raises(ValueError, match="--accept-corrections"):
        load(db_engine, day_export)
    with db_engine.connect() as conn:
        assert (
            conn.execute(
                text("""
            SELECT energy_mwh FROM generation_intervals WHERE source='biomass'
            ORDER BY interval_start_utc LIMIT 1
        """)
            ).scalar_one()
            == 1
        )
        assert (
            conn.execute(
                text("""
            SELECT count(*) FROM import_runs WHERE status='failed'
        """)
            ).scalar_one()
            == 1
        )
    outcome = load(db_engine, day_export, accept_corrections=True)
    assert outcome["updated"] == 1
    with db_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT previous_energy_mwh FROM observation_revisions")).scalar_one()
            == 1
        )
        assert (
            conn.execute(
                text("""
            SELECT energy_mwh FROM generation_intervals WHERE source='biomass'
            ORDER BY interval_start_utc LIMIT 1
        """)
            ).scalar_one()
            == 9
        )


def test_missing_snapshot_never_erases_known_values(db_engine, day_export):
    load(db_engine, day_export)
    change_first_value(day_export, "-")
    result = load(db_engine, day_export, accept_corrections=True)
    assert result["preserved"] == 1
    assert result["updated"] == 0
    with db_engine.connect() as conn:
        assert (
            conn.execute(
                text("""
            SELECT energy_mwh FROM generation_intervals WHERE source='biomass'
            ORDER BY interval_start_utc LIMIT 1
        """)
            ).scalar_one()
            == 1
        )


def test_bad_timeline_leaves_failure_history_but_no_observations(db_engine, day_export):
    lines = day_export.read_text(encoding="utf-8-sig").splitlines()
    day_export.write_text("\n".join(lines[:-1]))
    with pytest.raises(TimeNormalizationError, match="incomplete"):
        load(db_engine, day_export)
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM generation_intervals")).scalar_one() == 0
        assert conn.execute(text("SELECT status FROM import_runs")).scalar_one() == "failed"


def test_database_enforces_interval_duration(db_engine, day_export):
    load(db_engine, day_export)
    with pytest.raises(IntegrityError), db_engine.begin() as conn:
        conn.execute(
            text("""
            UPDATE generation_intervals
            SET interval_end_utc=interval_start_utc+interval '16 minutes'
        """)
        )


def test_failure_after_writes_rolls_back_entire_publication(db_engine, day_export):
    with db_engine.begin() as conn:
        conn.execute(
            text("""
            CREATE FUNCTION reject_test_success() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.status='succeeded' THEN RAISE EXCEPTION 'test publication failure';
            END IF; RETURN NEW; END $$
        """)
        )
        conn.execute(
            text("""
            CREATE TRIGGER reject_success BEFORE UPDATE ON import_runs
            FOR EACH ROW EXECUTE FUNCTION reject_test_success()
        """)
        )
    try:
        with pytest.raises(DBAPIError, match="test publication failure"):
            load(db_engine, day_export)
        with db_engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM generation_intervals")).scalar_one() == 0
            assert conn.execute(text("SELECT status FROM import_runs")).scalar_one() == "failed"
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("DROP TRIGGER reject_success ON import_runs"))
            conn.execute(text("DROP FUNCTION reject_test_success()"))
