from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vidxp.cli_commands.index import create_index
from vidxp.cli_support import legacy_modalities, state_from_context


def videoindex(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    modalities: Annotated[
        str,
        typer.Option(
            "--modalities",
            "-m",
            help="Comma-separated dialogue, scene, and actor modalities.",
        ),
    ] = "dialogue,scene,actor",
    frame_stride: Annotated[
        int,
        typer.Option("--frame-stride", min=1),
    ] = 1,
) -> None:
    create_index(
        state_from_context(ctx),
        path,
        modalities=legacy_modalities(modalities),
        frame_stride=frame_stride,
    )


def dialogue(
    ctx: typer.Context,
    query: str,
) -> float | None:
    result = state_from_context(ctx).service.search(
        "dialogue",
        query,
        top_k=1,
    )
    if not result.hits:
        typer.echo("No dialogue matches found.")
        return None
    timestamp = result.hits[0].start
    typer.secho(f"{timestamp:.3f} seconds", fg=typer.colors.GREEN, bold=True)
    return timestamp


def scene(
    ctx: typer.Context,
    query: str,
) -> float | None:
    result = state_from_context(ctx).service.search(
        "scene",
        query,
        top_k=1,
    )
    if not result.hits:
        typer.echo("No scene matches found.")
        return None
    timestamp = result.hits[0].start
    typer.secho(f"{timestamp:.3f} seconds", fg=typer.colors.GREEN, bold=True)
    return timestamp


def actor(
    ctx: typer.Context,
    cluster_id: str,
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_path: Path = Path("output.mp4"),
) -> None:
    state = state_from_context(ctx)
    result = state.service.render_actor(
        cluster_id,
        input_path,
        output_path,
    )
    typer.secho(
        f"Video saved as {result.output_path}",
        fg=typer.colors.GREEN,
    )
