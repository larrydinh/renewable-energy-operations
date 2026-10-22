"""Stream SMARD actual-generation CSVs using the inspected export contract.

Timestamp labels are preserved verbatim. UTC normalization is a separate step.
"""

import csv
import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

SOURCES = {
    "Biomass": "biomass",
    "Hydropower": "hydropower",
    "Wind offshore": "wind_offshore",
    "Wind onshore": "wind_onshore",
    "Photovoltaics": "photovoltaics",
    "Other renewable": "other_renewable",
}
SOURCE_HEADERS = {f"{name} [MWh] Original resolutions": key for name, key in SOURCES.items()}
REQUIRED_HEADERS = ("Start date", "End date", *SOURCE_HEADERS)
# Accept ungrouped digits or groups of exactly three after each comma.
NUMBER = re.compile(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?")


class SmardParseError(ValueError):
    """An input does not match the source contract."""


@dataclass(frozen=True, slots=True)
class GenerationRecord:
    """One source measurement, retaining original labels and physical row origin."""

    source: str
    start_label: str
    end_label: str
    energy_mwh: Decimal | None
    source_file: str
    source_row: int


def parse_energy(value: str) -> Decimal | None:
    """Parse English decimal formatting; only '-' represents missing energy."""
    value = value.strip()
    if value == "-":
        return None
    if NUMBER.fullmatch(value) is None:
        raise SmardParseError(f"Invalid MWh value {value!r}; expected English decimal or '-'")
    return Decimal(value.replace(",", ""))


def iter_generation(path: Path) -> Iterator[GenerationRecord]:
    """Yield six records per row, rejecting invalid headers, values and row shapes.

    Conventional columns are allowed but not interpreted. A consumer must exhaust
    this iterator to validate the full file; records yielded earlier are not a
    promise that later rows are valid. No database publication happens here.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";", strict=True)
        try:
            header = next(reader, None)
            if header is None:
                raise SmardParseError(f"{path}: empty file")
            if len(header) != len(set(header)):
                raise SmardParseError(f"{path}: duplicate column headers")
            missing = [name for name in REQUIRED_HEADERS if name not in header]
            if missing:
                raise SmardParseError(f"{path}: missing required columns: {', '.join(missing)}")
            indexes = {name: header.index(name) for name in REQUIRED_HEADERS}
            row_count = 0
            while True:
                row_number = reader.line_num + 1
                row = next(reader, None)
                if row is None:
                    break
                if len(row) != len(header):
                    raise SmardParseError(
                        f"{path}: row {row_number}: expected {len(header)} fields, got {len(row)}"
                    )
                start, end = (row[indexes[name]] for name in ("Start date", "End date"))
                if not start.strip() or not end.strip():
                    raise SmardParseError(f"{path}: row {row_number}: empty timestamp label")
                # Validate the entire row before yielding any of its measurements.
                records = []
                for column, source in SOURCE_HEADERS.items():
                    try:
                        energy = parse_energy(row[indexes[column]])
                    except SmardParseError as exc:
                        raise SmardParseError(
                            f"{path}: row {row_number}, column {column!r}: {exc}"
                        ) from exc
                    records.append(
                        GenerationRecord(source, start, end, energy, str(path), row_number)
                    )
                row_count += 1
                yield from records
            if row_count == 0:
                raise SmardParseError(f"{path}: header has no data rows")
        except csv.Error as exc:
            raise SmardParseError(
                f"{path}: near row {reader.line_num}: invalid CSV: {exc}"
            ) from exc


def summarize_file(path: Path) -> dict[str, object]:
    """Fully validate a file and summarize observed values without retaining all rows."""
    sources = {source: {"observed": 0, "missing": 0, "zero": 0} for source in SOURCES.values()}
    measurements = 0
    rows = 0
    row_observed = 0
    complete = partial = empty = 0
    for record in iter_generation(path):
        measurements += 1
        counts = sources[record.source]
        if record.energy_mwh is None:
            counts["missing"] += 1
        else:
            counts["observed"] += 1
            counts["zero"] += record.energy_mwh == 0
            row_observed += 1
        if record.source == "other_renewable":
            rows += 1
            complete += row_observed == 6
            partial += 0 < row_observed < 6
            empty += row_observed == 0
            row_observed = 0
    return {
        "file": str(path),
        "source_rows": rows,
        "measurement_records": measurements,
        "rows_all_sources_observed": complete,
        "rows_partially_observed": partial,
        "rows_all_sources_missing": empty,
        "sources": sources,
    }
