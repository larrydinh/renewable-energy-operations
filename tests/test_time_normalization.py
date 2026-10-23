"""Exercise clock changes using independently constructed local-clock fixtures."""

import csv
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path

import pytest

from energy_ops.cli import main
from energy_ops.smard import REQUIRED_HEADERS, iter_generation
from energy_ops.time_normalization import (
    TimeNormalizationError,
    normalize_file,
    parse_timestamp_label,
)


def label(instant: datetime) -> str:
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return (
        f"{months[instant.month - 1]} {instant.day}, {instant.year} "
        f"{instant.hour % 12 or 12}:{instant.minute:02d} {'PM' if instant.hour >= 12 else 'AM'}"
    )


def export_rows(start: date, end: date) -> list[list[str]]:
    """Construct 2024 test days by local clock order, without a UTC-grid algorithm."""
    rows = []
    day = start
    while day < end:
        hours = list(range(24))
        if day == date(2024, 3, 31):
            hours.remove(2)
        elif day == date(2024, 10, 27):
            hours.insert(3, 2)
        for hour in hours:
            for minute in (0, 15, 30, 45):
                wall = datetime(day.year, day.month, day.day, hour, minute)
                rows.append(
                    [
                        label(wall),
                        label(wall + timedelta(minutes=15)),
                        "1,459.75",
                        "1.25",
                        "2.50",
                        "3.75",
                        "0.00",
                        "-",
                    ]
                )
        day += timedelta(days=1)
    return rows


def write_export(tmp_path: Path, rows: list[list[str]]) -> Path:
    path = tmp_path / "sample.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(REQUIRED_HEADERS)
        writer.writerows(rows)
    return path


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Jan 1, 2024 12:00 AM", datetime(2024, 1, 1)),
        ("Jan 1, 2024 12:00 PM", datetime(2024, 1, 1, 12)),
        ("Feb 29, 2024 11:45 PM", datetime(2024, 2, 29, 23, 45)),
    ],
)
def test_parse_label(value: str, expected: datetime) -> None:
    assert parse_timestamp_label(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "Feb 29, 2023 1:00 AM",
        "Xxx 1, 2024 1:00 AM",
        "Jan 32, 2024 1:00 AM",
        "Jan 1, 2024 00:00 AM",
        "Jan 1, 2024 1:60 AM",
        "2024-01-01T00:00Z",
    ],
)
def test_reject_invalid_label(value: str) -> None:
    with pytest.raises(TimeNormalizationError, match="Invalid timestamp label"):
        parse_timestamp_label(value)


@pytest.mark.parametrize(
    ("start", "end", "expected", "utc_start", "utc_end", "warning_count"),
    [
        (
            date(2024, 1, 15),
            date(2024, 1, 16),
            96,
            datetime(2024, 1, 14, 23, tzinfo=UTC),
            datetime(2024, 1, 15, 23, tzinfo=UTC),
            0,
        ),
        (
            date(2024, 7, 15),
            date(2024, 7, 16),
            96,
            datetime(2024, 7, 14, 22, tzinfo=UTC),
            datetime(2024, 7, 15, 22, tzinfo=UTC),
            0,
        ),
        (
            date(2024, 3, 31),
            date(2024, 4, 1),
            92,
            datetime(2024, 3, 30, 23, tzinfo=UTC),
            datetime(2024, 3, 31, 22, tzinfo=UTC),
            1,
        ),
        (
            date(2024, 10, 27),
            date(2024, 10, 28),
            100,
            datetime(2024, 10, 26, 22, tzinfo=UTC),
            datetime(2024, 10, 27, 23, tzinfo=UTC),
            1,
        ),
        (
            date(2024, 2, 28),
            date(2024, 3, 1),
            192,
            datetime(2024, 2, 27, 23, tzinfo=UTC),
            datetime(2024, 2, 29, 23, tzinfo=UTC),
            0,
        ),
        (
            date(2023, 12, 31),
            date(2024, 1, 2),
            192,
            datetime(2023, 12, 30, 23, tzinfo=UTC),
            datetime(2024, 1, 1, 23, tzinfo=UTC),
            0,
        ),
    ],
)
def test_periods_and_unchanged_measurements(
    tmp_path: Path,
    start: date,
    end: date,
    expected: int,
    utc_start: datetime,
    utc_end: datetime,
    warning_count: int,
) -> None:
    path = write_export(tmp_path, export_rows(start, end))
    result = normalize_file(path, start_date=start, end_date=end)
    assert result.expected_intervals == expected
    assert len(result.records) == expected * 6
    assert result.records[0].interval_start_utc == utc_start
    assert result.records[-1].interval_end_utc == utc_end
    intervals = result.records[::6]
    assert all(a.interval_end_utc == b.interval_start_utc for a, b in pairwise(intervals))
    assert len(result.warnings) == warning_count
    assert len({(r.source, r.interval_start_utc) for r in result.records}) == expected * 6
    for record, raw in zip(result.records, iter_generation(path), strict=True):
        assert record.energy_mwh == raw.energy_mwh
        assert record.start_label == raw.start_label
        assert record.end_label == raw.end_label
        assert record.source_row == raw.source_row
        assert record.source_file == str(path)
        assert record.interval_start_utc.tzinfo is UTC
        assert record.interval_end_utc - record.interval_start_utc == timedelta(minutes=15)
    report = result.summary()
    assert report["missing_measurements"] == expected
    assert report["end_label_warning_count"] == warning_count
    assert sum(r.energy_mwh for r in result.records if r.source == "biomass") == (
        Decimal("1459.75") * expected
    )


def test_both_autumn_occurrences_survive(tmp_path: Path) -> None:
    path = write_export(tmp_path, export_rows(date(2024, 10, 27), date(2024, 10, 28)))
    result = normalize_file(path, start_date=date(2024, 10, 27), end_date=date(2024, 10, 28))
    repeated = [
        r
        for r in result.records
        if r.source == "biomass" and r.start_label == "Oct 27, 2024 2:15 AM"
    ]
    assert [r.interval_start_utc for r in repeated] == [
        datetime(2024, 10, 27, 0, 15, tzinfo=UTC),
        datetime(2024, 10, 27, 1, 15, tzinfo=UTC),
    ]
    assert all(r.energy_mwh == Decimal("1459.75") for r in repeated)
    assert result.summary()["non_96_interval_days"] == {"2024-10-27": 100}
    assert result.warnings[0].canonical_local_end == "2024-10-27T02:00:00+01:00"


def test_spring_gap_and_original_end_label(tmp_path: Path) -> None:
    path = write_export(tmp_path, export_rows(date(2024, 3, 31), date(2024, 4, 1)))
    result = normalize_file(path, start_date=date(2024, 3, 31), end_date=date(2024, 4, 1))
    assert not any(parse_timestamp_label(r.start_label).hour == 2 for r in result.records)
    warning = result.warnings[0]
    assert warning.original_end_label == "Mar 31, 2024 2:00 AM"
    assert warning.canonical_local_end == "2024-03-31T03:00:00+02:00"
    assert warning.canonical_utc_end == "2024-03-31T01:00:00+00:00"
    assert result.summary()["non_96_interval_days"] == {"2024-03-31": 92}


def test_canonical_transition_end_is_also_accepted(tmp_path: Path) -> None:
    rows = export_rows(date(2024, 3, 31), date(2024, 4, 1))
    rows[7][1] = "Mar 31, 2024 3:00 AM"
    path = write_export(tmp_path, rows)
    result = normalize_file(path, start_date=date(2024, 3, 31), end_date=date(2024, 4, 1))
    assert result.warnings == ()


@pytest.mark.parametrize("mutation", ["remove_middle", "remove_last", "duplicate", "swap", "extra"])
def test_reject_incomplete_or_disordered_grid(tmp_path: Path, mutation: str) -> None:
    rows = export_rows(date(2024, 1, 1), date(2024, 1, 2))
    if mutation == "remove_middle":
        rows.pop(10)
    elif mutation == "remove_last":
        rows.pop()
    elif mutation == "duplicate":
        rows.insert(10, rows[10])
    elif mutation == "swap":
        rows[10], rows[11] = rows[11], rows[10]
    else:
        rows.append(rows[-1])
    path = write_export(tmp_path, rows)
    with pytest.raises(TimeNormalizationError, match="row|incomplete"):
        normalize_file(path, start_date=date(2024, 1, 1), end_date=date(2024, 1, 2))


@pytest.mark.parametrize("column", [0, 1])
def test_invalid_timestamp_has_row_context(tmp_path: Path, column: int) -> None:
    rows = export_rows(date(2024, 1, 1), date(2024, 1, 2))
    rows[10][column] = "bad label"
    path = write_export(tmp_path, rows)
    with pytest.raises(TimeNormalizationError, match="row 12: Invalid timestamp"):
        normalize_file(path, start_date=date(2024, 1, 1), end_date=date(2024, 1, 2))


def test_arbitrary_end_label_is_not_a_warning(tmp_path: Path) -> None:
    rows = export_rows(date(2024, 3, 31), date(2024, 4, 1))
    rows[7][1] = "Mar 31, 2024 4:00 AM"
    path = write_export(tmp_path, rows)
    with pytest.raises(TimeNormalizationError, match="end label"):
        normalize_file(path, start_date=date(2024, 3, 31), end_date=date(2024, 4, 1))


def test_wrong_period_rejected(tmp_path: Path) -> None:
    path = write_export(tmp_path, export_rows(date(2024, 1, 1), date(2024, 1, 2)))
    with pytest.raises(TimeNormalizationError, match="start label"):
        normalize_file(path, start_date=date(2024, 1, 2), end_date=date(2024, 1, 3))


@pytest.mark.parametrize("end", [date(2024, 1, 1), date(2023, 12, 31)])
def test_empty_or_reversed_period_rejected(tmp_path: Path, end: date) -> None:
    with pytest.raises(TimeNormalizationError, match="end_date must be after"):
        normalize_file(tmp_path / "unused.csv", start_date=date(2024, 1, 1), end_date=end)


def test_datetime_boundary_rejected(tmp_path: Path) -> None:
    with pytest.raises(TimeNormalizationError, match="must be dates"):
        normalize_file(
            tmp_path / "unused.csv", start_date=datetime(2024, 1, 1), end_date=date(2024, 1, 2)
        )


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [(date(2024, 3, 31), date(2024, 4, 1), 92), (date(2024, 10, 27), date(2024, 10, 28), 100)],
)
def test_normalize_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], start: date, end: date, expected: int
) -> None:
    path = write_export(tmp_path, export_rows(start, end))
    code = main(
        [
            "normalize-smard",
            str(path),
            "--start-date",
            start.isoformat(),
            "--end-date",
            end.isoformat(),
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["source_rows"] == expected
    assert report["end_label_warning_count"] == 1
    assert captured.err == ""


def test_normalize_command_failure_has_no_partial_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = export_rows(date(2024, 1, 1), date(2024, 1, 2))
    path = write_export(tmp_path, rows[:-1])
    assert (
        main(
            ["normalize-smard", str(path), "--start-date", "2024-01-01", "--end-date", "2024-01-02"]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "expected 96 rows" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("value", ["20240101", "Jan 1, 2024", "2024-02-30"])
def test_command_rejects_bad_date_format(capsys: pytest.CaptureFixture[str], value: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["normalize-smard", "unused.csv", "--start-date", value, "--end-date", "2024-02-01"])
    assert exc.value.code == 2
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_command_requires_explicit_period(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["normalize-smard", "unused.csv"])
    assert exc.value.code == 2
    assert "required" in capsys.readouterr().err
