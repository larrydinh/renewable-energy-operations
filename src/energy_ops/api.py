"""Read-only local API for committed generation data and import history."""

import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from energy_ops.db import get_engine
from energy_ops.smard import SOURCES

ZONE = ZoneInfo("Europe/Berlin")


class Bucket(StrEnum):
    day = "day"
    month = "month"
    year = "year"


def encoded(value: object) -> object:
    # Preserve exact decimal values in JSON; chart clients explicitly convert to numbers.
    return jsonable_encoder(value, custom_encoder={Decimal: str})


def query_window(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    days = (end_date - start_date).days
    if not 1 <= days <= 1830:
        raise HTTPException(422, "Choose an exclusive date range between 1 and 1830 days")
    return (
        datetime.combine(start_date, time.min, ZONE).astimezone(UTC),
        datetime.combine(end_date, time.min, ZONE).astimezone(UTC),
    )


def create_app(engine: Engine | None = None) -> FastAPI:
    application = FastAPI(title="Renewable Energy Operations", version="0.1.0")

    def connection() -> Iterator[Connection]:
        with (engine or get_engine()).connect() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '15s'"))
            yield conn

    DB = Annotated[Connection, Depends(connection)]

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logging.getLogger(__name__).error("Database request failed", exc_info=exc)
        return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})

    @application.get("/health/live")
    def live():
        return {"status": "ok"}

    @application.get("/health/ready")
    def ready(conn: DB):
        conn.execute(text("SELECT 1 FROM generation_intervals LIMIT 1"))
        return {"status": "ready"}

    @application.get("/v1/overview")
    def overview(conn: DB):
        stats = dict(
            conn.execute(
                text("""
            SELECT count(*) AS measurement_records, count(energy_mwh) AS observed_measurements,
                count(*)-count(energy_mwh) AS unavailable_measurements,
                min(interval_start_utc) FILTER (WHERE energy_mwh IS NOT NULL) AS first_observed_utc,
                max(interval_end_utc) FILTER (WHERE energy_mwh IS NOT NULL) AS latest_observed_utc,
                count(DISTINCT source) AS source_count
            FROM generation_intervals
        """)
            )
            .mappings()
            .one()
        )
        stats["sources"] = [
            dict(row)
            for row in conn.execute(
                text("""
            SELECT source, count(energy_mwh) AS observed,
                max(interval_end_utc) FILTER (WHERE energy_mwh IS NOT NULL) AS latest_observed_utc
            FROM generation_intervals GROUP BY source ORDER BY source
        """)
            ).mappings()
        ]
        stats["successful_imports"] = conn.execute(
            text("""
            SELECT count(*) FROM import_runs WHERE status IN ('succeeded','no_change')
        """)
        ).scalar_one()
        stats["region"] = "Germany"
        stats["timezone"] = "Europe/Berlin"
        stats["unit"] = "MWh"
        return encoded(stats)

    @application.get("/v1/generation/summary")
    def summary(
        start_date: date,
        end_date: date,
        conn: DB,
        bucket: Bucket = Bucket.day,
        sources: Annotated[list[str] | None, Query()] = None,
    ):
        start, end = query_window(start_date, end_date)
        selected = list(dict.fromkeys(sources or SOURCES.values()))
        if any(source not in SOURCES.values() for source in selected):
            raise HTTPException(422, "Unknown renewable source")
        rows = conn.execute(
            text("""
            WITH slots AS (
                SELECT generate_series(CAST(:start AS timestamptz),
                    CAST(:end AS timestamptz)-interval '15 minutes', interval '15 minutes') AS slot
            ), selected AS (SELECT unnest(CAST(:sources AS text[])) AS source)
            SELECT date_trunc(:bucket, slots.slot AT TIME ZONE 'Europe/Berlin')::date
                AS bucket_start,
                selected.source, sum(g.energy_mwh) AS observed_energy_mwh,
                count(*) AS expected_intervals, count(g.energy_mwh) AS observed_intervals
            FROM slots CROSS JOIN selected LEFT JOIN generation_intervals g
                ON g.source=selected.source AND g.interval_start_utc=slots.slot
            GROUP BY 1,2 ORDER BY 1,2
        """),
            {"start": start, "end": end, "sources": selected, "bucket": bucket.value},
        )
        data = []
        for row in rows.mappings():
            item = dict(row)
            item["missing_intervals"] = item["expected_intervals"] - item["observed_intervals"]
            item["coverage_percent"] = round(
                100 * item["observed_intervals"] / item["expected_intervals"], 3
            )
            item["is_complete"] = item["missing_intervals"] == 0
            data.append(item)
        return encoded(
            {
                "unit": "MWh",
                "timezone": "Europe/Berlin",
                "start_date": start_date,
                "end_date_exclusive": end_date,
                "data": data,
            }
        )

    @application.get("/v1/generation/intervals")
    def intervals(
        start_date: date,
        end_date: date,
        source: str,
        conn: DB,
        limit: Annotated[int, Query(ge=1, le=5000)] = 5000,
        offset: Annotated[int, Query(ge=0, le=200000)] = 0,
    ):
        start, end = query_window(start_date, end_date)
        if (end_date - start_date).days > 31:
            raise HTTPException(422, "Interval queries are limited to 31 days")
        if source not in SOURCES.values():
            raise HTTPException(422, "Unknown renewable source")
        rows = conn.execute(
            text("""
            SELECT g.source, g.interval_start_utc, g.interval_end_utc, g.energy_mwh,
                g.source_row, g.start_label, g.end_label, g.revision_number, r.filename,
                g.import_run_id FROM generation_intervals g
            JOIN import_runs r ON r.id=g.import_run_id
            WHERE g.source=:source AND g.interval_start_utc >= :start
                AND g.interval_start_utc < :end
            ORDER BY g.interval_start_utc LIMIT :limit OFFSET :offset
        """),
            {"source": source, "start": start, "end": end, "limit": limit, "offset": offset},
        )
        return encoded(
            {
                "unit": "MWh",
                "limit": limit,
                "offset": offset,
                "data": [dict(row) for row in rows.mappings()],
            }
        )

    @application.get("/v1/runs")
    def runs(conn: DB, limit: Annotated[int, Query(ge=1, le=200)] = 50):
        rows = conn.execute(
            text("""
            SELECT id, filename, start_date, end_date, status, started_at, finished_at,
                source_rows, measurement_records, inserted_count, updated_count, preserved_count,
                missing_count, warnings, error FROM import_runs
            ORDER BY started_at DESC LIMIT :limit
        """),
            {"limit": limit},
        )
        return encoded({"data": [dict(row) for row in rows.mappings()]})

    web = Path(__file__).parent / "web"
    application.mount("/assets", StaticFiles(directory=web), name="assets")

    @application.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(web / "index.html", headers={"Cache-Control": "no-cache"})

    return application


app = create_app()
