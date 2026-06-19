"""Smoke tests for package metadata and CLI."""
from __future__ import annotations

from click.testing import CliRunner

import pruvagraph
from pruvagraph.cli import main


def test_version() -> None:
    assert pruvagraph.__version__ == "1.5.0"


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "PruvaGraph" in result.output


def test_report_dashboard_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, [".", "report-dashboard", "--help"])
    assert result.exit_code == 0
    assert "ROI" in result.output or "report-dashboard" in result.output
