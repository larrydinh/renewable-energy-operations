"""Batch boundaries, partial failure, safe reruns, and scheduler exit codes."""

import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from energy_ops.batch import DATABASE_ERROR, export_period, import_directory
from energy_ops.cli import main


@pytest.mark.parametrize(
    "name",
    [
        "generation.csv",
        "Actual_generation_invalid_Quarterhour.csv",
        "Actual_generation_202402300000_202403010000_Quarterhour.csv",
        "Actual_generation_202401010015_202401020000_Quarterhour.csv",
        "Actual_generation_202401010000_202401020015_Quarterhour.csv",
        "Actual_generation_202401020000_202401010000_Quarterhour.csv",
        "Actual_generation_202401010000_202401010000_Quarterhour.csv",
    ],
)
def test_rejects_ambiguous_or_invalid_periods(name):
    with pytest.raises(ValueError):
        export_period(Path(name))


def test_reads_local_period_across_year_boundary():
    assert export_period(Path("Actual_generation_202312310000_202401020000_Quarterhour.csv")) == (
        date(2023, 12, 31),
        date(2024, 1, 2),
    )


def test_empty_or_missing_directory_fails_without_import(tmp_path):
    for directory in (tmp_path, tmp_path / "absent"):
        with pytest.raises(ValueError):
            import_directory(None, directory)


def test_filename_errors_and_database_errors_are_reported_without_secrets(tmp_path, monkeypatch):
    (tmp_path / "Actual_generation_invalid_Quarterhour.csv").touch()
    (tmp_path / "Actual_generation_202401010000_202401020000_Quarterhour.csv").touch()

    def unavailable(*args, **kwargs):
        raise OperationalError("secret connection details", {}, RuntimeError("secret password"))

    monkeypatch.setattr("energy_ops.batch.import_file", unavailable)
    report = import_directory(None, tmp_path)
    assert report["failed"] == 2
    assert report["total_files"] == 2
    assert report["files"][0]["error"] == DATABASE_ERROR
    assert "secret" not in json.dumps(report)


@pytest.mark.integration
def test_batch_continues_after_failure_and_reruns_safely(
    db_engine, day_export, monkeypatch, capsys
):
    directory = day_export.parent / "batch"
    directory.mkdir()
    original = day_export.read_text(encoding="utf-8-sig")
    (directory / "Actual_generation_202401010000_202401020000_Quarterhour.csv").write_text(original)
    (directory / "Actual_generation_202401020000_202401030000_Quarterhour.csv").write_text(
        "bad csv"
    )
    third = original.replace("Jan 2,", "Jan 4,").replace("Jan 1,", "Jan 3,")
    (directory / "Actual_generation_202401030000_202401040000_Quarterhour.csv").write_text(third)
    # Unrelated CSVs are not interpreted as SMARD exports.
    (directory / "notes.csv").write_text("not an export")
    monkeypatch.setattr("energy_ops.db.get_engine", lambda: db_engine)

    assert main(["import-smard-batch", str(directory)]) == 1
    first = json.loads(capsys.readouterr().out)
    assert [row["status"] for row in first["files"]] == ["succeeded", "failed", "succeeded"]
    assert first["inserted"] == 1152
    assert first["failed"] == 1

    assert main(["import-smard-batch", str(directory)]) == 1
    rerun = json.loads(capsys.readouterr().out)
    assert rerun["no_change"] == 2
    assert rerun["inserted"] == 0
    assert rerun["updated"] == 0
    with db_engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM generation_intervals")) == 1152
        assert conn.scalar(text("SELECT count(*) FROM import_runs WHERE status='failed'")) == 2

    # Once the bad input is removed, a clean rerun returns success for scheduling.
    (directory / "Actual_generation_202401020000_202401030000_Quarterhour.csv").unlink()
    assert main(["import-smard-batch", str(directory)]) == 0
    clean = json.loads(capsys.readouterr().out)
    assert clean["status"] == "succeeded"
    assert clean["no_change"] == 2


def test_empty_batch_cli_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("energy_ops.db.get_engine", lambda: None)
    assert main(["import-smard-batch", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No files matching" in captured.err
