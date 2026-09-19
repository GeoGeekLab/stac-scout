from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from stac_scout.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


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
    assert '"data_type": "optical"' in result.stdout


def test_validate_request_rejects_invalid_input(tmp_path: Path) -> None:
    path = tmp_path / "request.json"
    path.write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["validate-request", str(path)])

    assert result.exit_code == 2
    assert "invalid request" in result.stdout
