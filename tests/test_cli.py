from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from stac_scout.cli import _resolve_adapter, app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.3.0" in result.output


def test_validate_request(tmp_path: Path) -> None:
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
                "data_type": "optical",
                "required_measurements": ["red", "nir"],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate-request", str(path)])

    assert result.exit_code == 0
    assert '"data_type": "optical"' in result.output


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


def test_providers_command_can_include_disabled_registry() -> None:
    result = runner.invoke(app, ["providers", "--all"])

    assert result.exit_code == 0
    assert '"key": "nasa-cmr"' in result.stdout


def test_resolve_adapter_requires_exactly_one_catalog_target() -> None:
    with pytest.raises(typer.BadParameter, match="provide exactly one"):
        _resolve_adapter(None, None)

    with pytest.raises(typer.BadParameter, match="provide exactly one"):
        _resolve_adapter("https://example.test/stac", "earth-search")


def test_discover_rejects_unknown_provider(tmp_path: Path) -> None:
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

    result = runner.invoke(app, ["discover", str(path), "--provider", "missing"])

    assert result.exit_code != 0
    assert "unknown provider" in result.output
