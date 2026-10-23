"""Transactional, audited publication of normalized local SMARD exports."""

import hashlib
import json
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from energy_ops.time_normalization import POLICY_VERSION, normalize_file

# One publication at a time in this single-dataset local application.
IMPORT_LOCK = 2026102301


def import_file(
    engine: Engine,
    path: Path,
    *,
    start_date: date,
    end_date: date,
    accept_corrections: bool = False,
) -> dict[str, object]:
    """Publish all rows atomically; preserve failures and previous changed values.

    Changed known values require explicit approval. Missing incoming values never
    erase known observations. This is local CLI ingestion, not a durable scheduler.
    """
    run_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO import_runs (id, filename, policy_version, start_date, end_date, status)
            VALUES (:id, :filename, :policy, :start, :end, 'running')
        """),
            {
                "id": run_id,
                "filename": path.name,
                "policy": POLICY_VERSION,
                "start": start_date,
                "end": end_date,
            },
        )
    try:
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": IMPORT_LOCK})
            previous = (
                conn.execute(
                    text("""
                SELECT * FROM import_runs WHERE checksum = :checksum
                AND policy_version = :policy AND start_date = :start AND end_date = :end
                AND status IN ('succeeded', 'no_change') ORDER BY finished_at DESC LIMIT 1
            """),
                    {
                        "checksum": checksum,
                        "policy": POLICY_VERSION,
                        "start": start_date,
                        "end": end_date,
                    },
                )
                .mappings()
                .first()
            )
            if previous:
                conn.execute(
                    text("""
                    UPDATE import_runs SET status='no_change', finished_at=clock_timestamp(),
                    checksum=:checksum, source_rows=:rows, measurement_records=:records,
                    missing_count=:missing, warnings=CAST(:warnings AS jsonb) WHERE id=:id
                """),
                    {
                        "id": run_id,
                        "checksum": checksum,
                        "rows": previous["source_rows"],
                        "records": previous["measurement_records"],
                        "missing": previous["missing_count"],
                        "warnings": json.dumps(previous["warnings"]),
                    },
                )
                return {"run_id": run_id, "status": "no_change", "inserted": 0, "updated": 0}

            result = normalize_file(path, start_date=start_date, end_date=end_date)
            if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                raise ValueError(
                    "Input file changed during normalization; retry with a stable export"
                )
            conn.execute(
                text("""
                CREATE TEMP TABLE import_stage (LIKE generation_intervals INCLUDING DEFAULTS)
                ON COMMIT DROP
            """)
            )
            driver = conn.connection.driver_connection
            with (
                driver.cursor() as cursor,
                cursor.copy("""
                COPY import_stage (source, interval_start_utc, interval_end_utc, energy_mwh,
                    import_run_id, source_row, start_label, end_label, revision_number) FROM STDIN
            """) as copy,
            ):
                for record in result.records:
                    copy.write_row(
                        (
                            record.source,
                            record.interval_start_utc,
                            record.interval_end_utc,
                            record.energy_mwh,
                            run_id,
                            record.source_row,
                            record.start_label,
                            record.end_label,
                            1,
                        )
                    )

            conflict_count = conn.execute(
                text("""
                SELECT count(*) FROM generation_intervals g JOIN import_stage s
                USING (source, interval_start_utc)
                WHERE g.energy_mwh IS NOT NULL AND s.energy_mwh IS NOT NULL
                AND g.energy_mwh IS DISTINCT FROM s.energy_mwh
            """)
            ).scalar_one()
            if conflict_count and not accept_corrections:
                raise ValueError(
                    f"{conflict_count} existing measurements differ. Review the export, then "
                    "use --accept-corrections to explicitly replace them with revision history."
                )
            preserved = conn.execute(
                text("""
                SELECT count(*) FROM generation_intervals g JOIN import_stage s
                USING (source, interval_start_utc)
                WHERE g.energy_mwh IS NOT NULL AND s.energy_mwh IS NULL
            """)
            ).scalar_one()
            conn.execute(
                text("""
                INSERT INTO observation_revisions (
                    source, interval_start_utc, previous_energy_mwh, previous_import_run_id,
                    previous_source_row, previous_start_label, previous_end_label,
                    previous_revision_number, replacement_import_run_id)
                SELECT g.source, g.interval_start_utc, g.energy_mwh, g.import_run_id,
                    g.source_row, g.start_label, g.end_label, g.revision_number, :id
                FROM generation_intervals g JOIN import_stage s USING (source, interval_start_utc)
                WHERE s.energy_mwh IS NOT NULL AND g.energy_mwh IS DISTINCT FROM s.energy_mwh
            """),
                {"id": run_id},
            )
            updated = conn.execute(
                text("""
                UPDATE generation_intervals g SET energy_mwh=s.energy_mwh,
                    import_run_id=s.import_run_id, source_row=s.source_row,
                    start_label=s.start_label, end_label=s.end_label,
                    revision_number=g.revision_number+1
                FROM import_stage s WHERE g.source=s.source
                AND g.interval_start_utc=s.interval_start_utc
                AND s.energy_mwh IS NOT NULL AND g.energy_mwh IS DISTINCT FROM s.energy_mwh
            """)
            ).rowcount
            inserted = conn.execute(
                text("""
                INSERT INTO generation_intervals SELECT * FROM import_stage
                ON CONFLICT (source, interval_start_utc) DO NOTHING
            """)
            ).rowcount
            summary = result.summary()
            status = "succeeded" if inserted or updated else "no_change"
            conn.execute(
                text("""
                UPDATE import_runs SET status=:status, finished_at=clock_timestamp(),
                    checksum=:checksum,
                    source_rows=:rows, measurement_records=:records, inserted_count=:inserted,
                    updated_count=:updated, preserved_count=:preserved, missing_count=:missing,
                    warnings=CAST(:warnings AS jsonb) WHERE id=:id
            """),
                {
                    "id": run_id,
                    "status": status,
                    "checksum": checksum,
                    "rows": summary["source_rows"],
                    "records": summary["measurement_records"],
                    "inserted": inserted,
                    "updated": updated,
                    "preserved": preserved,
                    "missing": summary["missing_measurements"],
                    "warnings": json.dumps(summary["end_label_warnings"]),
                },
            )
            return {
                "run_id": run_id,
                "status": status,
                "inserted": inserted,
                "updated": updated,
                "preserved": preserved,
            }
    except Exception as exc:
        # The publication transaction has rolled back; retain the rejected attempt separately.
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                    UPDATE import_runs SET status='failed', finished_at=clock_timestamp(),
                        error=:error
                    WHERE id=:id
                """),
                    {"id": run_id, "error": str(exc)[:1000]},
                )
        except SQLAlchemyError:
            pass  # A database outage can leave a running row for later reconciliation.
        raise
