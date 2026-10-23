"""Command-line entry point for local data inspection and publication."""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from energy_ops import __version__
from energy_ops.smard import SmardParseError, summarize_file
from energy_ops.time_normalization import TimeNormalizationError, normalize_file


def iso_date(value: str) -> date:
    """Require an explicit YYYY-MM-DD calendar date in CLI arguments."""
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected a date in YYYY-MM-DD format") from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Inspect, normalize, or publish local CSV exports."""
    parser = argparse.ArgumentParser(
        prog="energy-ops",
        description="Renewable-generation data operations for local SMARD exports.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    parse = commands.add_parser("parse-smard", help="Validate CSVs and report per-source counts")
    parse.add_argument("files", nargs="+", type=Path, help="SMARD actual-generation CSV paths")
    normalize = commands.add_parser(
        "normalize-smard", help="Validate a complete local-date period and normalize it to UTC"
    )
    normalize.add_argument("file", type=Path, help="One complete, ordered SMARD CSV export")
    normalize.add_argument(
        "--start-date", required=True, type=iso_date, help="Local start, inclusive"
    )
    normalize.add_argument("--end-date", required=True, type=iso_date, help="Local end, exclusive")
    commands.add_parser("init-db", help="Apply versioned PostgreSQL schema migrations")
    load = commands.add_parser("import-smard", help="Validate and publish one export to PostgreSQL")
    load.add_argument("file", type=Path)
    load.add_argument("--start-date", required=True, type=iso_date)
    load.add_argument("--end-date", required=True, type=iso_date)
    load.add_argument(
        "--accept-corrections",
        action="store_true",
        help="Explicitly replace conflicting known values, retaining revisions",
    )
    batch = commands.add_parser(
        "import-smard-batch", help="Import a directory of exports and report every outcome"
    )
    batch.add_argument(
        "directory", type=Path, help="Directory containing SMARD quarter-hour exports"
    )
    args = parser.parse_args(argv)
    if args.command == "import-smard-batch":
        from energy_ops.batch import import_directory
        from energy_ops.db import get_engine

        try:
            report = import_directory(get_engine(), args.directory)
        except (ValueError, OSError, RuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(report, indent=2))
        return 1 if report["failed"] else 0
    if args.command in ("init-db", "import-smard"):
        from psycopg import Error as PsycopgError
        from sqlalchemy.exc import SQLAlchemyError

        from energy_ops.db import get_engine, upgrade_database
        from energy_ops.ingestion import import_file

        if args.command == "import-smard" and args.end_date <= args.start_date:
            parser.error("--end-date must be after --start-date")
        try:
            engine = get_engine()
            if args.command == "init-db":
                upgrade_database(engine)
                print(json.dumps({"status": "schema_ready"}))
            else:
                outcome = import_file(
                    engine,
                    args.file,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    accept_corrections=args.accept_corrections,
                )
                print(json.dumps(outcome))
            return 0
        except (SQLAlchemyError, PsycopgError):
            print(
                "error: Database operation failed; check PostgreSQL and schema initialization.",
                file=sys.stderr,
            )
            return 1
        except (ValueError, OSError, RuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if args.command == "parse-smard":
        try:
            # Emit nothing until every requested file has passed parsing.
            summaries = [summarize_file(path) for path in args.files]
        except (SmardParseError, OSError, UnicodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps({"files": summaries}, indent=2))
        return 0
    if args.command == "normalize-smard":
        try:
            result = normalize_file(args.file, start_date=args.start_date, end_date=args.end_date)
        except (TimeNormalizationError, SmardParseError, OSError, UnicodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result.summary(), indent=2))
        return 0
    parser.print_help()
    return 0
