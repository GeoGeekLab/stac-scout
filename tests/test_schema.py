from __future__ import annotations

from typer.testing import CliRunner

from stac_scout.cli import app

runner = CliRunner()


def test_request_schema_command() -> None:
    result = runner.invoke(app, ["schema", "request"])

    assert result.exit_code == 0
    assert '"title": "ScoutRequest"' in result.stdout


def test_intent_schema_command() -> None:
    result = runner.invoke(app, ["schema", "intent"])

    assert result.exit_code == 0
    assert '"title": "IntentDraft"' in result.stdout


def test_task_advice_schema_command() -> None:
    result = runner.invoke(app, ["schema", "task-advice"])

    assert result.exit_code == 0
    assert '"title": "TaskAdvice"' in result.stdout


def test_manifest_schema_command() -> None:
    result = runner.invoke(app, ["schema", "manifest"])

    assert result.exit_code == 0
    assert '"title": "Manifest"' in result.stdout
    assert '"schema_version"' in result.stdout


def test_unknown_schema_fails() -> None:
    result = runner.invoke(app, ["schema", "missing"])

    assert result.exit_code == 2
    assert "unknown schema" in result.stdout
