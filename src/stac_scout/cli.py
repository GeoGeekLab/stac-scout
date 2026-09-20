from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Never

import typer
from pydantic import BaseModel, ValidationError
from rich.console import Console

from stac_scout import __version__
from stac_scout.catalogs import CatalogAdapter, GenericStacAdapter, build_adapter, inspect_catalog
from stac_scout.constraints import ConstraintViolationError
from stac_scout.federation import FederatedScout
from stac_scout.health import check_providers
from stac_scout.models import (
    IntentDraft,
    Manifest,
    ProviderSpec,
    ScoutRequest,
    TaskAdvice,
    TaskProfile,
)
from stac_scout.planning import odc_stac_recipe
from stac_scout.provenance import read_manifest, replay_manifest, write_manifest
from stac_scout.reasoning import intent_instructions
from stac_scout.registry import ProviderRegistry, UnknownProviderError
from stac_scout.scout import ScoutEngine
from stac_scout.tasking import TaskAdvisor
from stac_scout.tasks import TaskRegistry

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


def _constraint_violation(exc: ConstraintViolationError) -> Never:
    _print_json(
        {
            "error": str(exc),
            "constraints": [check.model_dump(mode="json") for check in exc.checks],
        }
    )
    raise typer.Exit(code=2)


def _provider(key: str, *, catalog_url: str | None = None) -> ProviderSpec:
    registry = ProviderRegistry.builtin()
    try:
        provider = registry.get(key)
    except UnknownProviderError as exc:
        raise typer.BadParameter(f"unknown provider: {key}") from exc
    if not provider.enabled:
        raise typer.BadParameter(f"provider is disabled: {key}")
    if catalog_url is not None:
        provider = provider.model_copy(update={"url": catalog_url})
    return provider


def _resolve_adapter(catalog: str | None, provider: str | None) -> CatalogAdapter:
    if (catalog is None) == (provider is None):
        raise typer.BadParameter("provide exactly one of --catalog or --provider")
    if provider is not None:
        return build_adapter(_provider(provider))
    assert catalog is not None
    return GenericStacAdapter(catalog)


def _adapter_for_manifest(manifest: Manifest) -> CatalogAdapter:
    if manifest.provider_key is None:
        return GenericStacAdapter(manifest.catalog_url)
    provider = _provider(manifest.provider_key, catalog_url=manifest.catalog_url)
    return build_adapter(provider)


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


@app.command("providers")
def providers(
    include_disabled: Annotated[bool, typer.Option("--all")] = False,
) -> None:
    registry = ProviderRegistry.builtin()
    _print_json(
        [
            provider.model_dump(mode="json")
            for provider in registry.all(include_disabled=include_disabled)
        ]
    )


@app.command("tasks")
def tasks() -> None:
    _print_json([profile.model_dump(mode="json") for profile in TaskRegistry.builtin().all()])


@app.command("task-profile")
def task_profile(task: str) -> None:
    try:
        profile = TaskRegistry.builtin().get(task)
    except ValueError as exc:
        raise typer.BadParameter(f"unknown task: {task}") from exc
    _print_json(profile)


@app.command("advise")
def advise(
    request_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    task: Annotated[str, typer.Option("--task")],
) -> None:
    request = _load_request(request_path)
    try:
        advice = TaskAdvisor().advise(request, task)
    except ValueError as exc:
        raise typer.BadParameter(f"unknown task: {task}") from exc
    _print_json(advice)


@app.command("advise-intent")
def advise_intent(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    try:
        draft = IntentDraft.model_validate_json(path.read_text(encoding="utf-8"))
        request = draft.to_request()
    except (OSError, ValidationError, ValueError) as exc:
        console.print(f"[red]unresolved intent[/red]: {exc}", highlight=False)
        raise typer.Exit(code=2) from exc

    if draft.task_type is None:
        console.print("[red]unresolved intent[/red]: task_type is required", highlight=False)
        raise typer.Exit(code=2)

    _print_json(TaskAdvisor().advise(request, draft.task_type))


@app.command("intent-contract")
def intent_contract() -> None:
    _print_json(
        {
            "instructions": intent_instructions(),
            "schema": IntentDraft.model_json_schema(),
        }
    )


@app.command("resolve-intent")
def resolve_intent(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    try:
        draft = IntentDraft.model_validate_json(path.read_text(encoding="utf-8"))
        request = draft.to_request()
    except (OSError, ValidationError, ValueError) as exc:
        console.print(f"[red]unresolved intent[/red]: {exc}", highlight=False)
        raise typer.Exit(code=2) from exc
    _print_json(request)


@app.command("health")
def health(
    provider: Annotated[list[str] | None, typer.Option("--provider")] = None,
    include_disabled: Annotated[bool, typer.Option("--all")] = False,
    timeout: Annotated[float, typer.Option(min=0.1, max=120.0)] = 10.0,
) -> None:
    registry = ProviderRegistry.builtin()
    try:
        selected = (
            registry.select(provider)
            if provider is not None
            else registry.all(include_disabled=include_disabled)
        )
    except (UnknownProviderError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    health = check_providers(selected, timeout=timeout)
    _print_json([item.model_dump(mode="json") for item in health])


@app.command("discover")
def discover(
    request_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    catalog: Annotated[str | None, typer.Option("--catalog")] = None,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    limit: Annotated[int, typer.Option(min=1, max=100)] = 10,
) -> None:
    request = _load_request(request_path)
    engine = ScoutEngine(_resolve_adapter(catalog, provider))
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


@app.command("federate")
def federate(
    request_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    provider: Annotated[list[str] | None, typer.Option("--provider")] = None,
    per_provider_limit: Annotated[int, typer.Option(min=1, max=100)] = 10,
    limit: Annotated[int, typer.Option(min=1, max=500)] = 20,
    max_workers: Annotated[int, typer.Option(min=1, max=32)] = 4,
    overall_timeout: Annotated[float, typer.Option(min=0.1, max=300.0)] = 30.0,
) -> None:
    request = _load_request(request_path)
    registry = ProviderRegistry.builtin()
    try:
        scout = FederatedScout.from_registry(registry, provider)
    except (UnknownProviderError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    result = scout.discover(
        request,
        per_provider_limit=per_provider_limit,
        limit=limit,
        max_workers=max_workers,
        overall_timeout_s=overall_timeout,
    )
    _print_json(
        {
            "candidates": [
                {
                    "provider": candidate.provider_key,
                    "collection_id": candidate.dataset.collection_id,
                    "title": candidate.dataset.title,
                    "score": candidate.score,
                    "identity": candidate.identity.model_dump(mode="json"),
                    "constraints": [
                        check.model_dump(mode="json") for check in candidate.constraints
                    ],
                }
                for candidate in result.candidates
            ],
            "duplicate_groups": [
                {
                    "identity": group.identity.model_dump(mode="json"),
                    "safe_to_collapse": group.safe_to_collapse,
                    "candidates": [
                        {
                            "provider": candidate.provider_key,
                            "collection_id": candidate.dataset.collection_id,
                        }
                        for candidate in group.candidates
                    ],
                }
                for group in result.duplicate_groups
            ],
            "failures": [
                {
                    "provider": failure.provider_key,
                    "error_type": failure.error_type,
                    "message": failure.message,
                    "status_code": failure.status_code,
                    "retryable": failure.retryable,
                }
                for failure in result.failures
            ],
        }
    )


@app.command("verify")
def verify(
    request_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    collection: Annotated[str, typer.Option("--collection")],
    catalog: Annotated[str | None, typer.Option("--catalog")] = None,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    max_items: Annotated[int | None, typer.Option(min=1, max=10_000)] = None,
) -> None:
    request = _load_request(request_path)
    try:
        _, probe = ScoutEngine(_resolve_adapter(catalog, provider)).verify(
            request,
            collection,
            max_items=max_items,
        )
    except ConstraintViolationError as exc:
        _constraint_violation(exc)
    _print_json(probe)


@app.command("plan")
def plan(
    request_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    collection: Annotated[str, typer.Option("--collection")],
    catalog: Annotated[str | None, typer.Option("--catalog")] = None,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    manifest_path: Annotated[Path | None, typer.Option("--manifest")] = None,
    recipe_path: Annotated[Path | None, typer.Option("--recipe")] = None,
    max_items: Annotated[int, typer.Option(min=1, max=10_000)] = 100,
) -> None:
    request = _load_request(request_path)
    try:
        result = ScoutEngine(_resolve_adapter(catalog, provider)).plan(
            request,
            collection,
            max_items=max_items,
        )
    except ConstraintViolationError as exc:
        _constraint_violation(exc)
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
        _adapter_for_manifest(manifest),
        max_items=max_items,
    )
    _print_json(
        {
            "probe": result.probe.model_dump(mode="json"),
            "search": result.search.model_dump(mode="json"),
            "comparison_status": result.comparison_status.value,
            "retained_item_ids": result.retained_item_ids,
            "missing_item_ids": result.missing_item_ids,
            "new_item_ids": result.new_item_ids,
            "unresolved_missing_item_ids": result.unresolved_missing_item_ids,
            "unresolved_new_item_ids": result.unresolved_new_item_ids,
            "collection_changed": result.collection_changed,
            "warnings": result.warnings,
        }
    )


@app.command("schema")
def schema(
    target: Annotated[
        str,
        typer.Argument(help="Schema name: request, intent, task-profile, task-advice, or manifest"),
    ],
) -> None:
    models: dict[str, type[BaseModel]] = {
        "request": ScoutRequest,
        "intent": IntentDraft,
        "task-profile": TaskProfile,
        "task-advice": TaskAdvice,
        "manifest": Manifest,
    }
    model = models.get(target)
    if model is None:
        console.print(f"[red]unknown schema[/red]: {target}", highlight=False)
        raise typer.Exit(code=2)

    console.print_json(json.dumps(model.model_json_schema(), indent=2))


if __name__ == "__main__":
    app()
