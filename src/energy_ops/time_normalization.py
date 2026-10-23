"""Normalize complete, ordered SMARD exports onto a verified UTC timeline.

The requested period is explicit and uses German local calendar dates. A result
is returned only after the entire file passes validation. Partial or unordered
grids are rejected rather than guessed into place.
"""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from itertools import groupby
from operator import attrgetter
from pathlib import Path
from zoneinfo import ZoneInfo

from energy_ops.smard import GenerationRecord, iter_generation

INTERVAL = timedelta(minutes=15)
SOURCE_TIMEZONE = "Europe/Berlin"
POLICY_VERSION = "smard-complete-grid-v1"
MONTHS = {
    name: index
    for index, name in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        start=1,
    )
}
LABEL = re.compile(r"([A-Z][a-z]{2}) ([0-9]{1,2}), ([0-9]{4}) (1[0-2]|[1-9]):([0-5][0-9]) (AM|PM)")


class TimeNormalizationError(ValueError):
    """A timestamp or the requested file timeline cannot be interpreted safely."""


@dataclass(frozen=True, slots=True)
class NormalizedGenerationRecord(GenerationRecord):
    """Original measurement and provenance, with unambiguous UTC boundaries."""

    interval_start_utc: datetime
    interval_end_utc: datetime


@dataclass(frozen=True, slots=True)
class EndLabelWarning:
    """A known source wall-clock end label differs at a DST boundary."""

    source_row: int
    original_end_label: str
    canonical_local_end: str
    canonical_utc_end: str


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Fully validated measurements; no partially validated result is exposed."""

    source_file: str
    start_date: date
    end_date: date
    records: tuple[NormalizedGenerationRecord, ...]
    warnings: tuple[EndLabelWarning, ...]
    expected_intervals: int

    def summary(self) -> dict[str, object]:
        """Return a compact, JSON-compatible validation report."""
        # Each input row yields six source measurements in a fixed order.
        intervals = self.records[::6]
        zone = ZoneInfo(SOURCE_TIMEZONE)
        daily = Counter(r.interval_start_utc.astimezone(zone).date() for r in intervals)
        return {
            "file": self.source_file,
            "normalization_policy": POLICY_VERSION,
            "source_timezone": SOURCE_TIMEZONE,
            "start_date": self.start_date.isoformat(),
            "end_date_exclusive": self.end_date.isoformat(),
            "source_rows": len(intervals),
            "expected_intervals": self.expected_intervals,
            "measurement_records": len(self.records),
            "missing_measurements": sum(r.energy_mwh is None for r in self.records),
            "first_interval_start_utc": intervals[0].interval_start_utc.isoformat(),
            "last_interval_end_utc": intervals[-1].interval_end_utc.isoformat(),
            "non_96_interval_days": {
                day.isoformat(): count for day, count in sorted(daily.items()) if count != 96
            },
            "end_label_warning_count": len(self.warnings),
            "end_label_warnings": [
                {
                    "rule": "source_wall_clock_end_at_dst_transition",
                    "source_row": warning.source_row,
                    "original_end_label": warning.original_end_label,
                    "canonical_local_end": warning.canonical_local_end,
                    "canonical_utc_end": warning.canonical_utc_end,
                }
                for warning in self.warnings
            ],
        }


def parse_timestamp_label(value: str) -> datetime:
    """Parse an English SMARD label independently of the machine's locale.

    The result is naive wall-clock text, not yet an instant. In particular,
    attaching a timezone to a repeated autumn label alone would be ambiguous.
    """
    match = LABEL.fullmatch(value)
    if match is None:
        raise TimeNormalizationError(f"Invalid timestamp label {value!r}")
    month, day, year, hour, minute, meridiem = match.groups()
    try:
        return datetime(
            int(year),
            MONTHS[month],
            int(day),
            int(hour) % 12 + (12 if meridiem == "PM" else 0),
            int(minute),
        )
    except (KeyError, ValueError) as exc:
        raise TimeNormalizationError(f"Invalid timestamp label {value!r}") from exc


def normalize_file(path: Path, *, start_date: date, end_date: date) -> NormalizationResult:
    """Validate and normalize a complete local-date range [start_date, end_date).

    Every start label must match the requested UTC grid in original row order.
    Source end labels must match either the canonical end or the documented
    wall-clock addition at an actual offset transition. All other disagreements
    fail. Missing energy values remain present as slots and retain None values.

    This function holds one file's normalized records in memory and returns them
    only after final row-count validation. Future bulk ingestion can stage rows
    transactionally instead; callers must not silently accept truncated grids.
    """
    if type(start_date) is not date or type(end_date) is not date:
        raise TimeNormalizationError("Period boundaries must be dates, not datetimes")
    if end_date <= start_date:
        raise TimeNormalizationError("end_date must be after start_date (exclusive)")
    zone = ZoneInfo(SOURCE_TIMEZONE)
    start_utc = datetime.combine(start_date, time.min, tzinfo=zone).astimezone(UTC)
    end_utc = datetime.combine(end_date, time.min, tzinfo=zone).astimezone(UTC)
    expected = (end_utc - start_utc) // INTERVAL
    if end_utc - start_utc != expected * INTERVAL:
        raise TimeNormalizationError("Requested period does not align to 15-minute UTC intervals")
    normalized = []
    warnings = []
    row_count = 0
    groups = groupby(iter_generation(path), key=attrgetter("source_row"))
    for index, (row_number, group) in enumerate(groups):
        records = tuple(group)
        first = records[0]
        context = f"{path}: row {row_number}"
        if index >= expected:
            raise TimeNormalizationError(f"{context}: extra row beyond requested period")
        try:
            original_start = parse_timestamp_label(first.start_label)
            original_end = parse_timestamp_label(first.end_label)
        except TimeNormalizationError as exc:
            raise TimeNormalizationError(f"{context}: {exc}") from exc
        utc_start = start_utc + index * INTERVAL
        utc_end = utc_start + INTERVAL
        local_start = utc_start.astimezone(zone)
        local_end = utc_end.astimezone(zone)
        if original_start != local_start.replace(tzinfo=None):
            raise TimeNormalizationError(
                f"{context}: start label {first.start_label!r} does not match expected "
                f"{local_start.isoformat()}; missing, duplicated, reordered, or wrong-period row"
            )
        if original_end != local_end.replace(tzinfo=None):
            is_transition = local_start.utcoffset() != local_end.utcoffset()
            if not is_transition or original_end != original_start + INTERVAL:
                raise TimeNormalizationError(
                    f"{context}: end label {first.end_label!r} does not match expected "
                    f"{local_end.isoformat()} or the known transition convention"
                )
            warnings.append(
                EndLabelWarning(
                    row_number, first.end_label, local_end.isoformat(), utc_end.isoformat()
                )
            )
        normalized.extend(
            NormalizedGenerationRecord(
                source=r.source,
                start_label=r.start_label,
                end_label=r.end_label,
                energy_mwh=r.energy_mwh,
                source_file=r.source_file,
                source_row=r.source_row,
                interval_start_utc=utc_start,
                interval_end_utc=utc_end,
            )
            for r in records
        )
        row_count += 1
    if row_count != expected:
        raise TimeNormalizationError(
            f"{path}: expected {expected} rows for [{start_date}, {end_date}), got {row_count}; "
            "file is incomplete"
        )
    return NormalizationResult(
        str(path), start_date, end_date, tuple(normalized), tuple(warnings), expected
    )
