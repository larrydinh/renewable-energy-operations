"""Command-line entry point for local data inspection."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from energy_ops import __version__
from energy_ops.smard import SmardParseError, summarize_file


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
    parser.print_help()
    return 0
