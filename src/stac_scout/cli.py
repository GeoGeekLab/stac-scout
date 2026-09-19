from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from stac_scout import __version__
from stac_scout.models import ScoutRequest

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command("version")
def version() -> None:
    console.print(__version__)


@app.command("validate-request")
def validate_request(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        request = ScoutRequest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        console.print(f"[red]invalid request[/red]: {exc}", highlight=False)
        raise typer.Exit(code=2) from exc

    console.print_json(request.model_dump_json(indent=2))


@app.command("schema")
def schema(
    target: Annotated[str, typer.Argument(help="Schema name. Currently: request")],
) -> None:
    if target != "request":
        console.print(f"[red]unknown schema[/red]: {target}", highlight=False)
        raise typer.Exit(code=2)

    console.print_json(json.dumps(ScoutRequest.model_json_schema(), indent=2))


if __name__ == "__main__":
    app()
