"""Command-line entry point; ingestion commands will be added next."""

import argparse
from collections.abc import Sequence

from energy_ops import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Show the available interface without starting any external services."""
    parser = argparse.ArgumentParser(
        prog="energy-ops",
        description="Renewable-generation data operations. Ingestion is not implemented yet.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
