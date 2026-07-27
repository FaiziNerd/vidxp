from __future__ import annotations

from pathlib import Path
from typing import Annotated, Iterable

import typer

from vidxp.cli_support import (
    CLIState,
    IndexProgress,
    OutputFormat,
    effective_output_format,
    emit_json,
    emit_status,
    selected_modalities,
    state_from_context,
)


app = typer.Typer(no_args_is_help=True, help="Manage a local video index.")


def create_index(
    state: CLIState,
    path: Path,
    *,
    modalities: Iterable[str],
    frame_stride: int,
) -> dict:
    show_progress = (
        not state.quiet and state.output_format == OutputFormat.rich
    )
    with IndexProgress(show_progress) as progress:
        summary = state.service.create_index(
            path,
            modalities=modalities,
            frame_stride=frame_stride,
            progress_callback=progress.update,
        )
    if state.output_format == OutputFormat.json:
        emit_json(summary)
    else:
        typer.secho(
            "Video indexing completed successfully.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    return summary


@app.command("create")
def index_create(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Local video file to index.",
        ),
    ],
    modalities: Annotated[
        list[str] | None,
        typer.Option(
            "--modality",
            "-m",
            help="Modality to index; repeat to select more than one.",
        ),
    ] = None,
    frame_stride: Annotated[
        int,
        typer.Option(
            "--frame-stride",
            min=1,
            help="Materialize every Nth frame for visual modalities.",
        ),
    ] = 1,
) -> None:
    """Create or replace a local index for one video."""

    state = state_from_context(ctx)
    create_index(
        state,
        path,
        modalities=selected_modalities(modalities),
        frame_stride=frame_stride,
    )


@app.command("status")
def index_status(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Show the state and source of the selected index."""

    state = state_from_context(ctx)
    emit_status(
        state.service.index_status(),
        output_format=effective_output_format(state, json_output),
    )


@app.command("clear")
def index_clear(
    ctx: typer.Context,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Clear indexed records and VidXP run state."""

    state = state_from_context(ctx)
    if not yes:
        typer.confirm(
            f"Clear the local index at {state.service.index_directory}?",
            abort=True,
        )
    cleared = state.service.clear_index()
    payload = {
        "cleared": cleared,
        "index_directory": str(state.service.index_directory),
    }
    if effective_output_format(state, json_output) == OutputFormat.json:
        emit_json(payload)
    else:
        typer.echo("Index cleared." if cleared else "No index was found.")
