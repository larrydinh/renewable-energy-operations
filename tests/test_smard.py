"""Test the source contract, malformed inputs and measurement provenance."""

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from energy_ops.smard import (
    REQUIRED_HEADERS,
    SmardParseError,
    iter_generation,
    parse_energy,
    summarize_file,
)

FIXTURE = Path(__file__).parent / "fixtures" / "smard_actual_generation_sample.csv"


def write_csv(tmp_path: Path, header: list[str], rows: list[list[str]]) -> Path:
    path = tmp_path / "input.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,459.75", Decimal("1459.75")),
        ("1234.56", Decimal("1234.56")),
        ("1,234,567.89", Decimal("1234567.89")),
        ("0.00", Decimal("0")),
        ("-12.50", Decimal("-12.50")),
        (" 12.50 ", Decimal("12.50")),
        ("12", Decimal("12")),
        ("0.123456789012345678901234567890", Decimal("0.123456789012345678901234567890")),
        ("-", None),
    ],
)
def test_parse_energy(raw: str, expected: Decimal | None) -> None:
    assert parse_energy(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", " ", "NaN", "Infinity", "1e3", "1.459,75", "12,34", "1,23,456", "abc"]
)
def test_reject_invalid_energy(raw: str) -> None:
    with pytest.raises(SmardParseError, match="Invalid MWh value"):
        parse_energy(raw)


def test_fixture_values_and_provenance() -> None:
    records = list(iter_generation(FIXTURE))
    assert len(records) == 18
    assert {r.source for r in records} == {
        "biomass",
        "hydropower",
        "wind_offshore",
        "wind_onshore",
        "photovoltaics",
        "other_renewable",
    }
    wind = records[2]
    assert wind.source == "wind_offshore"
    assert wind.energy_mwh == Decimal("1459.75")
    assert wind.start_label == "Jan 1, 2024 12:00 AM"
    assert wind.end_label == "Jan 1, 2024 12:15 AM"
    assert wind.source_row == 2
    assert wind.source_file == str(FIXTURE)
    assert {r.source_row for r in records} == {2, 3, 4}
    assert all(r.source != "hydro_pumped_storage" for r in records)


def test_summary_distinguishes_missing_zero_and_partial_rows() -> None:
    report = summarize_file(FIXTURE)
    assert report["source_rows"] == 3
    assert report["measurement_records"] == 18
    assert report["rows_all_sources_observed"] == 1
    assert report["rows_partially_observed"] == 1
    assert report["rows_all_sources_missing"] == 1
    assert report["sources"]["photovoltaics"] == {"observed": 2, "missing": 1, "zero": 1}
    assert report["sources"]["hydropower"] == {"observed": 1, "missing": 2, "zero": 0}


def test_columns_can_be_reordered(tmp_path: Path) -> None:
    header = list(reversed(REQUIRED_HEADERS))
    values = {h: "1.25" for h in REQUIRED_HEADERS}
    values.update({"Start date": "original start", "End date": "original end"})
    path = write_csv(tmp_path, header, [[values[h] for h in header]])
    records = list(iter_generation(path))
    assert len(records) == 6
    assert records[0].start_label == "original start"


@pytest.mark.parametrize("case", ["missing", "wrong_unit", "duplicate"])
def test_invalid_headers(tmp_path: Path, case: str) -> None:
    header = list(REQUIRED_HEADERS)
    if case == "missing":
        header.pop()
    elif case == "wrong_unit":
        header[-1] = header[-1].replace("MWh", "MW")
    else:
        header.append(header[-1])
    path = write_csv(tmp_path, header, [])
    with pytest.raises(SmardParseError, match="columns|headers"):
        list(iter_generation(path))


@pytest.mark.parametrize("extra_fields", [-1, 1])
def test_invalid_row_width(tmp_path: Path, extra_fields: int) -> None:
    path = write_csv(tmp_path, list(REQUIRED_HEADERS), [["1"] * (8 + extra_fields)])
    with pytest.raises(SmardParseError, match="row 2: expected 8 fields"):
        list(iter_generation(path))


def test_invalid_value_reports_row_and_column_before_yielding(tmp_path: Path) -> None:
    path = write_csv(tmp_path, list(REQUIRED_HEADERS), [["start", "end", *(["1"] * 5), "bad"]])
    with pytest.raises(SmardParseError, match="row 2, column 'Other renewable"):
        next(iter_generation(path))


@pytest.mark.parametrize("header_only", [False, True])
def test_empty_file_or_header_only(tmp_path: Path, header_only: bool) -> None:
    path = tmp_path / "empty.csv"
    path.write_text(";".join(REQUIRED_HEADERS) + "\n" if header_only else "")
    with pytest.raises(SmardParseError, match="empty file|no data rows"):
        list(iter_generation(path))


def test_empty_timestamp(tmp_path: Path) -> None:
    path = write_csv(tmp_path, list(REQUIRED_HEADERS), [["", "end", *(["1"] * 6)]])
    with pytest.raises(SmardParseError, match="empty timestamp"):
        list(iter_generation(path))


def test_malformed_csv_quoting(tmp_path: Path) -> None:
    path = tmp_path / "broken.csv"
    path.write_text(";".join(REQUIRED_HEADERS) + '\n"unterminated')
    with pytest.raises(SmardParseError, match="invalid CSV"):
        list(iter_generation(path))
