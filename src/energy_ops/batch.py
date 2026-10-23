"""Sequential imports of local SMARD exports with a scheduler-friendly report."""

import re
from datetime import UTC, date, datetime
from pathlib import Path

from psycopg import Error as PsycopgError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from energy_ops.ingestion import import_file

EXPORT_PATTERN = "Actual_generation_*_Quarterhour.csv"
DATABASE_ERROR = "Database operation failed; check PostgreSQL and schema initialization."


def export_period(path: Path) -> tuple[date, date]:
    """Read midnight, exclusive-end period boundaries from a SMARD export name."""
    match = re.fullmatch(r"Actual_generation_(\d{12})_(\d{12})_Quarterhour\.csv", path.name)
    if not match:
        raise ValueError("Expected Actual_generation_YYYYMMDD0000_YYYYMMDD0000_Quarterhour.csv")
    try:
        start, end = (datetime.strptime(value, "%Y%m%d%H%M") for value in match.groups())
    except ValueError as exc:
        raise ValueError("Export filename contains an invalid calendar timestamp") from exc
    if any(value.hour or value.minute for value in (start, end)):
        raise ValueError("Export filename boundaries must be local midnight")
    if end <= start:
        raise ValueError("Export end must be after its start")
    return start.date(), end.date()


def import_directory(engine: Engine, directory: Path) -> dict:
    """Attempt every matching file; commit each independently and retain failures.

    No correction approval is inferred for a whole directory. Conflicting values
    require review and the existing single-file --accept-corrections command.
    """
    if not directory.is_dir():
        raise ValueError(f"Not a readable export directory: {directory}")
    files = sorted(directory.glob(EXPORT_PATTERN))
    if not files:
        raise ValueError(f"No files matching {EXPORT_PATTERN} in {directory}")
    started = datetime.now(UTC).isoformat()
    results = []
    for path in files:
        result = {"filename": path.name}
        try:
            start, end = export_period(path)
            result.update(start_date=start.isoformat(), end_date=end.isoformat())
            result.update(import_file(engine, path, start_date=start, end_date=end))
        except (SQLAlchemyError, PsycopgError):
            # Database exceptions can include connection strings or query parameters.
            result.update(status="failed", error=DATABASE_ERROR)
        except (ValueError, OSError, RuntimeError) as exc:
            result.update(status="failed", error=str(exc))
        results.append(result)
    counts = {
        status: sum(result["status"] == status for result in results)
        for status in ("succeeded", "no_change", "failed")
    }
    return {
        "status": "failed" if counts["failed"] else "succeeded",
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "total_files": len(results),
        **counts,
        "inserted": sum(result.get("inserted", 0) for result in results),
        "updated": sum(result.get("updated", 0) for result in results),
        "files": results,
    }
