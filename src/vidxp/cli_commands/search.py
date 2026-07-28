from __future__ import annotations

from typing import Annotated

import typer

from vidxp.cli_support import (
    CLIState,
    effective_output_format,
    emit_search,
    state_from_context,
)
from vidxp.core.contracts import SearchResult


app = typer.Typer(no_args_is_help=True, help="Search the active index.")


def run_search(
    state: CLIState,
    modality: str,
    query: str,
    *,
    top_k: int,
    json_output: bool,
) -> SearchResult:
    result = state.service.search(modality, query, top_k=top_k)
    emit_search(
        result,
        output_format=effective_output_format(state, json_output),
    )
    return result


@app.command("dialogue")
def search_dialogue_command(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Dialogue text to find.")],
    top_k: Annotated[
        int,
        typer.Option("--top-k", "-k", min=1, help="Maximum ranked hits."),
    ] = 10,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Find ranked intervals matching spoken dialogue."""

    run_search(
        state_from_context(ctx),
        "dialogue",
        query,
        top_k=top_k,
        json_output=json_output,
    )


@app.command("scene")
def search_scene_command(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Visual description to find.")],
    top_k: Annotated[
        int,
        typer.Option("--top-k", "-k", min=1, help="Maximum ranked hits."),
    ] = 10,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Find ranked intervals matching a visual description."""

    run_search(
        state_from_context(ctx),
        "scene",
        query,
        top_k=top_k,
        json_output=json_output,
    )
