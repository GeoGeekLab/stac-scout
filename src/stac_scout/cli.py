from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel, ValidationError
from rich.console import Console

from stac_scout import __version__
from stac_scout.catalogs import GenericStacAdapter, inspect_catalog
from stac_scout.models import Manifest, ScoutRequest
from stac_scout.planning import odc_stac_recipe
from stac_scout.provenance import read_manifest, replay_manifest, write_manifest
from stac_scout.scout import ScoutEngine

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _load_request(path: Path) -> ScoutRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ScoutRequest.model_validate(payload)


def _print_json(value: Any) -> None:
    if hasattr(value, "model_dump_json"):
        console.print_json(value.model_dump_json(indent=2))
        return
    console.print_json(json.dumps(value, indent=2, default=str))


@app.command("version")
def version() -> None:
    console.print(__version__)


@app.command("validate-request")
def validate_request(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    try:
        request = _load_request(path)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        console.print(f"[red]invalid request[/red]: {exc}", highlight=False)
        raise typer.Exit(code=2) from exc

    _print_json(request)


@app.command("inspect-catalog")
def inspect_catalog_command(url: str) -> None:
    _print_json(inspect_catalog(url))


@app.command("discover")
def discover(
    request_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    catalog: Annotated[str, typer.Option("--catalog")],
    limit: Annotated[int, typer.Option(min=1, max=100)] = 10,
) -> None:
    request = _load_request(request_path)
    engine = ScoutEngine(GenericStacAdapter(catalog))
    results = engine.discover(request, limit=limit)
    payload = [
        {
            "collection_id": result.dataset.collection_id,
            "title": result.dataset.title,
            "score": result.score,
            "constraints": [check.model_dump(mode="json") for check in result.constraints],
        }
        for result in results
    ]
    _print_json(payload)


@app.command("verify")
def verify(
    request_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    collection: Annotated[str, typer.Option("--collection")],
    catalog: Annotated[str, typer.Option("--catalog")],
    max_items: Annotated[int, typer.Option(min=1, max=10_000)] = 100,
) -> None:
    request = _load_request(request_path)
    _, probe = ScoutEngine(GenericStacAdapter(catalog)).verify(
        request,
        collection,
        max_items=max_items,
    )
    _print_json(probe)


@app.command("plan")
def plan(
    request_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    collection: Annotated[str, typer.Option("--collection")],
    catalog: Annotated[str, typer.Option("--catalog")],
    manifest_path: Annotated[Path | None, typer.Option("--manifest")] = None,
    recipe_path: Annotated[Path | None, typer.Option("--recipe")] = None,
    max_items: Annotated[int, typer.Option(min=1, max=10_000)] = 100,
) -> None:
    request = _load_request(request_path)
    result = ScoutEngine(GenericStacAdapter(catalog)).plan(
        request,
        collection,
        max_items=max_items,
    )
    if manifest_path is not None:
        write_manifest(result.manifest, manifest_path)
    if recipe_path is not None:
        recipe_path.write_text(odc_stac_recipe(result.manifest), encoding="utf-8")

    _print_json(
        {
            "probe": result.probe.model_dump(mode="json"),
            "access_plan": result.access_plan.model_dump(mode="json"),
            "missing_measurements": result.missing_measurements,
            "manifest": result.manifest.model_dump(mode="json"),
        }
    )


@app.command("replay")
def replay(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    max_items: Annotated[int, typer.Option(min=1, max=10_000)] = 100,
) -> None:
    manifest = read_manifest(path)
    result = replay_manifest(
        manifest,
        GenericStacAdapter(manifest.catalog_url),
        max_items=max_items,
    )
    _print_json(
        {
            "probe": result.probe.model_dump(mode="json"),
            "retained_item_ids": result.retained_item_ids,
            "missing_item_ids": result.missing_item_ids,
            "new_item_ids": result.new_item_ids,
        }
    )


@app.command("schema")
def schema(
    target: Annotated[str, typer.Argument(help="Schema name: request or manifest")],
) -> None:
    models: dict[str, type[BaseModel]] = {
        "request": ScoutRequest,
        "manifest": Manifest,
    }
    model = models.get(target)
    if model is None:
        console.print(f"[red]unknown schema[/red]: {target}", highlight=False)
        raise typer.Exit(code=2)

    console.print_json(json.dumps(model.model_json_schema(), indent=2))


if __name__ == "__main__":
    app()
