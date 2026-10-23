"""Command-line entry point for local data inspection."""

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
    """Validate CSVs locally without starting external services."""
    parser = argparse.ArgumentParser(
        prog="energy-ops",
        description="Renewable-generation data operations: inspect SMARD CSV files locally.",
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
    args = parser.parse_args(argv)
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
