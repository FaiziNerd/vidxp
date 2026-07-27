from __future__ import annotations

import os
import sys
from pathlib import Path
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
    if effective_output_format(state, json_output) == OutputFormat.json:
        emit_json(result)
    else:
        typer.secho(
            "Selected VidXP runtime models are prepared.",
            fg=typer.colors.GREEN,
            bold=True,
        )


def ui(ctx: typer.Context) -> None:
    """Launch Streamlit with the selected repository configuration."""

    state = state_from_context(ctx)
    os.environ["VIDXP_CONFIG_FILE"] = str(state.registry.path)
    os.environ["VIDXP_REPOSITORY"] = state.repository.name
    os.environ["VIDXP_INDEX_DIR"] = str(state.service.index_directory)
    if state.service.device is None:
        os.environ.pop("VIDXP_DEVICE", None)
    else:
        os.environ["VIDXP_DEVICE"] = state.service.device

    try:
        from vidxp import frontend
    except ModuleNotFoundError as exc:
        if exc.name == "streamlit":
            raise RuntimeError(
                "The browser interface requires the frontend extra. "
                "Install vidxp[frontend]."
            ) from exc
        raise

    frontend.SERVICE = state.service
    frontend.SAVED_VIDEO_PATH = (
        state.service.index_directory / "source-video.mp4"
    )
    frontend.ACTOR_OUTPUT_PATH = (
        state.service.index_directory / "actor-result.mp4"
    )
    sys.argv = [sys.argv[0]]
    frontend.main()
