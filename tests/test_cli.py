"""Exercise the installed CLI contract, including the generated console script."""

import shutil
import subprocess
import sys
from importlib.metadata import version

import pytest


@pytest.fixture(params=["module", "console"])
def command(request: pytest.FixtureRequest) -> list[str]:
    if request.param == "module":
        return [sys.executable, "-m", "energy_ops"]
    executable = shutil.which("energy-ops")
    assert executable is not None, "Install the package before testing its console entry point."
    return [executable]


def test_version_matches_installed_distribution(command: list[str]) -> None:
    result = subprocess.run([*command, "--version"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert result.stdout.strip() == f"energy-ops {version('renewable-energy-operations')}"
    assert result.stderr == ""


@pytest.mark.parametrize("arguments", [[], ["--help"]])
def test_help_is_available(command: list[str], arguments: list[str]) -> None:
    result = subprocess.run([*command, *arguments], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "usage: energy-ops" in result.stdout
    assert "Ingestion is not implemented yet." in result.stdout


def test_unknown_option_is_rejected(command: list[str]) -> None:
    result = subprocess.run(
        [*command, "--unknown-option"], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
