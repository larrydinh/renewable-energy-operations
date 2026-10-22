"""Exercise the installed CLI contract, including the generated console script."""

import json
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

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
    assert "parse-smard" in result.stdout


def test_unknown_option_is_rejected(command: list[str]) -> None:
    result = subprocess.run(
        [*command, "--unknown-option"], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_parse_smard_command(command: list[str]) -> None:
    fixture = Path(__file__).parent / "fixtures" / "smard_actual_generation_sample.csv"
    result = subprocess.run(
        [*command, "parse-smard", str(fixture)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)["files"][0]
    assert report["source_rows"] == 3
    assert report["measurement_records"] == 18
    assert report["sources"]["hydropower"]["missing"] == 2
    assert result.stderr == ""


def test_parse_failure_does_not_emit_partial_report(command: list[str], tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "smard_actual_generation_sample.csv"
    invalid = tmp_path / "invalid.csv"
    invalid.write_text(fixture.read_text() + "wrong;row\n")
    result = subprocess.run(
        [*command, "parse-smard", str(fixture), str(invalid)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "row 5" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_file_reports_friendly_error(command: list[str], tmp_path: Path) -> None:
    result = subprocess.run(
        [*command, "parse-smard", str(tmp_path / "absent.csv")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "absent.csv" in result.stderr
    assert "Traceback" not in result.stderr
