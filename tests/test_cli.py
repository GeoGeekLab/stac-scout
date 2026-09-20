from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from stac_scout import __version__
from stac_scout.cli import _resolve_adapter, app

runner = CliRunner()


def _request_file(tmp_path: Path) -> Path:
    path = tmp_path / "request.json"
    path.write_text(
        json.dumps(
            {
                "task": "vegetation analysis",
                "place": "Singapore",
                "datetime": {
                    "start": "2026-06-01T00:00:00Z",
                    "end": "2026-06-30T23:59:59Z",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_validate_request(tmp_path: Path) -> None:
    path = _request_file(tmp_path)

    result = runner.invoke(app, ["validate-request", str(path)])

    assert result.exit_code == 0
    assert '"task": "vegetation analysis"' in result.output


def test_validate_request_rejects_invalid_input(tmp_path: Path) -> None:
    path = tmp_path / "request.json"
    path.write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["validate-request", str(path)])

    assert result.exit_code == 2
    assert "invalid request" in result.stdout


def test_providers_command_lists_enabled_registry() -> None:
    result = runner.invoke(app, ["providers"])

    assert result.exit_code == 0
    assert '"key": "earth-search"' in result.stdout
    assert '"key": "planetary-computer"' in result.stdout
    assert '"key": "nasa-cmr"' not in result.stdout


def test_tasks_command_lists_task_registry() -> None:
    result = runner.invoke(app, ["tasks"])

    assert result.exit_code == 0
    assert '"task_type": "wildfire_impact"' in result.stdout
    assert '"task_type": "flood_extent"' in result.stdout


def test_task_profile_command() -> None:
    result = runner.invoke(app, ["task-profile", "snow_cover"])

    assert result.exit_code == 0
    assert '"required_measurements"' in result.stdout
    assert '"green"' in result.stdout
    assert '"swir16"' in result.stdout


def test_advise_command_derives_requirements(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["advise", str(_request_file(tmp_path)), "--task", "vegetation_condition"],
    )

    assert result.exit_code == 0
    assert '"data_type": "optical"' in result.stdout
    assert '"red"' in result.stdout
    assert '"nir"' in result.stdout


def test_resolve_adapter_requires_exactly_one_catalog_target() -> None:
    with pytest.raises(typer.BadParameter, match="provide exactly one"):
        _resolve_adapter(None, None)

    with pytest.raises(typer.BadParameter, match="provide exactly one"):
        _resolve_adapter("https://example.test/stac", "earth-search")


def test_discover_rejects_unknown_provider(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["discover", str(_request_file(tmp_path)), "--provider", "missing"],
    )

    assert result.exit_code != 0
    assert "unknown provider" in result.output


def test_federate_cli_exposes_execution_controls() -> None:
    root = typer.main.get_command(app)
    command = root.get_command(None, "federate")

    assert command is not None
    parameter_names = {parameter.name for parameter in command.params}
    assert {"max_workers", "overall_timeout"} <= parameter_names
