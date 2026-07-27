from __future__ import annotations

from typing import Annotated

import typer

from vidxp.cli_support import (
    OutputFormat,
    effective_output_format,
    emit_json,
    legacy_modalities,
    state_from_context,
)


def doctor(
    ctx: typer.Context,
    modalities: Annotated[
        str,
        typer.Option(
            "--modalities",
            "-m",
            help="Only validate dependencies for these modalities.",
        ),
    ] = "dialogue,scene,actor",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Validate selected indexing dependencies without downloading models."""

    selected = legacy_modalities(modalities)
    state = state_from_context(ctx)
    result = state.service.check_dependencies(selected)
    if effective_output_format(state, json_output) == OutputFormat.json:
        emit_json(result)
    else:
        for check in result["checks"]:
            if check["ok"]:
                detail = f": {check['path']}" if check.get("path") else ""
                typer.secho(
                    f"OK {check['name']}{detail}",
                    fg=typer.colors.GREEN,
                )
            else:
                typer.secho(
                    f"FAILED {check['name']}: {check['error']}",
                    fg=typer.colors.RED,
                )
    if not result["ok"]:
        raise typer.Exit(1)
    if effective_output_format(state, json_output) == OutputFormat.rich:
        typer.secho(
            "Selected VidXP dependencies are available.",
            fg=typer.colors.GREEN,
            bold=True,
        )


def prepare(
    ctx: typer.Context,
    modalities: Annotated[
        str,
        typer.Option(
            "--modalities",
            "-m",
            help="Only prepare models for these modalities.",
        ),
    ] = "dialogue,scene",
    language: Annotated[
        str | None,
        typer.Option(
            "--language",
            "-l",
            help="Also cache the WhisperX alignment model for this language.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Download and cache selected runtime models before indexing."""

    selected = legacy_modalities(modalities)
    state = state_from_context(ctx)
    try:
        result = state.service.prepare_models(
            selected,
            language=language,
            progress_callback=(
                None
                if state.quiet
                or effective_output_format(state, json_output)
                == OutputFormat.json
                else lambda event: typer.echo(event["message"])
            ),
        )
    except Exception as exc:
        typer.secho(
            f"Model preparation failed: {type(exc).__name__}: {exc}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1) from exc
    if effective_output_format(state, json_output) == OutputFormat.json:
        emit_json(result)
    else:
        typer.secho(
            "Selected VidXP runtime models are prepared.",
            fg=typer.colors.GREEN,
            bold=True,
        )
